"""Main CLI entry point for kctl-api."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_api import __version__
from kctl_api.core.callbacks import AppContext


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-api {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-api",
    help="Kodemeio API CLI - manage your FastAPI platform.",
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
        str, typer.Option("--format", "-f", help="Output format: pretty, json, csv, yaml")
    ] = "pretty",
    no_header: Annotated[bool, typer.Option("--no-header", help="Omit table headers (for scripting)")] = False,
    profile: Annotated[str | None, typer.Option("--profile", "-p", help="Config profile name")] = None,
    url: Annotated[str | None, typer.Option("--url", help="API URL override")] = None,
    ai_url: Annotated[str | None, typer.Option("--ai-url", help="AI API URL override")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="API key override")] = None,
    database_url: Annotated[str | None, typer.Option("--database-url", help="Database URL override")] = None,
    redis_url: Annotated[str | None, typer.Option("--redis-url", help="Redis URL override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio API CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output or output_format == "json",
        quiet=quiet,
        format=output_format,
        no_header=no_header,
        profile=profile,
        url_override=url,
        ai_url_override=ai_url,
        api_key_override=api_key,
        database_url_override=database_url,
        redis_url_override=redis_url,
    )


def _register_commands() -> None:
    """Register all command groups (lazy imports for fast startup)."""
    from kctl_api.commands.ai import app as ai_app
    from kctl_api.commands.aliases import register_aliases
    from kctl_api.commands.apps import app as apps_app
    from kctl_api.commands.auth import app as auth_app
    from kctl_api.commands.automation import app as automation_app
    from kctl_api.commands.build_cmd import app as build_app
    from kctl_api.commands.clean import app as clean_app
    from kctl_api.commands.config_cmd import app as config_app
    from kctl_api.commands.dashboard import app as dashboard_app
    from kctl_api.commands.db import app as db_app
    from kctl_api.commands.deploy import app as deploy_app
    from kctl_api.commands.deps import app as deps_app
    from kctl_api.commands.dev import app as dev_app
    from kctl_api.commands.docker_cmd import app as docker_app
    from kctl_api.commands.doctor_cmd import app as doctor_app
    from kctl_api.commands.env import app as env_app
    from kctl_api.commands.files import app as files_app
    from kctl_api.commands.fmt_cmd import app as fmt_app
    from kctl_api.commands.health import app as health_app
    from kctl_api.commands.jobs import app as jobs_app
    from kctl_api.commands.lint_cmd import app as lint_app
    from kctl_api.commands.logs import app as logs_app
    from kctl_api.commands.marketplace import app as marketplace_app
    from kctl_api.commands.monitor_cmd import app as monitor_app
    from kctl_api.commands.notifications import app as notifications_app
    from kctl_api.commands.odoo_proxy import app as odoo_app
    from kctl_api.commands.openapi import app as openapi_app
    from kctl_api.commands.perf import app as perf_app
    from kctl_api.commands.rate_limit import app as rate_limit_app
    from kctl_api.commands.realtime import app as realtime_app
    from kctl_api.commands.redis_cmd import app as redis_app
    from kctl_api.commands.routes_cmd import app as routes_app
    from kctl_api.commands.saas import app as saas_app
    from kctl_api.commands.scaffold import app as scaffold_app
    from kctl_api.commands.security_cmd import app as security_app
    from kctl_api.commands.services import app as services_app
    from kctl_api.commands.shell import app as shell_app
    from kctl_api.commands.streams import app as streams_app
    from kctl_api.commands.stripe_cmd import app as stripe_app
    from kctl_api.commands.tenant_ai import app as tenant_ai_app
    from kctl_api.commands.test_cmd import app as test_app
    from kctl_api.commands.users import app as users_app
    from kctl_api.commands.webhooks import app as webhooks_app
    from kctl_api.commands.workflows import app as workflows_app
    from kctl_api.commands.ws import app as ws_app

    # Authentication & access
    app.add_typer(config_app, name="config")
    app.add_typer(auth_app, name="auth")
    app.add_typer(health_app, name="health")

    # API resources
    app.add_typer(users_app, name="users")
    app.add_typer(files_app, name="files")
    app.add_typer(jobs_app, name="jobs")
    app.add_typer(workflows_app, name="workflows")
    app.add_typer(automation_app, name="automation")
    app.add_typer(notifications_app, name="notifications")
    app.add_typer(webhooks_app, name="webhooks")
    app.add_typer(marketplace_app, name="marketplace")
    app.add_typer(saas_app, name="saas")
    app.add_typer(stripe_app, name="stripe")
    app.add_typer(odoo_app, name="odoo")
    app.add_typer(realtime_app, name="realtime")

    # AI platform
    app.add_typer(ai_app, name="ai")
    app.add_typer(tenant_ai_app, name="tenant-ai")

    # Infrastructure
    app.add_typer(db_app, name="db")
    app.add_typer(redis_app, name="redis")
    app.add_typer(streams_app, name="streams")
    app.add_typer(services_app, name="services")
    app.add_typer(deploy_app, name="deploy")
    app.add_typer(apps_app, name="apps")
    app.add_typer(docker_app, name="docker")

    # Development tools
    app.add_typer(dev_app, name="dev")
    app.add_typer(test_app, name="test")
    app.add_typer(lint_app, name="lint")
    app.add_typer(fmt_app, name="fmt")
    app.add_typer(build_app, name="build")
    app.add_typer(scaffold_app, name="scaffold")
    app.add_typer(shell_app, name="shell")

    # API analysis & testing
    app.add_typer(openapi_app, name="openapi")
    app.add_typer(routes_app, name="routes")
    app.add_typer(rate_limit_app, name="rate-limit")
    app.add_typer(ws_app, name="ws")
    app.add_typer(perf_app, name="perf")

    # Environment & security
    app.add_typer(doctor_app, name="doctor")
    app.add_typer(env_app, name="env")
    app.add_typer(security_app, name="security")
    app.add_typer(deps_app, name="deps")
    app.add_typer(clean_app, name="clean")

    # Observability & monitoring
    app.add_typer(logs_app, name="logs")
    app.add_typer(dashboard_app, name="dashboard")
    app.add_typer(monitor_app, name="monitor")

    # Skill generation
    from kctl_api.commands.skill_cmd import app as skill_app

    app.add_typer(skill_app, name="skill")

    # Short aliases
    register_aliases(app)


_register_commands()

# Load plugins via entry points
from kctl_api.core.plugins import discover_and_load_plugins  # noqa: E402

discover_and_load_plugins(app)


@app.command("self-update")
def self_update_cmd(ctx: typer.Context) -> None:
    """Check for updates and upgrade kctl-api."""
    actx = ctx.obj
    out = actx.output

    from kctl_lib.self_update import check_update
    from kctl_lib.self_update import update as do_update

    latest = check_update("kctl-api", __version__)
    if latest:
        out.info(f"Updating to {latest}...")
        do_update("kctl-api")
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
        path = install_completions("kctl-api", shell)
        if path:
            typer.echo(f"Completions installed to {path}")
        else:
            typer.echo(f"Could not install completions for {shell}", err=True)
            raise typer.Exit(code=1)
    else:
        script = get_completion_script("kctl-api", shell)
        typer.echo(script)


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
