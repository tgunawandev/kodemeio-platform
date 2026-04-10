"""Sync markdown docs between repos and Outline wiki.

Supports multi-mapping configs (.outline-sync.yaml v2) with per-mapping
direction (push/pull/mixed) and .ssot marker awareness.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional

import typer

from kctl_outline.core.callbacks import AppContext
from kctl_outline.core.client import OutlineClient
from kctl_outline.core.config import resolve_connection
from kctl_outline.core.exceptions import APIError
from kctl_outline.core.sync_config import SyncConfig, SyncMapping, SyncMode, load_sync_config
from kctl_outline.core.sync_planner import (
    PlannedAction,
    PlannedActionKind,
    plan_push_mapping,
)
from kctl_outline.core.sync_pull import pull_mapping_with_reconcile
from kctl_outline.core.sync_ssot import SSoTMode, find_ssot_mode
from kctl_outline.core.sync_state import (
    FileSyncEntry,
    MappingSyncEntry,
    SyncState,
    _mapping_key,
    load_sync_state,
    save_sync_state,
)

app = typer.Typer(help="Sync markdown docs from repos to Outline wiki.")


# --- Outline API helpers (push direction) ---


def _api_call_with_retry(client, endpoint: str, data: dict, max_retries: int = 6) -> dict:
    """POST to Outline API with retry on 429 rate limit."""
    for attempt in range(max_retries):
        try:
            result = client.post(endpoint, data=data)
            if endpoint.endswith((".create", ".update")):
                time.sleep(0.5)
            return result
        except APIError as e:
            if e.status_code == 429 and attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("unreachable")


def _ensure_collection(client, name: str) -> str:
    collections = client.post_all("collections.list")
    for col in collections:
        if col.get("name") == name:
            return col["id"]
    result = _api_call_with_retry(
        client,
        "collections.create",
        data={
            "name": name,
            "permission": "read_write",
        },
    )
    return result["data"]["id"]


def _ensure_parent_doc(client, collection_id: str, label: str) -> str:
    docs = client.post_all("documents.list", params={"collectionId": collection_id})
    for doc in docs:
        if doc.get("title") == label and doc.get("parentDocumentId") is None:
            return doc["id"]
    result = _api_call_with_retry(
        client,
        "documents.create",
        data={
            "title": label,
            "text": f"# {label}\n\nSynced documentation.",
            "collectionId": collection_id,
            "publish": True,
        },
    )
    return result["data"]["id"]


def _find_child_doc(
    client, collection_id: str, parent_doc_id: str | None, title: str, docs_cache: list[dict]
) -> str | None:
    for doc in docs_cache:
        if doc.get("title") == title and doc.get("parentDocumentId") == parent_doc_id:
            return doc["id"]
    return None


def _ensure_section_doc(
    client,
    collection_id: str,
    parent_doc_id: str,
    section_name: str,
    docs_cache: list[dict],
    section_cache: dict[str, str],
) -> str:
    cache_key = f"{parent_doc_id}/{section_name}"
    if cache_key in section_cache:
        return section_cache[cache_key]
    title = section_name.replace("-", " ").replace("_", " ").title()
    existing = _find_child_doc(client, collection_id, parent_doc_id, title, docs_cache)
    if existing:
        section_cache[cache_key] = existing
        return existing
    result = _api_call_with_retry(
        client,
        "documents.create",
        data={
            "title": title,
            "text": f"# {title}\n",
            "collectionId": collection_id,
            "parentDocumentId": parent_doc_id,
            "publish": True,
        },
    )
    doc_id = result["data"]["id"]
    section_cache[cache_key] = doc_id
    docs_cache.append({"id": doc_id, "title": title, "parentDocumentId": parent_doc_id})
    return doc_id


def _resolve_parent_for_file(
    client,
    collection_id: str,
    root_parent_doc_id: str,
    rel_path: str,
    docs_cache: list[dict],
    section_cache: dict[str, str],
) -> str:
    parts = Path(rel_path).parts
    if len(parts) <= 1:
        return root_parent_doc_id
    current_parent = root_parent_doc_id
    for dir_part in parts[:-1]:
        current_parent = _ensure_section_doc(client, collection_id, current_parent, dir_part, docs_cache, section_cache)
    return current_parent


# Per-profile client cache. One sync run typically uses one config (one profile),
# so this is at most a single entry — but the cache lets future per-mapping
# routing reuse clients if multiple profiles end up in the same config.
_CLIENT_CACHE: dict[str, OutlineClient] = {}


def _build_client_for_mapping(
    ctx: typer.Context,
    mapping: SyncMapping,
    cfg: SyncConfig | None = None,
):
    """Return the Outline client for a given mapping.

    Routing priority:
      1. If cfg.profile is set, build a fresh client using that profile (so
         that .outline-sync.kod.yaml hits outline.kodeme.io and
         .outline-sync.tpp.yaml hits outline.idtpp.com regardless of which
         profile the active CLI invocation chose).
      2. Otherwise fall back to the context's default client (the active
         CLI profile / env / overrides).

    Clients are cached by profile name within a single CLI invocation.
    """
    profile = cfg.profile if cfg is not None and cfg.profile else None
    if not profile:
        return ctx.obj.client

    if profile in _CLIENT_CACHE:
        return _CLIENT_CACHE[profile]

    url, token = resolve_connection(
        profile_name=profile,
        url_override=ctx.obj.url_override if ctx.obj else None,
        token_override=ctx.obj.token_override if ctx.obj else None,
    )
    client = OutlineClient(base_url=url, token=token)
    _CLIENT_CACHE[profile] = client
    return client


# --- Mode helpers ---


def _filter_actions_by_ssot(
    actions: list[PlannedAction],
    repo_path: Path,
    expected_mode: SSoTMode,
) -> list[PlannedAction]:
    """For mixed mode: keep only actions where the file's .ssot marker matches expected_mode."""
    out: list[PlannedAction] = []
    for a in actions:
        marker = find_ssot_mode(a.file_path, root=repo_path)
        if marker == expected_mode or marker is None:
            out.append(a)
    return out


