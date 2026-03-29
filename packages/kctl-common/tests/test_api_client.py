"""Tests for kctl_common.api_client — APIClient base class."""

from __future__ import annotations

import httpx
import pytest
from pytest_httpx import HTTPXMock

from kctl_common.api_client import APIClient
from kctl_common.exceptions import APIError, AuthenticationError, ConfigError
from kctl_common.exceptions import ConnectionError as KctlConnectionError


# ---------------------------------------------------------------------------
# Test subclasses
# ---------------------------------------------------------------------------


class TestClient(APIClient):
    AUTH_HEADER = "X-Api-Key"
    AUTH_PREFIX = ""
    API_PREFIX = "/api/v1"


class CloudflareStyleClient(APIClient):
    BASE_URL = "https://api.example.com/v4"
    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"

    def _unwrap_response(self, response: httpx.Response) -> dict:  # type: ignore[override]
        data = response.json()
        if isinstance(data, dict) and "result" in data:
            return data["result"]  # type: ignore[no-any-return]
        return data  # type: ignore[no-any-return]


class RetryClient(APIClient):
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
            TestClient(base_url="https://example.com", credential="")

    def test_requires_base_url_when_no_class_base_url(self) -> None:
        with pytest.raises(ConfigError):
            TestClient(credential="my-key")

    def test_uses_class_base_url(self) -> None:
        c = CloudflareStyleClient(credential="tok123")
        assert "api.example.com" in c._base_url

    def test_instance_overrides_class_base_url(self) -> None:
        c = CloudflareStyleClient(base_url="https://custom.example.com/v4", credential="tok123")
        assert "custom.example.com" in c._base_url

    def test_api_prefix_appended(self) -> None:
        c = TestClient(base_url="https://example.com", credential="key")
        assert c._base_url.endswith("/api/v1")

    def test_api_prefix_not_doubled(self) -> None:
        c = TestClient(base_url="https://example.com/api/v1", credential="key")
        assert c._base_url.count("/api/v1") == 1

    def test_trailing_slash_cleaned(self) -> None:
        c = TestClient(base_url="https://example.com/", credential="key")
        assert not c._base_url.endswith("/api/v1/")

    def test_context_manager(self) -> None:
        with TestClient(base_url="https://example.com", credential="key") as c:
            assert isinstance(c, TestClient)


# ---------------------------------------------------------------------------
# Auth header tests
# ---------------------------------------------------------------------------


class TestAuthHeaders:
    def test_raw_key_no_prefix(self) -> None:
        c = TestClient(base_url="https://example.com", credential="my-key")
        headers = c._build_auth_header()
        assert headers == {"X-Api-Key": "my-key"}

    def test_bearer_prefix(self) -> None:
        c = CloudflareStyleClient(credential="tok123")
        headers = c._build_auth_header()
        assert headers == {"Authorization": "Bearer tok123"}


# ---------------------------------------------------------------------------
# HTTP method tests (using pytest-httpx)
# ---------------------------------------------------------------------------


