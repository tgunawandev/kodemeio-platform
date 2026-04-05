"""Tests for alias management commands."""

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


ALIAS_DATA = {
    "id": "42",
    "address": "alias@example.com",
    "goto": "user@example.com",
    "domain": "example.com",
    "active": "1",
    "created": "2024-01-01",
    "modified": "2024-06-01",
}


class TestAliasesList:
    def test_list_all_aliases(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = [ALIAS_DATA]
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "list"])
        assert result.exit_code == 0
        mock_client.mc_get.assert_called_once_with("alias/all")

    def test_list_empty(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = []
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "list"])
        assert result.exit_code == 0

    def test_list_non_list_response(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = {}
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "list"])
        assert result.exit_code == 0

    def test_list_domain_filter_still_calls_alias_all(self, runner: CliRunner, mock_client: MagicMock) -> None:
        other_alias = {**ALIAS_DATA, "id": "43", "address": "other@other.com", "domain": "other.com"}
        mock_client.mc_get.return_value = [ALIAS_DATA, other_alias]
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "list", "--domain", "example.com"])
        assert result.exit_code == 0
        mock_client.mc_get.assert_called_once_with("alias/all")

    def test_list_domain_filter_excludes_other_domains(self, runner: CliRunner, mock_client: MagicMock) -> None:
        other_alias = {**ALIAS_DATA, "id": "43", "address": "other@other.com", "domain": "other.com"}
        mock_client.mc_get.return_value = [ALIAS_DATA, other_alias]
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "list", "--domain", "example.com"])
        assert result.exit_code == 0
        assert "other@other.com" not in result.output

    def test_list_shows_address(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = [ALIAS_DATA]
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "list"])
        assert "alias@example.com" in result.output

    def test_list_shows_goto(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = [ALIAS_DATA]
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "list"])
        assert "user@example.com" in result.output

    def test_list_inactive_alias(self, runner: CliRunner, mock_client: MagicMock) -> None:
        inactive = {**ALIAS_DATA, "active": "0"}
        mock_client.mc_get.return_value = [inactive]
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "list"])
        assert result.exit_code == 0

    def test_list_multiple_aliases(self, runner: CliRunner, mock_client: MagicMock) -> None:
        second = {**ALIAS_DATA, "id": "43", "address": "second@example.com"}
        mock_client.mc_get.return_value = [ALIAS_DATA, second]
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "list"])
        assert result.exit_code == 0
        assert "alias@example.com" in result.output
        assert "second@example.com" in result.output


class TestAliasesGet:
    def test_get_alias_by_id(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = [ALIAS_DATA]
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "get", "42"])
        assert result.exit_code == 0
        mock_client.mc_get.assert_called_once_with("alias/42")

    def test_get_alias_dict_response(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = ALIAS_DATA
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "get", "42"])
        assert result.exit_code == 0

    def test_get_alias_not_found_empty_list(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = []
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "get", "999"])
        assert result.exit_code == 1

    def test_get_alias_not_found_empty_dict(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = {}
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "get", "999"])
        assert result.exit_code == 1

    def test_get_alias_not_found_none(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = None
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "get", "999"])
        assert result.exit_code == 1

    def test_get_shows_address(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = [ALIAS_DATA]
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "get", "42"])
        assert "alias@example.com" in result.output

    def test_get_shows_goto(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = [ALIAS_DATA]
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "get", "42"])
        assert "user@example.com" in result.output


