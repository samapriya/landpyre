"""
api.py — Public SDK entry point: LandpyreClient.

This is the stable surface external code should use.  The CLI commands are
thin wrappers around this class.  Notebooks, scripts, FastAPI services, and
other tools consume LandpyreClient directly.

Usage
-----
    from landpyre import LandpyreClient

    client = LandpyreClient()

    # Refresh the catalogue
    snapshot = client.refresh()

    # Search
    results = client.search("hawaii fuel 2022")
    for r in results:
        print(r.item.display_label, r.score)

    # Filter precisely
    from landpyre.models import CatalogFilter
    items = client.get_items(CatalogFilter(region="CONUS", version="LF 2022"))

    # Save a manifest
    manifest = client.save_manifest(items, path="conus_2022.json")

    # Download
    results = client.download(items, output_dir=Path("./data"))

    # Verify
    vr = client.verify(manifest, output_dir=Path("./data"))
    print(vr.all_ok)

    # Export
    client.export(items, format="csv", path="catalogue.csv")
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from landpyre import cache as _cache
from landpyre import manifest as _manifest
from landpyre import scraper as _scraper
from landpyre.config import load_config
from landpyre.downloader import download_items, dry_run_summary
from landpyre.models import (
    CatalogFilter,
    CatalogItem,
    CatalogSnapshot,
    DownloadResult,
    ExportFormat,
    Manifest,
    ValidationResult,
)
from landpyre.search import SearchResult, search_catalog
from landpyre.verifier import verify_manifest


class LandpyreClient:
    """
    The primary SDK interface for landpyre.

    All parameters default to values from ``~/.config/landpyre/config.toml``
    so zero-argument usage works out of the box.
    """

    def __init__(
        self,
        cache_dir: Path | str | None = None,
        workers: int | None = None,
    ) -> None:
        cfg = load_config()
        if cache_dir:
            import os
            os.environ["LANDPYRE_CACHE_DIR"] = str(cache_dir)
        self._workers = workers or cfg.default_workers
        self._cfg = cfg

    # -----------------------------------------------------------------------
    # Catalogue
    # -----------------------------------------------------------------------

    def refresh(
        self,
        force: bool = False,
        progress_callback: Any | None = None,
    ) -> CatalogSnapshot:
        """
        Scrape the LANDFIRE catalogue and save to local cache.

        Parameters
        ----------
        force:
            Re-scrape even if a cache already exists.
        progress_callback:
            Optional ``(current_page: int, total_pages: int) -> None``.

        Returns
        -------
        The new CatalogSnapshot.
        """
        if _cache.cache_exists() and not force:
            return _cache.load_cache()

        items = _scraper.scrape_catalogue(progress_callback=progress_callback)
        return _cache.save_cache(items, scrape_url=_scraper.SEARCH_URL)

    def get_snapshot(self) -> CatalogSnapshot:
        """Return the current cache snapshot without scraping."""
        return _cache.load_cache()

    # -----------------------------------------------------------------------
    # Query
    # -----------------------------------------------------------------------

    def get_items(self, f: CatalogFilter | None = None) -> list[CatalogItem]:
        """
        Return catalogue items, optionally filtered.

        Parameters
        ----------
        f:
            A CatalogFilter instance.  Pass None to get all items.
        """
        return _cache.get_items(f)

    def search(
        self,
        query: str,
        limit: int = 50,
        threshold: float = 0.0,
        f: CatalogFilter | None = None,
    ) -> list[SearchResult]:
        """
        Fuzzy-search the catalogue.

        Parameters
        ----------
        query:
            Free-text query, e.g. ``"hawaii fuel 2022"``.
        limit:
            Maximum results to return.
        threshold:
            Minimum score (0..1).
        f:
            Optional pre-filter to narrow the search space.
        """
        items = _cache.get_items(f)
        return search_catalog(query, items, limit=limit, threshold=threshold)

    # -----------------------------------------------------------------------
    # Manifest
    # -----------------------------------------------------------------------

    def save_manifest(
        self,
        items: list[CatalogItem],
        path: Path | str | None = None,
    ) -> Manifest:
        """
        Save *items* to a manifest JSON file.

        Returns the written Manifest.
        """
        snapshot = _cache.load_cache()
        return _manifest.save_manifest(
            items,
            path=path,
            source_cache_timestamp=snapshot.last_run,
        )

    def load_manifest(self, path: Path | str) -> Manifest:
        """Load a manifest.json and return the Manifest object."""
        return _manifest.load_manifest(path)

    def items_from_manifest(self, manifest: Manifest) -> list[CatalogItem]:
        """Convert manifest items back to CatalogItems ready for download."""
        return _manifest.manifest_to_catalog_items(manifest)

    # -----------------------------------------------------------------------
    # Download
    # -----------------------------------------------------------------------

    def download(
        self,
        items: list[CatalogItem],
        output_dir: Path | str = "landfire_output",
        workers: int | None = None,
        dry_run: bool = False,
    ) -> list[DownloadResult]:
        """
        Download *items* concurrently and extract TIF files.

        Parameters
        ----------
        items:
            List of CatalogItem instances.
        output_dir:
            Root directory; TIFs land in ``output_dir/tif/``.
        workers:
            Thread count; defaults to config value.
        dry_run:
            If True, return SKIPPED results without touching the network.
        """
        out = Path(output_dir)
        w = workers or self._workers
        return download_items(items, out, workers=w, dry_run=dry_run)

    def download_manifest(
        self,
        manifest_path: Path | str,
        output_dir: Path | str = "landfire_output",
        workers: int | None = None,
        dry_run: bool = False,
    ) -> list[DownloadResult]:
        """
        Load a manifest and download all its items.
        """
        manifest = self.load_manifest(manifest_path)
        items = self.items_from_manifest(manifest)
        return self.download(items, output_dir=output_dir, workers=workers, dry_run=dry_run)

    def dry_run(
        self,
        items: list[CatalogItem],
        output_dir: Path | str = "landfire_output",
    ) -> dict[str, Any]:
        """Return a summary of what *download()* would do without network I/O."""
        return dry_run_summary(items, Path(output_dir))

    # -----------------------------------------------------------------------
    # Verify
    # -----------------------------------------------------------------------

    def verify(
        self,
        manifest: Manifest | Path | str,
        output_dir: Path | str = "landfire_output",
    ) -> ValidationResult:
        """
        Verify downloaded files against *manifest*.

        Parameters
        ----------
        manifest:
            A Manifest object or path to manifest.json.
        output_dir:
            The directory passed to ``download()``.
        """
        if not isinstance(manifest, Manifest):
            manifest = _manifest.load_manifest(manifest)
        return verify_manifest(manifest, Path(output_dir))

    # -----------------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------------

    def export(
        self,
        items: list[CatalogItem],
        format: ExportFormat | str = ExportFormat.JSON,
        path: Path | str | None = None,
    ) -> Path:
        """
        Export *items* to a file.

        Supported formats: json, csv, markdown.

        Returns the path written.
        """
        fmt = ExportFormat(format) if isinstance(format, str) else format
        dest = Path(path) if path else Path(f"landfire_export.{fmt.value}")

        if fmt == ExportFormat.JSON:
            _export_json(items, dest)
        elif fmt == ExportFormat.CSV:
            _export_csv(items, dest)
        elif fmt == ExportFormat.MARKDOWN:
            _export_markdown(items, dest)
        elif fmt == ExportFormat.PARQUET:
            _export_parquet(items, dest)
        else:
            raise ValueError(f"Unsupported export format: {fmt}")

        return dest


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

_EXPORT_FIELDS = [
    "theme", "product", "region", "version", "file_size", "checksum", "download_url",
]


def _export_json(items: list[CatalogItem], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    rows = [item.model_dump(mode="json", include=set(_EXPORT_FIELDS)) for item in items]
    with dest.open("w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2, ensure_ascii=False)


def _export_csv(items: list[CatalogItem], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_EXPORT_FIELDS)
        writer.writeheader()
        for item in items:
            row = {f: getattr(item, f, None) or "" for f in _EXPORT_FIELDS}
            writer.writerow(row)


def _export_markdown(items: list[CatalogItem], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "| Theme | Product | Region | Version | Size | URL |",
        "|-------|---------|--------|---------|------|-----|",
    ]
    for item in items:
        lines.append(
            f"| {item.theme or ''} | {item.product or ''} | {item.region or ''} "
            f"| {item.version or ''} | {item.file_size or ''} | {item.download_url} |"
        )
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _export_parquet(items: list[CatalogItem], dest: Path) -> None:
    try:
        import pandas as pd  # type: ignore[import]
    except ImportError:
        raise ImportError(
            "Parquet export requires pandas and pyarrow. "
            "Install them: pip install pandas pyarrow"
        )
    rows = [item.model_dump(mode="json", include=set(_EXPORT_FIELDS)) for item in items]
    pd.DataFrame(rows).to_parquet(dest, index=False)
