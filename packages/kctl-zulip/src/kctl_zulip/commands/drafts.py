"""Drafts management commands."""

from __future__ import annotations

import json
from typing import Annotated, Optional

import typer

from kctl_zulip.core.callbacks import AppContext

app = typer.Typer(help="Draft management.")


@app.command("list")
def list_(
    ctx: typer.Context,
) -> None:
    """List drafts."""
    c: AppContext = ctx.obj
    data = c.client.get("drafts")
    drafts = data.get("drafts", [])

    rows = []
    for d in drafts:
        did = str(d.get("id", ""))
        dtype = d.get("type", "")
        to = str(d.get("to", ""))[:30]
        topic = d.get("topic", "") or ""
        content = (d.get("content", "") or "")[:50]
        timestamp = str(d.get("timestamp", ""))
        rows.append([did, dtype, to, topic, content, timestamp])

    c.output.table(
        f"Drafts ({len(drafts)})",
        [("ID", "cyan"), ("Type", ""), ("To", "green"), ("Topic", ""), ("Content", ""), ("Timestamp", "dim")],
        rows,
        data_for_json=drafts,
    )


@app.command()
def create(
    ctx: typer.Context,
    content: Annotated[str, typer.Option("--content", "-c", help="Draft content")],
    to: Annotated[str, typer.Option("--to", help="Stream name or comma-separated user IDs")],
    topic: Annotated[Optional[str], typer.Option("--topic", "-t", help="Topic (for stream drafts)")] = None,
    draft_type: Annotated[str, typer.Option("--type", help="Draft type: stream or private")] = "stream",
) -> None:
    """Create a draft."""
    c: AppContext = ctx.obj

    draft: dict = {
        "type": draft_type,
        "content": content,
    }

    if draft_type == "stream":
        draft["to"] = [to]
        if topic:
            draft["topic"] = topic
    else:
        recipients = []
        for r in to.split(","):
            r = r.strip()
            try:
                recipients.append(int(r))
            except ValueError:
                recipients.append(r)
        draft["to"] = recipients

    result = c.client.post("drafts", data={"drafts": json.dumps([draft])})
    ids = result.get("ids", [])
    draft_id = ids[0] if ids else "unknown"
    c.output.success(f"Draft created (ID: {draft_id})")


@app.command()
def update(
    ctx: typer.Context,
    draft_id: Annotated[int, typer.Argument(help="Draft ID")],
    content: Annotated[Optional[str], typer.Option("--content", "-c", help="New content")] = None,
    topic: Annotated[Optional[str], typer.Option("--topic", "-t", help="New topic")] = None,
) -> None:
    """Update a draft."""
    c: AppContext = ctx.obj

    payload: dict = {}
    if content is not None:
        payload["content"] = content
    if topic is not None:
        payload["topic"] = topic

    if not payload:
        c.output.warn("No fields to update")
        return

    c.client.patch(f"drafts/{draft_id}", data=payload)
    c.output.success(f"Draft {draft_id} updated")


@app.command()
def delete(
    ctx: typer.Context,
    draft_id: Annotated[int, typer.Argument(help="Draft ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a draft."""
    c: AppContext = ctx.obj

    if not force:
        if not typer.confirm(f"Delete draft {draft_id}?"):
            raise typer.Abort()

    c.client.delete(f"drafts/{draft_id}")
    c.output.success(f"Draft {draft_id} deleted")
