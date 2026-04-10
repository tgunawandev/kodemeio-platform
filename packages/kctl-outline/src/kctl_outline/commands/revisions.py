"""Revision history commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_outline.core.callbacks import AppContext

app = typer.Typer(help="Document revision history.")


@app.command("list")
def list_(
    ctx: typer.Context,
    document_id: Annotated[str, typer.Argument(help="Document ID")],
    offset: Annotated[int, typer.Option(help="Pagination offset")] = 0,
    limit: Annotated[int, typer.Option(help="Results per page")] = 25,
) -> None:
    """List revisions for a document."""
    c: AppContext = ctx.obj
    result = c.client.post(
        "documents.revisions",
        data={
            "id": document_id,
            "offset": offset,
            "limit": limit,
        },
    )
    revisions = result.get("data", [])
    pagination = result.get("pagination", {})

    rows = []
    for r in revisions:
        rid = r.get("id", "")[:8]
        version = str(r.get("version", ""))
        title = r.get("title", "")
        user = r.get("createdBy", {})
        author = user.get("name", "") if isinstance(user, dict) else ""
        created = (r.get("createdAt", "") or "")[:19]
        rows.append([rid, version, title, author, created])

    total = pagination.get("total", len(revisions))
    c.output.table(
        f"Revisions for {document_id[:8]} ({total} total)",
        [("ID", "cyan"), ("Version", "dim"), ("Title", "green"), ("Author", ""), ("Created", "dim")],
        rows,
        data_for_json=revisions,
    )


@app.command()
def restore(
    ctx: typer.Context,
    document_id: Annotated[str, typer.Argument(help="Document ID")],
    revision_id: Annotated[str, typer.Argument(help="Revision ID to restore")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Restore a document to a specific revision."""
    c: AppContext = ctx.obj

    if not force:
        if not typer.confirm(f"Restore document {document_id[:8]} to revision {revision_id[:8]}?"):
            raise typer.Abort()

    c.client.post(
        "documents.restore",
        data={
            "id": document_id,
            "revisionId": revision_id,
        },
    )
    c.output.success(f"Document {document_id[:8]} restored to revision {revision_id[:8]}")
