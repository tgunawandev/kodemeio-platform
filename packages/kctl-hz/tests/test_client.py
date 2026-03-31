"""Tests for API clients using pytest-httpx."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from kctl_hz.core.client import HetznerCloudClient, HetznerDnsClient
from kctl_hz.core.exceptions import APIError, ConfigError


class TestCloudClient:
    """HetznerCloudClient tests."""

    def test_no_token_raises(self) -> None:
        with pytest.raises(ConfigError, match="No Cloud API token"):
            HetznerCloudClient(credential="")

    def test_get_servers(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://api.hetzner.cloud/v1/servers",
            json={"servers": [{"id": 1, "name": "web-1"}]},
        )
        client = HetznerCloudClient(credential="test-token")
        data = client.get("/servers")
        assert data["servers"][0]["name"] == "web-1"

    def test_auth_error_401(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://api.hetzner.cloud/v1/servers",
            status_code=401,
        )
        client = HetznerCloudClient(credential="bad-token")
        from kctl_lib.exceptions import AuthenticationError

        with pytest.raises(AuthenticationError):
            client.get("/servers")

    def test_auth_error_403(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://api.hetzner.cloud/v1/servers",
            status_code=403,
        )
        client = HetznerCloudClient(credential="limited-token")
        from kctl_lib.exceptions import AuthenticationError

        with pytest.raises(AuthenticationError):
            client.get("/servers")

    def test_api_error_404(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://api.hetzner.cloud/v1/servers/999",
            status_code=404,
            json={"error": {"message": "not found", "code": "not_found"}},
        )
        client = HetznerCloudClient(credential="test-token")
        with pytest.raises(APIError):
            client.get("/servers/999")

    def test_post_create_server(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://api.hetzner.cloud/v1/servers",
            method="POST",
            json={"server": {"id": 2, "name": "new-server"}, "action": {"id": 100}},
        )
        client = HetznerCloudClient(credential="test-token")
        result = client.post("/servers", json={"name": "new-server", "server_type": "cx22", "image": "ubuntu-24.04"})
        assert result["server"]["name"] == "new-server"

    def test_delete_server(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://api.hetzner.cloud/v1/servers/1",
            method="DELETE",
            status_code=200,
        )
        client = HetznerCloudClient(credential="test-token")
        client.delete("/servers/1")  # Should not raise

    def test_get_all_pagination(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://api.hetzner.cloud/v1/servers?per_page=50&page=1",
            json={
                "servers": [{"id": 1}],
                "meta": {"pagination": {"page": 1, "next_page": 2, "last_page": 2}},
            },
        )
        httpx_mock.add_response(
            url="https://api.hetzner.cloud/v1/servers?per_page=50&page=2",
            json={
                "servers": [{"id": 2}],
                "meta": {"pagination": {"page": 2, "next_page": None, "last_page": 2}},
            },
        )
        client = HetznerCloudClient(credential="test-token")
        results = client.get_all("/servers", "servers")
        assert len(results) == 2
        assert results[0]["id"] == 1
        assert results[1]["id"] == 2

    def test_context_manager(self, httpx_mock: HTTPXMock) -> None:
        with HetznerCloudClient(credential="test-token") as client:
            httpx_mock.add_response(
                url="https://api.hetzner.cloud/v1/servers",
                json={"servers": []},
            )
            data = client.get("/servers")
            assert data["servers"] == []


class TestDnsClient:
    """HetznerDnsClient tests."""

    def test_no_token_raises(self) -> None:
        with pytest.raises(ConfigError, match="No DNS API token"):
            HetznerDnsClient(credential="")

    def test_get_zones(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://dns.hetzner.com/api/v1/zones",
            json={"zones": [{"id": "z1", "name": "kodeme.io"}]},
        )
        client = HetznerDnsClient(credential="test-dns-token")
        data = client.get("/zones")
        assert data["zones"][0]["name"] == "kodeme.io"

    def test_create_record(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://dns.hetzner.com/api/v1/records",
            method="POST",
            json={"record": {"id": "r1", "type": "A", "name": "app", "value": "1.2.3.4"}},
        )
        client = HetznerDnsClient(credential="test-dns-token")
        result = client.post("/records", json={"zone_id": "z1", "type": "A", "name": "app", "value": "1.2.3.4"})
        assert result["record"]["type"] == "A"

    def test_put_record(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://dns.hetzner.com/api/v1/records/r1",
            method="PUT",
            json={"record": {"id": "r1", "type": "A", "name": "www", "value": "5.6.7.8"}},
        )
        client = HetznerDnsClient(credential="test-dns-token")
        result = client.put("/records/r1", json={"zone_id": "z1", "type": "A", "name": "www", "value": "5.6.7.8"})
        assert result["record"]["value"] == "5.6.7.8"

    def test_put_auth_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://dns.hetzner.com/api/v1/records/r1",
            method="PUT",
            status_code=401,
        )
        client = HetznerDnsClient(credential="bad-token")
        from kctl_lib.exceptions import AuthenticationError

        with pytest.raises(AuthenticationError):
            client.put("/records/r1", json={})

    def test_get_auth_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://dns.hetzner.com/api/v1/zones",
            status_code=401,
        )
        client = HetznerDnsClient(credential="bad-token")
        from kctl_lib.exceptions import AuthenticationError

        with pytest.raises(AuthenticationError):
            client.get("/zones")

    def test_delete_record(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://dns.hetzner.com/api/v1/records/r1",
            method="DELETE",
            status_code=200,
        )
        client = HetznerDnsClient(credential="test-dns-token")
        client.delete("/records/r1")  # Should not raise

    def test_api_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://dns.hetzner.com/api/v1/zones",
            status_code=400,
            json={"error": {"message": "bad request"}},
        )
        client = HetznerDnsClient(credential="test-dns-token")
        with pytest.raises(APIError):
            client.get("/zones")
