"""Tests for users commands with mocked client."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_ak.cli import app
from kctl_ak.core.callbacks import AppContext

runner = CliRunner()


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


SAMPLE_USERS = [
    {
        "pk": 1,
        "username": "akadmin",
        "email": "admin@kodeme.io",
        "name": "Admin",
        "is_active": True,
        "is_superuser": True,
        "groups_obj": [],
    },
    {
        "pk": 2,
        "username": "tri.gunawan",
        "email": "tri@kodeme.io",
        "name": "Tri Gunawan",
        "is_active": True,
        "is_superuser": False,
        "groups_obj": [{"name": "kodemeio-admins", "pk": "grp-001"}],
    },
    {
        "pk": 3,
        "username": "inactive.user",
        "email": "old@kodeme.io",
        "name": "Old User",
        "is_active": False,
        "is_superuser": False,
        "groups_obj": [],
    },
]


class TestUsersListMocked:
    def test_users_list(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "results": SAMPLE_USERS,
            "pagination": {"current": 1, "total_pages": 1},
        }
        result = runner.invoke(app, ["users", "list"])
        assert result.exit_code == 0
        assert "akadmin" in result.output
        assert "tri.gunawan" in result.output

    def test_users_list_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "results": SAMPLE_USERS,
            "pagination": {"current": 1, "total_pages": 1},
        }
        result = runner.invoke(app, ["--json", "users", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 3

    def test_users_list_active_flag(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "results": [u for u in SAMPLE_USERS if u["is_active"]],
            "pagination": {"current": 1, "total_pages": 1},
        }
        result = runner.invoke(app, ["users", "list", "--active"])
        assert result.exit_code == 0
        call_kwargs = mock_client.get.call_args
        assert call_kwargs.kwargs.get("params", {}).get("is_active") is True

    def test_users_list_inactive_flag(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "results": [u for u in SAMPLE_USERS if not u["is_active"]],
            "pagination": {"current": 1, "total_pages": 1},
        }
        result = runner.invoke(app, ["users", "list", "--inactive"])
        assert result.exit_code == 0
        call_kwargs = mock_client.get.call_args
        assert call_kwargs.kwargs.get("params", {}).get("is_active") is False

    def test_users_list_empty(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"results": [], "pagination": {"current": 1, "total_pages": 1}}
        result = runner.invoke(app, ["users", "list"])
        assert result.exit_code == 0


class TestUsersGet:
    def test_users_get_by_pk(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_USERS[1]
        result = runner.invoke(app, ["users", "get", "tri.gunawan"])
        assert result.exit_code == 0

    def test_users_get_help(self) -> None:
        result = runner.invoke(app, ["users", "get", "--help"])
        assert result.exit_code == 0


class TestUsersCreate:
    def test_users_create(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {
            "pk": 10,
            "username": "new.user",
            "email": "new@kodeme.io",
            "name": "New User",
        }
        result = runner.invoke(
            app,
            ["users", "create", "--username", "new.user", "--email", "new@kodeme.io", "--name", "New User"],
        )
        assert result.exit_code == 0

    def test_users_create_help(self) -> None:
        result = runner.invoke(app, ["users", "create", "--help"])
        assert result.exit_code == 0
        assert "--groups" in result.output


class TestUsersSearch:
    def test_users_search(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "results": [SAMPLE_USERS[1]],
            "pagination": {"current": 1, "total_pages": 1},
        }
        result = runner.invoke(app, ["users", "search", "tri"])
        assert result.exit_code == 0

    def test_users_search_no_results(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"results": [], "pagination": {"current": 1, "total_pages": 1}}
        result = runner.invoke(app, ["users", "search", "zzz"])
        assert result.exit_code == 0

    def test_users_search_help(self) -> None:
        result = runner.invoke(app, ["users", "search", "--help"])
        assert result.exit_code == 0


class TestUsersMe:
    def test_users_me(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_USERS[0]
        result = runner.invoke(app, ["users", "me"])
        assert result.exit_code == 0

    def test_users_me_help(self) -> None:
        result = runner.invoke(app, ["users", "me", "--help"])
        assert result.exit_code == 0


class TestUsersExport:
    def test_users_export(self, mock_client: MagicMock) -> None:
        mock_client.get_all.return_value = SAMPLE_USERS
        result = runner.invoke(app, ["users", "export"])
        assert result.exit_code == 0

    def test_users_export_help(self) -> None:
        result = runner.invoke(app, ["users", "export", "--help"])
        assert result.exit_code == 0


class TestUsersPending:
    def test_users_pending(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"results": [], "pagination": {"current": 1, "total_pages": 1}}
        result = runner.invoke(app, ["users", "pending"])
        assert result.exit_code == 0

    def test_users_pending_help(self) -> None:
        result = runner.invoke(app, ["users", "pending", "--help"])
        assert result.exit_code == 0
