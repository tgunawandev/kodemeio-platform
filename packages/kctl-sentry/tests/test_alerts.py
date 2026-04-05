"""Tests for alerts, releases, and teams commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_sentry.cli import app

runner = CliRunner()


def _mock_resolve(*args, **kwargs):  # type: ignore[no-untyped-def]
    return ("https://sentry.io", "test-token", "kodemeio", "web-app")


def _make_mock_client() -> MagicMock:
    client = MagicMock()
    client.organization = "kodemeio"
    client.default_project = "web-app"
    client.resolve_project.return_value = "web-app"
    return client


MOCK_ALERT_RULES = [
    {
        "id": "101",
        "name": "High Error Rate",
        "status": "active",
        "projects": ["web-app"],
        "owner": {"name": "dev-team"},
    },
    {
        "id": "102",
        "name": "Spike Detection",
        "status": "active",
        "projects": ["api-app"],
        "owner": None,
    },
]

MOCK_RELEASES = [
    {
        "version": "1.2.3",
        "projects": [{"slug": "web-app"}],
        "newGroups": 5,
        "deployCount": 2,
        "dateCreated": "2026-03-28T10:00:00Z",
    },
    {
        "version": "1.2.2",
        "projects": [{"slug": "api-app"}],
        "newGroups": 0,
        "deployCount": 1,
        "dateCreated": "2026-03-20T10:00:00Z",
    },
]

MOCK_TEAMS = [
    {"id": "t1", "slug": "dev-team", "name": "Dev Team", "memberCount": 4},
    {"id": "t2", "slug": "ops-team", "name": "Ops Team", "memberCount": 2},
]


# ---------------------------------------------------------------------------
# Alerts commands
# ---------------------------------------------------------------------------


class TestAlertsList:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_list_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["alerts", "list", "--help"])
        assert result.exit_code == 0

    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_list_project_option(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["alerts", "list", "--help"])
        assert "--project" in result.output

    def test_list_json_direct(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Direct invocation with mocked AppContext."""
        from kctl_lib.output import Output

        from kctl_sentry.core.callbacks import AppContext

        ctx_obj = AppContext(quiet=True, json_mode=True)
        ctx_obj._output = Output(json_mode=True, quiet=True, format="json")
        mock_client = _make_mock_client()
        mock_client.org_get.return_value = MOCK_ALERT_RULES
        ctx_obj._client = mock_client

        ctx = MagicMock()
        ctx.obj = ctx_obj

        from kctl_sentry.commands.alerts import list_

        list_(ctx, project=None)
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["id"] == "101"

    def test_list_with_project_filter(self, capsys: pytest.CaptureFixture[str]) -> None:
        """When project is given, uses project_get instead of org_get."""
        from kctl_lib.output import Output

        from kctl_sentry.core.callbacks import AppContext

        ctx_obj = AppContext(quiet=True, json_mode=True)
        ctx_obj._output = Output(json_mode=True, quiet=True, format="json")
        mock_client = _make_mock_client()
        mock_client.project_get.return_value = [MOCK_ALERT_RULES[0]]
        ctx_obj._client = mock_client

        ctx = MagicMock()
        ctx.obj = ctx_obj

        from kctl_sentry.commands.alerts import list_

        list_(ctx, project="web-app")
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 1
        mock_client.project_get.assert_called_once_with("web-app", "/rules/")


class TestAlertsShow:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_show_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["alerts", "show", "--help"])
        assert result.exit_code == 0

    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_show_requires_project(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["alerts", "show", "--help"])
        assert "--project" in result.output

    def test_show_direct(self, capsys: pytest.CaptureFixture[str]) -> None:
        from kctl_lib.output import Output

        from kctl_sentry.core.callbacks import AppContext

        ctx_obj = AppContext(quiet=True, json_mode=True)
        ctx_obj._output = Output(json_mode=True, quiet=True, format="json")
        mock_client = _make_mock_client()
        mock_client.project_get.return_value = {
            "id": "101",
            "name": "High Error Rate",
            "status": "active",
            "conditions": [{"name": "An event is seen", "id": "evt"}],
            "actions": [{"name": "Send email", "id": "email"}],
            "frequency": 30,
            "dateCreated": "2026-01-01T00:00:00Z",
        }
        ctx_obj._client = mock_client

        ctx = MagicMock()
        ctx.obj = ctx_obj

        from kctl_sentry.commands.alerts import show

        show(ctx, rule_id="101", project="web-app")
        data = json.loads(capsys.readouterr().out)
        assert data["id"] == "101"
        assert data["name"] == "High Error Rate"


class TestAlertsCreate:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_create_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["alerts", "create", "--help"])
        assert result.exit_code == 0

    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_create_options(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["alerts", "create", "--help"])
        assert "--name" in result.output
        assert "--threshold" in result.output

    def test_create_direct(self, capsys: pytest.CaptureFixture[str]) -> None:
        from kctl_lib.output import Output

        from kctl_sentry.core.callbacks import AppContext

        ctx_obj = AppContext(quiet=True, json_mode=True)
        ctx_obj._output = Output(json_mode=True, quiet=True, format="json")
        mock_client = _make_mock_client()
        mock_client.org_post.return_value = {"id": "103", "name": "New Alert"}
        ctx_obj._client = mock_client

        ctx = MagicMock()
        ctx.obj = ctx_obj

        from kctl_sentry.commands.alerts import create

        create(ctx, project="web-app", name="New Alert", metric="events", threshold=100, time_window=60)
        data = json.loads(capsys.readouterr().out)
        assert data["id"] == "103"
        mock_client.org_post.assert_called_once()


