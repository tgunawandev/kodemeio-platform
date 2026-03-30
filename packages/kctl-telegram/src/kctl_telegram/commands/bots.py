"""Bot management commands.

List, inspect, create, update, and remove Telegram bots.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_telegram.core.callbacks import AppContext

app = typer.Typer(help="Manage Telegram bots.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all registered bots."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    data = c.get("bots")
    bots = data.get("results", []) if isinstance(data, dict) else data if isinstance(data, list) else []

    if not bots:
        out.warn("No bots found.")
        return

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for bot in bots:
        bot_id = str(bot.get("id", ""))
        username = bot.get("username", "")
        display_name = bot.get("display_name", "")
        is_active = bot.get("is_active", False)
        status = "[green]active[/green]" if is_active else "[red]inactive[/red]"

        rows.append([bot_id, f"@{username}" if username else "-", display_name, status])
        json_data.append(bot)

    out.table(
        "Bots",
        [("ID", "cyan"), ("Username", ""), ("Display Name", ""), ("Status", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def get(
    ctx: typer.Context,
    bot_id: Annotated[int, typer.Argument(help="Bot ID")],
) -> None:
    """Show bot details."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    bot = c.get(f"bots/{bot_id}")

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    info_kvs: list[tuple[str, str]] = [
        ("ID", str(bot.get("id", ""))),
        ("Username", f"@{bot.get('username', '')}" if bot.get("username") else "-"),
        ("Display Name", bot.get("display_name", "")),
        ("Is Active", "[green]Yes[/green]" if bot.get("is_active") else "[red]No[/red]"),
    ]

    # Show token masked
    token = bot.get("token", "")
    if token:
        masked = f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}" if len(token) > 10 else "****"
        info_kvs.append(("Token", masked))

    sections.append(("Bot Info", info_kvs))

    # Timestamps
    ts_kvs: list[tuple[str, str]] = []
    if bot.get("created_at"):
        ts_kvs.append(("Created", bot["created_at"]))
    if bot.get("updated_at"):
        ts_kvs.append(("Updated", bot["updated_at"]))
    if ts_kvs:
        sections.append(("Timestamps", ts_kvs))

    out.detail(f"Bot: {bot.get('display_name', bot.get('username', bot_id))}", sections, data_for_json=bot)


@app.command()
def add(
    ctx: typer.Context,
    token: Annotated[str, typer.Option("--token", help="Telegram bot token from BotFather.")],
    display_name: Annotated[str | None, typer.Option("--display-name", help="Friendly display name.")] = None,
) -> None:
    """Register a new Telegram bot."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    payload: dict = {"token": token}
    if display_name:
        payload["display_name"] = display_name

    bot = c.post("bots", json=payload)

    out.success(f"Bot created: {bot.get('display_name', bot.get('username', ''))}")
    out.kv("ID", str(bot.get("id", "")))
    out.kv("Username", f"@{bot.get('username', '')}" if bot.get("username") else "-")
    out.kv("Display Name", bot.get("display_name", ""))
    out.kv("Active", str(bot.get("is_active", True)))

    if actx.output.json_mode:
        out.raw_json(bot)


@app.command()
def update(
    ctx: typer.Context,
    bot_id: Annotated[int, typer.Argument(help="Bot ID")],
    display_name: Annotated[str | None, typer.Option("--display-name", help="New display name.")] = None,
    is_active: Annotated[bool | None, typer.Option("--is-active/--no-active", help="Enable or disable bot.")] = None,
) -> None:
    """Update a bot's settings."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    payload: dict = {}
    if display_name is not None:
        payload["display_name"] = display_name
    if is_active is not None:
        payload["is_active"] = is_active

    if not payload:
        out.warn("No changes specified. Use --display-name or --is-active/--no-active.")
        raise typer.Exit(1)

    bot = c.patch(f"bots/{bot_id}", json=payload)

    out.success(f"Bot {bot_id} updated")
    out.kv("Display Name", bot.get("display_name", ""))
    out.kv("Active", str(bot.get("is_active", "")))

    if actx.output.json_mode:
        out.raw_json(bot)


@app.command()
def remove(
    ctx: typer.Context,
    bot_id: Annotated[int, typer.Argument(help="Bot ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Remove a bot."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not force:
        # Fetch bot info for confirmation
        try:
            bot = c.get(f"bots/{bot_id}")
            name = bot.get("display_name", bot.get("username", str(bot_id)))
        except Exception:
            name = str(bot_id)

        if not typer.confirm(f"Remove bot '{name}' (ID: {bot_id})?"):
            raise typer.Exit(0)

    c.delete(f"bots/{bot_id}")
    out.success(f"Bot {bot_id} removed")
