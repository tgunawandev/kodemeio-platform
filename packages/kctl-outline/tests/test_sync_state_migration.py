"""Tests for the v1 → v2 sync state migration."""

from __future__ import annotations

import json
from pathlib import Path

from kctl_outline.core.sync_state import (
    FileSyncEntry,
    MappingSyncEntry,
    SyncState,
    migrate_v1_to_v2,
)


def test_v2_state_has_mappings_keyed_by_repo_and_collection() -> None:
    state = SyncState(version=2)
    state.mappings["repo1::Collection A"] = MappingSyncEntry(
        repo_path="/tmp/repo1",
        src="shared",
        collection_name="Collection A",
        collection_id="col-1",
        files={},
    )
    assert "repo1::Collection A" in state.mappings


def test_migrate_v1_state_creates_one_mapping_per_repo() -> None:
    v1 = {
        "version": 1,
        "repos": {
            "/abs/path/kodemeio-docs": {
                "repo_path": "/abs/path/kodemeio-docs",
                "repo_name": "kodemeio-docs",
                "collection_id": "col-old",
                "collection_name": "Documentation",
                "parent_doc_id": "doc-old",
                "files": {
                    "README.md": {
                        "rel_path": "README.md",
                        "doc_id": "doc-1",
                        "content_hash": "abc",
                        "title": "README",
                        "synced_at": "2026-04-01T00:00:00",
                    }
                },
                "last_synced": "2026-04-01T00:00:00",
            }
        },
    }
    v2 = migrate_v1_to_v2(v1)
    assert v2.version == 2
    assert len(v2.mappings) == 1
    key = next(iter(v2.mappings.keys()))
    assert "kodemeio-docs" in key
    m = v2.mappings[key]
    assert m.collection_name == "Documentation"
    assert m.src == "."
    assert "README.md" in m.files
    assert m.files["README.md"].doc_id == "doc-1"


def test_load_v1_file_auto_migrates(tmp_path: Path, monkeypatch) -> None:
    """When STATE_FILE is v1 on disk, load_sync_state returns a v2 state."""
    v1_path = tmp_path / "outline-sync.json"
    v1_path.write_text(
        json.dumps(
            {
                "version": 1,
                "repos": {
                    "/r": {
                        "repo_path": "/r",
                        "repo_name": "r",
                        "collection_id": "c",
                        "collection_name": "Docs",
                        "parent_doc_id": "p",
                        "files": {},
                        "last_synced": "",
                    }
                },
            }
        )
    )

    import kctl_outline.core.sync_state as st

    monkeypatch.setattr(st, "STATE_FILE", v1_path)
    monkeypatch.setattr(st, "STATE_DIR", tmp_path)
    state = st.load_sync_state()
    assert state.version == 2
    assert len(state.mappings) == 1


def test_v2_round_trip(tmp_path: Path, monkeypatch) -> None:
    import kctl_outline.core.sync_state as st

    monkeypatch.setattr(st, "STATE_FILE", tmp_path / "out.json")
    monkeypatch.setattr(st, "STATE_DIR", tmp_path)
    state = SyncState(version=2)
    state.mappings["k::Coll"] = MappingSyncEntry(
        repo_path="/k",
        src=".",
        collection_name="Coll",
        collection_id="c1",
        files={"a.md": FileSyncEntry(rel_path="a.md", doc_id="d", content_hash="h", title="A", synced_at="now")},
    )
    st.save_sync_state(state)
    loaded = st.load_sync_state()
    assert loaded.version == 2
    assert "k::Coll" in loaded.mappings
    assert loaded.mappings["k::Coll"].files["a.md"].doc_id == "d"
