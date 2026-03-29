"""Peer (device) management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_rustdesk.core.callbacks import AppContext

app = typer.Typer(help="Manage RustDesk peers (devices).")


@app.command("list")
def list_(
    ctx: typer.Context,
    online: Annotated[bool, typer.Option("--online", help="Only online peers")] = False,
) -> None:
    """List all registered peers."""
    c: AppContext = ctx.obj
    ex = c.executor

    if online:
        sql = (
            "SELECT id, uuid, pk, created_at, last_online, note "
            "FROM peer WHERE last_online > datetime('now', '-5 minutes') "
            "ORDER BY last_online DESC;"
        )
    else:
        sql = "SELECT id, uuid, pk, created_at, last_online, note FROM peer ORDER BY last_online DESC;"

    rows_data = ex.query_db(sql)
    rows = [[r.get("id", ""), r.get("uuid", ""), r.get("last_online", ""), r.get("note", "")] for r in rows_data]

    c.output.table(
        "Peers" + (" (online)" if online else ""),
        [("ID", "cyan"), ("UUID", "dim"), ("Last Online", ""), ("Note", "")],
        rows,
        data_for_json=rows_data,
    )


@app.command("get")
def get(
    ctx: typer.Context,
    peer_id: Annotated[str, typer.Argument(help="Peer ID")],
) -> None:
    """Get details for a specific peer."""
    c: AppContext = ctx.obj
    ex = c.executor

    rows = ex.query_db(f"SELECT * FROM peer WHERE id = '{peer_id}';")
    if not rows:
        c.output.error(f"Peer not found: {peer_id}")
        raise typer.Exit(1)

    peer = rows[0]
    sections = [("Peer Details", [(k, str(v)) for k, v in peer.items()])]
    c.output.detail(f"Peer: {peer_id}", sections, data_for_json=peer)


@app.command()
def count(ctx: typer.Context) -> None:
    """Count total peers."""
    c: AppContext = ctx.obj
    ex = c.executor

    total = ex.query_db_scalar("SELECT count(*) FROM peer;")
    recent = ex.query_db_scalar("SELECT count(*) FROM peer WHERE last_online > datetime('now', '-5 minutes');")

    sections = [("Peer Count", [("Total", total), ("Online (5m)", recent)])]
    c.output.detail(
        "Peer Count",
        sections,
        data_for_json={
            "total": int(total),
            "online": int(recent),
        },
    )


@app.command()
def search(
    ctx: typer.Context,
    term: Annotated[str, typer.Argument(help="Search term (ID, UUID, or note)")],
) -> None:
    """Search peers by ID, UUID, or note."""
    c: AppContext = ctx.obj
    ex = c.executor

    sql = (
        f"SELECT id, uuid, last_online, note FROM peer "
        f"WHERE id LIKE '%{term}%' OR uuid LIKE '%{term}%' OR note LIKE '%{term}%' "
        f"ORDER BY last_online DESC;"
    )
    rows_data = ex.query_db(sql)
    rows = [[r.get("id", ""), r.get("uuid", ""), r.get("last_online", ""), r.get("note", "")] for r in rows_data]

    c.output.table(
        f"Search: {term}",
        [("ID", "cyan"), ("UUID", "dim"), ("Last Online", ""), ("Note", "")],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def export(ctx: typer.Context) -> None:
    """Export all peers as JSON."""
    c: AppContext = ctx.obj
    rows = c.executor.query_db("SELECT * FROM peer ORDER BY last_online DESC;")
    c.output.raw_json(rows)
