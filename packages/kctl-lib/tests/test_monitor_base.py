"""Tests for kctl_lib.monitor_base."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from kctl_lib.monitor_base import dns_check, health_check_url, ssl_check


class TestHealthCheckUrl:
    @patch("kctl_lib.monitor_base.httpx")
    def test_healthy(self, mock_httpx: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.elapsed.total_seconds.return_value = 0.15
        mock_resp.text = '{"status": "ok"}'
        mock_httpx.get.return_value = mock_resp
        result = health_check_url("https://example.com/health")
        assert result["status_code"] == 200 and result["healthy"] is True

    @patch("kctl_lib.monitor_base.httpx")
    def test_unhealthy(self, mock_httpx: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.elapsed.total_seconds.return_value = 1.0
        mock_resp.text = "err"
        mock_httpx.get.return_value = mock_resp
        result = health_check_url("https://example.com/health")
        assert result["healthy"] is False

    @patch("kctl_lib.monitor_base.httpx")
    def test_error(self, mock_httpx: MagicMock) -> None:
        mock_httpx.get.side_effect = Exception("refused")
        result = health_check_url("https://example.com/health")
        assert result["healthy"] is False and "error" in result


class TestDnsCheck:
    @patch("kctl_lib.monitor_base.socket")
    def test_resolves(self, mock_socket: MagicMock) -> None:
        mock_socket.getaddrinfo.return_value = [(2, 1, 6, "", ("93.184.216.34", 443))]
        mock_socket.AF_UNSPEC = 0
        mock_socket.SOCK_STREAM = 1
        result = dns_check("example.com")
        assert result["resolved"] is True and result["ip"] == "93.184.216.34"

    @patch("kctl_lib.monitor_base.socket")
    def test_fails(self, mock_socket: MagicMock) -> None:
        mock_socket.getaddrinfo.side_effect = OSError("nope")
        mock_socket.AF_UNSPEC = 0
        mock_socket.SOCK_STREAM = 1
        result = dns_check("bad.invalid")
        assert result["resolved"] is False


class TestSslCheck:
    def test_returns_dict_with_domain(self) -> None:
        # Smoke test: ssl_check always returns a dict with the domain key
        result = ssl_check("this-domain-does-not-exist.invalid")
        assert isinstance(result, dict)
        assert result["domain"] == "this-domain-does-not-exist.invalid"
        assert result["valid"] is False
