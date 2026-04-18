"""Event (activity feed) commands."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

import typer

from kctl_outline.core.callbacks import AppContext

app = typer.Typer(help="Activity feed / event log.")


@app.command("list")
def list_(
    ctx: typer.Context,
    offset: Annotated[int, typer.Option(help="Pagination offset")] = 0,
    limit: Annotated[int, typer.Option(help="Results per page")] = 25,
    name: Annotated[str | None, typer.Option("--name", help="Filter by event name (e.g. documents.create)")] = None,
    collection_id: Annotated[str | None, typer.Option("--collection", "-c", help="Filter by collection ID")] = None,
    document_id: Annotated[str | None, typer.Option("--document", "-d", help="Filter by document ID")] = None,
) -> None:
    """List recent events (activity feed)."""
    c: AppContext = ctx.obj
    data: dict = {"offset": offset, "limit": limit}
    if name:
        data["name"] = name
    if collection_id:
        data["collectionId"] = collection_id
    if document_id:
        data["documentId"] = document_id

    result = c.client.post("events.list", data=data)
    events = result.get("data", [])

    rows = [
        [
            e.get("id", "")[:8],
            e.get("name", ""),
            e.get("actorId", "")[:8],
            _format_date(e.get("createdAt", "")),
            _event_context(e),
        ]
        for e in events
    ]

    c.output.table(
        f"Events ({len(events)})",
        [("ID", "cyan"), ("Event", "green"), ("Actor", ""), ("Date", "dim"), ("Context", "dim")],
        rows,
        data_for_json=events,
    )


def _format_date(dt_str: str) -> str:
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return dt_str[:16]


def _event_context(event: dict) -> str:
    data = event.get("data", {})
    if isinstance(data, dict):
        title = data.get("title", data.get("name", ""))
        if title:
            return str(title)[:40]
    doc_id = event.get("documentId", "")
    if doc_id:
        return f"doc:{doc_id[:8]}"
    collection_id = event.get("collectionId", "")
    if collection_id:
        return f"col:{collection_id[:8]}"
    return ""