def _execute_push(
    client,
    output,
    repo_path: Path,
    mapping: SyncMapping,
    actions: list[PlannedAction],
    state: SyncState,
) -> None:
    """Apply CREATE/UPDATE/SKIP actions to Outline."""
    now = datetime.now(timezone.utc).isoformat()
    repo_label = (Path(repo_path).name + "/" + str(mapping.src)).rstrip("/")

    collection_id = _ensure_collection(client, mapping.collection)
    root_parent = mapping.subpath or repo_label
    root_parent_id = _ensure_parent_doc(client, collection_id, root_parent)
    docs_cache = client.post_all("documents.list", params={"collectionId": collection_id})
    section_cache: dict[str, str] = {}

    key = _mapping_key(str(repo_path), mapping.collection, str(mapping.src))
    entry = state.mappings.get(key) or MappingSyncEntry(
        repo_path=str(repo_path),
        src=str(mapping.src),
        collection_name=mapping.collection,
        collection_id=collection_id,
        parent_doc_id=root_parent_id,
    )
    entry.collection_id = collection_id
    entry.parent_doc_id = root_parent_id

    created = updated = skipped = 0
    for action in actions:
        if action.kind == PlannedActionKind.SKIP:
            skipped += 1
            output.info(f"  skip   {action.rel_path}")
            continue

        body = action.file_path.read_text()
        footer = (
            f"\n\n---\n"
            f"> **Source:** `{repo_label}/{action.rel_path}`\\\n"
            f"> **Path:** `{action.file_path}`\\\n"
            f"> *Synced by kctl-outline — do not edit in Outline*"
        )
        text = body + footer

        target_parent_id = _resolve_parent_for_file(
            client,
            collection_id,
            root_parent_id,
            action.rel_path,
            docs_cache,
            section_cache,
        )

        if action.kind == PlannedActionKind.CREATE:
            existing_id = _find_child_doc(client, collection_id, target_parent_id, action.title, docs_cache)
            if existing_id:
                _api_call_with_retry(
                    client,
                    "documents.update",
                    data={
                        "id": existing_id,
                        "title": action.title,
                        "text": text,
                    },
                )
                action.doc_id = existing_id
                output.success(f"  update {action.rel_path} -> {action.title} (found existing)")
                updated += 1
            else:
                result = _api_call_with_retry(
                    client,
                    "documents.create",
                    data={
                        "title": action.title,
                        "text": text,
                        "collectionId": collection_id,
                        "parentDocumentId": target_parent_id,
                        "publish": True,
                    },
                )
                action.doc_id = result["data"]["id"]
                docs_cache.append({"id": action.doc_id, "title": action.title, "parentDocumentId": target_parent_id})
                output.success(f"  create {action.rel_path} -> {action.title}")
                created += 1
        elif action.kind == PlannedActionKind.UPDATE:
            _api_call_with_retry(
                client,
                "documents.update",
                data={
                    "id": action.doc_id,
                    "title": action.title,
                    "text": text,
                },
            )
            output.success(f"  update {action.rel_path} -> {action.title}")
            updated += 1

        entry.files[action.rel_path] = FileSyncEntry(
            rel_path=action.rel_path,
            doc_id=action.doc_id,
            content_hash=action.content_hash,
            title=action.title,
            synced_at=now,
        )

    entry.last_synced = now
    state.mappings[key] = entry
    save_sync_state(state)
    output.info(f"  Summary: {created} created, {updated} updated, {skipped} skipped")


