<div align="center">

<img src="https://i.imgur.com/bgpXO7o.png" alt="landpyre logo" width="160" style="border-radius: 50%;" />

# 🔥 landpyre

**Discover & Download USGS LANDFIRE Data**

*Unofficial CLI and SDK for LANDFIRE data — discover, filter, search, and download geospatial datasets with ease.*

[![PyPI version](https://img.shields.io/pypi/v/landpyre?color=%23ecc328&label=pypi&logo=pypi&logoColor=white)](https://pypi.org/project/landpyre/)
[![Python](https://img.shields.io/pypi/pyversions/landpyre?color=%2398cbff&logo=python&logoColor=white)](https://pypi.org/project/landpyre/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green?logo=apache&logoColor=white)](https://github.com/samapriya/landpyre/blob/main/LICENSE)
[![Docs](https://img.shields.io/badge/docs-landpyre.geocarpentry.org-blue?logo=readthedocs&logoColor=white)](https://landpyre.geocarpentry.org)

[**Documentation**](https://landpyre.geocarpentry.org) · [**GitHub**](https://github.com/samapriya/landpyre) · [**Issues**](https://github.com/samapriya/landpyre/issues)

</div>

---

## Overview

**landpyre** is a modern, typed SDK and CLI for working with [LANDFIRE](https://www.landfire.gov/) geospatial datasets published by the USGS. It handles catalog discovery, fuzzy search, manifest-based reproducible downloads, checksum verification, and data export — all from the terminal or Python.

Built with [Pydantic](https://docs.pydantic.dev/), [Click](https://click.palletsprojects.com/), and [Rich](https://github.com/Textualize/rich).

---

## What's new in v0.2.0

- **Typed SDK** — `LandpyreClient` with `search()`, `download()`, `verify()`, `export()`
- **Pydantic models** — `CatalogItem`, `CatalogFilter`, `DownloadResult`, and more
- **`landpyre search`** — fuzzy full-text search ranked by relevance
- **`landpyre manifest`** — save reproducible download selections to `manifest.json`
- **`landpyre verify`** — checksum and existence validation against a manifest
- **`landpyre config`** — persistent defaults (`default_region`, `default_output`, etc.)
- **`landpyre doctor`** — environment diagnostics (Python, disk, network, SSL, cache)
- **`--dry-run`** on download — preview files and total size without hitting the network
- **`--open`** on download — open the output folder in your file explorer after completion
- **`--json`** on every command — machine-readable output for scripting
- **Schema versioning** — stale caches are detected and prompt a helpful `refresh`
- **Resumable downloads** — partial ZIPs are continued from where they left off
- **Checksum verification** — MD5 verified during download when available

---

## Installation

```bash
# Standard install
pip install landpyre

# With Parquet export support
pip install "landpyre[parquet]"

# From source (development)
git clone https://github.com/samapriya/landpyre.git
cd landpyre
pip install -e ".[dev]"
```

**Requirements:** Python ≥ 3.10, internet access for `refresh` (all other commands work offline).

---

## CLI Quick Start

```bash
# 1. Fetch and cache the full LANDFIRE catalogue
landpyre refresh

# 2. Fuzzy-search the catalogue
landpyre search "hawaii fuel 2022"

# 3. Browse with filters
landpyre list --version "LF 2022" --region Hawaii

# 4. Statistics summary
landpyre stats

# 5. Save a manifest for reproducible downloads
landpyre manifest --version "LF 2022" --region Hawaii -o hawaii.json

# 6. Preview what will be downloaded (no network I/O)
landpyre download --manifest hawaii.json --dry-run

# 7. Download
landpyre download --manifest hawaii.json --output ./hawaii_data

# 8. Verify integrity
landpyre verify --manifest hawaii.json --output ./hawaii_data

# 9. Check your environment
landpyre doctor
```

---

## SDK Quick Start

### 1. Setup & Client Exploration

```python
from landpyre import LandpyreClient

client = LandpyreClient()

# refresh() is a no-op if a valid cache already exists.
# Pass force=True to always re-scrape.
snapshot = client.refresh()

print(f"Cache contains {snapshot.item_count} items.")
print(f"Last scraped: {snapshot.last_run}")
print(f"Schema version: {snapshot.schema_version}")
```

### 2. Filtering & Fuzzy Search

```python
from landpyre import LandpyreClient
from landpyre.models import CatalogFilter, FilterMode

client = LandpyreClient()
client.refresh()

# Precise regex filtering
f_regex = CatalogFilter(version=r"LF 202[234]", mode=FilterMode.REGEX)
items = client.get_items(f_regex)

# Ranked fuzzy search across product, theme, region, and version
results = client.search("hawaii fuel 2022", threshold=0.6)

for r in results[:3]:
    print(f"{r.score:.0%} - {r.item.filename}")
```

### 3. Manifests & Dry-runs

```python
from landpyre import LandpyreClient
from landpyre.models import CatalogFilter

client = LandpyreClient()
client.refresh()

items = client.get_items(CatalogFilter(region="Hawaii", version="LF 2022"))

# Save state to manifest
manifest = client.save_manifest(items, path="hawaii_lf2022.json")

# Dry run to calculate total payload
summary = client.dry_run(items, output_dir="./data")
print(f"Files to download : {summary['item_count']}")
print(f"Total size        : {summary['total_bytes_fmt']}")

# Load state back later
loaded = client.load_manifest("hawaii_lf2022.json")
```

### 4. Downloads & Verification

```python
from landpyre import LandpyreClient
from landpyre.models import CatalogFilter

client = LandpyreClient()
client.refresh()

items = client.get_items(CatalogFilter(region="Hawaii", version="LF 2022"))
client.save_manifest(items, path="hawaii_lf2022.json")

# Resumable multi-threaded download
results = client.download(items, output_dir="./data", workers=4)

# Post-download integrity verification against the manifest
vr = client.verify("hawaii_lf2022.json", output_dir="./data")

print(f"All OK        : {vr.all_ok}")
print(f"Files missing : {vr.files_missing}")
print(f"Files corrupt : {vr.files_corrupt}")
```

### 5. Exporting Catalog Metadata

```python
from landpyre import LandpyreClient
from landpyre.models import CatalogFilter

client = LandpyreClient()
client.refresh()

items = client.get_items(CatalogFilter(version="LF 2022"))

# Standard exports
client.export(items, format="json",     path="lf2022.json")
client.export(items, format="csv",      path="lf2022.csv")
client.export(items, format="markdown", path="lf2022.md")

# Parquet (requires `pip install "landpyre[parquet]"`)
client.export(items, format="parquet",  path="lf2022.parquet")
```

---

## CLI Reference

### `landpyre refresh`

Scrapes the LANDFIRE catalogue and saves it to `~/.landpyre/landfire_latest.json`.

```bash
landpyre refresh                  # Refresh only if no valid cache exists
landpyre refresh --force          # Force re-scrape
landpyre refresh --check-scraper  # Health-check the scraper without saving
landpyre refresh --json           # Machine-readable output
```

---

### `landpyre search QUERY`

Fuzzy full-text search across product, theme, region, and version. Results are ranked by relevance score.

```bash
landpyre search "hawaii fuel"
landpyre search "CONUS LF 2022" --limit 10
landpyre search "fire behavior" --threshold 0.5
landpyre search "fuel model" --json
```

| Flag | Description |
|------|-------------|
| `--limit` / `-l` | Maximum results (default: 20) |
| `--threshold` | Minimum relevance score 0.0–1.0 (default: 0.0) |
| `--json` | Output as JSON |

---

### `landpyre list`

Browse the catalogue with exact/substring filters.

```bash
landpyre list
landpyre list --version "LF 2022"
landpyre list --region "Hawaii" --version "LF 2022"
landpyre list --theme "Fire" --limit 20 --url
landpyre list --region "CONUS" --json
```

| Flag | Short | Description |
|------|-------|-------------|
| `--version` | `-V` | Filter by version |
| `--region` | `-r` | Filter by region |
| `--theme` | `-t` | Filter by theme |
| `--limit` | `-l` | Max rows (default: 50) |
| `--url` | | Show download URLs |
| `--json` | | Output as JSON |

---

### `landpyre manifest`

Save a filtered selection to a portable `manifest.json`.

```bash
landpyre manifest --version "LF 2022" --region Hawaii
landpyre manifest --version "LF 2024" -o conus_2024.json
landpyre manifest --show manifest.json        # Inspect an existing manifest
```

| Flag | Short | Description |
|------|-------|-------------|
| `--version` | `-V` | Version filter |
| `--region` | `-r` | Region filter |
| `--theme` | `-t` | Theme filter |
| `--output` | `-o` | Destination path (default: `manifest.json`) |
| `--show` | `-s` | Inspect an existing manifest |
| `--json` | | Output as JSON |

---

### `landpyre download`

Download files and extract TIF data. Accepts filters or a manifest.

```bash
landpyre download --version "LF 2022" --output lf2022
landpyre download --manifest manifest.json --output ./data
landpyre download --region "CONUS" --dry-run          # Preview only
landpyre download --manifest hawaii.json --yes --open # Skip confirm, open folder
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--version` | `-V` | | Version filter |
| `--region` | `-r` | | Region filter |
| `--theme` | `-t` | | Theme filter |
| `--manifest` | `-m` | | Replay a manifest.json |
| `--output` | `-o` | config / `landfire_output` | Output directory |
| `--workers` | `-w` | config / `4` | Concurrent threads |
| `--yes` | `-y` | | Skip confirmation |
| `--dry-run` | | | Preview without downloading |
| `--open` | | | Open output folder after download |
| `--json` | | | Output as JSON |

---

### `landpyre verify`

Verify downloaded files against a manifest (existence, size, MD5 checksum).

```bash
landpyre verify
landpyre verify --manifest hawaii.json --output ./hawaii_data
landpyre verify --json
```

---

### `landpyre config`

View and modify persistent configuration stored at `~/.config/landpyre/config.toml`.

```bash
landpyre config show
landpyre config get default_region
landpyre config set default_region CONUS
landpyre config set default_workers 6
landpyre config set auto_confirm true
```

| Key | Default | Description |
|-----|---------|-------------|
| `default_output` | `landfire_output` | Default download directory |
| `default_workers` | `4` | Default concurrent threads |
| `default_region` | — | Default region filter |
| `default_version` | — | Default version filter |
| `default_theme` | — | Default theme filter |
| `cache_dir` | `~/.landpyre` | Override cache location |
| `log_level` | `WARNING` | Logging level |
| `auto_confirm` | `false` | Skip download confirmation |
| `no_color` | `false` | Disable colour output |

---

### `landpyre doctor`

Run environment diagnostics: Python version, disk space, network reachability, SSL/TLS, cache existence, directory permissions, config validity, ZIP support, and Pydantic installation.

```bash
landpyre doctor
landpyre doctor --json
```

---

## SDK Reference

### `LandpyreClient`

```python
from landpyre import LandpyreClient

client = LandpyreClient(
    cache_dir=None,   # override cache location
    workers=4,        # default download thread count
)
```

| Method | Returns | Description |
|--------|---------|-------------|
| `refresh(force, progress_callback)` | `CatalogSnapshot` | Scrape and cache |
| `get_snapshot()` | `CatalogSnapshot` | Load current cache |
| `get_items(f)` | `list[CatalogItem]` | Filter query |
| `search(query, limit, threshold, f)` | `list[SearchResult]` | Fuzzy search |
| `save_manifest(items, path)` | `Manifest` | Save manifest |
| `load_manifest(path)` | `Manifest` | Load manifest |
| `items_from_manifest(manifest)` | `list[CatalogItem]` | Convert for download |
| `download(items, output_dir, workers, dry_run)` | `list[DownloadResult]` | Download |
| `download_manifest(path, output_dir, ...)` | `list[DownloadResult]` | Load + download |
| `dry_run(items, output_dir)` | `dict` | Preview summary |
| `verify(manifest, output_dir)` | `ValidationResult` | Integrity check |
| `export(items, format, path)` | `Path` | Export to file |

### Key Models

```python
from landpyre.models import (
    CatalogItem,      # One downloadable entry
    CatalogFilter,    # Filter criteria (substring/exact/regex/fuzzy)
    CatalogSnapshot,  # The full cached catalogue
    DownloadResult,   # Outcome of one download
    Manifest,         # Portable manifest document
    ValidationResult, # Outcome of a verify run
    LandpyreConfig,   # User preferences
)
```

### Filtering Logic

All filters are **case-insensitive** and **ANDed** together.

```python
from landpyre.models import CatalogFilter, FilterMode

CatalogFilter(region="haw")                                    # Substring (default)
CatalogFilter(region="Hawaii", mode=FilterMode.EXACT)          # Exact
CatalogFilter(version=r"LF 202[234]", mode=FilterMode.REGEX)   # Regex
CatalogFilter(product="fbfm", mode=FilterMode.FUZZY, fuzzy_threshold=0.5)  # Fuzzy
```

---

## Output Structure

```
landfire_output/
└── tif/
    ├── LF2022_FBFM40_220_HI.tif
    ├── LF2022_FVH_220_HI.tif
    └── ...
```

ZIP files are downloaded to `.tmp_zips/`, TIFs are extracted flat into `tif/`, and the ZIPs are removed automatically.

---

## Links

- **Documentation:** [landpyre.geocarpentry.org](https://landpyre.geocarpentry.org)
- **GitHub:** [github.com/samapriya/landpyre](https://github.com/samapriya/landpyre)
- **PyPI:** [pypi.org/project/landpyre](https://pypi.org/project/landpyre/)
- **Issues:** [github.com/samapriya/landpyre/issues](https://github.com/samapriya/landpyre/issues)

---

<div align="center">

Apache 2.0 License · Built by [Samapriya Roy](https://github.com/samapriya) · Powered by Pydantic, Click, and Rich

</div>
