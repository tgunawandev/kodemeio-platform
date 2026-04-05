"""Shared test fixtures for kctl-hz tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_hz.core.callbacks import AppContext
from kctl_hz.core.client import HetznerCloudClient
from kctl_lib.output import Output


@pytest.fixture
def runner() -> CliRunner:
    """Typer CLI test runner."""
    return CliRunner()


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
def mock_client(mock_cloud_client: MagicMock) -> MagicMock:
    """Standard mock_client alias — wraps mock_cloud_client (HetznerCloudClient)."""
    return mock_cloud_client


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
def mock_context(mock_cloud_client: MagicMock, mock_dns_client: MagicMock, mock_output: Output) -> AppContext:
    """AppContext with mocked cloud + DNS clients and output."""
    ctx = AppContext(quiet=True)
    ctx._client = mock_cloud_client
    ctx._dns_client = mock_dns_client
    ctx._output = mock_output
    return ctx
