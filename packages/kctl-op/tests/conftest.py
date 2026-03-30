"""Test fixtures for kctl-op."""

import pytest
from pathlib import Path
from collections import OrderedDict


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
    return OrderedDict([
        ("DB_HOST", "localhost"),
        ("DB_PORT", "5432"),
        ("DB_NAME", "mydb"),
        ("DB_PASSWORD", "super_secret_123"),
        ("API_KEY", "abc123def456"),
        ("EXPORTED_VAR", "exported_value"),
        ("EMPTY_VAR", ""),
    ])
