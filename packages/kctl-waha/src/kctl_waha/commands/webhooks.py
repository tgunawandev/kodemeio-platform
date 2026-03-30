"""Webhook management commands.

View and configure webhooks for WhatsApp sessions.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_waha.core.callbacks import AppContext
from kctl_waha.core.exceptions import KctlError

app = typer.Typer(help="Manage session webhooks.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List webhook configurations for all sessions."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        raw = c.get("sessions/", params={"all": "true"})
    except KctlError as e:
        out.error(f"Failed to list sessions: {e}")
        raise typer.Exit(1) from e

    sessions = raw if isinstance(raw, list) else []

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for s in sessions:
        name = s.get("name", "unknown")
        config = s.get("config", {})
        webhooks = config.get("webhooks", [])

        if not webhooks:
            rows.append([name, "[dim]none[/dim]", "[dim]-[/dim]", "[dim]-[/dim]"])
            json_data.append(
                {
                    "session": name,
                    "webhook_url": None,
                    "events": [],
                    "hmac": False,
                }
            )
            continue

        for wh in webhooks:
            wh_url = wh.get("url", "")
            events = wh.get("events", [])
            events_str = ", ".join(events) if events else "[dim]all[/dim]"
            hmac = "[green]yes[/green]" if wh.get("hmac") else "[dim]no[/dim]"

            rows.append([name, wh_url, events_str, hmac])
            json_data.append(
                {
                    "session": name,
                    "webhook_url": wh_url,
                    "events": events,
                    "hmac": bool(wh.get("hmac")),
                }
            )

    out.table(
        f"Webhooks ({len(rows)})",
        [("Session", "cyan"), ("URL", ""), ("Events", "dim"), ("HMAC", "")],
        rows,
        data_for_json=json_data,
    )


@app.command("set")
def set_(
    ctx: typer.Context,
    session: Annotated[str, typer.Argument(help="Session name.")],
    url: Annotated[str, typer.Option("--url", help="Webhook URL.")],
    events: Annotated[
        str | None,
        typer.Option("--events", help="Comma-separated events (e.g. message,message.ack,session.status)."),
    ] = None,
    hmac_key: Annotated[str | None, typer.Option("--hmac-key", help="HMAC secret for webhook signature.")] = None,
) -> None:
    """Set webhook configuration for a session.

    Examples:
      kctl-waha webhooks set default --url https://bridge.kodeme.io/webhook
      kctl-waha webhooks set default --url https://n8n.kodeme.io/waha --events message,session.status
      kctl-waha webhooks set default --url https://hook.io/waha --hmac-key mysecret
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    webhook_config: dict = {"url": url}
    if events:
        webhook_config["events"] = [e.strip() for e in events.split(",")]
    if hmac_key:
        webhook_config["hmac"] = {"key": hmac_key}

    try:
        c.put(
            f"sessions/{session}",
            data={
                "config": {
                    "webhooks": [webhook_config],
                },
            },
        )
    except KctlError as e:
        out.error(f"Failed to set webhook for session '{session}': {e}")
        raise typer.Exit(1) from e

    out.success(f"Webhook configured for session '{session}'")
    out.kv("URL", url)
    if events:
        out.kv("Events", events)
    if hmac_key:
        out.kv("HMAC", "enabled")
