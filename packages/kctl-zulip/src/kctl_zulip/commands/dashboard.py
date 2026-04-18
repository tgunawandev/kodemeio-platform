"""Dashboard command -- system overview."""

from __future__ import annotations

import time

import typer
from typing import Annotated

from kctl_zulip.core.callbacks import AppContext

app = typer.Typer(help="System overview dashboard.")


def _fetch_dashboard(ctx: AppContext) -> dict:
    """Collect all dashboard data."""
    c = ctx.client

    # Server settings
    settings = None
    try:
        settings = c.get("server_settings")
    except Exception:
        pass

    # Current user
    me = None
    try:
        me = c.get("users/me")
    except Exception:
        pass

    # Counts
    counts: dict[str, int] = {}

    try:
        data = c.get("users")
        members = data.get("members", [])
        active = [m for m in members if m.get("is_active", True) and not m.get("is_bot", False)]
        bots = [m for m in members if m.get("is_bot", False)]
        counts["Active Users"] = len(active)
        counts["Bots"] = len(bots)
        counts["Total Users"] = len(members)
    except Exception:
        counts["Users"] = -1

    try:
        data = c.get("streams")
        streams = data.get("streams", [])
        counts["Streams"] = len(streams)
    except Exception:
        counts["Streams"] = -1

    try:
        data = c.get("user_groups")
        counts["User Groups"] = len(data.get("user_groups", []))
    except Exception:
        counts["User Groups"] = -1

    try:
        data = c.get("realm/emoji")
        counts["Custom Emoji"] = len(data.get("emoji", {}))
    except Exception:
        counts["Custom Emoji"] = -1

    return {
        "settings": settings,
        "me": me,
        "counts": counts,
    }


def _display_dashboard(ctx: AppContext, data: dict) -> None:
    """Render dashboard output."""
    out = ctx.output

    if out.json_mode:
        out.raw_json(data)
        return

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    # Server info
    settings = data.get("settings") or {}
    if settings:
        sections.append(
            (
                "Server",
                [
                    ("Realm", settings.get("realm_name", "unknown")),
                    ("Zulip Version", settings.get("zulip_version", "unknown")),
                    ("Feature Level", str(settings.get("zulip_feature_level", "unknown"))),
                    ("Push Notifications", str(settings.get("push_notifications_enabled", False))),
                ],
            )
        )

    # Current user
    me = data.get("me")
    if me:
        sections.append(
            (
                "Authenticated As",
                [
                    ("Email", me.get("email", "")),
                    ("Name", me.get("full_name", "")),
                ],
            )
        )

    # Counts
    count_kvs: list[tuple[str, str]] = []
    for label, count in data.get("counts", {}).items():
        if count < 0:
            count_kvs.append((label, "[red]error[/red]"))
        else:
            count_kvs.append((label, str(count)))
    if count_kvs:
        sections.append(("Resources", count_kvs))

    out.detail("Zulip Dashboard", sections, data_for_json=data)


@app.callback(invoke_without_command=True)
def dashboard(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously refresh.")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Refresh interval in seconds.")] = 10,
) -> None:
    """Show system overview dashboard."""
    actx: AppContext = ctx.obj

    if watch:
        try:
            while True:
                data = _fetch_dashboard(actx)
                actx.output.console.clear()
                _display_dashboard(actx, data)
                actx.output.text(f"\n[dim]Refreshing every {interval}s. Press Ctrl+C to stop.[/dim]")
                time.sleep(interval)
        except KeyboardInterrupt:
            actx.output.info("Stopped watching.")
    else:
        data = _fetch_dashboard(actx)
        _display_dashboard(actx, data)
