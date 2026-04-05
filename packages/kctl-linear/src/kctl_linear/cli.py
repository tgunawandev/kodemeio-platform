"""Main CLI entry point for kctl-linear."""

from __future__ import annotations

from pathlib import Path

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

# Load third-party plugins via entry points
discover_and_load_plugins(app)


# ---------------------------------------------------------------------------
# Skill generation
# ---------------------------------------------------------------------------
skill_app = typer.Typer(help="Skill management", hidden=True)


@skill_app.command()
def generate(
    output_dir: Annotated[
        str,
        typer.Option("--output", "-o", help="Output directory"),
    ] = str(Path.home() / ".claude" / "skills" / "linear-admin"),
) -> None:
    """Regenerate SKILL.md from current CLI commands."""
    from kctl_lib.skill_generator import generate_skill

    out_path = Path(output_dir)
    extra = Path(__file__).parent / "SKILL.extra.md"
    content = generate_skill(
        app,
        "kctl-linear",
        "linear-admin",
        "Linear project tracking administration via kctl-linear CLI",
        output_dir=out_path,
        extra_file=extra if extra.exists() else None,
    )
    print(f"Generated SKILL.md at {out_path / 'SKILL.md'}")
    print(f"Commands: {content.count('|') // 2} entries")


app.add_typer(skill_app, name="skill")


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
