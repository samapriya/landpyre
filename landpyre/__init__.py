"""
landpyre — LANDFIRE data discovery, search, and download SDK + CLI.

Package layout
--------------
landpyre/
├── __init__.py        ← version + public re-exports
├── api.py             ← LandpyreClient (primary SDK entry point)
├── models.py          ← typed domain models (Pydantic)
├── errors.py          ← typed exception hierarchy
├── config.py          ← persistent user config (~/.config/landpyre/config.toml)
├── scraper.py         ← LANDFIRE catalogue scraper
├── cache.py           ← local JSON cache with schema versioning
├── downloader.py      ← concurrent ZIP downloader + TIF extractor
├── search.py          ← fuzzy catalogue search engine
├── manifest.py        ← portable download manifests
├── verifier.py        ← file integrity verification
├── cli.py             ← Click group wiring all commands
├── commands/          ← one module per CLI command
│   ├── refresh.py
│   ├── list_cmd.py
│   ├── stats.py
│   ├── download.py
│   ├── search_cmd.py
│   ├── manifest_cmd.py
│   ├── verify_cmd.py
│   ├── config_cmd.py
│   └── doctor_cmd.py
└── ui/
    └── banner.py

SDK quick start
---------------
    from landpyre import LandpyreClient

    client = LandpyreClient()
    client.refresh()                                    # scrape + cache
    items = client.search("hawaii fuel 2022")           # fuzzy search
    manifest = client.save_manifest(                    # reproducible selection
        [r.item for r in items], path="hawaii.json"
    )
    results = client.download(                          # concurrent download
        [r.item for r in items], output_dir="./data"
    )
    vr = client.verify(manifest, output_dir="./data")  # integrity check
    client.export(items, format="csv", path="out.csv") # export

CLI quick start
---------------
    landpyre refresh
    landpyre search "hawaii fuel"
    landpyre list --version "LF 2022" --region Hawaii
    landpyre manifest --version "LF 2022" --region Hawaii
    landpyre download --manifest manifest.json
    landpyre verify
    landpyre stats
    landpyre config show
    landpyre doctor
"""

from __future__ import annotations

__version__ = "0.2.0"
__author__ = "landpyre contributors"

__all__ = [
    "__version__",
    # SDK
    "LandpyreClient",
    # Models
    "CatalogItem",
    "CatalogFilter",
    "CatalogSnapshot",
    "DownloadJob",
    "DownloadResult",
    "DownloadStatus",
    "ExportFormat",
    "FilterMode",
    "Manifest",
    "ManifestItem",
    "ValidationResult",
    "LandpyreConfig",
    # Errors
    "LandpyreError",
    "CacheNotFoundError",
    "CacheSchemaMismatchError",
    "ScraperError",
    "DownloadError",
    "ManifestError",
    "ConfigError",
    # Low-level callables (backward-compatible with v0.1.0)
    "scrape_catalogue",
    "load_cache",
    "save_cache",
    "get_items",
    "download_items",
]

# ── SDK ──────────────────────────────────────────────────────────────────────
from landpyre.api import LandpyreClient

# ── Models ───────────────────────────────────────────────────────────────────
from landpyre.models import (
    CatalogItem,
    CatalogFilter,
    CatalogSnapshot,
    DownloadJob,
    DownloadResult,
    DownloadStatus,
    ExportFormat,
    FilterMode,
    LandpyreConfig,
    Manifest,
    ManifestItem,
    ValidationResult,
)

# ── Errors ───────────────────────────────────────────────────────────────────
from landpyre.errors import (
    LandpyreError,
    CacheNotFoundError,
    CacheSchemaMismatchError,
    ScraperError,
    DownloadError,
    ManifestError,
    ConfigError,
)

# ── Low-level callables (v0.1.0 backward compat) ────────────────────────────
from landpyre.scraper import scrape_catalogue
from landpyre.cache import load_cache, save_cache, get_items
from landpyre.downloader import download_items
