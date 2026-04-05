"""Shared fixtures for kctl-pg CLI tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from kctl_lib.output import Output
from typer.testing import CliRunner

from kctl_pg.core.callbacks import AppContext
from kctl_pg.core.client import PostgresClient


class FakeClient:
    """Mock PostgresClient that returns pre-configured query results."""

    def __init__(self, results: dict[str, Any] | None = None):
        self._results = results or {}
        self._call_index: dict[str, int] = {}
        self.closed = False

    def add_result(self, key: str, value: Any) -> None:
        self._results[key] = value

    def fetchall(self, sql: str, params: tuple | dict | None = None) -> list[dict]:
        return self._get_result(sql)

    def fetchone(self, sql: str, params: tuple | dict | None = None) -> dict | None:
        result = self._get_result(sql)
        if isinstance(result, list):
            return result[0] if result else None
        return result

    def fetchval(self, sql: str, params: tuple | dict | None = None) -> Any:
        result = self._get_result(sql)
        if isinstance(result, list) and result:
            return next(iter(result[0].values()))
        if isinstance(result, dict):
            return next(iter(result.values()))
        return result

    def execute(self, sql: str, params: tuple | dict | None = None) -> None:
        pass

    def close(self) -> None:
        self.closed = True

    def _get_result(self, sql: str) -> Any:
        # Match by substring in the query
        for key, value in self._results.items():
            if key.lower() in sql.lower():
                return value
        return []


@pytest.fixture
def fake_client() -> FakeClient:
    return FakeClient()


@pytest.fixture
def output() -> Output:
    return Output(json_mode=False, quiet=True)


@pytest.fixture
def json_output() -> Output:
    return Output(json_mode=True, quiet=False)


# ---------------------------------------------------------------------------
# Standard fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runner() -> CliRunner:
    """Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    """Mock PostgresClient spec'd to the real class."""
    return MagicMock(spec=PostgresClient)


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
    """AppContext with mocked PostgresClient and output."""
    ctx = AppContext(quiet=True)
    ctx._client = mock_client
    ctx._output = mock_output
    return ctx


@pytest.fixture
def mock_ssh_run(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock kctl_lib.ssh.ssh_run."""
    from kctl_lib.ssh import SSHResult

    mock = MagicMock()
    mock.return_value = SSHResult(stdout="", stderr="", returncode=0)
    monkeypatch.setattr("kctl_lib.ssh.ssh_run", mock)
    return mock


@pytest.fixture
def mock_ssh_tunnel(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock kctl_lib.ssh_tunnel.SSHTunnel as a context manager."""
    mock_tunnel = MagicMock()
    mock_tunnel.__enter__ = MagicMock(return_value=mock_tunnel)
    mock_tunnel.__exit__ = MagicMock(return_value=False)
    mock_tunnel.local_bind_port = 15432

    mock_cls = MagicMock(return_value=mock_tunnel)
    monkeypatch.setattr("kctl_lib.ssh_tunnel.SSHTunnel", mock_cls)
    return mock_cls
