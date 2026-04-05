"""Main CLI entry point for kctl-github."""

from __future__ import annotations


from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_github import __version__
from kctl_github.commands.billing import app as billing_app
from kctl_github.commands.ci import app as ci_app
from kctl_github.commands.config_cmd import app as config_app
from kctl_github.commands.dashboard import app as dashboard_app
from kctl_github.commands.health import app as health_app
from kctl_github.commands.labels import app as labels_app
from kctl_github.commands.prs import app as prs_app
from kctl_github.commands.repos import app as repos_app
from kctl_github.commands.secrets import app as secrets_app
from kctl_github.commands.stats import app as stats_app
from kctl_github.core.callbacks import AppContext
from kctl_github.core.plugins import discover_and_load_plugins
from kctl_github.commands.doctor_cmd import app as doctor_app
from kctl_github.commands.skill_cmd import app as skill_app


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-github {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-github",
    help="GitHub cross-repo management for kodemeio-* repositories",
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
    """GitHub cross-repo management for kodemeio-* repositories."""
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
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(repos_app, name="repos")
app.add_typer(ci_app, name="ci")
app.add_typer(prs_app, name="prs")
app.add_typer(secrets_app, name="secrets")
app.add_typer(labels_app, name="labels")
app.add_typer(stats_app, name="stats")
app.add_typer(billing_app, name="billing")
app.add_typer(doctor_app, name="doctor")
app.add_typer(skill_app, name="skill", hidden=True)

# Load third-party plugins via entry points
discover_and_load_plugins(app)


@app.command("self-update")
def self_update_cmd(ctx: typer.Context) -> None:
    """Check for updates and upgrade kctl-github."""
    actx = ctx.obj
    out = actx.output

    from kctl_lib.self_update import check_update
    from kctl_lib.self_update import update as do_update

    latest = check_update("kctl-github", __version__)
    if latest:
        out.info(f"Updating to {latest}...")
        do_update("kctl-github")
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
        path = install_completions("kctl-github", shell)
        if path:
            typer.echo(f"Completions installed to {path}")
        else:
            typer.echo(f"Could not install completions for {shell}", err=True)
            raise typer.Exit(code=1)
    else:
        script = get_completion_script("kctl-github", shell)
        typer.echo(script)


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
