"""Tests for lint command group."""

from __future__ import annotations

from kctl_pg.commands.lint import (
    _check_indexes,
    _check_permissions,
    _check_schema,
    _finding,
    _severity_style,
)
from tests.conftest import FakeClient


def test_finding_structure():
    f = _finding("error", "primary_key", "public.users", "Missing PK")
    assert f["severity"] == "error"
    assert f["category"] == "primary_key"
    assert f["object"] == "public.users"
    assert f["message"] == "Missing PK"


def test_severity_style_error():
    assert "[red]" in _severity_style("error")


def test_severity_style_warning():
    assert "[yellow]" in _severity_style("warning")


def test_severity_style_info():
    assert "[blue]" in _severity_style("info")


def test_check_schema_non_snake_case():
    client = FakeClient()
    client.add_result(
        "pg_tables",
        [
            {"schemaname": "public", "tablename": "MyTable"},
            {"schemaname": "public", "tablename": "good_table"},
        ],
    )
    findings = _check_schema(client)
    naming_findings = [f for f in findings if f["category"] == "naming" and "snake_case" in f["message"]]
    assert len(naming_findings) == 1
    assert "MyTable" in naming_findings[0]["message"]


def test_check_schema_missing_pk():
    client = FakeClient()
    client.add_result("pg_tables", [])
    # Use a unique substring from the missing PK query (indisprimary)
    client.add_result("indisprimary", [{"schema": "public", "table_name": "orphan"}])
    findings = _check_schema(client)
    pk_findings = [f for f in findings if f["category"] == "primary_key"]
    assert len(pk_findings) == 1


def test_check_schema_no_issues():
    client = FakeClient()
    # All queries return empty results
    findings = _check_schema(client)
    assert findings == []


def test_check_indexes_unused():
    client = FakeClient()
    # Use "indisprimary" as key — matches the unused indexes query (has NOT i.indisprimary)
    client.add_result(
        "indisprimary",
        [
            {
                "schema": "public",
                "table_name": "orders",
                "index_name": "idx_old",
                "scans": 2,
                "index_size": "1 MB",
                "index_bytes": 1048576,
            },
        ],
    )
    findings = _check_indexes(client, min_scans=50)
    unused = [f for f in findings if f["category"] == "unused_index"]
    assert len(unused) == 1
    assert "idx_old" in unused[0]["message"]


def test_check_indexes_duplicate():
    client = FakeClient()
    client.add_result(
        "index_cols",
        [
            {
                "table_name": "public.users",
                "index_a": "idx_users_email",
                "index_b": "idx_users_email_2",
                "column_list": "email",
                "size_a": "100 kB",
                "size_b": "100 kB",
            },
        ],
    )
    findings = _check_indexes(client, min_scans=50)
    dupes = [f for f in findings if f["category"] == "duplicate_index"]
    assert len(dupes) == 1


def test_check_permissions_superuser():
    client = FakeClient()
    client.add_result(
        "pg_roles",
        [
            {
                "rolname": "admin_user",
                "rolcanlogin": True,
                "rolcreatedb": True,
                "rolcreaterole": False,
                "rolbypassrls": False,
            },
        ],
    )
    findings = _check_permissions(client)
    su_findings = [f for f in findings if f["category"] == "superuser"]
    assert len(su_findings) == 1


def test_check_permissions_no_issues():
    client = FakeClient()
    findings = _check_permissions(client)
    assert findings == []
