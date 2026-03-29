"""Tests for kctl_common.git_ops."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, call, patch

import pytest

from kctl_common.git_ops import branch_status, changelog_generate, diff_summary, pr_create, release_tag


def _make_result(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    r: subprocess.CompletedProcess[str] = MagicMock(spec=subprocess.CompletedProcess)
    r.stdout = stdout
    r.returncode = returncode
    return r


class TestBranchStatus:
    def test_clean_branch_no_ahead_behind(self) -> None:
        def side_effect(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            if "rev-parse" in cmd:
                return _make_result("main\n")
            if "rev-list" in cmd:
                return _make_result("0\t0\n")
            if "status" in cmd:
                return _make_result("")
            if "stash" in cmd:
                return _make_result("")
            return _make_result("", returncode=1)

        with patch("kctl_common.git_ops.run_quiet", side_effect=side_effect):
            result = branch_status()

        assert result["branch"] == "main"
        assert result["ahead"] == 0
        assert result["behind"] == 0
        assert result["dirty_count"] == 0
        assert result["dirty_files"] == []
        assert result["stash_count"] == 0

    def test_dirty_branch_ahead_behind(self) -> None:
        def side_effect(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            if "rev-parse" in cmd:
                return _make_result("feature/foo\n")
            if "rev-list" in cmd:
                return _make_result("3\t1\n")
            if "status" in cmd:
                return _make_result(" M file1.py\n?? file2.txt\n")
            if "stash" in cmd:
                return _make_result("stash@{0}: WIP\nstash@{1}: WIP\n")
            return _make_result("", returncode=1)

        with patch("kctl_common.git_ops.run_quiet", side_effect=side_effect):
            result = branch_status()

        assert result["branch"] == "feature/foo"
        assert result["ahead"] == 3
        assert result["behind"] == 1
        assert result["dirty_count"] == 2
        assert len(result["dirty_files"]) == 2
        assert result["stash_count"] == 2

    def test_git_failure_returns_unknown(self) -> None:
        def side_effect(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            return _make_result("", returncode=1)

        with patch("kctl_common.git_ops.run_quiet", side_effect=side_effect):
            result = branch_status()

        assert result["branch"] == "unknown"
        assert result["ahead"] == 0
        assert result["behind"] == 0

    def test_no_tab_in_ahead_behind(self) -> None:
        def side_effect(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            if "rev-parse" in cmd:
                return _make_result("main\n")
            if "rev-list" in cmd:
                return _make_result("no tab here\n")
            if "status" in cmd:
                return _make_result("")
            if "stash" in cmd:
                return _make_result("")
            return _make_result("", returncode=1)

        with patch("kctl_common.git_ops.run_quiet", side_effect=side_effect):
            result = branch_status()

        assert result["ahead"] == 0
        assert result["behind"] == 0


class TestDiffSummary:
    def test_typical_diff(self) -> None:
        raw = " src/foo.py | 10 +++++-----\n src/bar.py |  5 ++---\n 2 files changed, 8 insertions(+), 7 deletions(-)"
        with patch("kctl_common.git_ops.run_quiet", return_value=_make_result(raw)):
            result = diff_summary()

        assert result["files_changed"] == 2
        assert result["insertions"] == 8
        assert result["deletions"] == 7
        assert result["raw"] == raw.strip()

    def test_single_file_changed(self) -> None:
        raw = " src/foo.py | 3 +++\n 1 file changed, 3 insertions(+)"
        with patch("kctl_common.git_ops.run_quiet", return_value=_make_result(raw)):
            result = diff_summary(base="develop")

        assert result["files_changed"] == 1
        assert result["insertions"] == 3
        assert result["deletions"] == 0

    def test_git_failure_returns_zeros(self) -> None:
        with patch("kctl_common.git_ops.run_quiet", return_value=_make_result("", returncode=1)):
            result = diff_summary()

        assert result == {"files_changed": 0, "insertions": 0, "deletions": 0, "raw": ""}

    def test_empty_diff(self) -> None:
        with patch("kctl_common.git_ops.run_quiet", return_value=_make_result("")):
            result = diff_summary()

        assert result["files_changed"] == 0
        assert result["insertions"] == 0
        assert result["deletions"] == 0


class TestChangelogGenerate:
    def test_mixed_commits(self) -> None:
        log = (
            "abc1234 feat: add login page\n"
            "def5678 fix: handle null pointer\n"
            "ghi9012 chore: update deps\n"
            "jkl3456 feat: add dashboard\n"
        )
        with patch("kctl_common.git_ops.run_quiet", return_value=_make_result(log)):
            result = changelog_generate()

        assert "### Features" in result
        assert "### Fixes" in result
        assert "### Other" in result
        assert "feat: add login page" in result
        assert "fix: handle null pointer" in result
        assert "chore: update deps" in result

    def test_since_tag_passed_to_git(self) -> None:
        with patch("kctl_common.git_ops.run_quiet", return_value=_make_result("")) as mock_rq:
            changelog_generate(since_tag="v1.0.0")

        args = mock_rq.call_args[0][0]
        assert "v1.0.0..HEAD" in args

    def test_no_since_tag_uses_limit(self) -> None:
        with patch("kctl_common.git_ops.run_quiet", return_value=_make_result("")) as mock_rq:
            changelog_generate()

        args = mock_rq.call_args[0][0]
        assert "-50" in args

    def test_only_features(self) -> None:
        log = "abc1234 feat: new feature\n"
        with patch("kctl_common.git_ops.run_quiet", return_value=_make_result(log)):
            result = changelog_generate()

        assert "### Features" in result
        assert "### Fixes" not in result
        assert "### Other" not in result

    def test_git_failure_returns_empty(self) -> None:
        with patch("kctl_common.git_ops.run_quiet", return_value=_make_result("", returncode=1)):
            result = changelog_generate()

        assert result == ""

    def test_empty_log_returns_empty(self) -> None:
        with patch("kctl_common.git_ops.run_quiet", return_value=_make_result("")):
            result = changelog_generate()

        assert result == ""


class TestPrCreate:
    def test_calls_gh_pr_create(self) -> None:
        mock_run = MagicMock(return_value=_make_result("https://github.com/org/repo/pull/42\n"))
        with patch("kctl_common.git_ops.run", mock_run):
            url = pr_create("My PR", "Body text", base="develop")

        assert url == "https://github.com/org/repo/pull/42"
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "gh" in cmd
        assert "pr" in cmd
        assert "create" in cmd
        assert "--title" in cmd
        assert "My PR" in cmd
        assert "--base" in cmd
        assert "develop" in cmd


class TestReleaseTag:
    def test_tags_and_pushes(self) -> None:
        mock_run = MagicMock(return_value=_make_result(""))
        with patch("kctl_common.git_ops.run", mock_run):
            release_tag("v1.2.3", "Release v1.2.3")

        assert mock_run.call_count == 2
        first_cmd = mock_run.call_args_list[0][0][0]
        second_cmd = mock_run.call_args_list[1][0][0]
        assert "tag" in first_cmd
        assert "v1.2.3" in first_cmd
        assert "push" in second_cmd
        assert "v1.2.3" in second_cmd
