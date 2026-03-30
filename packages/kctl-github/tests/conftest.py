"""Shared test configuration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_github.cli import app
from kctl_github.core.callbacks import AppContext


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def cli_app():
    return app


@pytest.fixture
def mock_client():
    """Mock GitHubClient for command tests."""
    client = MagicMock()
    client.organization = "tgunawandev"
    client.repo_prefix = "kodemeio-"
    return client


@pytest.fixture
def mock_context(mock_client):
    """Patch AppContext.client to return mock_client."""
    with patch.object(AppContext, "client", new_callable=lambda: property(lambda self: mock_client)):
        yield mock_client
