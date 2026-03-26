"""
tests/test_models.py — Unit tests for Pydantic domain models and filter logic.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from landpyre.models import (
    CatalogFilter,
    CatalogItem,
    CatalogSnapshot,
    FilterMode,
    Manifest,
    ManifestItem,
    SCHEMA_VERSION,
)
from tests import SAMPLE_ITEMS


# ---------------------------------------------------------------------------
# CatalogItem
# ---------------------------------------------------------------------------


def test_catalog_item_requires_download_url():
    with pytest.raises(ValidationError):
        CatalogItem()  # missing download_url


def test_catalog_item_file_size_bytes_gb():
    item = CatalogItem(download_url="https://example.com/file.zip", file_size="1.5 GB")
    assert item.file_size_bytes == int(1.5 * 1024**3)


def test_catalog_item_file_size_bytes_mb():
    item = CatalogItem(download_url="https://example.com/file.zip", file_size="512 MB")
    assert item.file_size_bytes == 512 * 1024**2


def test_catalog_item_file_size_bytes_none():
    item = CatalogItem(download_url="https://example.com/file.zip", file_size=None)
    assert item.file_size_bytes is None


def test_catalog_item_file_size_bytes_unparseable():
    item = CatalogItem(download_url="https://example.com/file.zip", file_size="unknown")
    assert item.file_size_bytes is None


def test_catalog_item_filename():
    item = CatalogItem(download_url="https://example.com/path/hawaii_fbfm40.zip")
    assert item.filename == "hawaii_fbfm40.zip"


def test_catalog_item_display_label():
    item = SAMPLE_ITEMS[0]
    assert "Hawaii" in item.display_label
    assert "LF 2022" in item.display_label


def test_catalog_item_from_dict():
    d = {
        "download_url": "https://example.com/a.zip",
        "region": "Hawaii",
        "version": "LF 2022",
        "extra_unknown_field": "should_be_ignored",
    }
    item = CatalogItem.from_dict(d)
    assert item.region == "Hawaii"
    assert item.version == "LF 2022"


def test_catalog_item_serialises_to_dict():
    item = SAMPLE_ITEMS[0]
    d = item.model_dump()
    assert d["region"] == "Hawaii"
    assert d["download_url"].startswith("https://")


# ---------------------------------------------------------------------------
# CatalogFilter
# ---------------------------------------------------------------------------


def test_filter_substring_match():
    f = CatalogFilter(region="haw")
    assert f.matches(SAMPLE_ITEMS[0])   # Hawaii
    assert not f.matches(SAMPLE_ITEMS[1])  # CONUS


def test_filter_case_insensitive():
    f = CatalogFilter(region="HAWAII")
    assert f.matches(SAMPLE_ITEMS[0])


def test_filter_and_logic():
    f = CatalogFilter(region="Hawaii", version="LF 2022")
    assert f.matches(SAMPLE_ITEMS[0])
    assert not f.matches(SAMPLE_ITEMS[1])


def test_filter_none_field_is_wildcard():
    f = CatalogFilter(version=None, region=None)
    for item in SAMPLE_ITEMS:
        assert f.matches(item)


def test_filter_exact_mode():
    f = CatalogFilter(region="Hawaii", mode=FilterMode.EXACT)
    assert f.matches(SAMPLE_ITEMS[0])
    f2 = CatalogFilter(region="haw", mode=FilterMode.EXACT)
    assert not f2.matches(SAMPLE_ITEMS[0])


def test_filter_regex_mode():
    f = CatalogFilter(version=r"LF 20(22|24)", mode=FilterMode.REGEX)
    assert f.matches(SAMPLE_ITEMS[0])   # LF 2022
    assert not f.matches(SAMPLE_ITEMS[1])  # LF 2020


def test_filter_fuzzy_mode():
    f = CatalogFilter(product="fbfm", mode=FilterMode.FUZZY, fuzzy_threshold=0.5)
    assert f.matches(SAMPLE_ITEMS[0])   # FBFM40


def test_filter_from_kwargs():
    f = CatalogFilter.from_kwargs(region="Alaska")
    assert f.matches(SAMPLE_ITEMS[2])
    assert not f.matches(SAMPLE_ITEMS[0])


# ---------------------------------------------------------------------------
# CatalogSnapshot
# ---------------------------------------------------------------------------


def test_snapshot_syncs_item_count():
    snap = CatalogSnapshot(
        schema_version=SCHEMA_VERSION,
        last_run="2025-01-01 00:00:00 UTC",
        item_count=0,   # will be overwritten by validator
        items=SAMPLE_ITEMS,
    )
    assert snap.item_count == len(SAMPLE_ITEMS)


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


def test_manifest_item_from_catalog_item():
    mi = ManifestItem.from_catalog_item(SAMPLE_ITEMS[0])
    assert mi.download_url == SAMPLE_ITEMS[0].download_url
    assert mi.region == "Hawaii"
    assert mi.checksum == SAMPLE_ITEMS[0].checksum


def test_manifest_syncs_item_count():
    m = Manifest(
        created_at="2025-01-01T00:00:00Z",
        items=[ManifestItem.from_catalog_item(i) for i in SAMPLE_ITEMS],
    )
    assert m.item_count == len(SAMPLE_ITEMS)
