"""Shared test fixtures for kctl-cf tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_cf.core.callbacks import AppContext
from kctl_cf.core.client import CloudflareClient
from kctl_cf.core.output import Output


@pytest.fixture
def runner() -> CliRunner:
    """Typer CLI test runner."""
    return CliRunner()


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


@pytest.fixture
def mock_config(tmp_path: Path):
    """Redirect kctl-lib config to a temp directory."""
    config_dir = tmp_path / "kodemeio"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.yaml"
    config_file.write_text("default_profile: default\nprofiles: {}\n")
    with patch("kctl_lib.config.CONFIG_FILE", config_file):
        yield config_file


@pytest.fixture
def mock_output() -> Output:
    """Output instance in quiet/JSON mode for test assertions."""
    return Output(json_mode=True, quiet=True, format="json")


@pytest.fixture
def mock_context(mock_client: MagicMock, mock_output: Output) -> AppContext:
    """AppContext with mocked client and output."""
    ctx = AppContext(quiet=True)
    ctx._client = mock_client
    ctx._output = mock_output
    return ctx
