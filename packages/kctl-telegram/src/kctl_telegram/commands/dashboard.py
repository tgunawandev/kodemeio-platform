"""Dashboard command -- system overview.

Shows version, resource counts, bot list, and system status.
"""

from __future__ import annotations

import contextlib
import time
from typing import Annotated

import typer

from kctl_telegram.core.callbacks import AppContext

app = typer.Typer(help="System overview dashboard.")


def _fetch_count(ctx: AppContext, endpoint: str) -> int:
    """Fetch resource count using page_size=1."""
    try:
        data = ctx.client.get(endpoint, params={"page_size": 1})
        return data.get("pagination", {}).get("count", len(data.get("results", [])))
    except Exception:
        return -1


def _fetch_dashboard(ctx: AppContext, compact: bool = False) -> dict:
    """Collect all dashboard data."""
    c = ctx.client

    # Health / version
    health_data = None
    with contextlib.suppress(Exception):
        health_data = c.check_health()

    # Counts
    counts: dict[str, int] = {}
    counts["Bots"] = _fetch_count(ctx, "bots")
    counts["Groups"] = _fetch_count(ctx, "groups")
    counts["Scheduled Messages"] = _fetch_count(ctx, "messages/scheduled")

    # Bot list
    bots: list[dict] = []
    if not compact:
        try:
            data = c.get("bots", params={"page_size": 20})
            bots = data.get("results", []) if isinstance(data, dict) else data if isinstance(data, list) else []
        except Exception:
            pass

    return {
        "health": health_data,
        "counts": counts,
        "bots": bots,
    }


def _display_dashboard(ctx: AppContext, data: dict, compact: bool = False) -> None:
    """Render dashboard output."""
    out = ctx.output

    if out.json_mode:
        out.raw_json(data)
        return

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    # Version / status section
    health = data.get("health")
    ver_kvs: list[tuple[str, str]] = []
    if health:
        ver_kvs.append(("Version", health.get("version", "unknown")))
        status = health.get("status", "unknown")
        if status in ("healthy", "ok"):
            ver_kvs.append(("Status", f"[green]{status}[/green]"))
        else:
            ver_kvs.append(("Status", f"[yellow]{status}[/yellow]"))
    else:
        ver_kvs.append(("Status", "[red]Unavailable[/red]"))
    sections.append(("Service", ver_kvs))

    # Counts section
    count_kvs: list[tuple[str, str]] = []
    for label, count in data.get("counts", {}).items():
        if count < 0:
            count_kvs.append((label, "[red]error[/red]"))
        else:
            count_kvs.append((label, str(count)))
    sections.append(("Resources", count_kvs))

    # Bot list (unless compact)
    if not compact:
        bots = data.get("bots", [])
        if bots:
            bot_kvs: list[tuple[str, str]] = []
            for bot in bots:
                username = bot.get("username", "unknown")
                display_name = bot.get("display_name", "")
                is_active = bot.get("is_active", False)
                status_str = "[green]active[/green]" if is_active else "[red]inactive[/red]"
                label = f"@{username}" if username else display_name
                bot_kvs.append((label, f"{display_name}  {status_str}"))
            sections.append(("Bots", bot_kvs))
        else:
            sections.append(("Bots", [("Status", "[dim]No bots configured[/dim]")]))

    out.detail("Telegram Dashboard", sections, data_for_json=data)


@app.callback(invoke_without_command=True)
def dashboard(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously refresh.")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Refresh interval in seconds.")] = 10,
    compact: Annotated[bool, typer.Option("--compact", "-c", help="Hide bot list.")] = False,
) -> None:
    """Show system overview dashboard."""
    actx: AppContext = ctx.obj

    if watch:
        try:
            while True:
                data = _fetch_dashboard(actx, compact=compact)
                actx.output.console.clear()
                _display_dashboard(actx, data, compact=compact)
                actx.output.text(f"\n[dim]Refreshing every {interval}s. Press Ctrl+C to stop.[/dim]")
                time.sleep(interval)
        except KeyboardInterrupt:
            actx.output.info("Stopped watching.")
    else:
        data = _fetch_dashboard(actx, compact=compact)
        _display_dashboard(actx, data, compact=compact)
