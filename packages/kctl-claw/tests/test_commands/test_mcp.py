"""Tests for mcp command group."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from kctl_claw.cli import app

runner = CliRunner()


def test_mcp_list(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "mcp", "list"])
    assert result.exit_code == 0
    assert "kodemeio-mcp-odoo" in result.output
    assert "kodemeio-mcp-prometheus" in result.output


def test_mcp_list_json(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "--json", "mcp", "list"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert any(d["name"] == "kodemeio-mcp-odoo" for d in data)


def test_mcp_get(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "mcp", "get", "kodemeio-mcp-odoo"])
    assert result.exit_code == 0
    assert "kodemeio-mcp-odoo" in result.output
    assert "node" in result.output


def test_mcp_get_not_found(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "mcp", "get", "nonexistent-server"])
    assert result.exit_code == 1


def test_mcp_get_shows_env_vars(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "mcp", "get", "kodemeio-mcp-odoo"])
    assert result.exit_code == 0
    # The sample fixture has ODOO_URL env var
    assert "ODOO_URL" in result.output


def test_mcp_tools_placeholder(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "mcp", "tools", "kodemeio-mcp-odoo"])
    assert result.exit_code == 0
    assert "introspection" in result.output.lower() or "container" in result.output.lower()


def test_mcp_tools_not_found(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "mcp", "tools", "nonexistent"])
    assert result.exit_code == 1


def test_mcp_profiles(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "mcp", "profiles"])
    assert result.exit_code == 0
    assert "default" in result.output
    assert "content" in result.output


def test_mcp_add_to_profile(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "mcp", "add-to-profile", "brave-search", "trading"])
    assert result.exit_code == 0
    # Verify it was added
    cfg = json.loads((project_root / "config" / "openclaw.json").read_text())
    trading_servers = cfg["tools"]["profiles"]["trading"]["servers"]
    assert "brave-search" in trading_servers


def test_mcp_add_to_profile_duplicate(project_root):
    # brave-search is already in 'content' profile in sample fixture
    result = runner.invoke(app, ["--root", str(project_root), "mcp", "add-to-profile", "brave-search", "content"])
    assert result.exit_code == 0
    assert "already" in result.output.lower()


def test_mcp_add_to_profile_invalid_profile(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "mcp", "add-to-profile", "brave-search", "nonexistent"])
    assert result.exit_code == 1


def test_mcp_remove_from_profile(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "mcp", "remove-from-profile", "brave-search", "content"])
    assert result.exit_code == 0
    cfg = json.loads((project_root / "config" / "openclaw.json").read_text())
    content_servers = cfg["tools"]["profiles"]["content"]["servers"]
    assert "brave-search" not in content_servers


def test_mcp_remove_from_profile_not_member(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "mcp", "remove-from-profile", "brave-search", "trading"])
    assert result.exit_code == 0
    assert "not in" in result.output.lower()
