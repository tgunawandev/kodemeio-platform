"""Automation commands: maintenance-plan, alert-rules, report, baseline."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import typer

from kctl_pg.core.callbacks import AppContext

app = typer.Typer(help="Automation: maintenance plans, alerts, reports, baselines.")


# ---------------------------------------------------------------------------
# automation maintenance-plan
# ---------------------------------------------------------------------------


@app.command("plan")
def maintenance_plan(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
) -> None:
    """Generate recommended vacuum/analyze/reindex schedule based on table stats."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    c = actx.get_client(database=db)
    try:
        rows_data = c.fetchall("""
            SELECT
                n.nspname || '.' || c.relname AS table_name,
                pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
                pg_total_relation_size(c.oid) AS total_bytes,
                s.n_live_tup AS live_tuples,
                s.n_dead_tup AS dead_tuples,
                CASE WHEN s.n_live_tup > 0
                    THEN round(100.0 * s.n_dead_tup / s.n_live_tup, 1)
                    ELSE 0 END AS dead_pct,
                s.last_vacuum::text,
                s.last_autovacuum::text,
                s.last_analyze::text,
                s.last_autoanalyze::text,
                s.n_mod_since_analyze AS mods_since_analyze,
                s.n_ins_since_vacuum AS inserts_since_vacuum,
                (SELECT count(*) FROM pg_index i WHERE i.indrelid = c.oid) AS index_count,
                COALESCE(
                    (SELECT sum(pg_relation_size(i.indexrelid))
                     FROM pg_index i WHERE i.indrelid = c.oid), 0
                ) AS total_index_bytes
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
            WHERE c.relkind = 'r'
              AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast', 'audit')
              AND pg_total_relation_size(c.oid) > 65536
            ORDER BY pg_total_relation_size(c.oid) DESC
        """)
    finally:
        c.close()

    if not rows_data:
        out.info(f"No user tables found in '{db}'")
        return

    recommendations: list[dict] = []
    for r in rows_data:
        actions: list[str] = []
        schedule = "monthly"

        dead_pct = float(r["dead_pct"] or 0)
        mods = r["mods_since_analyze"] or 0
        inserts = r["inserts_since_vacuum"] or 0
        total_bytes = r["total_bytes"] or 0
        live = r["live_tuples"] or 0

        # Vacuum urgency
        if dead_pct > 20:
            actions.append("VACUUM (urgent: dead tuples > 20%)")
            schedule = "daily"
        elif dead_pct > 10:
            actions.append("VACUUM")
            schedule = "daily"
        elif inserts > max(live * 0.2, 1000):
            actions.append("VACUUM")
            schedule = "weekly"

        # Analyze urgency
        if mods > max(live * 0.1, 500):
            actions.append("ANALYZE (stats stale)")
            if schedule == "monthly":
                schedule = "weekly"

        # Reindex suggestion for large tables
        if total_bytes > 1073741824 and r["index_count"] and r["index_count"] > 0:  # > 1GB
            idx_ratio = (r["total_index_bytes"] or 0) / max(total_bytes, 1)
            if idx_ratio > 0.5:
                actions.append("REINDEX CONCURRENTLY (index bloat likely)")
                if schedule == "monthly":
                    schedule = "weekly"

        if not actions:
            actions.append("OK — no immediate action needed")

        recommendations.append(
            {
                "table": r["table_name"],
                "size": r["total_size"],
                "live_tuples": live,
                "dead_pct": dead_pct,
                "mods_since_analyze": mods,
                "recommended_actions": actions,
                "schedule": schedule,
            }
        )

    rows = [
        [
            rec["table"],
            rec["size"],
            f"{rec['live_tuples']:,}",
            _dead_style(rec["dead_pct"]),
            f"{rec['mods_since_analyze']:,}",
            "; ".join(rec["recommended_actions"]),
            _schedule_style(rec["schedule"]),
        ]
        for rec in recommendations
    ]

    out.table(
        f"Maintenance Plan — {db} ({len(recommendations)} tables)",
        [
            ("Table", "cyan"),
            ("Size", "green"),
            ("Live Tuples", ""),
            ("Dead %", ""),
            ("Mods Since Analyze", ""),
            ("Recommended Actions", ""),
            ("Schedule", ""),
        ],
        rows,
        data_for_json=recommendations,
    )


