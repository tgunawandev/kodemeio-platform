"""Comment management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_outline.core.callbacks import AppContext

app = typer.Typer(help="Comment management.")


@app.command("list")
def list_(
    ctx: typer.Context,
    document_id: Annotated[str, typer.Argument(help="Document ID")],
) -> None:
    """List comments on a document."""
    c: AppContext = ctx.obj
    result = c.client.post("comments.list", data={"documentId": document_id})
    comments = result.get("data", [])

    rows = [
        [
            cm.get("id", "")[:8],
            cm.get("createdBy", {}).get("name", ""),
            (cm.get("data", {}).get("text", "") if isinstance(cm.get("data"), dict) else str(cm.get("data", "")))[:60],
            (cm.get("createdAt") or "")[:10],
        ]
        for cm in comments
    ]

    c.output.table(
        f"Comments ({len(comments)})",
        [("ID", "cyan"), ("Author", "green"), ("Text", ""), ("Created", "dim")],
        rows,
        data_for_json=comments,
    )


@app.command()
def create(
    ctx: typer.Context,
    document_id: Annotated[str, typer.Argument(help="Document ID")],
    text: Annotated[str, typer.Argument(help="Comment text (Markdown)")],
) -> None:
    """Add a comment to a document."""
    c: AppContext = ctx.obj
    result = c.client.post(
        "comments.create",
        data={
            "documentId": document_id,
            "data": {"text": text},
        },
    )
    comment = result.get("data", {})
    c.output.success(f"Comment created (ID: {comment.get('id', '')[:8]})")


@app.command()
def delete(
    ctx: typer.Context,
    comment_id: Annotated[str, typer.Argument(help="Comment ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a comment."""
    c: AppContext = ctx.obj

    if not force and not typer.confirm(f"Delete comment {comment_id}?"):
        raise typer.Abort()

    c.client.post("comments.delete", data={"id": comment_id})
    c.output.success(f"Comment {comment_id} deleted")
