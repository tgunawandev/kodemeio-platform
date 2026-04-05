"""Main CLI entry point for kctl-claw."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_claw import __version__
from kctl_claw.commands.agents import app as agents_app
from kctl_claw.commands.agents_test import app as agents_test_app
from kctl_claw.commands.ai import app as ai_app
from kctl_claw.commands.aliases import register_aliases
from kctl_claw.commands.backup import app as backup_app
from kctl_claw.commands.config_cmd import app as config_app
from kctl_claw.commands.config_drift import app as config_drift_app
from kctl_claw.commands.cron import app as cron_app
from kctl_claw.commands.cron_debug import app as cron_debug_app
from kctl_claw.commands.deploy import app as deploy_app
from kctl_claw.commands.docker_cmd import app as docker_app
from kctl_claw.commands.doctor_cmd import app as doctor_app
from kctl_claw.commands.env import app as env_app
from kctl_claw.commands.health import app as health_app
from kctl_claw.commands.lint_cmd import app as lint_app
from kctl_claw.commands.logs import app as logs_app
from kctl_claw.commands.mcp import app as mcp_app
from kctl_claw.commands.mcp_test import app as mcp_test_app
from kctl_claw.commands.memory import app as memory_app
from kctl_claw.commands.monitor_cmd import app as monitor_app
from kctl_claw.commands.pipeline import app as pipeline_app
from kctl_claw.commands.prompts import app as prompts_app
from kctl_claw.commands.security import app as security_app
from kctl_claw.commands.skill_cmd import app as skill_app
from kctl_claw.commands.skills import app as skills_app
from kctl_claw.commands.skills_test import app as skills_test_app
from kctl_claw.commands.status import app as status_app
from kctl_claw.commands.telegram import app as telegram_app
from kctl_claw.commands.test_cmd import app as test_app
from kctl_claw.commands.trading import app as trading_app
from kctl_claw.core.callbacks import AppContext


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-claw {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-claw",
    help="Kodemeio OpenClaw CLI — manage AI agent gateway instances.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


@app.callback()
def main(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress info messages")] = False,
    output_format: Annotated[
        str, typer.Option("--format", "-f", help="Output format (pretty/json/csv/yaml)")
    ] = "pretty",
    no_header: Annotated[bool, typer.Option("--no-header", help="Omit table headers")] = False,
    profile: Annotated[str | None, typer.Option("--profile", "-p", help="Config profile name")] = None,
    root: Annotated[str | None, typer.Option("--root", help="Project root override")] = None,
    live: Annotated[bool, typer.Option("--live", help="Push config changes and trigger reload")] = False,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio OpenClaw CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        format=output_format,
        no_header=no_header,
        profile=profile,
        root_override=root,
        live=live,
    )


# Existing command groups
app.add_typer(agents_app, name="agents")
app.add_typer(ai_app, name="ai")
app.add_typer(backup_app, name="backup")
app.add_typer(config_app, name="config")
app.add_typer(cron_app, name="cron")
app.add_typer(deploy_app, name="deploy")
app.add_typer(env_app, name="env")
app.add_typer(health_app, name="health")
app.add_typer(logs_app, name="logs")
app.add_typer(memory_app, name="memory")
app.add_typer(mcp_app, name="mcp")
app.add_typer(security_app, name="security")
app.add_typer(skills_app, name="skills")
app.add_typer(status_app, name="status")
app.add_typer(telegram_app, name="telegram")
app.add_typer(skill_app, name="skill", hidden=True)
app.add_typer(trading_app, name="trading")

# New command groups (SP6)
app.add_typer(agents_test_app, name="agents-test")
app.add_typer(config_drift_app, name="config-drift")
app.add_typer(cron_debug_app, name="cron-debug")
app.add_typer(docker_app, name="docker")
app.add_typer(doctor_app, name="doctor")
app.add_typer(lint_app, name="lint")
app.add_typer(mcp_test_app, name="mcp-test")
app.add_typer(monitor_app, name="monitor")
app.add_typer(pipeline_app, name="pipeline")
app.add_typer(prompts_app, name="prompts")
app.add_typer(skills_test_app, name="skills-test")
app.add_typer(test_app, name="test")

register_aliases(app)


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
