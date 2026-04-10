"""Top-level search command."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from kctl_outline.core.callbacks import AppContext


def search_command(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Search query")],
    collection: Annotated[Optional[str], typer.Option("--collection", "-c", help="Filter by collection ID")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 25,
) -> None:
    """Search across all documents."""
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
