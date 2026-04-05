"""Main CLI entry point for kctl-grafana."""

from __future__ import annotations


from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_grafana import __version__
from kctl_grafana.commands.alert import app as alert_app
from kctl_grafana.commands.annotation import app as annotation_app
from kctl_grafana.commands.backup import app as backup_app
from kctl_grafana.commands.config_cmd import app as config_app
from kctl_grafana.commands.dashboard import app as dashboard_app
from kctl_grafana.commands.datasource import app as datasource_app
from kctl_grafana.commands.folder import app as folder_app
from kctl_grafana.commands.health import app as health_app
from kctl_grafana.commands.selftest import app as selftest_app
from kctl_grafana.commands.status import app as status_app
from kctl_grafana.commands.user import app as user_app
from kctl_grafana.core.callbacks import AppContext
from kctl_grafana.commands.skill_cmd import app as skill_app


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-grafana {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-grafana",
    help="Kodemeio Grafana CLI - manage your Grafana monitoring platform.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


@app.callback()
def main(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON (shortcut for --format json)")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress info messages")] = False,
    output_format: Annotated[
        str, typer.Option("--format", "-f", help="Output format: pretty, json, csv, yaml")
    ] = "pretty",
    no_header: Annotated[bool, typer.Option("--no-header", help="Omit headers in CSV output")] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Enable debug logging")] = False,
    profile: Annotated[str | None, typer.Option("--profile", "-p", help="Config profile name")] = None,
    url: Annotated[str | None, typer.Option("--url", help="API URL override")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="API key override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio Grafana CLI."""
    import os

    if debug:
        os.environ["KCTL_DEBUG"] = "1"

    effective_format = "json" if json_output else output_format

    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output or effective_format == "json",
        quiet=quiet,
        format=effective_format,
        no_header=no_header,
        debug=debug,
        profile=profile,
        url_override=url,
        api_key_override=api_key,
    )


# Command groups
app.add_typer(config_app, name="config")
app.add_typer(health_app, name="health")
app.add_typer(status_app, name="status")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(datasource_app, name="datasource")
app.add_typer(alert_app, name="alert")
app.add_typer(folder_app, name="folder")
app.add_typer(annotation_app, name="annotation")
app.add_typer(user_app, name="user")
app.add_typer(backup_app, name="backup")
app.add_typer(selftest_app, name="selftest")
app.add_typer(skill_app, name="skill", hidden=True)


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
