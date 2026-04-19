"""Tests for backups_flow shared helpers (the commands were removed in the Dokploy-native redesign)."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_dokploy.commands import backups_flow as bf
from kctl_dokploy.core.callbacks import AppContext

runner = CliRunner()


SAMPLE_COMPOSE = {
    "composeId": "comp-xyz",
    "name": "tpp-infra-postgres",
    "appName": "compose-sample-app",
    "serverId": "srv-1",
    "env": "POSTGRES_USER=postgres\nPOSTGRES_PASSWORD=secret123\nPOSTGRES_DB=mydb\n",
}


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


# ---------------------------------------------------------------------------
# Helper-level unit tests
# ---------------------------------------------------------------------------


class TestParseEnvStr:
    def test_empty(self) -> None:
        assert bf._parse_env_str("") == {}

    def test_basic(self) -> None:
        env = "A=1\nB=2\n"
        assert bf._parse_env_str(env) == {"A": "1", "B": "2"}

    def test_strips_surrounding_quotes(self) -> None:
        env = "PW=\"secret\"\nUSER='bob'\n"
        assert bf._parse_env_str(env) == {"PW": "secret", "USER": "bob"}

    def test_ignores_comments(self) -> None:
        env = "# header\nA=1\n  # indented\nB=2"
        assert bf._parse_env_str(env) == {"A": "1", "B": "2"}

    def test_ignores_lines_without_equals(self) -> None:
        env = "A=1\nnoequals\nB=2"
        assert bf._parse_env_str(env) == {"A": "1", "B": "2"}
