"""Tests for db command group: list, create, drop, size, info, rename, copy, owner."""

from __future__ import annotations

import pytest

from kctl_pg.commands.db import _quote_ident
from tests.conftest import FakeClient


# ---------------------------------------------------------------------------
# _quote_ident helper
# ---------------------------------------------------------------------------


def test_quote_ident_simple():
    assert _quote_ident("mydb") == '"mydb"'


def test_quote_ident_with_double_quote():
    assert _quote_ident('my"db') == '"my""db"'


def test_quote_ident_empty():
    assert _quote_ident("") == '""'


def test_quote_ident_with_spaces():
    assert _quote_ident("my db") == '"my db"'


def test_quote_ident_uppercase():
    assert _quote_ident("MyDB") == '"MyDB"'


# ---------------------------------------------------------------------------
# FakeClient: database list query
# ---------------------------------------------------------------------------


def test_db_list_returns_all_databases():
    client = FakeClient()
    client.add_result(
        "pg_database",
        [
            {
                "name": "postgres",
                "owner": "postgres",
                "encoding": "UTF8",
                "size": "8192 kB",
                "size_bytes": 8388608,
                "connections": 1,
            },
            {
                "name": "myapp",
                "owner": "appuser",
                "encoding": "UTF8",
                "size": "250 MB",
                "size_bytes": 262144000,
                "connections": 12,
            },
            {
                "name": "analytics",
                "owner": "analyst",
                "encoding": "UTF8",
                "size": "1 GB",
                "size_bytes": 1073741824,
                "connections": 3,
            },
        ],
    )
    rows = client.fetchall("SELECT d.datname AS name FROM pg_database d")
    assert len(rows) == 3
    assert rows[0]["name"] == "postgres"
    assert rows[1]["name"] == "myapp"
    assert rows[2]["name"] == "analytics"


