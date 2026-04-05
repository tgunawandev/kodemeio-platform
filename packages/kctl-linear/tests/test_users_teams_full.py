"""Full tests for users and teams commands."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from kctl_lib.output import Output
from typer.testing import CliRunner

from kctl_linear.cli import app
from kctl_linear.core.callbacks import AppContext
from kctl_linear.core.client import LinearClient

runner = CliRunner()

SAMPLE_USER = {
    "id": "user-1",
    "name": "Alice",
    "email": "alice@kodeme.io",
    "admin": True,
    "active": True,
}

SAMPLE_USER_INACTIVE = {
    "id": "user-2",
    "name": "Bob",
    "email": "bob@kodeme.io",
    "admin": False,
    "active": False,
}

SAMPLE_TEAM = {
    "id": "team-1",
    "key": "KOD",
    "name": "Kodeme",
    "description": "Main engineering team",
    "timezone": "Asia/Jakarta",
    "members": {
        "nodes": [
            {"name": "Alice", "email": "alice@kodeme.io", "active": True},
            {"name": "Bob", "email": "bob@kodeme.io", "active": False},
        ]
    },
    "states": {
        "nodes": [
            {"name": "Todo", "type": "unstarted", "color": "#aaa", "position": 0},
            {"name": "In Progress", "type": "started", "color": "#f0f", "position": 1},
            {"name": "Done", "type": "completed", "color": "#0f0", "position": 2},
        ]
    },
    "labels": {
        "nodes": [
            {"name": "bug", "color": "#f00"},
            {"name": "feature", "color": "#00f"},
        ]
    },
}

SAMPLE_TEAM_MINIMAL = {
    "id": "team-2",
    "key": "OPS",
    "name": "Ops",
    "description": None,
    "timezone": "",
    "members": {"nodes": []},
    "states": {"nodes": []},
    "labels": {"nodes": []},
}


def make_context(mock_client: MagicMock) -> AppContext:
    ctx = AppContext(quiet=True)
    ctx._client = mock_client
    ctx._output = Output(json_mode=False, quiet=True, format="pretty")
    return ctx


def make_json_context(mock_client: MagicMock) -> AppContext:
    ctx = AppContext(json_mode=True, quiet=True)
    ctx._client = mock_client
    ctx._output = Output(json_mode=True, quiet=True, format="json")
    return ctx


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock(spec=LinearClient)
    client.viewer.return_value = {
        "id": "user-123",
        "name": "Test User",
        "email": "test@kodeme.io",
        "admin": False,
        "active": True,
    }
    return client


# ── Users ──────────────────────────────────────────────────────────────────────


class TestUsersList:
    def test_list_users(self, mock_client: MagicMock):
        mock_client.query.return_value = {"users": {"nodes": [SAMPLE_USER, SAMPLE_USER_INACTIVE]}}
        result = runner.invoke(app, ["users", "list"], obj=make_context(mock_client))
        assert result.exit_code == 0

    def test_list_empty(self, mock_client: MagicMock):
        mock_client.query.return_value = {"users": {"nodes": []}}
        result = runner.invoke(app, ["users", "list"], obj=make_context(mock_client))
        assert result.exit_code == 0

    def test_list_json_output(self, mock_client: MagicMock):
        mock_client.query.return_value = {"users": {"nodes": [SAMPLE_USER]}}
        result = runner.invoke(app, ["--json", "users", "list"], obj=make_json_context(mock_client))
        assert result.exit_code == 0

    def test_list_admin_user(self, mock_client: MagicMock):
        mock_client.query.return_value = {"users": {"nodes": [SAMPLE_USER]}}
        result = runner.invoke(app, ["users", "list"], obj=make_context(mock_client))
        assert result.exit_code == 0

    def test_list_inactive_user(self, mock_client: MagicMock):
        mock_client.query.return_value = {"users": {"nodes": [SAMPLE_USER_INACTIVE]}}
        result = runner.invoke(app, ["users", "list"], obj=make_context(mock_client))
        assert result.exit_code == 0

    def test_list_missing_active_field_defaults_true(self, mock_client: MagicMock):
        user = {"id": "u3", "name": "Charlie", "email": "c@kodeme.io", "admin": False}
        mock_client.query.return_value = {"users": {"nodes": [user]}}
        result = runner.invoke(app, ["users", "list"], obj=make_context(mock_client))
        assert result.exit_code == 0


class TestUsersMe:
    def test_me_shows_viewer(self, mock_client: MagicMock):
        result = runner.invoke(app, ["users", "me"], obj=make_context(mock_client))
        assert result.exit_code == 0
        mock_client.viewer.assert_called_once()

    def test_me_json_output(self, mock_client: MagicMock):
        result = runner.invoke(app, ["--json", "users", "me"], obj=make_json_context(mock_client))
        assert result.exit_code == 0
        mock_client.viewer.assert_called_once()

    def test_me_admin_user(self, mock_client: MagicMock):
        mock_client.viewer.return_value = {
            "id": "user-admin",
            "name": "Admin",
            "email": "admin@kodeme.io",
            "admin": True,
            "active": True,
        }
        result = runner.invoke(app, ["users", "me"], obj=make_context(mock_client))
        assert result.exit_code == 0

    def test_me_inactive_user(self, mock_client: MagicMock):
        mock_client.viewer.return_value = {
            "id": "user-old",
            "name": "Former Member",
            "email": "old@kodeme.io",
            "admin": False,
            "active": False,
        }
        result = runner.invoke(app, ["users", "me"], obj=make_context(mock_client))
        assert result.exit_code == 0


# ── Teams ──────────────────────────────────────────────────────────────────────


class TestTeamsList:
    def test_list_teams(self, mock_client: MagicMock):
        mock_client.query.return_value = {"teams": {"nodes": [SAMPLE_TEAM, SAMPLE_TEAM_MINIMAL]}}
        result = runner.invoke(app, ["teams", "list"], obj=make_context(mock_client))
        assert result.exit_code == 0

    def test_list_empty(self, mock_client: MagicMock):
        mock_client.query.return_value = {"teams": {"nodes": []}}
        result = runner.invoke(app, ["teams", "list"], obj=make_context(mock_client))
        assert result.exit_code == 0

    def test_list_json_output(self, mock_client: MagicMock):
        mock_client.query.return_value = {"teams": {"nodes": [SAMPLE_TEAM]}}
        result = runner.invoke(app, ["--json", "teams", "list"], obj=make_json_context(mock_client))
        assert result.exit_code == 0

    def test_list_member_count(self, mock_client: MagicMock):
        mock_client.query.return_value = {"teams": {"nodes": [SAMPLE_TEAM]}}
        result = runner.invoke(app, ["teams", "list"], obj=make_context(mock_client))
        assert result.exit_code == 0

    def test_list_no_timezone(self, mock_client: MagicMock):
        team = {**SAMPLE_TEAM_MINIMAL, "timezone": ""}
        mock_client.query.return_value = {"teams": {"nodes": [team]}}
        result = runner.invoke(app, ["teams", "list"], obj=make_context(mock_client))
        assert result.exit_code == 0


class TestTeamsShow:
    def test_show_full_team(self, mock_client: MagicMock):
        mock_client.query.return_value = {"team": SAMPLE_TEAM}
        result = runner.invoke(app, ["teams", "show", "team-1"], obj=make_context(mock_client))
        assert result.exit_code == 0
        call_args = mock_client.query.call_args
        assert call_args[0][1]["id"] == "team-1"

    def test_show_json_output(self, mock_client: MagicMock):
        mock_client.query.return_value = {"team": SAMPLE_TEAM}
        result = runner.invoke(app, ["--json", "teams", "show", "team-1"], obj=make_json_context(mock_client))
        assert result.exit_code == 0

    def test_show_minimal_team(self, mock_client: MagicMock):
        mock_client.query.return_value = {"team": SAMPLE_TEAM_MINIMAL}
        result = runner.invoke(app, ["teams", "show", "team-2"], obj=make_context(mock_client))
        assert result.exit_code == 0

    def test_show_no_members(self, mock_client: MagicMock):
        team = {**SAMPLE_TEAM, "members": {"nodes": []}}
        mock_client.query.return_value = {"team": team}
        result = runner.invoke(app, ["teams", "show", "team-1"], obj=make_context(mock_client))
        assert result.exit_code == 0

    def test_show_no_states(self, mock_client: MagicMock):
        team = {**SAMPLE_TEAM, "states": {"nodes": []}}
        mock_client.query.return_value = {"team": team}
        result = runner.invoke(app, ["teams", "show", "team-1"], obj=make_context(mock_client))
        assert result.exit_code == 0

    def test_show_no_labels(self, mock_client: MagicMock):
        team = {**SAMPLE_TEAM, "labels": {"nodes": []}}
        mock_client.query.return_value = {"team": team}
        result = runner.invoke(app, ["teams", "show", "team-1"], obj=make_context(mock_client))
        assert result.exit_code == 0

    def test_show_states_sorted_by_position(self, mock_client: MagicMock):
        # States given out of order; should still render without error
        team = {
            **SAMPLE_TEAM,
            "states": {
                "nodes": [
                    {"name": "Done", "type": "completed", "color": "#0f0", "position": 2},
                    {"name": "Todo", "type": "unstarted", "color": "#aaa", "position": 0},
                    {"name": "In Progress", "type": "started", "color": "#f0f", "position": 1},
                ]
            },
        }
        mock_client.query.return_value = {"team": team}
        result = runner.invoke(app, ["teams", "show", "team-1"], obj=make_context(mock_client))
        assert result.exit_code == 0

    def test_show_no_description(self, mock_client: MagicMock):
        team = {**SAMPLE_TEAM, "description": None}
        mock_client.query.return_value = {"team": team}
        result = runner.invoke(app, ["teams", "show", "team-1"], obj=make_context(mock_client))
        assert result.exit_code == 0
