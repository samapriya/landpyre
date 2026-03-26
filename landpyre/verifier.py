"""
verifier.py — Verify downloaded files against a manifest.

Checks existence, file size (where known), and MD5 checksum (where the
manifest captured one).  Returns a ValidationResult with per-file details
so the CLI can present a clear repair plan.

Public API
----------
    verify_manifest(manifest, output_dir) -> ValidationResult
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from landpyre.models import (
    FileValidation,
    Manifest,
    ManifestItem,
    ValidationResult,
)
from landpyre.downloader import parse_bytes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _md5_file(path: Path, chunk: int = 1 << 17) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        while data := fh.read(chunk):
            h.update(data)
    return h.hexdigest()


def _verify_one(item: ManifestItem, tif_dir: Path) -> FileValidation:
    """Verify a single manifest item against the TIF output directory."""
    # TIF files are extracted flat into tif/
    tif_name = item.filename.replace(".zip", ".tif")
    path = tif_dir / tif_name

    exists = path.exists()
    actual_size = path.stat().st_size if exists else None
    expected_size = parse_bytes(item.file_size)

    actual_checksum: str | None = None
    checksum_ok: bool | None = None

    if exists and item.checksum:
        actual_checksum = _md5_file(path)
        checksum_ok = actual_checksum.lower() == item.checksum.lower()

    size_ok: bool | None = None
    if exists and expected_size is not None and actual_size is not None:
        size_ok = actual_size == expected_size

    return FileValidation(
        filename=item.filename,
        path=str(path),
        exists=exists,
        expected_checksum=item.checksum,
        actual_checksum=actual_checksum,
        expected_size=expected_size,
        actual_size=actual_size,
        checksum_ok=checksum_ok,
        size_ok=size_ok,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def verify_manifest(manifest: Manifest, output_dir: Path) -> ValidationResult:
    """
    Verify all items in *manifest* against files in *output_dir*.

    Looks for extracted TIF files in ``output_dir/tif/``.

    Parameters
    ----------
    manifest:
        A loaded Manifest object.
    output_dir:
        The root directory passed to ``download_items()``.

    Returns
    -------
    ValidationResult with per-file details.
    """
    tif_dir = output_dir / "tif"
    checked_at = datetime.now(timezone.utc).isoformat()

    details: list[FileValidation] = []
    for mi in manifest.items:
        details.append(_verify_one(mi, tif_dir))

    files_ok = sum(
        1 for d in details
        if d.exists and (d.checksum_ok is None or d.checksum_ok)
    )
    files_missing = sum(1 for d in details if not d.exists)
    files_corrupt = sum(1 for d in details if d.checksum_ok is False)

    return ValidationResult(
        manifest_path=str(output_dir / "manifest.json"),
        checked_at=checked_at,
        files_ok=files_ok,
        files_missing=files_missing,
        files_corrupt=files_corrupt,
        details=details,
    )
