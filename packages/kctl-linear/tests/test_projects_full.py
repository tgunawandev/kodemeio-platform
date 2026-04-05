"""Full tests for projects commands."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_linear.cli import app
from kctl_linear.core.client import LinearClient

runner = CliRunner()

SAMPLE_PROJECT = {
    "id": "proj-1",
    "name": "Q2 Roadmap",
    "state": "started",
    "progress": 0.45,
    "url": "https://linear.app/kodeme/project/q2-roadmap",
    "lead": {"name": "Alice"},
    "startDate": "2026-03-01",
    "targetDate": "2026-06-30",
    "description": "Main roadmap for Q2 2026.",
    "teams": {"nodes": [{"name": "Kodeme"}]},
    "members": {"nodes": [{"name": "Alice"}, {"name": "Bob"}]},
    "projectMilestones": {
        "nodes": [
            {"name": "M1: Foundation", "targetDate": "2026-04-15"},
            {"name": "M2: Launch", "targetDate": "2026-06-01"},
        ]
    },
    "issues": {
        "nodes": [
            {
                "identifier": "KOD-1",
                "title": "Setup CI",
                "state": {"name": "Done"},
                "assignee": {"name": "Alice"},
            },
            {
                "identifier": "KOD-2",
                "title": "Write docs",
                "state": {"name": "In Progress"},
                "assignee": None,
            },
        ]
    },
}

SAMPLE_PROJECT_MINIMAL = {
    "id": "proj-2",
    "name": "Side Project",
    "state": "planned",
    "progress": 0.0,
    "url": "https://linear.app/kodeme/project/side",
    "lead": None,
    "startDate": None,
    "targetDate": None,
    "description": None,
    "teams": {"nodes": []},
    "members": {"nodes": []},
    "projectMilestones": {"nodes": []},
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


class TestProjectsList:
    def test_list_returns_projects(self, mock_client: MagicMock):
        mock_client.query.return_value = {"projects": {"nodes": [SAMPLE_PROJECT]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["projects", "list"])
        assert result.exit_code == 0

    def test_list_empty(self, mock_client: MagicMock):
        mock_client.query.return_value = {"projects": {"nodes": []}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["projects", "list"])
        assert result.exit_code == 0

    def test_list_multiple_projects(self, mock_client: MagicMock):
        mock_client.query.return_value = {"projects": {"nodes": [SAMPLE_PROJECT, SAMPLE_PROJECT_MINIMAL]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["projects", "list"])
        assert result.exit_code == 0

    def test_list_json_output(self, mock_client: MagicMock):
        mock_client.query.return_value = {"projects": {"nodes": [SAMPLE_PROJECT]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["--json", "projects", "list"])
        assert result.exit_code == 0

    def test_list_no_lead(self, mock_client: MagicMock):
        mock_client.query.return_value = {"projects": {"nodes": [SAMPLE_PROJECT_MINIMAL]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["projects", "list"])
        assert result.exit_code == 0

    def test_list_null_progress(self, mock_client: MagicMock):
        project = {**SAMPLE_PROJECT, "progress": None}
        mock_client.query.return_value = {"projects": {"nodes": [project]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["projects", "list"])
        assert result.exit_code == 0

    def test_list_null_target_date(self, mock_client: MagicMock):
        project = {**SAMPLE_PROJECT, "targetDate": None}
        mock_client.query.return_value = {"projects": {"nodes": [project]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["projects", "list"])
        assert result.exit_code == 0


class TestProjectsShow:
    def test_show_full(self, mock_client: MagicMock):
        mock_client.query.return_value = {"project": SAMPLE_PROJECT}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["projects", "show", "proj-1"])
        assert result.exit_code == 0
        call_args = mock_client.query.call_args
        assert call_args[0][1]["id"] == "proj-1"

    def test_show_json_output(self, mock_client: MagicMock):
        mock_client.query.return_value = {"project": SAMPLE_PROJECT}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["--json", "projects", "show", "proj-1"])
        assert result.exit_code == 0

    def test_show_minimal_project(self, mock_client: MagicMock):
        mock_client.query.return_value = {"project": SAMPLE_PROJECT_MINIMAL}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["projects", "show", "proj-2"])
        assert result.exit_code == 0

    def test_show_no_description(self, mock_client: MagicMock):
        project = {**SAMPLE_PROJECT, "description": None}
        mock_client.query.return_value = {"project": project}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["projects", "show", "proj-1"])
        assert result.exit_code == 0

    def test_show_no_milestones(self, mock_client: MagicMock):
        project = {**SAMPLE_PROJECT, "projectMilestones": {"nodes": []}}
        mock_client.query.return_value = {"project": project}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["projects", "show", "proj-1"])
        assert result.exit_code == 0

    def test_show_no_issues(self, mock_client: MagicMock):
        project = {**SAMPLE_PROJECT, "issues": {"nodes": []}}
        mock_client.query.return_value = {"project": project}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["projects", "show", "proj-1"])
        assert result.exit_code == 0

    def test_show_no_lead(self, mock_client: MagicMock):
        project = {**SAMPLE_PROJECT, "lead": None}
        mock_client.query.return_value = {"project": project}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["projects", "show", "proj-1"])
        assert result.exit_code == 0

    def test_show_null_dates(self, mock_client: MagicMock):
        project = {**SAMPLE_PROJECT, "startDate": None, "targetDate": None}
        mock_client.query.return_value = {"project": project}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["projects", "show", "proj-1"])
        assert result.exit_code == 0

    def test_show_issue_no_assignee(self, mock_client: MagicMock):
        project = {
            **SAMPLE_PROJECT,
            "issues": {
                "nodes": [{"identifier": "KOD-3", "title": "No owner", "state": {"name": "Todo"}, "assignee": None}]
            },
        }
        mock_client.query.return_value = {"project": project}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["projects", "show", "proj-1"])
        assert result.exit_code == 0

    def test_show_no_teams(self, mock_client: MagicMock):
        project = {**SAMPLE_PROJECT, "teams": {"nodes": []}}
        mock_client.query.return_value = {"project": project}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["projects", "show", "proj-1"])
        assert result.exit_code == 0

    def test_show_no_members(self, mock_client: MagicMock):
        project = {**SAMPLE_PROJECT, "members": {"nodes": []}}
        mock_client.query.return_value = {"project": project}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["projects", "show", "proj-1"])
        assert result.exit_code == 0
