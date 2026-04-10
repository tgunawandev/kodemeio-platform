"""Tests for cli/src/kctl_outline/core/sync_pull.py.

Pull direction: read documents from an Outline collection and write them
to disk under the mapping's src directory. Uses FakeOutlineClient.
"""

from __future__ import annotations

from pathlib import Path

from kctl_outline.core.sync_config import SyncMapping, SyncMode
from kctl_outline.core.sync_pull import (
    PullResult,
    pull_mapping_to_disk,
    pull_mapping_with_reconcile,
)
from kctl_outline.core.sync_state import FileSyncEntry, MappingSyncEntry


def test_pull_writes_top_level_doc(tmp_repo: Path, fake_client_with_seed) -> None:
    client = fake_client_with_seed(
        collections=[{"name": "Coll", "permission": "read_write"}],
    )
    cid = client.collections[0]["id"]
    client.documents.append(
        {
            "id": "doc-1",
            "title": "Sales",
            "text": "# Sales\n\nBody.\n",
            "collectionId": cid,
            "parentDocumentId": None,
        }
    )
    mapping = SyncMapping(src=Path("shared/06-business-processes"), collection="Coll", mode=SyncMode.PULL)
    written = pull_mapping_to_disk(client, tmp_repo, mapping, state_entry=None)
    target = tmp_repo / "shared" / "06-business-processes" / "sales.md"
    assert target.is_file()
    assert "# Sales" in target.read_text()
    assert target in [w.file_path for w in written]


def test_pull_writes_nested_doc_using_parent_hierarchy(tmp_repo: Path, fake_client_with_seed) -> None:
    client = fake_client_with_seed(
        collections=[{"name": "Coll", "permission": "read_write"}],
    )
    cid = client.collections[0]["id"]
    parent = {"id": "doc-parent", "title": "Sales", "text": "# Sales", "collectionId": cid, "parentDocumentId": None}
    child = {
        "id": "doc-child",
        "title": "CRM Pipeline",
        "text": "# CRM Pipeline",
        "collectionId": cid,
        "parentDocumentId": "doc-parent",
    }
    client.documents.extend([parent, child])
    mapping = SyncMapping(src=Path("shared/06-business-processes"), collection="Coll", mode=SyncMode.PULL)
    pull_mapping_to_disk(client, tmp_repo, mapping, state_entry=None)
    nested = tmp_repo / "shared" / "06-business-processes" / "sales" / "crm-pipeline.md"
    assert nested.is_file()


def test_pull_strips_synced_footer(tmp_repo: Path, fake_client_with_seed) -> None:
    """If the doc text contains the auto-injected source footer from a prior
    push, the pull writer must strip it before saving to disk."""
    client = fake_client_with_seed(
        collections=[{"name": "Coll", "permission": "read_write"}],
    )
    cid = client.collections[0]["id"]
    body = "# Sales\n\nBody.\n"
    footer = (
        "\n\n---\n"
        "> **Source:** `kodemeio-docs/sales.md`\\\n"
        "> **Path:** `/abs/sales.md`\\\n"
        "> *Synced by kctl-outline — do not edit in Outline*"
    )
    client.documents.append(
        {
            "id": "doc-1",
            "title": "Sales",
            "text": body + footer,
            "collectionId": cid,
            "parentDocumentId": None,
        }
    )
    mapping = SyncMapping(src=Path("shared/06-business-processes"), collection="Coll", mode=SyncMode.PULL)
    pull_mapping_to_disk(client, tmp_repo, mapping, state_entry=None)
    target = tmp_repo / "shared" / "06-business-processes" / "sales.md"
    assert target.read_text() == body


