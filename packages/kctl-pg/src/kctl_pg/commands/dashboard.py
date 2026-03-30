"""Dashboard overview command."""

from __future__ import annotations

import typer

from kctl_pg.core.callbacks import AppContext
from kctl_pg.core.exceptions import KctlError

app = typer.Typer(help="System overview dashboard.")


@app.callback(invoke_without_command=True)
def dashboard(ctx: typer.Context) -> None:
    """Show system overview: databases, connections, sizes, activity."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        c = actx.client
    except KctlError as e:
        out.error(f"Cannot connect: {e}")
        raise typer.Exit(1) from e

    version = c.short_version
    uptime = c.fetchone("SELECT now() - pg_postmaster_start_time() AS uptime")
    uptime_str = str(uptime["uptime"]).split(".")[0] if uptime else "unknown"

    # Database summary
    dbs = c.fetchall("""
        SELECT
            datname AS name,
            pg_size_pretty(pg_database_size(datname)) AS size,
            pg_database_size(datname) AS size_bytes,
            (SELECT count(*) FROM pg_stat_activity WHERE datname = d.datname) AS conns
        FROM pg_database d
        WHERE datistemplate = false
        ORDER BY pg_database_size(datname) DESC
    """)

    total_size = sum(d["size_bytes"] for d in dbs)
    total_size_pretty = c.fetchval("SELECT pg_size_pretty(%s::bigint)", (total_size,))

    # Connection summary
    conn_stats = c.fetchone("""
        SELECT
            count(*) AS total,
            count(*) FILTER (WHERE state = 'active') AS active,
            count(*) FILTER (WHERE state = 'idle') AS idle,
            (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') AS max_conns
        FROM pg_stat_activity
        WHERE backend_type = 'client backend'
    """)

    # Role count
    role_count = c.fetchval("SELECT count(*) FROM pg_roles WHERE rolname !~ '^pg_'")

    # Long-running queries
    long_queries = c.fetchall("""
        SELECT
            pid,
            datname,
            usename,
            state,
            now() - query_start AS duration,
            left(query, 80) AS query
        FROM pg_stat_activity
        WHERE state = 'active'
          AND query NOT LIKE '%pg_stat_activity%'
          AND now() - query_start > interval '5 seconds'
        ORDER BY query_start
        LIMIT 5
    """)

    out.header("PostgreSQL Dashboard")

    # Server info
    out.text(f"  Version: [bold]{version}[/bold]   Uptime: {uptime_str}   Databases: {len(dbs)}   Roles: {role_count}")
    out.text(
        f"  Total size: [bold]{total_size_pretty}[/bold]   Connections: {conn_stats['total']}/{conn_stats['max_conns']} (active: {conn_stats['active']}, idle: {conn_stats['idle']})"
    )
    out.text("")

    # Database table
    db_rows = [[d["name"], d["size"], str(d["conns"])] for d in dbs]
    out.table(
        "Databases",
        [("Name", "cyan"), ("Size", "green"), ("Conns", "")],
        db_rows,
        data_for_json=dbs,
    )

    # Long-running queries
    if long_queries:
        out.text("")
        lq_rows = [
            [str(q["pid"]), q["datname"] or "-", q["usename"] or "-", str(q["duration"]).split(".")[0], q["query"]]
            for q in long_queries
        ]
        out.table(
            "Long-Running Queries (>5s)",
            [("PID", ""), ("Database", ""), ("User", ""), ("Duration", "yellow"), ("Query", "dim")],
            lq_rows,
        )
