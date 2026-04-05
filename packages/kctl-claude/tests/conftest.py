"""Shared test fixtures for kctl-claude."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from kctl_claude.cli import app
from kctl_claude.core.callbacks import AppContext
from kctl_claude.core.output import Output


@pytest.fixture
def runner() -> CliRunner:
    """Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_output() -> Output:
    """Output instance for testing."""
    return Output(json_mode=False, quiet=True, format="pretty")


@pytest.fixture
def mock_subprocess(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock subprocess.run for testing CLI wrappers."""
    mock = MagicMock()
    mock.return_value.returncode = 0
    mock.return_value.stdout = ""
    mock.return_value.stderr = ""
    monkeypatch.setattr("subprocess.run", mock)
    return mock


@pytest.fixture
def mock_context(mock_output: Output) -> AppContext:
    """AppContext with mocked output."""
    ctx = AppContext(quiet=True)
    ctx._output = mock_output
    return ctx


@pytest.fixture
def cli_app():
    """Return the Typer app for testing."""
    return app
