"""
cache.py — Local LANDFIRE catalogue cache backed by typed models.

Cache file location: ``~/.landpyre/landfire_latest.json``
(override via config.cache_dir or the LANDPYRE_CACHE_DIR env var).

Schema versioning
-----------------
The cache stores a ``schema_version`` integer alongside the items.
When the version on disk does not match ``models.SCHEMA_VERSION``,
``load_cache()`` raises ``CacheSchemaMismatchError`` with a clear message
directing the user to run ``landpyre refresh``.  This prevents silent
failures when new fields are added to CatalogItem.

Public API (re-exported from landpyre.api via LandpyreClient)
-------------------------------------------------------------
    cache_path() -> Path
    cache_exists() -> bool
    load_cache() -> CatalogSnapshot
    save_cache(items: list[CatalogItem]) -> CatalogSnapshot
    get_items(f: CatalogFilter | None) -> list[CatalogItem]
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from landpyre.errors import CacheNotFoundError, CacheSchemaMismatchError
from landpyre.models import SCHEMA_VERSION, CatalogFilter, CatalogItem, CatalogSnapshot

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

_DEFAULT_CACHE_DIR = Path.home() / ".landpyre"


def _cache_dir() -> Path:
    env = os.environ.get("LANDPYRE_CACHE_DIR")
    if env:
        return Path(env)
    # Late import to avoid circular dependency with config
    try:
        from landpyre.config import load_config
        cfg = load_config()
        if cfg.cache_dir:
            return Path(cfg.cache_dir)
    except Exception:  # noqa: BLE001
        pass
    return _DEFAULT_CACHE_DIR


def cache_path() -> Path:
    return _cache_dir() / "landfire_latest.json"


# ---------------------------------------------------------------------------
# Existence check
# ---------------------------------------------------------------------------


def cache_exists() -> bool:
    p = cache_path()
    return p.exists() and p.stat().st_size > 0


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------


def load_cache() -> CatalogSnapshot:
    """
    Load the cached catalogue from disk.

    Raises
    ------
    CacheNotFoundError
        If no cache file exists.
    CacheSchemaMismatchError
        If the on-disk schema version is outdated.
    """
    p = cache_path()
    if not p.exists() or p.stat().st_size == 0:
        raise CacheNotFoundError()

    with p.open("r", encoding="utf-8") as fh:
        raw: dict[str, Any] = json.load(fh)

    on_disk_version = raw.get("schema_version", 1)
    if on_disk_version < SCHEMA_VERSION:
        raise CacheSchemaMismatchError(found=on_disk_version, expected=SCHEMA_VERSION)

    # Deserialise items tolerantly: ignore unknown keys in case of future additions
    items: list[CatalogItem] = []
    for d in raw.get("items", []):
        try:
            items.append(CatalogItem.model_validate(d))
        except Exception:  # noqa: BLE001
            # Skip malformed entries rather than crashing the whole load
            pass

    return CatalogSnapshot(
        schema_version=on_disk_version,
        last_run=raw.get("last_run", ""),
        item_count=len(items),
        scrape_url=raw.get("scrape_url"),
        parser_version=raw.get("parser_version"),
        items=items,
    )


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------


def save_cache(items: list[CatalogItem], scrape_url: str | None = None) -> CatalogSnapshot:
    """
    Persist *items* to the cache file.

    Returns the CatalogSnapshot that was written.
    """
    p = cache_path()
    p.parent.mkdir(parents=True, exist_ok=True)

    now_local = datetime.now().astimezone()
    last_run_str = now_local.strftime("%Y-%m-%d %H:%M:%S %Z")

    snapshot = CatalogSnapshot(
        schema_version=SCHEMA_VERSION,
        last_run=last_run_str,
        item_count=len(items),
        scrape_url=scrape_url,
        items=items,
    )

    # Serialise items preserving all fields
    payload: dict[str, Any] = {
        "schema_version": snapshot.schema_version,
        "last_run": snapshot.last_run,
        "item_count": snapshot.item_count,
        "scrape_url": snapshot.scrape_url,
        "items": [item.model_dump(mode="json") for item in items],
    }

    with p.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, default=str)

    return snapshot


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


def get_items(f: CatalogFilter | None = None) -> list[CatalogItem]:
    """
    Return items from the cache, optionally filtered.

    This is the primary query entry point for both the CLI and SDK.
    """
    snapshot = load_cache()
    if f is None:
        return snapshot.items
    return [item for item in snapshot.items if f.matches(item)]
