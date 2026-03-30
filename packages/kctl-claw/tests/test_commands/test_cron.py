"""Tests for cron command group."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from kctl_claw.cli import app

runner = CliRunner()


def test_cron_list(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "cron", "list"])
    assert result.exit_code == 0
    assert "morning-briefing" in result.output
    # Rich may truncate long IDs in narrow terminal; check prefix
    assert "system-health-ch" in result.output


def test_cron_list_json(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "--json", "cron", "list"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 3


def test_cron_get(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "cron", "get", "morning-briefing"])
    assert result.exit_code == 0
    assert "morning-briefing" in result.output
    assert "0 7 * * *" in result.output


def test_cron_disable(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "cron", "disable", "morning-briefing"])
    assert result.exit_code == 0
    cfg = json.loads((project_root / "config" / "cron" / "jobs.json").read_text())
    job = next(j for j in cfg["jobs"] if j["id"] == "morning-briefing")
    assert job["enabled"] is False


def test_cron_enable(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "cron", "enable", "weekly-content-plan"])
    assert result.exit_code == 0
    cfg = json.loads((project_root / "config" / "cron" / "jobs.json").read_text())
    job = next(j for j in cfg["jobs"] if j["id"] == "weekly-content-plan")
    assert job["enabled"] is True


def test_cron_get_not_found(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "cron", "get", "nonexistent"])
    assert result.exit_code == 1


def test_cron_set_schedule(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "cron", "set-schedule", "morning-briefing", "0 8 * * *"])
    assert result.exit_code == 0
    cfg = json.loads((project_root / "config" / "cron" / "jobs.json").read_text())
    job = next(j for j in cfg["jobs"] if j["id"] == "morning-briefing")
    assert job["schedule"] == "0 8 * * *"


def test_cron_set_schedule_invalid(project_root):
    result = runner.invoke(app, ["--root", str(project_root), "cron", "set-schedule", "morning-briefing", "not-a-cron"])
    assert result.exit_code == 1


def test_cron_set_model(project_root):
    result = runner.invoke(
        app, ["--root", str(project_root), "cron", "set-model", "morning-briefing", "claude-sonnet-4-20250514"]
    )
    assert result.exit_code == 0
    cfg = json.loads((project_root / "config" / "cron" / "jobs.json").read_text())
    job = next(j for j in cfg["jobs"] if j["id"] == "morning-briefing")
    assert job["model"] == "claude-sonnet-4-20250514"
