"""Template management commands."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from kctl_outline.core.callbacks import AppContext

app = typer.Typer(help="Template management.")


@app.command("list")
def list_(
    ctx: typer.Context,
    offset: Annotated[int, typer.Option(help="Pagination offset")] = 0,
    limit: Annotated[int, typer.Option(help="Results per page")] = 25,
) -> None:
    """List document templates."""
    c: AppContext = ctx.obj
    result = c.client.post(
        "documents.list",
        data={
            "template": True,
            "offset": offset,
            "limit": limit,
        },
    )
    templates = result.get("data", [])
    pagination = result.get("pagination", {})

    rows = []
    for t in templates:
        tid = t.get("id", "")[:8]
        title = t.get("title", "")
        collection = (t.get("collectionId") or "")[:8]
        rev = str(t.get("revision", ""))
        updated = (t.get("updatedAt") or "")[:10]
        rows.append([tid, title, collection, rev, updated])

    total = pagination.get("total", len(templates))
    c.output.table(
        f"Templates ({total} total)",
        [("ID", "cyan"), ("Title", "green"), ("Collection", ""), ("Rev", "dim"), ("Updated", "dim")],
        rows,
        data_for_json=templates,
    )


@app.command()
def create(
    ctx: typer.Context,
    title: Annotated[str, typer.Argument(help="Template title")],
    collection_id: Annotated[str, typer.Option("--collection", "-c", help="Collection ID")] = "",
    text: Annotated[str, typer.Option("--text", "-t", help="Template body (Markdown)")] = "",
    publish: Annotated[bool, typer.Option("--publish", help="Publish immediately")] = True,
) -> None:
    """Create a new template."""
    c: AppContext = ctx.obj
    data: dict = {
        "title": title,
        "text": text or " ",
        "template": True,
        "publish": publish,
    }
    if collection_id:
        data["collectionId"] = collection_id

    result = c.client.post("documents.create", data=data)
    doc = result.get("data", {})

    c.output.detail(
        "Template Created",
        [
            (
                "Details",
                [
                    ("ID", doc.get("id", "")),
                    ("Title", doc.get("title", "")),
                    ("Collection", doc.get("collectionId", "")),
                    ("Published", str(bool(doc.get("publishedAt")))),
                ],
            )
        ],
        data_for_json=doc,
    )


@app.command()
def delete(
    ctx: typer.Context,
    template_id: Annotated[str, typer.Argument(help="Template (document) ID")],
    permanent: Annotated[bool, typer.Option("--permanent", help="Permanently delete")] = False,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a template."""
    c: AppContext = ctx.obj

    if not force:
        info = c.client.post("documents.info", data={"id": template_id})
        doc = info.get("data", {})
        if not typer.confirm(f"Delete template '{doc.get('title', template_id)}'?"):
            raise typer.Abort()

    c.client.post("documents.delete", data={"id": template_id, "permanent": permanent})
    c.output.success(f"Template {template_id} deleted")
