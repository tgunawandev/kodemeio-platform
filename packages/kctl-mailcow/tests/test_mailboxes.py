"""Tests for mailbox management commands."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_mailcow.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.base_url = "https://mail.kodeme.io"
    return client


@contextmanager
def inject_client(mock_client: MagicMock) -> Generator[MagicMock, None, None]:
    """Patch the AppContext to use a mock client."""
    with patch("kctl_mailcow.core.callbacks.resolve_connection", return_value=("https://mail.example.com", "testkey")):
        with patch("kctl_mailcow.core.callbacks.MailcowClient", return_value=mock_client):
            yield mock_client


MAILBOX_DATA = {
    "username": "user@example.com",
    "name": "Test User",
    "domain": "example.com",
    "quota_used": 1024 * 1024,
    "quota": 3072 * 1024 * 1024,
    "messages": 42,
    "active": "1",
    "created": "2024-01-01",
    "modified": "2024-06-01",
    "attributes": {"force_pw_update": "0", "tls_enforce_in": "0"},
}


class TestMailboxesList:
    def test_list_all_mailboxes(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = [MAILBOX_DATA]
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "list"])
        assert result.exit_code == 0
        mock_client.mc_get.assert_called_once_with("mailbox/all")

    def test_list_with_domain_filter(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = [MAILBOX_DATA]
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "list", "--domain", "example.com"])
        assert result.exit_code == 0
        mock_client.mc_get.assert_called_once_with("mailbox/example.com")

    def test_list_empty(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = []
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "list"])
        assert result.exit_code == 0

    def test_list_non_list_response(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = {}
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "list"])
        assert result.exit_code == 0

    def test_list_shows_email(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = [MAILBOX_DATA]
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "list"])
        assert "user@example.com" in result.output

    def test_list_zero_quota_no_division_error(self, runner: CliRunner, mock_client: MagicMock) -> None:
        zero_quota = {**MAILBOX_DATA, "quota": 0, "quota_used": 0}
        mock_client.mc_get.return_value = [zero_quota]
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "list"])
        assert result.exit_code == 0

    def test_list_inactive_mailbox(self, runner: CliRunner, mock_client: MagicMock) -> None:
        inactive = {**MAILBOX_DATA, "active": "0"}
        mock_client.mc_get.return_value = [inactive]
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "list"])
        assert result.exit_code == 0

    def test_list_multiple_mailboxes(self, runner: CliRunner, mock_client: MagicMock) -> None:
        second = {**MAILBOX_DATA, "username": "other@example.com"}
        mock_client.mc_get.return_value = [MAILBOX_DATA, second]
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "list"])
        assert result.exit_code == 0
        assert "user@example.com" in result.output
        assert "other@example.com" in result.output


class TestMailboxesGet:
    def test_get_mailbox(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = [MAILBOX_DATA]
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "get", "user@example.com"])
        assert result.exit_code == 0
        mock_client.mc_get.assert_called_once_with("mailbox/user@example.com")

    def test_get_mailbox_dict_response(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = MAILBOX_DATA
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "get", "user@example.com"])
        assert result.exit_code == 0

    def test_get_mailbox_not_found(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = []
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "get", "ghost@example.com"])
        assert result.exit_code == 1

    def test_get_mailbox_empty_dict(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = {}
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "get", "ghost@example.com"])
        assert result.exit_code == 1

    def test_get_shows_email(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = [MAILBOX_DATA]
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "get", "user@example.com"])
        assert "user@example.com" in result.output

    def test_get_shows_attributes_section(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = [MAILBOX_DATA]
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "get", "user@example.com"])
        assert result.exit_code == 0

    def test_get_no_attributes(self, runner: CliRunner, mock_client: MagicMock) -> None:
        no_attrs = {**MAILBOX_DATA, "attributes": {}}
        mock_client.mc_get.return_value = [no_attrs]
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "get", "user@example.com"])
        assert result.exit_code == 0

    def test_get_none_attributes(self, runner: CliRunner, mock_client: MagicMock) -> None:
        no_attrs = {**MAILBOX_DATA, "attributes": None}
        mock_client.mc_get.return_value = [no_attrs]
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "get", "user@example.com"])
        assert result.exit_code == 0


class TestMailboxesAdd:
    def test_add_mailbox_success(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = [{"type": "success", "msg": "Mailbox added"}]
        with inject_client(mock_client):
            result = runner.invoke(
                app,
                ["mailboxes", "add", "newuser", "example.com", "--password", "SecurePass123!"],
            )
        assert result.exit_code == 0
        mock_client.mc_add.assert_called_once()
        call_args = mock_client.mc_add.call_args
        assert call_args[0][0] == "mailbox"
        payload = call_args[0][1]
        assert payload["local_part"] == "newuser"
        assert payload["domain"] == "example.com"

    def test_add_mailbox_password_confirmation(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = [{"type": "success", "msg": "Mailbox added"}]
        with inject_client(mock_client):
            runner.invoke(
                app,
                ["mailboxes", "add", "newuser", "example.com", "--password", "SecurePass123!"],
            )
        payload = mock_client.mc_add.call_args[0][1]
        assert payload["password"] == payload["password2"]

    def test_add_mailbox_with_name(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = [{"type": "success", "msg": "Mailbox added"}]
        with inject_client(mock_client):
            result = runner.invoke(
                app,
                ["mailboxes", "add", "newuser", "example.com", "--password", "pass", "--name", "New User"],
            )
        assert result.exit_code == 0
        payload = mock_client.mc_add.call_args[0][1]
        assert payload["name"] == "New User"

    def test_add_mailbox_default_name_is_local_part(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = [{"type": "success", "msg": "Mailbox added"}]
        with inject_client(mock_client):
            runner.invoke(
                app,
                ["mailboxes", "add", "myuser", "example.com", "--password", "pass"],
            )
        payload = mock_client.mc_add.call_args[0][1]
        assert payload["name"] == "myuser"

    def test_add_mailbox_with_quota(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = [{"type": "success", "msg": "Mailbox added"}]
        with inject_client(mock_client):
            result = runner.invoke(
                app,
                ["mailboxes", "add", "newuser", "example.com", "--password", "pass", "--quota", "5120"],
            )
        assert result.exit_code == 0
        payload = mock_client.mc_add.call_args[0][1]
        assert payload["quota"] == 5120

    def test_add_mailbox_inactive(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = [{"type": "success", "msg": "Mailbox added"}]
        with inject_client(mock_client):
            result = runner.invoke(
                app,
                ["mailboxes", "add", "newuser", "example.com", "--password", "pass", "--inactive"],
            )
        assert result.exit_code == 0
        payload = mock_client.mc_add.call_args[0][1]
        assert payload["active"] == "0"

    def test_add_mailbox_active_by_default(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = [{"type": "success", "msg": "Mailbox added"}]
        with inject_client(mock_client):
            runner.invoke(
                app,
                ["mailboxes", "add", "newuser", "example.com", "--password", "pass"],
            )
        payload = mock_client.mc_add.call_args[0][1]
        assert payload["active"] == "1"

    def test_add_mailbox_api_error(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = [{"type": "danger", "msg": "Mailbox already exists"}]
        with inject_client(mock_client):
            result = runner.invoke(
                app,
                ["mailboxes", "add", "existing", "example.com", "--password", "pass"],
            )
        assert result.exit_code == 1


class TestMailboxesUpdate:
    def test_update_name(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_edit.return_value = [{"type": "success", "msg": "Updated"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "update", "user@example.com", "--name", "New Name"])
        assert result.exit_code == 0
        payload = mock_client.mc_edit.call_args[0][1]
        assert payload["items"] == ["user@example.com"]
        assert payload["attr"]["name"] == "New Name"

    def test_update_quota(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_edit.return_value = [{"type": "success", "msg": "Updated"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "update", "user@example.com", "--quota", "5120"])
        assert result.exit_code == 0
        payload = mock_client.mc_edit.call_args[0][1]
        assert payload["attr"]["quota"] == 5120

    def test_update_password_sets_both_fields(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_edit.return_value = [{"type": "success", "msg": "Updated"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "update", "user@example.com", "--password", "NewPass!"])
        assert result.exit_code == 0
        payload = mock_client.mc_edit.call_args[0][1]
        assert payload["attr"]["password"] == "NewPass!"
        assert payload["attr"]["password2"] == "NewPass!"

    def test_update_active(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_edit.return_value = [{"type": "success", "msg": "Updated"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "update", "user@example.com", "--active"])
        assert result.exit_code == 0
        payload = mock_client.mc_edit.call_args[0][1]
        assert payload["attr"]["active"] == "1"

    def test_update_inactive(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_edit.return_value = [{"type": "success", "msg": "Updated"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "update", "user@example.com", "--inactive"])
        assert result.exit_code == 0
        payload = mock_client.mc_edit.call_args[0][1]
        assert payload["attr"]["active"] == "0"

    def test_update_no_fields_exits_cleanly(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "update", "user@example.com"])
        assert result.exit_code == 0
        mock_client.mc_edit.assert_not_called()

    def test_update_api_error(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_edit.return_value = [{"type": "danger", "msg": "Update failed"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "update", "user@example.com", "--name", "Bad"])
        assert result.exit_code == 1

    def test_update_uses_mailbox_endpoint(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_edit.return_value = [{"type": "success", "msg": "Updated"}]
        with inject_client(mock_client):
            runner.invoke(app, ["mailboxes", "update", "user@example.com", "--name", "x"])
        assert mock_client.mc_edit.call_args[0][0] == "mailbox"


class TestMailboxesDelete:
    def test_delete_with_force(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_delete.return_value = [{"type": "success", "msg": "Deleted"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "delete", "user@example.com", "--force"])
        assert result.exit_code == 0
        mock_client.mc_delete.assert_called_once_with("mailbox", ["user@example.com"])

    def test_delete_without_force_aborts(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "delete", "user@example.com"], input="n\n")
        assert result.exit_code == 0
        mock_client.mc_delete.assert_not_called()

    def test_delete_without_force_confirms(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_delete.return_value = [{"type": "success", "msg": "Deleted"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "delete", "user@example.com"], input="y\n")
        assert result.exit_code == 0
        mock_client.mc_delete.assert_called_once()

    def test_delete_api_error(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_delete.return_value = [{"type": "danger", "msg": "Cannot delete"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["mailboxes", "delete", "user@example.com", "--force"])
        assert result.exit_code == 1

    def test_delete_passes_email_as_list(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_delete.return_value = [{"type": "success", "msg": "Deleted"}]
        with inject_client(mock_client):
            runner.invoke(app, ["mailboxes", "delete", "user@example.com", "--force"])
        call_args = mock_client.mc_delete.call_args[0]
        assert call_args[1] == ["user@example.com"]
