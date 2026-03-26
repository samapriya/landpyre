"""
landpyre CLI — entry point for all commands.
"""

from __future__ import annotations

import click
from rich.console import Console

from landpyre import __version__
from landpyre.commands.config_cmd import config_cmd
from landpyre.commands.doctor_cmd import doctor_cmd
from landpyre.commands.download import download_cmd
from landpyre.commands.list_cmd import list_cmd
from landpyre.commands.manifest_cmd import manifest_cmd
from landpyre.commands.readme_cmd import readme_cmd
from landpyre.commands.refresh import refresh
from landpyre.commands.search_cmd import search_cmd
from landpyre.commands.stats import stats
from landpyre.commands.verify_cmd import verify_cmd
from landpyre.ui import print_banner

console = Console()

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"], max_content_width=100)


class BannerGroup(click.Group):
    """Prints the ASCII banner before every invocation."""

    _banner_printed = False

    _COMMAND_ORDER = [
        "readme", "refresh", "search", "list", "stats",
        "manifest", "download", "verify", "config", "doctor",
    ]

    def list_commands(self, ctx: click.Context) -> list[str]:
        ordered = [c for c in self._COMMAND_ORDER if c in self.commands]
        extras = sorted(c for c in self.commands if c not in self._COMMAND_ORDER)
        return ordered + extras

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if not BannerGroup._banner_printed:
            print_banner(console)
            BannerGroup._banner_printed = True
        return super().parse_args(ctx, args)


@click.group(cls=BannerGroup, context_settings=CONTEXT_SETTINGS)
@click.version_option(__version__, "-v", "--version", prog_name="landpyre")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """
    \b
    landpyre — LANDFIRE data discovery and download SDK + CLI.

    Fetch, search, and download LANDFIRE geospatial datasets with filtering
    by region, version, and theme. Use manifests for reproducible workflows.

    \b
    Quick start:
      landpyre readme                     # Opens the Docs site
      landpyre refresh                    # Fetch and cache the full catalogue
      landpyre search "hawaii fuel 2022"  # Fuzzy search
      landpyre list                       # Browse available downloads
      landpyre stats                      # Summarise the catalogue
      landpyre download  --version "LF 2025" --output lf2025
    """
    ctx.ensure_object(dict)


cli.add_command(readme_cmd,   name="readme")
cli.add_command(refresh)
cli.add_command(list_cmd,     name="list")
cli.add_command(stats)
cli.add_command(download_cmd, name="download")
cli.add_command(search_cmd,   name="search")
cli.add_command(manifest_cmd, name="manifest")
cli.add_command(verify_cmd,   name="verify")
cli.add_command(config_cmd,   name="config")
cli.add_command(doctor_cmd,   name="doctor")


if __name__ == "__main__":
    cli()
