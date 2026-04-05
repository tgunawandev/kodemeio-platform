"""Main CLI entry point for kctl-pg."""

from __future__ import annotations


from typing import Annotated

import typer
from kctl_lib import handle_cli_error

from kctl_pg import __version__
from kctl_pg.commands.activity import app as activity_app
from kctl_pg.commands.automation import app as automation_app
from kctl_pg.commands.backup import app as backup_app
from kctl_pg.commands.config_cmd import app as config_app
from kctl_pg.commands.dashboard import app as dashboard_app
from kctl_pg.commands.db import app as db_app
from kctl_pg.commands.dr import app as dr_app
from kctl_pg.commands.extensions import app as extensions_app
from kctl_pg.commands.health import app as health_app
from kctl_pg.commands.indexes import app as indexes_app
from kctl_pg.commands.lint import app as lint_app
from kctl_pg.commands.maintenance import app as maintenance_app
from kctl_pg.commands.performance import app as performance_app
from kctl_pg.commands.pg_config import app as pg_config_app
from kctl_pg.commands.pgbouncer import app as pgbouncer_app
from kctl_pg.commands.pipeline import app as pipeline_app
from kctl_pg.commands.query import app as query_app
from kctl_pg.commands.replication import app as replication_app
from kctl_pg.commands.schemas import app as schemas_app
from kctl_pg.commands.security import app as security_app
from kctl_pg.commands.stats import app as stats_app
from kctl_pg.commands.tables import app as tables_app
from kctl_pg.commands.users import app as users_app
from kctl_pg.core.callbacks import AppContext
from kctl_pg.core.exceptions import KctlError
from kctl_pg.commands.skill_cmd import app as skill_app
from kctl_pg.commands.doctor_cmd import app as doctor_app


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-pg {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-pg",
    help="Kodemeio PostgreSQL CLI - manage PostgreSQL servers via SSH tunnel.",
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
    host: Annotated[str | None, typer.Option("--host", "-H", help="PostgreSQL host override")] = None,
    port: Annotated[int | None, typer.Option("--port", help="PostgreSQL port override")] = None,
    user: Annotated[str | None, typer.Option("--user", "-U", help="PostgreSQL user override")] = None,
    password: Annotated[str | None, typer.Option("--password", help="PostgreSQL password override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio PostgreSQL CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        host_override=host,
        port_override=port,
        user_override=user,
        password_override=password,
    )


# Register all command groups
app.add_typer(config_app, name="config")
app.add_typer(db_app, name="db")
app.add_typer(users_app, name="users")
app.add_typer(health_app, name="health")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(query_app, name="query")
app.add_typer(activity_app, name="activity")
app.add_typer(backup_app, name="backup")
app.add_typer(extensions_app, name="extensions")
app.add_typer(maintenance_app, name="maintenance")
app.add_typer(performance_app, name="performance")
app.add_typer(pg_config_app, name="pg-config")
app.add_typer(replication_app, name="replication")
app.add_typer(security_app, name="security")
app.add_typer(stats_app, name="stats")
app.add_typer(tables_app, name="tables")
app.add_typer(indexes_app, name="indexes")
app.add_typer(schemas_app, name="schemas")
app.add_typer(pgbouncer_app, name="pgbouncer")
app.add_typer(lint_app, name="lint")
app.add_typer(automation_app, name="automation")
app.add_typer(dr_app, name="dr")
app.add_typer(pipeline_app, name="pipeline")
app.add_typer(skill_app, name="skill", hidden=True)
app.add_typer(doctor_app, name="doctor")


@app.command("self-update")
def self_update_cmd(ctx: typer.Context) -> None:
    """Check for updates and upgrade kctl-pg."""
    actx = ctx.obj
    out = actx.output

    from kctl_lib.self_update import check_update
    from kctl_lib.self_update import update as do_update

    latest = check_update("kctl-pg", __version__)
    if latest:
        out.info(f"Updating to {latest}...")
        do_update("kctl-pg")
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
        path = install_completions("kctl-pg", shell)
        if path:
            typer.echo(f"Completions installed to {path}")
        else:
            typer.echo(f"Could not install completions for {shell}", err=True)
            raise typer.Exit(code=1)
    else:
        script = get_completion_script("kctl-pg", shell)
        typer.echo(script)


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