def test_pull_subpath_filters_to_subtree(tmp_repo: Path, fake_client_with_seed) -> None:
    """If mapping.subpath is set, only documents under that parent (by title) are pulled."""
    client = fake_client_with_seed(
        collections=[{"name": "Kod — Internal", "permission": "read_write"}],
    )
    cid = client.collections[0]["id"]
    runbooks = {"id": "rb", "title": "Runbooks", "text": "# Runbooks", "collectionId": cid, "parentDocumentId": None}
    bp = {"id": "bp", "title": "Business Processes", "text": "# BP", "collectionId": cid, "parentDocumentId": None}
    rb_child = {
        "id": "rb1",
        "title": "Restart Service",
        "text": "# Restart",
        "collectionId": cid,
        "parentDocumentId": "rb",
    }
    bp_child = {"id": "bp1", "title": "Hiring", "text": "# Hiring", "collectionId": cid, "parentDocumentId": "bp"}
    client.documents.extend([runbooks, bp, rb_child, bp_child])

    mapping = SyncMapping(
        src=Path("tenants/kod/runbooks"),
        collection="Kod — Internal",
        mode=SyncMode.PULL,
        subpath="Runbooks",
    )
    written = pull_mapping_to_disk(client, tmp_repo, mapping, state_entry=None)

    rel_paths = sorted(w.rel_path for w in written)
    assert rel_paths == ["restart-service.md"]
    assert (tmp_repo / "tenants/kod/runbooks/restart-service.md").is_file()
    assert not (tmp_repo / "tenants/kod/runbooks/hiring.md").exists()


def test_pull_with_reconcile_deletes_files_no_longer_in_outline(tmp_repo: Path, fake_client_with_seed) -> None:
    """If a doc was previously synced but is no longer in Outline, the local file is removed."""
    client = fake_client_with_seed(
        collections=[{"name": "Coll", "permission": "read_write"}],
    )
    cid = client.collections[0]["id"]
    # Outline currently has only one doc; the previous state recorded two.
    client.documents.append({
        "id": "doc-still-here",
        "title": "Sales",
        "text": "# Sales",
        "collectionId": cid,
        "parentDocumentId": None,
    })
    src = tmp_repo / "shared" / "06-business-processes"
    src.mkdir(parents=True)
    # Pre-existing local file from a previous sync that should be deleted
    stale = src / "deprecated-process.md"
    stale.write_text("# Deprecated\n")

    state_entry = MappingSyncEntry(
        repo_path=str(tmp_repo),
        src="shared/06-business-processes",
        collection_name="Coll",
        collection_id=cid,
        files={
            "sales.md": FileSyncEntry(
                rel_path="sales.md", doc_id="doc-still-here", content_hash="old", title="Sales", synced_at="prev",
            ),
            "deprecated-process.md": FileSyncEntry(
                rel_path="deprecated-process.md", doc_id="doc-removed-from-outline",
                content_hash="old", title="Deprecated", synced_at="prev",
            ),
        },
    )

    mapping = SyncMapping(
        src=Path("shared/06-business-processes"), collection="Coll", mode=SyncMode.PULL,
    )
    result = pull_mapping_with_reconcile(client, tmp_repo, mapping, state_entry)

    assert isinstance(result, PullResult)
    assert (tmp_repo / "shared/06-business-processes/sales.md").is_file()
    assert not stale.exists(), "stale file should have been deleted"
    assert stale in result.deleted
    assert any(w.rel_path == "sales.md" for w in result.written)


def test_pull_with_reconcile_leaves_untracked_files_alone(tmp_repo: Path, fake_client_with_seed) -> None:
    """An .md file that was never tracked in state must NOT be deleted."""
    client = fake_client_with_seed(
        collections=[{"name": "Coll", "permission": "read_write"}],
    )
    cid = client.collections[0]["id"]
    client.documents.append({
        "id": "doc-1", "title": "Sales", "text": "# Sales",
        "collectionId": cid, "parentDocumentId": None,
    })
    src = tmp_repo / "shared" / "06-business-processes"
    src.mkdir(parents=True)
    untracked = src / "stranger.md"
    untracked.write_text("# Stranger — placed here by a human, not tracked\n")

    state_entry = MappingSyncEntry(
        repo_path=str(tmp_repo), src="shared/06-business-processes",
        collection_name="Coll", collection_id=cid, files={},
    )
    mapping = SyncMapping(src=Path("shared/06-business-processes"), collection="Coll", mode=SyncMode.PULL)
    result = pull_mapping_with_reconcile(client, tmp_repo, mapping, state_entry)

    assert untracked.is_file(), "untracked files must not be touched"
    assert untracked not in result.deleted
