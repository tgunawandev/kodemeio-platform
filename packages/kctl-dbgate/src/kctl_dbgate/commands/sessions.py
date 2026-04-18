"""Session management commands.

Wraps /sessions/* RPC endpoints.

NOTE: DBGate does not expose a dedicated "list sessions" endpoint.
/sessions/ping takes a sesid and reports that session's status rather
than enumerating all sessions. We therefore expose `create`, `ping`
(checks a specific sesid) and `kill` — no `list`.
"""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib.exceptions import KctlError

from kctl_dbgate.core.callbacks import AppContext

app = typer.Typer(help="Manage DBGate database sessions.")


@app.command()
def create(
    ctx: typer.Context,
    connection: Annotated[str, typer.Option("--connection", help="Connection ID")],
    database: Annotated[str, typer.Option("--database", help="Database name")],
) -> None:
    """Create a new database session."""
    actx: AppContext = ctx.obj
    out = actx.output
    try:
        result = actx.client.call("/sessions/create", {"conid": connection, "database": database})
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    sesid = (result or {}).get("sesid", "")
    out.success(f"Session created: {sesid}")
    out.kv("Session ID", sesid)


@app.command()
def ping(
    ctx: typer.Context,
    sesid: Annotated[str, typer.Argument(help="Session ID")],
) -> None:
    """Check a session's status."""
    actx: AppContext = ctx.obj
    out = actx.output
    try:
        result = actx.client.call("/sessions/ping", {"sesid": sesid})
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e
    out.success(f"Session {sesid}: {result}")


@app.command()
def kill(
    ctx: typer.Context,
    sesid: Annotated[str, typer.Argument(help="Session ID")],
) -> None:
    """Kill a session."""
    actx: AppContext = ctx.obj
    out = actx.output
    try:
        actx.client.call("/sessions/kill", {"sesid": sesid})
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e
    out.success(f"Session {sesid} killed")
