"""Shared test configuration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_github.cli import app
from kctl_github.core.callbacks import AppContext
from kctl_github.core.client import GitHubClient
from kctl_lib.output import Output


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def cli_app():
    return app


@pytest.fixture
def mock_client() -> MagicMock:
    """Mock GitHubClient for command tests."""
    client = MagicMock(spec=GitHubClient)
    client.organization = "tgunawandev"
    client.repo_prefix = "kodemeio-"
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
