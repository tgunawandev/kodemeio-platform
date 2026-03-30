"""Blocks command group -- content block management."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from kctl_notion.core.callbacks import AppContext

app = typer.Typer(help="Content block management.")


def _extract_block_text(block: dict[str, Any]) -> str:
    """Extract plain text from a block's rich_text content."""
    block_type = block.get("type", "")
    type_data = block.get(block_type, {})
    rich_text = type_data.get("rich_text", [])
    if isinstance(rich_text, list):
        return "".join(t.get("plain_text", "") for t in rich_text)
    return ""


def _format_block_summary(block: dict[str, Any]) -> str:
    """Format a block into a one-line summary."""
    block_type = block.get("type", "")
    text = _extract_block_text(block)
    if text:
        return text[:80]
    if block_type in ("image", "file", "pdf"):
        type_data = block.get(block_type, {})
        file_data = type_data.get("file", type_data.get("external", {}))
        return file_data.get("url", "(media)")[:60] if file_data else "(media)"
    if block_type == "child_page":
        return block.get("child_page", {}).get("title", "(child page)")
    if block_type == "child_database":
        return block.get("child_database", {}).get("title", "(child database)")
    if block_type == "divider":
        return "---"
    if block_type == "table_of_contents":
        return "(table of contents)"
    return f"({block_type})"


@app.command("list")
def list_(
    ctx: typer.Context,
    page_id: Annotated[str, typer.Argument(help="Page or block ID to list children of")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max blocks to show")] = 50,
) -> None:
    """List blocks in a page."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        all_blocks: list[dict[str, Any]] = []
        cursor: str | None = None

        while len(all_blocks) < limit:
            result = client.get_block_children(page_id, start_cursor=cursor)
            blocks = result.get("results", [])
            all_blocks.extend(blocks)
            if not result.get("has_more"):
                break
            cursor = result.get("next_cursor")
            if not cursor:
                break

        all_blocks = all_blocks[:limit]

        if out.json_mode:
            out.raw_json({"blocks": all_blocks, "count": len(all_blocks)})
            return

        if not all_blocks:
            out.warn("No blocks found")
            return

        rows: list[list[str]] = []
        for i, block in enumerate(all_blocks):
            block_id = block.get("id", "")[:8]
            block_type = block.get("type", "unknown")
            has_children = "+" if block.get("has_children") else ""
            summary = _format_block_summary(block)
            rows.append([str(i + 1), block_id, block_type, has_children, summary[:60]])

        out.table(
            f"Blocks ({len(all_blocks)})",
            [("#", "dim"), ("ID", "cyan"), ("Type", "green"), ("Children", "yellow"), ("Content", "white")],
            rows,
        )
    finally:
        actx.close()


@app.command()
def append(
    ctx: typer.Context,
    page_id: Annotated[str, typer.Argument(help="Page ID to append to")],
    text: Annotated[str, typer.Option("--text", "-t", help="Paragraph text to add")],
    block_type: Annotated[
        str,
        typer.Option(
            "--type",
            help="Block type: paragraph, heading_1, heading_2, heading_3, "
            "bulleted_list_item, numbered_list_item, to_do, quote, callout, divider",
        ),
    ] = "paragraph",
) -> None:
    """Append a text block to a page."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        if block_type == "divider":
            children = [{"object": "block", "type": "divider", "divider": {}}]
        else:
            children = [
                {
                    "object": "block",
                    "type": block_type,
                    block_type: {
                        "rich_text": [{"type": "text", "text": {"content": text}}],
                    },
                }
            ]

        result = client.append_block_children(page_id, children)

        if out.json_mode:
            out.raw_json(result)
            return

        out.success(f"Appended {block_type} block to page {page_id[:8]}")
    finally:
        actx.close()
