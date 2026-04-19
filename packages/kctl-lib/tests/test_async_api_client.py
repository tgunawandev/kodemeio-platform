"""Tests for kctl_lib.async_api_client — AsyncAPIClient base class."""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from pytest_httpx import HTTPXMock

from kctl_lib.async_api_client import AsyncAPIClient
from kctl_lib.exceptions import APIError, AuthenticationError, ConfigError
from kctl_lib.exceptions import ConnectionError as KctlConnectionError

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


# ---------------------------------------------------------------------------
# stream_subscription tests — tRPC SSE consumer
# ---------------------------------------------------------------------------


class TestStreamSubscription:
    """Consume Dokploy tRPC SSE subscription.

    Wire format from Task 1 spike:
      - GET /api/trpc/<procedure>?input=<url-encoded {"json":{...}}>
      - Response Content-Type: text/event-stream
      - `event: connected\\ndata: {}` → skip (control)
      - `data: {"json":"<line>"}` (unnamed event) → yield "<line>"
      - `event: serialized-error\\ndata: {"json":{"message":"..."}}`
        → yield `Error: <message>`
      - `event: return\\ndata: ` → skip (end-of-stream marker)
    """

    @pytest.mark.anyio
    async def test_yields_log_lines_skips_control_events(self) -> None:
        sse_body = (
            b"event: connected\n"
            b"data: {}\n"
            b"\n"
            b'data: {"json":"Starting restore..."}\n'
            b"\n"
            b'data: {"json":"Downloaded 10.1 MB"}\n'
            b"\n"
            b'data: {"json":"Restore completed successfully"}\n'
            b"\n"
            b"event: return\n"
            b"data: \n"
            b"\n"
        )

        captured_request: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_request["method"] = request.method
            captured_request["url"] = str(request.url)
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=sse_body,
            )

        transport = httpx.MockTransport(handler)

        class _Client(AsyncAPIClient):
            BASE_URL = "http://localhost:3000"
            API_PREFIX = "/api"
            AUTH_HEADER = "x-api-key"
            AUTH_PREFIX = ""

        c = _Client(credential="T")
        c._client = httpx.AsyncClient(transport=transport, base_url=c._base_url)

        lines: list[str] = []
        async for line in c.stream_subscription(
            "/trpc/backup.restoreBackupWithLogs",
            {"json": {"backupType": "compose", "databaseId": "cmp-1"}},
        ):
            lines.append(line)

        await c._client.aclose()

        # Must GET, not POST.
        assert captured_request["method"] == "GET"
        # Must include URL-encoded input= query param carrying the payload.
        parsed = urlparse(captured_request["url"])
        qs = parse_qs(parsed.query)
        assert "input" in qs
        input_json = json.loads(qs["input"][0])
        assert input_json == {"json": {"backupType": "compose", "databaseId": "cmp-1"}}
        # Skips named 'connected' + 'return' events; yields only the log-line strings.
        assert lines == [
            "Starting restore...",
            "Downloaded 10.1 MB",
            "Restore completed successfully",
        ]

    @pytest.mark.anyio
    async def test_serialized_error_event_becomes_error_line(self) -> None:
        sse_body = (
            b"event: connected\n"
            b"data: {}\n"
            b"\n"
            b'data: {"json":"Starting..."}\n'
            b"\n"
            b"event: serialized-error\n"
            b'data: {"json":{"message":"pg_restore crashed: exit 1"}}\n'
            b"\n"
        )

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=sse_body,
            )

        transport = httpx.MockTransport(handler)

        class _Client(AsyncAPIClient):
            BASE_URL = "http://localhost:3000"
            API_PREFIX = "/api"
            AUTH_HEADER = "x-api-key"
            AUTH_PREFIX = ""

        c = _Client(credential="T")
        c._client = httpx.AsyncClient(transport=transport, base_url=c._base_url)

        lines: list[str] = []
        async for line in c.stream_subscription("/trpc/foo", {"json": {}}):
            lines.append(line)

        await c._client.aclose()

        # Log-line + error-line, in order. Error must start with "Error: " so
        # the downstream command can exit 1 on it.
        assert lines == [
            "Starting...",
            "Error: pg_restore crashed: exit 1",
        ]

    @pytest.mark.anyio
    async def test_4xx_raises_api_error_before_stream(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                400,
                headers={"content-type": "application/json"},
                json={"error": {"message": "Input validation failed"}},
            )

        transport = httpx.MockTransport(handler)

        class _Client(AsyncAPIClient):
            BASE_URL = "http://localhost:3000"
            API_PREFIX = "/api"
            AUTH_HEADER = "x-api-key"
            AUTH_PREFIX = ""

        c = _Client(credential="T")
        c._client = httpx.AsyncClient(transport=transport, base_url=c._base_url)

        with pytest.raises(APIError) as exc_info:
            async for _ in c.stream_subscription("/trpc/backup.x", {"json": {}}):
                pass

        await c._client.aclose()

        assert exc_info.value.status_code == 400
