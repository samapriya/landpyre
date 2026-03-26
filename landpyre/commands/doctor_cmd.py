"""
commands/doctor_cmd.py — Environment and setup diagnostics.
"""

from __future__ import annotations

import json as _json
import shutil
import socket
import ssl
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from landpyre import cache
from landpyre.config import config_path, load_config
from landpyre.ui.banner import STYLE_ERR, STYLE_HEADER, STYLE_OK, STYLE_WARN

console = Console()

_CHECK_URL = "https://www.landfire.gov"
_MIN_FREE_GB = 2.0
_MIN_PYTHON = (3, 10)


def _check_python() -> tuple[bool, str]:
    v = sys.version_info
    ok = (v.major, v.minor) >= _MIN_PYTHON
    return ok, f"{v.major}.{v.minor}.{v.micro}"


def _check_disk() -> tuple[bool, str]:
    try:
        usage = shutil.disk_usage(Path.home())
        free_gb = usage.free / 1024**3
        ok = free_gb >= _MIN_FREE_GB
        return ok, f"{free_gb:.1f} GB free"
    except Exception as exc:  # noqa: BLE001
        return False, f"Cannot check: {exc}"


def _check_network() -> tuple[bool, str]:
    try:
        socket.setdefaulttimeout(5)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("www.landfire.gov", 443))
        return True, "landfire.gov reachable"
    except Exception:  # noqa: BLE001
        return False, "Cannot reach landfire.gov"


def _check_ssl() -> tuple[bool, str]:
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(
            socket.socket(), server_hostname="www.landfire.gov"
        ) as s:
            s.settimeout(5)
            s.connect(("www.landfire.gov", 443))
        return True, "SSL/TLS OK"
    except Exception as exc:  # noqa: BLE001
        return False, f"SSL error: {exc}"


def _check_cache() -> tuple[bool, str]:
    if not cache.cache_exists():
        return False, "No cache — run `landpyre refresh`"
    try:
        snap = cache.load_cache()
        return True, f"{snap.item_count} items, last run {snap.last_run}"
    except Exception as exc:  # noqa: BLE001
        return False, f"Cache unreadable: {exc}"


def _check_cache_writable() -> tuple[bool, str]:
    try:
        p = cache.cache_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        test = p.parent / ".write_test"
        test.write_text("x")
        test.unlink()
        return True, str(p.parent)
    except Exception as exc:  # noqa: BLE001
        return False, f"Not writable: {exc}"


def _check_config() -> tuple[bool, str]:
    p = config_path()
    if not p.exists():
        return True, "No config file (defaults active)"
    try:
        load_config()
        return True, str(p)
    except Exception as exc:  # noqa: BLE001
        return False, f"Config parse error: {exc}"


def _check_zipfile() -> tuple[bool, str]:
    import zipfile
    return True, f"zipfile {zipfile.__name__} available"


def _check_pydantic() -> tuple[bool, str]:
    try:
        import pydantic
        return True, f"pydantic {pydantic.__version__}"
    except ImportError:
        return False, "pydantic not installed"


CHECKS = [
    ("Python version",       _check_python),
    ("Disk space",           _check_disk),
    ("Network (landfire.gov)", _check_network),
    ("SSL/TLS",              _check_ssl),
    ("Cache exists",         _check_cache),
    ("Cache dir writable",   _check_cache_writable),
    ("Config file",          _check_config),
    ("ZIP extraction",       _check_zipfile),
    ("Pydantic",             _check_pydantic),
]


@click.command("doctor")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def doctor_cmd(as_json: bool) -> None:
    """
    Run environment and setup diagnostics.

    Checks Python version, disk space, network reachability, SSL, cache
    health, config, and dependencies. Useful for troubleshooting or
    verifying a new installation.

    \b
    Examples:
      landpyre doctor
      landpyre doctor --json
    """
    results = []
    for name, fn in CHECKS:
        ok, detail = fn()
        results.append({"name": name, "ok": ok, "detail": detail})

    if as_json:
        click.echo(_json.dumps(results, indent=2))
        return

    table = Table(
        show_header=True, header_style=STYLE_HEADER,
        border_style="bright_black", expand=True,
    )
    table.add_column("Check", style="bold white", max_width=30)
    table.add_column("Status", width=8, justify="center")
    table.add_column("Detail", style="dim")

    for r in results:
        icon = f"[{STYLE_OK}]✓[/]" if r["ok"] else f"[{STYLE_ERR}]✗[/]"
        table.add_row(r["name"], icon, r["detail"])

    all_ok = all(r["ok"] for r in results)
    failed = [r for r in results if not r["ok"]]

    console.print()
    console.print(table)
    console.print()

    if all_ok:
        console.print(Panel(
            f"[{STYLE_OK}]✓ All checks passed. landpyre is ready.[/]",
            border_style="green",
        ))
    else:
        issues = "\n".join(f"  [red]•[/red] {r['name']}: [dim]{r['detail']}[/dim]" for r in failed)
        console.print(Panel(
            f"[{STYLE_WARN}]{len(failed)} check(s) failed:[/]\n\n{issues}",
            title="[bold yellow]Issues found[/bold yellow]",
            border_style="yellow",
        ))
