"""Pipeline commands: gate, health-report — orchestrate multiple checks."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import typer

from kctl_pg.commands.lint import _check_indexes, _check_permissions, _check_schema
from kctl_pg.core.callbacks import AppContext

app = typer.Typer(help="Pipeline orchestration: quality gates, combined health reports.")


# ---------------------------------------------------------------------------
# pipeline gate
# ---------------------------------------------------------------------------


@app.command()
def gate(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
    strict: Annotated[bool, typer.Option("--strict", help="Fail on warnings too")] = False,
    min_scans: Annotated[int, typer.Option("--min-scans", help="Unused index threshold")] = 50,
) -> None:
    """Run quality gate: lint + alerts + DR checks. Exit 0/1 for CI."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    # --- Step 1: Lint checks ---
    c = actx.get_client(database=db)
    try:
        lint_findings: list[dict] = []
        lint_findings.extend(_check_schema(c))
        lint_findings.extend(_check_indexes(c, min_scans))
        lint_findings.extend(_check_permissions(c))
    finally:
        c.close()

    lint_errors = sum(1 for f in lint_findings if f["severity"] == "error")
    lint_warnings = sum(1 for f in lint_findings if f["severity"] == "warning")
    lint_info = sum(1 for f in lint_findings if f["severity"] == "info")

    lint_status = "FAIL" if lint_errors > 0 else ("WARN" if lint_warnings > 0 else "PASS")

    # --- Step 2: Alert checks ---
    c2 = actx.get_client(database="postgres")
    try:
        alert_rules = _collect_alerts(c2)
    finally:
        c2.close()

    alert_violations = [r for r in alert_rules if r["status"] == "ALERT"]
    alert_critical = len(alert_violations)
    alert_status = "FAIL" if alert_critical > 0 else "PASS"

    # --- Step 3: DR checks ---
    c3 = actx.get_client(database="postgres")
    try:
        dr_metrics = _collect_dr_metrics(c3)
    finally:
        c3.close()

    dr_critical = sum(1 for m in dr_metrics if m["rating"] == "CRITICAL")
    dr_warnings = sum(1 for m in dr_metrics if m["rating"] == "WARNING")
    dr_status = "FAIL" if dr_critical > 0 else ("WARN" if dr_warnings > 0 else "PASS")

    # --- Aggregate result ---
    gate_result = {
        "database": db,
        "timestamp": datetime.now(UTC).isoformat(),
        "lint": {
            "status": lint_status,
            "errors": lint_errors,
            "warnings": lint_warnings,
            "info": lint_info,
            "findings": lint_findings,
        },
        "alerts": {
            "status": alert_status,
            "violations": alert_critical,
            "total_rules": len(alert_rules),
            "rules": alert_rules,
        },
        "dr": {
            "status": dr_status,
            "critical": dr_critical,
            "warnings": dr_warnings,
            "metrics": dr_metrics,
        },
    }

    # Determine overall pass/fail
    has_errors = lint_errors > 0 or alert_critical > 0 or dr_critical > 0
    has_warnings = lint_warnings > 0 or dr_warnings > 0
    gate_pass = not has_errors and (not strict or not has_warnings)
    gate_result["overall"] = "PASS" if gate_pass else "FAIL"

    if actx.json_mode:
        out.raw_json(gate_result)
    else:
        rows = [
            [
                "Lint",
                _gate_style(lint_status),
                f"{lint_errors} errors, {lint_warnings} warnings, {lint_info} info",
            ],
            [
                "Alerts",
                _gate_style(alert_status),
                f"{alert_critical} violations / {len(alert_rules)} rules checked",
            ],
            [
                "DR/RPO-RTO",
                _gate_style(dr_status),
                f"{dr_critical} critical, {dr_warnings} warnings",
            ],
        ]

        title = f"Quality Gate — {db}"
        if strict:
            title += " (strict)"

        out.table(
            title,
            [
                ("Check", "cyan"),
                ("Status", ""),
                ("Details", ""),
            ],
            rows,
            data_for_json=gate_result,
        )

        if gate_pass:
            out.success("Gate PASSED")
        else:
            out.error("Gate FAILED")

    if not gate_pass:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# pipeline health-report
# ---------------------------------------------------------------------------


