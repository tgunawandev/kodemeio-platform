"""Audit log and connection history commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_rustdesk.core.callbacks import AppContext

app = typer.Typer(help="Audit logs and connection history.")


@app.command()
def connections(
    ctx: typer.Context,
    today: Annotated[bool, typer.Option("--today", help="Only today")] = False,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max rows")] = 50,
) -> None:
    """Show connection history."""
    c: AppContext = ctx.obj
    ex = c.executor

    where = "WHERE date(created_at) = date('now')" if today else ""
    sql = f"SELECT peer_id, ip, created_at FROM conn_log {where} ORDER BY created_at DESC LIMIT {limit};"

    rows_data = ex.query_db(sql)
    rows = [[r.get("peer_id", ""), r.get("ip", ""), r.get("created_at", "")] for r in rows_data]

    title = "Connections (today)" if today else f"Connections (last {limit})"
    c.output.table(
        title,
        [("Peer ID", "cyan"), ("IP", ""), ("Time", "dim")],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def logins(
    ctx: typer.Context,
    failed: Annotated[bool, typer.Option("--failed", help="Only failed logins")] = False,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max rows")] = 50,
) -> None:
    """Show login history."""
    c: AppContext = ctx.obj
    ex = c.executor

    where = "WHERE type != 0" if failed else ""
    sql = f"SELECT user_id, ip, type, created_at FROM login_log {where} ORDER BY created_at DESC LIMIT {limit};"

    rows_data = ex.query_db(sql)
    rows = [
        [
            r.get("user_id", ""),
            r.get("ip", ""),
            "failed" if r.get("type", "0") != "0" else "ok",
            r.get("created_at", ""),
        ]
        for r in rows_data
    ]

    title = "Failed Logins" if failed else f"Logins (last {limit})"
    c.output.table(
        title,
        [("User", "cyan"), ("IP", ""), ("Status", ""), ("Time", "dim")],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def stats(ctx: typer.Context) -> None:
    """Show connection statistics."""
    c: AppContext = ctx.obj
    ex = c.executor

    total_conns = ex.query_db_scalar("SELECT count(*) FROM conn_log;")
    today_conns = ex.query_db_scalar("SELECT count(*) FROM conn_log WHERE date(created_at) = date('now');")
    unique_peers = ex.query_db_scalar("SELECT count(DISTINCT peer_id) FROM conn_log;")
    unique_ips = ex.query_db_scalar("SELECT count(DISTINCT ip) FROM conn_log;")
    total_logins = ex.query_db_scalar("SELECT count(*) FROM login_log;")
    failed_logins = ex.query_db_scalar("SELECT count(*) FROM login_log WHERE type != 0;")

    top_peers = ex.query_db("SELECT peer_id, count(*) as cnt FROM conn_log GROUP BY peer_id ORDER BY cnt DESC LIMIT 5;")

    sections = [
        (
            "Connection Stats",
            [
                ("Total connections", total_conns),
                ("Today", today_conns),
                ("Unique peers", unique_peers),
                ("Unique IPs", unique_ips),
            ],
        ),
        (
            "Login Stats",
            [
                ("Total logins", total_logins),
                ("Failed logins", failed_logins),
            ],
        ),
        ("Top Peers", [(p.get("peer_id", ""), f"{p.get('cnt', 0)} connections") for p in top_peers]),
    ]

    c.output.detail(
        "Audit Statistics",
        sections,
        data_for_json={
            "connections": {
                "total": int(total_conns),
                "today": int(today_conns),
                "unique_peers": int(unique_peers),
                "unique_ips": int(unique_ips),
            },
            "logins": {"total": int(total_logins), "failed": int(failed_logins)},
            "top_peers": top_peers,
        },
    )


@app.command()
def active(ctx: typer.Context) -> None:
    """Show currently active sessions."""
    c: AppContext = ctx.obj
    ex = c.executor

    sql = (
        "SELECT peer_id, ip, created_at FROM conn_log "
        "WHERE created_at > datetime('now', '-5 minutes') "
        "ORDER BY created_at DESC;"
    )

    rows_data = ex.query_db(sql)
    rows = [[r.get("peer_id", ""), r.get("ip", ""), r.get("created_at", "")] for r in rows_data]

    c.output.table(
        "Active Sessions (last 5m)",
        [("Peer ID", "cyan"), ("IP", ""), ("Connected", "dim")],
        rows,
        data_for_json=rows_data,
    )
