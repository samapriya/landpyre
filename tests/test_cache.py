"""
tests/test_cache.py — Unit tests for cache read/write/filter with typed models.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import patch

from landpyre import cache
from landpyre.errors import CacheNotFoundError, CacheSchemaMismatchError
from landpyre.models import CatalogFilter, SCHEMA_VERSION
from tests import SAMPLE_ITEMS


def test_save_and_load_cache(tmp_path):
    fake_cache = tmp_path / "landfire_latest.json"
    with (
        patch.object(cache, "cache_path", return_value=fake_cache),
    ):
        snap = cache.save_cache(SAMPLE_ITEMS)
        assert fake_cache.exists()
        assert snap.item_count == len(SAMPLE_ITEMS)

        loaded = cache.load_cache()
        assert loaded.item_count == len(SAMPLE_ITEMS)
        assert loaded.items[0].region == "Hawaii"
        assert "last_run" in loaded.model_dump()


def test_save_writes_schema_version(tmp_path):
    fake_cache = tmp_path / "landfire_latest.json"
    with patch.object(cache, "cache_path", return_value=fake_cache):
        cache.save_cache(SAMPLE_ITEMS)
        raw = json.loads(fake_cache.read_text())
        assert raw["schema_version"] == SCHEMA_VERSION


def test_load_cache_missing_raises(tmp_path):
    fake_cache = tmp_path / "does_not_exist.json"
    with patch.object(cache, "cache_path", return_value=fake_cache):
        with pytest.raises(CacheNotFoundError):
            cache.load_cache()


def test_load_cache_old_schema_raises(tmp_path):
    fake_cache = tmp_path / "landfire_latest.json"
    # Write a v1 cache (schema_version missing = treated as 1)
    fake_cache.write_text(json.dumps({
        "schema_version": 1,
        "last_run": "2024-01-01",
        "item_count": 0,
        "items": [],
    }))
    with patch.object(cache, "cache_path", return_value=fake_cache):
        with pytest.raises(CacheSchemaMismatchError):
            cache.load_cache()


def test_get_items_no_filter(tmp_path):
    fake_cache = tmp_path / "landfire_latest.json"
    with patch.object(cache, "cache_path", return_value=fake_cache):
        cache.save_cache(SAMPLE_ITEMS)
        result = cache.get_items()
        assert len(result) == len(SAMPLE_ITEMS)


def test_get_items_filter_by_region(tmp_path):
    fake_cache = tmp_path / "landfire_latest.json"
    with patch.object(cache, "cache_path", return_value=fake_cache):
        cache.save_cache(SAMPLE_ITEMS)
        f = CatalogFilter(region="Hawaii")
        result = cache.get_items(f)
        assert len(result) == 1
        assert result[0].region == "Hawaii"


def test_get_items_filter_by_version(tmp_path):
    fake_cache = tmp_path / "landfire_latest.json"
    with patch.object(cache, "cache_path", return_value=fake_cache):
        cache.save_cache(SAMPLE_ITEMS)
        f = CatalogFilter(version="LF 2020")
        result = cache.get_items(f)
        assert len(result) == 1
        assert result[0].region == "CONUS"


def test_get_items_filter_combined(tmp_path):
    fake_cache = tmp_path / "landfire_latest.json"
    with patch.object(cache, "cache_path", return_value=fake_cache):
        cache.save_cache(SAMPLE_ITEMS)

        # Alaska + LF 2020 → no match
        result = cache.get_items(CatalogFilter(region="Alaska", version="LF 2020"))
        assert result == []

        # Alaska + LF 2016 → one match
        result = cache.get_items(CatalogFilter(region="Alaska", version="LF 2016"))
        assert len(result) == 1
        assert result[0].region == "Alaska"


def test_get_items_case_insensitive(tmp_path):
    fake_cache = tmp_path / "landfire_latest.json"
    with patch.object(cache, "cache_path", return_value=fake_cache):
        cache.save_cache(SAMPLE_ITEMS)
        assert len(cache.get_items(CatalogFilter(region="hawaii"))) == 1
        assert len(cache.get_items(CatalogFilter(version="lf 2022"))) == 1


def test_cache_timestamp_present(tmp_path):
    fake_cache = tmp_path / "landfire_latest.json"
    with patch.object(cache, "cache_path", return_value=fake_cache):
        cache.save_cache(SAMPLE_ITEMS)
        loaded = cache.load_cache()
    assert isinstance(loaded.last_run, str)
    assert len(loaded.last_run) > 0
    assert any(c.isdigit() for c in loaded.last_run)


def test_malformed_items_skipped_on_load(tmp_path):
    """Items with missing required fields are silently dropped rather than crashing."""
    fake_cache = tmp_path / "landfire_latest.json"
    raw = {
        "schema_version": SCHEMA_VERSION,
        "last_run": "2025-01-01",
        "item_count": 2,
        "items": [
            {"download_url": "https://example.com/a.zip", "region": "Hawaii"},
            {"region": "broken_no_url"},  # missing download_url — should be skipped
        ],
    }
    fake_cache.write_text(json.dumps(raw))
    with patch.object(cache, "cache_path", return_value=fake_cache):
        snap = cache.load_cache()
    assert snap.item_count == 1
    assert snap.items[0].region == "Hawaii"
