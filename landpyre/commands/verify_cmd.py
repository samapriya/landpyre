"""
commands/verify_cmd.py — Verify downloaded files against a manifest.
"""

from __future__ import annotations

import json as _json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from landpyre.errors import ManifestError
from landpyre.manifest import load_manifest
from landpyre.ui.banner import STYLE_ERR, STYLE_HEADER, STYLE_OK, STYLE_WARN
from landpyre.verifier import verify_manifest

console = Console()


@click.command("verify")
@click.option("--manifest", "-m", "manifest_path", default="manifest.json", show_default=True,
              help="Path to manifest.json.")
@click.option("--output", "-o", default=None,
              help="Output directory that was used for download (default: from config or 'landfire_output').")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def verify_cmd(manifest_path: str, output: str | None, as_json: bool) -> None:
    """
    Verify downloaded files against a saved manifest.

    Checks existence, file size, and MD5 checksum (where available).
    Reports missing and corrupt files so you know what needs re-downloading.

    \b
    Examples:
      landpyre verify
      landpyre verify --manifest hawaii.json --output ./hawaii_2022
      landpyre verify --json
    """
    from landpyre.config import load_config
    cfg = load_config()
    output_dir = Path(output or cfg.default_output)

    try:
        manifest = load_manifest(manifest_path)
    except ManifestError as exc:
        console.print(f"[{STYLE_ERR}]✗ {exc}[/]")
        raise SystemExit(1)

    result = verify_manifest(manifest, output_dir)

    if as_json:
        click.echo(_json.dumps(result.model_dump(mode="json"), indent=2))
        return

    # ── Result table ────────────────────────────────────────────────────────
    table = Table(show_header=True, header_style=STYLE_HEADER,
                  border_style="bright_black", expand=True)
    table.add_column("File", max_width=40)
    table.add_column("Exists", width=8, justify="center")
    table.add_column("Checksum", width=12, justify="center")
    table.add_column("Size", width=10, justify="center")

    def _tick(val: bool | None) -> str:
        if val is None:
            return "[dim]—[/dim]"
        return "[bold green]✓[/bold green]" if val else "[bold red]✗[/bold red]"

    for d in result.details:
        table.add_row(
            d.filename,
            _tick(d.exists),
            _tick(d.checksum_ok),
            _tick(d.size_ok),
        )

    status_color = "green" if result.all_ok else "yellow" if result.files_missing == 0 else "red"
    status_icon = "✓" if result.all_ok else "⚠"
    status_label = "All files verified" if result.all_ok else "Issues found"

    console.print()
    console.print(table)
    console.print()
    console.print(Panel(
        f"  [bold white]Files OK       :[/bold white]  [bold green]{result.files_ok}[/bold green]\n"
        f"  [bold white]Files missing  :[/bold white]  "
        f"[{'bold red' if result.files_missing else 'dim'}]{result.files_missing}[/]\n"
        f"  [bold white]Files corrupt  :[/bold white]  "
        f"[{'bold red' if result.files_corrupt else 'dim'}]{result.files_corrupt}[/]"
        + (
            "\n\n  Re-download missing/corrupt files with:\n"
            "  [bold]landpyre download --manifest " + manifest_path + "[/bold]"
            if not result.all_ok else ""
        ),
        title=f"[bold {status_color}]{status_icon} {status_label}[/bold {status_color}]",
        border_style=status_color, padding=(1, 2),
    ))
