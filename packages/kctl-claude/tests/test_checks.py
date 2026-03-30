"""Unit tests for the health check collector (core/checks.py)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from kctl_claude.core.checks import (
    _auth_info,
    _claude_info,
    _config_info,
    _count_config,
    _git_info,
    _server_info,
    _settings_info,
    _sync_status,
    _tools_info,
    _update_info,
    collect_status,
)


class TestCollectStatus:
    """Test the top-level collect_status function."""

    def test_returns_all_keys(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        data = collect_status(claude_dir, None)
        assert "timestamp" in data
        assert "claude" in data
        assert "auth" in data
        assert "config" in data
        assert "settings" in data
        assert "tools" in data
        assert "server" in data
        assert "git" in data
        assert "updates" in data


class TestClaudeInfo:
    def test_not_installed(self) -> None:
        with patch("kctl_claude.core.checks.shutil.which", return_value=None):
            result = _claude_info()
        assert result["installed"] is False
        assert result["version"] == ""

    def test_installed(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "1.0.5\n"
        with (
            patch("kctl_claude.core.checks.shutil.which", return_value="/usr/bin/claude"),
            patch("kctl_claude.core.checks.subprocess.run", return_value=mock_result),
        ):
            result = _claude_info()
        assert result["installed"] is True
        assert result["version"] == "1.0.5"

    def test_version_timeout(self) -> None:
        with (
            patch("kctl_claude.core.checks.shutil.which", return_value="/usr/bin/claude"),
            patch(
                "kctl_claude.core.checks.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=5),
            ),
        ):
            result = _claude_info()
        assert result["installed"] is True
        assert result["version"] == "unknown"


class TestAuthInfo:
    def test_has_credentials(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / ".credentials.json").write_text("{}")
        result = _auth_info(claude_dir)
        assert result["credentials"] is True

    def test_no_credentials(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        result = _auth_info(claude_dir)
        assert result["credentials"] is False


class TestCountConfig:
    def test_empty_dir(self, tmp_path: Path) -> None:
        result = _count_config(tmp_path)
        assert result == {"agents": 0, "skills": 0, "commands": 0, "rules": 0}

    def test_none_path(self) -> None:
        result = _count_config(None)
        assert result["agents"] == 0

    def test_with_files(self, tmp_path: Path) -> None:
        (tmp_path / "agents").mkdir()
        (tmp_path / "agents" / "a.md").write_text("agent")
        (tmp_path / "agents" / "b.md").write_text("agent")
        (tmp_path / "rules").mkdir()
        (tmp_path / "rules" / "r.md").write_text("rule")
        result = _count_config(tmp_path)
        assert result["agents"] == 2
        assert result["rules"] == 1
        assert result["skills"] == 0

    def test_with_skills(self, tmp_path: Path) -> None:
        (tmp_path / "skills").mkdir()
        (tmp_path / "skills" / "skill1").mkdir()
        (tmp_path / "skills" / "skill2").mkdir()
        result = _count_config(tmp_path)
        assert result["skills"] == 2


class TestSyncStatus:
    def test_no_config_dir(self, tmp_path: Path) -> None:
        result = _sync_status(tmp_path, None)
        assert result["sync_status"] == "no-repo"

    def test_synced(self, tmp_path: Path) -> None:
        local = tmp_path / "local"
        repo = tmp_path / "repo"
        for d in (local, repo):
            (d / "agents").mkdir(parents=True)
            (d / "agents" / "a.md").write_text("same content")
        result = _sync_status(local, repo)
        assert result["sync_status"] == "synced"

    def test_out_of_sync(self, tmp_path: Path) -> None:
        local = tmp_path / "local"
        repo = tmp_path / "repo"
        for d in (local, repo):
            (d / "agents").mkdir(parents=True)
        (local / "agents" / "a.md").write_text("local content")
        (repo / "agents" / "a.md").write_text("repo content")
        result = _sync_status(local, repo)
        assert result["sync_status"] == "out-of-sync"
        assert len(result["sync_details"]) > 0


class TestSettingsInfo:
    def test_no_settings(self, tmp_path: Path) -> None:
        result = _settings_info(tmp_path)
        assert result["exists"] is False

    def test_with_settings(self, tmp_path: Path) -> None:
        sf = tmp_path / "settings.json"
        sf.write_text('{"PreToolUse": [], "enabledPlugins": []}')
        result = _settings_info(tmp_path)
        assert result["exists"] is True
        assert result["hooks"] is True
        assert result["plugins"] is True


class TestConfigInfo:
    def test_no_repo(self, tmp_path: Path) -> None:
        result = _config_info(tmp_path, None)
        assert result["sync_status"] == "no-repo"
        assert result["repo"] == {}


class TestToolsInfo:
    def test_returns_expected_keys(self) -> None:
        result = _tools_info()
        assert "kctl_installed" in result
        assert "kctl_total" in result
        assert "kctl_config" in result
        for tool in ("ruff", "prettier", "docker", "uv", "gh"):
            assert tool in result


class TestServerInfo:
    def test_no_docker(self) -> None:
        with patch("kctl_claude.core.checks.shutil.which", return_value=None):
            result = _server_info()
        assert result["container_running"] is False
        assert result["sdk_api_up"] is False


class TestGitInfo:
    def test_returns_dict(self) -> None:
        result = _git_info()
        assert "branch" in result
        assert "clean" in result

    def test_git_not_found(self) -> None:
        with patch(
            "kctl_claude.core.checks.subprocess.run",
            side_effect=FileNotFoundError("git"),
        ):
            result = _git_info()
        assert result["branch"] == ""
        assert result["clean"] is True


class TestUpdateInfo:
    def test_no_commands(self) -> None:
        with patch(
            "kctl_claude.core.checks.subprocess.run",
            side_effect=FileNotFoundError("not found"),
        ):
            result = _update_info()
        assert result["current"] == ""
        assert result["latest_npm"] == ""
        assert result["up_to_date"] is False
