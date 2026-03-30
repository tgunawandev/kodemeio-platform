"""Shared test fixtures for kctl-cloudflare tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kctl_cloudflare.core.output import Output


@pytest.fixture
def mock_client() -> MagicMock:
    """A mocked CloudflareClient that returns predictable data.

    Stubs the most common methods so command-level tests can run without
    a live Cloudflare API.
    """
    client = MagicMock()
    client.account_id = "test_account_id"
    client.check_health.return_value = {"status": "active"}
    client.get.return_value = []
    client.post.return_value = {}
    client.put.return_value = {}
    client.patch.return_value = {}
    client.delete.return_value = {}
    client.get_zone_id.return_value = "zone_id_123"
    return client


def _make_actx(
    *,
    json_mode: bool = False,
    quiet: bool = False,
    format: str = "pretty",
    no_header: bool = False,
    client: MagicMock | None = None,
    profile: str | None = None,
) -> MagicMock:
    """Create a mock AppContext for command-level tests."""
    actx = MagicMock()
    actx.json_mode = json_mode
    actx.quiet = quiet
    actx.format = format
    actx.no_header = no_header
    actx.output = Output(json_mode=json_mode, quiet=quiet, format=format, no_header=no_header)
    actx.client = client or MagicMock()
    actx.profile = profile
    actx.api_token_override = None
    actx.account_id_override = None
    return actx


def _make_ctx(actx: MagicMock) -> MagicMock:
    """Create a mock typer.Context wrapping an AppContext."""
    ctx = MagicMock()
    ctx.obj = actx
    return ctx
