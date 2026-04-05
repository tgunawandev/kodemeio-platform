"""Tests for kctl-api users commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_api.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# users --help checks
# ---------------------------------------------------------------------------
class TestUsersHelp:
    def test_users_help(self) -> None:
        result = runner.invoke(app, ["users", "--help"])
        assert result.exit_code == 0

    def test_users_list_help(self) -> None:
        result = runner.invoke(app, ["users", "list", "--help"])
        assert result.exit_code == 0
        assert "--page" in result.output
        assert "--per-page" in result.output

    def test_users_get_help(self) -> None:
        result = runner.invoke(app, ["users", "get", "--help"])
        assert result.exit_code == 0

    def test_users_create_help(self) -> None:
        result = runner.invoke(app, ["users", "create", "--help"])
        assert result.exit_code == 0
        assert "--email" in result.output

    def test_users_update_help(self) -> None:
        result = runner.invoke(app, ["users", "update", "--help"])
        assert result.exit_code == 0

    def test_users_delete_help(self) -> None:
        result = runner.invoke(app, ["users", "delete", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# users list
# ---------------------------------------------------------------------------
class TestUsersList:
    def _make_client(self, items: list, total: int = None) -> MagicMock:
        mock = MagicMock()
        mock.get.return_value = {"items": items, "total": total if total is not None else len(items)}
        return mock

    def test_list_empty(self) -> None:
        mock_client = self._make_client([])
        with patch(
            "kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)
        ):
            result = runner.invoke(app, ["users", "list"])
        assert result.exit_code == 0

    def test_list_with_users(self) -> None:
        users = [
            {
                "id": 1,
                "email": "alice@test.com",
                "name": "Alice",
                "role": "admin",
                "tier": "premium",
                "is_active": True,
            },
            {"id": 2, "email": "bob@test.com", "name": "Bob", "role": "user", "tier": "free", "is_active": True},
        ]
        mock_client = self._make_client(users, total=2)
        with patch(
            "kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)
        ):
            result = runner.invoke(app, ["users", "list"])
        assert result.exit_code == 0
        assert "alice@test.com" in result.output
        assert "bob@test.com" in result.output

    def test_list_json_mode(self) -> None:
        users = [
            {"id": 1, "email": "alice@test.com", "name": "Alice", "role": "user", "tier": "free", "is_active": True}
        ]
        mock_client = self._make_client(users)
        with patch(
            "kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)
        ):
            result = runner.invoke(app, ["--json", "users", "list"])
        assert result.exit_code == 0
        assert "alice@test.com" in result.output

    def test_list_with_pagination(self) -> None:
        mock_client = self._make_client([])
        with patch(
            "kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)
        ):
            result = runner.invoke(app, ["users", "list", "--page", "2", "--per-page", "50"])
        assert result.exit_code == 0
        # Verify params passed to client
        call_kwargs = mock_client.get.call_args
        assert call_kwargs is not None
        params = call_kwargs.kwargs.get("params", call_kwargs.args[1] if len(call_kwargs.args) > 1 else {})
        assert params.get("page") == 2
        assert params.get("per_page") == 50

    def test_list_with_search(self) -> None:
        mock_client = self._make_client([])
        with patch(
            "kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)
        ):
            result = runner.invoke(app, ["users", "list", "--search", "alice"])
        assert result.exit_code == 0

    def test_list_auth_error(self) -> None:
        from kctl_api.core.exceptions import AuthenticationError

        mock_client = MagicMock()
        mock_client.get.side_effect = AuthenticationError("Unauthorized")
        with patch(
            "kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)
        ):
            result = runner.invoke(app, ["users", "list"])
        assert result.exit_code == 1
        assert "Auth failed" in result.output

    def test_list_connection_error(self) -> None:
        from kctl_api.core.exceptions import ConnectionError as KctlConnectionError

        mock_client = MagicMock()
        mock_client.get.side_effect = KctlConnectionError("http://localhost", ConnectionError("refused"))
        with patch(
            "kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)
        ):
            result = runner.invoke(app, ["users", "list"])
        assert result.exit_code == 1
        assert "Connection failed" in result.output

    def test_list_api_error(self) -> None:
        from kctl_api.core.exceptions import APIError

        mock_client = MagicMock()
        mock_client.get.side_effect = APIError(detail="Server error")
        with patch(
            "kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)
        ):
            result = runner.invoke(app, ["users", "list"])
        assert result.exit_code == 1
        assert "API error" in result.output


# ---------------------------------------------------------------------------
# users get
# ---------------------------------------------------------------------------
class TestUsersGet:
    def test_get_by_id(self) -> None:
        user = {
            "id": 42,
            "email": "alice@test.com",
            "name": "Alice",
            "role": "admin",
            "tier": "premium",
            "is_active": True,
            "created_at": "2024-01-01",
            "updated_at": "2024-06-01",
        }
        mock_client = MagicMock()
        mock_client.get.return_value = user

        with (
            patch("kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)),
            patch("kctl_api.commands.users.resolve_user", return_value=user),
        ):
            result = runner.invoke(app, ["users", "get", "42"])
        assert result.exit_code == 0
        assert "alice@test.com" in result.output

    def test_get_json_mode(self) -> None:
        user = {"id": 1, "email": "user@test.com", "role": "user", "tier": "free", "is_active": True}
        mock_client = MagicMock()

        with (
            patch("kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)),
            patch("kctl_api.commands.users.resolve_user", return_value=user),
        ):
            result = runner.invoke(app, ["--json", "users", "get", "1"])
        assert result.exit_code == 0
        assert "user@test.com" in result.output

    def test_get_auth_error(self) -> None:
        from kctl_api.core.exceptions import AuthenticationError

        mock_client = MagicMock()
        with (
            patch("kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)),
            patch("kctl_api.commands.users.resolve_user", side_effect=AuthenticationError("Unauthorized")),
        ):
            result = runner.invoke(app, ["users", "get", "99"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# users create
# ---------------------------------------------------------------------------
class TestUsersCreate:
    def test_create_success(self) -> None:
        new_user = {"id": 10, "email": "new@test.com", "name": "New User"}
        mock_client = MagicMock()
        mock_client.post.return_value = new_user

        with patch(
            "kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)
        ):
            result = runner.invoke(
                app,
                ["users", "create", "--email", "new@test.com", "--name", "New User", "--password", "Pass123!"],
            )
        assert result.exit_code == 0
        assert "new@test.com" in result.output

    def test_create_json_mode(self) -> None:
        new_user = {"id": 11, "email": "json@test.com", "name": "JSON User"}
        mock_client = MagicMock()
        mock_client.post.return_value = new_user

        with patch(
            "kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)
        ):
            result = runner.invoke(
                app,
                [
                    "--json",
                    "users",
                    "create",
                    "--email",
                    "json@test.com",
                    "--name",
                    "JSON User",
                    "--password",
                    "Pass123!",
                ],
            )
        assert result.exit_code == 0
        assert "json@test.com" in result.output

    def test_create_api_error(self) -> None:
        from kctl_api.core.exceptions import APIError

        mock_client = MagicMock()
        mock_client.post.side_effect = APIError(detail="Email already registered")

        with patch(
            "kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)
        ):
            result = runner.invoke(
                app,
                ["users", "create", "--email", "dup@test.com", "--name", "Dup", "--password", "Pass123!"],
            )
        assert result.exit_code == 1
        assert "API error" in result.output

    def test_create_connection_error(self) -> None:
        from kctl_api.core.exceptions import ConnectionError as KctlConnectionError

        mock_client = MagicMock()
        mock_client.post.side_effect = KctlConnectionError("http://localhost", ConnectionError("refused"))

        with patch(
            "kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)
        ):
            result = runner.invoke(
                app,
                ["users", "create", "--email", "x@test.com", "--name", "X", "--password", "Pass123!"],
            )
        assert result.exit_code == 1
        assert "Connection failed" in result.output


# ---------------------------------------------------------------------------
# users update
# ---------------------------------------------------------------------------
class TestUsersUpdate:
    def test_update_no_fields(self) -> None:
        mock_client = MagicMock()
        with (
            patch("kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)),
            patch("kctl_api.commands.users.resolve_user_id", return_value="1"),
        ):
            result = runner.invoke(app, ["users", "update", "1"])
        assert result.exit_code == 0
        assert "No fields to update" in result.output

    def test_update_name(self) -> None:
        mock_client = MagicMock()
        mock_client.patch.return_value = {"id": 1, "email": "a@test.com", "name": "New Name"}
        with (
            patch("kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)),
            patch("kctl_api.commands.users.resolve_user_id", return_value="1"),
        ):
            result = runner.invoke(app, ["users", "update", "1", "--name", "New Name"])
        assert result.exit_code == 0
        assert "updated" in result.output.lower() or "New Name" in result.output

    def test_update_api_error(self) -> None:
        from kctl_api.core.exceptions import APIError

        mock_client = MagicMock()
        mock_client.patch.side_effect = APIError(detail="Not found")
        with (
            patch("kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)),
            patch("kctl_api.commands.users.resolve_user_id", return_value="999"),
        ):
            result = runner.invoke(app, ["users", "update", "999", "--name", "Ghost"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# users delete
# ---------------------------------------------------------------------------
class TestUsersDelete:
    def test_delete_success(self) -> None:
        mock_client = MagicMock()
        mock_client.delete.return_value = {}
        with (
            patch("kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)),
            patch("kctl_api.commands.users.resolve_user_id", return_value="5"),
        ):
            result = runner.invoke(app, ["users", "delete", "5", "--force"])
        assert result.exit_code == 0

    def test_delete_api_error(self) -> None:
        from kctl_api.core.exceptions import APIError

        mock_client = MagicMock()
        mock_client.delete.side_effect = APIError(detail="Not found")
        with (
            patch("kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)),
            patch("kctl_api.commands.users.resolve_user_id", return_value="999"),
        ):
            result = runner.invoke(app, ["users", "delete", "999", "--force"])
        assert result.exit_code == 1

    def test_delete_connection_error(self) -> None:
        from kctl_api.core.exceptions import ConnectionError as KctlConnectionError

        mock_client = MagicMock()
        mock_client.delete.side_effect = KctlConnectionError("http://localhost", ConnectionError("refused"))
        with (
            patch("kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)),
            patch("kctl_api.commands.users.resolve_user_id", return_value="1"),
        ):
            result = runner.invoke(app, ["users", "delete", "1", "--force"])
        assert result.exit_code == 1
