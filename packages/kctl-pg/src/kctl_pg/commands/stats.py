"""PostgreSQL statistics views commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_pg.core.callbacks import AppContext

app = typer.Typer(help="PostgreSQL statistics views (tables, indexes, WAL, I/O).")


@app.command()
def tables(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Database name (default: current)")] = None,
) -> None:
    """Show table statistics from pg_stat_user_tables."""
    actx: AppContext = ctx.obj
    if database:
        c = actx.get_client(database)
    else:
        c = actx.client
    out = actx.output

    rows_data = c.fetchall("""
        SELECT
            schemaname,
            relname AS table_name,
            seq_scan,
            seq_tup_read,
            idx_scan,
            idx_tup_fetch,
            n_tup_ins,
            n_tup_upd,
            n_tup_del,
            n_live_tup,
            n_dead_tup,
            last_vacuum::text,
            last_autovacuum::text,
            last_analyze::text,
            last_autoanalyze::text
        FROM pg_stat_user_tables
        ORDER BY n_live_tup DESC
        LIMIT 50
    """)

    rows = [
        [
            f"{r['schemaname']}.{r['table_name']}",
            f"{r['n_live_tup']:,}",
            f"{r['n_dead_tup']:,}",
            f"{r['seq_scan']:,}",
            f"{r['idx_scan'] or 0:,}",
            f"{r['n_tup_ins']:,}",
            f"{r['n_tup_upd']:,}",
            f"{r['n_tup_del']:,}",
            (r["last_autovacuum"] or r["last_vacuum"] or "-")[:19],
        ]
        for r in rows_data
    ]

    out.table(
        f"Table Statistics ({len(rows_data)})",
        [
            ("Table", "cyan"),
            ("Live Rows", ""),
            ("Dead Rows", "yellow"),
            ("Seq Scans", ""),
            ("Idx Scans", ""),
            ("Inserts", "dim"),
            ("Updates", "dim"),
            ("Deletes", "dim"),
            ("Last Vacuum", ""),
        ],
        rows,
        data_for_json=rows_data,
    )

    if database:
        c.close()


@app.command()
def indexes(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Database name (default: current)")] = None,
) -> None:
    """Show index statistics from pg_stat_user_indexes."""
    actx: AppContext = ctx.obj
    if database:
        c = actx.get_client(database)
    else:
        c = actx.client
    out = actx.output

    rows_data = c.fetchall("""
        SELECT
            schemaname,
            relname AS table_name,
            indexrelname AS index_name,
            idx_scan,
            idx_tup_read,
            idx_tup_fetch,
            pg_size_pretty(pg_relation_size(indexrelid::regclass)) AS index_size
        FROM pg_stat_user_indexes
        ORDER BY idx_scan DESC
        LIMIT 50
    """)

    rows = [
        [
            f"{r['schemaname']}.{r['table_name']}",
            r["index_name"],
            f"{r['idx_scan']:,}",
            f"{r['idx_tup_read']:,}",
            f"{r['idx_tup_fetch']:,}",
            r["index_size"],
        ]
        for r in rows_data
    ]

    out.table(
        f"Index Statistics ({len(rows_data)})",
        [
            ("Table", "cyan"),
            ("Index", ""),
            ("Scans", ""),
            ("Tuples Read", ""),
            ("Tuples Fetched", ""),
            ("Size", "dim"),
        ],
        rows,
        data_for_json=rows_data,
    )

    if database:
        c.close()


@app.command()
def bgwriter(ctx: typer.Context) -> None:
    """Show background writer statistics."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    row = c.fetchone("""
        SELECT
            checkpoints_timed,
            checkpoints_req,
            checkpoint_write_time,
            checkpoint_sync_time,
            buffers_checkpoint,
            buffers_clean,
            maxwritten_clean,
            buffers_backend,
            buffers_backend_fsync,
            buffers_alloc,
            stats_reset::text
        FROM pg_stat_bgwriter
    """)

    if not row:
        out.error("Could not fetch bgwriter stats")
        raise typer.Exit(1)

    sections = [
        (
            "Checkpoints",
            [
                ("Timed", f"{row['checkpoints_timed']:,}"),
                ("Requested", f"{row['checkpoints_req']:,}"),
                ("Write Time (ms)", f"{row['checkpoint_write_time']:,.0f}"),
                ("Sync Time (ms)", f"{row['checkpoint_sync_time']:,.0f}"),
            ],
        ),
        (
            "Buffers",
            [
                ("Checkpoint", f"{row['buffers_checkpoint']:,}"),
                ("Clean", f"{row['buffers_clean']:,}"),
                ("Backend", f"{row['buffers_backend']:,}"),
                ("Backend Fsync", f"{row['buffers_backend_fsync']:,}"),
                ("Allocated", f"{row['buffers_alloc']:,}"),
                ("Max Written Clean", f"{row['maxwritten_clean']:,}"),
            ],
        ),
        (
            "Stats Reset",
            [
                ("Reset At", row["stats_reset"] or "never"),
            ],
        ),
    ]

    out.detail("Background Writer Stats", sections, data_for_json=row)


@app.command()
def replication(ctx: typer.Context) -> None:
    """Show replication status from pg_stat_replication."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    rows_data = c.fetchall("""
        SELECT
            pid,
            usename,
            application_name,
            client_addr::text,
            state,
            sent_lsn::text,
            write_lsn::text,
            flush_lsn::text,
            replay_lsn::text,
            sync_state,
            reply_time::text
        FROM pg_stat_replication
        ORDER BY application_name
    """)

    if not rows_data:
        out.info("No active replication connections")
        return

    rows = [
        [
            str(r["pid"]),
            r["usename"] or "-",
            r["application_name"] or "-",
            r["client_addr"] or "-",
            r["state"] or "-",
            r["sent_lsn"] or "-",
            r["replay_lsn"] or "-",
            r["sync_state"] or "-",
        ]
        for r in rows_data
    ]

    out.table(
        f"Replication ({len(rows_data)})",
        [
            ("PID", ""),
            ("User", ""),
            ("App", "cyan"),
            ("Client", ""),
            ("State", "green"),
            ("Sent LSN", "dim"),
            ("Replay LSN", "dim"),
            ("Sync", ""),
        ],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def wal(ctx: typer.Context) -> None:
    """Show WAL statistics (PostgreSQL 14+)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Check version
    version = c.short_version
    major = int(version.split(".")[0]) if version and version[0].isdigit() else 0

    if major < 14:
        out.error(f"pg_stat_wal requires PostgreSQL 14+ (current: {version})")
        raise typer.Exit(1)

    row = c.fetchone("""
        SELECT
            wal_records,
            wal_fpi,
            wal_bytes,
            wal_buffers_full,
            wal_write,
            wal_sync,
            wal_write_time,
            wal_sync_time,
            stats_reset::text
        FROM pg_stat_wal
    """)

    if not row:
        out.error("Could not fetch WAL stats")
        raise typer.Exit(1)

    def _fmt_bytes(b: int) -> str:
        if b >= 1_073_741_824:
            return f"{b / 1_073_741_824:.2f} GB"
        if b >= 1_048_576:
            return f"{b / 1_048_576:.2f} MB"
        return f"{b:,} B"

    sections = [
        (
            "WAL Activity",
            [
                ("Records", f"{row['wal_records']:,}"),
                ("Full Page Images", f"{row['wal_fpi']:,}"),
                ("Bytes Written", _fmt_bytes(row["wal_bytes"])),
                ("Buffers Full", f"{row['wal_buffers_full']:,}"),
            ],
        ),
        (
            "I/O",
            [
                ("Write Ops", f"{row['wal_write']:,}"),
                ("Sync Ops", f"{row['wal_sync']:,}"),
                ("Write Time (ms)", f"{row['wal_write_time']:,.0f}"),
                ("Sync Time (ms)", f"{row['wal_sync_time']:,.0f}"),
            ],
        ),
        (
            "Stats Reset",
            [
                ("Reset At", row["stats_reset"] or "never"),
            ],
        ),
    ]

    out.detail("WAL Statistics", sections, data_for_json=row)


