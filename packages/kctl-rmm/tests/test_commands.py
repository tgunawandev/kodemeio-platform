"""Command-level tests for kctl-rmm: agents, alerts, checks, scripts."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_rmm.cli import app

runner = CliRunner()


def _mock_resolve(*args, **kwargs):  # type: ignore[no-untyped-def]
    return ("https://rmm.kodeme.io", "test-api-key")


def _make_actx(json_mode: bool = True) -> MagicMock:
    from kctl_lib.output import Output

    from kctl_rmm.core.callbacks import AppContext

    ctx_obj = AppContext(quiet=True, json_mode=json_mode)
    ctx_obj._output = Output(json_mode=json_mode, quiet=True, format="json" if json_mode else "pretty")
    ctx_obj._client = MagicMock()
    return ctx_obj


def _make_ctx(actx: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.obj = actx
    return ctx


MOCK_AGENTS = [
    {
        "agent_id": "agent-001",
        "hostname": "mac-workstation",
        "client_name": "Mandiri Agro",
        "site_name": "Head Office",
        "operating_system": "Windows 11 Pro",
        "plat": "windows",
        "status": "online",
    },
    {
        "agent_id": "agent-002",
        "hostname": "tpp-server-01",
        "client_name": "Pakerti",
        "site_name": "Server Room",
        "operating_system": "Ubuntu 22.04",
        "plat": "linux",
        "status": "offline",
    },
]

MOCK_ALERTS = [
    {
        "id": 1,
        "agent": {"hostname": "mac-workstation"},
        "alert_type": "CPU",
        "severity": "warning",
        "message": "CPU usage above 80% for 5 minutes",
        "alert_time": "2026-03-29T08:00:00Z",
    },
    {
        "id": 2,
        "agent": "agent-002",
        "alert_type": "disk",
        "severity": "error",
        "message": "Disk usage above 95%",
        "created": "2026-03-28T10:00:00Z",
    },
]

MOCK_CHECKS = [
    {
        "id": 10,
        "readable_desc": "Disk space > 80%",
        "check_type": "diskspace",
        "status": "passing",
        "agent": {"hostname": "mac-workstation"},
        "alert_severity": "warning",
    },
    {
        "id": 11,
        "readable_desc": "CPU load > 90%",
        "check_type": "cpuload",
        "status": "failing",
        "agent": {"hostname": "tpp-server-01"},
        "alert_severity": "error",
    },
]

MOCK_SCRIPTS = [
    {
        "id": 1,
        "name": "Disk Cleanup",
        "shell": "powershell",
        "script_type": "builtin",
        "description": "Cleans temp files and empties recycle bin",
        "default_timeout": 90,
        "args": [],
        "script_body": "Remove-Item -Recurse $env:TEMP\\*\n",
    },
    {
        "id": 2,
        "name": "Update Odoo",
        "shell": "bash",
        "script_type": "custom",
        "description": "Pull latest Odoo from git and restart service",
        "default_timeout": 300,
        "args": ["--branch", "18.0"],
        "script_body": "#!/bin/bash\ngit pull\nsystemctl restart odoo\n",
    },
]


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------


class TestSmokeHelp:
    @patch("kctl_rmm.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_root_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    @patch("kctl_rmm.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_agents_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["agents", "--help"])
        assert result.exit_code == 0

    @patch("kctl_rmm.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_alerts_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["alerts", "--help"])
        assert result.exit_code == 0

    @patch("kctl_rmm.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_checks_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["checks", "--help"])
        assert result.exit_code == 0

    @patch("kctl_rmm.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_scripts_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["scripts", "--help"])
        assert result.exit_code == 0

    @patch("kctl_rmm.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_clients_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["clients", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Agents commands
# ---------------------------------------------------------------------------


class TestAgentsList:
    @patch("kctl_rmm.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_list_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["agents", "list", "--help"])
        assert result.exit_code == 0

    @patch("kctl_rmm.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_list_filter_options(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["agents", "list", "--help"])
        assert "--client" in result.output
        assert "--site" in result.output

    def test_list_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx._client.get.return_value = MOCK_AGENTS
        ctx = _make_ctx(actx)

        from kctl_rmm.commands.agents import list_

        list_(ctx, detail=False, client=None, site=None)
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["agent_id"] == "agent-001"
        assert data[1]["hostname"] == "tpp-server-01"

    def test_list_filter_by_client(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx._client.get.return_value = MOCK_AGENTS
        ctx = _make_ctx(actx)

        from kctl_rmm.commands.agents import list_

        list_(ctx, detail=False, client="Mandiri", site=None)
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 1
        assert "Mandiri" in data[0]["client_name"]

    def test_list_filter_by_site(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx._client.get.return_value = MOCK_AGENTS
        ctx = _make_ctx(actx)

        from kctl_rmm.commands.agents import list_

        list_(ctx, detail=False, client=None, site="Server Room")
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 1
        assert data[0]["site_name"] == "Server Room"

    def test_list_empty(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx._client.get.return_value = []
        ctx = _make_ctx(actx)

        from kctl_rmm.commands.agents import list_

        list_(ctx, detail=False, client=None, site=None)
        data = json.loads(capsys.readouterr().out)
        assert data == []

    def test_list_dict_response_with_results_key(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Some API versions wrap in 'results'."""
        actx = _make_actx(json_mode=True)
        actx._client.get.return_value = {"results": MOCK_AGENTS}
        ctx = _make_ctx(actx)

        from kctl_rmm.commands.agents import list_

        list_(ctx, detail=False, client=None, site=None)
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 2


