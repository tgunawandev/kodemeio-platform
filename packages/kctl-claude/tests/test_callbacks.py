"""Tests for core/callbacks.py — AppContext."""

from __future__ import annotations

from pathlib import Path

from kctl_claude.core.callbacks import AppContext
from kctl_claude.core.output import Output


class TestAppContext:
    def test_lazy_output_initialization(self) -> None:
        ctx = AppContext()
        assert ctx._output is None
        out = ctx.output
        assert isinstance(out, Output)
        # Should return same instance on second access
        assert ctx.output is out

    def test_json_mode_propagated(self) -> None:
        ctx = AppContext(json_mode=True)
        assert ctx.output.json_mode is True

    def test_quiet_propagated(self) -> None:
        ctx = AppContext(quiet=True)
        assert ctx.output.quiet is True

    def test_verbose_default(self) -> None:
        ctx = AppContext()
        assert ctx.verbose is False

    def test_verbose_set(self) -> None:
        ctx = AppContext(verbose=True)
        assert ctx.verbose is True

    def test_paths_lazy(self) -> None:
        ctx = AppContext()
        assert ctx._paths is None
        paths = ctx.paths
        assert isinstance(paths, dict)
        assert "claude_dir" in paths

    def test_claude_dir(self) -> None:
        ctx = AppContext()
        assert ctx.claude_dir == Path.home() / ".claude"

    def test_repo_dir_none_when_not_found(self) -> None:
        ctx = AppContext()
        ctx._paths = {"claude_dir": Path.home() / ".claude", "repo_dir": None}
        assert ctx.repo_dir is None

    def test_config_dir_from_repo(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        (repo / "config" / ".claude").mkdir(parents=True)
        ctx = AppContext()
        ctx._paths = {"claude_dir": tmp_path, "repo_dir": repo}
        assert ctx.config_dir == repo / "config" / ".claude"

    def test_config_dir_none_without_repo(self) -> None:
        ctx = AppContext()
        ctx._paths = {"claude_dir": Path.home() / ".claude", "repo_dir": None}
        assert ctx.config_dir is None