@app.command()
def io(ctx: typer.Context) -> None:
    """Show I/O statistics (PostgreSQL 16+)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    version = c.short_version
    major = int(version.split(".")[0]) if version and version[0].isdigit() else 0

    if major < 16:
        out.error(f"pg_stat_io requires PostgreSQL 16+ (current: {version})")
        raise typer.Exit(1)

    rows_data = c.fetchall("""
        SELECT
            backend_type,
            object,
            context,
            reads,
            read_time,
            writes,
            write_time,
            writebacks,
            writeback_time,
            extends,
            hits,
            evictions,
            reuses,
            fsyncs,
            fsync_time,
            stats_reset::text
        FROM pg_stat_io
        WHERE reads > 0 OR writes > 0 OR hits > 0
        ORDER BY reads + writes + hits DESC
        LIMIT 30
    """)

    if not rows_data:
        out.info("No I/O statistics available")
        return

    rows = [
        [
            r["backend_type"],
            r["object"],
            r["context"],
            f"{r['reads'] or 0:,}",
            f"{r['hits'] or 0:,}",
            f"{r['writes'] or 0:,}",
            f"{r['evictions'] or 0:,}",
            f"{r['fsyncs'] or 0:,}",
        ]
        for r in rows_data
    ]

    out.table(
        f"I/O Statistics ({len(rows_data)})",
        [
            ("Backend", "cyan"),
            ("Object", ""),
            ("Context", ""),
            ("Reads", ""),
            ("Hits", "green"),
            ("Writes", ""),
            ("Evictions", "yellow"),
            ("Fsyncs", "dim"),
        ],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def database(
    ctx: typer.Context,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Specific database name")] = None,
) -> None:
    """Show database-level statistics from pg_stat_database."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    sql = """
        SELECT
            datname,
            numbackends,
            xact_commit,
            xact_rollback,
            blks_read,
            blks_hit,
            tup_returned,
            tup_fetched,
            tup_inserted,
            tup_updated,
            tup_deleted,
            conflicts,
            temp_files,
            temp_bytes,
            deadlocks,
            pg_size_pretty(pg_database_size(datname)) AS db_size,
            stats_reset::text
        FROM pg_stat_database
        WHERE datname IS NOT NULL
    """
    params: list = []

    if name:
        sql += " AND datname = %s"
        params.append(name)
    else:
        sql += " AND datname NOT IN ('template0', 'template1')"

    sql += " ORDER BY pg_database_size(datname) DESC"

    rows_data = c.fetchall(sql, tuple(params) if params else None)

    if not rows_data:
        out.info("No database stats found")
        return

    # For a single database, show detailed view
    if name and len(rows_data) == 1:
        r = rows_data[0]
        total_blocks = r["blks_read"] + r["blks_hit"]
        cache_rate = f"{(r['blks_hit'] / total_blocks * 100):.1f}%" if total_blocks else "N/A"

        sections = [
            (
                "Database",
                [
                    ("Name", r["datname"]),
                    ("Size", r["db_size"]),
                    ("Connections", str(r["numbackends"])),
                ],
            ),
            (
                "Transactions",
                [
                    ("Commits", f"{r['xact_commit']:,}"),
                    ("Rollbacks", f"{r['xact_rollback']:,}"),
                    ("Deadlocks", f"{r['deadlocks']:,}"),
                    ("Conflicts", f"{r['conflicts']:,}"),
                ],
            ),
            (
                "Cache",
                [
                    ("Blocks Read", f"{r['blks_read']:,}"),
                    ("Blocks Hit", f"{r['blks_hit']:,}"),
                    ("Cache Hit Rate", cache_rate),
                ],
            ),
            (
                "Tuples",
                [
                    ("Returned", f"{r['tup_returned']:,}"),
                    ("Fetched", f"{r['tup_fetched']:,}"),
                    ("Inserted", f"{r['tup_inserted']:,}"),
                    ("Updated", f"{r['tup_updated']:,}"),
                    ("Deleted", f"{r['tup_deleted']:,}"),
                ],
            ),
            (
                "Temp",
                [
                    ("Temp Files", f"{r['temp_files']:,}"),
                    ("Temp Bytes", f"{r['temp_bytes']:,}"),
                ],
            ),
            (
                "Stats Reset",
                [
                    ("Reset At", r["stats_reset"] or "never"),
                ],
            ),
        ]
        out.detail(f"Database Stats: {name}", sections, data_for_json=r)
    else:
        rows = [
            [
                r["datname"],
                r["db_size"],
                str(r["numbackends"]),
                f"{r['xact_commit']:,}",
                f"{r['xact_rollback']:,}",
                f"{r['blks_hit'] / max(r['blks_read'] + r['blks_hit'], 1) * 100:.1f}%",
                f"{r['deadlocks']:,}",
                f"{r['tup_inserted']:,}",
            ]
            for r in rows_data
        ]

        out.table(
            f"Database Statistics ({len(rows_data)})",
            [
                ("Database", "cyan"),
                ("Size", ""),
                ("Conns", ""),
                ("Commits", ""),
                ("Rollbacks", "yellow"),
                ("Cache Hit", "green"),
                ("Deadlocks", "red"),
                ("Inserts", "dim"),
            ],
            rows,
            data_for_json=rows_data,
        )
