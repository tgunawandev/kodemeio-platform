"""Main CLI entry point for kctl-redis."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import handle_cli_error

from kctl_redis import __version__
from kctl_redis.commands.backup import app as backup_app
from kctl_redis.commands.clients import app as clients_app
from kctl_redis.commands.config_cmd import app as config_app
from kctl_redis.commands.dashboard import app as dashboard_app
from kctl_redis.commands.db import app as db_app
from kctl_redis.commands.health import app as health_app
from kctl_redis.commands.keys import app as keys_app
from kctl_redis.commands.maintenance import app as maintenance_app
from kctl_redis.commands.memory import app as memory_app
from kctl_redis.commands.performance import app as performance_app
from kctl_redis.commands.persistence import app as persistence_app
from kctl_redis.commands.pubsub import app as pubsub_app
from kctl_redis.commands.query import app as query_app
from kctl_redis.commands.replication import app as replication_app
from kctl_redis.commands.server import app as server_app
from kctl_redis.commands.streams import app as streams_app
from kctl_redis.commands.skill_cmd import app as skill_app
from kctl_redis.core.callbacks import AppContext
from kctl_redis.core.exceptions import KctlError


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-redis {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-redis",
    help="Kodemeio Redis CLI - manage Redis servers via SSH tunnel.",
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
    host: Annotated[str | None, typer.Option("--host", "-H", help="Redis host override")] = None,
    port: Annotated[int | None, typer.Option("--port", help="Redis port override")] = None,
    user: Annotated[str | None, typer.Option("--user", "-U", help="Redis username override")] = None,
    password: Annotated[str | None, typer.Option("--password", help="Redis password override")] = None,
    db: Annotated[int | None, typer.Option("--db", help="Redis database number override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio Redis CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        host_override=host,
        port_override=port,
        user_override=user,
        password_override=password,
        db_override=db,
    )


# Register all command groups
app.add_typer(config_app, name="config")
app.add_typer(health_app, name="health")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(query_app, name="query")
app.add_typer(keys_app, name="keys")
app.add_typer(db_app, name="db")
app.add_typer(memory_app, name="memory")
app.add_typer(clients_app, name="clients")
app.add_typer(server_app, name="server")
app.add_typer(persistence_app, name="persistence")
app.add_typer(replication_app, name="replication")
app.add_typer(pubsub_app, name="pubsub")
app.add_typer(streams_app, name="streams")
app.add_typer(performance_app, name="performance")
app.add_typer(backup_app, name="backup")
app.add_typer(maintenance_app, name="maintenance")
app.add_typer(skill_app, name="skill", hidden=True)


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
