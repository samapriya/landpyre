"""
commands/readme_cmd.py — Open the landpyre documentation in a browser.
"""

from __future__ import annotations

import webbrowser

import click
from rich.console import Console

from landpyre.ui.banner import STYLE_ERR, STYLE_OK, STYLE_WARN

console = Console()

DOCS_URL = "https://landpyre.geocarpentry.org/"


@click.command("readme")
def readme_cmd() -> None:
    """Open the landpyre documentation webpage in your browser."""
    try:
        opened = webbrowser.open(DOCS_URL, new=2)
        if not opened:
            console.print(f"[{STYLE_WARN}]Your setup does not have a monitor.[/]")
            console.print(f"  Visit: [cyan]{DOCS_URL}[/cyan]")
        else:
            console.print(f"[{STYLE_OK}]✓ Opening documentation…[/]")
            console.print(f"  [dim]{DOCS_URL}[/dim]")
    except Exception as exc:  # noqa: BLE001
        console.print(f"[{STYLE_ERR}]✗ {exc}[/]")
        console.print(f"  Visit: [cyan]{DOCS_URL}[/cyan]")
