"""
commands/config_cmd.py — View and modify persistent user configuration.
"""

from __future__ import annotations

import json as _json

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from landpyre.config import CONFIG_KEYS, config_path, get_value, load_config, set_value
from landpyre.errors import ConfigError
from landpyre.ui.banner import STYLE_ERR, STYLE_HEADER, STYLE_OK

console = Console()


@click.group("config")
def config_cmd() -> None:
    """
    View and modify persistent landpyre configuration.

    \b
    Examples:
      landpyre config show
      landpyre config get default_region
      landpyre config set default_region CONUS
      landpyre config set default_workers 6
    """


@config_cmd.command("show")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def config_show(as_json: bool) -> None:
    """Show all current configuration values."""
    cfg = load_config()
    data = cfg.model_dump()

    if as_json:
        click.echo(_json.dumps(data, indent=2))
        return

    table = Table(show_header=True, header_style=STYLE_HEADER,
                  border_style="bright_black", expand=True)
    table.add_column("Key", style="bold white", max_width=30)
    table.add_column("Value", style="cyan")
    table.add_column("Description", style="dim", max_width=50)

    for key, desc in CONFIG_KEYS.items():
        val = data.get(key)
        table.add_row(key, str(val) if val is not None else "[dim]—[/dim]", desc)

    console.print()
    console.print(Panel(
        f"  Config file: [dim]{config_path()}[/dim]",
        title="[bold cyan]landpyre configuration[/bold cyan]",
        border_style="cyan",
    ))
    console.print()
    console.print(table)


@config_cmd.command("get")
@click.argument("key")
@click.option("--json", "as_json", is_flag=True, default=False)
def config_get(key: str, as_json: bool) -> None:
    """Get a single config value by KEY."""
    try:
        val = get_value(key)
    except ConfigError as exc:
        console.print(f"[{STYLE_ERR}]✗ {exc}[/]")
        raise SystemExit(1)

    if as_json:
        click.echo(_json.dumps({key: val}))
    else:
        console.print(f"  [bold white]{key}:[/bold white]  [cyan]{val}[/cyan]")


@config_cmd.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str) -> None:
    """Set a config value.  KEY VALUE are positional arguments."""
    try:
        set_value(key, value)
    except ConfigError as exc:
        console.print(f"[{STYLE_ERR}]✗ {exc}[/]")
        raise SystemExit(1)

    console.print(f"  [{STYLE_OK}]✓ {key} = {value}[/]")
    console.print(f"  [dim]Saved to {config_path()}[/dim]")