@app.command("report")
def health_report(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
    fmt: Annotated[str, typer.Option("--format", "-f", help="Output format: pretty, json, markdown")] = "pretty",
) -> None:
    """Comprehensive health report combining all checks."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    report = _build_health_report(actx, db)

    if fmt == "json" or actx.json_mode:
        out.raw_json(report)
        return

    if fmt == "markdown":
        md = _render_markdown(report)
        out.text(md)
        return

    # Pretty (default) — Rich panels
    sections: list[tuple[str, list[tuple[str, str]]]] = []

    sections.append(
        (
            "Server",
            [
                ("Version", report["server"]["version"]),
                ("Uptime", report["server"]["uptime"]),
                ("Role", report["server"]["role"]),
                ("Timestamp", report["timestamp"]),
            ],
        )
    )

    ov = report["databases"]
    sections.append(
        (
            "Databases",
            [
                ("Count", str(ov["count"])),
                ("Total Size", ov["total_size"]),
                ("Largest", f"{ov['largest']['name']} ({ov['largest']['size']})" if ov.get("largest") else "N/A"),
            ],
        )
    )

    perf = report["performance"]
    sections.append(
        (
            "Performance",
            [
                ("Cache Hit Ratio", f"{perf['cache_hit_ratio']}%"),
                ("Active Connections", str(perf["active_connections"])),
                ("Idle Connections", str(perf["idle_connections"])),
                ("Slow Queries (> 5m)", str(perf["slow_queries"])),
            ],
        )
    )

    maint = report["maintenance"]
    sections.append(
        (
            "Maintenance",
            [
                ("Tables Never Vacuumed", str(maint["never_vacuumed"])),
                ("Tables Never Analyzed", str(maint["never_analyzed"])),
                ("High Dead Tuples", str(maint["high_dead_tuples"])),
            ],
        )
    )

    repl = report["replication"]
    sections.append(
        (
            "Replication",
            [
                ("Is Primary", "yes" if not repl["is_replica"] else "no"),
                ("Replicas", str(repl["replica_count"])),
                ("Max Lag", repl["max_lag"]),
            ],
        )
    )

    sec = report["security"]
    sections.append(
        (
            "Security",
            [
                ("Superusers", str(sec["superuser_count"])),
                ("Public Schema Grants", sec["public_schema_grants"]),
                ("Lint Findings", f"{sec['lint_errors']} errors, {sec['lint_warnings']} warnings"),
            ],
        )
    )

    dr = report["dr"]
    sections.append(
        (
            "Disaster Recovery",
            [
                ("WAL Archiving", dr["wal_archiving"]),
                ("Backup Score (3-2-1)", dr["backup_score"]),
                ("Critical Issues", str(dr["critical_count"])),
            ],
        )
    )

    out.detail(f"Health Report — {db}", sections, data_for_json=report)


# ---------------------------------------------------------------------------
# Internal: collect alert metrics (reuses automation alert logic inline)
# ---------------------------------------------------------------------------


def _collect_alerts(c) -> list[dict]:
    """Collect alert metrics without rendering — returns list of rule dicts."""
    rules: list[dict] = []

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
                "current": f"{pct}%",
                "threshold": "> 80%",
                "status": "ALERT" if pct > 80 else "OK",
                "value": pct,
            }
        )

    rows = c.fetchall("""
        SELECT EXTRACT(EPOCH FROM replay_lag)::numeric AS lag_seconds
        FROM pg_stat_replication
    """)
    if rows:
        max_lag = max(float(r["lag_seconds"] or 0) for r in rows)
        rules.append(
            {
                "metric": "Replication Lag",
                "current": f"{max_lag:.1f}s",
                "threshold": "> 60s",
                "status": "ALERT" if max_lag > 60 else "OK",
                "value": max_lag,
            }
        )

    long_q = c.fetchval("""
        SELECT count(*) FROM pg_stat_activity
        WHERE state = 'active' AND backend_type = 'client backend'
          AND now() - query_start > interval '300 seconds'
    """)
    rules.append(
        {
            "metric": "Long Queries",
            "current": str(long_q or 0),
            "threshold": "> 0",
            "status": "ALERT" if (long_q or 0) > 0 else "OK",
            "value": long_q or 0,
        }
    )

    cache = c.fetchone("""
        SELECT round(100.0 * sum(blks_hit) / nullif(sum(blks_hit) + sum(blks_read), 0), 2) AS ratio
        FROM pg_stat_database WHERE datname NOT LIKE 'template%%'
    """)
    if cache and cache["ratio"] is not None:
        ratio = float(cache["ratio"])
        rules.append(
            {
                "metric": "Cache Hit Ratio",
                "current": f"{ratio}%",
                "threshold": "< 95%",
                "status": "ALERT" if ratio < 95 else "OK",
                "value": ratio,
            }
        )

    return rules


# ---------------------------------------------------------------------------
# Internal: collect DR metrics (reuses dr rpo-rto logic inline)
# ---------------------------------------------------------------------------


def _collect_dr_metrics(c) -> list[dict]:
    """Collect DR/RPO-RTO metrics without rendering."""
    from kctl_pg.commands.dr import _rpo_rating

    metrics: list[dict] = []

    archive = c.fetchone("""
        SELECT last_archived_time::text,
               EXTRACT(EPOCH FROM now() - last_archived_time) AS seconds_since_archive,
               failed_count
        FROM pg_stat_archiver
    """)
    if archive and archive["last_archived_time"]:
        secs = float(archive["seconds_since_archive"] or 0)
        metrics.append({"metric": "WAL Archive", "value": f"{secs:.0f}s", "rating": _rpo_rating(secs)})
    else:
        metrics.append({"metric": "WAL Archive", "value": "not configured", "rating": "CRITICAL"})

    replicas = c.fetchall("""
        SELECT EXTRACT(EPOCH FROM replay_lag)::numeric AS lag_seconds
        FROM pg_stat_replication
    """)
    if replicas:
        max_lag = max(float(r["lag_seconds"] or 0) for r in replicas)
        metrics.append({"metric": "Replication Lag", "value": f"{max_lag:.1f}s", "rating": _rpo_rating(max_lag)})
    else:
        metrics.append({"metric": "Replication", "value": "none", "rating": "WARNING"})

    size_row = c.fetchone("""
        SELECT sum(pg_database_size(datname)) AS total_bytes
        FROM pg_database WHERE datname NOT LIKE 'template%%'
    """)
    if size_row and size_row["total_bytes"]:
        from kctl_pg.commands.dr import _rto_rating

        est_secs = (size_row["total_bytes"] or 0) / (100 * 1024 * 1024)
        metrics.append({"metric": "Restore Time (est)", "value": f"{est_secs:.0f}s", "rating": _rto_rating(est_secs)})

    return metrics


# ---------------------------------------------------------------------------
# Internal: build full health report
# ---------------------------------------------------------------------------


def _build_health_report(actx: AppContext, db: str) -> dict:
    """Build comprehensive health report from multiple data sources."""
    c = actx.get_client(database=db)
    try:
        # Server info
        version = c.fetchval("SHOW server_version") or "unknown"
        uptime_row = c.fetchone("SELECT now() - pg_postmaster_start_time() AS uptime")
        uptime = str(uptime_row["uptime"]) if uptime_row else "unknown"
        is_replica = c.fetchval("SELECT pg_is_in_recovery()") or False

        # Database overview
        dbs = c.fetchall("""
            SELECT datname AS name,
                   pg_size_pretty(pg_database_size(datname)) AS size,
                   pg_database_size(datname) AS size_bytes
            FROM pg_database WHERE NOT datistemplate ORDER BY pg_database_size(datname) DESC
        """)
        total_bytes = sum(d["size_bytes"] for d in dbs) if dbs else 0

        # Performance
        cache = c.fetchone("""
            SELECT round(100.0 * sum(blks_hit) / nullif(sum(blks_hit) + sum(blks_read), 0), 2) AS ratio
            FROM pg_stat_database WHERE datname NOT LIKE 'template%%'
        """)
        conns = c.fetchone("""
            SELECT
                count(*) FILTER (WHERE state = 'active') AS active,
                count(*) FILTER (WHERE state = 'idle') AS idle,
                count(*) FILTER (WHERE state = 'active' AND now() - query_start > interval '5 minutes') AS slow
            FROM pg_stat_activity WHERE backend_type = 'client backend'
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

        # Replication
        replicas = (
            c.fetchall("""
            SELECT EXTRACT(EPOCH FROM replay_lag)::numeric AS lag_seconds
            FROM pg_stat_replication
        """)
            if not is_replica
            else []
        )
        max_lag_val = max((float(r["lag_seconds"] or 0) for r in replicas), default=0) if replicas else 0

        # Security (lint permissions)
        perm_findings = _check_permissions(c)
        superusers = (
            c.fetchval("""
            SELECT count(*) FROM pg_roles WHERE rolsuper = true AND rolcanlogin = true
        """)
            or 0
        )
        public_row = c.fetchone("""
            SELECT has_schema_privilege('public', 'public', 'CREATE') AS can_create
        """)
        public_grants = "yes" if (public_row and public_row["can_create"]) else "no"

        # DR
        dr_metrics = _collect_dr_metrics(c)
    finally:
        c.close()

    from kctl_pg.commands.dr import _pretty_bytes

    return {
        "database": db,
        "timestamp": datetime.now(UTC).isoformat(),
        "server": {
            "version": version,
            "uptime": uptime,
            "role": "standby" if is_replica else "primary",
        },
        "databases": {
            "count": len(dbs),
            "total_size": _pretty_bytes(total_bytes),
            "total_bytes": total_bytes,
            "largest": {"name": dbs[0]["name"], "size": dbs[0]["size"]} if dbs else None,
        },
        "performance": {
            "cache_hit_ratio": float(cache["ratio"]) if cache and cache["ratio"] else 0,
            "active_connections": conns["active"] if conns else 0,
            "idle_connections": conns["idle"] if conns else 0,
            "slow_queries": conns["slow"] if conns else 0,
        },
        "maintenance": {
            "never_vacuumed": maint.get("never_vacuumed", 0),
            "never_analyzed": maint.get("never_analyzed", 0),
            "high_dead_tuples": maint.get("high_dead_tuples", 0),
        },
        "replication": {
            "is_replica": is_replica,
            "replica_count": len(replicas),
            "max_lag": f"{max_lag_val:.1f}s" if replicas else "N/A",
        },
        "security": {
            "superuser_count": superusers,
            "public_schema_grants": public_grants,
            "lint_errors": sum(1 for f in perm_findings if f["severity"] == "error"),
            "lint_warnings": sum(1 for f in perm_findings if f["severity"] == "warning"),
        },
        "dr": {
            "wal_archiving": next((m["value"] for m in dr_metrics if "WAL" in m["metric"]), "unknown"),
            "backup_score": f"{sum(1 for m in dr_metrics if m['rating'] in ('GOOD', 'PASS')) + 1}/3",
            "critical_count": sum(1 for m in dr_metrics if m["rating"] == "CRITICAL"),
            "metrics": dr_metrics,
        },
    }