# ---------------------------------------------------------------------------
# automation alert-rules
# ---------------------------------------------------------------------------


@app.command("alerts")
def alert_rules(ctx: typer.Context) -> None:
    """Show current metric values against recommended alert thresholds."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    rules: list[dict] = []

    # 1. Connection usage %
    row = c.fetchone("""
        SELECT
            (SELECT count(*) FROM pg_stat_activity WHERE backend_type = 'client backend') AS current_conns,
            (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') AS max_conns
    """)
    if row:
        pct = round(100.0 * row["current_conns"] / max(row["max_conns"], 1), 1)
        rules.append(
            {
                "metric": "Connection Usage",
                "current": f"{row['current_conns']}/{row['max_conns']} ({pct}%)",
                "threshold": "> 80%",
                "status": "ALERT" if pct > 80 else "OK",
                "value": pct,
            }
        )

    # 2. Replication lag
    rows = c.fetchall("""
        SELECT
            client_addr::text,
            application_name,
            EXTRACT(EPOCH FROM replay_lag)::numeric AS lag_seconds
        FROM pg_stat_replication
    """)
    if rows:
        max_lag = max(float(r["lag_seconds"] or 0) for r in rows)
        rules.append(
            {
                "metric": "Replication Lag (max)",
                "current": f"{max_lag:.1f}s",
                "threshold": "> 60s",
                "status": "ALERT" if max_lag > 60 else "OK",
                "value": max_lag,
            }
        )
    else:
        rules.append(
            {
                "metric": "Replication Lag",
                "current": "no replicas",
                "threshold": "> 60s",
                "status": "N/A",
                "value": 0,
            }
        )

    # 3. Long-running queries
    long_q = c.fetchval("""
        SELECT count(*)
        FROM pg_stat_activity
        WHERE state = 'active'
          AND backend_type = 'client backend'
          AND now() - query_start > interval '300 seconds'
    """)
    rules.append(
        {
            "metric": "Long Queries (> 5m)",
            "current": str(long_q or 0),
            "threshold": "> 0",
            "status": "ALERT" if (long_q or 0) > 0 else "OK",
            "value": long_q or 0,
        }
    )

    # 4. Database size / disk usage
    row = c.fetchone("""
        SELECT
            pg_size_pretty(sum(pg_database_size(datname))) AS total_size,
            sum(pg_database_size(datname)) AS total_bytes
        FROM pg_database
        WHERE datname NOT LIKE 'template%%'
    """)
    if row:
        rules.append(
            {
                "metric": "Total Database Size",
                "current": row["total_size"],
                "threshold": "monitor growth",
                "status": "INFO",
                "value": row["total_bytes"],
            }
        )

    # 5. Cache hit ratio
    cache_row = c.fetchone("""
        SELECT
            round(
                100.0 * sum(blks_hit) / nullif(sum(blks_hit) + sum(blks_read), 0)
            , 2) AS cache_hit_ratio
        FROM pg_stat_database
        WHERE datname NOT LIKE 'template%%'
    """)
    if cache_row and cache_row["cache_hit_ratio"] is not None:
        ratio = float(cache_row["cache_hit_ratio"])
        rules.append(
            {
                "metric": "Cache Hit Ratio",
                "current": f"{ratio}%",
                "threshold": "< 95%",
                "status": "ALERT" if ratio < 95 else "OK",
                "value": ratio,
            }
        )

    # 6. Dead tuples ratio
    dead_row = c.fetchone("""
        SELECT
            sum(n_dead_tup) AS total_dead,
            sum(n_live_tup) AS total_live,
            CASE WHEN sum(n_live_tup) > 0
                THEN round(100.0 * sum(n_dead_tup) / sum(n_live_tup), 2)
                ELSE 0 END AS dead_ratio
        FROM pg_stat_user_tables
    """)
    if dead_row and dead_row["total_live"]:
        ratio = float(dead_row["dead_ratio"] or 0)
        rules.append(
            {
                "metric": "Dead Tuple Ratio",
                "current": f"{ratio}% ({dead_row['total_dead']:,} dead / {dead_row['total_live']:,} live)",
                "threshold": "> 10%",
                "status": "ALERT" if ratio > 10 else "OK",
                "value": ratio,
            }
        )

    rows = [
        [
            r["metric"],
            r["current"],
            r["threshold"],
            _alert_style(r["status"]),
        ]
        for r in rules
    ]

    out.table(
        f"Alert Rules ({sum(1 for r in rules if r['status'] == 'ALERT')} active alerts)",
        [
            ("Metric", "cyan"),
            ("Current Value", ""),
            ("Threshold", "dim"),
            ("Status", ""),
        ],
        rows,
        data_for_json=rules,
    )


# ---------------------------------------------------------------------------
# automation report
# ---------------------------------------------------------------------------


@app.command()
def report(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
    period: Annotated[str, typer.Option("--period", help="Report period: daily, weekly, monthly")] = "weekly",
) -> None:
    """Generate a health report: sizes, slow queries, connections, maintenance."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    c = actx.get_client(database=db)
    try:
        report_data = _build_report(c, db, period)
    finally:
        c.close()

    if actx.json_mode:
        out.raw_json(report_data)
        return

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    # Overview
    ov = report_data["overview"]
    sections.append(
        (
            "Overview",
            [
                ("Database", db),
                ("Period", period),
                ("Generated", report_data["generated_at"]),
                ("Database Size", ov["database_size"]),
                ("Total Tables", str(ov["table_count"])),
                ("Total Indexes", str(ov["index_count"])),
            ],
        )
    )

    # Connection stats
    cs = report_data["connections"]
    sections.append(
        (
            "Connections",
            [
                ("Current", f"{cs['current']}/{cs['max']}"),
                ("Usage", f"{cs['usage_pct']}%"),
                ("Idle", str(cs["idle"])),
                ("Active", str(cs["active"])),
                ("Idle in Transaction", str(cs["idle_in_transaction"])),
            ],
        )
    )

    # Top tables by size
    if report_data["top_tables"]:
        sections.append(
            ("Top Tables by Size", [(t["table_name"], t["total_size"]) for t in report_data["top_tables"][:10]])
        )

    # Maintenance status
    maint = report_data["maintenance"]
    sections.append(
        (
            "Maintenance",
            [
                ("Tables Never Vacuumed", str(maint["never_vacuumed"])),
                ("Tables Never Analyzed", str(maint["never_analyzed"])),
                ("High Dead Tuple Tables", str(maint["high_dead_tuples"])),
            ],
        )
    )

    # Slow queries
    sq = report_data["slow_queries"]
    sections.append(
        (
            "Slow Queries",
            [
                ("Currently Running > 1s", str(sq["running_slow"])),
                ("Currently Running > 5m", str(sq["running_very_slow"])),
            ],
        )
    )

    out.detail(f"Health Report — {db} ({period})", sections, data_for_json=report_data)


def _build_report(c, db: str, period: str) -> dict:
    # Overview
    overview = (
        c.fetchone("""
        SELECT
            pg_size_pretty(pg_database_size(current_database())) AS database_size,
            pg_database_size(current_database()) AS database_bytes,
            (SELECT count(*) FROM pg_stat_user_tables) AS table_count,
            (SELECT count(*) FROM pg_stat_user_indexes) AS index_count
    """)
        or {}
    )

    # Connections
    conns = (
        c.fetchone("""
        SELECT
            (SELECT count(*) FROM pg_stat_activity WHERE backend_type = 'client backend') AS current,
            (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') AS max,
            (SELECT count(*) FROM pg_stat_activity WHERE state = 'idle') AS idle,
            (SELECT count(*) FROM pg_stat_activity WHERE state = 'active') AS active,
            (SELECT count(*) FROM pg_stat_activity WHERE state = 'idle in transaction') AS idle_in_transaction
    """)
        or {}
    )
    conns["usage_pct"] = round(100.0 * (conns.get("current", 0) or 0) / max(conns.get("max", 1) or 1, 1), 1)

    # Top tables
    top_tables = c.fetchall("""
        SELECT
            schemaname || '.' || relname AS table_name,
            pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
            pg_total_relation_size(relid) AS total_bytes,
            n_live_tup AS live_tuples,
            n_dead_tup AS dead_tuples
        FROM pg_stat_user_tables
        ORDER BY pg_total_relation_size(relid) DESC
        LIMIT 10
    """)

    # Maintenance
    maint = (
        c.fetchone("""
        SELECT
            (SELECT count(*) FROM pg_stat_user_tables WHERE last_vacuum IS NULL AND last_autovacuum IS NULL) AS never_vacuumed,
            (SELECT count(*) FROM pg_stat_user_tables WHERE last_analyze IS NULL AND last_autoanalyze IS NULL) AS never_analyzed,
            (SELECT count(*) FROM pg_stat_user_tables
             WHERE n_live_tup > 0 AND round(100.0 * n_dead_tup / n_live_tup, 1) > 10) AS high_dead_tuples
    """)
        or {}
    )

    # Slow queries
    slow = (
        c.fetchone("""
        SELECT
            (SELECT count(*) FROM pg_stat_activity
             WHERE state = 'active' AND backend_type = 'client backend'
               AND now() - query_start > interval '1 second') AS running_slow,
            (SELECT count(*) FROM pg_stat_activity
             WHERE state = 'active' AND backend_type = 'client backend'
               AND now() - query_start > interval '5 minutes') AS running_very_slow
    """)
        or {}
    )

    return {
        "database": db,
        "period": period,
        "generated_at": datetime.now(UTC).isoformat(),
        "overview": overview,
        "connections": conns,
        "top_tables": top_tables,
        "maintenance": maint,
        "slow_queries": slow,
    }


# ---------------------------------------------------------------------------
# automation baseline
# ---------------------------------------------------------------------------


@app.command()
def baseline(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
) -> None:
    """Capture current performance baseline for future comparison."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    c = actx.get_client(database=db)
    try:
        baseline_data = _capture_baseline(c, db)
    finally:
        c.close()

    if actx.json_mode:
        out.raw_json(baseline_data)
        return

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    sections.append(
        (
            "Baseline Info",
            [
                ("Database", db),
                ("Captured At", baseline_data["captured_at"]),
                ("PostgreSQL Version", baseline_data["pg_version"]),
            ],
        )
    )

    perf = baseline_data["performance"]
    sections.append(
        (
            "Performance Metrics",
            [
                ("Cache Hit Ratio", f"{perf['cache_hit_ratio']}%"),
                ("Index Hit Ratio", f"{perf['index_hit_ratio']}%"),
                ("Transactions/s (commits)", str(perf["xact_commit"])),
                ("Transactions/s (rollbacks)", str(perf["xact_rollback"])),
                ("Temp Files Created", str(perf["temp_files"])),
                ("Temp Bytes Written", perf["temp_bytes_pretty"]),
                ("Deadlocks", str(perf["deadlocks"])),
                ("Conflicts", str(perf["conflicts"])),
            ],
        )
    )

    sizes = baseline_data["sizes"]
    sections.append(
        (
            "Database Sizes",
            [
                ("Database Size", sizes["database_size"]),
                ("Total Table Size", sizes["table_size"]),
                ("Total Index Size", sizes["index_size"]),
                ("Index/Table Ratio", f"{sizes['index_ratio']}%"),
            ],
        )
    )

    tbl = baseline_data["table_stats"]
    sections.append(
        (
            "Table Statistics",
            [
                ("Total Tables", str(tbl["total_tables"])),
                ("Total Live Tuples", f"{tbl['total_live_tuples']:,}"),
                ("Total Dead Tuples", f"{tbl['total_dead_tuples']:,}"),
                ("Dead Tuple Ratio", f"{tbl['dead_ratio']}%"),
            ],
        )
    )

    out.detail("Performance Baseline", sections, data_for_json=baseline_data)
    out.info("Save --json output to compare against future baselines")


def _capture_baseline(c, db: str) -> dict:
    version = c.fetchval("SELECT version()")

    perf = (
        c.fetchone("""
        SELECT
            round(100.0 * sum(blks_hit) / nullif(sum(blks_hit) + sum(blks_read), 0), 2) AS cache_hit_ratio,
            sum(xact_commit) AS xact_commit,
            sum(xact_rollback) AS xact_rollback,
            sum(temp_files) AS temp_files,
            sum(temp_bytes) AS temp_bytes,
            pg_size_pretty(sum(temp_bytes)) AS temp_bytes_pretty,
            sum(deadlocks) AS deadlocks,
            sum(conflicts) AS conflicts
        FROM pg_stat_database
        WHERE datname = current_database()
    """)
        or {}
    )

    idx_hit = c.fetchval("""
        SELECT round(100.0 * sum(idx_blks_hit) / nullif(sum(idx_blks_hit) + sum(idx_blks_read), 0), 2)
        FROM pg_statio_user_indexes
    """)
    perf["index_hit_ratio"] = idx_hit or 0

    sizes = (
        c.fetchone("""
        SELECT
            pg_size_pretty(pg_database_size(current_database())) AS database_size,
            pg_database_size(current_database()) AS database_bytes,
            pg_size_pretty(sum(pg_total_relation_size(relid))
                FILTER (WHERE schemaname NOT IN ('pg_catalog', 'information_schema'))) AS table_size,
            sum(pg_total_relation_size(relid))
                FILTER (WHERE schemaname NOT IN ('pg_catalog', 'information_schema')) AS table_bytes,
            pg_size_pretty(sum(pg_indexes_size(relid))
                FILTER (WHERE schemaname NOT IN ('pg_catalog', 'information_schema'))) AS index_size,
            sum(pg_indexes_size(relid))
                FILTER (WHERE schemaname NOT IN ('pg_catalog', 'information_schema')) AS index_bytes
        FROM pg_stat_user_tables
    """)
        or {}
    )
    tbl_bytes = sizes.get("table_bytes") or 1
    idx_bytes = sizes.get("index_bytes") or 0
    sizes["index_ratio"] = round(100.0 * idx_bytes / max(tbl_bytes, 1), 1)

    tbl_stats = (
        c.fetchone("""
        SELECT
            count(*) AS total_tables,
            coalesce(sum(n_live_tup), 0) AS total_live_tuples,
            coalesce(sum(n_dead_tup), 0) AS total_dead_tuples,
            CASE WHEN sum(n_live_tup) > 0
                THEN round(100.0 * sum(n_dead_tup) / sum(n_live_tup), 2)
                ELSE 0 END AS dead_ratio
        FROM pg_stat_user_tables
    """)
        or {}
    )

    return {
        "database": db,
        "captured_at": datetime.now(UTC).isoformat(),
        "pg_version": version,
        "performance": perf,
        "sizes": sizes,
        "table_stats": tbl_stats,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dead_style(pct: float) -> str:
    if pct >= 20:
        return f"[red]{pct}%[/red]"
    if pct >= 10:
        return f"[yellow]{pct}%[/yellow]"
    return f"[green]{pct}%[/green]"


def _schedule_style(schedule: str) -> str:
    if schedule == "daily":
        return f"[red]{schedule}[/red]"
    if schedule == "weekly":
        return f"[yellow]{schedule}[/yellow]"
    return f"[green]{schedule}[/green]"


def _alert_style(status: str) -> str:
    if status == "ALERT":
        return f"[red]{status}[/red]"
    if status == "OK":
        return f"[green]{status}[/green]"
    return f"[dim]{status}[/dim]"
