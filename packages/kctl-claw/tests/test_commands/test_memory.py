"""Tests for memory command group."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_claw.cli import app
from kctl_claw.core.exceptions import GatewayError

runner = CliRunner()


def test_memory_stats(project_root):
    """stats lists files in workspace directory."""
    # conftest creates config/workspace/memory/ directory
    mem_file = project_root / "config" / "workspace" / "memory" / "test.md"
    mem_file.write_text("# Test memory\n")

    result = runner.invoke(app, ["--root", str(project_root), "memory", "stats"])
    assert result.exit_code == 0


def test_memory_stats_missing_workspace(project_root):
    """stats warns gracefully when workspace directory missing."""
    import shutil

    shutil.rmtree(project_root / "config" / "workspace")
    result = runner.invoke(app, ["--root", str(project_root), "memory", "stats"])
    assert result.exit_code == 0
    assert "not found" in result.output


def test_memory_list(project_root):
    """list shows memory files."""
    mem_file = project_root / "config" / "workspace" / "memory" / "notes.md"
    mem_file.write_text("# Notes\n")
    result = runner.invoke(app, ["--root", str(project_root), "memory", "list"])
    assert result.exit_code == 0
    assert "notes.md" in result.output


def test_memory_list_empty(project_root):
    """list shows info message when no memory files exist."""
    result = runner.invoke(app, ["--root", str(project_root), "memory", "list"])
    assert result.exit_code == 0
    assert "No memory files" in result.output


def test_memory_list_missing_directory(project_root):
    """list warns when memory directory missing."""
    import shutil

    shutil.rmtree(project_root / "config" / "workspace" / "memory")
    result = runner.invoke(app, ["--root", str(project_root), "memory", "list"])
    assert result.exit_code == 0
    assert "not found" in result.output


def test_memory_search_graceful_error(project_root):
    """search shows warning when gateway unavailable."""
    mock_gw = MagicMock()
    mock_gw.get.side_effect = GatewayError(message="Connection refused")

    with patch("kctl_claw.core.callbacks.AppContext.gateway", new_callable=lambda: property(lambda self: mock_gw)):
        result = runner.invoke(app, ["--root", str(project_root), "memory", "search", "test query"])

    assert result.exit_code == 0
    assert "Gateway not available" in result.output or "unavailable" in result.output.lower()


def test_memory_prune_abort(project_root):
    """prune aborts when confirmation is wrong."""
    result = runner.invoke(app, ["--root", str(project_root), "memory", "prune"], input="NOPE\n")
    assert result.exit_code == 0
    assert "Aborted" in result.output


def test_memory_prune_confirm_gateway_error(project_root):
    """prune handles gateway error gracefully after confirmation."""
    mock_gw = MagicMock()
    mock_gw.post.side_effect = GatewayError(message="Connection refused")

    with patch("kctl_claw.core.callbacks.AppContext.gateway", new_callable=lambda: property(lambda self: mock_gw)):
        result = runner.invoke(app, ["--root", str(project_root), "memory", "prune"], input="PRUNE\n")

    assert result.exit_code == 0
    assert "Gateway not available" in result.output or "unavailable" in result.output.lower()


def test_memory_clear_abort(project_root):
    """clear aborts when wrong agent name entered."""
    result = runner.invoke(app, ["--root", str(project_root), "memory", "clear", "kodemeiodev"], input="wrongname\n")
    assert result.exit_code == 0
    assert "Aborted" in result.output


def test_memory_clear_confirm_gateway_error(project_root):
    """clear handles gateway error after correct confirmation."""
    mock_gw = MagicMock()
    mock_gw.post.side_effect = GatewayError(message="Connection refused")

    with patch("kctl_claw.core.callbacks.AppContext.gateway", new_callable=lambda: property(lambda self: mock_gw)):
        result = runner.invoke(
            app, ["--root", str(project_root), "memory", "clear", "kodemeiodev"], input="kodemeiodev\n"
        )

    assert result.exit_code == 0
    assert "Gateway not available" in result.output or "unavailable" in result.output.lower()
