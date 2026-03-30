"""Shared test fixtures for kctl-api."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from kctl_api.cli import app


@pytest.fixture
def runner() -> CliRunner:
    """Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def cli_app():
    """The main kctl-api Typer application."""
    return app
