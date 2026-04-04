"""Fail2ban management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage fail2ban bans.")


@app.command()
def status(ctx: typer.Context) -> None:
    """Show fail2ban status and banned IPs."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("fail2ban")
    item = data if isinstance(data, dict) else {}

    if not item:
        c.output.info("No fail2ban data available.")
        if c.json_mode:
            c.output.raw_json({})
        return

    banned = item.get("banned", [])
    sections = [
        (
            "Fail2ban Status",
            [
                ("Active Bans", str(len(banned))),
                ("Ban Time", str(item.get("ban_time", ""))),
                ("Max Attempts", str(item.get("max_attempts", ""))),
                ("Retry Window", str(item.get("retry_window", ""))),
            ],
        ),
    ]
    if banned:
        sections.append(("Banned IPs", [(ip, "") for ip in banned[:50]]))

    c.output.detail("Fail2ban", sections, data_for_json=item)


@app.command()
def ban(
    ctx: typer.Context,
    ip: Annotated[str, typer.Argument(help="IP address to ban")],
) -> None:
    """Ban an IP address."""
    c: AppContext = ctx.obj
    # fail2ban is a singleton endpoint — no items key needed
    result = c.client.mc_edit("fail2ban", {"attr": {"ban_ip": ip}})
    handle_result(c, result, f"IP '{ip}' banned")


@app.command()
def unban(
    ctx: typer.Context,
    ip: Annotated[str, typer.Argument(help="IP address to unban")],
) -> None:
    """Unban an IP address."""
    c: AppContext = ctx.obj
    # fail2ban is a singleton endpoint — no items key needed
    result = c.client.mc_edit("fail2ban", {"attr": {"unban_ip": ip}})
    handle_result(c, result, f"IP '{ip}' unbanned")
