"""Connection inspection commands."""

from __future__ import annotations

import typer
from kctl_lib.exceptions import KctlError

from kctl_dbgate.core.callbacks import AppContext

app = typer.Typer(help="Inspect pre-configured DBGate connections.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all connections known to DBGate (env-configured + user-added)."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        connections = actx.client.list_connections()
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    rows: list[list[str]] = []
    for conn in connections:
        rows.append(
            [
                str(conn.get("_id", "")),
                str(conn.get("displayName") or conn.get("label") or ""),
                str(conn.get("engine", "")),
                str(conn.get("server", "")),
                str(conn.get("port", "")),
                str(conn.get("user", "")),
                "yes" if conn.get("isReadOnly") else "no",
            ]
        )

    out.table(
        title=f"{len(rows)} connection(s)",
        columns=[
            ("ID", "cyan"),
            ("Label", "white"),
            ("Engine", "magenta"),
            ("Server", "green"),
            ("Port", "yellow"),
            ("User", "blue"),
            ("ReadOnly", "yellow"),
        ],
        rows=rows,
    )
