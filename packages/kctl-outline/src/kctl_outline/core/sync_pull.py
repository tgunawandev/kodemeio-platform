"""Pull direction: copy documents from an Outline collection to disk."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from kctl_outline.core.sync_config import SyncMapping
from kctl_outline.core.sync_state import MappingSyncEntry, compute_file_hash


@dataclass
class PulledFile:
    rel_path: str  # relative to mapping.src
    file_path: Path  # absolute path on disk
    doc_id: str
    content_hash: str
    title: str


@dataclass
class PullResult:
    """Outcome of a pull operation, including reconciliation actions."""

    written: list[PulledFile]
    deleted: list[Path]  # files removed because their Outline doc no longer exists


_SYNCED_FOOTER_RE = re.compile(
    r"\n\n---\n"
    r"> \*\*Source:\*\*[^\n]*\n"
    r"> \*\*Path:\*\*[^\n]*\n"
    r"> \*Synced by kctl-outline[^\n]*",
    re.MULTILINE,
)


def _title_to_filename(title: str) -> str:
    """Convert an Outline doc title to a kebab-case filename stem."""
    s = title.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s or "untitled"


def _strip_synced_footer(text: str) -> str:
    return _SYNCED_FOOTER_RE.sub("", text).rstrip() + "\n"


def _build_doc_index(documents: list[dict]) -> dict[str, dict]:
    return {d["id"]: d for d in documents}


def _doc_path_segments(doc: dict, index: dict[str, dict]) -> list[str]:
    """Walk parents to compute the directory path (excluding the leaf doc)."""
    parts: list[str] = []
    parent_id = doc.get("parentDocumentId")
    while parent_id:
        parent = index.get(parent_id)
        if parent is None:
            break
        parts.append(_title_to_filename(parent["title"]))
        parent_id = parent.get("parentDocumentId")
    return list(reversed(parts))


def pull_mapping_to_disk(
    client,
    repo_path: Path,
    mapping: SyncMapping,
    state_entry: MappingSyncEntry | None,
) -> list[PulledFile]:
    """Walk an Outline collection and write its documents to disk under mapping.src.

    Args:
        client: kctl-outline httpx client (or FakeOutlineClient)
        repo_path: repo root
        mapping: SyncMapping with mode=PULL
        state_entry: previous mapping state (currently unused; reserved for
                     conflict detection in a later iteration)

    Returns:
        List of PulledFile records describing what was written.
    """
    # Resolve collection id
    collections = client.post_all("collections.list")
    cid = next((c["id"] for c in collections if c.get("name") == mapping.collection), None)
    if cid is None:
        raise ValueError(f"collection not found: {mapping.collection!r}")

    docs = client.post_all("documents.list", params={"collectionId": cid})
    index = _build_doc_index(docs)

    # If subpath is set, restrict to descendants of the doc with that title
    subpath_root_id: str | None = None
    if mapping.subpath:
        for d in docs:
            if d.get("title") == mapping.subpath and d.get("parentDocumentId") is None:
                subpath_root_id = d["id"]
                break
        if subpath_root_id is None:
            return []

    def _is_in_subpath(doc: dict) -> bool:
        if subpath_root_id is None:
            return True
        if doc["id"] == subpath_root_id:
            return False  # the subpath root itself is the "folder", not a file
        parent_id = doc.get("parentDocumentId")
        while parent_id:
            if parent_id == subpath_root_id:
                return True
            parent = index.get(parent_id)
            parent_id = parent.get("parentDocumentId") if parent else None
        return False

    src_root = (repo_path / mapping.src).resolve()
    src_root.mkdir(parents=True, exist_ok=True)

    written: list[PulledFile] = []
    for doc in docs:
        if not _is_in_subpath(doc):
            continue

        # Compute path: parents (minus subpath root if any) → leaf filename
        all_segments = _doc_path_segments(doc, index)
        if subpath_root_id is not None and all_segments:
            # Drop the subpath root from the prefix
            subpath_segment = _title_to_filename(index[subpath_root_id]["title"])
            try:
                idx = all_segments.index(subpath_segment)
                all_segments = all_segments[idx + 1 :]
            except ValueError:
                pass

        leaf = _title_to_filename(doc["title"]) + ".md"
        rel_segments = all_segments + [leaf]
        rel_path = "/".join(rel_segments)
        target = src_root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)

        body = _strip_synced_footer(doc.get("text", "") or "")
        if not body.endswith("\n"):
            body += "\n"
        target.write_text(body)

        written.append(
            PulledFile(
                rel_path=rel_path,
                file_path=target,
                doc_id=doc["id"],
                content_hash=compute_file_hash(target),
                title=doc["title"],
            )
        )

    return written


def pull_mapping_with_reconcile(
    client,
    repo_path: Path,
    mapping: SyncMapping,
    state_entry: MappingSyncEntry | None,
) -> PullResult:
    """Pull from Outline AND reconcile deletions against the previous state.

    Any file that exists in `state_entry.files` but no longer corresponds to
    a document on the Outline side gets deleted from disk and reported in
    PullResult.deleted. This is the reconciliation behavior the nightly cron
    needs so that documents removed in Outline don't linger on disk.

    Files NOT tracked in state_entry are left alone (a stranger could have
    placed an unrelated .md file under mapping.src — we don't touch it).
    """
    written = pull_mapping_to_disk(client, repo_path, mapping, state_entry)

    deleted: list[Path] = []
    if state_entry is not None and state_entry.files:
        live_doc_ids = {w.doc_id for w in written}
        live_rel_paths = {w.rel_path for w in written}
        src_root = (repo_path / mapping.src).resolve()
        for tracked_rel, tracked_entry in state_entry.files.items():
            if tracked_entry.doc_id in live_doc_ids:
                continue
            if tracked_rel in live_rel_paths:
                continue
            stale_path = src_root / tracked_rel
            if stale_path.is_file():
                stale_path.unlink()
                deleted.append(stale_path)
                # Best-effort: remove now-empty parent directories under src_root
                parent = stale_path.parent
                while parent != src_root and parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()
                    parent = parent.parent

    return PullResult(written=written, deleted=deleted)
