"""Bridge sidecar management commands.

Interact with the WAHA bridge service for Chatwoot/Odoo integration.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_waha.core.callbacks import AppContext
from kctl_waha.core.exceptions import KctlError

app = typer.Typer(help="Manage WAHA bridge sidecar.")


@app.command()
def health(ctx: typer.Context) -> None:
    """Check bridge sidecar health."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        result = actx.bridge.check_health()
    except KctlError as e:
        out.error(f"Bridge health check failed: {e}")
        raise typer.Exit(1) from e

    if not result:
        out.error("Bridge is not responding")
        raise typer.Exit(1)

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Bridge Health",
            [
                ("Status", "[green]Healthy[/green]"),
            ],
        ),
    ]

    # Include any extra fields from health response
    if isinstance(result, dict):
        for key, value in result.items():
            if key != "status":
                sections[0][1].append((key.replace("_", " ").title(), str(value)))

    out.detail("Bridge Sidecar", sections, data_for_json=result)


@app.command()
def status(ctx: typer.Context) -> None:
    """Show bridge setup status (WAHA, Chatwoot, Odoo config)."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        result = actx.bridge.get("setup/status")
    except KctlError as e:
        out.error(f"Failed to get bridge status: {e}")
        raise typer.Exit(1) from e

    if not isinstance(result, dict):
        out.error("Unexpected response format")
        raise typer.Exit(1)

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    # WAHA config
    waha_cfg = result.get("waha", {})
    if isinstance(waha_cfg, dict):
        waha_kvs: list[tuple[str, str]] = []
        for key, value in waha_cfg.items():
            display_key = key.replace("_", " ").title()
            if "key" in key.lower() or "token" in key.lower() or "secret" in key.lower():
                value = "****" if value else "[dim]not set[/dim]"
            waha_kvs.append((display_key, str(value)))
        if waha_kvs:
            sections.append(("WAHA", waha_kvs))

    # Chatwoot config
    chatwoot_cfg = result.get("chatwoot", {})
    if isinstance(chatwoot_cfg, dict):
        cw_kvs: list[tuple[str, str]] = []
        for key, value in chatwoot_cfg.items():
            display_key = key.replace("_", " ").title()
            if "key" in key.lower() or "token" in key.lower() or "secret" in key.lower():
                value = "****" if value else "[dim]not set[/dim]"
            cw_kvs.append((display_key, str(value)))
        if cw_kvs:
            sections.append(("Chatwoot", cw_kvs))

    # Odoo config
    odoo_cfg = result.get("odoo", {})
    if isinstance(odoo_cfg, dict):
        odoo_kvs: list[tuple[str, str]] = []
        for key, value in odoo_cfg.items():
            display_key = key.replace("_", " ").title()
            if "key" in key.lower() or "token" in key.lower() or "secret" in key.lower() or "password" in key.lower():
                value = "****" if value else "[dim]not set[/dim]"
            odoo_kvs.append((display_key, str(value)))
        if odoo_kvs:
            sections.append(("Odoo", odoo_kvs))

    if not sections:
        sections.append(("Status", [("Info", "[dim]No configuration data returned[/dim]")]))

    out.detail("Bridge Setup Status", sections, data_for_json=result)


@app.command("setup-chatwoot")
def setup_chatwoot(
    ctx: typer.Context,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Inbox name.")] = None,
    callback_url: Annotated[str | None, typer.Option("--callback-url", help="Callback URL for Chatwoot.")] = None,
) -> None:
    """Setup Chatwoot inbox integration via bridge.

    Creates or configures a Chatwoot inbox for WhatsApp message routing.
    """
    actx: AppContext = ctx.obj
    out = actx.output

    body: dict = {}
    if name:
        body["name"] = name
    if callback_url:
        body["callback_url"] = callback_url

    try:
        result = actx.bridge.post("setup/chatwoot-inbox", data=body)
    except KctlError as e:
        out.error(f"Failed to setup Chatwoot inbox: {e}")
        raise typer.Exit(1) from e

    if out.json_mode:
        out.raw_json(result)
    else:
        out.success("Chatwoot inbox setup initiated")
        if isinstance(result, dict):
            for key, value in result.items():
                display_key = key.replace("_", " ").title()
                out.kv(display_key, str(value))


@app.command("setup-webhook")
def setup_webhook(
    ctx: typer.Context,
    session: Annotated[str, typer.Option("--session", "-s", help="Session name.")] = "default",
    webhook_url: Annotated[str | None, typer.Option("--webhook-url", help="Webhook URL to configure.")] = None,
) -> None:
    """Setup WAHA webhook via bridge.

    Configures the WAHA session webhook to route messages through the bridge.
    """
    actx: AppContext = ctx.obj
    out = actx.output

    body: dict = {"session": session}
    if webhook_url:
        body["webhook_url"] = webhook_url

    try:
        result = actx.bridge.post("setup/waha-webhook", data=body)
    except KctlError as e:
        out.error(f"Failed to setup WAHA webhook: {e}")
        raise typer.Exit(1) from e

    if out.json_mode:
        out.raw_json(result)
    else:
        out.success(f"WAHA webhook configured for session '{session}'")
        if isinstance(result, dict):
            for key, value in result.items():
                display_key = key.replace("_", " ").title()
                out.kv(display_key, str(value))
