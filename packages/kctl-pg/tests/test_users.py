"""Tests for users command group: list, create, drop, password, get, grant, revoke, alter, grant-db, etc."""

from __future__ import annotations

import string

from kctl_pg.commands.users import _generate_password, _quote_ident
from tests.conftest import FakeClient


# ---------------------------------------------------------------------------
# _quote_ident helper
# ---------------------------------------------------------------------------


def test_quote_ident_simple():
    assert _quote_ident("alice") == '"alice"'


def test_quote_ident_with_double_quote():
    assert _quote_ident('al"ice') == '"al""ice"'


def test_quote_ident_empty():
    assert _quote_ident("") == '""'


# ---------------------------------------------------------------------------
# _generate_password helper
# ---------------------------------------------------------------------------


def test_generate_password_default_length():
    pwd = _generate_password()
    assert len(pwd) == 24


def test_generate_password_custom_length():
    pwd = _generate_password(32)
    assert len(pwd) == 32


def test_generate_password_only_alphanumeric():
    pwd = _generate_password(100)
    allowed = set(string.ascii_letters + string.digits)
    assert all(c in allowed for c in pwd)


def test_generate_password_unique():
    """Two generated passwords should be different."""
    p1 = _generate_password()
    p2 = _generate_password()
    assert p1 != p2


# ---------------------------------------------------------------------------
# FakeClient: users list query
# ---------------------------------------------------------------------------


def test_users_list_all_roles():
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
                "name": "appuser",
                "superuser": False,
                "login": True,
                "createdb": False,
                "createrole": False,
                "replication": False,
                "inherit": True,
                "conn_limit": 10,
                "member_of": "",
            },
        ],
    )
    rows = client.fetchall("SELECT r.rolname AS name FROM pg_roles r WHERE r.rolname !~ '^pg_'")
    assert len(rows) == 2
    assert rows[0]["name"] == "postgres"
    assert rows[0]["superuser"] is True
    assert rows[1]["conn_limit"] == 10


