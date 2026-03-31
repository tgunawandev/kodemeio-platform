"""Main CLI entry point for kctl-notion."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_notion import __version__
from kctl_notion.commands.blocks import app as blocks_app
from kctl_notion.commands.config_cmd import app as config_app
from kctl_notion.commands.databases import app as databases_app
from kctl_notion.commands.health import app as health_app
from kctl_notion.commands.pages import app as pages_app
from kctl_notion.commands.search import search as search_cmd
from kctl_notion.commands.users import app as users_app
from kctl_notion.core.callbacks import AppContext
from kctl_notion.core.plugins import discover_and_load_plugins


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-notion {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-notion",
    help="Notion workspace management",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


@app.callback()
def main(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress info messages")] = False,
    profile: Annotated[str | None, typer.Option("--profile", "-p", help="Config profile name")] = None,
    format: Annotated[str, typer.Option("--format", "-f", help="Output format: pretty, json, csv, yaml")] = "pretty",
    no_header: Annotated[bool, typer.Option("--no-header", help="Omit header row in CSV output")] = False,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Notion workspace management."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        format=format,
        no_header=no_header,
    )


# Register command groups
app.add_typer(config_app, name="config")
app.add_typer(health_app, name="health")
app.command(name="search")(search_cmd)
app.add_typer(pages_app, name="pages")
app.add_typer(databases_app, name="databases")
app.add_typer(blocks_app, name="blocks")
app.add_typer(users_app, name="users")

# Load third-party plugins via entry points
discover_and_load_plugins(app)


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
