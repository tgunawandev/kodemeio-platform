"""Snapshot export, import, and diff engine for Kodemeio module state.

Enables offline comparison of installed module state between environments.
Snapshots are stored as JSON files on disk and can be diffed without any
network access or Docker runtime.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field


# ============================================================================
# Data Models
# ============================================================================


class SnapshotEntry(BaseModel):
    """A single installed module captured in a snapshot."""

    name: str
    version: str = ""
    state: str = "installed"
    author: str = ""
    category: str = ""


class SnapshotMetadata(BaseModel):
    """Metadata about when and where a snapshot was taken."""

    exported_at: str = ""
    database: str = ""
    odoo_version: str = ""
    profile: str = ""


class ModuleSnapshot(BaseModel):
    """A point-in-time capture of all installed modules in an Odoo database."""

    metadata: SnapshotMetadata
    modules: list[SnapshotEntry] = Field(default_factory=list)


class SnapshotDiff(BaseModel):
    """The result of comparing two ModuleSnapshot objects."""

    source_a: str = ""
    source_b: str = ""
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    # Each tuple: (module_name, version_in_a, version_in_b)
    version_changed: list[tuple[str, str, str]] = Field(default_factory=list)
    # Each tuple: (module_name, state_in_a, state_in_b)
    state_changed: list[tuple[str, str, str]] = Field(default_factory=list)


# ============================================================================
# I/O
# ============================================================================


def save_snapshot(snapshot: ModuleSnapshot, path: Path) -> None:
    """Write a ModuleSnapshot to a JSON file.

    If ``metadata.exported_at`` is empty it is set to the current UTC
    timestamp (ISO 8601) before writing.  An already-set timestamp is
    preserved unchanged.

    Args:
        snapshot: The snapshot to persist.
        path: Destination file path (created or overwritten).
    """
    if not snapshot.metadata.exported_at:
        snapshot.metadata.exported_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")


def load_snapshot(path: Path) -> ModuleSnapshot:
    """Load a ModuleSnapshot from a JSON file.

    Args:
        path: Path to a JSON file previously written by :func:`save_snapshot`.

    Returns:
        A validated :class:`ModuleSnapshot` instance.

    Raises:
        ValueError: If the file contains invalid JSON or does not match the
            expected snapshot structure.
        FileNotFoundError: If the file does not exist (propagated from Path.read_text).
    """
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Snapshot file contains invalid JSON: {path}") from exc

    try:
        return ModuleSnapshot.model_validate(data)
    except Exception as exc:
        raise ValueError(f"Snapshot file has unexpected structure: {path}") from exc


# ============================================================================
# Diff
# ============================================================================


def diff_snapshots(a: ModuleSnapshot, b: ModuleSnapshot) -> SnapshotDiff:
    """Compare two snapshots and return a structured diff.

    Detects:
    - **added**: modules present in *b* but absent from *a*.
    - **removed**: modules present in *a* but absent from *b*.
    - **version_changed**: modules in both with a different ``version``.
    - **state_changed**: modules in both with a different ``state``.

    A module can appear in both ``version_changed`` and ``state_changed``
    simultaneously if both attributes differ.

    Args:
        a: The baseline snapshot (e.g., production).
        b: The comparison snapshot (e.g., staging).

    Returns:
        A :class:`SnapshotDiff` describing all differences.
    """
    map_a: dict[str, SnapshotEntry] = {entry.name: entry for entry in a.modules}
    map_b: dict[str, SnapshotEntry] = {entry.name: entry for entry in b.modules}

    names_a = set(map_a)
    names_b = set(map_b)

    added = sorted(names_b - names_a)
    removed = sorted(names_a - names_b)

    version_changed: list[tuple[str, str, str]] = []
    state_changed: list[tuple[str, str, str]] = []

    for name in sorted(names_a & names_b):
        entry_a = map_a[name]
        entry_b = map_b[name]

        if entry_a.version != entry_b.version:
            version_changed.append((name, entry_a.version, entry_b.version))

        if entry_a.state != entry_b.state:
            state_changed.append((name, entry_a.state, entry_b.state))

    return SnapshotDiff(
        source_a=a.metadata.database,
        source_b=b.metadata.database,
        added=added,
        removed=removed,
        version_changed=version_changed,
        state_changed=state_changed,
    )
