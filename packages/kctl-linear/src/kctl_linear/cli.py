"""Main CLI entry point for kctl-linear."""

from __future__ import annotations


from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_linear import __version__
from kctl_linear.commands.config_cmd import app as config_app
from kctl_linear.commands.cycles import app as cycles_app
from kctl_linear.commands.dashboard import app as dashboard_app
from kctl_linear.commands.health import app as health_app
from kctl_linear.commands.issues import app as issues_app
from kctl_linear.commands.labels import app as labels_app
from kctl_linear.commands.projects import app as projects_app
from kctl_linear.commands.teams import app as teams_app
from kctl_linear.commands.users import app as users_app
from kctl_linear.core.callbacks import AppContext
from kctl_linear.core.plugins import discover_and_load_plugins
from kctl_linear.commands.skill_cmd import app as skill_app
from kctl_linear.commands.doctor_cmd import app as doctor_app


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-linear {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-linear",
    help="Linear project management",
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
    """Linear project management."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        format=format,
        no_header=no_header,
    )


# Command group registration
app.add_typer(config_app, name="config")
app.add_typer(health_app, name="health")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(issues_app, name="issues")
app.add_typer(cycles_app, name="cycles")
app.add_typer(projects_app, name="projects")
app.add_typer(teams_app, name="teams")
app.add_typer(labels_app, name="labels")
app.add_typer(users_app, name="users")
app.add_typer(skill_app, name="skill", hidden=True)
app.add_typer(doctor_app, name="doctor")

# Load third-party plugins via entry points
discover_and_load_plugins(app)


@app.command("self-update")
def self_update_cmd(ctx: typer.Context) -> None:
    """Check for updates and upgrade kctl-linear."""
    actx = ctx.obj
    out = actx.output

    from kctl_lib.self_update import check_update
    from kctl_lib.self_update import update as do_update

    latest = check_update("kctl-linear", __version__)
    if latest:
        out.info(f"Updating to {latest}...")
        do_update("kctl-linear")
        out.success(f"Updated to {latest}")
    else:
        out.success("Already up to date")


@app.command()
def completions(
    shell: Annotated[str, typer.Argument(help="Shell type: zsh, bash, fish")] = "zsh",
    install: Annotated[bool, typer.Option("--install", help="Install completions")] = False,
) -> None:
    """Generate or install shell completions."""
    from kctl_lib.completions import get_completion_script, install_completions

    if install:
        path = install_completions("kctl-linear", shell)
        if path:
            typer.echo(f"Completions installed to {path}")
        else:
            typer.echo(f"Could not install completions for {shell}", err=True)
            raise typer.Exit(code=1)
    else:
        script = get_completion_script("kctl-linear", shell)
        typer.echo(script)


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
