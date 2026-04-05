"""Shared test fixtures for kctl-redis."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from kctl_lib.output import Output
from typer.testing import CliRunner

from kctl_redis.core.callbacks import AppContext
from kctl_redis.core.client import RedisClient


class FakeRedisClient:
    """Mock Redis client for testing commands without a real connection."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._info_data: dict[str, dict[str, Any]] = {}

    def set_info(self, section: str, data: dict[str, Any]) -> None:
        """Set fake INFO data for a section."""
        self._info_data[section] = data

    def info(self, section: str | None = None) -> dict[str, Any]:
        if section:
            return self._info_data.get(section, {})
        result: dict[str, Any] = {}
        for s in self._info_data.values():
            result.update(s)
        return result

    def execute(self, *args: str) -> Any:
        return "OK"

    def ping(self) -> bool:
        return True

    @property
    def r(self) -> MagicMock:
        return MagicMock()

    @property
    def server_version(self) -> str:
        return "7.2.0"

    def close(self) -> None:
        pass


@pytest.fixture
def fake_client() -> FakeRedisClient:
    return FakeRedisClient()


@pytest.fixture
def output() -> Output:
    return Output(json_mode=False, quiet=False)


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
    """Mock RedisClient spec'd to the real class."""
    return MagicMock(spec=RedisClient)


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
    """AppContext with mocked RedisClient and output."""
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
    mock_tunnel.local_bind_port = 16379

    mock_cls = MagicMock(return_value=mock_tunnel)
    monkeypatch.setattr("kctl_lib.ssh_tunnel.SSHTunnel", mock_cls)
    return mock_cls
