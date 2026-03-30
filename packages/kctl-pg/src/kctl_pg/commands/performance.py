"""Performance monitoring commands: overview, slow queries, stats, cache, locks, etc."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_pg.core.callbacks import AppContext
from kctl_pg.core.exceptions import DatabaseError

app = typer.Typer(help="Performance monitoring and diagnostics.")


def _format_ts(ts: object) -> str:
    """Format a timestamp for display, returning '-' for None."""
    if ts is None:
        return "-"
    return str(ts).split(".")[0]


@app.command()
def overview(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Filter by database")] = None,
) -> None:
    """Show performance overview: cache hits, transactions, connections, DB sizes."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Database stats
    sql = """
        SELECT
            datname,
            numbackends AS connections,
            xact_commit AS commits,
            xact_rollback AS rollbacks,
            blks_read,
            blks_hit,
            CASE
                WHEN blks_hit + blks_read = 0 THEN 0
                ELSE round(100.0 * blks_hit / (blks_hit + blks_read), 2)
            END AS cache_hit_ratio,
            tup_returned,
            tup_fetched,
            tup_inserted,
            tup_updated,
            tup_deleted,
            pg_size_pretty(pg_database_size(datname)) AS size
        FROM pg_stat_database
        WHERE datname NOT LIKE 'template%%'
    """
    params: list = []
    if database:
        sql += " AND datname = %s"
        params.append(database)
    sql += " ORDER BY pg_database_size(datname) DESC"

    rows_data = c.fetchall(sql, tuple(params) if params else None)

    if not rows_data:
        out.info("No databases found")
        return

    # Connection usage
    max_conns = c.fetchval("SELECT setting::int FROM pg_settings WHERE name = 'max_connections'")
    total_conns = c.fetchval("SELECT count(*) FROM pg_stat_activity WHERE backend_type = 'client backend'")

    # Summary section
    total_commits = sum(r["commits"] for r in rows_data)
    total_rollbacks = sum(r["rollbacks"] for r in rows_data)
    total_hits = sum(r["blks_hit"] for r in rows_data)
    total_reads = sum(r["blks_read"] for r in rows_data)
    overall_ratio = round(100.0 * total_hits / (total_hits + total_reads), 2) if (total_hits + total_reads) > 0 else 0

    sections = [
        (
            "Connections",
            [
                ("Used / Max", f"{total_conns} / {max_conns}"),
                ("Usage %", f"{round(100.0 * total_conns / max_conns, 1)}%" if max_conns else "-"),
            ],
        ),
        (
            "Transactions (cumulative)",
            [
                ("Commits", f"{total_commits:,}"),
                ("Rollbacks", f"{total_rollbacks:,}"),
                (
                    "Rollback Ratio",
                    f"{round(100.0 * total_rollbacks / (total_commits + total_rollbacks), 2)}%"
                    if (total_commits + total_rollbacks) > 0
                    else "0%",
                ),
            ],
        ),
        (
            "Buffer Cache",
            [
                ("Overall Hit Ratio", f"{overall_ratio}%"),
                ("Blocks Hit", f"{total_hits:,}"),
                ("Blocks Read", f"{total_reads:,}"),
            ],
        ),
    ]

    json_data = {
        "connections": {"used": total_conns, "max": max_conns},
        "transactions": {"commits": total_commits, "rollbacks": total_rollbacks},
        "cache": {"hit_ratio": overall_ratio, "blks_hit": total_hits, "blks_read": total_reads},
        "databases": rows_data,
    }

    out.detail("Performance Overview", sections, data_for_json=json_data)

    # Per-database table
    rows = [
        [
            r["datname"],
            r["size"],
            str(r["connections"]),
            f"{r['cache_hit_ratio']}%",
            f"{r['commits']:,}",
            f"{r['rollbacks']:,}",
        ]
        for r in rows_data
    ]

    out.table(
        "Per-Database Stats",
        [
            ("Database", "cyan"),
            ("Size", "green"),
            ("Conns", ""),
            ("Cache Hit %", "yellow"),
            ("Commits", ""),
            ("Rollbacks", "red"),
        ],
        rows,
        data_for_json=rows_data,
    )