class TestAliasesAdd:
    def test_add_alias_success(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = [{"type": "success", "msg": "Alias added"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "add", "alias@example.com", "user@example.com"])
        assert result.exit_code == 0
        mock_client.mc_add.assert_called_once()
        call_args = mock_client.mc_add.call_args
        assert call_args[0][0] == "alias"
        payload = call_args[0][1]
        assert payload["address"] == "alias@example.com"
        assert payload["goto"] == "user@example.com"

    def test_add_alias_active_by_default(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = [{"type": "success", "msg": "Alias added"}]
        with inject_client(mock_client):
            runner.invoke(app, ["aliases", "add", "alias@example.com", "user@example.com"])
        payload = mock_client.mc_add.call_args[0][1]
        assert payload["active"] == "1"

    def test_add_alias_inactive(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = [{"type": "success", "msg": "Alias added"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "add", "alias@example.com", "user@example.com", "--inactive"])
        assert result.exit_code == 0
        payload = mock_client.mc_add.call_args[0][1]
        assert payload["active"] == "0"

    def test_add_alias_multiple_goto(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = [{"type": "success", "msg": "Alias added"}]
        with inject_client(mock_client):
            result = runner.invoke(
                app,
                ["aliases", "add", "alias@example.com", "a@example.com,b@example.com"],
            )
        assert result.exit_code == 0
        payload = mock_client.mc_add.call_args[0][1]
        assert payload["goto"] == "a@example.com,b@example.com"

    def test_add_alias_api_error(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = [{"type": "danger", "msg": "Alias already exists"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "add", "existing@example.com", "user@example.com"])
        assert result.exit_code == 1

    def test_add_alias_dict_error_response(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = {"type": "danger", "msg": "Failed"}
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "add", "alias@example.com", "user@example.com"])
        assert result.exit_code == 1

    def test_add_alias_dict_success_response(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = {"type": "success", "msg": "ok"}
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "add", "alias@example.com", "user@example.com"])
        assert result.exit_code == 0


class TestAliasesUpdate:
    def test_update_goto(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_edit.return_value = [{"type": "success", "msg": "Updated"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "update", "42", "--goto", "new@example.com"])
        assert result.exit_code == 0
        payload = mock_client.mc_edit.call_args[0][1]
        assert payload["items"] == ["42"]
        assert payload["attr"]["goto"] == "new@example.com"

    def test_update_address(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_edit.return_value = [{"type": "success", "msg": "Updated"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "update", "42", "--address", "newalias@example.com"])
        assert result.exit_code == 0
        payload = mock_client.mc_edit.call_args[0][1]
        assert payload["attr"]["address"] == "newalias@example.com"

    def test_update_active(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_edit.return_value = [{"type": "success", "msg": "Updated"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "update", "42", "--active"])
        assert result.exit_code == 0
        payload = mock_client.mc_edit.call_args[0][1]
        assert payload["attr"]["active"] == "1"

    def test_update_inactive(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_edit.return_value = [{"type": "success", "msg": "Updated"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "update", "42", "--inactive"])
        assert result.exit_code == 0
        payload = mock_client.mc_edit.call_args[0][1]
        assert payload["attr"]["active"] == "0"

    def test_update_no_fields_exits_cleanly(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "update", "42"])
        assert result.exit_code == 0
        mock_client.mc_edit.assert_not_called()

    def test_update_api_error(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_edit.return_value = [{"type": "danger", "msg": "Update failed"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "update", "42", "--goto", "bad@example.com"])
        assert result.exit_code == 1

    def test_update_endpoint_uses_alias_resource(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_edit.return_value = [{"type": "success", "msg": "Updated"}]
        with inject_client(mock_client):
            runner.invoke(app, ["aliases", "update", "42", "--goto", "new@example.com"])
        assert mock_client.mc_edit.call_args[0][0] == "alias"


class TestAliasesDelete:
    def test_delete_with_force(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_delete.return_value = [{"type": "success", "msg": "Deleted"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "delete", "42", "--force"])
        assert result.exit_code == 0
        mock_client.mc_delete.assert_called_once_with("alias", ["42"])

    def test_delete_without_force_aborts(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "delete", "42"], input="n\n")
        assert result.exit_code == 0
        mock_client.mc_delete.assert_not_called()

    def test_delete_without_force_confirms(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_delete.return_value = [{"type": "success", "msg": "Deleted"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "delete", "42"], input="y\n")
        assert result.exit_code == 0
        mock_client.mc_delete.assert_called_once()

    def test_delete_api_error(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_delete.return_value = [{"type": "danger", "msg": "Cannot delete"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["aliases", "delete", "42", "--force"])
        assert result.exit_code == 1

    def test_delete_passes_id_as_list(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_delete.return_value = [{"type": "success", "msg": "Deleted"}]
        with inject_client(mock_client):
            runner.invoke(app, ["aliases", "delete", "99", "--force"])
        call_args = mock_client.mc_delete.call_args[0]
        assert call_args[1] == ["99"]
