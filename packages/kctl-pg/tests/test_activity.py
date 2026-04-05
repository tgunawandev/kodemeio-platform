"""Tests for activity command group: list, kill, locks."""

from __future__ import annotations

from tests.conftest import FakeClient


# ---------------------------------------------------------------------------
# FakeClient: activity list query
# ---------------------------------------------------------------------------


def test_activity_list_returns_connections():
    client = FakeClient()
    client.add_result(
        "pg_stat_activity",
        [
            {
                "pid": 100,
                "database": "myapp",
                "user": "appuser",
                "client_addr": "10.0.0.5",
                "state": "active",
                "backend_age": None,
                "query_duration": None,
                "query": "SELECT * FROM orders LIMIT 100",
            },
            {
                "pid": 101,
                "database": "myapp",
                "user": "appuser",
                "client_addr": "10.0.0.5",
                "state": "idle",
                "backend_age": None,
                "query_duration": None,
                "query": "",
            },
        ],
    )
    rows = client.fetchall(
        "SELECT pid, datname AS database FROM pg_stat_activity WHERE backend_type = 'client backend'"
    )
    assert len(rows) == 2
    assert rows[0]["pid"] == 100
    assert rows[0]["state"] == "active"
    assert rows[1]["state"] == "idle"


def test_activity_list_empty():
    client = FakeClient()
    rows = client.fetchall("SELECT pid FROM pg_stat_activity WHERE backend_type = 'client backend'")
    assert rows == []


def test_activity_list_filtered_by_database():
    client = FakeClient()
    client.add_result(
        "pg_stat_activity",
        [
            {"pid": 200, "database": "myapp", "user": "appuser", "state": "active", "query": "SELECT 1"},
        ],
    )
    rows = client.fetchall(
        "SELECT pid FROM pg_stat_activity WHERE backend_type = 'client backend' AND datname = %s",
        ("myapp",),
    )
    assert len(rows) == 1
    assert rows[0]["pid"] == 200


def test_activity_list_filtered_by_state():
    client = FakeClient()
    client.add_result(
        "pg_stat_activity",
        [
            {"pid": 300, "database": "myapp", "user": "appuser", "state": "active", "query": "SELECT now()"},
        ],
    )
    rows = client.fetchall(
        "SELECT pid FROM pg_stat_activity WHERE backend_type = 'client backend' AND state = %s",
        ("active",),
    )
    assert len(rows) == 1
    assert rows[0]["state"] == "active"


# ---------------------------------------------------------------------------
# Activity list: row rendering helpers
# ---------------------------------------------------------------------------


def test_activity_pid_as_string():
    """PIDs should be converted to strings for display."""
    pid = 12345
    assert str(pid) == "12345"


def test_activity_client_addr_none_becomes_dash():
    client_addr = None
    display = str(client_addr) if client_addr else "-"
    assert display == "-"


def test_activity_client_addr_present():
    client_addr = "192.168.1.10"
    display = str(client_addr) if client_addr else "-"
    assert display == "192.168.1.10"


def test_activity_state_none_becomes_dash():
    state = None
    display = state or "-"
    assert display == "-"


def test_activity_query_none_becomes_dash():
    query = None
    display = query[:60] if query else "-"
    assert display == "-"


def test_activity_query_truncation():
    query = "SELECT " + "x" * 100
    display = query[:60] if query else "-"
    assert len(display) == 60


def test_activity_query_duration_split():
    """Duration is trimmed to seconds."""
    query_duration = "0:01:23.456789"
    display = str(query_duration).split(".")[0] if query_duration else "-"
    assert display == "0:01:23"


def test_activity_query_duration_none():
    query_duration = None
    display = str(query_duration).split(".")[0] if query_duration else "-"
    assert display == "-"


# ---------------------------------------------------------------------------
# FakeClient: kill — pg_cancel_backend / pg_terminate_backend
# ---------------------------------------------------------------------------


def test_activity_kill_cancel_success():
    client = FakeClient()
    client.add_result("pg_cancel_backend", True)
    result = client.fetchval("SELECT pg_cancel_backend(%s)", (12345,))
    assert result is True


def test_activity_kill_cancel_failure():
    client = FakeClient()
    client.add_result("pg_cancel_backend", False)
    result = client.fetchval("SELECT pg_cancel_backend(%s)", (99999,))
    assert result is False


def test_activity_kill_terminate_success():
    client = FakeClient()
    client.add_result("pg_terminate_backend", True)
    result = client.fetchval("SELECT pg_terminate_backend(%s)", (12345,))
    assert result is True


