"""
tests/__init__.py — Shared test fixtures used across all test modules.
"""

from __future__ import annotations

from landpyre.models import CatalogItem

SAMPLE_ITEMS: list[CatalogItem] = [
    CatalogItem(
        theme="Fire Behavior",
        product="FBFM40",
        region_version="Hawaii LF 2022",
        region="Hawaii",
        version="LF 2022",
        file_size="1.2 GB",
        checksum="abc123def456abc123def456abc12345",
        download_url="https://www.landfire.gov/data-downloads/hawaii_fbfm40_lf2022.zip",
        source_page=1,
    ),
    CatalogItem(
        theme="Fuel",
        product="FVH",
        region_version="CONUS LF 2020",
        region="CONUS",
        version="LF 2020",
        file_size="48.3 GB",
        checksum=None,
        download_url="https://www.landfire.gov/data-downloads/conus_fvh_lf2020.zip",
        source_page=2,
    ),
    CatalogItem(
        theme="Fire Behavior",
        product="FRcc",
        region_version="Alaska LF 2016 Remap",
        region="Alaska",
        version="LF 2016 Remap",
        file_size="5.7 GB",
        checksum=None,
        download_url="https://www.landfire.gov/data-downloads/alaska_frcc_lf2016.zip",
        source_page=3,
    ),
]
