"""Tests for kctl_accurate.core.client.AccurateClientWrapper."""

from __future__ import annotations

import pytest
from kctl_lib.exceptions import APIError, AuthenticationError, ConfigError
from kctl_lib.exceptions import ConnectionError as KctlConnectionError
from pytest_httpx import HTTPXMock

from kctl_accurate.core.client import AccurateClientWrapper
from kctl_accurate.core.config import ServiceConfig


def _make_wrapper(**overrides: object) -> AccurateClientWrapper:
    cfg = ServiceConfig(
        api_token="aut.fake-token-1234",
        signature_secret="secretsecret",
        db_id=12345,
        host="https://public.accurate.id",
    )
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return AccurateClientWrapper(cfg)


def test_blank_token_raises_config_error() -> None:
    cfg = ServiceConfig()
    with pytest.raises(ConfigError) as exc_info:
        AccurateClientWrapper(cfg)
    assert "api_token" in str(exc_info.value)


def test_blank_secret_raises_config_error() -> None:
    cfg = ServiceConfig(api_token="t", db_id=1)
    with pytest.raises(ConfigError) as exc_info:
        AccurateClientWrapper(cfg)
    assert "signature_secret" in str(exc_info.value)


def test_blank_db_id_raises_config_error() -> None:
    cfg = ServiceConfig(api_token="t", signature_secret="s")
    with pytest.raises(ConfigError) as exc_info:
        AccurateClientWrapper(cfg)
    assert "db_id" in str(exc_info.value)


def test_token_info_success(httpx_mock: HTTPXMock) -> None:
    # AccurateClient.token_info() uses POST to the token discovery endpoint.
    httpx_mock.add_response(
        method="POST",
        url="https://account.accurate.id/api/api-token.do",
        json={
            "s": True,
            "d": {
                "user": {"name": "tri"},
                "database": {"id": 12345, "alias": "TPP", "host": "https://public.accurate.id"},
            },
        },
    )
    w = _make_wrapper()
    info = w.token_info()
    assert info["d"]["user"]["name"] == "tri"


def test_401_translates_to_auth_error(httpx_mock: HTTPXMock) -> None:
    # AccurateClient.token_info() uses POST to the token discovery endpoint.
    httpx_mock.add_response(
        method="POST",
        url="https://account.accurate.id/api/api-token.do",
        status_code=401,
        text="invalid signature",
    )
    w = _make_wrapper()
    with pytest.raises(AuthenticationError):
        w.token_info()


def test_connection_error(httpx_mock: HTTPXMock) -> None:
    import httpx

    # token_info() uses POST; add reusable exception to cover the SDK's
    # rate-limit-retry wrapper (which may attempt more than once).
    httpx_mock.add_exception(
        httpx.ConnectError("dns fail"),
        url="https://account.accurate.id/api/api-token.do",
        is_reusable=True,
    )
    w = _make_wrapper()
    with pytest.raises(KctlConnectionError):
        w.token_info()