def _execute_pull(
    client,
    output,
    repo_path: Path,
    mapping: SyncMapping,
    state: SyncState,
) -> None:
    """Pull from Outline to disk and reconcile deletions against state."""
    key = _mapping_key(str(repo_path), mapping.collection, str(mapping.src))
    entry = state.mappings.get(key)
    result = pull_mapping_with_reconcile(client, repo_path, mapping, state_entry=entry)
    now = datetime.now(timezone.utc).isoformat()

    new_entry = entry or MappingSyncEntry(
        repo_path=str(repo_path),
        src=str(mapping.src),
        collection_name=mapping.collection,
        collection_id="",
    )
    new_entry.files = {}
    for w in result.written:
        new_entry.files[w.rel_path] = FileSyncEntry(
            rel_path=w.rel_path,
            doc_id=w.doc_id,
            content_hash=w.content_hash,
            title=w.title,
            synced_at=now,
        )
        output.success(f"  pulled  {w.rel_path}")
    for d in result.deleted:
        try:
            rel = d.relative_to(repo_path)
        except ValueError:
            rel = d
        output.warn(f"  deleted {rel} (no longer in Outline)")
    new_entry.last_synced = now
    state.mappings[key] = new_entry
    save_sync_state(state)
    output.info(f"  Summary: {len(result.written)} pulled, {len(result.deleted)} deleted")


# --- Commands ---


@app.command("run")
def sync_run(
    ctx: typer.Context,
    path: Annotated[Optional[str], typer.Argument(help="Path to repo directory")] = None,
    no_dry_run: Annotated[bool, typer.Option("--no-dry-run", help="Actually write changes")] = False,
    mode_filter: Annotated[
        Optional[str], typer.Option("--mode", help="Run only mappings with this mode (push/pull/mixed)")
    ] = None,
    config_file: Annotated[
        Optional[str],
        typer.Option(
            "--config",
            help="Sync config file (default: .outline-sync.yaml). Use this to point at .outline-sync.kod.yaml or .outline-sync.tpp.yaml.",
        ),
    ] = None,
) -> None:
    """Sync markdown docs from a repo to Outline. Dry-run by default."""
    c: AppContext = ctx.obj
    if path is None:
        path = "."
    repo_path = Path(path).resolve()

    cfg = load_sync_config(repo_path, config_file=config_file)
    if cfg is None:
        looked_for = config_file or ".outline-sync.yaml"
        c.output.warn(f"{repo_path}: {looked_for} not found")
        raise typer.Exit(code=1)

    state = load_sync_state()
    dry_run = not no_dry_run
    mode_filter_value = SyncMode(mode_filter) if mode_filter else None

    for mapping in cfg.mappings:
        if mode_filter_value and mapping.mode != mode_filter_value and mapping.mode != SyncMode.MIXED:
            continue

        # Lazy client construction: dry-run push doesn't need credentials.
        # Only build the client when we're actually going to hit the API.
        client = None
        c.output.header(f"{repo_path.name} -> {mapping.collection} [{mapping.mode.value}]")

        if mapping.mode == SyncMode.PUSH or mapping.mode == SyncMode.MIXED:
            entry = state.mappings.get(_mapping_key(str(repo_path), mapping.collection, str(mapping.src)))
            actions = plan_push_mapping(repo_path, mapping, entry)
            if mapping.mode == SyncMode.MIXED:
                actions = _filter_actions_by_ssot(actions, repo_path, SSoTMode.GIT)
            for a in actions:
                color = {"create": "green", "update": "yellow", "skip": "dim"}.get(a.kind.value, "")
                c.output.text(f"  [{color}]{a.kind.value:6s}[/{color}] {a.rel_path} -> {a.title}")
            if not dry_run:
                if client is None:
                    client = _build_client_for_mapping(ctx, mapping, cfg)
                _execute_push(client, c.output, repo_path, mapping, actions, state)

        if mapping.mode == SyncMode.PULL or mapping.mode == SyncMode.MIXED:
            if dry_run:
                c.output.info(f"  (pull dry-run: would walk collection '{mapping.collection}')")
            else:
                if client is None:
                    client = _build_client_for_mapping(ctx, mapping, cfg)
                _execute_pull(client, c.output, repo_path, mapping, state)

    if dry_run:
        c.output.info("\nDry run complete. Use --no-dry-run to apply.")


