"""
ui/banner.py — ASCII art banner and shared Rich styling constants.
"""

from __future__ import annotations

from rich.console import Console
from rich.text import Text

LANDPYRE_ASCII = r"""
  _                    _
 | |    __ _ _ __   __| |_ __  _   _ _ __ ___
 | |   / _` | '_ \ / _` | '_ \| | | | '__/ _ \
 | |__| (_| | | | | (_| | |_) | |_| | | |  __/
 |_____\__,_|_| |_|\__,_| .__/ \__, |_|  \___|
                         |_|    |___/
"""

TAGLINE = "Discover & Download USGS LANDFIRE data."


def print_banner(console: Console) -> None:
    """Print the landpyre splash banner."""
    text = Text(LANDPYRE_ASCII, style="bold green")
    console.print(text)
    console.print(f"  [dim]{TAGLINE}[/dim]\n", highlight=False)


# ── Shared palette used across commands ─────────────────────────────────────

STYLE_HEADER  = "bold cyan"
STYLE_OK      = "bold green"
STYLE_WARN    = "bold yellow"
STYLE_ERR     = "bold red"
STYLE_DIM     = "dim"
STYLE_VERSION = "magenta"
STYLE_REGION  = "cyan"
STYLE_SIZE    = "yellow"
STYLE_URL     = "blue underline"
