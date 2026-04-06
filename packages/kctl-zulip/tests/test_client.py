"""Test ZulipClient class directly."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from kctl_lib.exceptions import AuthenticationError
from kctl_lib.exceptions import ConnectionError as KctlConnectionError
from kctl_zulip.core.client import ZulipAPIError, ZulipClient


def test_init_requires_url():
    with pytest.raises(KctlConnectionError):
        ZulipClient(base_url="", email="bot@test.io", api_key="key123")


def test_init_requires_email():
    with pytest.raises(AuthenticationError):
        ZulipClient(base_url="https://zulip.test.io", email="", api_key="key123")


def test_init_requires_api_key():
    with pytest.raises(AuthenticationError):
        ZulipClient(base_url="https://zulip.test.io", email="bot@test.io", api_key="")


def test_error_envelope_result_error():
    """200 response with result=error should raise ZulipAPIError."""
    client = ZulipClient(base_url="https://zulip.test.io", email="bot@test.io", api_key="key123")
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.content = b'{"result": "error", "msg": "Bad request"}'
    resp.json.return_value = {"result": "error", "msg": "Bad request"}
    resp.text = '{"result": "error", "msg": "Bad request"}'

    with pytest.raises(ZulipAPIError):
        client._check_response(resp)
    client.close()


def test_401_auth_error():
    """401 should raise AuthenticationError."""
    client = ZulipClient(base_url="https://zulip.test.io", email="bot@test.io", api_key="key123")
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 401
    resp.content = b""

    with pytest.raises(AuthenticationError):
        client._check_response(resp)
    client.close()


def test_success_response():
    """200 with result=success should not raise."""
    client = ZulipClient(base_url="https://zulip.test.io", email="bot@test.io", api_key="key123")
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.content = b'{"result": "success"}'
    resp.json.return_value = {"result": "success"}

    # Should not raise
    client._check_response(resp)
    client.close()
