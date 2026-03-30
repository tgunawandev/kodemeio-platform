"""Tests for ConfigManager — JSON config read/write/patch/validate."""

from __future__ import annotations

import json

import pytest

from kctl_claw.core.config_manager import ConfigFile, ConfigManager


def _make_project(tmp_path):
    """Create minimal project structure for testing."""
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "cron").mkdir()
    openclaw = {"agents": {"list": [{"name": "test", "model": "opus"}]}}
    (tmp_path / "config" / "openclaw.json").write_text(json.dumps(openclaw))
    mcp = {"mcpServers": {"test-server": {"command": "node", "args": ["/opt/test.mjs"]}}}
    (tmp_path / "config" / "config.json").write_text(json.dumps(mcp))
    jobs = {"jobs": [{"id": "job1", "name": "Job 1", "schedule": "0 7 * * *", "enabled": True}]}
    (tmp_path / "config" / "cron" / "jobs.json").write_text(json.dumps(jobs))
    return tmp_path


def test_read(tmp_path):
    root = _make_project(tmp_path)
    mgr = ConfigManager(root)
    data = mgr.read(ConfigFile.OPENCLAW)
    assert data["agents"]["list"][0]["name"] == "test"


def test_write_atomic(tmp_path):
    root = _make_project(tmp_path)
    mgr = ConfigManager(root)
    data = mgr.read(ConfigFile.OPENCLAW)
    data["agents"]["list"][0]["model"] = "sonnet"
    mgr.write(ConfigFile.OPENCLAW, data)
    reloaded = mgr.read(ConfigFile.OPENCLAW)
    assert reloaded["agents"]["list"][0]["model"] == "sonnet"


def test_backup_before_modify(tmp_path):
    root = _make_project(tmp_path)
    mgr = ConfigManager(root)
    bak_path = mgr.backup_before_modify(ConfigFile.OPENCLAW)
    assert bak_path.exists()
    assert ".bak." in bak_path.name


def test_diff(tmp_path):
    root = _make_project(tmp_path)
    mgr = ConfigManager(root)
    local = mgr.read(ConfigFile.OPENCLAW)
    remote = json.loads(json.dumps(local))
    remote["agents"]["list"][0]["model"] = "different"
    diffs = mgr.diff(ConfigFile.OPENCLAW, remote)
    assert len(diffs) > 0


def test_read_nonexistent_raises(tmp_path):
    mgr = ConfigManager(tmp_path)
    with pytest.raises(FileNotFoundError):
        mgr.read(ConfigFile.OPENCLAW)
