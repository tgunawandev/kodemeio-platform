"""Document management commands."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from kctl_outline.core.callbacks import AppContext

app = typer.Typer(help="Document management.")


@app.command("list")
def list_(
    ctx: typer.Context,
    collection: Annotated[Optional[str], typer.Option("--collection", "-c", help="Filter by collection ID")] = None,
    offset: Annotated[int, typer.Option(help="Pagination offset")] = 0,
    limit: Annotated[int, typer.Option(help="Results per page")] = 25,
) -> None:
    """List documents."""
    c: AppContext = ctx.obj
    params: dict = {"offset": offset, "limit": limit}
    if collection:
        params["collectionId"] = collection

    result = c.client.post("documents.list", data=params)
    docs = result.get("data", [])
    pagination = result.get("pagination", {})

    rows = [
        [
            d.get("id", "")[:8],
            d.get("title", ""),
            (d.get("collectionId") or "")[:8],
            str(d.get("revision", "")),
            "yes" if d.get("publishedAt") else "draft",
            (d.get("updatedAt") or "")[:10],
        ]
        for d in docs
    ]

    total = pagination.get("total", len(docs))
    c.output.table(
        f"Documents ({total} total)",
        [("ID", "cyan"), ("Title", "green"), ("Collection", ""), ("Rev", "dim"), ("Status", ""), ("Updated", "dim")],
        rows,
        data_for_json=docs,
    )


@app.command()
def get(
    ctx: typer.Context,
    doc_id: Annotated[str, typer.Argument(help="Document ID")],
) -> None:
    """Get document details."""
    c: AppContext = ctx.obj
    result = c.client.post("documents.info", data={"id": doc_id})
    doc = result.get("data", {})

    c.output.detail(
        f"Document: {doc.get('title', '')}",
        [
            ("Details", [
                ("ID", doc.get("id", "")),
                ("Title", doc.get("title", "")),
                ("Collection", doc.get("collectionId", "")),
                ("Revision", str(doc.get("revision", ""))),
                ("Template", str(doc.get("template", False))),
                ("Archived", str(doc.get("archivedAt") is not None)),
            ]),
            ("Dates", [
                ("Created", doc.get("createdAt", "")),
                ("Updated", doc.get("updatedAt", "")),
                ("Published", doc.get("publishedAt", "") or "draft"),
            ]),
            ("Author", [
                ("Created by", doc.get("createdBy", {}).get("name", "")),
                ("Updated by", doc.get("updatedBy", {}).get("name", "")),
            ]),
        ],
        data_for_json=doc,
    )


@app.command()
def create(
    ctx: typer.Context,
    title: Annotated[str, typer.Argument(help="Document title")],
    collection_id: Annotated[str, typer.Option("--collection", "-c", help="Collection ID")] = "",
    text: Annotated[str, typer.Option("--text", "-t", help="Document body (Markdown)")] = "",
    publish: Annotated[bool, typer.Option("--publish", help="Publish immediately")] = True,
    parent_id: Annotated[Optional[str], typer.Option("--parent", help="Parent document ID")] = None,
    template: Annotated[bool, typer.Option("--template", help="Create as template")] = False,
) -> None:
    """Create a new document."""
    c: AppContext = ctx.obj
    data: dict = {
        "title": title,
        "text": text or " ",
        "publish": publish,
        "template": template,
    }
    if collection_id:
        data["collectionId"] = collection_id
    if parent_id:
        data["parentDocumentId"] = parent_id

    result = c.client.post("documents.create", data=data)
    doc = result.get("data", {})

    c.output.detail(
        "Document Created",
        [("Details", [
            ("ID", doc.get("id", "")),
            ("Title", doc.get("title", "")),
            ("Collection", doc.get("collectionId", "")),
            ("Published", str(bool(doc.get("publishedAt")))),
        ])],
        data_for_json=doc,
    )


@app.command()
def update(
    ctx: typer.Context,
    doc_id: Annotated[str, typer.Argument(help="Document ID")],
    title: Annotated[Optional[str], typer.Option("--title", help="New title")] = None,
    text: Annotated[Optional[str], typer.Option("--text", help="New body (Markdown)")] = None,
    append: Annotated[bool, typer.Option("--append", help="Append text instead of replace")] = False,
    done: Annotated[bool, typer.Option("--done", help="Mark as done")] = False,
) -> None:
    """Update a document."""
    c: AppContext = ctx.obj
    data: dict = {"id": doc_id}

    if title:
        data["title"] = title
    if text:
        if append:
            data["append"] = True
            data["text"] = text
        else:
            data["text"] = text
    if done:
        data["done"] = True

    result = c.client.post("documents.update", data=data)
    doc = result.get("data", {})
    c.output.success(f"Document updated: {doc.get('title', doc_id)}")


@app.command()
def delete(
    ctx: typer.Context,
    doc_id: Annotated[str, typer.Argument(help="Document ID")],
    permanent: Annotated[bool, typer.Option("--permanent", help="Permanently delete")] = False,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a document."""
    c: AppContext = ctx.obj

    if not force:
        info = c.client.post("documents.info", data={"id": doc_id})
        doc = info.get("data", {})
        if not typer.confirm(f"Delete document '{doc.get('title', doc_id)}'?"):
            raise typer.Abort()

    c.client.post("documents.delete", data={"id": doc_id, "permanent": permanent})
    c.output.success(f"Document {doc_id} deleted")


