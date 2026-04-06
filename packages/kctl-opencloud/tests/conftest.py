"""Shared test fixtures for kctl-opencloud."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from kctl_opencloud.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def cli_app():
    return app