# ---------------------------------------------------------------------------
# Releases commands
# ---------------------------------------------------------------------------


class TestReleasesList:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_list_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["releases", "list", "--help"])
        assert result.exit_code == 0

    def test_list_direct(self, capsys: pytest.CaptureFixture[str]) -> None:
        from kctl_lib.output import Output

        from kctl_sentry.core.callbacks import AppContext

        ctx_obj = AppContext(quiet=True, json_mode=True)
        ctx_obj._output = Output(json_mode=True, quiet=True, format="json")
        mock_client = _make_mock_client()
        mock_client.org_get.return_value = MOCK_RELEASES
        ctx_obj._client = mock_client

        ctx = MagicMock()
        ctx.obj = ctx_obj

        from kctl_sentry.commands.releases import list_

        list_(ctx, project=None, limit=20)
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["version"] == "1.2.3"


class TestReleasesCreate:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_create_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["releases", "create", "--help"])
        assert result.exit_code == 0

    def test_create_direct(self, capsys: pytest.CaptureFixture[str]) -> None:
        from kctl_lib.output import Output

        from kctl_sentry.core.callbacks import AppContext

        ctx_obj = AppContext(quiet=True)
        ctx_obj._output = Output(json_mode=False, quiet=True, format="pretty")
        mock_client = _make_mock_client()
        mock_client.org_post.return_value = {
            "version": "1.3.0",
            "projects": [{"slug": "web-app"}],
        }
        ctx_obj._client = mock_client

        ctx = MagicMock()
        ctx.obj = ctx_obj

        from kctl_sentry.commands.releases import create

        create(ctx, version="1.3.0", project="web-app")
        mock_client.org_post.assert_called_once()
        args = mock_client.org_post.call_args
        assert args[0][0] == "/releases/"
        assert args[1]["json"]["version"] == "1.3.0"


class TestReleasesShow:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_show_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["releases", "show", "--help"])
        assert result.exit_code == 0

    def test_show_direct(self, capsys: pytest.CaptureFixture[str]) -> None:
        from kctl_lib.output import Output

        from kctl_sentry.core.callbacks import AppContext

        ctx_obj = AppContext(quiet=True, json_mode=True)
        ctx_obj._output = Output(json_mode=True, quiet=True, format="json")
        mock_client = _make_mock_client()
        mock_client.org_get.side_effect = [
            {
                "version": "1.2.3",
                "projects": [{"slug": "web-app"}],
                "newGroups": 5,
                "deployCount": 2,
                "dateCreated": "2026-03-28T10:00:00Z",
                "firstEvent": "2026-03-28T10:05:00Z",
                "lastEvent": "2026-03-29T08:00:00Z",
                "lastCommit": {
                    "id": "abc123def456",
                    "message": "feat: add login",
                    "author": {"name": "dev1"},
                },
            },
            [],  # resolved issues
        ]
        ctx_obj._client = mock_client

        ctx = MagicMock()
        ctx.obj = ctx_obj

        from kctl_sentry.commands.releases import show

        show(ctx, version="1.2.3")
        data = json.loads(capsys.readouterr().out)
        assert data["release"]["version"] == "1.2.3"


class TestReleasesAssociate:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_associate_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["releases", "associate", "--help"])
        assert result.exit_code == 0

    def test_associate_direct(self) -> None:
        from kctl_lib.output import Output

        from kctl_sentry.core.callbacks import AppContext

        ctx_obj = AppContext(quiet=True)
        ctx_obj._output = Output(json_mode=False, quiet=True, format="pretty")
        mock_client = _make_mock_client()
        mock_client.org_put.return_value = {}
        ctx_obj._client = mock_client

        ctx = MagicMock()
        ctx.obj = ctx_obj

        from kctl_sentry.commands.releases import associate_commits

        associate_commits(ctx, version="1.2.3", commits="kodemeio-odoo@abc123..def456")
        mock_client.org_put.assert_called_once()
        args = mock_client.org_put.call_args
        assert "1.2.3" in args[0][0]


# ---------------------------------------------------------------------------
# Teams commands
# ---------------------------------------------------------------------------


class TestTeamsList:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_list_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["teams", "list", "--help"])
        assert result.exit_code == 0

    def test_list_direct(self, capsys: pytest.CaptureFixture[str]) -> None:
        from kctl_sentry.commands.teams import list_

        from kctl_lib.output import Output

        from kctl_sentry.core.callbacks import AppContext

        ctx_obj = AppContext(quiet=True, json_mode=True)
        ctx_obj._output = Output(json_mode=True, quiet=True, format="json")
        mock_client = _make_mock_client()
        mock_client.org_get.return_value = MOCK_TEAMS
        ctx_obj._client = mock_client

        ctx = MagicMock()
        ctx.obj = ctx_obj

        list_(ctx)
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["slug"] == "dev-team"
