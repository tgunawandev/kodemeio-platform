"""Tests for telegram command group."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from kctl_claw.cli import app

runner = CliRunner()


def test_telegram_bots(project_root):
    """bots lists configured bots with token env and bound agent."""
    result = runner.invoke(app, ["--root", str(project_root), "telegram", "bots"])
    assert result.exit_code == 0
    assert "kodemeiodev" in result.output
    assert "kontenosdev" in result.output
    assert "TELEGRAM_KODEMEIODEV_BOT_TOKEN" in result.output


def test_telegram_bots_json(project_root):
    """bots outputs valid JSON with expected fields."""
    result = runner.invoke(app, ["--root", str(project_root), "--json", "telegram", "bots"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["name"] == "kodemeiodev"
    assert "token_env" in data[0]
    assert "agent" in data[0]


def test_telegram_bots_shows_bound_agent(project_root):
    """bots shows the bound agent from bindings."""
    result = runner.invoke(app, ["--root", str(project_root), "telegram", "bots"])
    assert result.exit_code == 0
    # The binding maps telegram:kodemeiodev -> kodemeiodev
    assert "kodemeiodev" in result.output


def test_telegram_bindings(project_root):
    """bindings shows channel-to-agent mapping."""
    result = runner.invoke(app, ["--root", str(project_root), "telegram", "bindings"])
    assert result.exit_code == 0
    assert "telegram:kodemeiodev" in result.output
    assert "kodemeiodev" in result.output


def test_telegram_bindings_json(project_root):
    """bindings outputs valid JSON."""
    result = runner.invoke(app, ["--root", str(project_root), "--json", "telegram", "bindings"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["channel"] == "telegram:kodemeiodev"
    assert data[0]["agent"] == "kodemeiodev"


def test_telegram_allowlist(project_root):
    """allowlist shows allowed user IDs."""
    result = runner.invoke(app, ["--root", str(project_root), "telegram", "allowlist"])
    assert result.exit_code == 0
    assert "634688702" in result.output
    assert "dm" in result.output


def test_telegram_allowlist_json(project_root):
    """allowlist outputs valid JSON."""
    result = runner.invoke(app, ["--root", str(project_root), "--json", "telegram", "allowlist"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert any(entry["id"] == 634688702 for entry in data)
    assert any(entry["type"] == "dm" for entry in data)