class TestAgentsGet:
    @patch("kctl_rmm.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_get_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["agents", "get", "--help"])
        assert result.exit_code == 0

    def test_get_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        agent = MOCK_AGENTS[0].copy()
        agent["last_seen"] = "2026-03-29T10:00:00Z"
        agent["version"] = "2.1.0"
        actx._client.get.return_value = agent
        ctx = _make_ctx(actx)

        from kctl_rmm.commands.agents import get

        get(ctx, agent_id="agent-001")
        data = json.loads(capsys.readouterr().out)
        assert data["agent_id"] == "agent-001"
        assert data["hostname"] == "mac-workstation"

    def test_get_bad_response_exits(self) -> None:
        import typer

        actx = _make_actx(json_mode=True)
        actx._client.get.return_value = "not-a-dict"
        ctx = _make_ctx(actx)

        from kctl_rmm.commands.agents import get

        with pytest.raises((SystemExit, typer.Exit)):
            get(ctx, agent_id="bad-id")


# ---------------------------------------------------------------------------
# Alerts commands
# ---------------------------------------------------------------------------


class TestAlertsList:
    @patch("kctl_rmm.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_list_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["alerts", "list", "--help"])
        assert result.exit_code == 0

    @patch("kctl_rmm.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_list_severity_option(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["alerts", "list", "--help"])
        assert "--severity" in result.output

    def test_list_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx._client.patch.return_value = MOCK_ALERTS
        ctx = _make_ctx(actx)

        from kctl_rmm.commands.alerts import list_

        list_(ctx, severity=None)
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["id"] == 1

    def test_list_with_severity_filter(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx._client.patch.return_value = [MOCK_ALERTS[1]]
        ctx = _make_ctx(actx)

        from kctl_rmm.commands.alerts import list_

        list_(ctx, severity="error")
        call_args = actx._client.patch.call_args
        assert call_args[1]["data"]["severity"] == "error"

    def test_list_empty(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx._client.patch.return_value = []
        ctx = _make_ctx(actx)

        from kctl_rmm.commands.alerts import list_

        list_(ctx, severity=None)
        data = json.loads(capsys.readouterr().out)
        assert data == []


class TestAlertsDismiss:
    @patch("kctl_rmm.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_dismiss_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["alerts", "dismiss", "--help"])
        assert result.exit_code == 0

    def test_dismiss_calls_delete(self) -> None:
        actx = _make_actx(json_mode=False)
        actx._client.delete.return_value = None
        ctx = _make_ctx(actx)

        from kctl_rmm.commands.alerts import dismiss

        dismiss(ctx, alert_id=1)
        actx._client.delete.assert_called_once_with("/alerts/1/")


# ---------------------------------------------------------------------------
# Checks commands
# ---------------------------------------------------------------------------


class TestChecksList:
    @patch("kctl_rmm.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_list_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["checks", "list", "--help"])
        assert result.exit_code == 0

    def test_list_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx._client.get.return_value = MOCK_CHECKS
        ctx = _make_ctx(actx)

        from kctl_rmm.commands.checks import list_

        list_(ctx, agent=None)
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["check_type"] == "diskspace"
        assert data[1]["status"] == "failing"

    def test_list_with_agent_filter(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx._client.get.return_value = [MOCK_CHECKS[0]]
        ctx = _make_ctx(actx)

        from kctl_rmm.commands.checks import list_

        list_(ctx, agent="agent-001")
        # Agent-filtered calls use /checks/{agent_id}/ endpoint
        call_args = actx._client.get.call_args
        assert "agent-001" in call_args[0][0]

    def test_list_empty_shows_info(self) -> None:
        actx = _make_actx(json_mode=False)
        actx._client.get.return_value = []
        ctx = _make_ctx(actx)

        from kctl_rmm.commands.checks import list_

        list_(ctx, agent=None)
        # Should not raise even with empty results
        actx._output.info.assert_called_once()


class TestChecksCreate:
    @patch("kctl_rmm.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_create_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["checks", "create", "--help"])
        assert result.exit_code == 0

    @patch("kctl_rmm.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_create_options(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["checks", "create", "--help"])
        assert "--agent" in result.output
        assert "--type" in result.output
        assert "--severity" in result.output

    def test_create_direct(self) -> None:
        actx = _make_actx(json_mode=False)
        actx._client.post.return_value = {
            "id": 20,
            "check_type": "diskspace",
            "readable_desc": "Disk space check",
        }
        ctx = _make_ctx(actx)

        from kctl_rmm.commands.checks import create

        create(
            ctx,
            agent="agent-001",
            check_type="diskspace",
            name="Disk check",
            threshold=80,
            alert_severity="warning",
        )
        actx._client.post.assert_called_once()
        payload = actx._client.post.call_args[1]["json"]
        assert payload["agent"] == "agent-001"
        assert payload["check_type"] == "diskspace"


# ---------------------------------------------------------------------------
# Scripts commands
# ---------------------------------------------------------------------------


class TestScriptsList:
    @patch("kctl_rmm.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_list_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["scripts", "list", "--help"])
        assert result.exit_code == 0

    def test_list_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx._client.get.return_value = MOCK_SCRIPTS
        ctx = _make_ctx(actx)

        from kctl_rmm.commands.scripts import list_

        list_(ctx)
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "Disk Cleanup"
        assert data[1]["shell"] == "bash"

    def test_list_empty(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx._client.get.return_value = []
        ctx = _make_ctx(actx)

        from kctl_rmm.commands.scripts import list_

        list_(ctx)
        data = json.loads(capsys.readouterr().out)
        assert data == []


class TestScriptsGet:
    @patch("kctl_rmm.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_get_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["scripts", "get", "--help"])
        assert result.exit_code == 0

    def test_get_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx._client.get.return_value = MOCK_SCRIPTS[0]
        ctx = _make_ctx(actx)

        from kctl_rmm.commands.scripts import get

        get(ctx, script_id=1)
        data = json.loads(capsys.readouterr().out)
        assert data["name"] == "Disk Cleanup"
        assert data["shell"] == "powershell"

    def test_get_bad_response_exits(self) -> None:
        import typer

        actx = _make_actx(json_mode=True)
        actx._client.get.return_value = "unexpected"
        ctx = _make_ctx(actx)

        from kctl_rmm.commands.scripts import get

        with pytest.raises((SystemExit, typer.Exit)):
            get(ctx, script_id=999)


class TestScriptsRun:
    @patch("kctl_rmm.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_run_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["scripts", "run", "--help"])
        assert result.exit_code == 0

    @patch("kctl_rmm.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_run_options(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["scripts", "run", "--help"])
        assert "--agent" in result.output
