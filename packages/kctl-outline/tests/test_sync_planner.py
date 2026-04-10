"""Tests for cli/src/kctl_outline/core/sync_planner.py — planning only, no I/O."""

from __future__ import annotations

from pathlib import Path

import pytest

from kctl_outline.core.sync_config import SyncConfig, SyncMapping, SyncMode
from kctl_outline.core.sync_planner import (
    PlannedAction,
    PlannedActionKind,
    plan_push_mapping,
)
from kctl_outline.core.sync_state import MappingSyncEntry, FileSyncEntry


def _write(tmp: Path, rel: str, content: str) -> Path:
    p = tmp / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


def test_plan_push_creates_for_new_files(tmp_repo: Path) -> None:
    _write(tmp_repo, "shared/01-getting-started/intro.md", "# Intro\n")
    _write(tmp_repo, "shared/02-architecture/system.md", "# System\n")
    mapping = SyncMapping(src=Path("shared"), collection="Coll", mode=SyncMode.PUSH)
    actions = plan_push_mapping(tmp_repo, mapping, state_entry=None)
    kinds = sorted((a.kind for a in actions))
    assert kinds == [PlannedActionKind.CREATE, PlannedActionKind.CREATE]
    paths = sorted(a.rel_path for a in actions)
    assert paths == ["01-getting-started/intro.md", "02-architecture/system.md"]


def test_plan_push_skips_unchanged_files(tmp_repo: Path) -> None:
    f = _write(tmp_repo, "shared/01-getting-started/intro.md", "# Intro\n")
    mapping = SyncMapping(src=Path("shared"), collection="Coll", mode=SyncMode.PUSH)
    from kctl_outline.core.sync_state import compute_file_hash

    h = compute_file_hash(f)
    state_entry = MappingSyncEntry(
        repo_path=str(tmp_repo),
        src="shared",
        collection_name="Coll",
        collection_id="c1",
        files={
            "01-getting-started/intro.md": FileSyncEntry(
                rel_path="01-getting-started/intro.md",
                doc_id="d1",
                content_hash=h,
                title="Intro",
                synced_at="now",
            )
        },
    )
    actions = plan_push_mapping(tmp_repo, mapping, state_entry=state_entry)
    assert len(actions) == 1
    assert actions[0].kind == PlannedActionKind.SKIP


def test_plan_push_updates_changed_files(tmp_repo: Path) -> None:
    _write(tmp_repo, "shared/intro.md", "# Different Content\n")
    mapping = SyncMapping(src=Path("shared"), collection="Coll", mode=SyncMode.PUSH)
    state_entry = MappingSyncEntry(
        repo_path=str(tmp_repo),
        src="shared",
        collection_name="Coll",
        collection_id="c1",
        files={
            "intro.md": FileSyncEntry(
                rel_path="intro.md",
                doc_id="d1",
                content_hash="stale-hash",
                title="Intro",
                synced_at="now",
            )
        },
    )
    actions = plan_push_mapping(tmp_repo, mapping, state_entry=state_entry)
    assert len(actions) == 1
    assert actions[0].kind == PlannedActionKind.UPDATE
    assert actions[0].doc_id == "d1"


def test_plan_push_respects_include_globs(tmp_repo: Path) -> None:
    _write(tmp_repo, "shared/01-getting-started/intro.md", "x")
    _write(tmp_repo, "shared/draft/wip.md", "x")
    _write(tmp_repo, "shared/02-architecture/system.md", "x")
    mapping = SyncMapping(
        src=Path("shared"),
        collection="Coll",
        mode=SyncMode.PUSH,
        include=["01-*/**", "02-*/**"],
    )
    actions = plan_push_mapping(tmp_repo, mapping, state_entry=None)
    paths = sorted(a.rel_path for a in actions)
    assert paths == ["01-getting-started/intro.md", "02-architecture/system.md"]


def test_plan_push_respects_exclude_globs(tmp_repo: Path) -> None:
    _write(tmp_repo, "shared/intro.md", "x")
    _write(tmp_repo, "shared/draft/wip.md", "x")
    mapping = SyncMapping(
        src=Path("shared"),
        collection="Coll",
        mode=SyncMode.PUSH,
        exclude=["**/draft/**"],
    )
    actions = plan_push_mapping(tmp_repo, mapping, state_entry=None)
    paths = [a.rel_path for a in actions]
    assert paths == ["intro.md"]


def test_plan_push_skips_ssot_marker_files(tmp_repo: Path, write_ssot) -> None:
    """`.ssot` marker files themselves should never be synced."""
    _write(tmp_repo, "shared/intro.md", "x")
    write_ssot("shared", "git")
    mapping = SyncMapping(src=Path("shared"), collection="Coll", mode=SyncMode.PUSH)
    actions = plan_push_mapping(tmp_repo, mapping, state_entry=None)
    paths = [a.rel_path for a in actions]
    assert paths == ["intro.md"]


def test_plan_push_skips_non_markdown(tmp_repo: Path) -> None:
    _write(tmp_repo, "shared/intro.md", "x")
    _write(tmp_repo, "shared/image.png", "x")
    _write(tmp_repo, "shared/data.json", "x")
    mapping = SyncMapping(src=Path("shared"), collection="Coll", mode=SyncMode.PUSH)
    actions = plan_push_mapping(tmp_repo, mapping, state_entry=None)
    assert len(actions) == 1
    assert actions[0].rel_path == "intro.md"
