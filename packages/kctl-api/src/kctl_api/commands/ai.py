"""AI platform commands for kctl-api.

Manage copilots, chat, conversations, and AI service health.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.exceptions import APIError, AuthenticationError
from kctl_api.core.exceptions import ConnectionError as KctlConnectionError

app = typer.Typer(name="ai", help="AI platform — copilots, chat, conversations.", no_args_is_help=True)

_BASE = "/api/v1/ai"


# ---------------------------------------------------------------------------
# copilots
# ---------------------------------------------------------------------------
@app.command()
def copilots(ctx: typer.Context) -> None:
    """List available AI copilots via GET /api/v1/ai/copilots."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        data = actx.ai_client.get(f"{_BASE}/copilots")
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    items = data if isinstance(data, list) else data.get("items", []) if isinstance(data, dict) else []

    rows: list[list[str]] = []
    for cp in items:
        rows.append(
            [
                str(cp.get("id", "")),
                cp.get("name", ""),
                cp.get("model", ""),
                cp.get("description", "")[:50],
                "[green]active[/green]" if cp.get("active", True) else "[dim]inactive[/dim]",
            ]
        )

    out.table(
        title="AI Copilots",
        columns=[
            ("ID", "bold"),
            ("Name", ""),
            ("Model", ""),
            ("Description", "dim"),
            ("Status", ""),
        ],
        rows=rows,
        data_for_json=items,
    )


# ---------------------------------------------------------------------------
# health
# ---------------------------------------------------------------------------
@app.command()
def health(ctx: typer.Context) -> None:
    """Check AI service health via GET /api/v1/ai/health."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        data = actx.ai_client.get(f"{_BASE}/health")
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    if not data:
        out.error("No health data from ai-main.")
        raise typer.Exit(1)

    status = data.get("status", "unknown")
    healthy = status == "ok"

    out.detail(
        title="AI Service Health",
        sections=[
            (
                "Status",
                [
                    ("Status", "[green]ok[/green]" if healthy else f"[red]{status}[/red]"),
                    *[(k, str(v)) for k, v in data.items() if k != "status"],
                ],
            ),
        ],
        data_for_json=data,
    )

    if not healthy:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# chat
# ---------------------------------------------------------------------------
@app.command()
def chat(
    ctx: typer.Context,
    message: Annotated[str, typer.Argument(help="Message to send to the copilot.")],
    copilot: Annotated[str, typer.Option("--copilot", "-c", help="Copilot ID or name.")] = "default",
    conversation_id: Annotated[
        str | None, typer.Option("--conversation", help="Existing conversation ID to continue.")
    ] = None,
) -> None:
    """Send a chat message to an AI copilot via POST /api/v1/ai/chat."""
    actx: AppContext = ctx.obj
    out = actx.output

    payload: dict = {"message": message, "copilot": copilot}
    if conversation_id:
        payload["conversation_id"] = conversation_id

    try:
        result = actx.ai_client.post(f"{_BASE}/chat", json=payload)
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    if actx.json_mode:
        out.raw_json(result)
    else:
        reply = result.get("reply", result.get("message", "")) if isinstance(result, dict) else str(result)
        out.text(reply)


# ---------------------------------------------------------------------------
# conversations
# ---------------------------------------------------------------------------
@app.command()
def conversations(
    ctx: typer.Context,
    page: Annotated[int, typer.Option("--page", "-p", help="Page number.")] = 1,
    per_page: Annotated[int, typer.Option("--per-page", "-n", help="Items per page.")] = 20,
) -> None:
    """List AI conversations via GET /api/v1/ai/conversations."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        data = actx.ai_client.get(f"{_BASE}/conversations", params={"page": page, "per_page": per_page})
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    items = data.get("items", []) if isinstance(data, dict) else []
    total = data.get("total", len(items)) if isinstance(data, dict) else len(items)

    rows: list[list[str]] = []
    for c in items:
        rows.append(
            [
                str(c.get("id", "")),
                c.get("copilot", ""),
                str(c.get("message_count", "")),
                str(c.get("created_at", "")),
            ]
        )

    out.table(
        title=f"AI Conversations (page {page}, {total} total)",
        columns=[
            ("ID", "bold"),
            ("Copilot", ""),
            ("Messages", ""),
            ("Created", "dim"),
        ],
        rows=rows,
        data_for_json=items,
    )


# ---------------------------------------------------------------------------
# conversation
# ---------------------------------------------------------------------------
@app.command()
def conversation(
    ctx: typer.Context,
    conversation_id: Annotated[str, typer.Argument(help="Conversation ID.")],
) -> None:
    """Get conversation details and messages via GET /api/v1/ai/conversations/{id}."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        data = actx.ai_client.get(f"{_BASE}/conversations/{conversation_id}")
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    if not data:
        out.error(f"Conversation not found: {conversation_id}")
        raise typer.Exit(1)

    out.detail(
        title=f"Conversation: {conversation_id}",
        sections=[
            ("Details", [(k, str(v)) for k, v in data.items() if k != "messages"]),
        ],
        data_for_json=data,
    )

    # Print messages if present
    messages = data.get("messages", [])
    if messages and not actx.json_mode:
        out.header("Messages")
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            out.text(f"  [{role}] {content}")


# ---------------------------------------------------------------------------
# delete-conversation
# ---------------------------------------------------------------------------
@app.command(name="delete-conversation")
def delete_conversation(
    ctx: typer.Context,
    conversation_id: Annotated[str, typer.Argument(help="Conversation ID to delete.")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation.")] = False,
) -> None:
    """Delete an AI conversation via DELETE /api/v1/ai/conversations/{id}."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not force:
        confirm = typer.confirm(f"Delete conversation {conversation_id}?", default=False)
        if not confirm:
            out.info("Cancelled.")
            raise typer.Exit(0)

    try:
        result = actx.ai_client.delete(f"{_BASE}/conversations/{conversation_id}")
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"Conversation {conversation_id} deleted.")
    if actx.json_mode:
        out.raw_json(result)
