"""Shared test fixtures for kctl-odoo tests."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from kctl_lib.output import Output
from typer.testing import CliRunner

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.client import OdooClient


@pytest.fixture
def install_dir() -> Path:
    """Path to the real install/ bundle directory in the Odoo project root.

    Resolution order:
    1. ``KCTL_ODOO_REPO`` env var → ``{repo}/install``
    2. Walk up from this file looking for ``install/`` directory
    3. Skip if not found
    """
    # 1. Env var
    repo = os.environ.get("KCTL_ODOO_REPO")
    if repo:
        path = Path(repo) / "install"
        if path.is_dir():
            return path

    # 2. Walk up from test file (works when CLI is co-located with repo)
    cur = Path(__file__).resolve().parent
    for _ in range(10):
        candidate = cur / "install"
        if candidate.is_dir():
            return candidate
        parent = cur.parent
        if parent == cur:
            break
        cur = parent

    pytest.skip("install/ directory not found -- set KCTL_ODOO_REPO env var")
    return Path()  # unreachable, satisfies type checker


@pytest.fixture
def repo_root() -> Path:
    """Path to the Odoo repository root (has both install/ and src/).

    Resolution order:
    1. ``KCTL_ODOO_REPO`` env var
    2. Walk up from this file looking for dir with install/ and src/
    3. Skip if not found
    """
    # 1. Env var
    repo = os.environ.get("KCTL_ODOO_REPO")
    if repo:
        path = Path(repo)
        if path.is_dir():
            return path

    # 2. Walk up from test file
    cur = Path(__file__).resolve().parent
    for _ in range(10):
        if (cur / "install").is_dir() and (cur / "src").is_dir():
            return cur
        parent = cur.parent
        if parent == cur:
            break
        cur = parent

    pytest.skip("repo root (install/ + src/) not found -- set KCTL_ODOO_REPO env var")
    return Path()  # unreachable


@pytest.fixture
def mock_client() -> MagicMock:
    """A mocked OdooClient that returns predictable data.

    Stubs the most common methods so command-level tests can run without
    a live Odoo instance.
    """
    client = MagicMock(spec=OdooClient)
    client.database = "test_db"
    client.uid = 2
    client.authenticate.return_value = 2
    client.version_info.return_value = {"server_version": "18.0"}
    client.check_health.return_value = (True, "18.0")
    client.search_read.return_value = []
    client.search_count.return_value = 0
    client.search.return_value = []
    client.db_list.return_value = ["db1", "db2"]
    return client


@pytest.fixture
def runner() -> CliRunner:
    """Typer CLI test runner."""
    return CliRunner()


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
    """AppContext with mocked OdooClient and output."""
    ctx = AppContext(quiet=True)
    ctx._client = mock_client
    ctx._output = mock_output
    return ctx
