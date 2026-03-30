"""Tests for DokployClient."""

from __future__ import annotations

import pytest

from kctl_dokploy.core.client import DokployClient
from kctl_dokploy.core.exceptions import (
    APIError,
    AuthenticationError,
    ConfigError,
)


class TestClientInit:
    def test_requires_url(self) -> None:
        with pytest.raises(ConfigError, match="No URL"):
            DokployClient(base_url="", api_key="test")

    def test_appends_api_path(self) -> None:
        client = DokployClient(base_url="https://dokploy.io", api_key="k")
        assert client._base_url == "https://dokploy.io/api"
        client.close()

    def test_preserves_api_path(self) -> None:
        client = DokployClient(base_url="https://dokploy.io/api", api_key="k")
        assert client._base_url == "https://dokploy.io/api"
        client.close()

    def test_context_manager(self) -> None:
        with DokployClient(base_url="https://dokploy.io", api_key="k") as client:
            assert client._base_url == "https://dokploy.io/api"


class TestClientRequests:
    """Test request routing using httpx_mock (pytest-httpx)."""

    def test_get_returns_json(self, httpx_mock) -> None:
        httpx_mock.add_response(json={"status": "ok"})
        with DokployClient(base_url="https://test.io/api", api_key="k", max_retries=0) as client:
            result = client.get("/health")
        assert result == {"status": "ok"}

    def test_post_sends_json(self, httpx_mock) -> None:
        httpx_mock.add_response(json={"id": "123"})
        with DokployClient(base_url="https://test.io/api", api_key="k", max_retries=0) as client:
            result = client.post("/create", json={"name": "test"})
        assert result["id"] == "123"

    def test_put_method(self, httpx_mock) -> None:
        httpx_mock.add_response(json={"updated": True})
        with DokployClient(base_url="https://test.io/api", api_key="k", max_retries=0) as client:
            result = client.put("/update", json={"name": "new"})
        assert result["updated"] is True

    def test_patch_method(self, httpx_mock) -> None:
        httpx_mock.add_response(json={"patched": True})
        with DokployClient(base_url="https://test.io/api", api_key="k", max_retries=0) as client:
            result = client.patch("/patch", json={"field": "val"})
        assert result["patched"] is True

    def test_delete_method(self, httpx_mock) -> None:
        httpx_mock.add_response(json={})
        with DokployClient(base_url="https://test.io/api", api_key="k", max_retries=0) as client:
            result = client.delete("/remove", json={"id": "x"})
        assert result == {}

    def test_401_raises_auth_error(self, httpx_mock) -> None:
        httpx_mock.add_response(status_code=401)
        with (
            DokployClient(base_url="https://test.io/api", api_key="bad", max_retries=0) as client,
            pytest.raises(AuthenticationError),
        ):
            client.get("/protected")

    def test_403_raises_auth_error(self, httpx_mock) -> None:
        httpx_mock.add_response(status_code=403)
        with (
            DokployClient(base_url="https://test.io/api", api_key="k", max_retries=0) as client,
            pytest.raises(AuthenticationError),
        ):
            client.get("/forbidden")

    def test_422_raises_api_error(self, httpx_mock) -> None:
        httpx_mock.add_response(status_code=422, json={"detail": "validation failed"})
        with (
            DokployClient(base_url="https://test.io/api", api_key="k", max_retries=0) as client,
            pytest.raises(APIError) as exc_info,
        ):
            client.post("/validate")
        assert exc_info.value.status_code == 422

    def test_empty_response_returns_empty_dict(self, httpx_mock) -> None:
        httpx_mock.add_response(content=b"")
        with DokployClient(base_url="https://test.io/api", api_key="k", max_retries=0) as client:
            result = client.get("/empty")
        assert result == {}


class TestRetryLogic:
    def test_retries_on_500(self, httpx_mock) -> None:
        httpx_mock.add_response(status_code=500)
        httpx_mock.add_response(json={"ok": True})
        with DokployClient(base_url="https://test.io/api", api_key="k", max_retries=1, retry_base_delay=0.01) as client:
            result = client.get("/flaky")
        assert result == {"ok": True}

    def test_no_retry_on_400(self, httpx_mock) -> None:
        httpx_mock.add_response(status_code=400, json={"detail": "bad request"})
        with (
            DokployClient(base_url="https://test.io/api", api_key="k", max_retries=3, retry_base_delay=0.01) as client,
            pytest.raises(APIError),
        ):
            client.get("/bad")