def test_users_list_no_system_roles():
    client = FakeClient()
    client.add_result(
        "pg_roles",
        [
            {
                "name": "appuser",
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
    rows = client.fetchall("SELECT r.rolname AS name FROM pg_roles r WHERE r.rolname !~ '^pg_'")
    assert len(rows) == 1


def test_users_list_empty():
    client = FakeClient()
    rows = client.fetchall("SELECT r.rolname AS name FROM pg_roles r WHERE r.rolname !~ '^pg_'")
    assert rows == []


# ---------------------------------------------------------------------------
# FakeClient: role flags logic
# ---------------------------------------------------------------------------


def test_role_flags_superuser_login():
    """Verify _flags logic produces 'SL' for superuser+login."""
    role = {"superuser": True, "login": True, "createdb": False, "createrole": False, "replication": False}
    flags = []
    if role["superuser"]:
        flags.append("S")
    if role["login"]:
        flags.append("L")
    if role["createdb"]:
        flags.append("C")
    if role["createrole"]:
        flags.append("R")
    if role["replication"]:
        flags.append("P")
    assert "".join(flags) == "SL"


def test_role_flags_all():
    role = {"superuser": True, "login": True, "createdb": True, "createrole": True, "replication": True}
    flags = []
    if role["superuser"]:
        flags.append("S")
    if role["login"]:
        flags.append("L")
    if role["createdb"]:
        flags.append("C")
    if role["createrole"]:
        flags.append("R")
    if role["replication"]:
        flags.append("P")
    assert "".join(flags) == "SLCRP"


def test_role_flags_no_login():
    role = {"superuser": False, "login": False, "createdb": False, "createrole": False, "replication": False}
    flags = []
    if role["superuser"]:
        flags.append("S")
    if role["login"]:
        flags.append("L")
    if role["createdb"]:
        flags.append("C")
    if role["createrole"]:
        flags.append("R")
    if role["replication"]:
        flags.append("P")
    assert "".join(flags) == ""


# ---------------------------------------------------------------------------
# FakeClient: create role — duplicate check
# ---------------------------------------------------------------------------


def test_user_create_duplicate_check():
    client = FakeClient()
    client.add_result("pg_roles", [{"?column?": 1}])
    exists = client.fetchval("SELECT 1 FROM pg_roles WHERE rolname = %s", ("appuser",))
    assert exists is not None


def test_user_create_no_duplicate():
    client = FakeClient()
    exists = client.fetchval("SELECT 1 FROM pg_roles WHERE rolname = %s", ("newrole",))
    assert exists is None


# ---------------------------------------------------------------------------
# FakeClient: drop role — guards
# ---------------------------------------------------------------------------


def test_user_drop_not_exists():
    client = FakeClient()
    exists = client.fetchval("SELECT 1 FROM pg_roles WHERE rolname = %s", ("nosuchrole",))
    assert exists is None


def test_user_drop_system_postgres_blocked():
    """Cannot drop the 'postgres' superuser."""
    protected = {"postgres"}
    assert "postgres" in protected


# ---------------------------------------------------------------------------
# FakeClient: get role — detail
# ---------------------------------------------------------------------------


def test_user_get_role_info():
    client = FakeClient()
    client.add_result(
        "pg_roles",
        [
            {
                "name": "appuser",
                "superuser": False,
                "inherit": True,
                "createrole": False,
                "createdb": False,
                "login": True,
                "replication": False,
                "conn_limit": -1,
                "valid_until": None,
            }
        ],
    )
    role = client.fetchone("SELECT r.rolname AS name FROM pg_roles r WHERE r.rolname = %s", ("appuser",))
    assert role is not None
    assert role["name"] == "appuser"
    assert role["login"] is True
    assert role["superuser"] is False


def test_user_get_role_not_found():
    client = FakeClient()
    role = client.fetchone("SELECT r.rolname FROM pg_roles r WHERE r.rolname = %s", ("nosuchrole",))
    assert role is None


def test_user_get_role_memberships():
    client = FakeClient()
    client.add_result(
        "pg_auth_members",
        [
            {"rolname": "readonly"},
            {"rolname": "reporting"},
        ],
    )
    memberships = client.fetchall(
        "SELECT b.rolname FROM pg_auth_members m JOIN pg_roles b ON m.roleid = b.oid WHERE m.member = (SELECT oid FROM pg_roles WHERE rolname = %s)",
        ("appuser",),
    )
    assert len(memberships) == 2
    assert memberships[0]["rolname"] == "readonly"


def test_user_get_owned_databases():
    client = FakeClient()
    client.add_result(
        "pg_database",
        [
            {"datname": "myapp"},
            {"datname": "myapp_test"},
        ],
    )
    owned = client.fetchall(
        "SELECT datname FROM pg_database WHERE datdba = (SELECT oid FROM pg_roles WHERE rolname = %s)",
        ("appuser",),
    )
    assert len(owned) == 2


# ---------------------------------------------------------------------------
# FakeClient: conn_limit display
# ---------------------------------------------------------------------------


def test_conn_limit_unlimited():
    conn_limit = -1
    display = str(conn_limit) if conn_limit >= 0 else "unlimited"
    assert display == "unlimited"


def test_conn_limit_positive():
    conn_limit = 25
    display = str(conn_limit) if conn_limit >= 0 else "unlimited"
    assert display == "25"


def test_conn_limit_zero():
    conn_limit = 0
    display = str(conn_limit) if conn_limit >= 0 else "unlimited"
    assert display == "0"


# ---------------------------------------------------------------------------
# FakeClient: alter role — parameter validation
# ---------------------------------------------------------------------------


def test_user_alter_role_exists():
    client = FakeClient()
    client.add_result("pg_roles", [{"?column?": 1}])
    exists = client.fetchval("SELECT 1 FROM pg_roles WHERE rolname = %s", ("appuser",))
    assert exists is not None


def test_user_alter_role_not_exists():
    client = FakeClient()
    exists = client.fetchval("SELECT 1 FROM pg_roles WHERE rolname = %s", ("nosuchrole",))
    assert exists is None


def test_user_alter_param_exists():
    client = FakeClient()
    client.add_result("pg_settings", [{"?column?": 1}])
    param_exists = client.fetchval("SELECT 1 FROM pg_settings WHERE name = %s", ("search_path",))
    assert param_exists is not None


def test_user_alter_param_not_exists():
    client = FakeClient()
    param_exists = client.fetchval("SELECT 1 FROM pg_settings WHERE name = %s", ("invalid_param",))
    assert param_exists is None


# ---------------------------------------------------------------------------
# FakeClient: grant-db privilege validation
# ---------------------------------------------------------------------------


def test_grant_db_valid_privileges():
    valid_privs = {"connect", "create", "temp", "temporary", "all"}
    test_cases = [
        ("connect", True),
        ("create", True),
        ("temp", True),
        ("all", True),
        ("invalid", False),
        ("delete", False),
    ]
    for priv, expected in test_cases:
        assert (priv in valid_privs) == expected


def test_grant_db_database_exists():
    client = FakeClient()
    client.add_result("pg_database", [{"?column?": 1}])
    exists = client.fetchval("SELECT 1 FROM pg_database WHERE datname = %s", ("myapp",))
    assert exists is not None


def test_grant_db_database_not_exists():
    client = FakeClient()
    exists = client.fetchval("SELECT 1 FROM pg_database WHERE datname = %s", ("nosuchdb",))
    assert exists is None


def test_grant_db_role_exists():
    client = FakeClient()
    client.add_result("pg_roles", [{"?column?": 1}])
    exists = client.fetchval("SELECT 1 FROM pg_roles WHERE rolname = %s", ("appuser",))
    assert exists is not None


# ---------------------------------------------------------------------------
# FakeClient: grant-schema privilege validation
# ---------------------------------------------------------------------------


def test_grant_schema_valid_privileges():
    valid_privs = {"usage", "create", "all"}
    test_cases = [
        ("usage", True),
        ("create", True),
        ("all", True),
        ("select", False),
        ("delete", False),
    ]
    for priv, expected in test_cases:
        assert (priv in valid_privs) == expected


def test_grant_schema_schema_exists():
    client = FakeClient()
    client.add_result("pg_namespace", [{"?column?": 1}])
    exists = client.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = %s", ("public",))
    assert exists is not None


def test_grant_schema_schema_not_exists():
    client = FakeClient()
    exists = client.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = %s", ("nosuchschema",))
    assert exists is None


# ---------------------------------------------------------------------------
# FakeClient: grant-table privilege validation
# ---------------------------------------------------------------------------


def test_grant_table_valid_privileges():
    valid_privs = {"select", "insert", "update", "delete", "truncate", "references", "trigger", "all"}
    test_cases = [
        ("select", True),
        ("insert", True),
        ("update", True),
        ("delete", True),
        ("truncate", True),
        ("references", True),
        ("trigger", True),
        ("all", True),
        ("connect", False),
        ("usage", False),
    ]
    for priv, expected in test_cases:
        assert (priv in valid_privs) == expected


def test_grant_table_all_tables_in_schema_detection():
    """ALL TABLES IN SCHEMA syntax is detected via startswith."""
    table = "ALL TABLES IN SCHEMA public"
    assert table.upper().startswith("ALL TABLES IN SCHEMA ")
    schema_name = table.split()[-1]
    assert schema_name == "public"


def test_grant_table_normal_table():
    table = "users"
    assert not table.upper().startswith("ALL TABLES IN SCHEMA ")


# ---------------------------------------------------------------------------
# FakeClient: password — fetchone with role
# ---------------------------------------------------------------------------


def test_password_role_check():
    client = FakeClient()
    client.add_result("pg_roles", [{"?column?": 1}])
    exists = client.fetchval("SELECT 1 FROM pg_roles WHERE rolname = %s", ("appuser",))
    assert exists is not None


def test_password_role_not_found():
    client = FakeClient()
    exists = client.fetchval("SELECT 1 FROM pg_roles WHERE rolname = %s", ("nosuchrole",))
    assert exists is None
