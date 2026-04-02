"""Shared test fixtures for kctl-rustdesk."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from kctl_lib.output import Output
from kctl_rustdesk.cli import app
from kctl_rustdesk.core.callbacks import AppContext
from kctl_rustdesk.core.executor import RustDeskExecutor


@pytest.fixture
def runner() -> CliRunner:
    """Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_executor() -> MagicMock:
    """Mock RustDeskExecutor with sensible defaults."""
    executor = MagicMock(spec=RustDeskExecutor)
    executor.is_remote = False
    executor.hbbs_container = "kodemeio-rustdesk-hbbs-1"
    executor.hbbr_container = "kodemeio-rustdesk-hbbr-1"
    executor.DB_PATH = "/root/db_v2.sqlite3"
    executor.KEY_PUB_PATH = "/root/id_ed25519.pub"
    executor.KEY_PRIV_PATH = "/root/id_ed25519"
    return executor


@pytest.fixture
def mock_output() -> Output:
    """Output instance with quiet mode for testing."""
    return Output(json_mode=False, quiet=True, format="pretty")


@pytest.fixture
def mock_context(mock_executor: MagicMock, mock_output: Output) -> AppContext:
    """AppContext with mocked executor and output."""
    ctx = AppContext(quiet=True)
    ctx._executor = mock_executor
    ctx._output = mock_output
    return ctx


@pytest.fixture
def cli_app():
    """Return the Typer app for testing."""
    return app
