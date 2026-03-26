"""
tests/test_scraper.py — Unit tests for scraper parsing and health check.
"""

from __future__ import annotations

import pytest
from landpyre.scraper import _split_region_version, check_scraper_health
from landpyre.models import CatalogItem
from tests import SAMPLE_ITEMS


@pytest.mark.parametrize(
    "raw, expected_region, expected_version",
    [
        ("Hawaii LF 2022",        "Hawaii",  "LF 2022"),
        ("CONUS LF 2020",         "CONUS",   "LF 2020"),
        ("Alaska LF 2016 Remap",  "Alaska",  "LF 2016 Remap"),
        ("CONUS LF 2014 NGDA",    "CONUS",   "LF 2014 NGDA"),
        ("LF 2022",               None,      "LF 2022"),
        ("Hawaii",                "Hawaii",  None),
        (None,                    None,      None),
        ("",                      None,      None),
    ],
)
def test_split_region_version(raw, expected_region, expected_version):
    region, version = _split_region_version(raw)
    assert region == expected_region
    assert version == expected_version


def test_health_check_passes_on_good_data():
    health = check_scraper_health(SAMPLE_ITEMS)
    assert health["ok"] is True
    assert health["item_count"] == len(SAMPLE_ITEMS)
    assert health["warnings"] == []


def test_health_check_fails_on_empty():
    health = check_scraper_health([])
    assert health["ok"] is False
    assert any("0 items" in w for w in health["warnings"])


def test_health_check_warns_on_missing_urls():
    bad_items = [
        CatalogItem(download_url="", region="Hawaii", version="LF 2022"),
    ] * 10
    health = check_scraper_health(bad_items)
    assert "download_url" in str(health["warnings"])


def test_health_check_field_coverage_keys():
    health = check_scraper_health(SAMPLE_ITEMS)
    assert "region" in health["field_coverage"]
    assert "version" in health["field_coverage"]
    assert "download_url" in health["field_coverage"]
