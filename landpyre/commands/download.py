"""
commands/download.py — Download LANDFIRE files with pre-flight summary and progress.
"""

from __future__ import annotations

import json as _json
from pathlib import Path

import click
from landpyre import cache
from landpyre.downloader import (download_items, dry_run_summary, fmt_bytes,
                                 open_output_folder, parse_bytes)
from landpyre.errors import (CacheNotFoundError, CacheSchemaMismatchError,
                             ManifestError)
from landpyre.manifest import load_manifest, manifest_to_catalog_items
from landpyre.models import CatalogFilter, CatalogItem
from landpyre.ui.banner import (STYLE_ERR, STYLE_HEADER, STYLE_OK,
                                STYLE_REGION, STYLE_SIZE, STYLE_VERSION,
                                STYLE_WARN)
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def _pre_flight_panel(items: list[CatalogItem], output_dir: Path) -> None:
    PREVIEW_LIMIT = 25
    total_bytes = 0.0
    known = 0
    for item in items:
        b = item.file_size_bytes
        if b is not None:
            total_bytes += b
            known += 1

    table = Table(
        show_header=True, header_style=STYLE_HEADER,
        border_style="bright_black", expand=True, row_styles=["", "dim"],
    )
    table.add_column("#", width=4, style="bright_black")
    table.add_column("Region", style=STYLE_REGION, max_width=18)
    table.add_column("Version", style=STYLE_VERSION, max_width=18)
    table.add_column("Product", max_width=28)
    table.add_column("Size", style=STYLE_SIZE, width=12, justify="right")

    for idx, item in enumerate(items[:PREVIEW_LIMIT], 1):
        table.add_row(str(idx), item.region or "—", item.version or "—",
                      item.product or "—", item.file_size or "—")

    console.print()
    console.print(table)
    if len(items) > PREVIEW_LIMIT:
        console.print(f"  [dim]… and {len(items) - PREVIEW_LIMIT} more[/dim]")

    size_note = (
        f"[bold yellow]{fmt_bytes(total_bytes)}[/bold yellow]"
        if known == len(items)
        else f"[bold yellow]≥ {fmt_bytes(total_bytes)}[/bold yellow]  "
             f"[dim](size unknown for {len(items) - known} file(s))[/dim]"
    )

    console.print()
    console.print(Panel(
        f"  [bold white]Files to download:[/bold white]  [bold green]{len(items)}[/bold green]\n"
        f"  [bold white]Approx. total size:[/bold white] {size_note}\n"
        f"  [bold white]Output directory:[/bold white]   [dim]{output_dir.resolve()}[/dim]\n"
        f"  [bold white]TIF files land in:[/bold white]  [dim]{(output_dir / 'tif').resolve()}[/dim]",
        title="[bold cyan]Download pre-flight[/bold cyan]",
        border_style="cyan", padding=(1, 2),
    ))


@click.command()
@click.option("--version", "-V", default=None, help="Filter by version, e.g. 'LF 2022'.")
@click.option("--region", "-r", default=None, help="Filter by region, e.g. 'Hawaii'.")
@click.option("--theme", "-t", default=None, help="Filter by theme keyword.")
@click.option("--manifest", "-m", "manifest_path", default=None,
              help="Path to a manifest.json file. Overrides version/region/theme filters.")
@click.option("--output", "-o", default=None, show_default=True,
              help="Root directory for downloaded TIF files (default: from config or 'landfire_output').")
@click.option("--workers", "-w", default=None, show_default=True,
              help="Concurrent download threads (default: from config or 4).")
@click.option("--yes", "-y", is_flag=True, default=False,
              help="Skip the confirmation prompt.")
@click.option("--dry-run", is_flag=True, default=False,
              help="Show what would be downloaded without hitting the network.")
@click.option("--open", "open_after", is_flag=True, default=False,
              help="Open the output folder in the file explorer after download.")
@click.option("--json", "as_json", is_flag=True, default=False,
              help="Emit result summary as JSON.")
