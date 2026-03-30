"""Main CLI entry point for kctl-glitchtip."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_common import KctlError, handle_cli_error

from kctl_glitchtip import __version__
from kctl_glitchtip.commands.alerts import app as alerts_app
from kctl_glitchtip.commands.config_cmd import app as config_app
from kctl_glitchtip.commands.events import app as events_app
from kctl_glitchtip.commands.health import app as health_app
from kctl_glitchtip.commands.issues import app as issues_app
from kctl_glitchtip.commands.orgs import app as orgs_app
from kctl_glitchtip.commands.projects import app as projects_app
from kctl_glitchtip.commands.teams import app as teams_app
from kctl_glitchtip.commands.uptime import app as uptime_app
from kctl_glitchtip.commands.users import app as users_app
from kctl_glitchtip.core.callbacks import AppContext
from kctl_glitchtip.core.plugins import discover_and_load_plugins


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-glitchtip {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-glitchtip",
    help="Kodemeio GlitchTip CLI - manage your GlitchTip error tracking platform.",
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
    url: Annotated[str | None, typer.Option("--url", help="API URL override")] = None,
    token: Annotated[str | None, typer.Option("--token", help="API token override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio GlitchTip CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        format=format,
        no_header=no_header,
        url_override=url,
        token_override=token,
    )


# Register all command groups
app.add_typer(projects_app, name="projects")
app.add_typer(issues_app, name="issues")
app.add_typer(teams_app, name="teams")
app.add_typer(orgs_app, name="orgs")
app.add_typer(events_app, name="events")
app.add_typer(users_app, name="users")
app.add_typer(health_app, name="health")
app.add_typer(alerts_app, name="alerts")
app.add_typer(config_app, name="config")
app.add_typer(uptime_app, name="uptime")

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
