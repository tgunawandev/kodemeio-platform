"""Tests for kctl_accurate.core.exceptions translator."""

from __future__ import annotations

import httpx
from accurate_sdk.exceptions import (
    AccurateAPIError,
    AccurateRateLimitError,
    PaginationLimitExceeded,
)
from kctl_lib.exceptions import (
    APIError,
    AuthenticationError,
    ConfigError,
    NotFoundError,
)
from kctl_lib.exceptions import ConnectionError as KctlConnectionError

from kctl_accurate.core.exceptions import translate


def _http_status_error(code: int, body: str = "boom") -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.com/api")
    response = httpx.Response(code, content=body.encode(), request=request)
    return httpx.HTTPStatusError(f"HTTP {code}", request=request, response=response)


def test_translate_401_to_auth_error() -> None:
    out = translate(_http_status_error(401, "unauthorized"))
    assert isinstance(out, AuthenticationError)


def test_translate_403_to_auth_error() -> None:
    out = translate(_http_status_error(403, "forbidden"))
    assert isinstance(out, AuthenticationError)


def test_translate_404_to_not_found() -> None:
    out = translate(_http_status_error(404, "not found"))
    assert isinstance(out, NotFoundError)


def test_translate_429_to_api_error_with_rate_message() -> None:
    out = translate(_http_status_error(429, "too many"))
    assert isinstance(out, APIError)
    assert "rate" in str(out).lower()


def test_translate_500_to_api_error() -> None:
    out = translate(_http_status_error(503, "down"))
    assert isinstance(out, APIError)


def test_translate_request_error_to_connection_error() -> None:
    exc = httpx.ConnectError("network down")
    out = translate(exc)
    assert isinstance(out, KctlConnectionError)


def test_translate_accurate_rate_limit_error() -> None:
    out = translate(AccurateRateLimitError("retried 5 times, still 429"))
    assert isinstance(out, APIError)
    assert "rate" in str(out).lower()


def test_translate_accurate_api_error() -> None:
    out = translate(AccurateAPIError("s=false from API"))
    assert isinstance(out, APIError)
    assert "s=false" in str(out)


def test_translate_pagination_limit_exceeded() -> None:
    # PaginationLimitExceeded takes (path, row_count, max_pages, page_size)
    # The str() representation includes "rowCount=12345"
    out = translate(PaginationLimitExceeded("/api/customer/list.do", 12345, 100, 100))
    assert isinstance(out, APIError)
    assert "12345" in str(out)


def test_translate_passthrough_kctl_error() -> None:
    inner = ConfigError("missing token")
    out = translate(inner)
    assert out is inner  # never re-wrap


def test_translate_unknown_exception() -> None:
    out = translate(RuntimeError("???"))
    assert isinstance(out, APIError)