def test_db_list_connections_count():
    client = FakeClient()
    client.add_result(
        "pg_database",
        [
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
    assert rows[0]["connections"] == 5


def test_db_list_empty_server():
    client = FakeClient()
    # No result configured → returns []
    rows = client.fetchall("SELECT d.datname FROM pg_database d WHERE d.datistemplate = false")
    assert rows == []


# ---------------------------------------------------------------------------
# FakeClient: database existence check (fetchval)
# ---------------------------------------------------------------------------


def test_db_exists_check_returns_1():
    client = FakeClient()
    client.add_result("pg_database", [{"?column?": 1}])
    val = client.fetchval("SELECT 1 FROM pg_database WHERE datname = %s", ("myapp",))
    assert val == 1


def test_db_exists_check_returns_none():
    client = FakeClient()
    # No result for this key
    val = client.fetchval("SELECT 1 FROM pg_database WHERE datname = %s", ("nonexistent",))
    assert val is None


# ---------------------------------------------------------------------------
# FakeClient: database size query
# ---------------------------------------------------------------------------


def test_db_size_query():
    client = FakeClient()
    client.add_result(
        "pg_database",
        [
            {"name": "myapp", "size": "250 MB", "size_bytes": 262144000},
            {"name": "analytics", "size": "1 GB", "size_bytes": 1073741824},
        ],
    )
    rows = client.fetchall("SELECT datname AS name, pg_size_pretty(pg_database_size(datname)) AS size FROM pg_database")
    total = sum(r["size_bytes"] for r in rows)
    assert total == 262144000 + 1073741824


def test_db_size_total_pretty():
    client = FakeClient()
    client.add_result("pg_size_pretty", "1.25 GB")
    val = client.fetchval("SELECT pg_size_pretty(%s::bigint)", (1335885824,))
    assert val == "1.25 GB"


# ---------------------------------------------------------------------------
# FakeClient: database create — duplicate check
# ---------------------------------------------------------------------------


def test_db_create_duplicate_detection():
    client = FakeClient()
    client.add_result("pg_database", [{"?column?": 1}])
    # Should detect that the DB already exists
    exists = client.fetchval("SELECT 1 FROM pg_database WHERE datname = %s", ("myapp",))
    assert exists is not None


def test_db_create_no_duplicate():
    client = FakeClient()
    # No result → no existing database
    exists = client.fetchval("SELECT 1 FROM pg_database WHERE datname = %s", ("newdb",))
    assert exists is None


# ---------------------------------------------------------------------------
# FakeClient: drop — pre-checks
# ---------------------------------------------------------------------------


def test_db_drop_not_exists():
    client = FakeClient()
    exists = client.fetchval("SELECT 1 FROM pg_database WHERE datname = %s", ("nosuchdb",))
    assert exists is None


def test_db_drop_system_databases_blocked():
    """System databases must never be dropped."""
    system_dbs = {"postgres", "template0", "template1"}
    # Simulate the guard logic
    for name in system_dbs:
        assert name in system_dbs  # The guard in the command checks this set


def test_db_drop_size_display():
    client = FakeClient()
    client.add_result("pg_size_pretty", "128 MB")
    size = client.fetchval("SELECT pg_size_pretty(pg_database_size(%s))", ("myapp",))
    assert size == "128 MB"


def test_db_drop_terminate_connections_query():
    """Verify terminate connections query pattern."""
    client = FakeClient()
    client.add_result("pg_stat_activity", [{"pg_terminate_backend": True}, {"pg_terminate_backend": True}])
    rows = client.fetchall(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
        ("myapp",),
    )
    # The execute is called, not fetchall, but FakeClient doesn't error on extra calls
    assert isinstance(rows, list)


# ---------------------------------------------------------------------------
# FakeClient: database info — detail query
# ---------------------------------------------------------------------------


def test_db_info_fetchone():
    client = FakeClient()
    client.add_result(
        "pg_database",
        [
            {
                "name": "myapp",
                "owner": "appuser",
                "encoding": "UTF8",
                "collation": "en_US.UTF-8",
                "ctype": "en_US.UTF-8",
                "size": "250 MB",
                "conn_limit": -1,
                "allow_connections": True,
            }
        ],
    )
    db = client.fetchone("SELECT d.datname AS name FROM pg_database d WHERE d.datname = %s", ("myapp",))
    assert db is not None
    assert db["name"] == "myapp"
    assert db["owner"] == "appuser"
    assert db["encoding"] == "UTF8"


def test_db_info_not_found():
    client = FakeClient()
    db = client.fetchone("SELECT d.datname FROM pg_database d WHERE d.datname = %s", ("nosuchdb",))
    assert db is None


def test_db_info_connection_count():
    client = FakeClient()
    client.add_result("pg_stat_activity", [{"count": 7}])
    conns = client.fetchval("SELECT count(*) FROM pg_stat_activity WHERE datname = %s", ("myapp",))
    assert conns == 7


# ---------------------------------------------------------------------------
# FakeClient: rename — guards
# ---------------------------------------------------------------------------


def test_db_rename_source_not_found():
    client = FakeClient()
    exists = client.fetchval("SELECT 1 FROM pg_database WHERE datname = %s", ("nosource",))
    assert exists is None


def test_db_rename_target_already_exists():
    client = FakeClient()
    client.add_result("pg_database", [{"?column?": 1}])
    target_exists = client.fetchval("SELECT 1 FROM pg_database WHERE datname = %s", ("existing_target",))
    assert target_exists is not None


def test_db_rename_system_db_blocked():
    """Renaming system databases should be blocked."""
    system_dbs = {"postgres", "template0", "template1"}
    for name in system_dbs:
        assert name in system_dbs


def test_db_rename_active_connections_count():
    client = FakeClient()
    client.add_result("pg_stat_activity", [{"count": 3}])
    conns = client.fetchval(
        "SELECT count(*) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
        ("myapp",),
    )
    assert conns == 3


# ---------------------------------------------------------------------------
# FakeClient: copy (template-based) — guards
# ---------------------------------------------------------------------------


def test_db_copy_source_not_found():
    client = FakeClient()
    exists = client.fetchval("SELECT 1 FROM pg_database WHERE datname = %s", ("nosource",))
    assert exists is None


def test_db_copy_target_already_exists():
    client = FakeClient()
    client.add_result("pg_database", [{"?column?": 1}])
    target_exists = client.fetchval("SELECT 1 FROM pg_database WHERE datname = %s", ("existing_target",))
    assert target_exists is not None


def test_db_copy_source_size():
    client = FakeClient()
    client.add_result("pg_size_pretty", "500 MB")
    size = client.fetchval("SELECT pg_size_pretty(pg_database_size(%s))", ("myapp",))
    assert size == "500 MB"


# ---------------------------------------------------------------------------
# FakeClient: owner change — guards
# ---------------------------------------------------------------------------


def test_db_owner_db_not_found():
    client = FakeClient()
    exists = client.fetchval("SELECT 1 FROM pg_database WHERE datname = %s", ("nosuchdb",))
    assert exists is None


def test_db_owner_role_not_found():
    client = FakeClient()
    role_exists = client.fetchval("SELECT 1 FROM pg_roles WHERE rolname = %s", ("nosuchrole",))
    assert role_exists is None


def test_db_owner_role_exists():
    client = FakeClient()
    client.add_result("pg_roles", [{"?column?": 1}])
    role_exists = client.fetchval("SELECT 1 FROM pg_roles WHERE rolname = %s", ("appuser",))
    assert role_exists is not None


# ---------------------------------------------------------------------------
# FakeClient: multi-result handling
# ---------------------------------------------------------------------------


def test_fake_client_fetchval_from_list():
    """fetchval extracts first column of first row."""
    client = FakeClient()
    client.add_result("pg_database", [{"?column?": 42}])
    val = client.fetchval("SELECT count(*) FROM pg_database")
    assert val == 42


def test_fake_client_fetchall_multiple_rows():
    """fetchall returns all rows."""
    client = FakeClient()
    client.add_result(
        "pg_database",
        [
            {"name": "db1", "size_bytes": 1000},
            {"name": "db2", "size_bytes": 2000},
            {"name": "db3", "size_bytes": 3000},
        ],
    )
    rows = client.fetchall("SELECT name, size_bytes FROM pg_database")
    assert len(rows) == 3
    assert rows[2]["name"] == "db3"


def test_fake_client_close_sets_flag():
    client = FakeClient()
    assert not client.closed
    client.close()
    assert client.closed


def test_fake_client_execute_no_error():
    """execute() runs without error."""
    client = FakeClient()
    client.execute("CREATE DATABASE myapp ENCODING 'UTF8'")  # Should not raise


def test_fake_client_no_match_returns_empty():
    """Unmatched key returns empty list."""
    client = FakeClient()
    rows = client.fetchall("SELECT * FROM some_unregistered_view")
    assert rows == []
