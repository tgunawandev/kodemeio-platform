"""Shared test fixtures for kctl-api."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_api.cli import app
from kctl_api.core.callbacks import AppContext
from kctl_api.core.client import ApiClient
from kctl_api.core.output import Output


@pytest.fixture
def runner() -> CliRunner:
    """Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def cli_app():
    """The main kctl-api Typer application."""
    return app


@pytest.fixture
def mock_client() -> MagicMock:
    """Mocked ApiClient with predictable responses."""
    client = MagicMock(spec=ApiClient)
    client._base_url = "https://api.kodeme.io"
    client.check_health.return_value = {"status": "ok"}
    client.get.return_value = []
    client.post.return_value = {}
    client.put.return_value = {}
    client.patch.return_value = {}
    client.delete.return_value = {}
    return client


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