@app.command("slow-queries")
def slow_queries(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Filter by database")] = None,
    min_duration: Annotated[float, typer.Option("--min-duration", help="Minimum mean duration in ms")] = 0,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of queries to show")] = 20,
) -> None:
    """Show slowest queries from pg_stat_statements."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Check if pg_stat_statements is available
    ext = c.fetchval("SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'")
    if not ext:
        out.warn("pg_stat_statements extension is not installed.")
        out.info("Install it with: kctl-pg extensions install pg_stat_statements")
        return

    sql = """
        SELECT
            d.datname AS database,
            s.calls,
            round(s.total_exec_time::numeric, 2) AS total_time_ms,
            round(s.mean_exec_time::numeric, 2) AS mean_time_ms,
            round(s.min_exec_time::numeric, 2) AS min_time_ms,
            round(s.max_exec_time::numeric, 2) AS max_time_ms,
            s.rows,
            left(s.query, 120) AS query
        FROM pg_stat_statements s
        JOIN pg_database d ON d.oid = s.dbid
        WHERE s.calls > 0
    """
    params: list = []

    if database:
        sql += " AND d.datname = %s"
        params.append(database)
    if min_duration > 0:
        sql += " AND s.mean_exec_time >= %s"
        params.append(min_duration)

    sql += " ORDER BY s.mean_exec_time DESC LIMIT %s"
    params.append(limit)

    try:
        rows_data = c.fetchall(sql, tuple(params))
    except DatabaseError:
        out.error(
            "Failed to query pg_stat_statements. The extension may need to be loaded in shared_preload_libraries."
        )
        return

    if not rows_data:
        out.info("No queries found matching criteria")
        return

    rows = [
        [
            r["database"],
            str(r["calls"]),
            f"{r['mean_time_ms']} ms",
            f"{r['total_time_ms']} ms",
            f"{r['min_time_ms']}",
            f"{r['max_time_ms']}",
            str(r["rows"]),
            r["query"][:80] if r["query"] else "-",
        ]
        for r in rows_data
    ]

    out.table(
        f"Slowest Queries (top {limit})",
        [
            ("Database", "cyan"),
            ("Calls", ""),
            ("Mean Time", "yellow"),
            ("Total Time", "red"),
            ("Min (ms)", "dim"),
            ("Max (ms)", "dim"),
            ("Rows", ""),
            ("Query", "dim"),
        ],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def cache(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Filter by database")] = None,
) -> None:
    """Show buffer cache hit ratio per database."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    sql = """
        SELECT
            datname,
            blks_hit,
            blks_read,
            CASE
                WHEN blks_hit + blks_read = 0 THEN 0
                ELSE round(100.0 * blks_hit / (blks_hit + blks_read), 2)
            END AS hit_ratio
        FROM pg_stat_database
        WHERE datname NOT LIKE 'template%%'
    """
    params: list = []
    if database:
        sql += " AND datname = %s"
        params.append(database)
    sql += " ORDER BY blks_hit + blks_read DESC"

    rows_data = c.fetchall(sql, tuple(params) if params else None)

    if not rows_data:
        out.info("No databases found")
        return

    rows = [
        [
            r["datname"],
            _cache_ratio_style(r["hit_ratio"]),
            f"{r['blks_hit']:,}",
            f"{r['blks_read']:,}",
        ]
        for r in rows_data
    ]

    out.table(
        "Buffer Cache Hit Ratio",
        [
            ("Database", "cyan"),
            ("Hit Ratio", ""),
            ("Blocks Hit", "green"),
            ("Blocks Read", "red"),
        ],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def settings(
    ctx: typer.Context,
    filter: Annotated[str | None, typer.Option("--filter", "-f", help="Filter settings by name pattern")] = None,
) -> None:
    """Show PostgreSQL configuration parameters."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    sql = """
        SELECT
            name,
            setting,
            unit,
            category,
            short_desc,
            source,
            pending_restart
        FROM pg_settings
    """
    params: list = []
    if filter:
        sql += " WHERE name LIKE %s"
        params.append(f"%{filter}%")
    sql += " ORDER BY category, name"

    rows_data = c.fetchall(sql, tuple(params) if params else None)

    if not rows_data:
        out.info("No settings found matching the filter")
        return

    rows = [
        [
            r["name"],
            r["setting"],
            r["unit"] or "",
            r["source"],
            "[yellow]yes[/yellow]" if r["pending_restart"] else "",
            (r["short_desc"] or "")[:50],
        ]
        for r in rows_data
    ]

    out.table(
        f"PostgreSQL Settings ({len(rows_data)})",
        [
            ("Name", "cyan"),
            ("Value", "green"),
            ("Unit", "dim"),
            ("Source", ""),
            ("Restart?", ""),
            ("Description", "dim"),
        ],
        rows,
        data_for_json=rows_data,
    )


def _cache_ratio_style(ratio: object) -> str:
    """Style cache hit ratio with color based on value."""
    if ratio is None:
        return "-"
    r = float(ratio)
    if r >= 99:
        return f"[green]{r}%[/green]"
    if r >= 90:
        return f"[yellow]{r}%[/yellow]"
    return f"[red]{r}%[/red]"


@app.command()
def explain(
    ctx: typer.Context,
    sql: Annotated[str, typer.Argument(help="SQL query to explain")],
    database: Annotated[str, typer.Option("--db", "-d", help="Target database")] = "postgres",
    analyze_opt: Annotated[
        bool, typer.Option("--analyze", help="Actually execute the query (EXPLAIN ANALYZE)")
    ] = False,
    buffers: Annotated[bool, typer.Option("--buffers", help="Include buffer usage statistics")] = False,
) -> None:
    """Show query execution plan (EXPLAIN)."""
    actx: AppContext = ctx.obj
    out = actx.output

    c = actx.get_client(database=database)
    try:
        options: list[str] = ["FORMAT JSON"]
        if analyze_opt:
            options.append("ANALYZE")
        if buffers:
            options.append("BUFFERS")

        option_str = ", ".join(options)
        explain_sql = f"EXPLAIN ({option_str}) {sql}"

        out.info(f"Running: EXPLAIN ({option_str}) ...")
        rows = c.fetchall(explain_sql)

        if not rows:
            out.info("No plan returned")
            return

        # pg returns EXPLAIN (FORMAT JSON) as a list with one row containing
        # the plan as a JSON array in the first column
        import json as json_mod

        plan_data = rows[0]
        # The key name varies; get the first value
        plan_json = next(iter(plan_data.values()))

        if actx.output.json_mode:
            out.raw_json(plan_json)
            return

        # Pretty-print the JSON plan
        formatted = json_mod.dumps(plan_json, indent=2, default=str)
        out.header("Query Plan")
        out.text(formatted)

        # Extract and display summary if ANALYZE was used
        if analyze_opt and isinstance(plan_json, list) and len(plan_json) > 0:
            plan = plan_json[0]
            if "Planning Time" in plan:
                out.kv("Planning Time", f"{plan['Planning Time']} ms")
            if "Execution Time" in plan:
                out.kv("Execution Time", f"{plan['Execution Time']} ms")
    finally:
        c.close()


@app.command("temp-files")
def temp_files(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Filter by database")] = None,
) -> None:
    """Show temporary file usage per database."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    sql = """
        SELECT
            datname,
            temp_files,
            pg_size_pretty(temp_bytes) AS temp_size,
            temp_bytes,
            pg_size_pretty(pg_database_size(datname)) AS db_size
        FROM pg_stat_database
        WHERE datname NOT LIKE 'template%%'
    """
    params: list = []
    if database:
        sql += " AND datname = %s"
        params.append(database)
    sql += " ORDER BY temp_bytes DESC"

    rows_data = c.fetchall(sql, tuple(params) if params else None)

    if not rows_data:
        out.info("No databases found")
        return

    rows = [
        [
            r["datname"],
            str(r["temp_files"]),
            r["temp_size"],
            r["db_size"],
        ]
        for r in rows_data
    ]

    total_files = sum(r["temp_files"] for r in rows_data)
    total_bytes = sum(r["temp_bytes"] for r in rows_data)
    total_pretty = c.fetchval("SELECT pg_size_pretty(%s::bigint)", (total_bytes,))

    rows.append(
        [
            "[bold]TOTAL[/bold]",
            f"[bold]{total_files}[/bold]",
            f"[bold]{total_pretty}[/bold]",
            "",
        ]
    )

    out.table(
        "Temporary File Usage",
        [
            ("Database", "cyan"),
            ("Temp Files", "yellow"),
            ("Temp Size", "red"),
            ("DB Size", "green"),
        ],
        rows,
        data_for_json=[
            *rows_data,
            {"datname": "TOTAL", "temp_files": total_files, "temp_size": total_pretty, "temp_bytes": total_bytes},
        ],
    )

    if total_bytes > 1_073_741_824:  # 1 GB
        out.warn("High temporary file usage. Consider increasing work_mem.")


@app.command()
def progress(ctx: typer.Context) -> None:
    """Show progress of running maintenance operations (vacuum, analyze, create index, etc.)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    found_any = False

    # VACUUM progress (PG 9.6+)
    try:
        vacuum_data = c.fetchall("""
            SELECT
                a.pid,
                a.datname AS database,
                a.query,
                p.phase,
                p.heap_blks_total,
                p.heap_blks_scanned,
                p.heap_blks_vacuumed,
                CASE
                    WHEN p.heap_blks_total > 0
                    THEN round(100.0 * p.heap_blks_vacuumed / p.heap_blks_total, 1)
                    ELSE 0
                END AS pct_complete
            FROM pg_stat_progress_vacuum p
            JOIN pg_stat_activity a ON a.pid = p.pid
        """)
        if vacuum_data:
            found_any = True
            vac_rows = [
                [
                    str(r["pid"]),
                    r["database"],
                    r["phase"],
                    f"{r['pct_complete']}%",
                    str(r["heap_blks_total"]),
                    str(r["heap_blks_vacuumed"]),
                ]
                for r in vacuum_data
            ]
            out.table(
                f"VACUUM Progress ({len(vacuum_data)})",
                [
                    ("PID", ""),
                    ("Database", "cyan"),
                    ("Phase", ""),
                    ("Complete", "green"),
                    ("Total Blocks", "dim"),
                    ("Vacuumed", "dim"),
                ],
                vac_rows,
                data_for_json=vacuum_data,
            )
    except DatabaseError:
        pass

    # ANALYZE progress (PG 13+)
    try:
        analyze_data = c.fetchall("""
            SELECT
                a.pid,
                a.datname AS database,
                p.phase,
                p.sample_blks_total,
                p.sample_blks_scanned,
                CASE
                    WHEN p.sample_blks_total > 0
                    THEN round(100.0 * p.sample_blks_scanned / p.sample_blks_total, 1)
                    ELSE 0
                END AS pct_complete
            FROM pg_stat_progress_analyze p
            JOIN pg_stat_activity a ON a.pid = p.pid
        """)
        if analyze_data:
            found_any = True
            ana_rows = [[str(r["pid"]), r["database"], r["phase"], f"{r['pct_complete']}%"] for r in analyze_data]
            out.table(
                f"ANALYZE Progress ({len(analyze_data)})",
                [("PID", ""), ("Database", "cyan"), ("Phase", ""), ("Complete", "green")],
                ana_rows,
                data_for_json=analyze_data,
            )
    except DatabaseError:
        pass

    # CREATE INDEX progress (PG 12+)
    try:
        index_data = c.fetchall("""
            SELECT
                a.pid,
                a.datname AS database,
                p.phase,
                p.lockers_total,
                p.lockers_done,
                p.blocks_total,
                p.blocks_done,
                p.tuples_total,
                p.tuples_done,
                CASE
                    WHEN p.blocks_total > 0
                    THEN round(100.0 * p.blocks_done / p.blocks_total, 1)
                    ELSE 0
                END AS pct_complete
            FROM pg_stat_progress_create_index p
            JOIN pg_stat_activity a ON a.pid = p.pid
        """)
        if index_data:
            found_any = True
            idx_rows = [
                [
                    str(r["pid"]),
                    r["database"],
                    r["phase"],
                    f"{r['pct_complete']}%",
                    str(r["tuples_total"]),
                    str(r["tuples_done"]),
                ]
                for r in index_data
            ]
            out.table(
                f"CREATE INDEX Progress ({len(index_data)})",
                [
                    ("PID", ""),
                    ("Database", "cyan"),
                    ("Phase", ""),
                    ("Complete", "green"),
                    ("Tuples Total", "dim"),
                    ("Tuples Done", "dim"),
                ],
                idx_rows,
                data_for_json=index_data,
            )
    except DatabaseError:
        pass

    # CLUSTER progress (PG 12+)
    try:
        cluster_data = c.fetchall("""
            SELECT
                a.pid,
                a.datname AS database,
                p.phase,
                p.heap_blks_total,
                p.heap_blks_scanned,
                CASE
                    WHEN p.heap_blks_total > 0
                    THEN round(100.0 * p.heap_blks_scanned / p.heap_blks_total, 1)
                    ELSE 0
                END AS pct_complete
            FROM pg_stat_progress_cluster p
            JOIN pg_stat_activity a ON a.pid = p.pid
        """)
        if cluster_data:
            found_any = True
            cls_rows = [[str(r["pid"]), r["database"], r["phase"], f"{r['pct_complete']}%"] for r in cluster_data]
            out.table(
                f"CLUSTER Progress ({len(cluster_data)})",
                [("PID", ""), ("Database", "cyan"), ("Phase", ""), ("Complete", "green")],
                cls_rows,
                data_for_json=cluster_data,
            )
    except DatabaseError:
        pass

    # BASEBACKUP progress (PG 13+)
    try:
        backup_data = c.fetchall("""
            SELECT
                a.pid,
                p.phase,
                p.backup_total,
                p.backup_streamed,
                CASE
                    WHEN p.backup_total > 0
                    THEN round(100.0 * p.backup_streamed / p.backup_total, 1)
                    ELSE 0
                END AS pct_complete
            FROM pg_stat_progress_basebackup p
            JOIN pg_stat_activity a ON a.pid = p.pid
        """)
        if backup_data:
            found_any = True
            bak_rows = [
                [str(r["pid"]), r["phase"], f"{r['pct_complete']}%", str(r["backup_total"]), str(r["backup_streamed"])]
                for r in backup_data
            ]
            out.table(
                f"BASEBACKUP Progress ({len(backup_data)})",
                [("PID", ""), ("Phase", ""), ("Complete", "green"), ("Total Bytes", "dim"), ("Streamed", "dim")],
                bak_rows,
                data_for_json=backup_data,
            )
    except DatabaseError:
        pass

    # COPY progress (PG 14+)
    try:
        copy_data = c.fetchall("""
            SELECT
                a.pid,
                a.datname AS database,
                p.type,
                p.bytes_processed,
                p.bytes_total,
                p.tuples_processed,
                p.tuples_excluded,
                CASE
                    WHEN p.bytes_total > 0
                    THEN round(100.0 * p.bytes_processed / p.bytes_total, 1)
                    ELSE 0
                END AS pct_complete
            FROM pg_stat_progress_copy p
            JOIN pg_stat_activity a ON a.pid = p.pid
        """)
        if copy_data:
            found_any = True
            cp_rows = [
                [str(r["pid"]), r["database"], r["type"], f"{r['pct_complete']}%", str(r["tuples_processed"])]
                for r in copy_data
            ]
            out.table(
                f"COPY Progress ({len(copy_data)})",
                [("PID", ""), ("Database", "cyan"), ("Type", ""), ("Complete", "green"), ("Tuples", "")],
                cp_rows,
                data_for_json=copy_data,
            )
    except DatabaseError:
        pass

    if not found_any:
        out.success("No maintenance operations currently in progress")