def download_cmd(
    version: str | None,
    region: str | None,
    theme: str | None,
    manifest_path: str | None,
    output: str | None,
    workers: int | None,
    yes: bool,
    dry_run: bool,
    open_after: bool,
    as_json: bool,
) -> None:
    """
    Download LANDFIRE files and extract TIF data to a local directory.

    Pass --manifest to replay a saved manifest.json instead of filtering the
    live cache. Use --dry-run to preview without downloading.

    \b
    Examples:
      landpyre download --version "LF 2022" --output lf2022
      landpyre download --region "Hawaii" --version "LF 2022" --yes
      landpyre download --manifest manifest.json --output ./data
      landpyre download --region "CONUS" --dry-run
      landpyre download --version "LF 2024" --open
    """
    from landpyre.config import load_config
    cfg = load_config()
    output_dir = Path(output or cfg.default_output)
    n_workers = workers or cfg.default_workers

    # ── Resolve items ────────────────────────────────────────────────────────
    if manifest_path:
        try:
            manifest = load_manifest(manifest_path)
            items = manifest_to_catalog_items(manifest)
        except ManifestError as exc:
            console.print(f"[{STYLE_ERR}]✗ {exc}[/]")
            raise SystemExit(1)
    else:
        f = CatalogFilter(version=version, region=region, theme=theme)
        try:
            items = cache.get_items(f)
        except (CacheNotFoundError, CacheSchemaMismatchError) as exc:
            console.print(f"[{STYLE_ERR}]✗ {exc}[/]")
            raise SystemExit(1)

    if not items:
        msg = f"[{STYLE_WARN}]No catalogue items match the filters provided.[/]"
        if as_json:
            click.echo(_json.dumps({"status": "no_items"}))
            return
        console.print(Panel(msg, title="[yellow]No matching files[/yellow]", border_style="yellow"))
        return

    # ── Dry-run ──────────────────────────────────────────────────────────────
    if dry_run:
        summary = dry_run_summary(items, output_dir)
        if as_json:
            click.echo(_json.dumps(summary, indent=2))
        else:
            console.print()
            console.print(Panel(
                f"  [bold white]Files:[/bold white]       [bold green]{summary['item_count']}[/bold green]\n"
                f"  [bold white]Total size:[/bold white]  [bold yellow]{summary['total_bytes_fmt']}[/bold yellow]\n"
                f"  [bold white]Output dir:[/bold white]  [dim]{summary['output_dir']}[/dim]\n"
                f"  [bold white]TIF dir:[/bold white]     [dim]{summary['tif_dir']}[/dim]",
                title="[bold cyan]Dry run — nothing downloaded[/bold cyan]",
                border_style="cyan", padding=(1, 2),
            ))
        return

    # ── Pre-flight ───────────────────────────────────────────────────────────
    if not as_json:
        _pre_flight_panel(items, output_dir)

    # ── Confirm ──────────────────────────────────────────────────────────────
    if not yes and not cfg.auto_confirm and not as_json:
        console.print()
        answer = click.prompt("  Proceed with download? [Y/n]", default="Y", show_default=False)
        if answer.strip().lower() not in {"y", "yes", ""}:
            console.print(f"\n  [{STYLE_WARN}]Download cancelled.[/]")
            return

    # ── Download ─────────────────────────────────────────────────────────────
    if not as_json:
        console.print()
        console.print(f"  [{STYLE_HEADER}]Starting {len(items)} download(s) with {n_workers} worker(s)…[/]")
        console.print()

    results = download_items(items, output_dir, workers=n_workers)

    ok = [r for r in results if r.ok]
    skipped = [r for r in results if r.status.value == "skipped"]
    errors = [r for r in results if not r.ok and r.status.value != "skipped"]
    tif_count = sum(len(r.tifs_extracted) for r in ok + skipped)

    if as_json:
        click.echo(_json.dumps({
            "status": "complete",
            "ok": len(ok),
            "skipped": len(skipped),
            "errors": len(errors),
            "tifs_extracted": tif_count,
            "output_dir": str(output_dir.resolve()),
            "failed_urls": [r.item.download_url for r in errors],
        }, indent=2))
        if open_after:
            open_output_folder(output_dir)
        return

    console.print()
    if errors:
        console.print(Panel(
            f"[{STYLE_OK}]✓ {len(ok)} file(s) downloaded  ·  {tif_count} TIF(s) extracted[/]\n"
            f"[{STYLE_ERR}]✗ {len(errors)} file(s) failed[/]\n\n"
            + "\n".join(f"  [red]•[/red] {e.item.download_url}\n    [dim]{e.error}[/dim]" for e in errors),
            title="[bold yellow]Download complete (with errors)[/bold yellow]",
            border_style="yellow",
        ))
    else:
        skip_note = f"  [dim]{len(skipped)} already existed, skipped.[/dim]\n\n" if skipped else "\n"
        console.print(Panel(
            f"[{STYLE_OK}]✓ {len(ok)} downloaded · {len(skipped)} skipped[/]\n"
            f"{skip_note}"
            f"  [bold white]TIF files available :[/bold white]  [bold green]{tif_count}[/bold green]\n"
            f"  [bold white]TIF output folder   :[/bold white]  [dim]{(output_dir / 'tif').resolve()}[/dim]",
            title="[bold green]Download complete[/bold green]",
            border_style="green", padding=(1, 2),
        ))

    if open_after:
        open_output_folder(output_dir)
