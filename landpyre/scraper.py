"""
scraper.py — Scrapes the LANDFIRE full-extent download catalogue.

Returns typed ``CatalogItem`` objects (not raw dicts).  Includes a scraper
health check that validates expected field populations so a Drupal layout
change is caught early rather than silently producing empty data.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import bs4
import requests
from bs4 import BeautifulSoup

from landpyre import __version__
from landpyre.errors import ScraperError
from landpyre.models import CatalogItem

BASE_DOMAIN = "https://www.landfire.gov"
SEARCH_URL = (
    "https://www.landfire.gov/data/FullExtentDownloads"
    "?field_version_target_id=All"
    "&field_theme_target_id=All"
    "&field_region_id_target_id=All"
)

# Known LF version tokens
_VERSION_RE = re.compile(r"(LF\s+\d{4}(?:\s+\w+)*)", re.IGNORECASE)

# Scraper health: minimum fraction of items that must have each field populated.
# If a scrape returns below these thresholds the health check will warn/error.
_HEALTH_THRESHOLDS = {
    "region": 0.50,
    "version": 0.50,
    "download_url": 0.99,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _split_region_version(raw: str | None) -> tuple[str | None, str | None]:
    """
    Parse a raw ``region_version`` string such as ``"Hawaii LF 2022"`` into
    ``("Hawaii", "LF 2022")``.
    """
    if not raw:
        return None, None
    raw = raw.strip()
    match = _VERSION_RE.search(raw)
    if match:
        version = match.group(1).strip()
        region = raw[: match.start()].strip(" -–") or None
        return region or None, version
    return raw or None, None


def _get_last_page_number(base_url: str) -> int:
    test_url = f"{base_url}&page=last"
    try:
        response = requests.get(test_url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ScraperError(f"Failed to probe pagination: {exc}") from exc

    parsed = urlparse(response.url)
    params = parse_qs(parsed.query)
    if "page" in params and params["page"][0].isdigit():
        return int(params["page"][0])

    soup = BeautifulSoup(response.text, "html.parser")
    last_link = soup.find("a", title=re.compile(r"last page", re.I))
    if not last_link:
        last_link = soup.find("a", string=re.compile(r"^Last$", re.I))
    if last_link and last_link.has_attr("href"):
        href_params = parse_qs(urlparse(last_link["href"]).query)
        if "page" in href_params and href_params["page"][0].isdigit():
            return int(href_params["page"][0])

    return 0


def _scrape_page(soup: BeautifulSoup, page_number: int, scrape_ts: datetime) -> list[CatalogItem]:
    items: list[CatalogItem] = []

    download_links = soup.find_all("a", href=re.compile(r"/data-downloads/"))
    for anchor in download_links:
        href: str = anchor.get("href", "")
        download_url = BASE_DOMAIN + href if href.startswith("/") else href

        theme_tag = anchor.find_previous("h3")
        theme = theme_tag.get_text(strip=True) if theme_tag else "Unknown Theme"

        product_tag = anchor.find_previous(["h4", "h5"])
        product = product_tag.get_text(strip=True) if product_tag else "Unknown Product"

        texts: list[str] = []
        for node in anchor.next_elements:
            if isinstance(node, bs4.Tag):
                if node.name == "a" and "data-downloads" in node.get("href", ""):
                    break
                if node.name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                    break
            elif isinstance(node, bs4.NavigableString):
                text_str = str(node).strip()
                if text_str and text_str.lower() != "download":
                    texts.append(text_str)

        text_after = " ".join(texts)

        rv_match = re.search(r"^(.*?)\s*File Size:", text_after, re.IGNORECASE)
        region_version_raw = rv_match.group(1).strip() if rv_match else None

        size_match = re.search(r"File Size:\s*\(?([^)|]+)\)?", text_after, re.IGNORECASE)
        file_size = size_match.group(1).strip() if size_match else None

        chk_match = re.search(r"Checksum:\s*\{?([a-fA-F0-9]+)\}?", text_after, re.IGNORECASE)
        checksum = chk_match.group(1).strip() if chk_match else None

        region, version = _split_region_version(region_version_raw)

        items.append(
            CatalogItem(
                theme=theme,
                product=product,
                region_version=region_version_raw,
                region=region,
                version=version,
                file_size=file_size,
                checksum=checksum,
                download_url=download_url,
                source_page=page_number,
                scrape_timestamp=scrape_ts,
                parser_version=__version__,
            )
        )

    return items


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def check_scraper_health(items: list[CatalogItem]) -> dict[str, Any]:
    """
    Validate that a freshly scraped list of items looks sane.

    Returns a dict with keys:
        ok (bool), warnings (list[str]), item_count (int),
        field_coverage (dict[str, float])
    """
    warnings: list[str] = []
    n = len(items)
    coverage: dict[str, float] = {}

    if n == 0:
        return {
            "ok": False,
            "warnings": ["Scraper returned 0 items — the page structure may have changed."],
            "item_count": 0,
            "field_coverage": {},
        }

    for field, threshold in _HEALTH_THRESHOLDS.items():
        populated = sum(1 for i in items if getattr(i, field, None))
        ratio = populated / n
        coverage[field] = round(ratio, 3)
        if ratio < threshold:
            warnings.append(
                f"Field '{field}' populated in only {ratio:.0%} of items "
                f"(expected ≥ {threshold:.0%}). The page layout may have changed."
            )

    return {
        "ok": len(warnings) == 0,
        "warnings": warnings,
        "item_count": n,
        "field_coverage": coverage,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scrape_catalogue(
    progress_callback: Any | None = None,
) -> list[CatalogItem]:
    """
    Scrape the full LANDFIRE download catalogue and return typed CatalogItems.

    Parameters
    ----------
    progress_callback:
        Optional callable ``(current_page: int, total_pages: int) -> None``.
    """
    last_page = _get_last_page_number(SEARCH_URL)
    total_pages = last_page + 1
    scrape_ts = datetime.now(timezone.utc)

    all_items: list[CatalogItem] = []

    for page in range(total_pages):
        url = f"{SEARCH_URL}&page={page}"
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise ScraperError(f"Failed to fetch page {page}: {exc}") from exc

        soup = BeautifulSoup(resp.text, "html.parser")
        page_items = _scrape_page(soup, page + 1, scrape_ts)
        all_items.extend(page_items)

        if progress_callback:
            progress_callback(page + 1, total_pages)

    return all_items
