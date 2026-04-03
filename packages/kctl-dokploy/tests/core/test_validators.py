"""Tests for deploy validation gates."""

from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch

from kctl_dokploy.core.validators import (
    resolve_server_ip,
    validate_dns_ip,
    validate_dns_resolution,
)


# ---------------------------------------------------------------------------
# resolve_server_ip
# ---------------------------------------------------------------------------


class TestResolveServerIp:
    def test_returns_ip_for_matching_server(self) -> None:
        client = MagicMock()
        client.get.return_value = [
            {"name": "kodeme-service", "ipAddress": "49.13.14.79"},
            {"name": "kodeme-dev", "ipAddress": "10.0.0.1"},
        ]
        ok, msg, ip = resolve_server_ip(client, "kodeme-service")
        assert ok is True
        assert ip == "49.13.14.79"

    def test_fails_when_server_not_found(self) -> None:
        client = MagicMock()
        client.get.return_value = [
            {"name": "kodeme-service", "ipAddress": "49.13.14.79"},
        ]
        ok, msg, ip = resolve_server_ip(client, "nonexistent")
        assert ok is False
        assert ip == ""
        assert "not found" in msg

    def test_fails_when_server_has_no_ip(self) -> None:
        client = MagicMock()
        client.get.return_value = [
            {"name": "kodeme-service", "ipAddress": ""},
        ]
        ok, msg, ip = resolve_server_ip(client, "kodeme-service")
        assert ok is False
        assert "no IP" in msg

    def test_returns_ok_when_no_server_specified(self) -> None:
        ok, msg, ip = resolve_server_ip(MagicMock(), "")
        assert ok is True
        assert ip == ""

    def test_handles_api_error(self) -> None:
        client = MagicMock()
        client.get.side_effect = Exception("connection refused")
        ok, msg, ip = resolve_server_ip(client, "kodeme-service")
        assert ok is False
        assert "Failed to fetch" in msg


# ---------------------------------------------------------------------------
# validate_dns_ip
# ---------------------------------------------------------------------------


class TestValidateDnsIp:
    def test_matches(self) -> None:
        ok, msg = validate_dns_ip("49.13.14.79", "49.13.14.79", "kodeme-service")
        assert ok is True

    def test_mismatch(self) -> None:
        ok, msg = validate_dns_ip("1.2.3.4", "49.13.14.79", "kodeme-service")
        assert ok is False
        assert "MISMATCH" in msg

    def test_empty_manifest_ip(self) -> None:
        ok, msg = validate_dns_ip("", "49.13.14.79", "kodeme-service")
        assert ok is True

    def test_empty_server_ip(self) -> None:
        ok, msg = validate_dns_ip("1.2.3.4", "", "kodeme-service")
        assert ok is True


# ---------------------------------------------------------------------------
# validate_dns_resolution
# ---------------------------------------------------------------------------


class TestValidateDnsResolution:
    def test_passes_when_ip_matches(self) -> None:
        fake_result = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("49.13.14.79", 0))]
        with patch("socket.getaddrinfo", return_value=fake_result):
            ok, msg = validate_dns_resolution("app.kodeme.io", "49.13.14.79", max_retries=1)
        assert ok is True
        assert "verified" in msg

    def test_fails_when_ip_mismatches(self) -> None:
        fake_result = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.1", 0))]
        with patch("socket.getaddrinfo", return_value=fake_result):
            ok, msg = validate_dns_resolution("app.kodeme.io", "49.13.14.79", max_retries=1)
        assert ok is False
        assert "mismatch" in msg.lower()

    def test_fails_on_resolution_error(self) -> None:
        with patch("socket.getaddrinfo", side_effect=socket.gaierror("NXDOMAIN")):
            ok, msg = validate_dns_resolution("nope.kodeme.io", "49.13.14.79", max_retries=1)
        assert ok is False
        assert "resolution failed" in msg.lower()

    def test_retries_on_failure(self) -> None:
        fail_result = socket.gaierror("NXDOMAIN")
        success_result = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("49.13.14.79", 0))]

        with patch("socket.getaddrinfo", side_effect=[fail_result, success_result]) as mock_gai:
            with patch("time.sleep"):  # Don't actually sleep
                ok, msg = validate_dns_resolution("app.kodeme.io", "49.13.14.79", max_retries=2, retry_delay=0.01)
        assert ok is True
        assert mock_gai.call_count == 2

    def test_skips_when_no_expected_ip(self) -> None:
        ok, msg = validate_dns_resolution("app.kodeme.io", "")
        assert ok is True
        assert "skipping" in msg.lower()
