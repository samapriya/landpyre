"""
tests/test_downloader.py — Unit tests for downloader utilities.

Network-dependent tests (actual downloads) are excluded.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from landpyre.downloader import fmt_bytes, parse_bytes, dry_run_summary
from landpyre.models import DownloadStatus
from tests import SAMPLE_ITEMS


@pytest.mark.parametrize("s, expected", [
    ("1.2 GB",  int(1.2 * 1024**3)),
    ("512 MB",  512 * 1024**2),
    ("100 KB",  100 * 1024),
    ("1,024 MB", 1024 * 1024**2),
    ("0 B",     0),
    (None,      None),
    ("unknown", None),
    ("",        None),
])
def test_parse_bytes(s, expected):
    assert parse_bytes(s) == expected


@pytest.mark.parametrize("b, expected", [
    (1024**4,       "1.00 TB"),
    (1024**3,       "1.00 GB"),
    (1024**2,       "1.00 MB"),
    (1024,          "1.00 KB"),
    (512,           "512 B"),
])
def test_fmt_bytes(b, expected):
    assert fmt_bytes(b) == expected


def test_dry_run_summary_structure(tmp_path):
    summary = dry_run_summary(SAMPLE_ITEMS, tmp_path)
    assert summary["item_count"] == len(SAMPLE_ITEMS)
    assert "total_bytes" in summary
    assert "total_bytes_fmt" in summary
    assert len(summary["items"]) == len(SAMPLE_ITEMS)
    assert summary["items"][0]["filename"] == SAMPLE_ITEMS[0].filename


def test_dry_run_summary_known_size_count(tmp_path):
    # SAMPLE_ITEMS[0] and [2] have file_size; [1] also has one — all 3 known
    summary = dry_run_summary(SAMPLE_ITEMS, tmp_path)
    assert summary["known_size_count"] == 3


def test_download_items_dry_run_returns_skipped():
    from landpyre.downloader import download_items
    results = download_items(SAMPLE_ITEMS, Path("/tmp/does_not_matter"), dry_run=True)
    assert len(results) == len(SAMPLE_ITEMS)
    assert all(r.status == DownloadStatus.SKIPPED for r in results)
