"""Full tests for cycles commands."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_linear.cli import app
from kctl_linear.core.client import LinearClient

runner = CliRunner()

SAMPLE_ISSUE = {
    "identifier": "KOD-1",
    "title": "Fix the login bug",
    "priority": 2,
    "estimate": 3,
    "state": {"name": "In Progress"},
    "assignee": {"name": "Alice"},
}

SAMPLE_CYCLE = {
    "id": "cycle-1",
    "number": 5,
    "name": "Sprint 5",
    "startsAt": "2026-03-25T00:00:00Z",
    "endsAt": "2026-04-07T00:00:00Z",
    "progress": 0.6,
    "issues": {"nodes": [SAMPLE_ISSUE]},
}

SAMPLE_CYCLE_NO_NAME = {
    "id": "cycle-2",
    "number": 6,
    "name": None,
    "startsAt": "2026-04-08T00:00:00Z",
    "endsAt": "2026-04-21T00:00:00Z",
    "progress": 0.0,
    "issues": {"nodes": []},
}


@contextmanager
def mock_linear_client(client: MagicMock):
    with patch(
        "kctl_linear.core.callbacks.AppContext.client",
        new_callable=PropertyMock,
        return_value=client,
    ):
        yield client


@pytest.fixture
def mock_client() -> MagicMock:
    return MagicMock(spec=LinearClient)


class TestCyclesCurrent:
    def test_current_with_active_cycle(self, mock_client: MagicMock):
        mock_client.query.return_value = {"cycles": {"nodes": [SAMPLE_CYCLE]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "current"])
        assert result.exit_code == 0

    def test_current_no_active_cycle(self, mock_client: MagicMock):
        mock_client.query.return_value = {"cycles": {"nodes": []}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "current"])
        assert result.exit_code == 0

    def test_current_with_team_flag(self, mock_client: MagicMock):
        mock_client.query.return_value = {"cycles": {"nodes": [SAMPLE_CYCLE]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "current", "--team", "KOD"])
        assert result.exit_code == 0
        call_args = mock_client.query.call_args
        assert call_args[0][1]["teamKey"] == "KOD"

    def test_current_json_output(self, mock_client: MagicMock):
        mock_client.query.return_value = {"cycles": {"nodes": [SAMPLE_CYCLE]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["--json", "cycles", "current"])
        assert result.exit_code == 0

    def test_current_unnamed_cycle(self, mock_client: MagicMock):
        mock_client.query.return_value = {"cycles": {"nodes": [SAMPLE_CYCLE_NO_NAME]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "current"])
        assert result.exit_code == 0

    def test_current_issue_no_assignee(self, mock_client: MagicMock):
        cycle = {**SAMPLE_CYCLE, "issues": {"nodes": [{**SAMPLE_ISSUE, "assignee": None}]}}
        mock_client.query.return_value = {"cycles": {"nodes": [cycle]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "current"])
        assert result.exit_code == 0

    def test_current_null_progress(self, mock_client: MagicMock):
        cycle = {**SAMPLE_CYCLE, "progress": None}
        mock_client.query.return_value = {"cycles": {"nodes": [cycle]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "current"])
        assert result.exit_code == 0

    def test_current_null_dates(self, mock_client: MagicMock):
        cycle = {**SAMPLE_CYCLE, "startsAt": None, "endsAt": None}
        mock_client.query.return_value = {"cycles": {"nodes": [cycle]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "current"])
        assert result.exit_code == 0

    def test_current_no_issues(self, mock_client: MagicMock):
        cycle = {**SAMPLE_CYCLE, "issues": {"nodes": []}}
        mock_client.query.return_value = {"cycles": {"nodes": [cycle]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "current"])
        assert result.exit_code == 0


class TestCyclesList:
    def test_list_cycles(self, mock_client: MagicMock):
        mock_client.query.return_value = {"cycles": {"nodes": [SAMPLE_CYCLE, SAMPLE_CYCLE_NO_NAME]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "list"])
        assert result.exit_code == 0

    def test_list_empty(self, mock_client: MagicMock):
        mock_client.query.return_value = {"cycles": {"nodes": []}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "list"])
        assert result.exit_code == 0

    def test_list_with_team(self, mock_client: MagicMock):
        mock_client.query.return_value = {"cycles": {"nodes": [SAMPLE_CYCLE]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "list", "--team", "KOD"])
        assert result.exit_code == 0
        call_args = mock_client.query.call_args
        assert call_args[0][1]["teamKey"] == "KOD"

    def test_list_with_limit(self, mock_client: MagicMock):
        mock_client.query.return_value = {"cycles": {"nodes": [SAMPLE_CYCLE]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "list", "--limit", "5"])
        assert result.exit_code == 0
        call_args = mock_client.query.call_args
        assert call_args[0][1]["first"] == 5

    def test_list_json_output(self, mock_client: MagicMock):
        mock_client.query.return_value = {"cycles": {"nodes": [SAMPLE_CYCLE]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["--json", "cycles", "list"])
        assert result.exit_code == 0

    def test_list_unnamed_cycle_fallback(self, mock_client: MagicMock):
        mock_client.query.return_value = {"cycles": {"nodes": [SAMPLE_CYCLE_NO_NAME]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "list"])
        assert result.exit_code == 0

    def test_list_null_progress(self, mock_client: MagicMock):
        cycle = {**SAMPLE_CYCLE, "progress": None}
        mock_client.query.return_value = {"cycles": {"nodes": [cycle]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "list"])
        assert result.exit_code == 0

    def test_list_null_dates(self, mock_client: MagicMock):
        cycle = {**SAMPLE_CYCLE, "startsAt": None, "endsAt": None}
        mock_client.query.return_value = {"cycles": {"nodes": [cycle]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "list"])
        assert result.exit_code == 0


class TestCyclesShow:
    def test_show_cycle(self, mock_client: MagicMock):
        mock_client.query.return_value = {"cycle": SAMPLE_CYCLE}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "show", "cycle-1"])
        assert result.exit_code == 0
        call_args = mock_client.query.call_args
        assert call_args[0][1]["id"] == "cycle-1"

    def test_show_json_output(self, mock_client: MagicMock):
        mock_client.query.return_value = {"cycle": SAMPLE_CYCLE}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["--json", "cycles", "show", "cycle-1"])
        assert result.exit_code == 0

    def test_show_no_issues(self, mock_client: MagicMock):
        cycle = {**SAMPLE_CYCLE, "issues": {"nodes": []}}
        mock_client.query.return_value = {"cycle": cycle}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "show", "cycle-1"])
        assert result.exit_code == 0

    def test_show_unnamed_cycle(self, mock_client: MagicMock):
        mock_client.query.return_value = {"cycle": SAMPLE_CYCLE_NO_NAME}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "show", "cycle-2"])
        assert result.exit_code == 0

    def test_show_issue_no_estimate(self, mock_client: MagicMock):
        cycle = {**SAMPLE_CYCLE, "issues": {"nodes": [{**SAMPLE_ISSUE, "estimate": None}]}}
        mock_client.query.return_value = {"cycle": cycle}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "show", "cycle-1"])
        assert result.exit_code == 0

    def test_show_issue_no_assignee(self, mock_client: MagicMock):
        cycle = {**SAMPLE_CYCLE, "issues": {"nodes": [{**SAMPLE_ISSUE, "assignee": None}]}}
        mock_client.query.return_value = {"cycle": cycle}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "show", "cycle-1"])
        assert result.exit_code == 0

    def test_show_null_progress(self, mock_client: MagicMock):
        cycle = {**SAMPLE_CYCLE, "progress": None}
        mock_client.query.return_value = {"cycle": cycle}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "show", "cycle-1"])
        assert result.exit_code == 0

    def test_show_null_dates(self, mock_client: MagicMock):
        cycle = {**SAMPLE_CYCLE, "startsAt": None, "endsAt": None}
        mock_client.query.return_value = {"cycle": cycle}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "show", "cycle-1"])
        assert result.exit_code == 0


class TestCyclesStats:
    def test_stats_with_cycles(self, mock_client: MagicMock):
        mock_client.query.return_value = {"cycles": {"nodes": [SAMPLE_CYCLE, SAMPLE_CYCLE_NO_NAME]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "stats"])
        assert result.exit_code == 0

    def test_stats_empty(self, mock_client: MagicMock):
        mock_client.query.return_value = {"cycles": {"nodes": []}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "stats"])
        assert result.exit_code == 0

    def test_stats_with_team(self, mock_client: MagicMock):
        mock_client.query.return_value = {"cycles": {"nodes": [SAMPLE_CYCLE]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "stats", "--team", "KOD"])
        assert result.exit_code == 0
        call_args = mock_client.query.call_args
        assert call_args[0][1]["teamKey"] == "KOD"

    def test_stats_json_output(self, mock_client: MagicMock):
        mock_client.query.return_value = {"cycles": {"nodes": [SAMPLE_CYCLE]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["--json", "cycles", "stats"])
        assert result.exit_code == 0

    def test_stats_null_progress(self, mock_client: MagicMock):
        cycle = {**SAMPLE_CYCLE, "progress": None}
        mock_client.query.return_value = {"cycles": {"nodes": [cycle]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "stats"])
        assert result.exit_code == 0

    def test_stats_unnamed_cycle(self, mock_client: MagicMock):
        mock_client.query.return_value = {"cycles": {"nodes": [SAMPLE_CYCLE_NO_NAME]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["cycles", "stats"])
        assert result.exit_code == 0
