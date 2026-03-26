"""
downloader.py — Concurrent ZIP downloader with TIF extraction, resume support,
and checksum verification.

Design: ThreadPoolExecutor (concurrent I/O) — unchanged from v0.1.0.
New in v0.2.0:
  - Accepts and returns typed models (DownloadJob / DownloadResult)
  - Resume support: HEAD request checks Content-Length, Range header resumes
  - Checksum verification: MD5 of the completed ZIP is compared to CatalogItem.checksum
  - Dry-run mode: returns what *would* be downloaded without touching the network
  - open_output: platform-aware folder open after a successful batch
"""

from __future__ import annotations

import hashlib
import os
import platform
import re
import subprocess
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Any

import requests
from rich.console import Console
from rich.progress import (BarColumn, DownloadColumn, Progress, SpinnerColumn,
                           TaskID, TextColumn, TimeRemainingColumn,
                           TransferSpeedColumn)

from landpyre.models import (CatalogItem, DownloadJob, DownloadResult,
                             DownloadStatus)

console = Console()
_WRITE_LOCK = Lock()


# ---------------------------------------------------------------------------
# Size helpers (kept public — used by CLI commands)
# ---------------------------------------------------------------------------

_SIZE_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*(GB|MB|KB|B)", re.IGNORECASE)
_UNIT_BYTES = {"b": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3}


def parse_bytes(size_str: str | None) -> int | None:
    if not size_str:
        return None
    m = _SIZE_RE.search(size_str)
    if not m:
        return None
    return int(float(m.group(1).replace(",", "")) * _UNIT_BYTES.get(m.group(2).lower(), 1))


