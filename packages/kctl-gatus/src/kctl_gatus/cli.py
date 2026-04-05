"""Main CLI entry point for kctl-gatus."""

from __future__ import annotations

from pathlib import Path

from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_gatus import __version__
from kctl_gatus.commands.alerts import app as alerts_app
from kctl_gatus.commands.config_cmd import app as config_app
from kctl_gatus.commands.dashboard import app as dashboard_app
from kctl_gatus.commands.discovery import app as discovery_app
from kctl_gatus.commands.endpoints import app as endpoints_app
from kctl_gatus.commands.health import app as health_app
from kctl_gatus.commands.results import app as results_app
from kctl_gatus.core.callbacks import AppContext


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-gatus {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-gatus",
    help="Kodemeio Gatus CLI - manage your Gatus health monitoring platform.",
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
    url: Annotated[str | None, typer.Option("--url", help="API URL override")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="API key override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio Gatus CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        url_override=url,
        api_key_override=api_key,
    )


# Register all command groups
app.add_typer(endpoints_app, name="endpoints")
app.add_typer(results_app, name="results")
app.add_typer(alerts_app, name="alerts")
app.add_typer(discovery_app, name="discovery")
app.add_typer(health_app, name="health")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(config_app, name="config")


# ---------------------------------------------------------------------------
# Skill generation
# ---------------------------------------------------------------------------
skill_app = typer.Typer(help="Skill management", hidden=True)


@skill_app.command()
def generate(
    output_dir: Annotated[
        str,
        typer.Option("--output", "-o", help="Output directory"),
    ] = str(Path.home() / ".claude" / "skills" / "gatus-admin"),
) -> None:
    """Regenerate SKILL.md from current CLI commands."""
    from kctl_lib.skill_generator import generate_skill

    out_path = Path(output_dir)
    extra = Path(__file__).parent / "SKILL.extra.md"
    content = generate_skill(
        app,
        "kctl-gatus",
        "gatus-admin",
        "Gatus health monitoring administration via kctl-gatus CLI",
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
