"""
commands/list_cmd.py — Browse and filter the cached LANDFIRE catalogue.
"""

from __future__ import annotations

import json as _json

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from landpyre import cache
from landpyre.errors import CacheNotFoundError, CacheSchemaMismatchError
from landpyre.models import CatalogFilter
from landpyre.ui.banner import (
    STYLE_DIM,
    STYLE_ERR,
    STYLE_HEADER,
    STYLE_REGION,
    STYLE_SIZE,
    STYLE_VERSION,
    STYLE_WARN,
)

console = Console()


def _build_table(items: list, show_url: bool) -> Table:
    table = Table(
        show_header=True,
        header_style=STYLE_HEADER,
        border_style="bright_black",
        expand=True,
        row_styles=["", "dim"],
    )
    table.add_column("#", style="bright_black", width=5, no_wrap=True)
    table.add_column("Theme", style="bold white", max_width=22)
    table.add_column("Product", max_width=28)
    table.add_column("Region", style=STYLE_REGION, max_width=18)
    table.add_column("Version", style=STYLE_VERSION, max_width=18)
    table.add_column("Size", style=STYLE_SIZE, width=12, justify="right")
    if show_url:
        table.add_column("URL", style="blue", max_width=50, no_wrap=True)

    for idx, item in enumerate(items, start=1):
        row = [
            str(idx),
            item.theme or "—",
            item.product or "—",
            item.region or "—",
            item.version or "—",
            item.file_size or "—",
        ]
        if show_url:
            row.append(item.download_url or "—")
        table.add_row(*row)

    return table


@click.command()
@click.option("--version", "-V", default=None, help="Filter by version, e.g. 'LF 2022'.")
@click.option("--region", "-r", default=None, help="Filter by region, e.g. 'Hawaii'.")
@click.option("--theme", "-t", default=None, help="Filter by theme keyword.")
@click.option("--limit", "-l", default=50, show_default=True, help="Max rows to display.")
@click.option("--url", "show_url", is_flag=True, default=False, help="Also show download URLs.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def list_cmd(
    version: str | None,
    region: str | None,
    theme: str | None,
    limit: int,
    show_url: bool,
    as_json: bool,
) -> None:
    """
    List cached LANDFIRE catalogue entries with optional filters.

    \b
    Examples:
      landpyre list
      landpyre list --version "LF 2022"
      landpyre list --region "Hawaii" --version "LF 2022"
      landpyre list --theme "Fire" --limit 20 --url
      landpyre list --region "CONUS" --json
    """
    f = CatalogFilter(version=version, region=region, theme=theme)

    try:
        items = cache.get_items(f)
    except (CacheNotFoundError, CacheSchemaMismatchError) as exc:
        console.print(f"[{STYLE_ERR}]✗ {exc}[/]")
        raise SystemExit(1)

    if not items:
        if as_json:
            click.echo(_json.dumps([]))
            return
        console.print(
            Panel(
                f"[{STYLE_WARN}]No items match the given filters.[/]",
                title="[yellow]No results[/yellow]",
                border_style="yellow",
            )
        )
        return

    if as_json:
        click.echo(_json.dumps(
            [item.model_dump(mode="json") for item in items[:limit]],
            indent=2,
        ))
        return

    total = len(items)
    shown = items[:limit]

    console.print()
    console.print(
        f"  [{STYLE_HEADER}]Showing {len(shown)} of {total} items[/]"
        + (f"  [dim](version=[/dim][{STYLE_VERSION}]{version}[/][dim])[/dim]" if version else "")
        + (f"  [dim](region=[/dim][{STYLE_REGION}]{region}[/][dim])[/dim]" if region else "")
    )
    console.print()
    console.print(_build_table(shown, show_url))

    if total > limit:
        console.print(
            f"\n  [{STYLE_DIM}]… {total - limit} more items hidden. "
            f"Use --limit {total} to see all.[/{STYLE_DIM}]"
        )
