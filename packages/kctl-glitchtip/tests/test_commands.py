"""Command-level tests for kctl-glitchtip: projects, issues, uptime, orgs."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_glitchtip.cli import app

runner = CliRunner()


def _mock_resolve(*args, **kwargs):  # type: ignore[no-untyped-def]
    return ("https://glitchtip.kodeme.io", "test-token")


def _make_actx(json_mode: bool = True) -> MagicMock:
    from kctl_lib.output import Output

    from kctl_glitchtip.core.callbacks import AppContext

    ctx_obj = AppContext(quiet=True, json_mode=json_mode)
    ctx_obj._output = Output(json_mode=json_mode, quiet=True, format="json" if json_mode else "pretty")
    ctx_obj._client = MagicMock()
    return ctx_obj


def _make_ctx(actx: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.obj = actx
    return ctx


MOCK_PROJECTS = [
    {
        "id": "1",
        "name": "MAC SFA",
        "slug": "mac-sfa",
        "platform": "javascript",
        "organization": {"slug": "kodemeio", "name": "Kodemeio"},
        "firstEvent": "2026-01-15T10:00:00Z",
        "keys": [{"dsn": {"public": "https://abc123@glitchtip.kodeme.io/1"}}],
    },
    {
        "id": "2",
        "name": "Odoo Backend",
        "slug": "odoo-backend",
        "platform": "python",
        "organization": {"slug": "kodemeio", "name": "Kodemeio"},
        "firstEvent": None,
        "keys": [],
    },
]

MOCK_ISSUES = [
    {
        "id": "101",
        "title": "TypeError: Cannot read property 'x' of undefined",
        "status": "unresolved",
        "count": 42,
        "lastSeen": "2026-03-29T08:00:00Z",
        "project": {"slug": "mac-sfa"},
        "metadata": {"type": "TypeError"},
    },
    {
        "id": "102",
        "title": "ConnectionError: Database unreachable",
        "status": "resolved",
        "count": 5,
        "lastSeen": "2026-03-28T10:00:00Z",
        "project": {"slug": "odoo-backend"},
        "metadata": {},
    },
]

MOCK_MONITORS = [
    {
        "id": 1,
        "name": "MAC SFA Health",
        "monitorType": "Ping",
        "url": "https://sfa.mandiriagro.com/_health",
        "interval": 60,
        "isUp": True,
    },
    {
        "id": 2,
        "name": "Odoo Web",
        "monitorType": "GET",
        "url": "https://odoo.mandiriagro.com/web/login",
        "interval": 120,
        "isUp": False,
    },
]

MOCK_ORGS = [
    {
        "id": "1",
        "name": "Kodemeio",
        "slug": "kodemeio",
        "dateCreated": "2024-01-01T00:00:00Z",
        "status": {"id": "active", "name": "Active"},
    },
]


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------


class TestSmokeHelp:
    @patch("kctl_glitchtip.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_root_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    @patch("kctl_glitchtip.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_projects_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["projects", "--help"])
        assert result.exit_code == 0

    @patch("kctl_glitchtip.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_issues_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["issues", "--help"])
        assert result.exit_code == 0

    @patch("kctl_glitchtip.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_uptime_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["uptime", "--help"])
        assert result.exit_code == 0

    @patch("kctl_glitchtip.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_orgs_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["orgs", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Projects commands
# ---------------------------------------------------------------------------


class TestProjectsList:
    @patch("kctl_glitchtip.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_list_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["projects", "list", "--help"])
        assert result.exit_code == 0

    def test_list_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx._client.get_list.return_value = MOCK_PROJECTS
        ctx = _make_ctx(actx)

        from kctl_glitchtip.commands.projects import list_

        list_(ctx)
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["slug"] == "mac-sfa"

    def test_list_empty(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx._client.get_list.return_value = []
        ctx = _make_ctx(actx)

        from kctl_glitchtip.commands.projects import list_

        list_(ctx)
        data = json.loads(capsys.readouterr().out)
        assert data == []


class TestProjectsGet:
    @patch("kctl_glitchtip.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_get_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["projects", "get", "--help"])
        assert result.exit_code == 0

    def test_get_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        project = MOCK_PROJECTS[0].copy()
        project["teams"] = [{"slug": "dev-team"}]
        actx._client.get.return_value = project
        ctx = _make_ctx(actx)

        from kctl_glitchtip.commands.projects import get

        get(ctx, org_slug="kodemeio", project_slug="mac-sfa")
        data = json.loads(capsys.readouterr().out)
        assert data["slug"] == "mac-sfa"
        assert data["platform"] == "javascript"


# ---------------------------------------------------------------------------
# Issues commands
# ---------------------------------------------------------------------------


class TestIssuesList:
    @patch("kctl_glitchtip.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_list_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["issues", "list", "--help"])
        assert result.exit_code == 0

    @patch("kctl_glitchtip.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_list_requires_org(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["issues", "list", "--help"])
        assert "--org" in result.output

    def test_list_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx._client.get_list.return_value = MOCK_ISSUES
        ctx = _make_ctx(actx)

        from kctl_glitchtip.commands.issues import list_

        list_(ctx, org_slug="kodemeio", project=None, status=None, sort="-last_seen", limit=25)
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["id"] == "101"

    def test_list_with_project_filter(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx._client.get_list.return_value = [MOCK_ISSUES[0]]
        ctx = _make_ctx(actx)

        from kctl_glitchtip.commands.issues import list_

        list_(ctx, org_slug="kodemeio", project="mac-sfa", status=None, sort="-last_seen", limit=25)
        # Verify it used project-scoped endpoint
        call_args = actx._client.get_list.call_args
        assert "mac-sfa" in call_args[0][0]

    def test_list_with_status_filter(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx._client.get_list.return_value = [MOCK_ISSUES[0]]
        ctx = _make_ctx(actx)

        from kctl_glitchtip.commands.issues import list_

        list_(ctx, org_slug="kodemeio", project=None, status="unresolved", sort="-last_seen", limit=25)
        call_kwargs = actx._client.get_list.call_args[1]
        assert call_kwargs["params"]["query"] == "is:unresolved"


class TestIssuesGet:
    @patch("kctl_glitchtip.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_get_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["issues", "get", "--help"])
        assert result.exit_code == 0

    def test_get_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        issue = MOCK_ISSUES[0].copy()
        issue["culprit"] = "app.js:42"
        issue["level"] = "error"
        issue["count"] = 42
        issue["userCount"] = 5
        actx._client.get.return_value = issue
        ctx = _make_ctx(actx)

        from kctl_glitchtip.commands.issues import get

        get(ctx, issue_id="101")
        data = json.loads(capsys.readouterr().out)
        assert data["id"] == "101"
        assert data["status"] == "unresolved"


# ---------------------------------------------------------------------------
# Uptime commands
# ---------------------------------------------------------------------------


class TestUptimeList:
    @patch("kctl_glitchtip.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_list_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["uptime", "list", "--help"])
        assert result.exit_code == 0

    def test_list_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx._client.get_list.return_value = MOCK_MONITORS
        ctx = _make_ctx(actx)

        from kctl_glitchtip.commands.uptime import list_

        list_(ctx, org="kodemeio")
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "MAC SFA Health"

    def test_list_empty_shows_info(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=False)
        actx._client.get_list.return_value = []
        ctx = _make_ctx(actx)

        from kctl_glitchtip.commands.uptime import list_

        list_(ctx, org="kodemeio")
        # Should not raise; no monitors → info message
        actx._client.get_list.assert_called_once()

    def test_list_auto_detects_org(self, capsys: pytest.CaptureFixture[str]) -> None:
        """When org=None, fetches from organizations/ first."""
        actx = _make_actx(json_mode=True)

        def get_list_side(endpoint: str, **kwargs: object):  # type: ignore[no-untyped-def]
            if "organizations" in endpoint and "monitors" not in endpoint:
                return MOCK_ORGS
            return MOCK_MONITORS

        actx._client.get_list.side_effect = get_list_side
        ctx = _make_ctx(actx)

        from kctl_glitchtip.commands.uptime import list_

        list_(ctx, org=None)
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)


class TestUptimeCreate:
    @patch("kctl_glitchtip.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_create_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["uptime", "create", "--help"])
        assert result.exit_code == 0

    @patch("kctl_glitchtip.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_create_requires_name_and_url(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["uptime", "create", "--help"])
        assert "--name" in result.output
        assert "--url" in result.output

    def test_create_direct(self, capsys: pytest.CaptureFixture[str]) -> None:
        actx = _make_actx(json_mode=True)
        actx._client.post.return_value = {
            "id": 10,
            "name": "New Monitor",
            "url": "https://example.com/health",
            "interval": 60,
            "isUp": None,
        }
        ctx = _make_ctx(actx)

        from kctl_glitchtip.commands.uptime import create

        create(
            ctx,
            name="New Monitor",
            url="https://example.com/health",
            org="kodemeio",
            interval=60,
            monitor_type="Ping",
            expected_status=200,
            timeout=20,
            project=None,
        )
        actx._client.post.assert_called_once()
        call_args = actx._client.post.call_args
        assert "monitors" in call_args[0][0]
        payload = call_args[1]["json"]
        assert payload["name"] == "New Monitor"
        assert payload["url"] == "https://example.com/health"


# ---------------------------------------------------------------------------
# Orgs commands
# ---------------------------------------------------------------------------


class TestOrgsList:
    @patch("kctl_glitchtip.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_list_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["orgs", "list", "--help"])
        assert result.exit_code == 0

    def test_list_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        from kctl_glitchtip.commands.orgs import list_

        actx = _make_actx(json_mode=True)
        actx._client.get_list.return_value = MOCK_ORGS
        ctx = _make_ctx(actx)

        list_(ctx)
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["slug"] == "kodemeio"
