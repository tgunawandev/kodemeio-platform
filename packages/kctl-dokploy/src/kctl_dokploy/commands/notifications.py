"""Notification channel management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Manage notification channels.")

PROVIDERS = ("slack", "discord", "telegram", "email", "custom", "gotify", "ntfy", "pushover", "resend", "teams", "lark")


def _provider_label(p: str) -> str:
    return p.capitalize() if p != "ntfy" else "Ntfy"


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all notification channels."""
    c: AppContext = ctx.obj
    notifications = c.client.get("/notification.all")
    if not isinstance(notifications, list):
        notifications = []
    rows = []
    for n in notifications:
        nid = n.get("notificationId", "")[:12]
        name = n.get("name", "")
        ntype = n.get("notificationType", n.get("type", "unknown"))
        enabled = str(n.get("enabled", True))
        url = n.get("webhookUrl", n.get("slackWebhookUrl", n.get("discordWebhookUrl", "-")))
        rows.append([nid, name, ntype, enabled, str(url)[:50]])
    c.output.table(
        "Notification Channels",
        [("ID", "dim"), ("Name", "cyan"), ("Type", ""), ("Enabled", ""), ("URL", "dim")],
        rows,
        data_for_json=notifications,
    )


@app.command()
def get(
    ctx: typer.Context,
    notification_id: Annotated[str, typer.Argument(help="Notification channel ID")],
) -> None:
    """Get notification channel details."""
    c: AppContext = ctx.obj
    data = c.client.get("/notification.one", params={"notificationId": notification_id})
    if not isinstance(data, dict):
        c.output.error(f"Notification channel '{notification_id}' not found")
        raise typer.Exit(1)
    sections = [
        (
            "Notification Channel",
            [(str(k), str(v)) for k, v in data.items() if v is not None and k not in ("organizationId",)],
        ),
    ]
    c.output.detail(f"Notification: {data.get('name', '')}", sections, data_for_json=data)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Channel name")],
    provider: Annotated[str, typer.Option("--type", "-t", help=f"Provider: {', '.join(PROVIDERS)}")],
    webhook_url: Annotated[
        str | None, typer.Option("--webhook-url", help="Webhook URL (slack/discord/custom/teams/lark)")
    ] = None,
    email: Annotated[str | None, typer.Option("--email", help="Email address")] = None,
    chat_id: Annotated[str | None, typer.Option("--chat-id", help="Telegram chat ID")] = None,
    bot_token: Annotated[str | None, typer.Option("--bot-token", help="Telegram bot token")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="API key (gotify/ntfy/pushover/resend)")] = None,
    url: Annotated[str | None, typer.Option("--url", help="Server URL (gotify/ntfy)")] = None,
) -> None:
    """Create a notification channel (routes to provider-specific API)."""
    c: AppContext = ctx.obj
    provider = provider.lower()
    if provider not in PROVIDERS:
        c.output.error(f"Unknown provider '{provider}'. Use: {', '.join(PROVIDERS)}")
        raise typer.Exit(1)

    payload: dict = {"name": name}

    if provider == "slack":
        payload["webhookUrl"] = webhook_url or ""
    elif provider == "discord":
        payload["webhookUrl"] = webhook_url or ""
    elif provider == "telegram":
        payload["botToken"] = bot_token or ""
        payload["chatId"] = chat_id or ""
    elif provider == "email":
        # Email uses SMTP settings from Dokploy
        pass
    elif provider == "custom":
        payload["webhookUrl"] = webhook_url or ""
    elif provider in ("gotify", "ntfy"):
        payload["serverUrl"] = url or ""
        payload["appToken"] = api_key or ""
    elif provider == "pushover":
        payload["userKey"] = api_key or ""
    elif provider == "resend":
        payload["apiKey"] = api_key or ""
    elif provider == "teams":
        payload["webhookUrl"] = webhook_url or ""
    elif provider == "lark":
        payload["webhookUrl"] = webhook_url or ""

    endpoint = f"/notification.create{_provider_label(provider)}"
    result = c.client.post(endpoint, json=payload)
    nid = result.get("notificationId", "") if isinstance(result, dict) else ""
    c.output.success(f"{_provider_label(provider)} notification '{name}' created: {nid}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def update(
    ctx: typer.Context,
    notification_id: Annotated[str, typer.Argument(help="Notification channel ID")],
    provider: Annotated[str, typer.Option("--type", "-t", help=f"Provider: {', '.join(PROVIDERS)}")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="New name")] = None,
    webhook_url: Annotated[str | None, typer.Option("--webhook-url", help="New webhook URL")] = None,
    enabled: Annotated[bool | None, typer.Option("--enabled/--disabled", help="Enable or disable")] = None,
) -> None:
    """Update a notification channel (routes to provider-specific API)."""
    c: AppContext = ctx.obj
    provider = provider.lower()
    if provider not in PROVIDERS:
        c.output.error(f"Unknown provider '{provider}'. Use: {', '.join(PROVIDERS)}")
        raise typer.Exit(1)

    payload: dict = {"notificationId": notification_id}
    if name is not None:
        payload["name"] = name
    if webhook_url is not None:
        payload["webhookUrl"] = webhook_url
    if enabled is not None:
        payload["enabled"] = enabled

    endpoint = f"/notification.update{_provider_label(provider)}"
    result = c.client.post(endpoint, json=payload)
    c.output.success(f"Notification '{notification_id}' updated")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def remove(
    ctx: typer.Context,
    notification_id: Annotated[str, typer.Argument(help="Notification channel ID to remove")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Remove a notification channel (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Remove notification channel '{notification_id}'?", abort=True)
    result = c.client.post("/notification.remove", json={"notificationId": notification_id})
    c.output.success(f"Notification channel '{notification_id}' removed")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("test")
def test_channel(
    ctx: typer.Context,
    notification_id: Annotated[str, typer.Argument(help="Notification channel ID")],
    provider: Annotated[str, typer.Option("--type", "-t", help=f"Provider: {', '.join(PROVIDERS)}")],
) -> None:
    """Test a notification channel connection."""
    c: AppContext = ctx.obj
    provider = provider.lower()
    if provider not in PROVIDERS:
        c.output.error(f"Unknown provider '{provider}'. Use: {', '.join(PROVIDERS)}")
        raise typer.Exit(1)

    endpoint = f"/notification.test{_provider_label(provider)}Connection"
    c.output.info(f"Testing {provider} notification '{notification_id}'...")
    result = c.client.post(endpoint, json={"notificationId": notification_id})
    c.output.success(f"Test sent for '{notification_id}'")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("providers")
def email_providers(ctx: typer.Context) -> None:
    """List available email providers."""
    c: AppContext = ctx.obj
    data = c.client.get("/notification.getEmailProviders")
    if c.json_mode:
        c.output.raw_json(data)
        return
    if isinstance(data, list):
        rows = [[str(p)] for p in data]
        c.output.table("Email Providers", [("Provider", "cyan")], rows)
    else:
        c.output.info(f"Email providers: {data}")
