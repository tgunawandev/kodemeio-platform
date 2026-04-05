"""Shared test fixtures for kctl-grafana."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_grafana.cli import app
from kctl_grafana.core.callbacks import AppContext
from kctl_grafana.core.client import GrafanaClient
from kctl_grafana.core.output import Output


@pytest.fixture
def runner() -> CliRunner:
    """Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    """Mock GrafanaClient."""
    client = MagicMock(spec=GrafanaClient)
    client.org_id = 1
    client.root_url = "https://grafana.kodeme.io"
    return client


@pytest.fixture
def mock_output() -> Output:
    """Output instance for testing."""
    return Output(json_mode=False, quiet=True, format="pretty")


@pytest.fixture
def mock_context(mock_client: MagicMock, mock_output: Output) -> AppContext:
    """AppContext with mocked client."""
    ctx = AppContext(quiet=True)
    ctx._client = mock_client
    ctx._output = mock_output
    return ctx


@pytest.fixture
def cli_app():
    """Return the Typer app for testing."""
    return app


@pytest.fixture
def mock_config(tmp_path: Path):
    """Redirect kctl-lib config to a temp directory."""
    config_dir = tmp_path / "kodemeio"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.yaml"
    config_file.write_text("default_profile: default\nprofiles: {}\n")
    with patch("kctl_lib.config.CONFIG_FILE", config_file):
        yield config_file
