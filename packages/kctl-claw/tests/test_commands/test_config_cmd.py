"""Tests for config command group."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from kctl_claw.cli import app

runner = CliRunner()


def test_config_validate_all_ok(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "config", "validate"])
    assert result.exit_code == 0
    assert "OK" in result.output


def test_config_validate_bad_json(project_root):
    # Corrupt openclaw.json
    (project_root / "config" / "openclaw.json").write_text("{bad json}")
    result = runner.invoke(app, ["--root", str(project_root), "config", "validate"])
    assert result.exit_code == 1


def test_config_validate_missing_key(project_root):
    # Write openclaw.json with missing 'agents' key
    (project_root / "config" / "openclaw.json").write_text(json.dumps({"gateway": {}}))
    result = runner.invoke(app, ["--root", str(project_root), "config", "validate"])
    assert result.exit_code == 1
    assert "agents" in result.output


def test_config_show_openclaw(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "config", "show", "openclaw"])
    assert result.exit_code == 0
    assert "agents" in result.output


def test_config_show_mcp(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "config", "show", "mcp"])
    assert result.exit_code == 0
    assert "mcpServers" in result.output


def test_config_show_cron(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "config", "show", "cron"])
    assert result.exit_code == 0
    assert "jobs" in result.output


def test_config_show_unknown_file(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "config", "show", "unknown"])
    assert result.exit_code == 1
    assert "Unknown config file" in result.output


def test_config_reload_no_docker(project_root):
    # Docker is not available in tests — should fail gracefully with exit code 1
    result = runner.invoke(app, ["--root", str(project_root), "config", "reload"])
    assert result.exit_code == 1


def test_config_init(project_root, tmp_path, monkeypatch):
    # Redirect the config dir so we don't overwrite real config
    fake_config_dir = tmp_path / "fake-config-dir"
    fake_config_dir.mkdir()
    monkeypatch.setattr("kctl_common.config.CONFIG_DIR", fake_config_dir)
    monkeypatch.setattr("kctl_common.config.CONFIG_FILE", fake_config_dir / "config.yaml")

    result = runner.invoke(
        app,
        ["--root", str(project_root), "config", "init", "--gateway-url", "https://openclaw.kodeme.io"],
    )
    assert result.exit_code == 0
    assert "saved" in result.output.lower() or "Profile" in result.output
