"""Sync state persistence for repo-to-Outline synchronization."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from pydantic import BaseModel, Field


STATE_DIR = Path.home() / ".config" / "kodemeio"
STATE_FILE = STATE_DIR / "outline-sync.json"


class FileSyncEntry(BaseModel):
    """Tracks a single synced file."""

    rel_path: str
    doc_id: str
    content_hash: str
    title: str
    synced_at: str  # ISO 8601


class RepoSyncEntry(BaseModel):
    """Tracks a synced repository."""

    repo_path: str
    repo_name: str
    collection_id: str
    collection_name: str
    parent_doc_id: str
    files: dict[str, FileSyncEntry] = Field(default_factory=dict)
    last_synced: str = ""  # ISO 8601


class MappingSyncEntry(BaseModel):
    """Tracks a single (repo, src, collection) sync mapping."""

    repo_path: str
    src: str  # path relative to repo_path
    collection_name: str
    collection_id: str
    parent_doc_id: str = ""
    files: dict[str, FileSyncEntry] = Field(default_factory=dict)
    last_synced: str = ""


def _mapping_key(repo_path: str, collection_name: str, src: str) -> str:
    """Stable key for storing a mapping in SyncState.mappings."""
    return f"{Path(repo_path).name}::{src}::{collection_name}"


class SyncState(BaseModel):
    """Root sync state model.

    v1: per-repo state in `repos` (deprecated, kept for migration only)
    v2: per-mapping state in `mappings`
    """

    version: int = 2
    repos: dict[str, RepoSyncEntry] = Field(default_factory=dict)
    mappings: dict[str, MappingSyncEntry] = Field(default_factory=dict)


def migrate_v1_to_v2(data: dict) -> "SyncState":
    """Convert a v1 state dict (read from disk) into a v2 SyncState object."""
    new_mappings: dict[str, MappingSyncEntry] = {}
    for repo_key, repo in (data.get("repos") or {}).items():
        m = MappingSyncEntry(
            repo_path=repo["repo_path"],
            src=".",
            collection_name=repo.get("collection_name", "Documentation"),
            collection_id=repo.get("collection_id", ""),
            parent_doc_id=repo.get("parent_doc_id", ""),
            files={k: FileSyncEntry.model_validate(v) for k, v in (repo.get("files") or {}).items()},
            last_synced=repo.get("last_synced", ""),
        )
        new_mappings[_mapping_key(m.repo_path, m.collection_name, m.src)] = m
    return SyncState(version=2, mappings=new_mappings)


def compute_file_hash(path: Path) -> str:
    """SHA-256 hash of file contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def load_sync_state() -> SyncState:
    """Load sync state from disk, returning empty v2 state if missing.

    Auto-migrates v1 state files to v2 in-memory (does not rewrite disk
    until the next save_sync_state call).
    """
    if not STATE_FILE.exists():
        return SyncState(version=2)
    try:
        data = json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, ValueError):
        return SyncState(version=2)
    if data.get("version", 1) == 1:
        return migrate_v1_to_v2(data)
    try:
        return SyncState.model_validate(data)
    except ValueError:
        return SyncState(version=2)


def save_sync_state(state: SyncState) -> None:
    """Atomically write sync state to disk."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    data = state.model_dump(mode="json")
    fd, tmp_path = tempfile.mkstemp(dir=STATE_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, STATE_FILE)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
