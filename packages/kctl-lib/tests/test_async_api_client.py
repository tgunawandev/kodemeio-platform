"""Tests for kctl_common.async_api_client — AsyncAPIClient base class."""

from __future__ import annotations

import httpx
import pytest
from pytest_httpx import HTTPXMock

from kctl_common.async_api_client import AsyncAPIClient
from kctl_common.exceptions import APIError, AuthenticationError, ConfigError
from kctl_common.exceptions import ConnectionError as KctlConnectionError

# ---------------------------------------------------------------------------
# Test subclasses
# ---------------------------------------------------------------------------


class SampleAsyncClient(AsyncAPIClient):
    AUTH_HEADER = "X-Api-Key"
    AUTH_PREFIX = ""
    API_PREFIX = "/api/v1"


class AsyncRetryClient(AsyncAPIClient):
    AUTH_HEADER = "x-api-key"
    AUTH_PREFIX = ""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(retry_enabled=True, max_retries=2, retry_base_delay=0.01, **kwargs)


# ---------------------------------------------------------------------------
# Constructor tests
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_requires_credential(self) -> None:
        with pytest.raises(ConfigError):
            SampleAsyncClient(base_url="https://example.com", credential="")

    def test_requires_base_url(self) -> None:
        with pytest.raises(ConfigError):
            SampleAsyncClient(credential="my-key")

    def test_api_prefix_appended(self) -> None:
        c = SampleAsyncClient(base_url="https://example.com", credential="key")
        assert c._base_url.endswith("/api/v1")

    def test_api_prefix_not_doubled(self) -> None:
        c = SampleAsyncClient(base_url="https://example.com/api/v1", credential="key")
        assert c._base_url.count("/api/v1") == 1

    def test_trailing_slash_cleaned(self) -> None:
        c = SampleAsyncClient(base_url="https://example.com/", credential="key")
        assert not c._base_url.endswith("/api/v1/")

    @pytest.mark.anyio
    async def test_async_context_manager(self) -> None:
        async with SampleAsyncClient(base_url="https://example.com", credential="key") as c:
            assert isinstance(c, SampleAsyncClient)


# ---------------------------------------------------------------------------
# Auth header tests
# ---------------------------------------------------------------------------


class TestAuthHeaders:
    def test_raw_key_no_prefix(self) -> None:
        c = SampleAsyncClient(base_url="https://example.com", credential="my-key")
        headers = c._build_auth_header()
        assert headers == {"X-Api-Key": "my-key"}


# ---------------------------------------------------------------------------
# Async HTTP method tests
# ---------------------------------------------------------------------------


class TestAsyncHTTPMethods:
    @pytest.mark.anyio
    async def test_get(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(url="https://example.com/api/v1/things", json={"ok": True})
        async with SampleAsyncClient(base_url="https://example.com", credential="key") as c:
            result = await c.get("/things")
        assert result == {"ok": True}

    @pytest.mark.anyio
    async def test_post(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(url="https://example.com/api/v1/things", json={"id": 1}, method="POST")
        async with SampleAsyncClient(base_url="https://example.com", credential="key") as c:
            result = await c.post("/things", json={"name": "x"})
        assert result == {"id": 1}

    @pytest.mark.anyio
    async def test_put(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(url="https://example.com/api/v1/things/1", json={"id": 1}, method="PUT")
        async with SampleAsyncClient(base_url="https://example.com", credential="key") as c:
            result = await c.put("/things/1", json={"name": "y"})
        assert result == {"id": 1}

    @pytest.mark.anyio
    async def test_patch(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(url="https://example.com/api/v1/things/1", json={"id": 1}, method="PATCH")
        async with SampleAsyncClient(base_url="https://example.com", credential="key") as c:
            result = await c.patch("/things/1", json={"name": "z"})
        assert result == {"id": 1}

    @pytest.mark.anyio
    async def test_delete(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(url="https://example.com/api/v1/things/1", method="DELETE", text="")
        async with SampleAsyncClient(base_url="https://example.com", credential="key") as c:
            result = await c.delete("/things/1")
        assert result == {}

    @pytest.mark.anyio
    async def test_empty_response_body(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(url="https://example.com/api/v1/empty", text="")
        async with SampleAsyncClient(base_url="https://example.com", credential="key") as c:
            result = await c.get("/empty")
        assert result == {}


# ---------------------------------------------------------------------------
# Error mapping tests
# ---------------------------------------------------------------------------


class TestAsyncErrorMapping:
    @pytest.mark.anyio
    async def test_401_raises_authentication_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=401, json={"detail": "invalid key"})
        async with SampleAsyncClient(base_url="https://example.com", credential="key") as c:
            with pytest.raises(AuthenticationError):
                await c.get("/secret")

    @pytest.mark.anyio
    async def test_500_raises_api_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=500, json={"error": "boom"})
        async with SampleAsyncClient(base_url="https://example.com", credential="key") as c:
            with pytest.raises(APIError) as exc_info:
                await c.get("/broken")
        assert exc_info.value.status_code == 500

    @pytest.mark.anyio
    async def test_connect_error_raises_connection_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_exception(httpx.ConnectError("refused"))
        async with SampleAsyncClient(base_url="https://example.com", credential="key") as c:
            with pytest.raises(KctlConnectionError):
                await c.get("/down")


# ---------------------------------------------------------------------------
# Retry tests
# ---------------------------------------------------------------------------


class TestAsyncRetry:
    @pytest.mark.anyio
    async def test_retries_on_5xx_and_recovers(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=502, json={"error": "bad gateway"})
        httpx_mock.add_response(status_code=502, json={"error": "bad gateway"})
        httpx_mock.add_response(status_code=200, json={"ok": True})
        async with AsyncRetryClient(base_url="https://example.com", credential="key") as c:
            result = await c.get("/flaky")
        assert result == {"ok": True}

    @pytest.mark.anyio
    async def test_retry_exhausted_raises(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=503, json={"error": "unavailable"})
        httpx_mock.add_response(status_code=503, json={"error": "unavailable"})
        httpx_mock.add_response(status_code=503, json={"error": "unavailable"})
        async with AsyncRetryClient(base_url="https://example.com", credential="key") as c:
            with pytest.raises(APIError) as exc_info:
                await c.get("/down")
        assert exc_info.value.status_code == 503

    @pytest.mark.anyio
    async def test_retry_on_connect_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_exception(httpx.ConnectError("refused"))
        httpx_mock.add_exception(httpx.ConnectError("refused"))
        httpx_mock.add_response(status_code=200, json={"ok": True})
        async with AsyncRetryClient(base_url="https://example.com", credential="key") as c:
            result = await c.get("/recovering")
        assert result == {"ok": True}
