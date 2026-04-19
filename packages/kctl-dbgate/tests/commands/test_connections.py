"""Tests for the connections command group."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_httpx import HTTPXMock
from typer.testing import CliRunner

from kctl_dbgate.cli import app

BASE = "https://dbgate.example.com"


def _mock_login(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/auth/login",
        json={"accessToken": "tok"},
    )


def _body_of(req: Any) -> dict[str, Any]:
    return json.loads(req.content)  # type: ignore[no-any-return]


def test_list_prints_table(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/list",
        json=[
            {
                "_id": "a1",
                "displayName": "Alpha",
                "engine": "postgres@dbgate-plugin-postgres",
                "server": "db1",
                "port": 5432,
                "user": "u1",
            },
            {
                "_id": "b2",
                "displayName": "Beta",
                "engine": "mysql@dbgate-plugin-mysql",
                "server": "db2",
                "port": 3306,
                "user": "u2",
                "isReadOnly": True,
            },
        ],
    )
    runner = CliRunner()
    result = runner.invoke(app, ["connections", "list"])
    assert result.exit_code == 0, result.output
    assert "Alpha" in result.output
    assert "Beta" in result.output


def test_get_prints_detail(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/get",
        json={
            "_id": "a1",
            "displayName": "Alpha",
            "engine": "postgres@dbgate-plugin-postgres",
            "server": "db1",
            "port": 5432,
            "user": "u1",
        },
    )
    runner = CliRunner()
    result = runner.invoke(app, ["connections", "get", "a1"])
    assert result.exit_code == 0, result.output
    assert "Alpha" in result.output
    assert "db1" in result.output

    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/connections/get")
    assert _body_of(req) == {"conid": "a1"}


def test_test_reports_ok_on_connected(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/test",
        json={"msgtype": "connected", "version": "16.0"},
    )
    runner = CliRunner()
    result = runner.invoke(app, ["connections", "test", "a1"])
    assert result.exit_code == 0, result.output
    assert "connected" in result.output.lower() or "OK" in result.output


def test_create_sends_correct_payload(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/save",
        json={"_id": "new1"},
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "connections",
            "create",
            "--label",
            "MyDB",
            "--engine",
            "postgres@dbgate-plugin-postgres",
            "--server",
            "db.example.com",
            "--port",
            "5432",
            "--user",
            "postgres",
            "--password",
            "secret",
            "--database",
            "mydb",
        ],
    )
    assert result.exit_code == 0, result.output

    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/connections/save")
    body = _body_of(req)
    assert body["displayName"] == "MyDB"
    assert body["engine"] == "postgres@dbgate-plugin-postgres"
    assert body["server"] == "db.example.com"
    assert body["port"] == "5432"
    assert body["user"] == "postgres"
    assert body["password"] == "secret"
    assert body["database"] == "mydb"


def test_create_with_ssh_tunnel_sets_use_ssh_tunnel(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/save",
        json={"_id": "new_ssh"},
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "connections",
            "create",
            "--label",
            "via-ssh",
            "--engine",
            "postgres@dbgate-plugin-postgres",
            "--server",
            "127.0.0.1",
            "--port",
            "5432",
            "--user",
            "postgres",
            "--password",
            "dbpw",
            "--ssh-host",
            "1.2.3.4",
            "--ssh-port",
            "22",
            "--ssh-user",
            "root",
            "--ssh-mode",
            "keyFile",
            "--ssh-keyfile",
            "/root/.ssh/id_rsa",
        ],
    )
    assert result.exit_code == 0, result.output
    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/connections/save")
    body = _body_of(req)
    assert body["useSshTunnel"] is True
    assert body["sshHost"] == "1.2.3.4"
    assert body["sshPort"] == "22"
    assert body["sshLogin"] == "root"
    assert body["sshMode"] == "keyFile"
    assert body["sshKeyfile"] == "/root/.ssh/id_rsa"
    assert body["server"] == "127.0.0.1"  # from the SSH-target's perspective
    assert body["password"] == "dbpw"  # DB password, not SSH


def test_create_rejects_invalid_ssh_mode() -> None:
    # Typer rejects --ssh-mode before login happens — no HTTP mocks needed.
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "connections",
            "create",
            "--label",
            "bad",
            "--engine",
            "postgres@dbgate-plugin-postgres",
            "--server",
            "127.0.0.1",
            "--port",
            "5432",
            "--user",
            "u",
            "--password",
            "p",
            "--ssh-host",
            "1.2.3.4",
            "--ssh-mode",
            "nonsense",
        ],
    )
    assert result.exit_code != 0


def test_delete_confirms_by_default(httpx_mock: HTTPXMock) -> None:
    # No mocks at all — aborting before confirm means no HTTP traffic at all.
    runner = CliRunner()
    result = runner.invoke(app, ["connections", "delete", "a1"], input="n\n")
    # Exited non-failure after aborting.
    assert result.exit_code == 0
    delete_reqs = [r for r in httpx_mock.get_requests() if r.url.path == "/connections/delete"]
    assert len(delete_reqs) == 0


def test_delete_force_skips_confirm(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/delete",
        json={"_id": "a1"},
    )
    runner = CliRunner()
    result = runner.invoke(app, ["connections", "delete", "a1", "--force"])
    assert result.exit_code == 0, result.output

    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/connections/delete")
    assert _body_of(req) == {"_id": "a1"}


def test_new_sqlite_payload(httpx_mock: HTTPXMock) -> None:
    """new-sqlite must go through /connections/save so the user-provided file
    path and label are honoured — /connections/new-sqlite-database ignores
    both and drops the db file inside DBGate's app folder.
    """
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/save",
        json={"_id": "sq1"},
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["connections", "new-sqlite", "--label", "MyLite", "--file", "/tmp/my.db"],
    )
    assert result.exit_code == 0, result.output

    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/connections/save")
    body = _body_of(req)
    assert body["displayName"] == "MyLite"
    assert body["databaseFile"] == "/tmp/my.db"
    assert body["engine"] == "sqlite@dbgate-plugin-sqlite"
    assert body.get("singleDatabase") is True


def test_new_duckdb_payload(httpx_mock: HTTPXMock) -> None:
    """Same reasoning as new-sqlite: must use /connections/save directly."""
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/save",
        json={"_id": "dk1"},
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["connections", "new-duckdb", "--label", "MyDuck", "--file", "/tmp/d.duckdb"],
    )
    assert result.exit_code == 0, result.output

    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/connections/save")
    body = _body_of(req)
    assert body["displayName"] == "MyDuck"
    assert body["databaseFile"] == "/tmp/d.duckdb"
    assert body["engine"] == "duckdb@dbgate-plugin-duckdb"


def test_update_sends_id_and_fields(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/update",
        json={"_id": "a1"},
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["connections", "update", "a1", "--label", "NewLabel", "--port", "6543"],
    )
    assert result.exit_code == 0, result.output

    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/connections/update")
    body = _body_of(req)
    # DBGate destructures {_id, values} — a flat payload is silently a no-op.
    assert body["_id"] == "a1"
    assert "values" in body, f"update must nest fields under 'values', got: {body}"
    assert body["values"]["displayName"] == "NewLabel"
    assert body["values"]["port"] == "6543"


def test_update_rejects_no_fields() -> None:
    """Updating with no field flags must error instead of silently no-op'ing."""
    runner = CliRunner()
    result = runner.invoke(app, ["connections", "update", "a1"])
    assert result.exit_code != 0
    assert "no fields" in result.output.lower() or "at least one" in result.output.lower()


