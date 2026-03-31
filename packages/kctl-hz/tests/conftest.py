"""Shared test fixtures for kctl-hz tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from kctl_hz.core.callbacks import AppContext


@pytest.fixture
def mock_cloud_client() -> MagicMock:
    """A mocked HetznerCloudClient that returns predictable data.

    Stubs the most common methods so command-level tests can run without
    a live Hetzner API token.
    """
    client = MagicMock()
    client.get.return_value = {}
    client.post.return_value = {}
    client.put.return_value = {}
    client.delete.return_value = None
    client.get_all.return_value = []
    return client


@pytest.fixture
def mock_dns_client() -> MagicMock:
    """A mocked HetznerDnsClient."""
    client = MagicMock()
    client.get.return_value = {"zones": []}
    client.post.return_value = {}
    client.put.return_value = {}
    client.delete.return_value = None
    return client


@pytest.fixture
def make_actx(mock_cloud_client: MagicMock, mock_dns_client: MagicMock) -> Any:
    """Factory to create an AppContext with mocked clients.

    Usage:
        actx = make_actx(json_mode=True)
        actx = make_actx()  # defaults to pretty mode
    """

    def _make(
        json_mode: bool = False,
        quiet: bool = False,
        format: str = "pretty",
        no_header: bool = False,
    ) -> AppContext:
        actx = AppContext(json_mode=json_mode, quiet=quiet, format=format, no_header=no_header)
        actx._client = mock_cloud_client
        actx._dns_client = mock_dns_client
        return actx

    return _make
