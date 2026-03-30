"""Telegram bot management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.config_manager import ConfigFile
from kctl_claw.core.exceptions import GatewayError

_GATEWAY_HINT = "Start the gateway first: kctl-claw deploy up"

app = typer.Typer(help="Manage Telegram bot configuration.")


@app.command()
def bots(ctx: typer.Context) -> None:
    """List configured Telegram bots (name, token env var, bound agent)."""
    actx: AppContext = ctx.obj
    out = actx.output
    mgr = actx.config_mgr

    data = mgr.read(ConfigFile.OPENCLAW)
    accounts = data.get("channels", {}).get("telegram", {}).get("accounts", [])
    bindings = data.get("bindings", [])

    # Build a map from channel name to agent
    binding_map: dict[str, str] = {}
    for b in bindings:
        channel = b.get("channel", "")
        if channel.startswith("telegram:"):
            bot_name = channel.split(":", 1)[1]
            binding_map[bot_name] = b.get("agent", "")

    rows = []
    json_data = []
    for acct in accounts:
        name = acct.get("name", "")
        token_env = acct.get("tokenEnv", "")
        agent = binding_map.get(name, "(unbound)")
        rows.append([name, token_env, agent])
        json_data.append({"name": name, "token_env": token_env, "agent": agent})

    out.table(
        f"Telegram Bots ({len(accounts)})",
        [("Bot Name", "cyan"), ("Token Env Var", ""), ("Bound Agent", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def bindings(ctx: typer.Context) -> None:
    """Show bot-agent channel bindings."""
    actx: AppContext = ctx.obj
    out = actx.output
    mgr = actx.config_mgr

    data = mgr.read(ConfigFile.OPENCLAW)
    binding_list = data.get("bindings", [])

    rows = []
    json_data = []
    for b in binding_list:
        channel = b.get("channel", "")
        agent = b.get("agent", "")
        rows.append([channel, agent])
        json_data.append({"channel": channel, "agent": agent})

    out.table(
        f"Channel Bindings ({len(binding_list)})",
        [("Channel", "cyan"), ("Agent", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def allowlist(ctx: typer.Context) -> None:
    """Show Telegram DM and group allowlists."""
    actx: AppContext = ctx.obj
    out = actx.output
    mgr = actx.config_mgr

    data = mgr.read(ConfigFile.OPENCLAW)
    allow_from = data.get("channels", {}).get("telegram", {}).get("allowFrom", {})

    dm_ids = allow_from.get("dm", [])
    group_ids = allow_from.get("groups", [])

    rows = []
    json_data = []
    for uid in dm_ids:
        rows.append([str(uid), "dm"])
        json_data.append({"id": uid, "type": "dm"})
    for uid in group_ids:
        rows.append([str(uid), "group"])
        json_data.append({"id": uid, "type": "group"})

    out.table(
        f"Telegram Allowlist ({len(rows)} entries)",
        [("ID", "cyan"), ("Type", "")],
        rows,
        data_for_json=json_data,
    )


@app.command("test-send")
def test_send(
    ctx: typer.Context,
    bot: Annotated[str, typer.Argument(help="Bot name (from config)")],
    message: Annotated[str, typer.Argument(help="Message text to send")],
) -> None:
    """Send a test message via a configured bot."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info(f"Sending test message via bot {bot!r}: {message[:60]!r}")
    try:
        data = actx.gateway.post(f"/api/telegram/{bot}/test-send", {"message": message})
        if isinstance(data, dict):
            out.success(f"Message sent: {data.get('message_id', 'ok')}")
        else:
            out.success("Test message sent.")
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command("webhook-status")
def webhook_status(
    ctx: typer.Context,
    bot: Annotated[str, typer.Argument(help="Bot name (from config)")],
) -> None:
    """Check webhook delivery status for a bot."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info(f"Checking webhook status for bot {bot!r}...")
    try:
        data = actx.gateway.get(f"/api/telegram/{bot}/webhook")
        if isinstance(data, dict):
            sections = [
                (
                    "Webhook",
                    [
                        ("Bot", bot),
                        ("URL", str(data.get("url", ""))),
                        ("Status", str(data.get("status", ""))),
                        ("Pending Updates", str(data.get("pending_update_count", ""))),
                        ("Last Error", str(data.get("last_error_message", "none"))),
                    ],
                )
            ]
            out.detail(f"Webhook: {bot}", sections, data_for_json=data)
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command()
def simulate(
    ctx: typer.Context,
    bot: Annotated[str, typer.Argument(help="Bot name (from config)")],
    message: Annotated[str, typer.Argument(help="Message to simulate from a user")],
) -> None:
    """Simulate a user message to a bot and show the agent response."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info(f"Simulating user message to bot {bot!r}: {message[:60]!r}")
    try:
        data = actx.gateway.post(
            f"/api/telegram/{bot}/simulate",
            {"message": message, "user_id": 0, "username": "test_user"},
        )
        if isinstance(data, dict):
            sections = [
                (
                    "Simulation",
                    [
                        ("Bot", bot),
                        ("Input", message[:100]),
                        ("Agent", str(data.get("agent", ""))),
                        ("Response", str(data.get("response", ""))[:300]),
                        ("Tokens", str(data.get("tokens", ""))),
                    ],
                )
            ]
            out.detail(f"Simulation: {bot}", sections, data_for_json=data)
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command()
def recent(
    ctx: typer.Context,
    bot: Annotated[str, typer.Argument(help="Bot name (from config)")],
    count: Annotated[int, typer.Option("--count", help="Number of recent messages")] = 10,
) -> None:
    """Show recent messages for a bot."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info(f"Fetching last {count} messages for bot {bot!r}...")
    try:
        data = actx.gateway.get(f"/api/telegram/{bot}/messages", count=count)
        if isinstance(data, list):
            rows = [
                [
                    str(m.get("id", ""))[:8],
                    str(m.get("from", "")),
                    str(m.get("text", ""))[:60],
                    str(m.get("at", "")),
                ]
                for m in data
            ]
            out.table(
                f"Recent Messages: {bot} ({len(data)})",
                [("ID", "dim"), ("From", "cyan"), ("Text", ""), ("At", "dim")],
                rows,
                data_for_json=data,
            )
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)
