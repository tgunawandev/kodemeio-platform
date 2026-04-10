"""Stars/bookmarks management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_outline.core.callbacks import AppContext

app = typer.Typer(help="Star/bookmark management.")


@app.command("list")
def list_(
    ctx: typer.Context,
) -> None:
    """List starred documents."""
    c: AppContext = ctx.obj
    result = c.client.post("stars.list")
    stars = result.get("data", [])

    rows = []
    for s in stars:
        sid = str(s.get("id", ""))[:8]
        doc_id = str(s.get("documentId", ""))[:8]
        # Star may embed document details
        doc = s.get("document", {})
        title = doc.get("title", "") if isinstance(doc, dict) else ""
        created = (s.get("createdAt", "") or "")[:10]
        rows.append([sid, doc_id, title, created])

    c.output.table(
        f"Stars ({len(stars)})",
        [("Star ID", "cyan"), ("Doc ID", "green"), ("Title", ""), ("Starred At", "dim")],
        rows,
        data_for_json=stars,
    )


@app.command()
def add(
    ctx: typer.Context,
    document_id: Annotated[str, typer.Argument(help="Document ID to star")],
) -> None:
    """Star a document."""
    c: AppContext = ctx.obj
    result = c.client.post("stars.create", data={"documentId": document_id})
    star = result.get("data", {})
    c.output.success(f"Document starred: {document_id[:8]}")
    c.output.kv("Star ID", str(star.get("id", "")))


@app.command()
def remove(
    ctx: typer.Context,
    document_id: Annotated[str, typer.Argument(help="Document ID to unstar")],
) -> None:
    """Remove a star from a document."""
    c: AppContext = ctx.obj
    c.client.post("stars.delete", data={"documentId": document_id})
    c.output.success(f"Star removed from document: {document_id[:8]}")
