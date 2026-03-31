"""Main CLI entry point for kctl-telegram."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_telegram import __version__
from kctl_telegram.commands.bots import app as bots_app
from kctl_telegram.commands.chatwoot import app as chatwoot_app
from kctl_telegram.commands.config_cmd import app as config_app
from kctl_telegram.commands.dashboard import app as dashboard_app
from kctl_telegram.commands.groups import app as groups_app
from kctl_telegram.commands.health import app as health_app
from kctl_telegram.commands.messages import app as messages_app
from kctl_telegram.core.callbacks import AppContext
from kctl_telegram.core.exceptions import KctlError


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-telegram {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-telegram",
    help="Kodemeio Telegram CLI - manage your Telegram bot gateway.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


@app.callback()
def main(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress info messages")] = False,
    format_: Annotated[str, typer.Option("--format", "-f", help="Output format: pretty/json/csv/yaml")] = "pretty",
    no_header: Annotated[bool, typer.Option("--no-header", help="Suppress table headers (csv)")] = False,
    profile: Annotated[str | None, typer.Option("--profile", "-p", help="Config profile name")] = None,
    url: Annotated[str | None, typer.Option("--url", help="API URL override")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="API key override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio Telegram CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        format=format_,
        no_header=no_header,
        profile=profile,
        url_override=url,
        api_key_override=api_key,
    )


# Register all command groups
app.add_typer(config_app, name="config")
app.add_typer(health_app, name="health")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(bots_app, name="bots")
app.add_typer(groups_app, name="groups")
app.add_typer(messages_app, name="messages")
app.add_typer(chatwoot_app, name="chatwoot")


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        from kctl_lib import handle_cli_error

        handle_cli_error(e)


if __name__ == "__main__":
    _run()
