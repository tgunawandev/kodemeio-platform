"""Shared test fixtures for kctl-glitchtip."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from kctl_lib.output import Output
from typer.testing import CliRunner

from kctl_glitchtip.cli import app
from kctl_glitchtip.core.callbacks import AppContext
from kctl_glitchtip.core.client import GlitchTipClient


@pytest.fixture
def runner() -> CliRunner:
    """Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    """Mock GlitchTipClient."""
    client = MagicMock(spec=GlitchTipClient)
    client._original_base_url = "https://glitchtip.kodeme.io"
    return client


@pytest.fixture
def mock_output() -> Output:
    """Output instance for testing (quiet, no Rich rendering)."""
    return Output(json_mode=False, quiet=True, format="pretty")


@pytest.fixture
def mock_context(mock_client: MagicMock, mock_output: Output) -> AppContext:
    """AppContext with mocked client and output."""
    ctx = AppContext(quiet=True)
    ctx._client = mock_client
    ctx._output = mock_output
    return ctx


@pytest.fixture
def cli_app():
    """Return the Typer app for testing."""
    return app
