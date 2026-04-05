"""Tests for health check command."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from kctl_mailcow.cli import app
from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.exceptions import KctlError


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    from kctl_mailcow.core.client import MailcowClient

    client = MagicMock(spec=MailcowClient)
    client.base_url = "https://mail.kodeme.io"
    return client


@pytest.fixture
def mock_ctx(mock_client: MagicMock) -> AppContext:
    from kctl_lib.output import Output

    ctx = AppContext(quiet=True)
    ctx._client = mock_client
    ctx._output = Output(json_mode=False, quiet=True, format="pretty")
    return ctx


CONTAINERS_ALL_RUNNING = {
    "postfix": {"state": "running"},
    "dovecot": {"state": "running"},
    "rspamd": {"state": "running"},
    "clamd": {"state": "running"},
    "nginx": {"state": "running"},
}

CONTAINERS_SOME_DOWN = {
    "postfix": {"state": "running"},
    "dovecot": {"state": "running"},
    "rspamd": {"state": "exited"},
    "clamd": {"state": "exited"},
    "nginx": {"state": "running"},
}

CONTAINERS_STRING_FORMAT = {
    "postfix": "running",
    "dovecot": "running",
    "nginx": "running",
}


class TestHealthApiConnectivity:
    def test_api_up_full_score(self, runner: CliRunner, mock_ctx: AppContext, mock_client: MagicMock) -> None:
        mock_client.check_health.return_value = (True, "Mailcow 1.0")
        mock_client.mc_get.return_value = CONTAINERS_ALL_RUNNING
        result = runner.invoke(app, ["health"], obj=mock_ctx)
        assert result.exit_code == 0

    def test_api_down_check_health_raises(
        self, runner: CliRunner, mock_ctx: AppContext, mock_client: MagicMock
    ) -> None:
        mock_client.check_health.side_effect = KctlError("Connection refused")
        mock_client.mc_get.return_value = {}
        result = runner.invoke(app, ["health"], obj=mock_ctx)
        # Score < 50 since API is down and no containers
        assert result.exit_code == 1

    def test_api_down_returns_false(self, runner: CliRunner, mock_ctx: AppContext, mock_client: MagicMock) -> None:
        mock_client.check_health.return_value = (False, "Connection refused")
        mock_client.mc_get.return_value = {}
        result = runner.invoke(app, ["health"], obj=mock_ctx)
        assert result.exit_code == 1

    def test_api_up_no_containers_partial_score(
        self, runner: CliRunner, mock_ctx: AppContext, mock_client: MagicMock
    ) -> None:
        mock_client.check_health.return_value = (True, "Mailcow 1.0")
        mock_client.mc_get.return_value = {}
        result = runner.invoke(app, ["health"], obj=mock_ctx)
        # API is up (50 pts) but no containers (0 pts) => score=50, still passes
        assert result.exit_code == 0


class TestHealthContainers:
    def test_all_containers_running(self, runner: CliRunner, mock_ctx: AppContext, mock_client: MagicMock) -> None:
        mock_client.check_health.return_value = (True, "Mailcow 1.0")
        mock_client.mc_get.return_value = CONTAINERS_ALL_RUNNING
        result = runner.invoke(app, ["health"], obj=mock_ctx)
        assert result.exit_code == 0

    def test_containers_string_format(self, runner: CliRunner, mock_ctx: AppContext, mock_client: MagicMock) -> None:
        mock_client.check_health.return_value = (True, "Mailcow 1.0")
        mock_client.mc_get.return_value = CONTAINERS_STRING_FORMAT
        result = runner.invoke(app, ["health"], obj=mock_ctx)
        assert result.exit_code == 0

    def test_some_containers_down_still_passes_with_api(
        self, runner: CliRunner, mock_ctx: AppContext, mock_client: MagicMock
    ) -> None:
        mock_client.check_health.return_value = (True, "Mailcow 1.0")
        mock_client.mc_get.return_value = CONTAINERS_SOME_DOWN
        result = runner.invoke(app, ["health"], obj=mock_ctx)
        # API(50) + 3/5 containers running = 50 + 30 = 80 => passes
        assert result.exit_code == 0

    def test_containers_fetch_raises_does_not_crash(
        self, runner: CliRunner, mock_ctx: AppContext, mock_client: MagicMock
    ) -> None:
        mock_client.check_health.return_value = (True, "Mailcow 1.0")
        mock_client.mc_get.side_effect = Exception("Network error")
        result = runner.invoke(app, ["health"], obj=mock_ctx)
        # API up = 50 pts, no container info => score=50, still passes
        assert result.exit_code == 0

    def test_containers_not_dict_response(
        self, runner: CliRunner, mock_ctx: AppContext, mock_client: MagicMock
    ) -> None:
        mock_client.check_health.return_value = (True, "Mailcow 1.0")
        mock_client.mc_get.return_value = ["container1", "container2"]
        result = runner.invoke(app, ["health"], obj=mock_ctx)
        # Non-dict container response => containers=None, score=50
        assert result.exit_code == 0


class TestHealthScoring:
    def test_score_100_all_up(self, runner: CliRunner, mock_ctx: AppContext, mock_client: MagicMock) -> None:
        mock_client.check_health.return_value = (True, "ok")
        mock_client.mc_get.return_value = CONTAINERS_ALL_RUNNING
        result = runner.invoke(app, ["health"], obj=mock_ctx)
        assert result.exit_code == 0
        assert "100" in result.output

    def test_score_50_api_only(self, runner: CliRunner, mock_ctx: AppContext, mock_client: MagicMock) -> None:
        mock_client.check_health.return_value = (True, "ok")
        mock_client.mc_get.return_value = {}
        result = runner.invoke(app, ["health"], obj=mock_ctx)
        assert result.exit_code == 0
        assert "50" in result.output

    def test_score_0_everything_down(self, runner: CliRunner, mock_ctx: AppContext, mock_client: MagicMock) -> None:
        mock_client.check_health.side_effect = KctlError("Down")
        mock_client.mc_get.side_effect = Exception("Down")
        result = runner.invoke(app, ["health"], obj=mock_ctx)
        assert result.exit_code == 1
        assert "0" in result.output

    def test_exit_code_1_when_score_below_50(
        self, runner: CliRunner, mock_ctx: AppContext, mock_client: MagicMock
    ) -> None:
        mock_client.check_health.return_value = (False, "down")
        mock_client.mc_get.return_value = {"nginx": {"state": "exited"}}
        result = runner.invoke(app, ["health"], obj=mock_ctx)
        assert result.exit_code == 1

    def test_exit_code_0_when_score_exactly_50(
        self, runner: CliRunner, mock_ctx: AppContext, mock_client: MagicMock
    ) -> None:
        mock_client.check_health.return_value = (True, "ok")
        mock_client.mc_get.return_value = {}
        result = runner.invoke(app, ["health"], obj=mock_ctx)
        assert result.exit_code == 0


class TestHealthOutput:
    def test_output_contains_health_check(
        self, runner: CliRunner, mock_ctx: AppContext, mock_client: MagicMock
    ) -> None:
        mock_client.check_health.return_value = (True, "ok")
        mock_client.mc_get.return_value = CONTAINERS_ALL_RUNNING
        result = runner.invoke(app, ["health"], obj=mock_ctx)
        assert "Health" in result.output

    def test_output_contains_api_section(self, runner: CliRunner, mock_ctx: AppContext, mock_client: MagicMock) -> None:
        mock_client.check_health.return_value = (True, "ok")
        mock_client.mc_get.return_value = {}
        result = runner.invoke(app, ["health"], obj=mock_ctx)
        assert "API" in result.output

    def test_output_contains_containers_section(
        self, runner: CliRunner, mock_ctx: AppContext, mock_client: MagicMock
    ) -> None:
        mock_client.check_health.return_value = (True, "ok")
        mock_client.mc_get.return_value = CONTAINERS_ALL_RUNNING
        result = runner.invoke(app, ["health"], obj=mock_ctx)
        assert "postfix" in result.output or "Container" in result.output

    def test_json_output(self, runner: CliRunner, mock_ctx: AppContext, mock_client: MagicMock) -> None:
        from kctl_lib.output import Output

        mock_ctx._output = Output(json_mode=True, quiet=True, format="json")
        mock_client.check_health.return_value = (True, "ok")
        mock_client.mc_get.return_value = CONTAINERS_ALL_RUNNING
        result = runner.invoke(app, ["--json", "health"], obj=mock_ctx)
        assert result.exit_code == 0