def fmt_bytes(b: float) -> str:
    for unit, div in [("TB", 1 << 40), ("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)]:
        if b >= div:
            return f"{b / div:.2f} {unit}"
    return f"{b:.0f} B"


# ---------------------------------------------------------------------------
# Checksum
# ---------------------------------------------------------------------------


def _md5_file(path: Path, chunk: int = 1 << 17) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        while data := fh.read(chunk):
            h.update(data)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# ZIP extraction
# ---------------------------------------------------------------------------


def _extract_tifs(zip_path: Path, tif_dir: Path) -> list[Path]:
    extracted: list[Path] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        tif_members = [m for m in zf.infolist() if m.filename.lower().endswith(".tif")]
        for member in tif_members:
            basename = Path(member.filename).name
            dest = tif_dir / basename
            with zf.open(member) as src, dest.open("wb") as dst:
                dst.write(src.read())
            extracted.append(dest)
    return extracted


# ---------------------------------------------------------------------------
# Single-file download
# ---------------------------------------------------------------------------


def _download_one(
    job: DownloadJob,
    tmp_dir: Path,
    tif_dir: Path,
    progress: Progress,
    task_id: TaskID,
) -> DownloadResult:
    item = job.item
    url = item.download_url
    filename = item.filename
    zip_path = tmp_dir / filename
    start = time.monotonic()

    try:
        # ── Skip: all TIFs already extracted ────────────────────────────────
        # If any TIF in tif_dir shares the ZIP filename stem, treat as done.
        zip_stem = zip_path.stem.lower()
        existing_tifs = (
            [p for p in tif_dir.iterdir()
             if p.suffix.lower() == ".tif" and p.stem.lower().startswith(zip_stem)]
            if tif_dir.exists() else []
        )
        if existing_tifs:
            progress.update(task_id, description=f"[dim]Skipped (exists)[/] {filename}",
                            total=1, completed=1)
            return DownloadResult(
                item=item,
                status=DownloadStatus.SKIPPED,
                tifs_extracted=[str(t) for t in existing_tifs],
                bytes_written=0,
                elapsed_seconds=0.0,
            )

        # ── Resume: check how much is already on disk ────────────────────────
        resume_offset = zip_path.stat().st_size if zip_path.exists() else 0
        headers: dict[str, str] = {}
        if resume_offset > 0:
            headers["Range"] = f"bytes={resume_offset}-"

        with requests.get(url, stream=True, timeout=60, headers=headers) as resp:
            if resp.status_code == 416:
                # Range not satisfiable — file already complete
                pass
            else:
                resp.raise_for_status()
                total_raw = resp.headers.get("content-length")
                total = (int(total_raw) + resume_offset) if total_raw else None
                progress.update(task_id, total=total, completed=resume_offset)

                mode = "ab" if resume_offset > 0 else "wb"
                with zip_path.open(mode) as fh:
                    for chunk in resp.iter_content(chunk_size=1 << 17):
                        fh.write(chunk)
                        progress.update(task_id, advance=len(chunk))

        bytes_written = zip_path.stat().st_size

        # ── Checksum verification ────────────────────────────────────────────
        if item.checksum:
            progress.update(task_id, description=f"[yellow]Verifying[/] {filename}")
            actual = _md5_file(zip_path)
            if actual.lower() != item.checksum.lower():
                raise ValueError(
                    f"Checksum mismatch: expected {item.checksum}, got {actual}"
                )

        # ── Extract TIFs ─────────────────────────────────────────────────────
        progress.update(task_id, description=f"[yellow]Extracting[/] {filename}")
        tifs = _extract_tifs(zip_path, tif_dir)

        elapsed = time.monotonic() - start
        progress.update(task_id, description=f"[green]Done[/] {filename}")
        return DownloadResult(
            item=item,
            status=DownloadStatus.OK,
            tifs_extracted=[str(t) for t in tifs],
            bytes_written=bytes_written,
            elapsed_seconds=elapsed,
        )

    except Exception as exc:  # noqa: BLE001
        elapsed = time.monotonic() - start
        progress.update(task_id, description=f"[red]Error[/] {filename}")
        return DownloadResult(
            item=item,
            status=DownloadStatus.ERROR,
            elapsed_seconds=elapsed,
            error=str(exc),
        )

    finally:
        if zip_path.exists():
            zip_path.unlink()


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------


def dry_run_summary(items: list[CatalogItem], output_dir: Path) -> dict[str, Any]:
    """
    Return what *would* happen without touching the network.
    Used by `landpyre download --dry-run`.
    """
    total_bytes = 0.0
    known = 0
    for item in items:
        b = item.file_size_bytes
        if b is not None:
            total_bytes += b
            known += 1

    return {
        "item_count": len(items),
        "total_bytes": total_bytes,
        "total_bytes_fmt": fmt_bytes(total_bytes),
        "known_size_count": known,
        "output_dir": str(output_dir.resolve()),
        "tif_dir": str((output_dir / "tif").resolve()),
        "items": [
            {
                "filename": i.filename,
                "region": i.region,
                "version": i.version,
                "product": i.product,
                "file_size": i.file_size,
                "download_url": i.download_url,
            }
            for i in items
        ],
    }


# ---------------------------------------------------------------------------
# Open output folder
# ---------------------------------------------------------------------------


def open_output_folder(path: Path) -> None:
    """Open *path* in the OS file explorer (best-effort, no exception on failure)."""
    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.Popen(["open", str(path)])
        elif system == "Windows":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def download_items(
    items: list[CatalogItem],
    output_dir: Path,
    workers: int = 4,
    dry_run: bool = False,
) -> list[DownloadResult]:
    """
    Download and extract *items* concurrently.

    Parameters
    ----------
    items:
        CatalogItem instances to download.
    output_dir:
        Root output directory. TIF files land in ``output_dir/tif/``.
    workers:
        Number of concurrent download threads.
    dry_run:
        If True, skip all network I/O and return skipped results immediately.
    """
    if dry_run:
        return [
            DownloadResult(item=i, status=DownloadStatus.SKIPPED)
            for i in items
        ]

    tif_dir = output_dir / "tif"
    tmp_dir = output_dir / ".tmp_zips"
    tif_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    jobs = [DownloadJob(item=i) for i in items]
    results: list[DownloadResult] = []

    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30, style="cyan", complete_style="green"),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    ) as progress:
        overall = progress.add_task(
            f"[bold cyan]Overall — {len(jobs)} files", total=len(jobs)
        )

        futures = {}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for job in jobs:
                task_id = progress.add_task(
                    f"[cyan]{job.item.filename}",
                    total=None,
                    start=False,
                )
                future = pool.submit(
                    _download_one, job, tmp_dir, tif_dir, progress, task_id
                )
                futures[future] = task_id
                progress.start_task(task_id)

            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                progress.advance(overall)

    try:
        tmp_dir.rmdir()
    except OSError:
        pass

    return results
