"""Tests for commands/api_cmd.py — API command tests with httpx mocking."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
from typer.testing import CliRunner

from kctl_claude.cli import app

runner = CliRunner()


class TestApiHealth:
    def test_health_success(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "ok", "inFlight": 1, "maxConcurrent": 3}
        mock_resp.status_code = 200
        with patch("kctl_claude.commands.api_cmd.httpx.get", return_value=mock_resp):
            result = runner.invoke(app, ["api", "health"])
        assert result.exit_code == 0

    def test_health_json_mode(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "ok"}
        mock_resp.status_code = 200
        with patch("kctl_claude.commands.api_cmd.httpx.get", return_value=mock_resp):
            result = runner.invoke(app, ["--json", "api", "health"])
        assert result.exit_code == 0
        assert "status" in result.output

    def test_health_unreachable(self) -> None:
        with patch(
            "kctl_claude.commands.api_cmd.httpx.get",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = runner.invoke(app, ["api", "health"])
        assert result.exit_code == 1

    def test_health_timeout(self) -> None:
        with patch(
            "kctl_claude.commands.api_cmd.httpx.get",
            side_effect=httpx.TimeoutException("Timed out"),
        ):
            result = runner.invoke(app, ["api", "health"])
        assert result.exit_code == 1

    def test_health_non_json_response(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.side_effect = ValueError("Not JSON")
        mock_resp.status_code = 200
        with patch("kctl_claude.commands.api_cmd.httpx.get", return_value=mock_resp):
            result = runner.invoke(app, ["api", "health"])
        assert result.exit_code == 0


class TestApiTask:
    def test_task_success(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": "done"}
        mock_resp.status_code = 200
        with patch("kctl_claude.commands.api_cmd.httpx.post", return_value=mock_resp):
            result = runner.invoke(app, ["api", "task", "hello"])
        assert result.exit_code == 0

    def test_task_error_response(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"error": "bad request"}
        mock_resp.status_code = 400
        with patch("kctl_claude.commands.api_cmd.httpx.post", return_value=mock_resp):
            result = runner.invoke(app, ["api", "task", "hello"])
        assert result.exit_code == 1

    def test_task_timeout(self) -> None:
        with patch(
            "kctl_claude.commands.api_cmd.httpx.post",
            side_effect=httpx.TimeoutException("Timed out"),
        ):
            result = runner.invoke(app, ["api", "task", "hello"])
        assert result.exit_code == 1

    def test_task_invalid_workspace(self) -> None:
        result = runner.invoke(app, ["api", "task", "hello", "--workspace", "../etc/passwd"])
        assert result.exit_code == 1

    def test_task_absolute_workspace(self) -> None:
        result = runner.invoke(app, ["api", "task", "hello", "--workspace", "/etc/passwd"])
        assert result.exit_code == 1

    def test_task_valid_workspace(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": "ok"}
        mock_resp.status_code = 200
        with patch("kctl_claude.commands.api_cmd.httpx.post", return_value=mock_resp):
            result = runner.invoke(app, ["api", "task", "hello", "-w", "myproject"])
        assert result.exit_code == 0

    def test_task_non_json_response(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.side_effect = ValueError("Not JSON")
        mock_resp.status_code = 200
        with patch("kctl_claude.commands.api_cmd.httpx.post", return_value=mock_resp):
            result = runner.invoke(app, ["api", "task", "hello"])
        assert result.exit_code == 0

    def test_task_json_mode(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": "done"}
        mock_resp.status_code = 200
        with patch("kctl_claude.commands.api_cmd.httpx.post", return_value=mock_resp):
            result = runner.invoke(app, ["--json", "api", "task", "hello"])
        assert result.exit_code == 0
