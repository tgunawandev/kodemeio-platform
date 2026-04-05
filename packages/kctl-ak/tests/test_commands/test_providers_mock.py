"""Tests for providers commands with mocked client."""

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


SAMPLE_OAUTH2 = [
    {
        "pk": 1,
        "name": "mac-sfa",
        "client_id": "abc123",
        "client_secret": "secret456",
        "client_type": "confidential",
        "redirect_uris": "https://sfa.mandiriagro.com/callback",
        "assigned_application_name": "MAC SFA",
        "authorization_flow": "flow-001",
        "sub_mode": "hashed_user_id",
        "access_token_validity": "hours=1",
    },
    {
        "pk": 2,
        "name": "tpp-shop",
        "client_id": "def789",
        "client_secret": "xyz000",
        "client_type": "public",
        "redirect_uris": "https://shop.pakertitradisi.com/callback",
        "assigned_application_name": "TPP Shop",
        "authorization_flow": "flow-001",
        "sub_mode": "hashed_user_id",
        "access_token_validity": "hours=1",
    },
]

SAMPLE_LDAP = [
    {
        "pk": 10,
        "name": "ldap-provider",
        "base_dn": "dc=kodeme,dc=io",
        "authorization_flow": "flow-001",
        "assigned_application_name": None,
    }
]

SAMPLE_PROXY = [
    {
        "pk": 20,
        "name": "proxy-grafana",
        "external_host": "https://grafana.kodeme.io",
        "internal_host": "http://grafana:3000",
        "mode": "forward_single",
        "assigned_application_name": "Grafana",
        "authorization_flow": "flow-001",
    }
]


class TestProvidersListMocked:
    def test_list_all_types(self, mock_client: MagicMock) -> None:
        mock_client.get_all.return_value = SAMPLE_OAUTH2
        result = runner.invoke(app, ["providers", "list"])
        assert result.exit_code == 0

    def test_list_filtered_oauth2(self, mock_client: MagicMock) -> None:
        mock_client.get_all.return_value = SAMPLE_OAUTH2
        result = runner.invoke(app, ["providers", "list", "--type", "oauth2"])
        assert result.exit_code == 0

    def test_list_json(self, mock_client: MagicMock) -> None:
        mock_client.get_all.return_value = SAMPLE_OAUTH2
        result = runner.invoke(app, ["--json", "providers", "list"])
        assert result.exit_code == 0


class TestOAuth2Commands:
    def test_oauth2_list(self, mock_client: MagicMock) -> None:
        mock_client.get_all.return_value = SAMPLE_OAUTH2
        result = runner.invoke(app, ["providers", "oauth2", "list"])
        assert result.exit_code == 0
        assert "mac-sfa" in result.output

    def test_oauth2_list_json(self, mock_client: MagicMock) -> None:
        mock_client.get_all.return_value = SAMPLE_OAUTH2
        result = runner.invoke(app, ["--json", "providers", "oauth2", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["name"] == "mac-sfa"

    def test_oauth2_list_empty(self, mock_client: MagicMock) -> None:
        mock_client.get_all.return_value = []
        result = runner.invoke(app, ["providers", "oauth2", "list"])
        assert result.exit_code == 0

    def test_oauth2_get(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_OAUTH2[0]
        result = runner.invoke(app, ["providers", "oauth2", "get", "1"])
        assert result.exit_code == 0
        assert "mac-sfa" in result.output

    def test_oauth2_get_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_OAUTH2[0]
        result = runner.invoke(app, ["--json", "providers", "oauth2", "get", "1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "mac-sfa"

    def test_oauth2_credentials(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_OAUTH2[0]
        result = runner.invoke(app, ["providers", "oauth2", "credentials", "1"])
        assert result.exit_code == 0
        assert "abc123" in result.output

    def test_oauth2_credentials_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_OAUTH2[0]
        result = runner.invoke(app, ["--json", "providers", "oauth2", "credentials", "1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["client_id"] == "abc123"

    def test_oauth2_create(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"results": [{"pk": "flow-001"}]}
        mock_client.post.return_value = {"pk": 3, "name": "new-provider", "client_id": "new123"}
        result = runner.invoke(app, ["providers", "oauth2", "create", "new-provider", "https://example.com/callback"])
        assert result.exit_code == 0
        assert "new-provider" in result.output

    def test_oauth2_update_no_fields(self, mock_client: MagicMock) -> None:
        result = runner.invoke(app, ["providers", "oauth2", "update", "1"])
        assert result.exit_code == 1

    def test_oauth2_update_name(self, mock_client: MagicMock) -> None:
        mock_client.patch.return_value = {"pk": 1, "name": "renamed", "client_type": "confidential"}
        result = runner.invoke(app, ["providers", "oauth2", "update", "1", "--name", "renamed"])
        assert result.exit_code == 0

    def test_oauth2_update_invalid_client_type(self, mock_client: MagicMock) -> None:
        result = runner.invoke(app, ["providers", "oauth2", "update", "1", "--client-type", "invalid"])
        assert result.exit_code == 1

    def test_oauth2_delete_with_force(self, mock_client: MagicMock) -> None:
        mock_client.delete.return_value = {}
        result = runner.invoke(app, ["providers", "oauth2", "delete", "1", "--force"])
        assert result.exit_code == 0
        mock_client.delete.assert_called_once()


class TestLDAPCommands:
    def test_ldap_list(self, mock_client: MagicMock) -> None:
        mock_client.get_all.return_value = SAMPLE_LDAP
        result = runner.invoke(app, ["providers", "ldap", "list"])
        assert result.exit_code == 0
        assert "ldap-provider" in result.output

    def test_ldap_list_empty(self, mock_client: MagicMock) -> None:
        mock_client.get_all.return_value = []
        result = runner.invoke(app, ["providers", "ldap", "list"])
        assert result.exit_code == 0

    def test_ldap_get(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_LDAP[0]
        result = runner.invoke(app, ["providers", "ldap", "get", "10"])
        assert result.exit_code == 0
        assert "ldap-provider" in result.output

    def test_ldap_delete_with_force(self, mock_client: MagicMock) -> None:
        mock_client.delete.return_value = {}
        result = runner.invoke(app, ["providers", "ldap", "delete", "10", "--force"])
        assert result.exit_code == 0


class TestProxyCommands:
    def test_proxy_list(self, mock_client: MagicMock) -> None:
        mock_client.get_all.return_value = SAMPLE_PROXY
        result = runner.invoke(app, ["providers", "proxy", "list"])
        assert result.exit_code == 0
        assert "proxy-grafana" in result.output

    def test_proxy_list_json(self, mock_client: MagicMock) -> None:
        mock_client.get_all.return_value = SAMPLE_PROXY
        result = runner.invoke(app, ["--json", "providers", "proxy", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["name"] == "proxy-grafana"

    def test_proxy_get(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_PROXY[0]
        result = runner.invoke(app, ["providers", "proxy", "get", "20"])
        assert result.exit_code == 0
        assert "proxy-grafana" in result.output

    def test_proxy_create(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"results": [{"pk": "flow-001"}]}
        mock_client.post.return_value = {"pk": 21, "name": "new-proxy"}
        result = runner.invoke(app, ["providers", "proxy", "create", "new-proxy", "https://app.kodeme.io"])
        assert result.exit_code == 0

    def test_proxy_delete_with_force(self, mock_client: MagicMock) -> None:
        mock_client.delete.return_value = {}
        result = runner.invoke(app, ["providers", "proxy", "delete", "20", "--force"])
        assert result.exit_code == 0