@app.command("status")
def sync_status(
    ctx: typer.Context,
    path: Annotated[Optional[str], typer.Argument(help="Filter by repo path")] = None,
) -> None:
    """Show tracked sync state (per-mapping in v2)."""
    c: AppContext = ctx.obj
    state = load_sync_state()
    if not state.mappings:
        c.output.info("No mappings synced yet.")
        return
    rows = []
    for key, m in state.mappings.items():
        rows.append(
            [
                Path(m.repo_path).name,
                m.src or ".",
                m.collection_name,
                str(len(m.files)),
                m.last_synced[:19] if m.last_synced else "-",
            ]
        )
    c.output.table(
        f"Synced Mappings ({len(rows)})",
        [("Repo", "green"), ("Src", "cyan"), ("Collection", "cyan"), ("Files", ""), ("Last Synced", "dim")],
        rows,
    )


@app.command("diff")
def sync_diff(
    ctx: typer.Context,
    path: Annotated[str, typer.Argument(help="Path to repo directory")],
    config_file: Annotated[
        Optional[str],
        typer.Option("--config", help="Sync config file (default: .outline-sync.yaml)"),
    ] = None,
) -> None:
    """Show what would change on next sync (push mappings only)."""
    c: AppContext = ctx.obj
    repo_path = Path(path).resolve()
    cfg = load_sync_config(repo_path, config_file=config_file)
    if cfg is None:
        looked_for = config_file or ".outline-sync.yaml"
        c.output.warn(f"{repo_path}: {looked_for} not found")
        raise typer.Exit(code=1)
    state = load_sync_state()
    for mapping in cfg.mappings:
        if mapping.mode == SyncMode.PULL:
            c.output.info(f"  ({mapping.collection}: pull mode — diff not supported)")
            continue
        entry = state.mappings.get(_mapping_key(str(repo_path), mapping.collection, str(mapping.src)))
        actions = plan_push_mapping(repo_path, mapping, entry)
        c.output.header(f"{repo_path.name} -> {mapping.collection}")
        for a in actions:
            c.output.text(f"  {a.kind.value:6s} {a.rel_path} -> {a.title}")


@app.command("init")
def sync_init(
    ctx: typer.Context,
    path: Annotated[str, typer.Argument(help="Path to repo directory")],
    collection: Annotated[str, typer.Option("--collection", "-c", help="Collection name")] = "Documentation",
) -> None:
    """Create a minimal .outline-sync.yaml v2 stub."""
    c: AppContext = ctx.obj
    repo_path = Path(path).resolve()
    cfg_file = repo_path / ".outline-sync.yaml"
    if cfg_file.exists():
        c.output.warn(f"Config already exists: {cfg_file}")
        return
    content = (
        f"# Outline sync config (v2)\n"
        f"mappings:\n"
        f"  - src: .\n"
        f"    collection: {collection!r}\n"
        f"    mode: push\n"
        f"    include:\n"
        f"      - README.md\n"
        f"      - CLAUDE.md\n"
    )
    cfg_file.write_text(content)
    c.output.success(f"Created {cfg_file}")


@app.command("reset")
def sync_reset(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Clear all sync state (does NOT delete documents from Outline)."""
    c: AppContext = ctx.obj
    state = load_sync_state()
    if not state.mappings:
        c.output.info("No sync state to clear.")
        return
    if not force and not typer.confirm(f"Clear ALL sync state ({len(state.mappings)} mappings)?"):
        raise typer.Abort()
    state.mappings.clear()
    save_sync_state(state)
    c.output.success("Cleared all sync state")
