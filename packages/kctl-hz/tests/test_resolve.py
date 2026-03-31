"""Tests for the centralized resource resolution module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import typer

from kctl_hz.core.resolve import (
    resolve_dns_zone_id,
    resolve_firewall,
    resolve_load_balancer,
    resolve_network,
    resolve_server,
    resolve_volume,
)


@pytest.fixture
def client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def dns_client() -> MagicMock:
    return MagicMock()


class TestResolveServer:
    """resolve_server tests."""

    def test_by_name(self, client: MagicMock) -> None:
        client.get.return_value = {"servers": [{"id": 1, "name": "web-1"}]}
        result = resolve_server(client, "web-1")
        assert result["id"] == 1
        client.get.assert_called_once_with("/servers", params={"name": "web-1"})

    def test_not_found(self, client: MagicMock) -> None:
        client.get.return_value = {"servers": []}
        with pytest.raises(typer.Exit):
            resolve_server(client, "nonexistent")

    def test_by_id(self, client: MagicMock) -> None:
        client.get.return_value = {"server": {"id": 42, "name": "web-42"}}
        result = resolve_server(client, "42")
        assert result["id"] == 42
        client.get.assert_called_once_with("/servers/42")


class TestResolveVolume:
    """resolve_volume tests."""

    def test_by_name(self, client: MagicMock) -> None:
        client.get.return_value = {"volumes": [{"id": 10, "name": "data-vol"}]}
        result = resolve_volume(client, "data-vol")
        assert result["id"] == 10

    def test_not_found(self, client: MagicMock) -> None:
        client.get.return_value = {"volumes": []}
        with pytest.raises(typer.Exit):
            resolve_volume(client, "missing")


class TestResolveFirewall:
    """resolve_firewall tests."""

    def test_by_name(self, client: MagicMock) -> None:
        client.get.return_value = {"firewalls": [{"id": 5, "name": "web-fw"}]}
        result = resolve_firewall(client, "web-fw")
        assert result["id"] == 5


class TestResolveNetwork:
    """resolve_network tests."""

    def test_by_name(self, client: MagicMock) -> None:
        client.get.return_value = {"networks": [{"id": 3, "name": "internal"}]}
        result = resolve_network(client, "internal")
        assert result["id"] == 3


class TestResolveLoadBalancer:
    """resolve_load_balancer tests."""

    def test_by_name(self, client: MagicMock) -> None:
        client.get.return_value = {"load_balancers": [{"id": 7, "name": "web-lb"}]}
        result = resolve_load_balancer(client, "web-lb")
        assert result["id"] == 7


class TestResolveDnsZoneId:
    """resolve_dns_zone_id tests."""

    def test_found(self, dns_client: MagicMock) -> None:
        dns_client.get.return_value = {"zones": [{"id": "z1", "name": "kodeme.io"}]}
        result = resolve_dns_zone_id(dns_client, "kodeme.io")
        assert result == "z1"

    def test_not_found(self, dns_client: MagicMock) -> None:
        dns_client.get.return_value = {"zones": []}
        with pytest.raises(typer.Exit):
            resolve_dns_zone_id(dns_client, "missing.io")
