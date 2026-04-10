"""Pure planning logic for kctl-outline sync.

The planner takes a SyncMapping and current state, and returns a list of
PlannedActions. It performs no I/O against Outline; remote-state lookups
are passed in by the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from kctl_outline.core.sync_config import SyncMapping
from kctl_outline.core.sync_state import (
    FileSyncEntry,
    MappingSyncEntry,
    compute_file_hash,
)


class PlannedActionKind(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    SKIP = "skip"
    DELETE_REMOTE = "delete_remote"  # used by pull planner only
    WRITE_LOCAL = "write_local"  # used by pull planner only


@dataclass
class PlannedAction:
    kind: PlannedActionKind
    rel_path: str  # relative to mapping src
    file_path: Path  # absolute path on disk (may not exist for pull/create-local)
    title: str
    content_hash: str
    doc_id: str = ""

    def __lt__(self, other: "PlannedAction") -> bool:  # for sorting in tests
        return (self.kind.value, self.rel_path) < (other.kind.value, other.rel_path)


def _title_from_path(rel: str) -> str:
    """Convert a path stem to a Title Case document title."""
    import re

    stem = Path(rel).stem
    if stem.upper() in {"README", "CLAUDE", "CHANGELOG"}:
        return stem.upper() if stem.upper() != "CHANGELOG" else "Changelog"
    name = re.sub(r"^\d+[-_]", "", stem)
    words = re.split(r"[-_]", name)
    return " ".join(w.capitalize() for w in words)


def _glob_to_regex(pattern: str) -> "re.Pattern[str]":
    """Translate a gitignore-style glob into a regex.

    Supports `**` (recursive zero-or-more path segments), `*` (any chars
    except `/`), and `?` (single char except `/`). Anchored both ends.
    """
    import re

    out = ["^"]
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == "*":
            if i + 1 < len(pattern) and pattern[i + 1] == "*":
                # `**` consumes any number of path segments (including zero)
                # Followed by `/` means "zero or more dirs" — strip the slash too
                if i + 2 < len(pattern) and pattern[i + 2] == "/":
                    out.append("(?:.*/)?")
                    i += 3
                    continue
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
            i += 1
            continue
        if c == "?":
            out.append("[^/]")
            i += 1
            continue
        out.append(re.escape(c))
        i += 1
    out.append("$")
    return re.compile("".join(out))


def _matches_any(rel: str, patterns: list[str]) -> bool:
    return any(_glob_to_regex(pat).match(rel) for pat in patterns)


def _discover_markdown(src_root: Path) -> list[Path]:
    """Find all .md files under src_root, excluding .ssot markers and dotdirs."""
    out: list[Path] = []
    for p in sorted(src_root.rglob("*.md")):
        if any(part.startswith(".") for part in p.relative_to(src_root).parts):
            continue
        out.append(p)
    return out


def plan_push_mapping(
    repo_path: Path,
    mapping: SyncMapping,
    state_entry: MappingSyncEntry | None,
) -> list[PlannedAction]:
    """Plan push actions for one mapping.

    Args:
        repo_path: repo root (config-relative paths anchor here)
        mapping: SyncMapping describing src/collection/mode/filters
        state_entry: previously-synced state for this mapping (None on first sync)

    Returns:
        List of PlannedActions, one per source file. Files matching the
        include/exclude rules but unchanged since last sync get a SKIP action;
        new files get CREATE; changed files get UPDATE.
    """
    src_root = (repo_path / mapping.src).resolve()
    files = _discover_markdown(src_root)

    actions: list[PlannedAction] = []
    seen: set[str] = set()
    for fp in files:
        rel = fp.relative_to(src_root).as_posix()
        if mapping.include and not _matches_any(rel, mapping.include):
            continue
        if mapping.exclude and _matches_any(rel, mapping.exclude):
            continue
        seen.add(rel)
        title = _title_from_path(rel)
        h = compute_file_hash(fp)

        if state_entry and rel in state_entry.files:
            existing = state_entry.files[rel]
            if existing.content_hash == h:
                actions.append(
                    PlannedAction(
                        kind=PlannedActionKind.SKIP,
                        rel_path=rel,
                        file_path=fp,
                        title=title,
                        content_hash=h,
                        doc_id=existing.doc_id,
                    )
                )
            else:
                actions.append(
                    PlannedAction(
                        kind=PlannedActionKind.UPDATE,
                        rel_path=rel,
                        file_path=fp,
                        title=title,
                        content_hash=h,
                        doc_id=existing.doc_id,
                    )
                )
        else:
            actions.append(
                PlannedAction(
                    kind=PlannedActionKind.CREATE,
                    rel_path=rel,
                    file_path=fp,
                    title=title,
                    content_hash=h,
                )
            )
    return actions
