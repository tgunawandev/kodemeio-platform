"""Tests for health check orchestration."""

from __future__ import annotations

from unittest.mock import MagicMock

from kctl_dokploy.core.health_ops import (
    get_health_url,
    quick_health_check,
)


class TestGetHealthUrl:
    def test_known_service_n8n(self) -> None:
        url = get_health_url("https://n8n.kodeme.io", "n8n")
        assert url == "https://n8n.kodeme.io/healthz"

    def test_known_service_odoo(self) -> None:
        url = get_health_url("https://erp.kodeme.io", "odoo")
        assert url == "https://erp.kodeme.io/web/health"

    def test_known_service_grafana(self) -> None:
        url = get_health_url("https://grafana.kodeme.io", "grafana")
        assert url == "https://grafana.kodeme.io/api/health"

    def test_known_service_authentik(self) -> None:
        url = get_health_url("https://auth.kodeme.io", "authentik")
        assert url == "https://auth.kodeme.io/-/health/live/"

    def test_unknown_service_fallback(self) -> None:
        url = get_health_url("https://custom.kodeme.io", "custom")
        assert url == "https://custom.kodeme.io/"

    def test_no_hint_extracts_from_hostname(self) -> None:
        url = get_health_url("https://grafana.kodeme.io")
        assert url == "https://grafana.kodeme.io/api/health"

    def test_strips_trailing_slash(self) -> None:
        url = get_health_url("https://n8n.kodeme.io/", "n8n")
        assert url == "https://n8n.kodeme.io/healthz"


class TestQuickHealthCheck:
    def test_returns_status(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"composeStatus": "done"}
        result = quick_health_check(mock_client, "c1")
        assert result == "done"

    def test_returns_unreachable_on_error(self, mock_client: MagicMock) -> None:
        mock_client.get.side_effect = Exception("down")
        result = quick_health_check(mock_client, "c1")
        assert result == "unreachable"

    def test_returns_unknown_for_bad_response(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = "not a dict"
        result = quick_health_check(mock_client, "c1")
        assert result == "unknown"
