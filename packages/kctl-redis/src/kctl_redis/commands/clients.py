"""Client connection management commands for kctl-redis."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_redis.core.callbacks import AppContext

app = typer.Typer(help="Redis client management.", no_args_is_help=True)


@app.command(name="list")
def list_clients(ctx: typer.Context) -> None:
    """List connected clients."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    r = app_ctx.client.r

    clients = r.client_list()
    if app_ctx.json_mode:
        out.json({"clients": clients})
    else:
        rows = [
            {
                "id": c.get("id", "?"),
                "addr": c.get("addr", "?"),
                "name": c.get("name", ""),
                "age": c.get("age", "?"),
                "idle": c.get("idle", "?"),
                "db": c.get("db", "?"),
                "cmd": c.get("cmd", "?"),
            }
            for c in clients
        ]
        out.table(rows, columns=["id", "addr", "name", "age", "idle", "db", "cmd"], title="Connected Clients")

    app_ctx.close()


@app.command()
def kill(
    ctx: typer.Context,
    client_id: Annotated[int, typer.Argument(help="Client ID to kill")],
) -> None:
    """Kill a client connection by ID."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    r = app_ctx.client.r

    r.client_kill_filter(_id=client_id)
    out.success(f"Killed client {client_id}")
    app_ctx.close()


@app.command()
def info(ctx: typer.Context) -> None:
    """Show client connection info."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    clients_info = c.info("clients")
    if app_ctx.json_mode:
        out.json(clients_info)
    else:
        rows = [{"metric": k, "value": str(v)} for k, v in clients_info.items()]
        out.table(rows, columns=["metric", "value"], title="Client Info")

    app_ctx.close()
