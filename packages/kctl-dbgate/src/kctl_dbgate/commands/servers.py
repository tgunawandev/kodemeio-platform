"""Server-level database management commands.

Wraps DBGate's /server-connections/* RPC endpoints.
"""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib.exceptions import KctlError

from kctl_dbgate.core.callbacks import AppContext

app = typer.Typer(help="Server-level database management (ping, summary, create/drop DB).")


@app.command()
def ping(
    ctx: typer.Context,
    conid: Annotated[str, typer.Argument(help="Connection ID")],
) -> None:
    """Ping a server-level connection (keeps it alive).

    DBGate's /server-connections/ping expects {conidArray, strmid}, NOT a
    single conid — a flat {conid} makes the server iterate over an empty
    list (uniq(undefined) -> []) and do nothing.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    try:
        result = actx.client.call(
            "/server-connections/ping",
            {"conidArray": [conid], "strmid": "kctl-dbgate"},
        )
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e
    out.success(f"Ping OK: {result}")


@app.command()
def summary(
    ctx: typer.Context,
    conid: Annotated[str, typer.Argument(help="Connection ID")],
) -> None:
    """Show databases on a server."""
    actx: AppContext = ctx.obj
    out = actx.output
    try:
        result = actx.client.call("/server-connections/server-summary", {"conid": conid})
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    items = result if isinstance(result, list) else (result or {}).get("databases") or []
    rows: list[list[str]] = []
    for db in items:
        if isinstance(db, dict):
            rows.append([str(db.get("name", "")), str(db.get("sortingKey", "")), str(db.get("owner", ""))])
        else:
            rows.append([str(db), "", ""])
    out.table(
        title=f"{len(rows)} database(s) on {conid}",
        columns=[("Name", "cyan"), ("SortingKey", "dim"), ("Owner", "dim")],
        rows=rows,
        data_for_json=items if isinstance(items, list) else None,
    )


@app.command("create-database")
def create_database(
    ctx: typer.Context,
    conid: Annotated[str, typer.Argument(help="Connection ID")],
    name: Annotated[str, typer.Option("--name", help="Database name")],
) -> None:
    """Create a new database on the server."""
    actx: AppContext = ctx.obj
    out = actx.output
    try:
        actx.client.call("/server-connections/create-database", {"conid": conid, "name": name})
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e
    out.success(f"Database '{name}' created on {conid}")


@app.command("drop-database")
def drop_database(
    ctx: typer.Context,
    conid: Annotated[str, typer.Argument(help="Connection ID")],
    name: Annotated[str, typer.Option("--name", help="Database name")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Drop a database on the server."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not force and not typer.confirm(f"DROP DATABASE '{name}' on {conid}?"):
        raise typer.Exit(0)

    try:
        actx.client.call("/server-connections/drop-database", {"conid": conid, "name": name})
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e
    out.success(f"Database '{name}' dropped on {conid}")


@app.command()
def refresh(
    ctx: typer.Context,
    conid: Annotated[str, typer.Argument(help="Connection ID")],
) -> None:
    """Refresh server metadata cache."""
    actx: AppContext = ctx.obj
    out = actx.output
    try:
        actx.client.call("/server-connections/refresh", {"conid": conid})
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e
    out.success(f"Server {conid} refreshed")


@app.command()
def disconnect(
    ctx: typer.Context,
    conid: Annotated[str, typer.Argument(help="Connection ID")],
) -> None:
    """Disconnect a server-level connection."""
    actx: AppContext = ctx.obj
    out = actx.output
    try:
        actx.client.call("/server-connections/disconnect", {"conid": conid})
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e
    out.success(f"Server {conid} disconnected")
