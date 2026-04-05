"""Test fixtures for kctl-op."""

from __future__ import annotations

from pathlib import Path
from collections import OrderedDict
from unittest.mock import MagicMock

import pytest
from kctl_lib.output import Output
from typer.testing import CliRunner

from kctl_op.core.callbacks import AppContext
from kctl_op.core.client import OnePasswordClient


@pytest.fixture
def tmp_env_file(tmp_path):
    """Create a temporary .env file."""

    def _create(content: str, filename: str = ".env.prod") -> Path:
        env_file = tmp_path / filename
        env_file.write_text(content)
        return env_file

    return _create


@pytest.fixture
def sample_env_content():
    return """# Database configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mydb
DB_PASSWORD="super_secret_123"

# API Keys
API_KEY=abc123def456
export EXPORTED_VAR=exported_value

# Empty value
EMPTY_VAR=
"""


@pytest.fixture
def sample_env_vars():
    return OrderedDict(
        [
            ("DB_HOST", "localhost"),
            ("DB_PORT", "5432"),
            ("DB_NAME", "mydb"),
            ("DB_PASSWORD", "super_secret_123"),
            ("API_KEY", "abc123def456"),
            ("EXPORTED_VAR", "exported_value"),
            ("EMPTY_VAR", ""),
        ]
    )


@pytest.fixture
def runner() -> CliRunner:
    """Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    """Mock OnePasswordClient spec'd to the real class."""
    return MagicMock(spec=OnePasswordClient)


@pytest.fixture
def mock_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect config loading to a temporary directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    monkeypatch.setenv("KCTL_CONFIG_DIR", str(config_dir))
    return config_file


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
