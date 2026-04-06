"""Shared test fixtures for kctl-zulip."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_zulip.cli import app
from kctl_zulip.core.callbacks import AppContext
from kctl_zulip.core.client import ZulipClient
from kctl_zulip.core.output import Output


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    return MagicMock(spec=ZulipClient)


@pytest.fixture
def mock_output() -> Output:
    return Output(json_mode=False, quiet=True, format="pretty")


@pytest.fixture
def mock_context(mock_client: MagicMock, mock_output: Output) -> AppContext:
    ctx = AppContext(quiet=True)
    ctx._client = mock_client
    ctx._output = mock_output
    return ctx


@pytest.fixture
def cli_app():
    return app


@pytest.fixture
def mock_config(tmp_path: Path):
    config_dir = tmp_path / "kodemeio"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.yaml"
    config_file.write_text(
        "default_profile: default\nprofiles:\n  default:\n    zulip:\n      url: https://zulip.test.io\n      email: bot@test.io\n      api_key: test-key-1234\n"
    )
    with (
        patch("kctl_zulip.core.config.CONFIG_FILE", config_file),
        patch("kctl_zulip.core.config.CONFIG_DIR", config_dir),
    ):
        yield config_file