def test_activity_kill_terminate_failure():
    client = FakeClient()
    client.add_result("pg_terminate_backend", False)
    result = client.fetchval("SELECT pg_terminate_backend(%s)", (99999,))
    assert result is False


def test_activity_kill_action_label():
    """Verify action label based on force flag."""
    force = False
    action = "Terminated" if force else "Cancelled"
    assert action == "Cancelled"

    force = True
    action = "Terminated" if force else "Cancelled"
    assert action == "Terminated"


# ---------------------------------------------------------------------------
# FakeClient: locks — lock contention detection
# ---------------------------------------------------------------------------


def test_activity_locks_no_contention():
    client = FakeClient()
    rows = client.fetchall(
        "SELECT blocked.pid AS blocked_pid FROM pg_catalog.pg_locks blocked WHERE NOT blocked.granted"
    )
    assert rows == []


def test_activity_locks_with_contention():
    client = FakeClient()
    client.add_result(
        "pg_locks",
        [
            {
                "blocked_pid": 400,
                "blocked_user": "appuser",
                "blocked_query": "UPDATE orders SET status = 'done' WHERE id = 1",
                "blocking_pid": 399,
                "blocking_user": "worker",
                "blocking_query": "BEGIN",
                "database": "myapp",
            }
        ],
    )
    rows = client.fetchall(
        "SELECT blocked.pid AS blocked_pid FROM pg_catalog.pg_locks blocked WHERE NOT blocked.granted"
    )
    assert len(rows) == 1
    assert rows[0]["blocked_pid"] == 400
    assert rows[0]["blocking_pid"] == 399


def test_activity_locks_filtered_by_database():
    """Locks are filtered in Python after fetchall."""
    all_rows = [
        {
            "blocked_pid": 100,
            "database": "db1",
            "blocked_user": "u1",
            "blocking_pid": 99,
            "blocking_user": "u2",
            "blocked_query": "",
            "blocking_query": "",
        },
        {
            "blocked_pid": 200,
            "database": "db2",
            "blocked_user": "u3",
            "blocking_pid": 199,
            "blocking_user": "u4",
            "blocked_query": "",
            "blocking_query": "",
        },
    ]
    # Filter in Python as the command does
    filtered = [r for r in all_rows if r["database"] == "db1"]
    assert len(filtered) == 1
    assert filtered[0]["blocked_pid"] == 100


def test_activity_locks_blocked_query_truncation():
    blocked_query = "UPDATE " + "x" * 200
    display = (blocked_query or "-")[:50]
    assert len(display) == 50


def test_activity_locks_blocking_query_none():
    blocking_query = None
    display = (blocking_query or "-")[:50]
    assert display == "-"


def test_activity_locks_no_database_filter():
    """When database is None, no filtering is applied."""
    all_rows = [
        {"blocked_pid": 100, "database": "db1"},
        {"blocked_pid": 200, "database": "db2"},
    ]
    database = None
    if database:
        filtered = [r for r in all_rows if r["database"] == database]
    else:
        filtered = all_rows
    assert len(filtered) == 2


# ---------------------------------------------------------------------------
# Multiple-connection scenarios
# ---------------------------------------------------------------------------


def test_activity_list_multiple_databases():
    client = FakeClient()
    client.add_result(
        "pg_stat_activity",
        [
            {"pid": 10, "database": "db1", "user": "u1", "state": "active", "query": "SELECT 1"},
            {"pid": 11, "database": "db2", "user": "u2", "state": "idle", "query": ""},
            {"pid": 12, "database": "db1", "user": "u3", "state": "active", "query": "SELECT 2"},
        ],
    )
    rows = client.fetchall("SELECT pid FROM pg_stat_activity WHERE backend_type = 'client backend'")
    active_conns = [r for r in rows if r["state"] == "active"]
    assert len(active_conns) == 2


def test_activity_list_idle_in_transaction():
    client = FakeClient()
    client.add_result(
        "pg_stat_activity",
        [
            {"pid": 500, "database": "myapp", "user": "appuser", "state": "idle in transaction", "query": "SELECT 1"},
        ],
    )
    rows = client.fetchall(
        "SELECT pid FROM pg_stat_activity WHERE backend_type = 'client backend' AND state = %s",
        ("idle in transaction",),
    )
    assert len(rows) == 1
    assert rows[0]["state"] == "idle in transaction"
