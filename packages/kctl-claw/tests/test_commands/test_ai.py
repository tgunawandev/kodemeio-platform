"""Tests for ai command group."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_claw.cli import app
from kctl_claw.core.exceptions import GatewayError

runner = CliRunner()


def _error_gateway():
    """Return a mock gateway that always raises GatewayError."""
    mock_gw = MagicMock()
    mock_gw.get.side_effect = GatewayError(message="Connection refused")
    return mock_gw


def test_ai_usage_graceful_error(project_root):
    """usage shows warning when gateway unavailable."""
    mock_gw = MagicMock()
    mock_gw.get.side_effect = GatewayError(message="Connection refused")

    with patch("kctl_claw.core.callbacks.AppContext.gateway", new_callable=lambda: property(lambda self: mock_gw)):
        result = runner.invoke(app, ["--root", str(project_root), "ai", "usage"])

    assert result.exit_code == 0
    assert "Gateway not available" in result.output or "unavailable" in result.output.lower()


def test_ai_cost_graceful_error(project_root):
    """cost shows warning when gateway unavailable."""
    mock_gw = MagicMock()
    mock_gw.get.side_effect = GatewayError(message="Connection refused")

    with patch("kctl_claw.core.callbacks.AppContext.gateway", new_callable=lambda: property(lambda self: mock_gw)):
        result = runner.invoke(app, ["--root", str(project_root), "ai", "cost"])

    assert result.exit_code == 0
    assert "Gateway not available" in result.output or "unavailable" in result.output.lower()


def test_ai_models_graceful_error(project_root):
    """models shows warning when gateway unavailable."""
    mock_gw = MagicMock()
    mock_gw.get.side_effect = GatewayError(message="Connection refused")

    with patch("kctl_claw.core.callbacks.AppContext.gateway", new_callable=lambda: property(lambda self: mock_gw)):
        result = runner.invoke(app, ["--root", str(project_root), "ai", "models"])

    assert result.exit_code == 0
    assert "Gateway not available" in result.output or "unavailable" in result.output.lower()


def test_ai_top_consumers_graceful_error(project_root):
    """top-consumers shows warning when gateway unavailable."""
    mock_gw = MagicMock()
    mock_gw.get.side_effect = GatewayError(message="Connection refused")

    with patch("kctl_claw.core.callbacks.AppContext.gateway", new_callable=lambda: property(lambda self: mock_gw)):
        result = runner.invoke(app, ["--root", str(project_root), "ai", "top-consumers"])

    assert result.exit_code == 0
    assert "Gateway not available" in result.output or "unavailable" in result.output.lower()


def test_ai_usage_dict_response(project_root):
    """usage renders dict response from gateway."""
    mock_gw = MagicMock()
    mock_gw.get.return_value = {"total_tokens": 10000, "total_cost_usd": 0.25}

    with patch("kctl_claw.core.callbacks.AppContext.gateway", new_callable=lambda: property(lambda self: mock_gw)):
        result = runner.invoke(app, ["--root", str(project_root), "ai", "usage"])

    assert result.exit_code == 0
    assert "total_tokens" in result.output or "10000" in result.output


def test_ai_models_list_response(project_root):
    """models renders list response from gateway."""
    mock_gw = MagicMock()
    mock_gw.get.return_value = [{"model": "claude-opus-4-6", "requests": 100, "tokens": 50000, "latency_ms": 1200}]

    with patch("kctl_claw.core.callbacks.AppContext.gateway", new_callable=lambda: property(lambda self: mock_gw)):
        result = runner.invoke(app, ["--root", str(project_root), "ai", "models"])

    assert result.exit_code == 0
    assert "claude-opus-4-6" in result.output
