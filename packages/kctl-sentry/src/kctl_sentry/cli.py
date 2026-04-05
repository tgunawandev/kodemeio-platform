"""Main CLI entry point for kctl-sentry."""

from __future__ import annotations


from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_sentry import __version__
from kctl_sentry.commands.alerts import app as alerts_app
from kctl_sentry.commands.config_cmd import app as config_app
from kctl_sentry.commands.dashboard import app as dashboard_app
from kctl_sentry.commands.environments import app as environments_app
from kctl_sentry.commands.health import app as health_app
from kctl_sentry.commands.issues import app as issues_app
from kctl_sentry.commands.projects import app as projects_app
from kctl_sentry.commands.releases import app as releases_app
from kctl_sentry.commands.stats import app as stats_app
from kctl_sentry.commands.teams import app as teams_app
from kctl_sentry.core.callbacks import AppContext
from kctl_sentry.core.plugins import discover_and_load_plugins
from kctl_sentry.commands.skill_cmd import app as skill_app


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-sentry {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-sentry",
    help="Kodemeio Sentry CLI — error triage, release tracking, and project management.",
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
    auth_token: Annotated[str | None, typer.Option("--auth-token", help="Auth token override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio Sentry CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        format=format,
        no_header=no_header,
        auth_token_override=auth_token,
    )


app.add_typer(config_app, name="config")
app.add_typer(health_app, name="health")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(issues_app, name="issues")
app.add_typer(projects_app, name="projects")
app.add_typer(releases_app, name="releases")
app.add_typer(alerts_app, name="alerts")
app.add_typer(stats_app, name="stats")
app.add_typer(teams_app, name="teams")
app.add_typer(environments_app, name="environments")
app.add_typer(skill_app, name="skill", hidden=True)

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
