"""Search command -- global workspace search via POST /search."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_notion.core.callbacks import AppContext


def _extract_title(obj: dict) -> str:  # type: ignore[type-arg]
    """Extract a readable title from a Notion object."""
    props = obj.get("properties", {})
    # Try common title property patterns
    for key in ("title", "Title", "Name", "name"):
        prop = props.get(key)
        if prop and isinstance(prop, dict):
            title_parts = prop.get("title", [])
            if isinstance(title_parts, list) and title_parts:
                return "".join(t.get("plain_text", "") for t in title_parts)
    # Fallback: check all properties for title type
    for prop in props.values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            title_parts = prop.get("title", [])
            if isinstance(title_parts, list) and title_parts:
                return "".join(t.get("plain_text", "") for t in title_parts)
    return "(untitled)"


def search(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Search query text")],
    type: Annotated[str | None, typer.Option("--type", "-t", help="Filter: page or database")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 20,
) -> None:
    """Search across the Notion workspace."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        result = client.search(query=query, filter_type=type, page_size=limit)
        items = result.get("results", [])

        if out.json_mode:
            out.raw_json({"results": items, "count": len(items), "has_more": result.get("has_more", False)})
            return

        if not items:
            out.warn("No results found")
            return

        rows: list[list[str]] = []
        for item in items:
            obj_type = item.get("object", "unknown")
            obj_id = item.get("id", "")[:8]
            title = _extract_title(item)
            last_edited = item.get("last_edited_time", "")[:10]
            rows.append([obj_id, obj_type, title[:60], last_edited])

        out.table(
            f"Search results for '{query}' ({len(items)} found)",
            [("ID", "cyan"), ("Type", "green"), ("Title", "white"), ("Edited", "yellow")],
            rows,
        )
    finally:
        actx.close()
