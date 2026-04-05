"""Tests for domain management commands."""

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


DOMAIN_DATA = {
    "domain_name": "example.com",
    "description": "Test domain",
    "aliases_in_domain": 2,
    "max_num_aliases_for_domain": 400,
    "mboxes_in_domain": 1,
    "max_num_mboxes_for_domain": 10,
    "quota_used_in_domain": 0,
    "max_quota_for_domain": 10240,
    "active": "1",
    "relay_all_recipients": "0",
    "backupmx": "0",
    "aliases_left": 398,
    "mboxes_left": 9,
    "quota": 10240,
}


class TestDomainsList:
    def test_list_all_domains(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = [DOMAIN_DATA]
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "list"])
        assert result.exit_code == 0
        mock_client.mc_get.assert_called_once_with("domain/all")

    def test_list_empty(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = []
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "list"])
        assert result.exit_code == 0

    def test_list_non_list_response(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = {}
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "list"])
        assert result.exit_code == 0

    def test_list_active_domain_included(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = [DOMAIN_DATA]
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "list"])
        assert result.exit_code == 0
        assert "example.com" in result.output

    def test_list_inactive_domain(self, runner: CliRunner, mock_client: MagicMock) -> None:
        inactive = {**DOMAIN_DATA, "active": "0"}
        mock_client.mc_get.return_value = [inactive]
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "list"])
        assert result.exit_code == 0

    def test_list_multiple_domains(self, runner: CliRunner, mock_client: MagicMock) -> None:
        second = {**DOMAIN_DATA, "domain_name": "other.com"}
        mock_client.mc_get.return_value = [DOMAIN_DATA, second]
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "list"])
        assert result.exit_code == 0
        assert "example.com" in result.output
        assert "other.com" in result.output


class TestDomainsGet:
    def test_get_domain_by_name(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = [DOMAIN_DATA]
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "get", "example.com"])
        assert result.exit_code == 0
        mock_client.mc_get.assert_called_once_with("domain/example.com")

    def test_get_domain_dict_response(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = DOMAIN_DATA
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "get", "example.com"])
        assert result.exit_code == 0

    def test_get_domain_not_found(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = []
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "get", "missing.com"])
        assert result.exit_code == 1

    def test_get_domain_none_response(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = None
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "get", "missing.com"])
        assert result.exit_code == 1

    def test_get_shows_domain_name(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = [DOMAIN_DATA]
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "get", "example.com"])
        assert "example.com" in result.output

    def test_get_shows_alias_info(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = [DOMAIN_DATA]
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "get", "example.com"])
        assert result.exit_code == 0