@app.command()
def search(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Search query")],
    collection: Annotated[Optional[str], typer.Option("--collection", "-c", help="Filter by collection ID")] = None,
    limit: Annotated[int, typer.Option(help="Max results")] = 25,
) -> None:
    """Search documents."""
    c: AppContext = ctx.obj
    data: dict = {"query": query, "limit": limit}
    if collection:
        data["collectionId"] = collection

    result = c.client.post("documents.search", data=data)
    docs = result.get("data", [])

    rows = [
        [
            d.get("document", {}).get("id", "")[:8],
            d.get("document", {}).get("title", ""),
            (d.get("document", {}).get("collectionId") or "")[:8],
            str(round(d.get("ranking", 0), 2)),
            d.get("context", "")[:60],
        ]
        for d in docs
    ]

    c.output.table(
        f"Search: '{query}' ({len(docs)} results)",
        [("ID", "cyan"), ("Title", "green"), ("Collection", ""), ("Score", "dim"), ("Context", "dim")],
        rows,
        data_for_json=docs,
    )


@app.command("export")
def export_(
    ctx: typer.Context,
    doc_id: Annotated[str, typer.Argument(help="Document ID")],
) -> None:
    """Export a document as Markdown."""
    c: AppContext = ctx.obj
    result = c.client.post("documents.info", data={"id": doc_id})
    doc = result.get("data", {})

    if c.output.json_mode:
        c.output.raw_json(doc)
    else:
        title = doc.get("title", "")
        text = doc.get("text", "")
        c.output.text(f"# {title}\n\n{text}")


@app.command()
def move(
    ctx: typer.Context,
    doc_id: Annotated[str, typer.Argument(help="Document ID")],
    collection_id: Annotated[str, typer.Option("--collection", "-c", help="Target collection ID")] = "",
    parent_id: Annotated[Optional[str], typer.Option("--parent", help="Target parent document ID")] = None,
) -> None:
    """Move a document to another collection or parent."""
    c: AppContext = ctx.obj
    data: dict = {"id": doc_id}
    if collection_id:
        data["collectionId"] = collection_id
    if parent_id:
        data["parentDocumentId"] = parent_id

    c.client.post("documents.move", data=data)
    c.output.success(f"Document {doc_id} moved")


@app.command()
def archive(
    ctx: typer.Context,
    doc_id: Annotated[str, typer.Argument(help="Document ID")],
) -> None:
    """Archive a document."""
    c: AppContext = ctx.obj
    c.client.post("documents.archive", data={"id": doc_id})
    c.output.success(f"Document {doc_id} archived")


@app.command()
def unarchive(
    ctx: typer.Context,
    doc_id: Annotated[str, typer.Argument(help="Document ID")],
) -> None:
    """Unarchive a document."""
    c: AppContext = ctx.obj
    c.client.post("documents.unarchive", data={"id": doc_id})
    c.output.success(f"Document {doc_id} unarchived")
