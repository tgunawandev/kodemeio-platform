"""Tests for agents command group."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from kctl_claw.cli import app

runner = CliRunner()


def test_agents_list(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "agents", "list"])
    assert result.exit_code == 0
    assert "kodemeiodev" in result.output
    assert "kontenosdev" in result.output


def test_agents_list_json(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "--json", "agents", "list"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 5
    assert data[0]["name"] == "kodemeiodev"


def test_agents_get(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "agents", "get", "kodemeiodev"])
    assert result.exit_code == 0
    assert "kodemeiodev" in result.output
    assert "opus" in result.output


def test_agents_get_not_found(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "agents", "get", "nonexistent"])
    assert result.exit_code == 1


def test_agents_set_model(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "agents", "set-model", "journaltxdev", "claude-opus-4-6"])
    assert result.exit_code == 0
    # Verify the config was updated
    cfg = json.loads((project_root / "config" / "openclaw.json").read_text())
    agent = next(a for a in cfg["agents"]["list"] if a["name"] == "journaltxdev")
    assert agent["model"] == "claude-opus-4-6"


def test_agents_set_profile(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "agents", "set-profile", "journaltxdev", "default"])
    assert result.exit_code == 0
    cfg = json.loads((project_root / "config" / "openclaw.json").read_text())
    agent = next(a for a in cfg["agents"]["list"] if a["name"] == "journaltxdev")
    assert agent["profile"] == "default"


def test_agents_set_thinking(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "agents", "set-thinking", "kodemeiodev", "high"])
    assert result.exit_code == 0
    cfg = json.loads((project_root / "config" / "openclaw.json").read_text())
    agent = next(a for a in cfg["agents"]["list"] if a["name"] == "kodemeiodev")
    assert agent["thinking"] == "high"


def test_agents_set_thinking_invalid(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "agents", "set-thinking", "kodemeiodev", "turbo"])
    assert result.exit_code == 1


def test_agents_workspace_kodemeiodev(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "agents", "workspace", "kodemeiodev"])
    assert result.exit_code == 0


def test_agents_workspace_kontenosdev(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "agents", "workspace", "kontenosdev"])
    assert result.exit_code == 0


def test_agents_workspace_missing(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "agents", "workspace", "journaltxdev"])
    assert result.exit_code == 0
    assert "Workspace not found" in result.output
