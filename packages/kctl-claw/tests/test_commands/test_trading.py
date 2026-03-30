"""Tests for trading command group."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_claw.cli import app
from kctl_claw.core.exceptions import GatewayError

runner = CliRunner()


def _make_gateway_error():
    return GatewayError(message="Cannot connect to gateway at http://localhost:18789")


def test_trading_status_gateway_unavailable(project_root):
    """status shows helpful message when gateway is not available."""
    with patch(
        "kctl_claw.core.callbacks.AppContext.gateway", new_callable=lambda: property(lambda self: _error_gateway())
    ):
        result = runner.invoke(app, ["--root", str(project_root), "trading", "status"])
    assert result.exit_code == 0
    # Should not crash even without gateway


def test_trading_status_graceful_error(project_root):
    """status handles GatewayError gracefully."""
    mock_gw = MagicMock()
    mock_gw.get.side_effect = GatewayError(message="Connection refused")

    with patch("kctl_claw.core.callbacks.AppContext.gateway", new_callable=lambda: property(lambda self: mock_gw)):
        result = runner.invoke(app, ["--root", str(project_root), "trading", "status"])

    assert result.exit_code == 0
    assert "Gateway not available" in result.output or "unavailable" in result.output.lower()


def test_trading_kill_switch_abort(project_root):
    """kill-switch aborts when wrong confirmation is entered."""
    result = runner.invoke(app, ["--root", str(project_root), "trading", "kill-switch"], input="NOPE\n")
    assert result.exit_code == 0
    assert "Aborted" in result.output


def test_trading_kill_switch_confirm_gateway_error(project_root):
    """kill-switch handles gateway error gracefully after confirmation."""
    mock_gw = MagicMock()
    mock_gw.post.side_effect = GatewayError(message="Connection refused")

    with patch("kctl_claw.core.callbacks.AppContext.gateway", new_callable=lambda: property(lambda self: mock_gw)):
        result = runner.invoke(app, ["--root", str(project_root), "trading", "kill-switch"], input="KILL\n")

    assert result.exit_code == 0
    assert "Gateway not available" in result.output or "unavailable" in result.output.lower()


def test_trading_risk_limits_no_config(project_root):
    """risk-limits shows info when no config present."""
    result = runner.invoke(app, ["--root", str(project_root), "trading", "risk-limits"])
    assert result.exit_code == 0
    # Should show "No risk limits configured" or gateway error
    assert "risk" in result.output.lower() or "configured" in result.output.lower() or "Gateway" in result.output


def test_trading_portfolio_graceful_error(project_root):
    """portfolio handles gateway error gracefully."""
    mock_gw = MagicMock()
    mock_gw.get.side_effect = GatewayError(message="Connection refused")

    with patch("kctl_claw.core.callbacks.AppContext.gateway", new_callable=lambda: property(lambda self: mock_gw)):
        result = runner.invoke(app, ["--root", str(project_root), "trading", "portfolio"])

    assert result.exit_code == 0
    assert "Gateway not available" in result.output or "unavailable" in result.output.lower()


def test_trading_strategies_graceful_error(project_root):
    """strategies handles gateway error gracefully."""
    mock_gw = MagicMock()
    mock_gw.get.side_effect = GatewayError(message="Connection refused")

    with patch("kctl_claw.core.callbacks.AppContext.gateway", new_callable=lambda: property(lambda self: mock_gw)):
        result = runner.invoke(app, ["--root", str(project_root), "trading", "strategies"])

    assert result.exit_code == 0
    assert "Gateway not available" in result.output or "unavailable" in result.output.lower()


def _error_gateway():
    """Return a mock gateway that always errors."""
    mock_gw = MagicMock()
    mock_gw.get.side_effect = GatewayError(message="Connection refused")
    mock_gw.post.side_effect = GatewayError(message="Connection refused")
    return mock_gw
