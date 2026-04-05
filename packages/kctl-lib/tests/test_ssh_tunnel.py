"""Tests for kctl_lib.ssh_tunnel module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kctl_lib.exceptions import ConnectionError as KctlConnectionError
from kctl_lib.ssh_tunnel import SSHTunnel


class TestSSHTunnel:
    def test_local_port_before_start_raises(self):
        t = SSHTunnel(ssh_host="1.2.3.4")
        with pytest.raises(RuntimeError, match="not started"):
            _ = t.local_port

    @patch("sshtunnel.SSHTunnelForwarder")
    def test_start_and_stop(self, mock_forwarder_cls):
        mock_tunnel = MagicMock()
        mock_tunnel.local_bind_port = 54321
        mock_forwarder_cls.return_value = mock_tunnel

        t = SSHTunnel(ssh_host="1.2.3.4", remote_port=5432)
        port = t.start()
        assert port == 54321
        mock_tunnel.start.assert_called_once()

        t.stop()
        mock_tunnel.stop.assert_called_once()

    @patch("sshtunnel.SSHTunnelForwarder")
    def test_context_manager(self, mock_forwarder_cls):
        mock_tunnel = MagicMock()
        mock_tunnel.local_bind_port = 12345
        mock_forwarder_cls.return_value = mock_tunnel

        with SSHTunnel(ssh_host="1.2.3.4") as t:
            assert t.local_port == 12345
        mock_tunnel.stop.assert_called_once()

    @patch(
        "sshtunnel.SSHTunnelForwarder",
        side_effect=Exception("Connection refused"),
    )
    def test_start_failure(self, mock_cls):
        t = SSHTunnel(ssh_host="1.2.3.4")
        with pytest.raises(KctlConnectionError, match="1.2.3.4"):
            t.start()

    @patch("sshtunnel.SSHTunnelForwarder")
    def test_stop_idempotent(self, mock_forwarder_cls):
        """Calling stop() twice should not raise."""
        mock_tunnel = MagicMock()
        mock_tunnel.local_bind_port = 11111
        mock_forwarder_cls.return_value = mock_tunnel

        t = SSHTunnel(ssh_host="1.2.3.4")
        t.start()
        t.stop()
        t.stop()  # Second call should be safe

    @patch("sshtunnel.SSHTunnelForwarder")
    def test_custom_ssh_key(self, mock_forwarder_cls):
        mock_tunnel = MagicMock()
        mock_tunnel.local_bind_port = 22222
        mock_forwarder_cls.return_value = mock_tunnel

        t = SSHTunnel(ssh_host="1.2.3.4", ssh_key="~/.ssh/id_ed25519")
        t.start()
        call_kwargs = mock_forwarder_cls.call_args
        assert call_kwargs[1]["ssh_pkey"] is not None
