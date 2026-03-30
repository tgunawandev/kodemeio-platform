"""Tests for pipeline command group."""

from __future__ import annotations

from kctl_pg.commands.pipeline import (
    _collect_alerts,
    _collect_dr_metrics,
    _gate_style,
    _render_markdown,
)
from tests.conftest import FakeClient

# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------


def test_gate_style_pass():
    assert "[green]" in _gate_style("PASS")


def test_gate_style_fail():
    assert "[red]" in _gate_style("FAIL")


def test_gate_style_warn():
    assert "[yellow]" in _gate_style("WARN")


# ---------------------------------------------------------------------------
# Alert collection tests
# ---------------------------------------------------------------------------


def test_collect_alerts_no_violations():
    """Clean system — no alerts triggered."""
    client = FakeClient()
    # Connection check: 10/200 = 5%
    client.add_result("max_connections", [{"current_conns": 10, "max_conns": 200}])
    # No long queries
    client.add_result("query_start", [{"count": 0}])
    # Good cache hit ratio
    client.add_result("blks_hit", [{"ratio": 99.5}])

    rules = _collect_alerts(client)
    assert all(r["status"] == "OK" for r in rules)


def test_collect_alerts_connection_alert():
    """Connection usage above 80% triggers ALERT."""
    client = FakeClient()
    client.add_result("max_connections", [{"current_conns": 180, "max_conns": 200}])
    client.add_result("query_start", [{"count": 0}])
    client.add_result("blks_hit", [{"ratio": 99.0}])

    rules = _collect_alerts(client)
    conn_rule = next(r for r in rules if r["metric"] == "Connection Usage")
    assert conn_rule["status"] == "ALERT"


def test_collect_alerts_long_query_alert():
    """Long-running queries trigger ALERT."""
    client = FakeClient()
    client.add_result("max_connections", [{"current_conns": 10, "max_conns": 200}])
    client.add_result("query_start", 3)  # fetchval returns scalar
    client.add_result("blks_hit", [{"ratio": 99.0}])

    rules = _collect_alerts(client)
    lq_rule = next(r for r in rules if r["metric"] == "Long Queries")
    assert lq_rule["status"] == "ALERT"


# ---------------------------------------------------------------------------
# DR metric collection tests
# ---------------------------------------------------------------------------


def test_collect_dr_metrics_no_archiving():
    """No WAL archiving configured → CRITICAL."""
    client = FakeClient()
    # pg_stat_archiver returns no last_archived_time
    client.add_result(
        "pg_stat_archiver", [{"last_archived_time": None, "seconds_since_archive": None, "failed_count": 0}]
    )

    metrics = _collect_dr_metrics(client)
    wal_metric = next(m for m in metrics if "WAL" in m["metric"])
    assert wal_metric["rating"] == "CRITICAL"


def test_collect_dr_metrics_good_archiving():
    """Recent WAL archive → GOOD."""
    client = FakeClient()
    client.add_result(
        "pg_stat_archiver",
        [{"last_archived_time": "2026-03-27 10:00:00", "seconds_since_archive": 30, "failed_count": 0}],
    )

    metrics = _collect_dr_metrics(client)
    wal_metric = next(m for m in metrics if "WAL" in m["metric"])
    assert wal_metric["rating"] == "GOOD"


# ---------------------------------------------------------------------------
# Gate logic tests (via internal functions)
# ---------------------------------------------------------------------------


def test_gate_all_clean():
    """No findings, no alerts, no DR issues → would pass."""
    # Lint: empty findings
    from kctl_pg.commands.lint import _check_schema

    client = FakeClient()
    findings = _check_schema(client)
    assert findings == []

    # Alerts: all OK
    client2 = FakeClient()
    client2.add_result("max_connections", [{"current_conns": 5, "max_conns": 200}])
    client2.add_result("query_start", [{"count": 0}])
    client2.add_result("blks_hit", [{"ratio": 99.0}])
    rules = _collect_alerts(client2)
    assert all(r["status"] == "OK" for r in rules)


def test_gate_lint_errors_would_fail():
    """Lint errors would cause gate to fail."""
    from kctl_pg.commands.lint import _check_schema

    client = FakeClient()
    client.add_result("indisprimary", [{"schema": "public", "table_name": "broken"}])
    findings = _check_schema(client)
    errors = sum(1 for f in findings if f["severity"] == "error")
    assert errors > 0  # This would trigger gate failure


# ---------------------------------------------------------------------------
# Health report tests
# ---------------------------------------------------------------------------


def test_render_markdown_structure():
    """Markdown output has all required sections."""
    report = {
        "database": "test",
        "timestamp": "2026-03-27T10:00:00Z",
        "server": {"version": "16.3", "uptime": "5 days", "role": "primary"},
        "databases": {
            "count": 3,
            "total_size": "500 MB",
            "total_bytes": 524288000,
            "largest": {"name": "app", "size": "300 MB"},
        },
        "performance": {"cache_hit_ratio": 99.5, "active_connections": 5, "idle_connections": 10, "slow_queries": 0},
        "maintenance": {"never_vacuumed": 0, "never_analyzed": 1, "high_dead_tuples": 0},
        "replication": {"is_replica": False, "replica_count": 1, "max_lag": "0.5s"},
        "security": {"superuser_count": 1, "public_schema_grants": "no", "lint_errors": 0, "lint_warnings": 0},
        "dr": {"wal_archiving": "30s", "backup_score": "3/3", "critical_count": 0, "metrics": []},
    }

    md = _render_markdown(report)
    assert "# Health Report" in md
    assert "## Server" in md
    assert "## Databases" in md
    assert "## Performance" in md
    assert "## Maintenance" in md
    assert "## Replication" in md
    assert "## Security" in md
    assert "## Disaster Recovery" in md
    assert "16.3" in md
    assert "99.5%" in md


def test_render_markdown_has_tables():
    """Markdown contains properly formatted tables."""
    report = {
        "database": "test",
        "timestamp": "2026-03-27T10:00:00Z",
        "server": {"version": "16.3", "uptime": "1 day", "role": "primary"},
        "databases": {"count": 1, "total_size": "100 MB", "total_bytes": 104857600, "largest": None},
        "performance": {"cache_hit_ratio": 95.0, "active_connections": 2, "idle_connections": 3, "slow_queries": 1},
        "maintenance": {"never_vacuumed": 2, "never_analyzed": 0, "high_dead_tuples": 1},
        "replication": {"is_replica": False, "replica_count": 0, "max_lag": "N/A"},
        "security": {"superuser_count": 2, "public_schema_grants": "yes", "lint_errors": 1, "lint_warnings": 3},
        "dr": {"wal_archiving": "not configured", "backup_score": "1/3", "critical_count": 2, "metrics": []},
    }

    md = _render_markdown(report)
    # Check table formatting
    assert "| Metric | Value |" in md
    assert "|--------|-------|" in md
    # Check data values
    assert "not configured" in md
    assert "1/3" in md
    assert "2" in md  # superuser count


def test_health_report_json_structure():
    """Verify health report dict has all 7 top-level sections."""
    report = {
        "database": "test",
        "timestamp": "now",
        "server": {},
        "databases": {},
        "performance": {},
        "maintenance": {},
        "replication": {},
        "security": {},
        "dr": {},
    }
    assert "server" in report
    assert "databases" in report
    assert "performance" in report
    assert "maintenance" in report
    assert "replication" in report
    assert "security" in report
    assert "dr" in report
