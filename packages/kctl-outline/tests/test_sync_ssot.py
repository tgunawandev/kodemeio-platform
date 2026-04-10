"""Tests for cli/src/kctl_outline/core/sync_ssot.py."""

from __future__ import annotations

from pathlib import Path

from kctl_outline.core.sync_ssot import SSoTMode, find_ssot_mode


def test_no_marker_returns_none(tmp_repo: Path) -> None:
    f = tmp_repo / "doc.md"
    f.write_text("# x")
    assert find_ssot_mode(f, root=tmp_repo) is None


def test_git_marker_in_same_dir(tmp_repo: Path, write_ssot) -> None:
    write_ssot("shared/02-architecture", "git")
    f = tmp_repo / "shared" / "02-architecture" / "system.md"
    f.write_text("# x")
    assert find_ssot_mode(f, root=tmp_repo) == SSoTMode.GIT


def test_outline_marker_in_same_dir(tmp_repo: Path, write_ssot) -> None:
    write_ssot("shared/06-business-processes", "outline")
    f = tmp_repo / "shared" / "06-business-processes" / "sales.md"
    f.write_text("# x")
    assert find_ssot_mode(f, root=tmp_repo) == SSoTMode.OUTLINE


def test_marker_walks_up(tmp_repo: Path, write_ssot) -> None:
    write_ssot("tenants/terakidz/business-processes", "outline")
    f = tmp_repo / "tenants" / "terakidz" / "business-processes" / "deeply" / "nested.md"
    f.parent.mkdir(parents=True)
    f.write_text("# x")
    assert find_ssot_mode(f, root=tmp_repo) == SSoTMode.OUTLINE


def test_walker_stops_at_root(tmp_repo: Path) -> None:
    """Should never escape above the supplied root."""
    f = tmp_repo / "deep" / "doc.md"
    f.parent.mkdir()
    f.write_text("# x")
    assert find_ssot_mode(f, root=tmp_repo) is None


def test_invalid_marker_value_returns_none(tmp_repo: Path, write_ssot) -> None:
    write_ssot("shared/x", "garbage\n")
    f = tmp_repo / "shared" / "x" / "doc.md"
    f.write_text("# x")
    assert find_ssot_mode(f, root=tmp_repo) is None
