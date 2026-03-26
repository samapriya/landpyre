"""
commands/stats.py — Rich statistics summary of the cached LANDFIRE catalogue.
"""

from __future__ import annotations

import json as _json
from collections import Counter

import click
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from landpyre import cache
from landpyre.downloader import fmt_bytes
from landpyre.errors import CacheNotFoundError, CacheSchemaMismatchError
from landpyre.models import CatalogFilter
from landpyre.ui.banner import STYLE_ERR, STYLE_HEADER, STYLE_REGION, STYLE_VERSION

console = Console()


def _top_table(title: str, counter: Counter, style: str, n: int = 10) -> Table:
    table = Table(
        title=title, show_header=True, header_style=STYLE_HEADER,
        border_style="bright_black", title_style=f"bold {style}",
    )
    table.add_column("Name", style=style)
    table.add_column("Files", justify="right", style="bold white")
    for name, count in counter.most_common(n):
        table.add_row(name or "—", str(count))
    return table


@click.command()
@click.option("--version", "-V", default=None, help="Narrow stats to a specific version.")
@click.option("--region", "-r", default=None, help="Narrow stats to a specific region.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def stats(version: str | None, region: str | None, as_json: bool) -> None:
    """
    Display a rich summary of the cached LANDFIRE catalogue.

    \b
    Examples:
      landpyre stats
      landpyre stats --version "LF 2022"
      landpyre stats --region "Hawaii"
      landpyre stats --json
    """
    f = CatalogFilter(version=version, region=region)
    try:
        snapshot = cache.load_cache()
        items = cache.get_items(f)
    except (CacheNotFoundError, CacheSchemaMismatchError) as exc:
        console.print(f"[{STYLE_ERR}]✗ {exc}[/]")
        raise SystemExit(1)

    if not items:
        console.print("[yellow]No items match the filters.[/yellow]")
        return

    total_bytes = 0.0
    known_size_count = 0
    region_counter: Counter = Counter()
    version_counter: Counter = Counter()
    theme_counter: Counter = Counter()

    for item in items:
        b = item.file_size_bytes
        if b is not None:
            total_bytes += b
            known_size_count += 1
        region_counter[item.region or "Unknown"] += 1
        version_counter[item.version or "Unknown"] += 1
        theme_counter[item.theme or "Unknown"] += 1

    if as_json:
        click.echo(_json.dumps({
            "item_count": len(items),
            "total_bytes": total_bytes,
            "total_size_fmt": fmt_bytes(total_bytes),
            "known_size_count": known_size_count,
            "unique_regions": len(region_counter),
            "unique_versions": len(version_counter),
            "last_run": snapshot.last_run,
            "top_regions": dict(region_counter.most_common(10)),
            "top_versions": dict(version_counter.most_common(10)),
            "top_themes": dict(theme_counter.most_common(10)),
        }, indent=2))
        return

    filter_note = ""
    if version or region:
        parts = []
        if version:
            parts.append(f"version=[magenta]{version}[/magenta]")
        if region:
            parts.append(f"region=[cyan]{region}[/cyan]")
        filter_note = "  Filtered by: " + "  ".join(parts) + "\n\n"

    hero_text = (
        f"{filter_note}"
        f"  [bold white]Total files     :[/bold white]  [bold green]{len(items):,}[/bold green]\n"
        f"  [bold white]Aggregate size  :[/bold white]  [bold yellow]{fmt_bytes(total_bytes)}[/bold yellow]"
        f"  [dim](from {known_size_count:,} files with known size)[/dim]\n"
        f"  [bold white]Unique regions  :[/bold white]  [bold cyan]{len(region_counter)}[/bold cyan]\n"
        f"  [bold white]Unique versions :[/bold white]  [bold magenta]{len(version_counter)}[/bold magenta]\n"
        f"  [bold white]Cache timestamp :[/bold white]  [dim]{snapshot.last_run}[/dim]"
    )

    console.print()
    console.print(Panel(
        hero_text,
        title="[bold green]LANDFIRE Catalogue Statistics[/bold green]",
        border_style="green", padding=(1, 2),
    ))
    console.print()
    console.print(Columns([
        _top_table("Top Versions", version_counter, "magenta"),
        _top_table("Top Regions", region_counter, "cyan"),
        _top_table("Top Themes", theme_counter, "white"),
    ], equal=False, expand=True))

    # Per-version size breakdown
    console.print()
    version_bytes: dict[str, float] = {}
    version_files: dict[str, int] = {}
    for item in items:
        v = item.version or "Unknown"
        b = item.file_size_bytes or 0.0
        version_bytes[v] = version_bytes.get(v, 0.0) + b
        version_files[v] = version_files.get(v, 0) + 1

    size_table = Table(
        title="Size by Version", header_style=STYLE_HEADER,
        border_style="bright_black", title_style="bold magenta",
    )
    size_table.add_column("Version", style=STYLE_VERSION)
    size_table.add_column("Files", justify="right")
    size_table.add_column("Approx. Size", justify="right", style="yellow")
    for v, sz in sorted(version_bytes.items(), key=lambda x: x[1], reverse=True):
        size_table.add_row(v, str(version_files[v]), fmt_bytes(sz))
    console.print(size_table)
