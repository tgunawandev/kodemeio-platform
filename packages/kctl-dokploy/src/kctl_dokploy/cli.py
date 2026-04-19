"""Main CLI entry point for kctl-dokploy."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_dokploy import __version__
from kctl_dokploy.commands.aliases import register_aliases
from kctl_dokploy.commands.applications import app as applications_app
from kctl_dokploy.commands.audit import app as audit_app
from kctl_dokploy.commands.autodeploy import app as autodeploy_app
from kctl_dokploy.commands.backups import app as backups_app
from kctl_dokploy.commands.bulk import app as bulk_app
from kctl_dokploy.commands.certificates import app as certificates_app
from kctl_dokploy.commands.cluster import app as cluster_app
from kctl_dokploy.commands.compose import app as compose_app
from kctl_dokploy.commands.config_cmd import app as config_app
from kctl_dokploy.commands.dashboard import app as dashboard_app
from kctl_dokploy.commands.databases import app as databases_app
from kctl_dokploy.commands.deployments import app as deployments_app
from kctl_dokploy.commands.diagnose import app as diagnose_app
from kctl_dokploy.commands.docker import app as docker_app
from kctl_dokploy.commands.domains import app as domains_app
from kctl_dokploy.commands.env import app as env_app
from kctl_dokploy.commands.environments import app as environments_app
from kctl_dokploy.commands.git import app as git_app
from kctl_dokploy.commands.maintenance import app as maintenance_app
from kctl_dokploy.commands.monitoring import app as monitoring_app
from kctl_dokploy.commands.mounts import app as mounts_app
from kctl_dokploy.commands.notifications import app as notifications_app
from kctl_dokploy.commands.pipeline import app as pipeline_app
from kctl_dokploy.commands.ports import app as ports_app
from kctl_dokploy.commands.projects import app as projects_app
from kctl_dokploy.commands.redirects import app as redirects_app
from kctl_dokploy.commands.registry import app as registry_app
from kctl_dokploy.commands.report import app as report_app
from kctl_dokploy.commands.schedules import app as schedules_app
from kctl_dokploy.commands.security_cmd import app as security_app
from kctl_dokploy.commands.servers import app as servers_app
from kctl_dokploy.commands.settings import app as settings_app
from kctl_dokploy.commands.setup import app as setup_app
from kctl_dokploy.commands.status import app as status_app
from kctl_dokploy.commands.template import app as template_app
from kctl_dokploy.commands.users import app as users_app
from kctl_dokploy.commands.deploy import app as deploy_app
from kctl_dokploy.commands.patches import app as patches_app
from kctl_dokploy.commands.volume_backups import app as volume_backups_app
from kctl_dokploy.core.callbacks import AppContext
from kctl_dokploy.core.plugins import discover_and_register_plugins
from kctl_dokploy.commands.doctor_cmd import app as doctor_app
from kctl_dokploy.commands.skill_cmd import app as skill_app


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-dokploy {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-dokploy",
    help="Kodemeio Dokploy CLI - manage your Dokploy deployment platform.",
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
    """Kodemeio Dokploy CLI."""
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

    # Emit the profile banner once per invocation (no-op when profile is None,
    # quiet, or json mode — emit_banner handles those guards internally).
    if profile:
        from kctl_lib.config import get_service_config, resolve_inheritance_chain

        chain = resolve_inheritance_chain(profile)
        summary: str | None = None
        try:
            dokploy_cfg = get_service_config(profile, "dokploy")
            summary = dokploy_cfg.get("url") if dokploy_cfg else None
        except Exception:
            summary = None
        ctx.obj.emit_banner(
            app="kctl-dokploy",
            inheritance_chain=chain,
            service_summary=summary,
        )


# ---------------------------------------------------------------------------
# Top-level command groups (platform-wide resources)
# ---------------------------------------------------------------------------
app.add_typer(config_app, name="config")
app.add_typer(projects_app, name="projects")
app.add_typer(applications_app, name="applications")
app.add_typer(compose_app, name="compose")
app.add_typer(servers_app, name="servers")
app.add_typer(databases_app, name="databases")
app.add_typer(registry_app, name="registry")
app.add_typer(users_app, name="users")
app.add_typer(git_app, name="git")
app.add_typer(notifications_app, name="notifications")
app.add_typer(certificates_app, name="certificates")
app.add_typer(settings_app, name="settings")
app.add_typer(docker_app, name="docker")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(diagnose_app, name="diagnose")
app.add_typer(deploy_app, name="deploy")
app.add_typer(report_app, name="report")
app.add_typer(template_app, name="template")
app.add_typer(audit_app, name="audit")
app.add_typer(setup_app, name="setup")

# ---------------------------------------------------------------------------
# Compose sub-commands (mirrors Dokploy UI tabs)
# ---------------------------------------------------------------------------
compose_app.add_typer(backups_app, name="backups")
compose_app.add_typer(domains_app, name="domains")
compose_app.add_typer(env_app, name="env")
compose_app.add_typer(deployments_app, name="deployments")
compose_app.add_typer(schedules_app, name="schedules")
compose_app.add_typer(patches_app, name="patches")
compose_app.add_typer(volume_backups_app, name="volume-backups")
compose_app.add_typer(mounts_app, name="mounts")
compose_app.add_typer(ports_app, name="ports")
compose_app.add_typer(security_app, name="security")
compose_app.add_typer(redirects_app, name="redirects")
compose_app.add_typer(bulk_app, name="bulk")
compose_app.add_typer(autodeploy_app, name="autodeploy")

# ---------------------------------------------------------------------------
# Server sub-commands
# ---------------------------------------------------------------------------
servers_app.add_typer(monitoring_app, name="monitoring")
servers_app.add_typer(cluster_app, name="cluster")

# ---------------------------------------------------------------------------
# Project sub-commands
# ---------------------------------------------------------------------------
projects_app.add_typer(environments_app, name="environments")

# ---------------------------------------------------------------------------
# Merged groups
# ---------------------------------------------------------------------------
# status → absorbed into dashboard (status.health = dashboard.show)
# pipeline → removed (duplicates compose redeploy + deploy apply)
# maintenance → absorbed into diagnose

# Merge maintenance commands into diagnose
diagnose_app.add_typer(maintenance_app, name="maintenance")

# ---------------------------------------------------------------------------
# Backward compatibility — hidden aliases (old top-level still works)
# ---------------------------------------------------------------------------
app.add_typer(backups_app, name="backups", hidden=True)
app.add_typer(domains_app, name="domains", hidden=True)
app.add_typer(env_app, name="env", hidden=True)
app.add_typer(deployments_app, name="deployments", hidden=True)
app.add_typer(schedules_app, name="schedules", hidden=True)
app.add_typer(patches_app, name="patches", hidden=True)
app.add_typer(volume_backups_app, name="volume-backups", hidden=True)
app.add_typer(mounts_app, name="mounts", hidden=True)
app.add_typer(ports_app, name="ports", hidden=True)
app.add_typer(security_app, name="security", hidden=True)
app.add_typer(redirects_app, name="redirects", hidden=True)
app.add_typer(bulk_app, name="bulk", hidden=True)
app.add_typer(monitoring_app, name="monitoring", hidden=True)
app.add_typer(environments_app, name="environments", hidden=True)
app.add_typer(cluster_app, name="cluster", hidden=True)
app.add_typer(pipeline_app, name="pipeline", hidden=True)
app.add_typer(status_app, name="status", hidden=True)
app.add_typer(maintenance_app, name="maintenance", hidden=True)
app.add_typer(doctor_app, name="doctor")
app.add_typer(skill_app, name="skill", hidden=True)

# Hidden aliases for power users
register_aliases(app)

# Discover and register plugins
discover_and_register_plugins(app)


@app.command("self-update")
def self_update_cmd(ctx: typer.Context) -> None:
    """Check for updates and upgrade kctl-dokploy."""
    actx = ctx.obj
    out = actx.output

    from kctl_lib.self_update import check_update
    from kctl_lib.self_update import update as do_update

    latest = check_update("kctl-dokploy", __version__)
    if latest:
        out.info(f"Updating to {latest}...")
        do_update("kctl-dokploy")
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
        path = install_completions("kctl-dokploy", shell)
        if path:
            typer.echo(f"Completions installed to {path}")
        else:
            typer.echo(f"Could not install completions for {shell}", err=True)
            raise typer.Exit(code=1)
    else:
        script = get_completion_script("kctl-dokploy", shell)
        typer.echo(script)


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
