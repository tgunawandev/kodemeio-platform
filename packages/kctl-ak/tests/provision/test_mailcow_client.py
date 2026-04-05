"""Tests for lightweight Mailcow client."""

from __future__ import annotations

import pytest
import httpx

from kctl_ak.provision.mailcow_client import MailcowProvisionClient


@pytest.fixture
def mock_transport() -> httpx.MockTransport:
    """Mock transport that returns success for all Mailcow API calls."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/api/v1/get/mailbox/" in url:
            return httpx.Response(200, json=[])
        if "/api/v1/add/mailbox" in url:
            return httpx.Response(200, json=[{"type": "success", "msg": "Mailbox created"}])
        if "/api/v1/edit/mailbox" in url:
            return httpx.Response(200, json=[{"type": "success", "msg": "Mailbox updated"}])
        return httpx.Response(404)

    return httpx.MockTransport(handler)


@pytest.fixture
def client(mock_transport: httpx.MockTransport) -> MailcowProvisionClient:
    return MailcowProvisionClient(
        api_url="https://mail.kodeme.io",
        api_key="test-key",
        _transport=mock_transport,
    )


def test_mailbox_exists_false(client: MailcowProvisionClient) -> None:
    assert client.mailbox_exists("john@mandiriagro.com") is False


def test_create_mailbox(client: MailcowProvisionClient) -> None:
    result = client.create_mailbox(
        email="john@mandiriagro.com",
        name="John Doe",
        quota=1073741824,
    )
    assert result is True


def test_disable_mailbox(client: MailcowProvisionClient) -> None:
    result = client.disable_mailbox("john@mandiriagro.com")
    assert result is True


def test_enable_mailbox(client: MailcowProvisionClient) -> None:
    result = client.enable_mailbox("john@mandiriagro.com")
    assert result is True


def test_mailbox_exists_true(mock_transport: httpx.MockTransport) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "/api/v1/get/mailbox/" in str(request.url):
            return httpx.Response(200, json=[{"username": "john@mandiriagro.com", "active": "1"}])
        return httpx.Response(404)

    client = MailcowProvisionClient(
        api_url="https://mail.kodeme.io",
        api_key="test-key",
        _transport=httpx.MockTransport(handler),
    )
    assert client.mailbox_exists("john@mandiriagro.com") is True
