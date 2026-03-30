"""Tenant AI commands for kctl-api.

Per-tenant AI chat, streaming, history, and usage tracking.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.exceptions import APIError, AuthenticationError
from kctl_api.core.exceptions import ConnectionError as KctlConnectionError

app = typer.Typer(name="tenant-ai", help="Tenant AI — chat, stream, history, usage.", no_args_is_help=True)

_BASE = "/api/v1/tenant-ai"


# ---------------------------------------------------------------------------
# chat
# ---------------------------------------------------------------------------
@app.command()
def chat(
    ctx: typer.Context,
    message: Annotated[str, typer.Argument(help="Message to send.")],
    tenant_id: Annotated[str | None, typer.Option("--tenant", "-t", help="Tenant ID.")] = None,
) -> None:
    """Send a chat message to the tenant AI via POST /api/v1/tenant-ai/chat."""
    actx: AppContext = ctx.obj
    out = actx.output

    payload: dict = {"message": message}
    if tenant_id:
        payload["tenant_id"] = tenant_id

    try:
        result = actx.client.post(f"{_BASE}/chat", json=payload)
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    if actx.json_mode:
        out.raw_json(result)
    else:
        reply = result.get("reply", result.get("message", "")) if isinstance(result, dict) else str(result)
        out.text(reply)


# ---------------------------------------------------------------------------
# stream
# ---------------------------------------------------------------------------
@app.command()
def stream(
    ctx: typer.Context,
    message: Annotated[str, typer.Argument(help="Message to send.")],
    tenant_id: Annotated[str | None, typer.Option("--tenant", "-t", help="Tenant ID.")] = None,
) -> None:
    """Stream a chat response from the tenant AI via POST /api/v1/tenant-ai/chat/stream.

    Note: Currently sends a blocking request. True SSE streaming will be added in a future version.
    """
    actx: AppContext = ctx.obj
    out = actx.output

    payload: dict = {"message": message}
    if tenant_id:
        payload["tenant_id"] = tenant_id

    try:
        result = actx.client.post(f"{_BASE}/chat/stream", json=payload)
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    if actx.json_mode:
        out.raw_json(result)
    else:
        reply = result.get("reply", result.get("message", "")) if isinstance(result, dict) else str(result)
        out.text(reply)


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------
@app.command()
def history(
    ctx: typer.Context,
    tenant_id: Annotated[str | None, typer.Option("--tenant", "-t", help="Tenant ID.")] = None,
    page: Annotated[int, typer.Option("--page", "-p", help="Page number.")] = 1,
    per_page: Annotated[int, typer.Option("--per-page", "-n", help="Items per page.")] = 20,
) -> None:
    """List tenant AI conversation history via GET /api/v1/tenant-ai/history."""
    actx: AppContext = ctx.obj
    out = actx.output

    params: dict[str, str | int] = {"page": page, "per_page": per_page}
    if tenant_id:
        params["tenant_id"] = tenant_id

    try:
        data = actx.client.get(f"{_BASE}/history", params=params)
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    items = data.get("items", []) if isinstance(data, dict) else []
    total = data.get("total", len(items)) if isinstance(data, dict) else len(items)

    rows: list[list[str]] = []
    for h in items:
        rows.append(
            [
                str(h.get("id", "")),
                h.get("tenant_id", ""),
                str(h.get("message_count", "")),
                str(h.get("tokens_used", "")),
                str(h.get("created_at", "")),
            ]
        )

    out.table(
        title=f"Tenant AI History (page {page}, {total} total)",
        columns=[
            ("ID", "bold"),
            ("Tenant", ""),
            ("Messages", ""),
            ("Tokens", ""),
            ("Created", "dim"),
        ],
        rows=rows,
        data_for_json=items,
    )


# ---------------------------------------------------------------------------
# usage
# ---------------------------------------------------------------------------
@app.command()
def usage(
    ctx: typer.Context,
    tenant_id: Annotated[str | None, typer.Option("--tenant", "-t", help="Tenant ID.")] = None,
) -> None:
    """Get tenant AI usage statistics via GET /api/v1/tenant-ai/usage."""
    actx: AppContext = ctx.obj
    out = actx.output

    params: dict[str, str] = {}
    if tenant_id:
        params["tenant_id"] = tenant_id

    try:
        data = actx.client.get(f"{_BASE}/usage", params=params)
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    if not data:
        out.info("No usage data available.")
        return

    out.detail(
        title="Tenant AI Usage",
        sections=[
            ("Usage", [(k, str(v)) for k, v in data.items()]),
        ],
        data_for_json=data,
    )
