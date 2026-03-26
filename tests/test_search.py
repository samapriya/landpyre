"""
tests/test_search.py — Unit tests for the fuzzy search engine.
"""

from __future__ import annotations

import pytest
from landpyre.search import search_catalog, _tokenise
from tests import SAMPLE_ITEMS


def test_tokenise_basic():
    assert _tokenise("Hawaii LF 2022") == {"hawaii", "lf", "2022"}


def test_tokenise_none():
    assert _tokenise(None) == set()


def test_tokenise_empty():
    assert _tokenise("") == set()


def test_search_returns_results():
    results = search_catalog("hawaii fuel", SAMPLE_ITEMS)
    assert len(results) > 0


def test_search_hawaii_ranks_first():
    results = search_catalog("hawaii", SAMPLE_ITEMS)
    assert results[0].item.region == "Hawaii"


def test_search_score_between_0_and_1():
    results = search_catalog("fire behavior", SAMPLE_ITEMS)
    for r in results:
        assert 0.0 <= r.score <= 1.0


def test_search_empty_query_returns_nothing():
    results = search_catalog("", SAMPLE_ITEMS)
    assert results == []


def test_search_no_match_returns_empty():
    results = search_catalog("zzzzznonexistent", SAMPLE_ITEMS, threshold=0.5)
    assert results == []


def test_search_limit_respected():
    results = search_catalog("fire", SAMPLE_ITEMS, limit=1)
    assert len(results) <= 1


def test_search_threshold_filters_low_scores():
    results_all = search_catalog("fire", SAMPLE_ITEMS, threshold=0.0)
    results_strict = search_catalog("fire", SAMPLE_ITEMS, threshold=0.9)
    assert len(results_strict) <= len(results_all)


def test_search_results_sorted_descending():
    results = search_catalog("fire behavior alaska", SAMPLE_ITEMS)
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)
