"""Shared test fixtures for kctl-waha."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from kctl_lib.output import Output
from kctl_waha.cli import app
from kctl_waha.core.callbacks import AppContext
from kctl_waha.core.client import BridgeClient, WahaClient


@pytest.fixture
def runner() -> CliRunner:
    """Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    """Mock WahaClient."""
    client = MagicMock(spec=WahaClient)
    client.base_url = "https://waha.kodeme.io"
    return client


@pytest.fixture
def mock_bridge_client() -> MagicMock:
    """Mock BridgeClient."""
    bridge = MagicMock(spec=BridgeClient)
    bridge.base_url = "http://localhost:3000"
    return bridge


@pytest.fixture
def mock_output() -> Output:
    """Output instance for testing."""
    return Output(json_mode=False, quiet=True, format="pretty")


@pytest.fixture
def mock_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect config to tmp_path."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    monkeypatch.setattr("kctl_waha.core.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("kctl_waha.core.config.CONFIG_FILE", config_file)
    return config_file


@pytest.fixture
def mock_context(mock_client: MagicMock, mock_bridge_client: MagicMock, mock_output: Output) -> AppContext:
    """AppContext with mocked client and bridge."""
    ctx = AppContext(quiet=True)
    ctx._client = mock_client
    ctx._bridge = mock_bridge_client
    ctx._output = mock_output
    return ctx


@pytest.fixture
def cli_app():
    """Return the Typer app for testing."""
    return app
