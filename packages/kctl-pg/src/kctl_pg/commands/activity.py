"""Connection and activity monitoring commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_pg.core.callbacks import AppContext

app = typer.Typer(help="Monitor connections and activity.")


@app.command("list")
def list_(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Filter by database")] = None,
    state: Annotated[
        str | None, typer.Option("--state", help="Filter by state (active, idle, idle in transaction)")
    ] = None,
) -> None:
    """List active connections."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    sql = """
        SELECT
            pid,
            datname AS database,
            usename AS user,
            client_addr,
            state,
            now() - backend_start AS backend_age,
            now() - query_start AS query_duration,
            left(query, 100) AS query
        FROM pg_stat_activity
        WHERE backend_type = 'client backend'
    """
    params: list = []

    if database:
        sql += " AND datname = %s"
        params.append(database)
    if state:
        sql += " AND state = %s"
        params.append(state)

    sql += " ORDER BY backend_start"

    rows_data = c.fetchall(sql, tuple(params) if params else None)

    rows = [
        [
            str(r["pid"]),
            r["database"] or "-",
            r["user"] or "-",
            str(r["client_addr"]) if r["client_addr"] else "-",
            r["state"] or "-",
            str(r["query_duration"]).split(".")[0] if r["query_duration"] else "-",
            r["query"][:60] if r["query"] else "-",
        ]
        for r in rows_data
    ]

    out.table(
        f"Connections ({len(rows_data)})",
        [
            ("PID", ""),
            ("Database", "cyan"),
            ("User", ""),
            ("Client", ""),
            ("State", ""),
            ("Duration", "yellow"),
            ("Query", "dim"),
        ],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def kill(
    ctx: typer.Context,
    pid: Annotated[int, typer.Argument(help="Backend PID to terminate")],
    force: Annotated[
        bool, typer.Option("--force", help="Use pg_terminate_backend (instead of pg_cancel_backend)")
    ] = False,
) -> None:
    """Cancel or terminate a backend process."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if force:
        result = c.fetchval("SELECT pg_terminate_backend(%s)", (pid,))
        action = "Terminated"
    else:
        result = c.fetchval("SELECT pg_cancel_backend(%s)", (pid,))
        action = "Cancelled"

    if result:
        out.success(f"{action} backend PID {pid}")
    else:
        out.error(f"Failed to {action.lower()} PID {pid} (process may not exist)")


@app.command()
def locks(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Filter by database")] = None,
) -> None:
    """Show lock contention (blocked queries waiting for locks)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    rows_data = c.fetchall("""
        SELECT
            blocked.pid AS blocked_pid,
            blocked.usename AS blocked_user,
            blocked_activity.query AS blocked_query,
            blocking.pid AS blocking_pid,
            blocking.usename AS blocking_user,
            blocking_activity.query AS blocking_query,
            blocked.datname AS database
        FROM pg_catalog.pg_locks blocked
        JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked.pid
        JOIN pg_catalog.pg_locks blocking ON blocking.locktype = blocked.locktype
            AND blocking.database IS NOT DISTINCT FROM blocked.database
            AND blocking.relation IS NOT DISTINCT FROM blocked.relation
            AND blocking.page IS NOT DISTINCT FROM blocked.page
            AND blocking.tuple IS NOT DISTINCT FROM blocked.tuple
            AND blocking.virtualxid IS NOT DISTINCT FROM blocked.virtualxid
            AND blocking.transactionid IS NOT DISTINCT FROM blocked.transactionid
            AND blocking.classid IS NOT DISTINCT FROM blocked.classid
            AND blocking.objid IS NOT DISTINCT FROM blocked.objid
            AND blocking.objsubid IS NOT DISTINCT FROM blocked.objsubid
            AND blocking.pid != blocked.pid
        JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking.pid
        JOIN pg_stat_activity blocked_sa ON blocked_sa.pid = blocked.pid
        WHERE NOT blocked.granted
    """)

    if database:
        rows_data = [r for r in rows_data if r["database"] == database]

    if not rows_data:
        out.success("No lock contention detected")
        return

    rows = [
        [
            str(r["blocked_pid"]),
            r["blocked_user"] or "-",
            (r["blocked_query"] or "-")[:50],
            str(r["blocking_pid"]),
            r["blocking_user"] or "-",
            (r["blocking_query"] or "-")[:50],
        ]
        for r in rows_data
    ]

    out.table(
        f"Lock Contention ({len(rows_data)})",
        [
            ("Blocked PID", "red"),
            ("User", ""),
            ("Blocked Query", "dim"),
            ("Blocking PID", "yellow"),
            ("User", ""),
            ("Blocking Query", "dim"),
        ],
        rows,
        data_for_json=rows_data,
    )
