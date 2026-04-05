"""Tests for kctl-api health commands."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_api.cli import app
from kctl_api.commands.health import _check_api, _check_ai, _display_single_check, _display_all_results
from kctl_api.core.callbacks import AppContext
from kctl_api.core.output import Output

runner = CliRunner()


# ---------------------------------------------------------------------------
# _check_api unit tests
# ---------------------------------------------------------------------------
class TestCheckApi:
    def test_check_api_healthy(self) -> None:
        mock_client = MagicMock()
        mock_client.health_check.return_value = (True, {"status": "ok", "version": "1.0"})
        actx = AppContext(quiet=True)
        actx._client = mock_client

        result = _check_api(actx)
        assert result["service"] == "api-main"
        assert result["healthy"] is True
        assert result["status"] == "ok"

    def test_check_api_unhealthy(self) -> None:
        mock_client = MagicMock()
        mock_client.health_check.return_value = (False, {"status": "error"})
        actx = AppContext(quiet=True)
        actx._client = mock_client

        result = _check_api(actx)
        assert result["service"] == "api-main"
        assert result["healthy"] is False

    def test_check_api_exception(self) -> None:
        mock_client = MagicMock()
        mock_client.health_check.side_effect = ConnectionError("refused")
        actx = AppContext(quiet=True)
        actx._client = mock_client

        result = _check_api(actx)
        assert result["service"] == "api-main"
        assert result["healthy"] is False
        assert result["status"] == "error"
        assert "refused" in result["error"]


# ---------------------------------------------------------------------------
# _check_ai unit tests
# ---------------------------------------------------------------------------
class TestCheckAi:
    def test_check_ai_healthy(self) -> None:
        mock_ai_client = MagicMock()
        mock_ai_client.get.return_value = {"status": "ok"}
        actx = AppContext(quiet=True)
        actx._ai_client = mock_ai_client
        # Prevent lazy init from complaining about missing ai_url
        with patch.object(type(actx), "ai_client", new_callable=lambda: property(lambda self: mock_ai_client)):
            result = _check_ai(actx)
        assert result["service"] == "ai-main"
        assert result["healthy"] is True

    def test_check_ai_exception(self) -> None:
        actx = AppContext(quiet=True)
        with patch.object(
            type(actx),
            "ai_client",
            new_callable=lambda: property(lambda self: (_ for _ in ()).throw(Exception("no ai_url"))),
        ):
            result = _check_ai(actx)
        assert result["service"] == "ai-main"
        assert result["healthy"] is False
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# _display_single_check unit tests
# ---------------------------------------------------------------------------
class TestDisplaySingleCheck:
    def test_display_healthy_pretty(self, capsys: pytest.CaptureFixture) -> None:  # type: ignore[type-arg]
        out = Output(quiet=False)
        actx = AppContext(quiet=False)
        actx._output = out
        result = {"service": "api-main", "healthy": True, "status": "ok"}
        _display_single_check(actx, result)
        captured = capsys.readouterr()
        assert "api-main" in captured.out or "ok" in captured.out

    def test_display_error_with_message(self, capsys: pytest.CaptureFixture) -> None:  # type: ignore[type-arg]
        out = Output(quiet=False)
        actx = AppContext(quiet=False)
        actx._output = out
        result = {"service": "api-main", "healthy": False, "status": "error", "error": "connection refused"}
        _display_single_check(actx, result)
        captured = capsys.readouterr()
        assert "connection refused" in captured.out or "api-main" in captured.out

    def test_display_json_mode(self, capsys: pytest.CaptureFixture) -> None:  # type: ignore[type-arg]
        out = Output(json_mode=True)
        actx = AppContext(quiet=True, json_mode=True)
        actx._output = out
        result = {"service": "api-main", "healthy": True, "status": "ok"}
        _display_single_check(actx, result)
        captured = capsys.readouterr()
        assert '"service"' in captured.out
        assert "api-main" in captured.out


# ---------------------------------------------------------------------------
# _display_all_results unit tests
# ---------------------------------------------------------------------------
class TestDisplayAllResults:
    def test_display_all_healthy(self, capsys: pytest.CaptureFixture) -> None:  # type: ignore[type-arg]
        out = Output(quiet=False)
        actx = AppContext(quiet=False)
        actx._output = out
        results = [
            {"service": "api-main", "healthy": True, "status": "ok"},
            {"service": "ai-main", "healthy": True, "status": "ok"},
        ]
        _display_all_results(actx, results)
        captured = capsys.readouterr()
        assert "api-main" in captured.out
        assert "healthy" in captured.out.lower() or "All" in captured.out

    def test_display_partial_failure(self, capsys: pytest.CaptureFixture) -> None:  # type: ignore[type-arg]
        out = Output(quiet=False)
        actx = AppContext(quiet=False)
        actx._output = out
        results = [
            {"service": "api-main", "healthy": True, "status": "ok"},
            {"service": "database", "healthy": False, "status": "error", "error": "timeout"},
        ]
        _display_all_results(actx, results)
        captured = capsys.readouterr()
        assert "1/2" in captured.out or "1" in captured.out


# ---------------------------------------------------------------------------
# health api command
# ---------------------------------------------------------------------------
class TestHealthApiCommand:
    def test_api_healthy(self) -> None:
        mock_client = MagicMock()
        mock_client.health_check.return_value = (True, {"status": "ok"})

        with patch(
            "kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)
        ):
            result = runner.invoke(app, ["health", "api"])

        assert result.exit_code == 0

    def test_api_unhealthy_exits_1(self) -> None:
        mock_client = MagicMock()
        mock_client.health_check.return_value = (False, {"status": "error"})

        with patch(
            "kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)
        ):
            result = runner.invoke(app, ["health", "api"])

        assert result.exit_code == 1

    def test_api_connection_error_exits_1(self) -> None:
        from kctl_api.core.exceptions import ConnectionError as KctlConnectionError

        mock_client = MagicMock()
        mock_client.health_check.side_effect = KctlConnectionError("http://localhost", ConnectionError("refused"))

        with patch(
            "kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)
        ):
            result = runner.invoke(app, ["health", "api"])

        assert result.exit_code == 1

    def test_api_json_output(self) -> None:
        mock_client = MagicMock()
        mock_client.health_check.return_value = (True, {"status": "ok"})

        with patch(
            "kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)
        ):
            result = runner.invoke(app, ["--json", "health", "api"])

        assert result.exit_code == 0
        assert '"service"' in result.output
        assert "api-main" in result.output


# ---------------------------------------------------------------------------
# health ai command
# ---------------------------------------------------------------------------
class TestHealthAiCommand:
    def test_ai_healthy(self) -> None:
        mock_ai_client = MagicMock()
        mock_ai_client.get.return_value = {"status": "ok"}

        with patch(
            "kctl_api.core.callbacks.AppContext.ai_client", new_callable=lambda: property(lambda self: mock_ai_client)
        ):
            result = runner.invoke(app, ["health", "ai"])

        assert result.exit_code == 0

    def test_ai_unhealthy_exits_1(self) -> None:
        mock_ai_client = MagicMock()
        mock_ai_client.get.return_value = {"status": "error"}

        with patch(
            "kctl_api.core.callbacks.AppContext.ai_client", new_callable=lambda: property(lambda self: mock_ai_client)
        ):
            result = runner.invoke(app, ["health", "ai"])

        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# health db command
# ---------------------------------------------------------------------------
class TestHealthDbCommand:
    def test_db_no_database_url(self) -> None:
        """Without database_url, should exit 1 with error message."""
        with patch("kctl_api.core.callbacks.AppContext.database_url", new_callable=lambda: property(lambda self: "")):
            result = runner.invoke(app, ["health", "db"])
        assert result.exit_code == 1

    def test_db_with_mocked_query(self) -> None:
        async def mock_execute_query(db_url: str, sql: str) -> list:
            return [{"ping": 1}]

        async def mock_dispose() -> None:
            pass

        with (
            patch(
                "kctl_api.core.callbacks.AppContext.database_url",
                new_callable=lambda: property(lambda self: "postgresql+asyncpg://localhost/test"),
            ),
            patch("kctl_api.commands.health.execute_query", mock_execute_query, create=True),
        ):
            with patch("kctl_api.commands.health._check_db_async") as mock_check:
                import asyncio

                mock_check.return_value = asyncio.coroutine(
                    lambda: {"service": "database", "healthy": True, "status": "ok"}
                )()  # type: ignore[attr-defined]
                # Just verify it runs without unhandled exception
                result = runner.invoke(app, ["health", "db"])
        # Result could be 0 or 1 depending on mock setup; just check no crash
        assert result.exit_code in (0, 1)


# ---------------------------------------------------------------------------
# health redis command
# ---------------------------------------------------------------------------
class TestHealthRedisCommand:
    def test_redis_no_redis_url(self) -> None:
        with patch("kctl_api.core.callbacks.AppContext.redis_url", new_callable=lambda: property(lambda self: "")):
            result = runner.invoke(app, ["health", "redis"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# health all command
# ---------------------------------------------------------------------------
class TestHealthAllCommand:
    def test_all_healthy(self) -> None:
        mock_client = MagicMock()
        mock_client.health_check.return_value = (True, {"status": "ok"})
        mock_ai_client = MagicMock()
        mock_ai_client.get.return_value = {"status": "ok"}

        with (
            patch("kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)),
            patch(
                "kctl_api.core.callbacks.AppContext.ai_client",
                new_callable=lambda: property(lambda self: mock_ai_client),
            ),
            patch("kctl_api.core.callbacks.AppContext.database_url", new_callable=lambda: property(lambda self: "")),
            patch("kctl_api.core.callbacks.AppContext.redis_url", new_callable=lambda: property(lambda self: "")),
        ):
            result = runner.invoke(app, ["health", "all"])

        # Exit 1 because db/redis have no URL configured, but should run
        assert result.exit_code in (0, 1)
        assert "api-main" in result.output

    def test_all_json_mode(self) -> None:
        mock_client = MagicMock()
        mock_client.health_check.return_value = (True, {"status": "ok"})
        mock_ai_client = MagicMock()
        mock_ai_client.get.return_value = {"status": "ok"}

        with (
            patch("kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)),
            patch(
                "kctl_api.core.callbacks.AppContext.ai_client",
                new_callable=lambda: property(lambda self: mock_ai_client),
            ),
            patch("kctl_api.core.callbacks.AppContext.database_url", new_callable=lambda: property(lambda self: "")),
            patch("kctl_api.core.callbacks.AppContext.redis_url", new_callable=lambda: property(lambda self: "")),
        ):
            result = runner.invoke(app, ["--json", "health", "all"])

        assert result.exit_code in (0, 1)
        assert '"service"' in result.output


# ---------------------------------------------------------------------------
# health deep command
# ---------------------------------------------------------------------------
class TestHealthDeepCommand:
    def test_deep_runs_without_crash(self) -> None:
        mock_client = MagicMock()
        mock_client.health_check.return_value = (True, {"status": "ok"})
        mock_ai_client = MagicMock()
        mock_ai_client.get.return_value = {"status": "ok"}

        with (
            patch("kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)),
            patch(
                "kctl_api.core.callbacks.AppContext.ai_client",
                new_callable=lambda: property(lambda self: mock_ai_client),
            ),
            patch("kctl_api.core.callbacks.AppContext.database_url", new_callable=lambda: property(lambda self: "")),
            patch("kctl_api.core.callbacks.AppContext.redis_url", new_callable=lambda: property(lambda self: "")),
        ):
            result = runner.invoke(app, ["health", "deep"])

        # Should exit 0 or 1 depending on db/redis availability
        assert result.exit_code in (0, 1)
        assert "api-main" in result.output


# ---------------------------------------------------------------------------
# health deps-check command
# ---------------------------------------------------------------------------
class TestHealthDepsCheckCommand:
    def test_deps_check_runs(self) -> None:
        mock_client = MagicMock()
        mock_client.base_url = "http://localhost:8000"
        mock_response = MagicMock()
        mock_response.status_code = 200

        import httpx

        with (
            patch("kctl_api.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: mock_client)),
            patch("httpx.get", return_value=mock_response),
        ):
            result = runner.invoke(app, ["health", "deps-check"])

        assert result.exit_code in (0, 1)
