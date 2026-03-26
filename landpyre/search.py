"""
search.py — Fuzzy full-text search over the cached LANDFIRE catalogue.

Used by both the ``landpyre search`` CLI command and the SDK's
``LandpyreClient.search()`` method.

Algorithm
---------
Each CatalogItem is scored against the query by token overlap across
the union of (product, theme, region, version).  Results are ranked by
score descending, ties broken by item order (stable).  The score is
a float 0..1 representing the fraction of query tokens that appear in
the item's searchable text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from landpyre.models import CatalogItem

# ---------------------------------------------------------------------------
# Scored result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SearchResult:
    score: float
    item: CatalogItem

    # Exclude item from ordering so we sort purely by score
    def __lt__(self, other: "SearchResult") -> bool:
        return self.score > other.score  # descending

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SearchResult):
            return NotImplemented
        return self.score == other.score


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenise(text: str | None) -> set[str]:
    if not text:
        return set()
    return set(_TOKEN_RE.findall(text.lower()))


def _item_tokens(item: CatalogItem) -> set[str]:
    return (
        _tokenise(item.product)
        | _tokenise(item.theme)
        | _tokenise(item.region)
        | _tokenise(item.version)
    )


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _score(query_tokens: set[str], item_tokens: set[str]) -> float:
    if not query_tokens:
        return 0.0
    matched = query_tokens & item_tokens
    return len(matched) / len(query_tokens)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def search_catalog(
    query: str,
    items: list[CatalogItem],
    limit: int = 50,
    threshold: float = 0.0,
) -> list[SearchResult]:
    """
    Fuzzy-search *items* for *query*.

    Parameters
    ----------
    query:
        Free-text search string, e.g. ``"hawaii fuel 2022"``.
    items:
        List of CatalogItem (typically from cache.get_items()).
    limit:
        Maximum number of results to return.
    threshold:
        Minimum score (0..1) to include in results.
        0.0 means "any overlap"; 1.0 means "exact token match".

    Returns
    -------
    List of SearchResult sorted by score descending.
    """
    query_tokens = _tokenise(query)
    if not query_tokens:
        return []

    scored: list[SearchResult] = []
    for item in items:
        s = _score(query_tokens, _item_tokens(item))
        if s > threshold:
            scored.append(SearchResult(score=round(s, 4), item=item))

    scored.sort()
    return scored[:limit]
