"""
models.py — Typed domain models for the landpyre SDK.

All public SDK types live here. External code should import from
``landpyre.models`` or directly from ``landpyre`` (re-exported in __init__.py).

Design notes
------------
- Every raw dict that previously flowed through the codebase is replaced by
  one of these models. Pydantic validates on construction and serialises with
  .model_dump() / .model_dump_json().
- ``CatalogItem`` is the canonical representation of one download entry.
- ``CatalogFilter`` encapsulates all filter logic so it can be reused by
  cache.get_items(), search, manifest, and the CLI uniformly.
- ``DownloadJob`` tracks in-flight state; ``DownloadResult`` is the outcome.
- ``CatalogSnapshot`` is what the cache stores and what diff/sync operate on.
- ``ManifestItem`` is the portable, reproducible record saved to manifest.json.
- ``ValidationResult`` is returned by verify operations.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DownloadStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    OK = "ok"
    ERROR = "error"
    SKIPPED = "skipped"


class FilterMode(str, Enum):
    SUBSTRING = "substring"   # case-insensitive substring (default)
    EXACT = "exact"           # exact case-insensitive match
    REGEX = "regex"           # compiled regex
    FUZZY = "fuzzy"           # token-overlap score (used by search)


class ExportFormat(str, Enum):
    JSON = "json"
    CSV = "csv"
    PARQUET = "parquet"
    MARKDOWN = "markdown"


# ---------------------------------------------------------------------------
# Core catalog model
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 2


class CatalogItem(BaseModel):
    """One downloadable LANDFIRE entry scraped from the catalogue page."""

    theme: str | None = None
    product: str | None = None
    region_version: str | None = None   # raw, e.g. "Hawaii LF 2022"
    region: str | None = None           # parsed, e.g. "Hawaii"
    version: str | None = None          # parsed, e.g. "LF 2022"
    file_size: str | None = None        # human string, e.g. "1.2 GB"
    checksum: str | None = None
    download_url: str
    source_page: int | None = None

    # Provenance — populated by scraper/cache
    scrape_timestamp: datetime | None = None
    parser_version: str | None = None

    @property
    def file_size_bytes(self) -> int | None:
        """Parse file_size string to bytes, or None if unparseable."""
        if not self.file_size:
            return None
        _SIZE_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*(GB|MB|KB|B)", re.IGNORECASE)
        _UNITS = {"b": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3}
        m = _SIZE_RE.search(self.file_size)
        if not m:
            return None
        return int(float(m.group(1).replace(",", "")) * _UNITS.get(m.group(2).lower(), 1))

    @property
    def filename(self) -> str:
        """Derive filename from the download URL."""
        return self.download_url.split("/")[-1] or "download.zip"

    @property
    def display_label(self) -> str:
        """Short human label for progress bars and tables."""
        parts = [p for p in (self.region, self.version, self.product) if p]
        return " / ".join(parts) if parts else self.filename

    def matches(self, f: "CatalogFilter") -> bool:
        """Return True if this item satisfies *f*."""
        return f.matches(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CatalogItem":
        return cls(**{k: v for k, v in d.items() if k in cls.model_fields})


# ---------------------------------------------------------------------------
# Filter model
# ---------------------------------------------------------------------------


class CatalogFilter(BaseModel):
    """
    Encapsulates a set of filter criteria for catalog queries.

    Each field filter is a (value, mode) pair — defaults to substring match.
    Filters are ANDed together; None means "no constraint on this field".
    """

    version: str | None = None
    region: str | None = None
    theme: str | None = None
    product: str | None = None
    mode: FilterMode = FilterMode.SUBSTRING

    # Fuzzy search: min token overlap ratio 0..1
    fuzzy_threshold: float = Field(default=0.3, ge=0.0, le=1.0)

    def _field_matches(self, field_value: str | None, pattern: str | None) -> bool:
        if pattern is None:
            return True
        if field_value is None:
            return False
        fv = field_value.lower()
        pat = pattern.lower()

        if self.mode == FilterMode.EXACT:
            return fv == pat
        if self.mode == FilterMode.REGEX:
            return bool(re.search(pat, fv))
        if self.mode == FilterMode.FUZZY:
            a_tokens = set(fv.split())
            b_tokens = set(pat.split())
            if not b_tokens:
                return True
            overlap = len(a_tokens & b_tokens) / len(b_tokens)
            return overlap >= self.fuzzy_threshold
        # Default: SUBSTRING
        return pat in fv

    def matches(self, item: CatalogItem) -> bool:
        return (
            self._field_matches(item.version, self.version)
            and self._field_matches(item.region, self.region)
            and self._field_matches(item.theme, self.theme)
            and self._field_matches(item.product, self.product)
        )

    @classmethod
    def from_kwargs(
        cls,
        version: str | None = None,
        region: str | None = None,
        theme: str | None = None,
        product: str | None = None,
        mode: FilterMode = FilterMode.SUBSTRING,
    ) -> "CatalogFilter":
        return cls(version=version, region=region, theme=theme, product=product, mode=mode)


# ---------------------------------------------------------------------------
# Download models
# ---------------------------------------------------------------------------


class DownloadJob(BaseModel):
    """Tracks the state of a single file download."""

    item: CatalogItem
    status: DownloadStatus = DownloadStatus.PENDING
    retry_count: int = 0
    bytes_written: int = 0
    resume_offset: int = 0      # bytes already on disk from a previous attempt
    error: str | None = None

    model_config = {"arbitrary_types_allowed": True}


class DownloadResult(BaseModel):
    """The outcome of downloading one CatalogItem."""

    item: CatalogItem
    status: DownloadStatus
    tifs_extracted: list[str] = Field(default_factory=list)
    bytes_written: int = 0
    elapsed_seconds: float = 0.0
    error: str | None = None

    model_config = {"arbitrary_types_allowed": True}

    @property
    def ok(self) -> bool:
        return self.status == DownloadStatus.OK


# ---------------------------------------------------------------------------
# Cache / snapshot model
# ---------------------------------------------------------------------------


class CatalogSnapshot(BaseModel):
    """
    What the cache file stores.

    schema_version lets cache.py detect stale files and migrate gracefully
    rather than crashing on a KeyError when a new field is added to CatalogItem.
    """

    schema_version: int = SCHEMA_VERSION
    last_run: str                              # ISO-8601 local time string
    item_count: int
    scrape_url: str | None = None             # canonical source URL
    parser_version: str | None = None
    items: list[CatalogItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def sync_item_count(self) -> "CatalogSnapshot":
        self.item_count = len(self.items)
        return self


# ---------------------------------------------------------------------------
# Manifest models
# ---------------------------------------------------------------------------


class ManifestItem(BaseModel):
    """
    A portable record representing one item selected for download.

    Saved to manifest.json so a download session can be replayed exactly,
    verified against checksums, and shared with others.
    """

    download_url: str
    filename: str
    region: str | None = None
    version: str | None = None
    product: str | None = None
    theme: str | None = None
    file_size: str | None = None
    checksum: str | None = None
    source_page: int | None = None

    @classmethod
    def from_catalog_item(cls, item: CatalogItem) -> "ManifestItem":
        return cls(
            download_url=item.download_url,
            filename=item.filename,
            region=item.region,
            version=item.version,
            product=item.product,
            theme=item.theme,
            file_size=item.file_size,
            checksum=item.checksum,
            source_page=item.source_page,
        )


class Manifest(BaseModel):
    """The full manifest.json document."""

    schema_version: int = SCHEMA_VERSION
    created_at: str                             # ISO-8601
    source_cache_timestamp: str | None = None
    item_count: int = 0
    items: list[ManifestItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def sync_count(self) -> "Manifest":
        self.item_count = len(self.items)
        return self


# ---------------------------------------------------------------------------
# Verification model
# ---------------------------------------------------------------------------


class FileValidation(BaseModel):
    """Result for one file in a verify run."""

    filename: str
    path: str
    exists: bool
    expected_checksum: str | None = None
    actual_checksum: str | None = None
    expected_size: int | None = None
    actual_size: int | None = None
    checksum_ok: bool | None = None   # None = not checked (no expected checksum)
    size_ok: bool | None = None


class ValidationResult(BaseModel):
    """Aggregated result of a verify operation."""

    manifest_path: str
    checked_at: str
    files_ok: int = 0
    files_missing: int = 0
    files_corrupt: int = 0
    details: list[FileValidation] = Field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        return self.files_missing == 0 and self.files_corrupt == 0

    @property
    def needs_repair(self) -> list[FileValidation]:
        return [d for d in self.details if not d.exists or d.checksum_ok is False]


# ---------------------------------------------------------------------------
# Config model
# ---------------------------------------------------------------------------


class LandpyreConfig(BaseModel):
    """
    User preferences loaded from ~/.config/landpyre/config.toml.

    All fields have sensible defaults so the config file is optional.
    """

    default_output: str = "landfire_output"
    default_workers: int = Field(default=4, ge=1, le=32)
    default_region: str | None = None
    default_version: str | None = None
    default_theme: str | None = None
    cache_dir: str | None = None          # None → ~/.landpyre
    log_level: str = "WARNING"
    auto_confirm: bool = False
    no_color: bool = False
