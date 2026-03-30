"""Integration commands (webhooks, OAuth, bus, SMTP)."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext

app = typer.Typer(help="Integration & connectivity operations.")


@app.command("webhooks")
def webhook_list(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List webhook-type automated actions."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # base.automation with webhook-related triggers
    webhook_triggers = ["on_webhook", "on_webhook_once"]

    try:
        records = c.search_read(
            "base.automation",
            domain=[("trigger", "in", webhook_triggers)],
            fields=["id", "name", "trigger", "model_id", "active", "url", "webhook_uuid", "create_date", "write_date"],
            limit=limit,
            order="name",
        )
    except Exception:
        # Fallback: try without webhook-specific fields
        try:
            records = c.search_read(
                "base.automation",
                domain=[("trigger", "in", webhook_triggers)],
                fields=["id", "name", "trigger", "model_id", "active", "create_date", "write_date"],
                limit=limit,
                order="name",
            )
        except Exception:
            out.error(
                "base.automation model not available. Is the 'base_automation' module installed?"
                " (Install via: kctl-odoo modules install base_automation)"
            )
            raise typer.Exit(1) from None

    if not records:
        out.info("No webhook automations found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        model = r.get("model_id")
        model_name = model[1] if isinstance(model, list) else str(model or "-")
        status = "[green]active[/green]" if r.get("active") else "[dim]inactive[/dim]"
        url = r.get("url") or r.get("webhook_uuid") or "-"
        rows.append(
            [
                str(r["id"]),
                r["name"],
                r.get("trigger") or "-",
                model_name,
                status,
                str(url),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r["name"],
                "trigger": r.get("trigger"),
                "model": model_name,
                "active": r.get("active"),
                "url": r.get("url"),
                "webhook_uuid": r.get("webhook_uuid"),
            }
        )

    out.table(
        f"Webhook Automations ({len(records)})",
        [("ID", "cyan"), ("Name", ""), ("Trigger", ""), ("Model", "dim"), ("Status", ""), ("URL/UUID", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command("oauth")
def oauth_list(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List OAuth providers."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        records = c.search_read(
            "auth_oauth.provider",
            domain=[],
            fields=["id", "name", "enabled", "client_id", "auth_endpoint", "scope", "validation_endpoint", "css_class"],
            limit=limit,
            order="name",
        )
    except Exception:
        out.info("No OAuth providers configured (auth_oauth module not installed).")
        if actx.json_mode:
            out.raw_json([])
        return

    if not records:
        out.info("No OAuth providers configured.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        status = "[green]enabled[/green]" if r.get("enabled") else "[dim]disabled[/dim]"
        endpoint = r.get("auth_endpoint") or "-"
        if len(endpoint) > 40:
            endpoint = endpoint[:37] + "..."
        rows.append(
            [
                str(r["id"]),
                r["name"],
                status,
                r.get("client_id") or "-",
                endpoint,
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r["name"],
                "enabled": r.get("enabled"),
                "client_id": r.get("client_id"),
                "auth_endpoint": r.get("auth_endpoint"),
                "scope": r.get("scope"),
                "validation_endpoint": r.get("validation_endpoint"),
            }
        )

    out.table(
        f"OAuth Providers ({len(records)})",
        [("ID", "cyan"), ("Name", ""), ("Status", ""), ("Client ID", "dim"), ("Auth Endpoint", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command("send-bus")
def bus_send(
    ctx: typer.Context,
    channel: Annotated[str, typer.Argument(help="Bus channel name")],
    message: Annotated[str, typer.Argument(help="Message to send (string or JSON)")],
) -> None:
    """Send a message to the Odoo bus channel."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    import json

    # Try to parse message as JSON, otherwise send as string
    try:
        parsed_message = json.loads(message)
    except (json.JSONDecodeError, ValueError):
        parsed_message = message

    try:
        c.execute_kw("bus.bus", "_sendone", [channel, "notification", parsed_message])
    except Exception:
        try:
            c.execute_kw("bus.bus", "sendone", [channel, "notification", parsed_message])
        except Exception as e:
            out.error(f"Failed to send bus message: {e}")
            raise typer.Exit(1) from e

    out.success(f"Message sent to channel '{channel}'")
    if actx.json_mode:
        out.raw_json({"channel": channel, "message": parsed_message, "status": "sent"})


@app.command("test-smtp")
def test_smtp(
    ctx: typer.Context,
    server_id: Annotated[int | None, typer.Option("--server-id", help="Mail server ID (default: all)")] = None,
) -> None:
    """Test SMTP connection for outgoing mail servers."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if server_id:
        server_ids = [server_id]
    else:
        # Get all outgoing mail servers
        servers = c.search_read(
            "ir.mail_server",
            domain=[],
            fields=["id", "name", "smtp_host", "smtp_port"],
            order="sequence",
        )
        if not servers:
            out.error("No outgoing mail servers configured.")
            raise typer.Exit(1)
        server_ids = [s["id"] for s in servers]
        for s in servers:
            out.info(f"Found server: {s['name']} ({s.get('smtp_host')}:{s.get('smtp_port')})")

    results = []
    for sid in server_ids:
        out.info(f"Testing SMTP connection for server ID {sid}...")
        try:
            c.execute_kw("ir.mail_server", "test_smtp_connection", [[sid]])
            out.success(f"Server ID {sid}: SMTP connection successful")
            results.append({"server_id": sid, "status": "ok"})
        except Exception as e:
            error_msg = str(e)
            out.error(f"Server ID {sid}: SMTP test failed - {error_msg}")
            results.append({"server_id": sid, "status": "error", "error": error_msg})

    if actx.json_mode:
        out.raw_json(results)
