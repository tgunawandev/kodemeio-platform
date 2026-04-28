"""Full tests for issues commands."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_linear.cli import app
from kctl_linear.core.client import LinearClient

runner = CliRunner()

SAMPLE_ISSUE = {
    "id": "issue-1",
    "identifier": "KOD-1",
    "title": "Fix the login bug",
    "priority": 2,
    "priorityLabel": "Medium",
    "estimate": 3,
    "url": "https://linear.app/kodeme/issue/KOD-1",
    "state": {"name": "In Progress", "color": "#f00"},
    "assignee": {"name": "Alice", "email": "alice@kodeme.io"},
    "team": {"name": "Kodeme"},
    "project": {"name": "Q2 Sprint"},
    "cycle": {"name": "Cycle 5"},
    "labels": {"nodes": [{"name": "bug"}, {"name": "frontend"}]},
    "comments": {"nodes": []},
    "description": "The login form fails on mobile safari.",
    "createdAt": "2026-03-01T00:00:00Z",
    "updatedAt": "2026-03-28T00:00:00Z",
}

SAMPLE_ISSUE_2 = {
    "id": "issue-2",
    "identifier": "KOD-2",
    "title": "Add dark mode",
    "priority": 3,
    "state": {"name": "Todo"},
    "assignee": None,
    "createdAt": "2026-03-02T00:00:00Z",
    "updatedAt": "2026-03-28T00:00:00Z",
}


@contextmanager
def mock_linear_client(client: MagicMock):
    """Patch AppContext.client property with a mock LinearClient."""
    with patch(
        "kctl_linear.core.callbacks.AppContext.client",
        new_callable=PropertyMock,
        return_value=client,
    ):
        yield client


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


class TestIssuesList:
    def test_list_empty(self, mock_client: MagicMock):
        mock_client.query.return_value = {"issues": {"nodes": []}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "list"])
        assert result.exit_code == 0

    def test_list_with_issues(self, mock_client: MagicMock):
        mock_client.query.return_value = {"issues": {"nodes": [SAMPLE_ISSUE, SAMPLE_ISSUE_2]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "list"])
        assert result.exit_code == 0

    def test_list_with_team_filter(self, mock_client: MagicMock):
        mock_client.query.return_value = {"issues": {"nodes": [SAMPLE_ISSUE]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "list", "--team", "KOD"])
        assert result.exit_code == 0
        call_args = mock_client.query.call_args
        assert call_args[0][1]["teamKey"] == "KOD"

    def test_list_with_state_filter(self, mock_client: MagicMock):
        mock_client.query.return_value = {"issues": {"nodes": [SAMPLE_ISSUE]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "list", "--state", "In Progress"])
        assert result.exit_code == 0
        call_args = mock_client.query.call_args
        assert call_args[0][1]["state"] == "In Progress"

    def test_list_assignee_me_resolves_viewer(self, mock_client: MagicMock):
        mock_client.query.return_value = {"issues": {"nodes": [SAMPLE_ISSUE]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "list", "--assignee", "me"])
        assert result.exit_code == 0
        mock_client.viewer.assert_called_once()
        call_args = mock_client.query.call_args
        assert call_args[0][1]["assigneeId"] == "user-123"

    def test_list_assignee_by_name_resolves_user(self, mock_client: MagicMock):
        mock_client.query.side_effect = [
            {"users": {"nodes": [{"id": "user-456", "name": "Alice"}]}},
            {"issues": {"nodes": [SAMPLE_ISSUE]}},
        ]
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "list", "--assignee", "Alice"])
        assert result.exit_code == 0

    def test_list_json_output(self, mock_client: MagicMock):
        mock_client.query.return_value = {"issues": {"nodes": [SAMPLE_ISSUE]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["--json", "issues", "list"])
        assert result.exit_code == 0

    def test_list_with_limit(self, mock_client: MagicMock):
        mock_client.query.return_value = {"issues": {"nodes": []}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "list", "--limit", "10"])
        assert result.exit_code == 0
        call_args = mock_client.query.call_args
        assert call_args[0][1]["first"] == 10

    def test_list_assignee_not_found(self, mock_client: MagicMock):
        mock_client.query.return_value = {"users": {"nodes": []}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "list", "--assignee", "Ghost"])
        assert result.exit_code != 0


class TestIssuesShow:
    def test_show_issue(self, mock_client: MagicMock):
        mock_client.query.return_value = {"issue": SAMPLE_ISSUE}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "show", "KOD-1"])
        assert result.exit_code == 0
        call_args = mock_client.query.call_args
        assert call_args[0][1]["id"] == "KOD-1"

    def test_show_with_comments(self, mock_client: MagicMock):
        issue = {
            **SAMPLE_ISSUE,
            "comments": {
                "nodes": [{"user": {"name": "Bob"}, "createdAt": "2026-03-05T00:00:00Z", "body": "Looks good!"}]
            },
        }
        mock_client.query.return_value = {"issue": issue}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "show", "KOD-1"])
        assert result.exit_code == 0

    def test_show_no_description(self, mock_client: MagicMock):
        issue = {**SAMPLE_ISSUE, "description": None, "comments": {"nodes": []}}
        mock_client.query.return_value = {"issue": issue}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "show", "KOD-1"])
        assert result.exit_code == 0

    def test_show_json_output(self, mock_client: MagicMock):
        mock_client.query.return_value = {"issue": SAMPLE_ISSUE}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["--json", "issues", "show", "KOD-1"])
        assert result.exit_code == 0

    def test_show_no_assignee(self, mock_client: MagicMock):
        issue = {**SAMPLE_ISSUE, "assignee": None}
        mock_client.query.return_value = {"issue": issue}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "show", "KOD-1"])
        assert result.exit_code == 0

    def test_show_no_project_no_cycle(self, mock_client: MagicMock):
        issue = {**SAMPLE_ISSUE, "project": None, "cycle": None}
        mock_client.query.return_value = {"issue": issue}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "show", "KOD-1"])
        assert result.exit_code == 0

    def test_show_no_labels(self, mock_client: MagicMock):
        issue = {**SAMPLE_ISSUE, "labels": {"nodes": []}}
        mock_client.query.return_value = {"issue": issue}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "show", "KOD-1"])
        assert result.exit_code == 0

    def test_show_no_team(self, mock_client: MagicMock):
        issue = {**SAMPLE_ISSUE, "team": None}
        mock_client.query.return_value = {"issue": issue}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "show", "KOD-1"])
        assert result.exit_code == 0


class TestIssuesCreate:
    def test_create_success(self, mock_client: MagicMock):
        mock_client.query.side_effect = [
            {"teams": {"nodes": [{"id": "team-1"}]}},
            {
                "issueCreate": {
                    "success": True,
                    "issue": {"identifier": "KOD-3", "title": "New issue", "url": "https://linear.app/i/3"},
                }
            },
        ]
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "create", "--title", "New issue", "--team", "KOD"])
        assert result.exit_code == 0

    def test_create_with_priority(self, mock_client: MagicMock):
        mock_client.query.side_effect = [
            {"teams": {"nodes": [{"id": "team-1"}]}},
            {
                "issueCreate": {
                    "success": True,
                    "issue": {"identifier": "KOD-4", "title": "Urgent", "url": "https://linear.app/i/4"},
                }
            },
        ]
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "create", "--title", "Urgent", "--team", "KOD", "--priority", "1"])
        assert result.exit_code == 0
        call_args = mock_client.query.call_args_list[1]
        assert call_args[0][1]["priority"] == 1

    def test_create_with_assignee_me(self, mock_client: MagicMock):
        mock_client.query.side_effect = [
            {"teams": {"nodes": [{"id": "team-1"}]}},
            {
                "issueCreate": {
                    "success": True,
                    "issue": {"identifier": "KOD-5", "title": "My task", "url": "https://linear.app/i/5"},
                }
            },
        ]
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "create", "--title", "My task", "--team", "KOD", "--assignee", "me"])
        assert result.exit_code == 0
        mock_client.viewer.assert_called()

    def test_create_team_not_found(self, mock_client: MagicMock):
        mock_client.query.return_value = {"teams": {"nodes": []}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "create", "--title", "Oops", "--team", "MISSING"])
        assert result.exit_code != 0

    def test_create_json_output(self, mock_client: MagicMock):
        mock_client.query.side_effect = [
            {"teams": {"nodes": [{"id": "team-1"}]}},
            {
                "issueCreate": {
                    "success": True,
                    "issue": {"identifier": "KOD-6", "title": "JSON test", "url": "https://linear.app/i/6"},
                }
            },
        ]
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["--json", "issues", "create", "--title", "JSON test", "--team", "KOD"])
        assert result.exit_code == 0

    def test_create_with_description(self, mock_client: MagicMock):
        mock_client.query.side_effect = [
            {"teams": {"nodes": [{"id": "team-1"}]}},
            {
                "issueCreate": {
                    "success": True,
                    "issue": {"identifier": "KOD-7", "title": "Described", "url": "https://linear.app/i/7"},
                }
            },
        ]
        with mock_linear_client(mock_client):
            result = runner.invoke(
                app,
                ["issues", "create", "--title", "Described", "--team", "KOD", "--desc", "Details here"],
            )
        assert result.exit_code == 0
        call_args = mock_client.query.call_args_list[1]
        assert call_args[0][1]["description"] == "Details here"

    def test_create_with_named_assignee(self, mock_client: MagicMock):
        mock_client.query.side_effect = [
            {"teams": {"nodes": [{"id": "team-1"}]}},
            {"users": {"nodes": [{"id": "user-999", "name": "Carol"}]}},
            {
                "issueCreate": {
                    "success": True,
                    "issue": {"identifier": "KOD-8", "title": "Carol task", "url": "https://linear.app/i/8"},
                }
            },
        ]
        with mock_linear_client(mock_client):
            result = runner.invoke(
                app,
                ["issues", "create", "--title", "Carol task", "--team", "KOD", "--assignee", "Carol"],
            )
        assert result.exit_code == 0


class TestIssuesUpdate:
    def test_update_title(self, mock_client: MagicMock):
        mock_client.query.return_value = {
            "issueUpdate": {"success": True, "issue": {"identifier": "KOD-1", "title": "Updated title"}}
        }
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "update", "KOD-1", "--title", "Updated title"])
        assert result.exit_code == 0
        call_args = mock_client.query.call_args
        assert call_args[0][1]["title"] == "Updated title"

    def test_update_priority(self, mock_client: MagicMock):
        mock_client.query.return_value = {
            "issueUpdate": {"success": True, "issue": {"identifier": "KOD-1", "title": "Bug"}}
        }
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "update", "KOD-1", "--priority", "1"])
        assert result.exit_code == 0
        call_args = mock_client.query.call_args
        assert call_args[0][1]["priority"] == 1

    def test_update_assignee_me(self, mock_client: MagicMock):
        mock_client.query.return_value = {
            "issueUpdate": {"success": True, "issue": {"identifier": "KOD-1", "title": "Bug"}}
        }
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "update", "KOD-1", "--assignee", "me"])
        assert result.exit_code == 0
        mock_client.viewer.assert_called()

    def test_update_assignee_by_name(self, mock_client: MagicMock):
        mock_client.query.side_effect = [
            {"users": {"nodes": [{"id": "user-789", "name": "Bob"}]}},
            {"issueUpdate": {"success": True, "issue": {"identifier": "KOD-1", "title": "Bug"}}},
        ]
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "update", "KOD-1", "--assignee", "Bob"])
        assert result.exit_code == 0

    def test_update_json_output(self, mock_client: MagicMock):
        mock_client.query.return_value = {
            "issueUpdate": {"success": True, "issue": {"identifier": "KOD-1", "title": "Bug"}}
        }
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["--json", "issues", "update", "KOD-1", "--priority", "2"])
        assert result.exit_code == 0

    def test_update_description(self, mock_client: MagicMock):
        mock_client.query.return_value = {
            "issueUpdate": {"success": True, "issue": {"identifier": "KOD-1", "title": "Bug"}}
        }
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "update", "KOD-1", "--desc", "New description"])
        assert result.exit_code == 0
        call_args = mock_client.query.call_args
        assert call_args[0][1]["description"] == "New description"

    def test_update_id_always_set(self, mock_client: MagicMock):
        mock_client.query.return_value = {
            "issueUpdate": {"success": True, "issue": {"identifier": "KOD-99", "title": "X"}}
        }
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "update", "KOD-99", "--title", "X"])
        assert result.exit_code == 0
        call_args = mock_client.query.call_args
        assert call_args[0][1]["id"] == "KOD-99"


class TestIssuesComment:
    def test_comment_success(self, mock_client: MagicMock):
        mock_client.query.return_value = {"commentCreate": {"success": True}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "comment", "KOD-1", "--body", "This looks good!"])
        assert result.exit_code == 0
        call_args = mock_client.query.call_args
        assert call_args[0][1]["issueId"] == "KOD-1"
        assert call_args[0][1]["body"] == "This looks good!"

    def test_comment_failure(self, mock_client: MagicMock):
        mock_client.query.return_value = {"commentCreate": {"success": False}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "comment", "KOD-1", "--body", "test"])
        assert result.exit_code == 0

    def test_comment_json_output(self, mock_client: MagicMock):
        mock_client.query.return_value = {"commentCreate": {"success": True}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["--json", "issues", "comment", "KOD-1", "--body", "test"])
        assert result.exit_code == 0

    def test_comment_body_passed_through(self, mock_client: MagicMock):
        mock_client.query.return_value = {"commentCreate": {"success": True}}
        with mock_linear_client(mock_client):
            runner.invoke(app, ["issues", "comment", "KOD-1", "--body", "specific body"])
        call_args = mock_client.query.call_args
        assert call_args[0][1]["body"] == "specific body"


class TestIssuesSearch:
    def test_search_results(self, mock_client: MagicMock):
        mock_client.query.return_value = {"searchIssues": {"nodes": [SAMPLE_ISSUE]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "search", "login"])
        assert result.exit_code == 0
        call_args = mock_client.query.call_args
        assert call_args[0][1]["term"] == "login"

    def test_search_empty_results(self, mock_client: MagicMock):
        mock_client.query.return_value = {"searchIssues": {"nodes": []}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "search", "nonexistent"])
        assert result.exit_code == 0

    def test_search_with_limit(self, mock_client: MagicMock):
        mock_client.query.return_value = {"searchIssues": {"nodes": [SAMPLE_ISSUE]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "search", "bug", "--limit", "5"])
        assert result.exit_code == 0
        call_args = mock_client.query.call_args
        assert call_args[0][1]["first"] == 5

    def test_search_json_output(self, mock_client: MagicMock):
        mock_client.query.return_value = {"searchIssues": {"nodes": [SAMPLE_ISSUE]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["--json", "issues", "search", "login"])
        assert result.exit_code == 0

    def test_search_no_assignee(self, mock_client: MagicMock):
        issue_no_assignee = {**SAMPLE_ISSUE, "assignee": None}
        mock_client.query.return_value = {"searchIssues": {"nodes": [issue_no_assignee]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "search", "test"])
        assert result.exit_code == 0

    def test_search_multiple_results(self, mock_client: MagicMock):
        mock_client.query.return_value = {"searchIssues": {"nodes": [SAMPLE_ISSUE, SAMPLE_ISSUE_2]}}
        with mock_linear_client(mock_client):
            result = runner.invoke(app, ["issues", "search", "bug"])
        assert result.exit_code == 0
