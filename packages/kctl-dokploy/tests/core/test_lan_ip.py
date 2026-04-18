"""Unit tests for lan_ip module."""

from __future__ import annotations

from ipaddress import IPv4Address
from unittest.mock import patch

import pytest

from kctl_dokploy.core.lan_ip import current_lan_ipv4, is_private_ipv4


def test_is_private_ipv4_accepts_rfc1918() -> None:
    assert is_private_ipv4("192.168.1.5") is True
    assert is_private_ipv4("10.0.0.4") is True
    assert is_private_ipv4("172.16.5.7") is True


def test_is_private_ipv4_rejects_public_and_loopback() -> None:
    assert is_private_ipv4("8.8.8.8") is False
    assert is_private_ipv4("127.0.0.1") is False
    assert is_private_ipv4("169.254.1.1") is False  # link-local
    assert is_private_ipv4("not-an-ip") is False


def test_current_lan_ipv4_parses_ip_route_get() -> None:
    # Simulates: `ip -4 -o route get 1.1.1.1` output
    fake_out = "1.1.1.1 via 192.168.1.1 dev wlp0s20f3 src 192.168.1.5 uid 1000 \n   cache\n"
    with patch("kctl_dokploy.core.lan_ip._run_ip_route", return_value=fake_out):
        assert current_lan_ipv4() == IPv4Address("192.168.1.5")


def test_current_lan_ipv4_raises_when_no_src() -> None:
    with patch("kctl_dokploy.core.lan_ip._run_ip_route", return_value="no route"):
        with pytest.raises(RuntimeError, match="Could not determine LAN IP"):
            current_lan_ipv4()