class TestDomainsAdd:
    def test_add_domain_success(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = [{"type": "success", "msg": "Domain added"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "add", "newdomain.com"])
        assert result.exit_code == 0
        mock_client.mc_add.assert_called_once()
        call_args = mock_client.mc_add.call_args
        assert call_args[0][0] == "domain"
        assert call_args[0][1]["domain"] == "newdomain.com"

    def test_add_domain_with_description(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = [{"type": "success", "msg": "Domain added"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "add", "newdomain.com", "--description", "My domain"])
        assert result.exit_code == 0
        payload = mock_client.mc_add.call_args[0][1]
        assert payload["description"] == "My domain"

    def test_add_domain_with_custom_aliases(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = [{"type": "success", "msg": "Domain added"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "add", "newdomain.com", "--aliases", "100"])
        assert result.exit_code == 0
        payload = mock_client.mc_add.call_args[0][1]
        assert payload["aliases"] == 100

    def test_add_domain_inactive(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = [{"type": "success", "msg": "Domain added"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "add", "newdomain.com", "--inactive"])
        assert result.exit_code == 0
        payload = mock_client.mc_add.call_args[0][1]
        assert payload["active"] == "0"

    def test_add_domain_active_by_default(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = [{"type": "success", "msg": "Domain added"}]
        with inject_client(mock_client):
            runner.invoke(app, ["domains", "add", "newdomain.com"])
        payload = mock_client.mc_add.call_args[0][1]
        assert payload["active"] == "1"

    def test_add_domain_api_error(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = [{"type": "danger", "msg": "Domain already exists"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "add", "existing.com"])
        assert result.exit_code == 1

    def test_add_domain_default_description_is_domain(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = [{"type": "success", "msg": "ok"}]
        with inject_client(mock_client):
            runner.invoke(app, ["domains", "add", "example.com"])
        payload = mock_client.mc_add.call_args[0][1]
        assert payload["description"] == "example.com"

    def test_add_domain_sets_restart_sogo(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = [{"type": "success", "msg": "ok"}]
        with inject_client(mock_client):
            runner.invoke(app, ["domains", "add", "example.com"])
        payload = mock_client.mc_add.call_args[0][1]
        assert payload["restart_sogo"] == "1"

    def test_add_domain_dict_success_response(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = {"type": "success", "msg": "ok"}
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "add", "example.com"])
        assert result.exit_code == 0

    def test_add_domain_dict_error_response(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_add.return_value = {"type": "danger", "msg": "Failed"}
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "add", "example.com"])
        assert result.exit_code == 1


class TestDomainsUpdate:
    def test_update_description(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_edit.return_value = [{"type": "success", "msg": "Updated"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "update", "example.com", "--description", "New desc"])
        assert result.exit_code == 0
        mock_client.mc_edit.assert_called_once()
        payload = mock_client.mc_edit.call_args[0][1]
        assert payload["items"] == ["example.com"]
        assert payload["attr"]["description"] == "New desc"

    def test_update_active_flag(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_edit.return_value = [{"type": "success", "msg": "Updated"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "update", "example.com", "--active"])
        assert result.exit_code == 0
        payload = mock_client.mc_edit.call_args[0][1]
        assert payload["attr"]["active"] == "1"

    def test_update_inactive_flag(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_edit.return_value = [{"type": "success", "msg": "Updated"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "update", "example.com", "--inactive"])
        assert result.exit_code == 0
        payload = mock_client.mc_edit.call_args[0][1]
        assert payload["attr"]["active"] == "0"

    def test_update_no_fields_exits_cleanly(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "update", "example.com"])
        assert result.exit_code == 0
        mock_client.mc_edit.assert_not_called()

    def test_update_multiple_fields(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_edit.return_value = [{"type": "success", "msg": "Updated"}]
        with inject_client(mock_client):
            result = runner.invoke(
                app,
                ["domains", "update", "example.com", "--aliases", "500", "--quota", "20480"],
            )
        assert result.exit_code == 0
        payload = mock_client.mc_edit.call_args[0][1]
        assert payload["attr"]["aliases"] == 500
        assert payload["attr"]["quota"] == 20480

    def test_update_api_error(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_edit.return_value = [{"type": "danger", "msg": "Update failed"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "update", "example.com", "--description", "x"])
        assert result.exit_code == 1

    def test_update_mailboxes(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_edit.return_value = [{"type": "success", "msg": "Updated"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "update", "example.com", "--mailboxes", "20"])
        assert result.exit_code == 0
        payload = mock_client.mc_edit.call_args[0][1]
        assert payload["attr"]["mailboxes"] == 20

    def test_update_uses_edit_endpoint(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_edit.return_value = [{"type": "success", "msg": "Updated"}]
        with inject_client(mock_client):
            runner.invoke(app, ["domains", "update", "example.com", "--description", "x"])
        assert mock_client.mc_edit.call_args[0][0] == "domain"


class TestDomainsDelete:
    def test_delete_with_force(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_delete.return_value = [{"type": "success", "msg": "Deleted"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "delete", "example.com", "--force"])
        assert result.exit_code == 0
        mock_client.mc_delete.assert_called_once_with("domain", ["example.com"])

    def test_delete_without_force_aborts(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "delete", "example.com"], input="n\n")
        assert result.exit_code == 0
        mock_client.mc_delete.assert_not_called()

    def test_delete_without_force_confirms(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_delete.return_value = [{"type": "success", "msg": "Deleted"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "delete", "example.com"], input="y\n")
        assert result.exit_code == 0
        mock_client.mc_delete.assert_called_once()

    def test_delete_api_error(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_delete.return_value = [{"type": "danger", "msg": "Cannot delete"}]
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "delete", "example.com", "--force"])
        assert result.exit_code == 1

    def test_delete_passes_domain_as_list(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_delete.return_value = [{"type": "success", "msg": "Deleted"}]
        with inject_client(mock_client):
            runner.invoke(app, ["domains", "delete", "example.com", "--force"])
        call_args = mock_client.mc_delete.call_args[0]
        assert call_args[1] == ["example.com"]


class TestDomainsDnsCheck:
    def test_dns_check_success(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = {
            "mx": [{"name": "MX", "expected": "mail.example.com", "found": "mail.example.com", "ok": True}],
            "spf": [{"name": "SPF", "expected": "v=spf1 ...", "found": "v=spf1 ...", "ok": True}],
        }
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "dns-check", "example.com"])
        assert result.exit_code == 0
        mock_client.mc_get.assert_called_once_with("dns/example.com/check")

    def test_dns_check_non_dict_response(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = "unexpected"
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "dns-check", "example.com"])
        assert result.exit_code == 1

    def test_dns_check_empty_dict(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = {}
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "dns-check", "example.com"])
        assert result.exit_code == 0

    def test_dns_check_string_records(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = {
            "mx": ["mail.example.com"],
        }
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "dns-check", "example.com"])
        assert result.exit_code == 0

    def test_dns_check_dict_records(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = {
            "mx": {"host": "mail.example.com", "ttl": "300"},
        }
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "dns-check", "example.com"])
        assert result.exit_code == 0

    def test_dns_check_failed_record(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = {
            "mx": [{"name": "MX", "expected": "mail.example.com", "found": "", "ok": False}],
        }
        with inject_client(mock_client):
            result = runner.invoke(app, ["domains", "dns-check", "example.com"])
        assert result.exit_code == 0
