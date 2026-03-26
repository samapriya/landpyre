# 🔥 landpyre

> **Discover & Download USGS LANDFIRE Data**

A modern, fast, and beautiful **SDK + CLI** for discovering, filtering, searching, and downloading [LANDFIRE](https://www.landfire.gov/) geospatial datasets. Built with [Pydantic](https://docs.pydantic.dev/), [Click](https://click.palletsprojects.com/), and [Rich](https://github.com/Textualize/rich).

```
  _                    _
 | |    __ _ _ __   __| |_ __  _   _ _ __ ___
 | |   / _` | '_ \ / _` | '_ \| | | | '__/ _ \
 | |__| (_| | | | | (_| | |_) | |_| | | |  __/
 |_____\__,_|_| |_|\__,_| .__/ \__, |_|  \___|
                         |_|    |___/
```

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
- **`--check-scraper`** on refresh — validate that the scraper is parsing the page correctly
- **Schema versioning** — stale caches are detected and prompt a helpful `refresh`
- **Resumable downloads** — partial ZIPs are continued from where they left off
- **Checksum verification** — MD5 verified during download when available

---

## Installation

```bash
# From source (recommended during development)
git clone https://github.com/samapriya/landpyre.git
cd landpyre
pip install -e ".[dev]"

# With pip (once published)
pip install landpyre

# With Parquet export support
pip install "landpyre[parquet]"
```

**Requirements:** Python ≥ 3.10, internet access for `refresh` (all other commands work offline).

---

## CLI quick start

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

# 6. Preview what will be downloaded
landpyre download --manifest hawaii.json --dry-run

# 7. Download
landpyre download --manifest hawaii.json --output ./hawaii_data

# 8. Verify integrity
landpyre verify --manifest hawaii.json --output ./hawaii_data

# 9. Check your environment
landpyre doctor
```

---

## SDK quick start

```python
from landpyre import LandpyreClient

client = LandpyreClient()

# Refresh the catalogue (no-op if already cached)
client.refresh()

# Fuzzy search
results = client.search("hawaii fuel 2022")
for r in results:
    print(f"{r.score:.0%}  {r.item.display_label}")

# Precise filter
from landpyre.models import CatalogFilter
items = client.get_items(CatalogFilter(region="Hawaii", version="LF 2022"))

# Save a reproducible manifest
manifest = client.save_manifest(items, path="hawaii.json")

# Preview without downloading
summary = client.dry_run(items, output_dir="./data")
print(f"Would download {summary['item_count']} files ({summary['total_bytes_fmt']})")

# Download
results = client.download(items, output_dir="./data", workers=4)
ok = [r for r in results if r.ok]
print(f"{len(ok)} files downloaded")

# Verify
vr = client.verify(manifest, output_dir="./data")
print("All OK!" if vr.all_ok else f"{vr.files_missing} missing, {vr.files_corrupt} corrupt")

# Export catalogue subset
client.export(items, format="csv", path="hawaii_lf2022.csv")
```

---

## Commands

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

### `landpyre stats`

Rich statistics: total file count, aggregate size, per-version breakdown.

```bash
landpyre stats
landpyre stats --version "LF 2022"
landpyre stats --region "Hawaii"
landpyre stats --json
```

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

**Manifest file structure:**

```json
{
  "schema_version": 2,
  "created_at": "2025-06-15T14:32:01+00:00",
  "source_cache_timestamp": "2025-06-15 14:30:00 PDT",
  "item_count": 12,
  "items": [
    {
      "download_url": "https://www.landfire.gov/data-downloads/...",
      "filename": "LF2022_FBFM40_220_HI.zip",
      "region": "Hawaii",
      "version": "LF 2022",
      "product": "FBFM40",
      "file_size": "1.2 GB",
      "checksum": "abc123..."
    }
  ]
}
```

---

### `landpyre download`

Download files and extract TIF data. Accepts filters or a manifest.

```bash
landpyre download --version "LF 2022" --output lf2022
landpyre download --manifest manifest.json --output ./data
landpyre download --region "CONUS" --dry-run          # Preview only
landpyre download --manifest hawaii.json --yes --open # Skip confirm, open folder
landpyre download --version "LF 2024" --json          # Machine-readable result
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

Run environment diagnostics.

```bash
landpyre doctor
landpyre doctor --json
```

Checks: Python version, disk space, network reachability, SSL/TLS, cache existence, cache directory permissions, config file validity, ZIP support, Pydantic installation.

---

## SDK reference

### `LandpyreClient`

```python
from landpyre import LandpyreClient, CatalogFilter

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

### Key models

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

### Export formats

```python
client.export(items, format="json",     path="out.json")
client.export(items, format="csv",      path="out.csv")
client.export(items, format="markdown", path="out.md")
client.export(items, format="parquet",  path="out.parquet")  # requires [parquet] extra
```

---

## Filtering logic

All filters are **case-insensitive** and **ANDed** together.

```python
from landpyre.models import CatalogFilter, FilterMode

# Substring (default)
CatalogFilter(region="haw")                 # matches "Hawaii"

# Exact
CatalogFilter(region="Hawaii", mode=FilterMode.EXACT)

# Regex
CatalogFilter(version=r"LF 202[234]", mode=FilterMode.REGEX)

# Fuzzy (token overlap)
CatalogFilter(product="fbfm", mode=FilterMode.FUZZY, fuzzy_threshold=0.5)
```

---

## Cache file structure (v2)

```json
{
  "schema_version": 2,
  "last_run": "2025-06-15 14:32:01 PDT",
  "item_count": 842,
  "scrape_url": "https://www.landfire.gov/data/FullExtentDownloads?...",
  "items": [
    {
      "theme": "Fire Behavior",
      "product": "FBFM40",
      "region_version": "Hawaii LF 2022",
      "region": "Hawaii",
      "version": "LF 2022",
      "file_size": "1.2 GB",
      "checksum": "d41d8cd98f00b204e9800998ecf8427e",
      "download_url": "https://www.landfire.gov/data-downloads/...",
      "source_page": 3,
      "scrape_timestamp": "2025-06-15T21:32:00+00:00",
      "parser_version": "0.2.0"
    }
  ]
}
```

If your cache was written by v0.1.0 (schema version 1), landpyre will ask you to run `landpyre refresh` to rebuild it.

---

## Output structure

```
landfire_output/
└── tif/
    ├── LF2022_FBFM40_220_HI.tif
    ├── LF2022_FVH_220_HI.tif
    └── ...
```

ZIP files are downloaded to `.tmp_zips/`, TIFs are extracted flat into `tif/`, and the ZIPs are removed automatically.
