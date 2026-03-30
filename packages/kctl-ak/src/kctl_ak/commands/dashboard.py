"""Dashboard command -- system overview.

Shows version, resource counts, system status, and recent events.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Annotated

import typer

from kctl_ak.core.callbacks import AppContext

app = typer.Typer(help="System overview dashboard.")

# Endpoints with page_size=1 to get counts via pagination.count
_COUNT_ENDPOINTS: list[tuple[str, str]] = [
    ("Users", "core/users/"),
    ("Groups", "core/groups/"),
    ("Applications", "core/applications/"),
    ("Providers", "providers/all/"),
    ("Flows", "flows/instances/"),
    ("Outposts", "outposts/instances/"),
    ("Tokens", "core/tokens/"),
    ("Sessions", "core/authenticated_sessions/"),
]


def _fetch_count(ctx: AppContext, endpoint: str) -> int:
    """Fetch resource count using page_size=1."""
    try:
        data = ctx.client.get(endpoint, params={"page_size": 1})
        return data.get("pagination", {}).get("count", 0)
    except Exception:
        return -1


def _fetch_dashboard(ctx: AppContext, compact: bool = False) -> dict:
    """Collect all dashboard data."""
    c = ctx.client

    # Version
    version = None
    try:
        version = c.get("admin/version/")
    except Exception:
        pass

    # Counts
    counts: dict[str, int] = {}
    for label, endpoint in _COUNT_ENDPOINTS:
        counts[label] = _fetch_count(ctx, endpoint)

    # Recent events
    events: list[dict] = []
    if not compact:
        try:
            data = c.get("events/events/", params={"page_size": 5, "ordering": "-created"})
            events = data.get("results", [])
        except Exception:
            pass

    return {
        "version": version,
        "counts": counts,
        "events": events,
    }


def _display_dashboard(ctx: AppContext, data: dict, compact: bool = False) -> None:
    """Render dashboard output."""
    out = ctx.output

    if out.json_mode:
        out.raw_json(data)
        return

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    # Version section
    ver = data.get("version")
    ver_kvs: list[tuple[str, str]] = []
    if ver:
        ver_kvs.append(("Installed", ver.get("version_current", "unknown")))
        ver_kvs.append(("Latest", ver.get("version_latest", "unknown")))
        outdated = ver.get("outdated", False)
        ver_kvs.append(("Outdated", "[yellow]Yes[/yellow]" if outdated else "[green]No[/green]"))
    else:
        ver_kvs.append(("Status", "[red]Unavailable[/red]"))
    sections.append(("Version", ver_kvs))

    # Counts section
    count_kvs: list[tuple[str, str]] = []
    for label, count in data.get("counts", {}).items():
        if count < 0:
            count_kvs.append((label, "[red]error[/red]"))
        else:
            count_kvs.append((label, str(count)))
    sections.append(("Resources", count_kvs))

    # Events section (unless compact)
    if not compact:
        events = data.get("events", [])
        if events:
            event_kvs: list[tuple[str, str]] = []
            for ev in events:
                action = ev.get("action", "unknown")
                created = ev.get("created", "")
                if created:
                    try:
                        dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                        created = dt.strftime("%Y-%m-%d %H:%M")
                    except (ValueError, TypeError):
                        pass
                user_info = ev.get("user", {})
                username = user_info.get("username", "") if isinstance(user_info, dict) else ""
                app_name = ev.get("app", "")
                summary = f"{action}"
                if username:
                    summary += f" by {username}"
                if app_name:
                    summary += f" [{app_name}]"
                event_kvs.append((created, summary))
            sections.append(("Recent Events", event_kvs))
        else:
            sections.append(("Recent Events", [("Status", "[dim]No recent events[/dim]")]))

    out.detail("Authentik Dashboard", sections, data_for_json=data)


@app.callback(invoke_without_command=True)
def dashboard(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously refresh.")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Refresh interval in seconds.")] = 10,
    compact: Annotated[bool, typer.Option("--compact", "-c", help="Hide events section.")] = False,
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
