"""Chatwoot integration commands.

Manage Chatwoot inbox connections for Telegram bots.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_telegram.core.callbacks import AppContext

app = typer.Typer(help="Manage Chatwoot integrations.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List Chatwoot inboxes linked to Telegram bots."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    data = c.get("chatwoot/inboxes")
    inboxes = data.get("results", []) if isinstance(data, dict) else data if isinstance(data, list) else []

    if not inboxes:
        out.warn("No Chatwoot inboxes found.")
        return

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for inbox in inboxes:
        inbox_id = str(inbox.get("id", ""))
        bot_id = str(inbox.get("bot_id", ""))
        identifier = inbox.get("inbox_identifier", "")
        base_url = inbox.get("base_url", "")

        rows.append([inbox_id, bot_id, identifier, base_url])
        json_data.append(inbox)

    out.table(
        "Chatwoot Inboxes",
        [("ID", "cyan"), ("Bot ID", ""), ("Inbox Identifier", ""), ("Chatwoot URL", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def add(
    ctx: typer.Context,
    bot_id: Annotated[int, typer.Option("--bot-id", help="Telegram bot ID.")],
    inbox_identifier: Annotated[str, typer.Option("--inbox-identifier", help="Chatwoot inbox identifier.")],
    base_url: Annotated[str, typer.Option("--base-url", help="Chatwoot instance base URL.")],
    api_token: Annotated[str, typer.Option("--api-token", help="Chatwoot API token.")],
) -> None:
    """Link a Chatwoot inbox to a Telegram bot."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    payload: dict = {
        "bot_id": bot_id,
        "inbox_identifier": inbox_identifier,
        "base_url": base_url,
        "api_token": api_token,
    }

    result = c.post("chatwoot/inboxes", json=payload)

    out.success("Chatwoot inbox linked")
    out.kv("ID", str(result.get("id", "")))
    out.kv("Bot ID", str(bot_id))
    out.kv("Inbox", inbox_identifier)
    out.kv("Chatwoot URL", base_url)

    if actx.output.json_mode:
        out.raw_json(result)


@app.command()
def remove(
    ctx: typer.Context,
    inbox_id: Annotated[int, typer.Argument(help="Chatwoot inbox ID to remove")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Remove a Chatwoot inbox integration."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not force:
        try:
            inbox = c.get(f"chatwoot/inboxes/{inbox_id}")
            identifier = inbox.get("inbox_identifier", str(inbox_id))
        except Exception:
            identifier = str(inbox_id)

        if not typer.confirm(f"Remove Chatwoot inbox '{identifier}' (ID: {inbox_id})?"):
            raise typer.Exit(0)

    c.delete(f"chatwoot/inboxes/{inbox_id}")
    out.success(f"Chatwoot inbox {inbox_id} removed")
