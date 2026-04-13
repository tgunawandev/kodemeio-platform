from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from kctl_mm.core.callbacks import AppContext


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    return MagicMock(name="MattermostClient")


@pytest.fixture
def mock_mm_exec() -> MagicMock:
    return MagicMock(name="MMExec")


@pytest.fixture
def mock_output() -> MagicMock:
    return MagicMock(name="Output")


@pytest.fixture
def mock_context(mock_client, mock_mm_exec, mock_output) -> AppContext:
    ctx = AppContext(profile="default", format="json", quiet=True, no_header=False)
    ctx._client = mock_client
    ctx._mm_exec = mock_mm_exec
    ctx._output = mock_output
    ctx._settings = {
        "url": "https://mm.idtpp.com",
        "token": "t",
        "ssh_host": "mm.example.com",
        "ssh_user": "root",
        "compose_path": "/opt/mm/docker-compose.yml",
    }
    return ctx
