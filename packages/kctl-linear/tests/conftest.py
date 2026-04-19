"""Shared test configuration and fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from kctl_lib.output import Output
from typer.testing import CliRunner

from kctl_linear.core.callbacks import AppContext
from kctl_linear.core.client import LinearClient


@pytest.fixture
def mock_client() -> MagicMock:
    """Return a mock LinearClient."""
    client = MagicMock(spec=LinearClient)
    client.viewer.return_value = {
        "id": "user-123",
        "name": "Test User",
        "email": "test@kodeme.io",
        "admin": False,
        "active": True,
    }
    return client


@pytest.fixture
def mock_query(mock_client: MagicMock):
    """Convenience fixture to set up query return values."""

    def _set_query_response(response: dict[str, Any]) -> MagicMock:
        mock_client.query.return_value = response
        return mock_client

    return _set_query_response


SAMPLE_ISSUE = {
    "id": "issue-1",
    "identifier": "KOD-1",
    "title": "Test issue",
    "priority": 2,
    "state": {"name": "In Progress", "color": "#f00"},
    "assignee": {"name": "Test User", "email": "test@kodeme.io"},
    "createdAt": "2026-03-01T00:00:00Z",
    "updatedAt": "2026-03-28T00:00:00Z",
}

SAMPLE_CYCLE = {
    "id": "cycle-1",
    "number": 5,
    "name": "Sprint 5",
    "startsAt": "2026-03-25T00:00:00Z",
    "endsAt": "2026-04-07T00:00:00Z",
    "progress": 0.6,
    "issues": {"nodes": [SAMPLE_ISSUE]},
}


@pytest.fixture
def runner() -> CliRunner:
    """Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_graphql_client() -> MagicMock:
    """Mock LinearClient with a controllable query() method."""
    client = MagicMock(spec=LinearClient)
    client.query.return_value = {}
    client.viewer.return_value = {
        "id": "user-123",
        "name": "Test User",
        "email": "test@kodeme.io",
        "admin": False,
        "active": True,
    }
    return client


@pytest.fixture(autouse=True)
def _set_test_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Set KCTL_LINEAR_PROFILE and seed a minimal config for every test.

    Stage B of kctl-lib removed the silent default_profile fallback.  Any
    CliRunner invocation that does not pass ``--profile`` will now raise
    ValueError unless the env var is set.  This fixture ensures the env var
    always resolves to a real profile so tests focus on command behaviour.
    """
    config_dir = tmp_path / "kctl-test-config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.yaml"
    config_file.write_text("profiles:\n  test:\n    linear:\n      api_key: test-api-key\n      default_team: KOD\n")
    monkeypatch.setenv("KCTL_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("KCTL_LINEAR_PROFILE", "test")


@pytest.fixture
def mock_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect config loading to a temporary directory.

    Note: _set_test_profile (autouse) already sets KCTL_CONFIG_DIR and
    KCTL_LINEAR_PROFILE for every test.  This fixture is kept for tests that
    need to write their own profile data and returns the path to the config
    file inside the autouse-created directory so callers can extend it.
    """
    config_dir = tmp_path / "kctl-test-config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.yaml"
    # Ensure KCTL_CONFIG_DIR points here (autouse fixture already does this,
    # but be explicit in case fixture ordering varies).
    monkeypatch.setenv("KCTL_CONFIG_DIR", str(config_dir))
    return config_file


@pytest.fixture
def mock_output() -> Output:
    """Output instance with quiet mode for testing."""
    return Output(json_mode=False, quiet=True, format="pretty")


@pytest.fixture
def mock_context(mock_client: MagicMock, mock_output: Output) -> AppContext:
    """AppContext with mocked LinearClient and output."""
    ctx = AppContext(quiet=True)
    ctx._client = mock_client
    ctx._output = mock_output
    return ctx
