"""Notification channel management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Manage notification channels.")


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
            [
                ("ID", data.get("notificationId", "")),
                ("Name", data.get("name", "")),
                ("Type", data.get("notificationType", data.get("type", "unknown"))),
                ("Enabled", str(data.get("enabled", True))),
                (
                    "Webhook URL",
                    data.get("webhookUrl", data.get("slackWebhookUrl", data.get("discordWebhookUrl", "-"))),
                ),
                ("Created", data.get("createdAt", "-")),
            ],
        ),
    ]
    c.output.detail(f"Notification: {data.get('name', '')}", sections, data_for_json=data)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Channel name")],
    notification_type: Annotated[str, typer.Option("--type", "-t", help="Type (slack, discord, telegram, email)")],
    webhook_url: Annotated[str | None, typer.Option("--webhook-url", help="Webhook URL")] = None,
    email: Annotated[str | None, typer.Option("--email", help="Email address (for email type)")] = None,
    chat_id: Annotated[str | None, typer.Option("--chat-id", help="Telegram chat ID")] = None,
    bot_token: Annotated[str | None, typer.Option("--bot-token", help="Telegram bot token")] = None,
) -> None:
    """Create a new notification channel."""
    c: AppContext = ctx.obj
    payload: dict = {
        "name": name,
        "notificationType": notification_type,
    }
    if notification_type == "slack" and webhook_url:
        payload["slackWebhookUrl"] = webhook_url
    elif notification_type == "discord" and webhook_url:
        payload["discordWebhookUrl"] = webhook_url
    elif webhook_url:
        payload["webhookUrl"] = webhook_url
    if email:
        payload["email"] = email
    if chat_id:
        payload["telegramChatId"] = chat_id
    if bot_token:
        payload["telegramBotToken"] = bot_token
    result = c.client.post("/notification.create", json=payload)
    nid = result.get("notificationId", "") if isinstance(result, dict) else ""
    c.output.success(f"Notification channel '{name}' created: {nid}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def update(
    ctx: typer.Context,
    notification_id: Annotated[str, typer.Argument(help="Notification channel ID")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="New name")] = None,
    webhook_url: Annotated[str | None, typer.Option("--webhook-url", help="New webhook URL")] = None,
    enabled: Annotated[bool | None, typer.Option("--enabled/--disabled", help="Enable or disable")] = None,
) -> None:
    """Update a notification channel."""
    c: AppContext = ctx.obj
    payload: dict = {"notificationId": notification_id}
    if name is not None:
        payload["name"] = name
    if webhook_url is not None:
        payload["webhookUrl"] = webhook_url
        payload["slackWebhookUrl"] = webhook_url
        payload["discordWebhookUrl"] = webhook_url
    if enabled is not None:
        payload["enabled"] = enabled
    result = c.client.post("/notification.update", json=payload)
    c.output.success(f"Notification channel '{notification_id}' updated")
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
    notification_id: Annotated[str, typer.Argument(help="Notification channel ID to test")],
) -> None:
    """Test a notification channel."""
    c: AppContext = ctx.obj
    c.output.info(f"Testing notification channel '{notification_id}'...")
    result = c.client.post("/notification.test", json={"notificationId": notification_id})
    c.output.success(f"Notification channel '{notification_id}' test sent")
    if c.json_mode:
        c.output.raw_json(result)
