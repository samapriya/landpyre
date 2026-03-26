"""
config.py — Persistent user configuration for landpyre.

Config is stored at ``~/.config/landpyre/config.toml`` (XDG-style on
Linux/macOS; falls back to the same path on Windows).

All settings have defaults so the file is entirely optional.  The CLI
``landpyre config`` command exposes get/set/show subcommands backed by
this module.

Usage (SDK)
-----------
    from landpyre.config import load_config, save_config

    cfg = load_config()
    cfg.default_region = "CONUS"
    save_config(cfg)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from landpyre.errors import ConfigError
from landpyre.models import LandpyreConfig

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _config_dir() -> Path:
    if sys.platform == "win32":
        base = Path.home() / "AppData" / "Roaming"
    else:
        base = Path.home() / ".config"
    return base / "landpyre"


def config_path() -> Path:
    return _config_dir() / "config.toml"


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def load_config() -> LandpyreConfig:
    """
    Load config from disk, returning defaults if the file does not exist.

    Raises ConfigError if the file exists but cannot be parsed.
    """
    path = config_path()
    if not path.exists():
        return LandpyreConfig()

    try:
        import tomllib  # Python 3.11+
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            # No TOML library available — return defaults silently
            return LandpyreConfig()

    try:
        with path.open("rb") as fh:
            data: dict[str, Any] = tomllib.load(fh)
        return LandpyreConfig(**data)
    except Exception as exc:
        raise ConfigError(f"Cannot parse {path}: {exc}") from exc


def save_config(cfg: LandpyreConfig) -> None:
    """
    Write *cfg* to disk as TOML.

    Requires ``tomli_w`` (Python < 3.11) or the stdlib ``tomllib`` is
    read-only so we use ``tomli_w`` for writing on all versions.
    """
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import tomli_w  # type: ignore[import]
    except ImportError:
        raise ConfigError(
            "Writing config requires 'tomli_w'. Install it with: pip install tomli_w"
        )

    data = {k: v for k, v in cfg.model_dump().items() if v is not None}
    with path.open("wb") as fh:
        tomli_w.dump(data, fh)


def get_value(key: str) -> Any:
    cfg = load_config()
    if not hasattr(cfg, key):
        raise ConfigError(f"Unknown config key: {key!r}")
    return getattr(cfg, key)


def set_value(key: str, value: str) -> None:
    cfg = load_config()
    if not hasattr(cfg, key):
        raise ConfigError(f"Unknown config key: {key!r}")
    field_type = type(getattr(cfg, key))
    # Basic coercion: bool, int, str
    if field_type is bool:
        coerced: Any = value.lower() in {"true", "1", "yes"}
    elif field_type is int:
        coerced = int(value)
    else:
        coerced = value
    setattr(cfg, key, coerced)
    save_config(cfg)


# ---------------------------------------------------------------------------
# All available config keys with descriptions (used by `landpyre config show`)
# ---------------------------------------------------------------------------

CONFIG_KEYS: dict[str, str] = {
    "default_output":   "Default output directory for downloads",
    "default_workers":  "Default number of concurrent download threads",
    "default_region":   "Default region filter (e.g. 'CONUS', 'Hawaii')",
    "default_version":  "Default version filter (e.g. 'LF 2022')",
    "default_theme":    "Default theme filter",
    "cache_dir":        "Override cache directory (default: ~/.landpyre)",
    "log_level":        "Logging level: DEBUG, INFO, WARNING, ERROR",
    "auto_confirm":     "Skip download confirmation prompts automatically",
    "no_color":         "Disable Rich colour output",
}
