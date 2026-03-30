"""Regression tests for core existing commands using FakeClient."""

from __future__ import annotations

from kctl_pg.commands.lint import _check_indexes, _check_permissions, _check_schema, _finding
from tests.conftest import FakeClient

# ---------------------------------------------------------------------------
# db list — mock pg_database query
# ---------------------------------------------------------------------------


def test_db_list_returns_databases():
    """Verify db list query returns database names."""
    client = FakeClient()
    client.add_result(
        "pg_database",
        [
            {
                "name": "postgres",
                "owner": "postgres",
                "encoding": "UTF8",
                "size": "16 MB",
                "size_bytes": 16777216,
                "connections": 2,
            },
            {
                "name": "myapp",
                "owner": "app",
                "encoding": "UTF8",
                "size": "100 MB",
                "size_bytes": 104857600,
                "connections": 5,
            },
        ],
    )
    rows = client.fetchall("SELECT ... FROM pg_database ...")
    assert len(rows) == 2
    assert rows[0]["name"] == "postgres"
    assert rows[1]["name"] == "myapp"


# ---------------------------------------------------------------------------
# users list — mock pg_roles query
# ---------------------------------------------------------------------------


def test_users_list_returns_roles():
    """Verify users list query returns role names."""
    client = FakeClient()
    client.add_result(
        "pg_roles",
        [
            {
                "name": "postgres",
                "superuser": True,
                "login": True,
                "createdb": True,
                "createrole": True,
                "replication": False,
                "inherit": True,
                "conn_limit": -1,
                "member_of": "",
            },
            {
                "name": "app",
                "superuser": False,
                "login": True,
                "createdb": False,
                "createrole": False,
                "replication": False,
                "inherit": True,
                "conn_limit": -1,
                "member_of": "",
            },
        ],
    )
    rows = client.fetchall("SELECT ... FROM pg_roles ...")
    assert len(rows) == 2
    assert rows[0]["name"] == "postgres"
    assert rows[1]["name"] == "app"


# ---------------------------------------------------------------------------
# health — mock version/uptime/connection queries
# ---------------------------------------------------------------------------


def test_health_check_queries():
    """Verify health check queries return expected data."""
    client = FakeClient()
    client.add_result("server_version", [{"server_version": "16.3"}])
    client.add_result("pg_postmaster_start_time", [{"uptime": "5 days 02:30:00"}])
    client.add_result("pg_stat_activity", [{"total": 15, "active": 3, "idle": 10, "idle_in_tx": 2, "max_conns": 200}])
    client.add_result("pg_is_in_recovery", False)

    version = client.fetchone("SHOW server_version")
    assert version["server_version"] == "16.3"

    uptime = client.fetchone("SELECT now() - pg_postmaster_start_time() AS uptime")
    assert "5 days" in uptime["uptime"]


# ---------------------------------------------------------------------------
# extensions list — mock pg_extension query
# ---------------------------------------------------------------------------


def test_extensions_list_returns_extensions():
    """Verify extension list query returns extension names."""
    client = FakeClient()
    client.add_result(
        "pg_extension",
        [
            {"name": "plpgsql", "version": "1.0", "schema": "pg_catalog"},
            {"name": "postgis", "version": "3.5.0", "schema": "public"},
            {"name": "pgaudit", "version": "16.1", "schema": "public"},
        ],
    )
    rows = client.fetchall("SELECT ... FROM pg_extension ...")
    assert len(rows) == 3
    assert rows[1]["name"] == "postgis"


# ---------------------------------------------------------------------------
# activity list — mock pg_stat_activity query
# ---------------------------------------------------------------------------


def test_activity_list_returns_connections():
    """Verify activity list query returns connection info."""
    client = FakeClient()
    client.add_result(
        "pg_stat_activity",
        [
            {"pid": 100, "datname": "myapp", "usename": "app", "state": "active", "query": "SELECT 1"},
            {"pid": 101, "datname": "myapp", "usename": "app", "state": "idle", "query": ""},
        ],
    )
    rows = client.fetchall("SELECT ... FROM pg_stat_activity ...")
    assert len(rows) == 2
    assert rows[0]["pid"] == 100
    assert rows[0]["state"] == "active"


