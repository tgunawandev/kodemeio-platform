"""Main CLI entry point for kctl-dbgate."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import handle_cli_error  # noqa: F401

from kctl_dbgate import __version__
from kctl_dbgate.commands.config_cmd import app as config_app
from kctl_dbgate.commands.connections import app as connections_app
from kctl_dbgate.commands.doctor_cmd import app as doctor_app
from kctl_dbgate.commands.health import app as health_app
from kctl_dbgate.core.callbacks import AppContext
from kctl_dbgate.core.plugins import discover_and_load_plugins


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-dbgate {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-dbgate",
    help="Kodemeio DBGate CLI - manage your DBGate deployment.",
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
    url: Annotated[str | None, typer.Option("--url", help="DBGate URL override")] = None,
    login: Annotated[str | None, typer.Option("--login", help="UI login override")] = None,
    password: Annotated[str | None, typer.Option("--password", help="UI password override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio DBGate CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        format=format,
        no_header=no_header,
        url_override=url,
        login_override=login,
        password_override=password,
    )


# Register command groups
app.add_typer(config_app, name="config")
app.add_typer(health_app, name="health")
app.add_typer(connections_app, name="connections")
app.add_typer(doctor_app, name="doctor")

# Load any third-party plugins
discover_and_load_plugins(app)


def _run() -> None:
    app()


if __name__ == "__main__":
    _run()