# ---------------------------------------------------------------------------
# sync-from-dokploy tests
# ---------------------------------------------------------------------------


def _fake_subprocess_factory(calls: list[str], fixtures: dict[str, str]):
    """Return a MagicMock that answers based on the command string."""

    def runner(cmd, capture_output=True, text=True, **_kw):
        cmd_str = " ".join(cmd)
        calls.append(cmd_str)
        for key, stdout in fixtures.items():
            if key in cmd_str:
                m = MagicMock()
                m.returncode = 0
                m.stdout = stdout
                m.stderr = ""
                return m
        m = MagicMock()
        m.returncode = 1
        m.stdout = ""
        m.stderr = "not mocked: " + cmd_str
        return m

    return runner


def test_sync_from_dokploy_creates_per_compose_connections(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    # Empty connection list on DBGate → every compose becomes a new connection
    httpx_mock.add_response(method="POST", url=f"{BASE}/connections/list", json=[])
    # Two create calls will happen
    httpx_mock.add_response(method="POST", url=f"{BASE}/connections/save", json={"_id": "new_a"})
    httpx_mock.add_response(method="POST", url=f"{BASE}/connections/save", json={"_id": "new_b"})

    compose_list = json.dumps(
        [
            {"composeId": "c1", "name": "mac-odoo-erp"},
            {"composeId": "c2", "name": "mac-odoo-hrms"},
            {"composeId": "c3", "name": "mac-odoo-erp-stg"},  # skipped by default
            {"composeId": "c4", "name": "mac-infra-postgres"},  # doesn't match prefix
        ]
    )
    servers_list = json.dumps(
        [
            {"serverId": "s1", "name": "tpp-prod-02", "ipAddress": "46.224.93.123"},
        ]
    )
    compose_c1 = json.dumps(
        {
            "serverId": "s1",
            "env": "PGUSER=odoo\nPGPASSWORD=pw1\nPGDATABASE=mac_odoo_erp\n",
        }
    )
    compose_c2 = json.dumps(
        {
            "serverId": "s1",
            "env": "PGUSER=odoo\nPGPASSWORD=pw2\nPGDATABASE=mac_odoo_hrms\n",
        }
    )

    calls: list[str] = []
    fake = _fake_subprocess_factory(
        calls,
        {
            "compose list": compose_list,
            "servers list": servers_list,
            "compose get c1": compose_c1,
            "compose get c2": compose_c2,
        },
    )

    runner = CliRunner()
    with patch("kctl_dbgate.commands.connections._subprocess.run", side_effect=fake):
        result = runner.invoke(
            app,
            [
                "connections",
                "sync-from-dokploy",
                "--dokploy-profile",
                "idtpp",
                "--service-prefix",
                "mac-odoo",
                "--ssh-keyfile",
                "/root/.ssh/id_rsa_kodeme",
            ],
        )

    assert result.exit_code == 0, result.output

    saves = [r for r in httpx_mock.get_requests() if r.url.path == "/connections/save"]
    assert len(saves) == 2, f"expected 2 creates (stg skipped), got {len(saves)}"

    bodies = [json.loads(r.content) for r in saves]
    by_db = {b["database"]: b for b in bodies}
    assert set(by_db.keys()) == {"mac_odoo_erp", "mac_odoo_hrms"}

    # Every create must carry the ssh tunnel fields, pointed at the server IP
    for b in bodies:
        assert b["useSshTunnel"] is True
        assert b["sshHost"] == "46.224.93.123"
        assert b["sshKeyfile"] == "/root/.ssh/id_rsa_kodeme"
        assert b["sshMode"] == "keyFile"
        assert b["server"] == "127.0.0.1"
        assert b["user"] == "odoo"


def test_sync_from_dokploy_dry_run_makes_no_writes(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(method="POST", url=f"{BASE}/connections/list", json=[])

    compose_list = json.dumps([{"composeId": "c1", "name": "mac-odoo-erp"}])
    servers_list = json.dumps([{"serverId": "s1", "name": "tpp-prod-02", "ipAddress": "46.224.93.123"}])
    compose_detail = json.dumps(
        {
            "serverId": "s1",
            "env": "PGUSER=odoo\nPGPASSWORD=pw\nPGDATABASE=mac_odoo_erp\n",
        }
    )

    calls: list[str] = []
    fake = _fake_subprocess_factory(
        calls,
        {
            "compose list": compose_list,
            "servers list": servers_list,
            "compose get c1": compose_detail,
        },
    )

    runner = CliRunner()
    with patch("kctl_dbgate.commands.connections._subprocess.run", side_effect=fake):
        result = runner.invoke(
            app,
            [
                "connections",
                "sync-from-dokploy",
                "--dokploy-profile",
                "idtpp",
                "--service-prefix",
                "mac-odoo",
                "--dry-run",
            ],
        )
    assert result.exit_code == 0, result.output

    # No /connections/save requests — dry-run
    saves = [r for r in httpx_mock.get_requests() if r.url.path == "/connections/save"]
    assert saves == []


def test_sync_from_dokploy_skips_existing_by_default(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    # A connection with the matching label already exists
    existing_label = "mac-odoo-erp → mac_odoo_erp (ssh tpp-prod-02)"
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/list",
        json=[{"_id": "already", "displayName": existing_label}],
    )

    compose_list = json.dumps([{"composeId": "c1", "name": "mac-odoo-erp"}])
    servers_list = json.dumps([{"serverId": "s1", "name": "tpp-prod-02", "ipAddress": "46.224.93.123"}])
    compose_detail = json.dumps(
        {
            "serverId": "s1",
            "env": "PGUSER=odoo\nPGPASSWORD=pw\nPGDATABASE=mac_odoo_erp\n",
        }
    )

    calls: list[str] = []
    fake = _fake_subprocess_factory(
        calls,
        {
            "compose list": compose_list,
            "servers list": servers_list,
            "compose get c1": compose_detail,
        },
    )

    runner = CliRunner()
    with patch("kctl_dbgate.commands.connections._subprocess.run", side_effect=fake):
        result = runner.invoke(
            app,
            [
                "connections",
                "sync-from-dokploy",
                "--dokploy-profile",
                "idtpp",
                "--service-prefix",
                "mac-odoo",
            ],
        )
    assert result.exit_code == 0, result.output
    saves = [r for r in httpx_mock.get_requests() if r.url.path == "/connections/save"]
    assert saves == [], "skip-existing mode must not create duplicates"
    updates = [r for r in httpx_mock.get_requests() if r.url.path == "/connections/update"]
    assert updates == [], "skip-existing must not upsert"


def test_sync_from_dokploy_upsert_replaces_existing(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    existing_label = "mac-odoo-erp → mac_odoo_erp (ssh tpp-prod-02)"
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/list",
        json=[{"_id": "already", "displayName": existing_label}],
    )
    httpx_mock.add_response(method="POST", url=f"{BASE}/connections/update", json={"_id": "already"})

    compose_list = json.dumps([{"composeId": "c1", "name": "mac-odoo-erp"}])
    servers_list = json.dumps([{"serverId": "s1", "name": "tpp-prod-02", "ipAddress": "46.224.93.123"}])
    compose_detail = json.dumps(
        {
            "serverId": "s1",
            "env": "PGUSER=odoo\nPGPASSWORD=pw\nPGDATABASE=mac_odoo_erp\n",
        }
    )

    calls: list[str] = []
    fake = _fake_subprocess_factory(
        calls,
        {
            "compose list": compose_list,
            "servers list": servers_list,
            "compose get c1": compose_detail,
        },
    )

    runner = CliRunner()
    with patch("kctl_dbgate.commands.connections._subprocess.run", side_effect=fake):
        result = runner.invoke(
            app,
            [
                "connections",
                "sync-from-dokploy",
                "--dokploy-profile",
                "idtpp",
                "--service-prefix",
                "mac-odoo",
                "--upsert",
            ],
        )
    assert result.exit_code == 0, result.output

    updates = [r for r in httpx_mock.get_requests() if r.url.path == "/connections/update"]
    assert len(updates) == 1
    body = json.loads(updates[0].content)
    assert body["_id"] == "already"
    assert body["values"]["database"] == "mac_odoo_erp"
    assert body["values"]["useSshTunnel"] is True