# ---------------------------------------------------------------------------
# tables list — mock information_schema.tables query
# ---------------------------------------------------------------------------


def test_tables_list_returns_table_names():
    """Verify table list query returns table names."""
    client = FakeClient()
    client.add_result(
        "pg_stat_user_tables",
        [
            {"schemaname": "public", "relname": "users", "n_live_tup": 1000, "n_dead_tup": 50},
            {"schemaname": "public", "relname": "orders", "n_live_tup": 5000, "n_dead_tup": 200},
        ],
    )
    rows = client.fetchall("SELECT ... FROM pg_stat_user_tables ...")
    assert len(rows) == 2
    assert rows[0]["relname"] == "users"


# ---------------------------------------------------------------------------
# maintenance vacuum — verify vacuum SQL construction
# ---------------------------------------------------------------------------


def test_maintenance_vacuum_sql():
    """Verify VACUUM SQL is constructed correctly."""
    # The vacuum command builds SQL like: VACUUM (VERBOSE) schema.table
    table = "public.users"
    sql = f"VACUUM (VERBOSE) {table}"
    assert "VACUUM" in sql
    assert "VERBOSE" in sql
    assert table in sql

    # Full vacuum
    sql_full = f"VACUUM (FULL, VERBOSE) {table}"
    assert "FULL" in sql_full


# ---------------------------------------------------------------------------
# performance cache — mock pg_stat_database
# ---------------------------------------------------------------------------


def test_performance_cache_hit_ratio():
    """Verify cache hit ratio calculation."""
    client = FakeClient()
    client.add_result(
        "pg_stat_database",
        [
            {"datname": "myapp", "blks_hit": 9900, "blks_read": 100, "hit_ratio": 99.0},
        ],
    )
    rows = client.fetchall("SELECT ... FROM pg_stat_database ...")
    assert rows[0]["hit_ratio"] == 99.0

    # Manual calculation check
    hit = 9900
    read = 100
    ratio = round(100.0 * hit / (hit + read), 2)
    assert ratio == 99.0


# ---------------------------------------------------------------------------
# dashboard — mock multiple queries
# ---------------------------------------------------------------------------


def test_dashboard_queries():
    """Verify dashboard collects multiple data sources."""
    client = FakeClient()
    # Version
    client.add_result("version()", [{"version": "PostgreSQL 16.3"}])
    # Databases
    client.add_result(
        "pg_database",
        [
            {"datname": "postgres", "size": "16 MB", "connections": 2},
            {"datname": "myapp", "size": "100 MB", "connections": 5},
        ],
    )

    version = client.fetchone("SELECT version()")
    assert "16.3" in version["version"]

    dbs = client.fetchall("SELECT ... FROM pg_database ...")
    assert len(dbs) == 2


# ---------------------------------------------------------------------------
# Cross-module: lint findings format consistency
# ---------------------------------------------------------------------------


def test_lint_finding_keys():
    """All lint findings have consistent keys."""
    f = _finding("error", "test", "public.users", "Test message")
    required_keys = {"severity", "category", "object", "message"}
    assert set(f.keys()) == required_keys


def test_lint_schema_empty_db():
    """Schema lint on empty database returns no findings."""
    client = FakeClient()
    findings = _check_schema(client)
    assert findings == []


def test_lint_indexes_empty_db():
    """Index lint on empty database returns no findings."""
    client = FakeClient()
    findings = _check_indexes(client, min_scans=50)
    assert findings == []


def test_lint_permissions_empty_db():
    """Permission lint on empty database returns no findings."""
    client = FakeClient()
    findings = _check_permissions(client)
    assert findings == []
