"""
commands/manifest_cmd.py — Generate and inspect download manifests.
"""

from __future__ import annotations

import json as _json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from landpyre import cache
from landpyre.errors import CacheNotFoundError, CacheSchemaMismatchError, ManifestError
from landpyre.manifest import load_manifest, save_manifest
from landpyre.models import CatalogFilter
from landpyre.ui.banner import STYLE_ERR, STYLE_HEADER, STYLE_OK, STYLE_REGION, STYLE_VERSION, STYLE_WARN

console = Console()


@click.command("manifest")
@click.option("--version", "-V", default=None, help="Filter by version, e.g. 'LF 2022'.")
@click.option("--region", "-r", default=None, help="Filter by region, e.g. 'Hawaii'.")
@click.option("--theme", "-t", default=None, help="Filter by theme keyword.")
@click.option("--output", "-o", default="manifest.json", show_default=True,
              help="Path to write the manifest file.")
@click.option("--show", "-s", "show_path", default=None,
              help="Path to an existing manifest.json to inspect (skips creation).")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def manifest_cmd(
    version: str | None,
    region: str | None,
    theme: str | None,
    output: str,
    show_path: str | None,
    as_json: bool,
) -> None:
    """
    Generate or inspect a portable download manifest.

    Without --show, filters the current cache and writes a manifest.json
    that can be replayed with `landpyre download --manifest`.

    \b
    Examples:
      landpyre manifest --version "LF 2022" --region "Hawaii"
      landpyre manifest --version "LF 2024" -o conus_2024.json
      landpyre manifest --show manifest.json
    """
    # ── Inspect existing manifest ────────────────────────────────────────────
    if show_path:
        try:
            m = load_manifest(show_path)
        except ManifestError as exc:
            console.print(f"[{STYLE_ERR}]✗ {exc}[/]")
            raise SystemExit(1)

        if as_json:
            click.echo(_json.dumps(m.model_dump(mode="json"), indent=2))
            return

        table = Table(show_header=True, header_style=STYLE_HEADER,
                      border_style="bright_black", expand=True, row_styles=["", "dim"])
        table.add_column("Product", max_width=28)
        table.add_column("Region", style=STYLE_REGION, max_width=18)
        table.add_column("Version", style=STYLE_VERSION, max_width=18)
        table.add_column("Size", width=12, justify="right", style="yellow")
        table.add_column("Checksum", style="dim", max_width=20)

        for mi in m.items:
            table.add_row(
                mi.product or "—", mi.region or "—", mi.version or "—",
                mi.file_size or "—",
                (mi.checksum[:8] + "…") if mi.checksum else "—",
            )

        console.print()
        console.print(Panel(
            f"  [bold white]Source:[/bold white]    [dim]{show_path}[/dim]\n"
            f"  [bold white]Created:[/bold white]   [dim]{m.created_at}[/dim]\n"
            f"  [bold white]Items:[/bold white]     [bold green]{m.item_count}[/bold green]",
            title="[bold cyan]Manifest[/bold cyan]", border_style="cyan",
        ))
        console.print()
        console.print(table)
        return

    # ── Create new manifest ──────────────────────────────────────────────────
    f = CatalogFilter(version=version, region=region, theme=theme)
    try:
        snapshot = cache.load_cache()
        items = cache.get_items(f)
    except (CacheNotFoundError, CacheSchemaMismatchError) as exc:
        console.print(f"[{STYLE_ERR}]✗ {exc}[/]")
        raise SystemExit(1)

    if not items:
        if as_json:
            click.echo(_json.dumps({"status": "no_items"}))
            return
        console.print(Panel(
            f"[{STYLE_WARN}]No catalogue items match the filters provided.[/]",
            title="[yellow]No matching items[/yellow]", border_style="yellow",
        ))
        return

    try:
        manifest = save_manifest(items, path=output, source_cache_timestamp=snapshot.last_run)
    except ManifestError as exc:
        console.print(f"[{STYLE_ERR}]✗ {exc}[/]")
        raise SystemExit(1)

    if as_json:
        click.echo(_json.dumps({
            "status": "ok",
            "path": str(Path(output).resolve()),
            "item_count": manifest.item_count,
        }))
        return

    console.print()
    console.print(Panel(
        f"[{STYLE_OK}]✓ Manifest saved![/]\n\n"
        f"  [bold white]Items   :[/bold white]  [bold green]{manifest.item_count}[/bold green]\n"
        f"  [bold white]Path    :[/bold white]  [dim]{Path(output).resolve()}[/dim]\n\n"
        f"  Replay with:\n"
        f"  [bold]landpyre download --manifest {output}[/bold]",
        title="[bold green]Manifest created[/bold green]",
        border_style="green", padding=(1, 2),
    ))
