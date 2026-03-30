"""Pages command group -- page management."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from kctl_notion.core.callbacks import AppContext

app = typer.Typer(help="Page management.")


def _extract_title(obj: dict[str, Any]) -> str:
    """Extract a readable title from a Notion page object."""
    props = obj.get("properties", {})
    for prop in props.values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            title_parts = prop.get("title", [])
            if isinstance(title_parts, list) and title_parts:
                return "".join(t.get("plain_text", "") for t in title_parts)
    return "(untitled)"


def _extract_parent_info(obj: dict[str, Any]) -> str:
    """Extract parent type and ID from a Notion page."""
    parent = obj.get("parent", {})
    parent_type = parent.get("type", "unknown")
    if parent_type == "database_id":
        return f"db:{parent.get('database_id', '')[:8]}"
    if parent_type == "page_id":
        return f"page:{parent.get('page_id', '')[:8]}"
    if parent_type == "workspace":
        return "workspace"
    return parent_type


@app.command("list")
def list_(
    ctx: typer.Context,
    parent: Annotated[str | None, typer.Option("--parent", help="Parent page/database ID")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 20,
) -> None:
    """List pages (recently edited). Uses search with page filter."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        if parent:
            # Query parent as database to list child pages
            result = client.query_database(parent, page_size=limit)
            pages = result.get("results", [])
        else:
            # Search for all pages
            result = client.search(filter_type="page", page_size=limit)
            pages = result.get("results", [])

        if out.json_mode:
            out.raw_json({"pages": pages, "count": len(pages)})
            return

        if not pages:
            out.warn("No pages found")
            return

        rows: list[list[str]] = []
        for page in pages:
            page_id = page.get("id", "")[:8]
            title = _extract_title(page)
            parent_info = _extract_parent_info(page)
            last_edited = page.get("last_edited_time", "")[:10]
            rows.append([page_id, title[:50], parent_info, last_edited])

        out.table(
            f"Pages ({len(pages)})",
            [("ID", "cyan"), ("Title", "white"), ("Parent", "green"), ("Edited", "yellow")],
            rows,
        )
    finally:
        actx.close()


@app.command()
def show(
    ctx: typer.Context,
    page_id: Annotated[str, typer.Argument(help="Page ID")],
) -> None:
    """Show page title, properties, and content preview."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        page = client.get_page(page_id)

        if out.json_mode:
            out.raw_json(page)
            return

        title = _extract_title(page)
        parent_info = _extract_parent_info(page)
        created = page.get("created_time", "")[:10]
        edited = page.get("last_edited_time", "")[:10]
        archived = page.get("archived", False)
        url = page.get("url", "")

        sections: list[tuple[str, list[tuple[str, str]]]] = [
            (
                "Page Info",
                [
                    ("ID", page.get("id", "")),
                    ("Title", title),
                    ("Parent", parent_info),
                    ("Created", created),
                    ("Last edited", edited),
                    ("Archived", str(archived)),
                    ("URL", url),
                ],
            ),
        ]

        # Show properties
        props = page.get("properties", {})
        if props:
            prop_fields: list[tuple[str, str]] = []
            for name, prop in props.items():
                prop_type = prop.get("type", "unknown")
                prop_fields.append((name, prop_type))
            sections.append(("Properties", prop_fields))

        # Fetch first few blocks for content preview
        try:
            blocks_result = client.get_block_children(page_id)
            blocks = blocks_result.get("results", [])[:5]
            if blocks:
                content_fields: list[tuple[str, str]] = []
                for i, block in enumerate(blocks):
                    block_type = block.get("type", "unknown")
                    text = _extract_block_text(block)
                    content_fields.append((f"Block {i + 1} ({block_type})", text[:80]))
                sections.append(("Content Preview", content_fields))
        except Exception:  # noqa: BLE001
            pass

        out.detail(f"Page: {title}", sections)
    finally:
        actx.close()


@app.command()
def create(
    ctx: typer.Context,
    parent: Annotated[str, typer.Option("--parent", help="Parent page or database ID")],
    title: Annotated[str, typer.Option("--title", help="Page title")],
    database: Annotated[bool, typer.Option("--database", help="Parent is a database (not a page)")] = False,
) -> None:
    """Create a new page under a parent page or database."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        parent_type = "database_id" if database else "page_id"
        result = client.create_page(parent, title, parent_type=parent_type)

        if out.json_mode:
            out.raw_json(result)
            return

        new_id = result.get("id", "")
        url = result.get("url", "")
        out.success(f"Page created: {new_id}")
        if url:
            out.kv("URL", url)
    finally:
        actx.close()


@app.command()
def update(
    ctx: typer.Context,
    page_id: Annotated[str, typer.Argument(help="Page ID")],
    title: Annotated[str | None, typer.Option("--title", help="New page title")] = None,
    archived: Annotated[bool | None, typer.Option("--archived/--no-archived", help="Archive or unarchive")] = None,
) -> None:
    """Update page properties (title, archived status)."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        payload: dict[str, Any] = {}
        if title is not None:
            payload["title"] = {"title": [{"text": {"content": title}}]}

        update_body: dict[str, Any] = {}
        if payload:
            update_body["properties"] = payload
        if archived is not None:
            update_body["archived"] = archived

        if not update_body:
            out.error("No changes specified. Use --title or --archived/--no-archived")
            raise typer.Exit(1)

        # Build the PATCH request manually for flexibility
        result = client.patch(f"/pages/{page_id}", json=update_body)

        if out.json_mode:
            out.raw_json(result)
            return

        out.success(f"Page {page_id[:8]} updated")
    finally:
        actx.close()


def _extract_block_text(block: dict[str, Any]) -> str:
    """Extract plain text from a block."""
    block_type = block.get("type", "")
    type_data = block.get(block_type, {})
    rich_text = type_data.get("rich_text", [])
    if isinstance(rich_text, list):
        return "".join(t.get("plain_text", "") for t in rich_text)
    return ""
