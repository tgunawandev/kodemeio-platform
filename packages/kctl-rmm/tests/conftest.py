"""Shared test fixtures for kctl-rmm."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from kctl_lib.output import Output
from typer.testing import CliRunner

from kctl_rmm.cli import app
from kctl_rmm.core.callbacks import AppContext
from kctl_rmm.core.client import RMMClient


@pytest.fixture
def runner() -> CliRunner:
    """Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    """Mock RMMClient spec'd to the real class."""
    client = MagicMock(spec=RMMClient)
    return client


@pytest.fixture
def mock_output() -> Output:
    """Output instance with quiet mode for testing."""
    return Output(json_mode=False, quiet=True, format="pretty")


@pytest.fixture
def mock_context(mock_client: MagicMock, mock_output: Output) -> AppContext:
    """AppContext with mocked client and output."""
    ctx = AppContext(quiet=True)
    ctx._client = mock_client
    ctx._output = mock_output
    return ctx


@pytest.fixture
def mock_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect config loading to a temporary directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    monkeypatch.setenv("KCTL_CONFIG_DIR", str(config_dir))
    return config_file


@pytest.fixture
def cli_app():
    """Return the Typer app for testing."""
    return app
