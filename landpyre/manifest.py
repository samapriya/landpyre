"""
manifest.py — Generate, save, and load portable download manifests.

A manifest is a JSON file that captures exactly which LANDFIRE items were
selected, their checksums, and their download URLs.  It can be committed to
version control, shared with collaborators, and replayed with
``landpyre download --manifest manifest.json``.

Public API
----------
    save_manifest(items, path) -> Manifest
    load_manifest(path) -> Manifest
    manifest_to_catalog_items(manifest) -> list[CatalogItem]
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from landpyre.errors import ManifestError
from landpyre.models import (
    SCHEMA_VERSION,
    CatalogItem,
    Manifest,
    ManifestItem,
)

DEFAULT_MANIFEST_FILENAME = "manifest.json"


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------


def save_manifest(
    items: list[CatalogItem],
    path: Path | str | None = None,
    source_cache_timestamp: str | None = None,
) -> Manifest:
    """
    Save *items* as a manifest JSON file.

    Parameters
    ----------
    items:
        The CatalogItems to include.
    path:
        Destination path (default: ``./manifest.json``).
    source_cache_timestamp:
        The ``last_run`` string from the cache snapshot, for provenance.

    Returns
    -------
    The Manifest object that was written.
    """
    dest = Path(path) if path else Path(DEFAULT_MANIFEST_FILENAME)
    dest.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()
    manifest = Manifest(
        schema_version=SCHEMA_VERSION,
        created_at=now,
        source_cache_timestamp=source_cache_timestamp,
        items=[ManifestItem.from_catalog_item(i) for i in items],
    )

    try:
        with dest.open("w", encoding="utf-8") as fh:
            json.dump(manifest.model_dump(mode="json"), fh, indent=2, ensure_ascii=False)
    except OSError as exc:
        raise ManifestError(f"Cannot write manifest to {dest}: {exc}") from exc

    return manifest


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------


def load_manifest(path: Path | str) -> Manifest:
    """
    Load a manifest.json from *path*.

    Raises ManifestError if the file cannot be read or parsed.
    """
    src = Path(path)
    if not src.exists():
        raise ManifestError(f"Manifest not found: {src}")

    try:
        with src.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Cannot read manifest {src}: {exc}") from exc

    try:
        return Manifest.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        raise ManifestError(f"Invalid manifest format in {src}: {exc}") from exc


# ---------------------------------------------------------------------------
# Conversion back to CatalogItems (for download)
# ---------------------------------------------------------------------------


def manifest_to_catalog_items(manifest: Manifest) -> list[CatalogItem]:
    """Convert ManifestItems back to CatalogItems for passing to download_items()."""
    return [
        CatalogItem(
            download_url=mi.download_url,
            region=mi.region,
            version=mi.version,
            product=mi.product,
            theme=mi.theme,
            file_size=mi.file_size,
            checksum=mi.checksum,
            source_page=mi.source_page,
        )
        for mi in manifest.items
    ]
