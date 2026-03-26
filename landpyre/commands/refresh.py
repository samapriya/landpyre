"""
commands/refresh.py — Scrape the LANDFIRE catalogue and update the local cache.
"""

from __future__ import annotations

import click
from landpyre import cache
from landpyre.errors import CacheSchemaMismatchError, ScraperError
from landpyre.scraper import check_scraper_health, scrape_catalogue
from landpyre.ui.banner import STYLE_ERR, STYLE_OK, STYLE_WARN
from rich.console import Console
from rich.panel import Panel
from rich.progress import (BarColumn, MofNCompleteColumn, Progress,
                           SpinnerColumn, TaskProgressColumn, TextColumn,
                           TimeRemainingColumn)

console = Console()


@click.command()
@click.option("--force", "-f", is_flag=True, default=False,
              help="Force refresh even if a recent cache already exists.")
@click.option("--check-scraper", is_flag=True, default=False,
              help="Run scraper health check and report field coverage without saving.")
@click.option("--json", "as_json", is_flag=True, default=False,
              help="Emit result as JSON.")
def refresh(force: bool, check_scraper: bool, as_json: bool) -> None:
    """
    Scrape the LANDFIRE catalogue and save it to the local cache.

    \b
    The cache is stored at:
      ~/.landpyre/landfire_latest.json

    All subsequent commands (list, stats, download) read from this cache,
    so you only need to scrape once. Run again with --force to update.

    \b
    Examples:
      landpyre refresh
      landpyre refresh --force
      landpyre refresh --check-scraper
    """
    import json as _json

    # ── Early exit: cache already fresh ────────────────────────────────────
    if not force and not check_scraper:
        try:
            data = cache.load_cache()
            if as_json:
                click.echo(_json.dumps({
                    "status": "cache_exists",
                    "last_run": data.last_run,
                    "item_count": data.item_count,
                }))
            else:
                console.print(
                    Panel(
                        f"[{STYLE_WARN}]Cache already exists[/] from [bold]{data.last_run}[/]"
                        f"\n[dim]Contains {data.item_count} items.[/dim]"
                        f"\n\nRun with [bold]--force[/bold] to refresh.",
                        title="[bold yellow]Cache exists[/bold yellow]",
                        border_style="yellow",
                    )
                )
            return
        except (FileNotFoundError, CacheSchemaMismatchError):
            pass  # No valid cache — proceed with scrape

    console.print()
    console.print("[bold cyan]  Probing LANDFIRE catalogue pages…[/bold cyan]")
    console.print()

    with Progress(
        SpinnerColumn(spinner_name="dots", style="cyan"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=38, style="cyan", complete_style="green"),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task("[cyan]Scraping pages…", total=None)

        def on_page(current: int, total: int) -> None:
            progress.update(
                task, total=total, completed=current,
                description=f"[cyan]Scraping page {current}/{total}…",
            )

        try:
            items = scrape_catalogue(progress_callback=on_page)
        except ScraperError as exc:
            console.print(f"\n[{STYLE_ERR}]Error:[/] {exc}")
            raise SystemExit(1)

    # ── Health check output ─────────────────────────────────────────────────
    health = check_scraper_health(items)
    if not health["ok"]:
        console.print()
        for w in health["warnings"]:
            console.print(f"  [{STYLE_WARN}]⚠ {w}[/]")

    if check_scraper:
        if as_json:
            click.echo(_json.dumps(health, indent=2))
        else:
            console.print()
            console.print(Panel(
                "\n".join([
                    f"  Items scraped: [bold]{health['item_count']}[/bold]",
                    "",
                    "  Field coverage:",
                    *[
                        f"    [dim]{k}:[/dim]  {v:.0%}"
                        for k, v in health["field_coverage"].items()
                    ],
                    "",
                    f"  Status: [{'bold green' if health['ok'] else 'bold red'}]"
                    f"{'✓ healthy' if health['ok'] else '✗ issues detected'}[/]",
                ]),
                title="[bold cyan]Scraper health check[/bold cyan]",
                border_style="cyan" if health["ok"] else "red",
            ))
        return

    # ── Save ────────────────────────────────────────────────────────────────
    snapshot = cache.save_cache(items)

    if as_json:
        click.echo(_json.dumps({
            "status": "ok",
            "item_count": snapshot.item_count,
            "last_run": snapshot.last_run,
            "cache_path": str(cache.cache_path()),
        }))
    else:
        console.print()
        console.print(
            Panel(
                f"[{STYLE_OK}]✓ Catalogue refreshed successfully![/]\n\n"
                f"  [bold]Items cached :[/bold]  {snapshot.item_count}\n"
                f"  [bold]Timestamp    :[/bold]  {snapshot.last_run}\n"
                f"  [bold]Saved to     :[/bold]  [dim]{cache.cache_path()}[/dim]",
                title="[bold green]Refresh complete[/bold green]",
                border_style="green",
            )
        )