class TestHTTPMethods:
    def test_get(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(url="https://example.com/api/v1/things", json={"ok": True})
        c = TestClient(base_url="https://example.com", credential="key")
        result = c.get("/things")
        assert result == {"ok": True}

    def test_post(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(url="https://example.com/api/v1/things", json={"id": 1}, method="POST")
        c = TestClient(base_url="https://example.com", credential="key")
        result = c.post("/things", json={"name": "x"})
        assert result == {"id": 1}

    def test_put(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(url="https://example.com/api/v1/things/1", json={"id": 1}, method="PUT")
        c = TestClient(base_url="https://example.com", credential="key")
        result = c.put("/things/1", json={"name": "y"})
        assert result == {"id": 1}

    def test_patch(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(url="https://example.com/api/v1/things/1", json={"id": 1}, method="PATCH")
        c = TestClient(base_url="https://example.com", credential="key")
        result = c.patch("/things/1", json={"name": "z"})
        assert result == {"id": 1}

    def test_delete(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(url="https://example.com/api/v1/things/1", method="DELETE", text="")
        c = TestClient(base_url="https://example.com", credential="key")
        result = c.delete("/things/1")
        assert result == {}

    def test_empty_response_body(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(url="https://example.com/api/v1/empty", text="")
        c = TestClient(base_url="https://example.com", credential="key")
        result = c.get("/empty")
        assert result == {}

    def test_params_passed(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json={"items": []})
        c = TestClient(base_url="https://example.com", credential="key")
        c.get("/search", params={"q": "test"})
        req = httpx_mock.get_request()
        assert req is not None
        assert "q=test" in str(req.url)


# ---------------------------------------------------------------------------
# Error mapping tests
# ---------------------------------------------------------------------------


class TestErrorMapping:
    def test_401_raises_authentication_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=401, json={"detail": "invalid key"})
        c = TestClient(base_url="https://example.com", credential="key")
        with pytest.raises(AuthenticationError):
            c.get("/secret")

    def test_403_raises_authentication_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=403, json={"detail": "forbidden"})
        c = TestClient(base_url="https://example.com", credential="key")
        with pytest.raises(AuthenticationError):
            c.get("/secret")

    def test_404_raises_api_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=404, json={"detail": "not found"})
        c = TestClient(base_url="https://example.com", credential="key")
        with pytest.raises(APIError) as exc_info:
            c.get("/missing")
        assert exc_info.value.status_code == 404

    def test_500_raises_api_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=500, json={"error": "boom"})
        c = TestClient(base_url="https://example.com", credential="key")
        with pytest.raises(APIError) as exc_info:
            c.get("/broken")
        assert exc_info.value.status_code == 500

    def test_connect_error_raises_connection_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_exception(httpx.ConnectError("refused"))
        c = TestClient(base_url="https://example.com", credential="key")
        with pytest.raises(KctlConnectionError):
            c.get("/down")

    def test_timeout_raises_connection_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_exception(httpx.ReadTimeout("timed out"))
        c = TestClient(base_url="https://example.com", credential="key")
        with pytest.raises(KctlConnectionError):
            c.get("/slow")


# ---------------------------------------------------------------------------
# Response unwrapping tests
# ---------------------------------------------------------------------------


class TestResponseUnwrapping:
    def test_default_returns_json_as_is(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json={"foo": "bar"})
        c = TestClient(base_url="https://example.com", credential="key")
        assert c.get("/data") == {"foo": "bar"}

    def test_custom_unwrap_response(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json={"success": True, "result": {"id": 42}})
        c = CloudflareStyleClient(credential="tok")
        assert c.get("/zones") == {"id": 42}


# ---------------------------------------------------------------------------
# Retry tests
# ---------------------------------------------------------------------------


class TestRetry:
    def test_retries_on_5xx(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=502, json={"error": "bad gateway"})
        httpx_mock.add_response(status_code=502, json={"error": "bad gateway"})
        httpx_mock.add_response(status_code=200, json={"ok": True})
        c = RetryClient(base_url="https://example.com", credential="key")
        result = c.get("/flaky")
        assert result == {"ok": True}

    def test_no_retry_on_4xx(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=400, json={"detail": "bad request"})
        c = RetryClient(base_url="https://example.com", credential="key")
        with pytest.raises(APIError) as exc_info:
            c.get("/bad")
        assert exc_info.value.status_code == 400
        # Only one request should have been made
        assert len(httpx_mock.get_requests()) == 1

    def test_retry_exhausted_raises(self, httpx_mock: HTTPXMock) -> None:
        # max_retries=2, so 1 initial + 2 retries = 3 total attempts
        httpx_mock.add_response(status_code=503, json={"error": "unavailable"})
        httpx_mock.add_response(status_code=503, json={"error": "unavailable"})
        httpx_mock.add_response(status_code=503, json={"error": "unavailable"})
        c = RetryClient(base_url="https://example.com", credential="key")
        with pytest.raises(APIError) as exc_info:
            c.get("/down")
        assert exc_info.value.status_code == 503

    def test_retry_on_connect_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_exception(httpx.ConnectError("refused"))
        httpx_mock.add_exception(httpx.ConnectError("refused"))
        httpx_mock.add_response(status_code=200, json={"ok": True})
        c = RetryClient(base_url="https://example.com", credential="key")
        result = c.get("/recovering")
        assert result == {"ok": True}

    def test_retry_disabled_by_default(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=502, json={"error": "bad gateway"})
        c = TestClient(base_url="https://example.com", credential="key")
        with pytest.raises(APIError):
            c.get("/flaky")
        assert len(httpx_mock.get_requests()) == 1


# ---------------------------------------------------------------------------
# Debug logging tests
# ---------------------------------------------------------------------------


class TestDebugLogging:
    def test_logs_when_debug_enabled(
        self, httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("KCTL_DEBUG", "1")
        httpx_mock.add_response(json={"ok": True})
        c = TestClient(base_url="https://example.com", credential="key")
        c.get("/things")
        captured = capsys.readouterr()
        assert "GET" in captured.err

    def test_no_logs_by_default(self, httpx_mock: HTTPXMock, capsys: pytest.CaptureFixture[str]) -> None:
        httpx_mock.add_response(json={"ok": True})
        c = TestClient(base_url="https://example.com", credential="key")
        c.get("/things")
        captured = capsys.readouterr()
        assert captured.err == ""
