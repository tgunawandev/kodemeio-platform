"""Main CLI entry point for kctl-supa."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import handle_cli_error

from kctl_supa import __version__
from kctl_supa.commands.advisors_cmd import app as advisors_app
from kctl_supa.commands.auth_cmd import app as auth_app
from kctl_supa.commands.backup_cmd import app as backup_app
from kctl_supa.commands.config_cmd import app as config_app
from kctl_supa.commands.cron_cmd import app as cron_app
from kctl_supa.commands.dashboard_cmd import app as dashboard_app
from kctl_supa.commands.db_cmd import app as db_app
from kctl_supa.commands.deploy_cmd import app as deploy_app
from kctl_supa.commands.doctor_cmd import app as doctor_app
from kctl_supa.commands.functions_cmd import app as functions_app
from kctl_supa.commands.health_cmd import app as health_app
from kctl_supa.commands.integrations_cmd import app as integrations_app
from kctl_supa.commands.logs_cmd import app as logs_app
from kctl_supa.commands.maintenance_cmd import app as maintenance_app
from kctl_supa.commands.migrate_cmd import app as migrate_app
from kctl_supa.commands.monitor_cmd import app as monitor_app
from kctl_supa.commands.publications_cmd import app as publications_app
from kctl_supa.commands.queues_cmd import app as queues_app
from kctl_supa.commands.realtime_cmd import app as realtime_app
from kctl_supa.commands.security_cmd import app as security_app
from kctl_supa.commands.settings_cmd import app as settings_app
from kctl_supa.commands.skill_cmd import app as skill_app
from kctl_supa.commands.status_cmd import app as status_app
from kctl_supa.commands.storage_cmd import app as storage_app
from kctl_supa.commands.upgrade_cmd import app as upgrade_app
from kctl_supa.commands.vault_cmd import app as vault_app
from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.exceptions import SupabaseError


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-supa {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-supa",
    help="Kodemeio Supabase CLI - manage self-hosted Supabase instances.",
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
    url: Annotated[str | None, typer.Option("--url", help="Supabase URL override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio Supabase CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        url_override=url,
    )


_P_ADMIN = "Admin & Config"
app.add_typer(config_app, name="config", rich_help_panel=_P_ADMIN)
app.add_typer(security_app, name="security", rich_help_panel=_P_ADMIN)
app.add_typer(doctor_app, name="doctor", rich_help_panel=_P_ADMIN)
app.add_typer(vault_app, name="vault", rich_help_panel=_P_ADMIN)
app.add_typer(integrations_app, name="integrations", rich_help_panel=_P_ADMIN)
app.add_typer(settings_app, name="settings", rich_help_panel=_P_ADMIN)

_P_SERVICES = "Services"
app.add_typer(health_app, name="health", rich_help_panel=_P_SERVICES)
app.add_typer(status_app, name="status", rich_help_panel=_P_SERVICES)
app.add_typer(dashboard_app, name="dashboard", rich_help_panel=_P_SERVICES)
app.add_typer(monitor_app, name="monitor", rich_help_panel=_P_SERVICES)
app.add_typer(advisors_app, name="advisors", rich_help_panel=_P_SERVICES)

_P_DATABASE = "Database"
app.add_typer(db_app, name="db", rich_help_panel=_P_DATABASE)
app.add_typer(backup_app, name="backup", rich_help_panel=_P_DATABASE)
app.add_typer(maintenance_app, name="maintenance", rich_help_panel=_P_DATABASE)
app.add_typer(migrate_app, name="migrate", rich_help_panel=_P_DATABASE)
app.add_typer(cron_app, name="cron", rich_help_panel=_P_DATABASE)
app.add_typer(queues_app, name="queues", rich_help_panel=_P_DATABASE)

_P_AUTH = "Auth & Users"
app.add_typer(auth_app, name="auth", rich_help_panel=_P_AUTH)

_P_STORAGE = "Storage & Files"
app.add_typer(storage_app, name="storage", rich_help_panel=_P_STORAGE)

_P_RT = "Realtime & Functions"
app.add_typer(realtime_app, name="realtime", rich_help_panel=_P_RT)
app.add_typer(functions_app, name="functions", rich_help_panel=_P_RT)
app.add_typer(publications_app, name="publications", rich_help_panel=_P_RT)

_P_OPS = "Operations"
app.add_typer(logs_app, name="logs", rich_help_panel=_P_OPS)
app.add_typer(deploy_app, name="deploy", rich_help_panel=_P_OPS)
app.add_typer(upgrade_app, name="upgrade", rich_help_panel=_P_OPS)

app.add_typer(skill_app, name="skill", hidden=True)


@app.command("self-update")
def self_update_cmd(ctx: typer.Context) -> None:
    """Check for updates and upgrade kctl-supa."""
    actx = ctx.obj
    out = actx.output
    from kctl_lib.self_update import check_update
    from kctl_lib.self_update import update as do_update

    latest = check_update("kctl-supa", __version__)
    if latest:
        out.info(f"Updating to {latest}...")
        do_update("kctl-supa")
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
        path = install_completions("kctl-supa", shell)
        if path:
            typer.echo(f"Completions installed to {path}")
        else:
            typer.echo(f"Could not install completions for {shell}", err=True)
            raise typer.Exit(code=1)
    else:
        script = get_completion_script("kctl-supa", shell)
        typer.echo(script)


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except SupabaseError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