# ---------------------------------------------------------------------------
# Internal: markdown renderer
# ---------------------------------------------------------------------------


def _render_markdown(report: dict) -> str:
    """Render health report as Markdown."""
    lines: list[str] = []
    lines.append(f"# Health Report — {report['database']}")
    lines.append(f"*Generated: {report['timestamp']}*\n")

    srv = report["server"]
    lines.append("## Server")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Version | {srv['version']} |")
    lines.append(f"| Uptime | {srv['uptime']} |")
    lines.append(f"| Role | {srv['role']} |")
    lines.append("")

    dbs = report["databases"]
    lines.append("## Databases")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Count | {dbs['count']} |")
    lines.append(f"| Total Size | {dbs['total_size']} |")
    if dbs.get("largest"):
        lines.append(f"| Largest | {dbs['largest']['name']} ({dbs['largest']['size']}) |")
    lines.append("")

    perf = report["performance"]
    lines.append("## Performance")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Cache Hit Ratio | {perf['cache_hit_ratio']}% |")
    lines.append(f"| Active Connections | {perf['active_connections']} |")
    lines.append(f"| Idle Connections | {perf['idle_connections']} |")
    lines.append(f"| Slow Queries (> 5m) | {perf['slow_queries']} |")
    lines.append("")

    maint = report["maintenance"]
    lines.append("## Maintenance")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Never Vacuumed | {maint['never_vacuumed']} |")
    lines.append(f"| Never Analyzed | {maint['never_analyzed']} |")
    lines.append(f"| High Dead Tuples | {maint['high_dead_tuples']} |")
    lines.append("")

    repl = report["replication"]
    lines.append("## Replication")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Is Primary | {'no' if repl['is_replica'] else 'yes'} |")
    lines.append(f"| Replicas | {repl['replica_count']} |")
    lines.append(f"| Max Lag | {repl['max_lag']} |")
    lines.append("")

    sec = report["security"]
    lines.append("## Security")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Superusers | {sec['superuser_count']} |")
    lines.append(f"| Public Schema Grants | {sec['public_schema_grants']} |")
    lines.append(f"| Lint Findings | {sec['lint_errors']} errors, {sec['lint_warnings']} warnings |")
    lines.append("")

    dr = report["dr"]
    lines.append("## Disaster Recovery")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| WAL Archiving | {dr['wal_archiving']} |")
    lines.append(f"| Backup Score | {dr['backup_score']} |")
    lines.append(f"| Critical Issues | {dr['critical_count']} |")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _gate_style(status: str) -> str:
    if status == "PASS":
        return "[green]PASS[/green]"
    if status == "FAIL":
        return "[red]FAIL[/red]"
    return f"[yellow]{status}[/yellow]"
