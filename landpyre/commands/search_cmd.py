"""
commands/search_cmd.py — Fuzzy search over the cached LANDFIRE catalogue.
"""

from __future__ import annotations

import json as _json

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from landpyre import cache
from landpyre.errors import CacheNotFoundError, CacheSchemaMismatchError
from landpyre.search import search_catalog
from landpyre.ui.banner import STYLE_ERR, STYLE_HEADER, STYLE_REGION, STYLE_SIZE, STYLE_VERSION, STYLE_WARN

console = Console()


@click.command("search")
@click.argument("query")
@click.option("--limit", "-l", default=20, show_default=True, help="Maximum results.")
@click.option("--threshold", default=0.0, show_default=True,
              help="Minimum relevance score 0.0–1.0.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def search_cmd(query: str, limit: int, threshold: float, as_json: bool) -> None:
    """
    Fuzzy-search the catalogue by keyword.

    QUERY is a free-text string, e.g. "hawaii fuel 2022" or "CONUS LF 2024".
    Results are ranked by relevance score.

    \b
    Examples:
      landpyre search "hawaii fuel"
      landpyre search "CONUS LF 2022" --limit 10
      landpyre search "fire behavior" --json
      landpyre search "fuel model" --threshold 0.5
    """
    try:
        items = cache.get_items()
    except (CacheNotFoundError, CacheSchemaMismatchError) as exc:
        console.print(f"[{STYLE_ERR}]✗ {exc}[/]")
        raise SystemExit(1)

    results = search_catalog(query, items, limit=limit, threshold=threshold)

    if not results:
        if as_json:
            click.echo(_json.dumps([]))
            return
        console.print(Panel(
            f"[{STYLE_WARN}]No results for [bold]{query!r}[/bold].[/]\n\n"
            "Try fewer words or a lower --threshold.",
            title="[yellow]No results[/yellow]", border_style="yellow",
        ))
        return

    if as_json:
        click.echo(_json.dumps(
            [{"score": r.score, **r.item.model_dump(mode="json")} for r in results],
            indent=2,
        ))
        return

    table = Table(
        show_header=True, header_style=STYLE_HEADER,
        border_style="bright_black", expand=True, row_styles=["", "dim"],
    )
    table.add_column("Score", width=7, justify="right", style="bold green")
    table.add_column("Theme", style="bold white", max_width=22)
    table.add_column("Product", max_width=28)
    table.add_column("Region", style=STYLE_REGION, max_width=18)
    table.add_column("Version", style=STYLE_VERSION, max_width=18)
    table.add_column("Size", style=STYLE_SIZE, width=12, justify="right")

    for r in results:
        item = r.item
        table.add_row(
            f"{r.score:.0%}",
            item.theme or "—",
            item.product or "—",
            item.region or "—",
            item.version or "—",
            item.file_size or "—",
        )

    console.print()
    console.print(f"  [{STYLE_HEADER}]{len(results)} result(s) for [bold]{query!r}[/bold][/]")
    console.print()
    console.print(table)
