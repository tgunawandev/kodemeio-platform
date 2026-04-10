"""Dashboard command -- system overview."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Annotated

import typer

from kctl_outline.core.callbacks import AppContext

app = typer.Typer(help="System overview dashboard.")


def _fetch_dashboard(ctx: AppContext) -> dict:
    """Collect all dashboard data."""
    c = ctx.client

    # Auth info (team stats)
    auth_info = None
    try:
        result = c.post("auth.info")
        auth_info = result.get("data", {})
    except Exception:
        pass

    # Collections count
    collections = []
    try:
        result = c.post("collections.list", data={"limit": 100})
        collections = result.get("data", [])
    except Exception:
        pass

    # Recent events
    events: list[dict] = []
    try:
        result = c.post("events.list", data={"limit": 5})
        events = result.get("data", [])
    except Exception:
        pass

    return {
        "auth_info": auth_info,
        "collections": collections,
        "events": events,
    }


def _display_dashboard(ctx: AppContext, data: dict) -> None:
    """Render dashboard output."""
    out = ctx.output

    if out.json_mode:
        out.raw_json(data)
        return

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    # Team section
    auth = data.get("auth_info", {})
    team = auth.get("team", {}) if auth else {}
    user = auth.get("user", {}) if auth else {}

    if team:
        sections.append(("Team", [
            ("Name", team.get("name", "unknown")),
            ("Members", str(team.get("memberCount", 0))),
            ("Documents", str(team.get("documentCount", 0))),
            ("Collections", str(team.get("collectionCount", 0))),
        ]))
    else:
        sections.append(("Team", [("Status", "[red]Unavailable[/red]")]))

    if user:
        sections.append(("Authenticated As", [
            ("User", user.get("name", "")),
            ("Role", user.get("role", "")),
        ]))

    # Collections section
    collections = data.get("collections", [])
    if collections:
        col_kvs: list[tuple[str, str]] = []
        for col in collections[:10]:
            col_kvs.append((col.get("name", ""), col.get("id", "")[:8]))
        sections.append(("Collections", col_kvs))

    # Events section
    events = data.get("events", [])
    if events:
        event_kvs: list[tuple[str, str]] = []
        for ev in events:
            created = ev.get("createdAt", "")
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    created = dt.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError):
                    pass
            name = ev.get("name", "unknown")
            actor = ev.get("actorId", "")[:8]
            event_kvs.append((created, f"{name} (actor: {actor})"))
        sections.append(("Recent Events", event_kvs))

    out.detail("Outline Dashboard", sections, data_for_json=data)


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
