"""Tests for certificates commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_dokploy.cli import app
from kctl_dokploy.core.callbacks import AppContext

runner = CliRunner()

SAMPLE_CERTS = [
    {
        "certificateId": "cert-aaa-111",
        "name": "kodeme-wildcard",
        "certificateType": "letsencrypt",
        "autoRenew": True,
        "expiresAt": "2026-06-01T00:00:00Z",
        "domain": "*.kodeme.io",
        "createdAt": "2026-03-01T00:00:00Z",
    },
    {
        "certificateId": "cert-bbb-222",
        "name": "api-cert",
        "certificateType": "letsencrypt",
        "autoRenew": True,
        "expiresAt": "2026-07-15T00:00:00Z",
        "domain": "api.kodeme.io",
        "createdAt": "2026-04-01T00:00:00Z",
    },
]


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


class TestCertificatesList:
    def test_list_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_CERTS
        result = runner.invoke(app, ["--json", "certificates", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "kodeme-wildcard"

    def test_list_empty(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = []
        result = runner.invoke(app, ["--json", "certificates", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []


class TestCertificatesGet:
    def test_get_certificate_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_CERTS[0]
        result = runner.invoke(app, ["--json", "certificates", "get", "cert-aaa-111"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "kodeme-wildcard"
        assert data["certificateType"] == "letsencrypt"

    def test_get_not_found_exits_1(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = "not a dict"
        result = runner.invoke(app, ["certificates", "get", "nonexistent"])
        assert result.exit_code == 1


class TestCertificatesCreate:
    def test_create_letsencrypt_cert(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"certificateId": "cert-new-001"}
        result = runner.invoke(
            app,
            [
                "--json",
                "certificates",
                "create",
                "--name",
                "my-cert",
                "--domain",
                "app.kodeme.io",
            ],
        )
        assert result.exit_code == 0
        assert "my-cert" in result.output


class TestCertificatesRemove:
    def test_remove_with_force(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["certificates", "remove", "cert-bbb-222", "--force"])
        assert result.exit_code == 0

    def test_remove_prompts_without_force(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["certificates", "remove", "cert-bbb-222"], input="y\n")
        assert result.exit_code == 0

    def test_renew_certificate(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["certificates", "renew", "cert-aaa-111"])
        assert result.exit_code == 0
