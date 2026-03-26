"""
errors.py — Typed exception hierarchy for the landpyre SDK.

All landpyre exceptions derive from LandpyreError so callers can catch
the whole family with a single except clause if needed.
"""

from __future__ import annotations


class LandpyreError(Exception):
    """Base class for all landpyre exceptions."""


class CacheNotFoundError(LandpyreError):
    """Raised when the local cache file is missing or empty."""

    def __init__(self) -> None:
        super().__init__(
            "No cache found. Run `landpyre refresh` first."
        )


class CacheSchemaMismatchError(LandpyreError):
    """Raised when the cache was written by an older schema version."""

    def __init__(self, found: int, expected: int) -> None:
        super().__init__(
            f"Cache schema version {found} is outdated (expected {expected}). "
            "Run `landpyre refresh` to rebuild the cache."
        )


class ScraperError(LandpyreError):
    """Raised when the scraper cannot fetch or parse a page."""


class DownloadError(LandpyreError):
    """Raised when a download fails and cannot be retried."""


class ManifestError(LandpyreError):
    """Raised when a manifest file cannot be read or written."""


class ConfigError(LandpyreError):
    """Raised when config.toml cannot be parsed."""


class VerifyError(LandpyreError):
    """Raised when verification cannot be completed (not the same as a corrupt file)."""
