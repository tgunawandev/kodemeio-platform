"""Health check command -- verify Notion API connectivity."""

from __future__ import annotations

import typer

from kctl_notion.core.callbacks import AppContext

app = typer.Typer(help="API health check.")


@app.callback(invoke_without_command=True)
def health(ctx: typer.Context) -> None:
    """Check Notion API reachability and accessible pages count."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        me = client.get_me()
        # Search with empty query to count accessible pages
        search_result = client.search(page_size=1)
        total_hint = len(search_result.get("results", []))
        has_more = search_result.get("has_more", False)

        bot_name = me.get("name", "Unknown")
        bot_type = me.get("type", "unknown")
        workspace = me.get("bot", {}).get("workspace_name", "Unknown") if me.get("bot") else "N/A"

        if out.json_mode:
            out.raw_json(
                {
                    "status": "healthy",
                    "bot_name": bot_name,
                    "bot_type": bot_type,
                    "workspace": workspace,
                    "has_accessible_content": total_hint > 0 or has_more,
                }
            )
            return

        out.success("Notion API is reachable")
        out.kv("Bot name", bot_name)
        out.kv("Type", bot_type)
        out.kv("Workspace", workspace)
        out.kv("Accessible content", "Yes" if (total_hint > 0 or has_more) else "None found")
    finally:
        actx.close()
