"""
tests/test_manifest.py — Unit tests for manifest save, load, and conversion.
"""

from __future__ import annotations

import json
import pytest

from landpyre.errors import ManifestError
from landpyre.manifest import load_manifest, manifest_to_catalog_items, save_manifest
from landpyre.models import SCHEMA_VERSION
from tests import SAMPLE_ITEMS


def test_save_manifest_creates_file(tmp_path):
    dest = tmp_path / "manifest.json"
    m = save_manifest(SAMPLE_ITEMS, path=dest)
    assert dest.exists()
    assert m.item_count == len(SAMPLE_ITEMS)


def test_save_manifest_content(tmp_path):
    dest = tmp_path / "manifest.json"
    save_manifest(SAMPLE_ITEMS, path=dest)
    raw = json.loads(dest.read_text())
    assert raw["schema_version"] == SCHEMA_VERSION
    assert len(raw["items"]) == len(SAMPLE_ITEMS)
    assert raw["items"][0]["download_url"] == SAMPLE_ITEMS[0].download_url


def test_load_manifest_roundtrip(tmp_path):
    dest = tmp_path / "manifest.json"
    save_manifest(SAMPLE_ITEMS, path=dest)
    m = load_manifest(dest)
    assert m.item_count == len(SAMPLE_ITEMS)
    assert m.items[0].region == "Hawaii"


def test_load_manifest_missing_raises(tmp_path):
    with pytest.raises(ManifestError, match="not found"):
        load_manifest(tmp_path / "does_not_exist.json")


def test_load_manifest_invalid_json_raises(tmp_path):
    dest = tmp_path / "bad.json"
    dest.write_text("not valid json{{{")
    with pytest.raises(ManifestError):
        load_manifest(dest)


def test_manifest_to_catalog_items(tmp_path):
    dest = tmp_path / "manifest.json"
    save_manifest(SAMPLE_ITEMS, path=dest)
    m = load_manifest(dest)
    items = manifest_to_catalog_items(m)
    assert len(items) == len(SAMPLE_ITEMS)
    assert items[0].download_url == SAMPLE_ITEMS[0].download_url
    assert items[0].region == SAMPLE_ITEMS[0].region


def test_manifest_preserves_checksum(tmp_path):
    dest = tmp_path / "manifest.json"
    save_manifest(SAMPLE_ITEMS, path=dest)
    m = load_manifest(dest)
    assert m.items[0].checksum == SAMPLE_ITEMS[0].checksum


def test_save_manifest_with_cache_timestamp(tmp_path):
    dest = tmp_path / "manifest.json"
    m = save_manifest(SAMPLE_ITEMS, path=dest, source_cache_timestamp="2025-06-01 10:00:00 PDT")
    assert m.source_cache_timestamp == "2025-06-01 10:00:00 PDT"
