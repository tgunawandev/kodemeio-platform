"""Tests for GrafanaClient."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kctl_grafana.core.client import GrafanaClient


class TestGrafanaClient:
    """Test GrafanaClient initialization and methods."""

    def test_missing_url_raises(self) -> None:
        with pytest.raises(Exception, match="No URL configured"):
            GrafanaClient(base_url="", api_key="test-key")

    @patch("kctl_grafana.core.client.httpx.get")
    def test_check_health_success(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"database": "ok", "version": "11.4.0"}
        mock_get.return_value = mock_response

        client = GrafanaClient(base_url="https://grafana.kodeme.io", api_key="test-key")
        health = client.check_health()

        assert health["database"] == "ok"
        assert health["version"] == "11.4.0"

    @patch("kctl_grafana.core.client.httpx.get")
    def test_check_health_unreachable(self, mock_get: MagicMock) -> None:
        import httpx

        mock_get.side_effect = httpx.ConnectError("Connection refused")

        client = GrafanaClient(base_url="https://grafana.kodeme.io", api_key="test-key")
        health = client.check_health()

        assert health["status"] == "error"

    @patch("kctl_grafana.core.client.httpx.get")
    def test_get_version(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"database": "ok", "version": "11.4.0"}
        mock_get.return_value = mock_response

        client = GrafanaClient(base_url="https://grafana.kodeme.io", api_key="test-key")
        version = client.get_version()

        assert version == "11.4.0"

    def test_root_url(self) -> None:
        client = GrafanaClient(base_url="https://grafana.kodeme.io", api_key="test-key")
        assert client.root_url == "https://grafana.kodeme.io"
