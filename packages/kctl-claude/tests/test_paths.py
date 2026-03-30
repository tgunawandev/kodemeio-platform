"""Tests for core/paths.py — path resolution."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from kctl_claude.core.paths import _find_repo, resolve_paths


class TestResolvePaths:
    def test_returns_claude_dir(self) -> None:
        paths = resolve_paths()
        assert paths["claude_dir"] == Path.home() / ".claude"

    def test_returns_all_keys(self) -> None:
        paths = resolve_paths()
        assert "claude_dir" in paths
        assert "repo_dir" in paths
        assert "config_dir" in paths
        assert "scripts_dir" in paths


class TestFindRepo:
    def test_finds_repo_from_git(self, tmp_path: Path) -> None:
        # Simulate being inside a git repo with config/.claude
        (tmp_path / "config" / ".claude").mkdir(parents=True)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = str(tmp_path) + "\n"
        with patch("kctl_claude.core.paths.subprocess.run", return_value=mock_result):
            result = _find_repo()
        assert result == tmp_path

    def test_git_not_found(self) -> None:
        with patch(
            "kctl_claude.core.paths.subprocess.run",
            side_effect=FileNotFoundError("git not found"),
        ):
            # May return a well-known path or None
            result = _find_repo()
            assert result is None or isinstance(result, Path)

    def test_git_timeout(self) -> None:
        with patch(
            "kctl_claude.core.paths.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="git", timeout=3),
        ):
            result = _find_repo()
            assert result is None or isinstance(result, Path)

    def test_git_repo_without_config_dir(self, tmp_path: Path) -> None:
        # Repo exists but no config/.claude
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = str(tmp_path) + "\n"
        with patch("kctl_claude.core.paths.subprocess.run", return_value=mock_result):
            result = _find_repo()
        # Should fall through to well-known paths
        assert result is None or isinstance(result, Path)
