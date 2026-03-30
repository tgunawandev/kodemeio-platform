"""Dashboard command -- system overview.

Shows WAHA version, session list with status, and bridge connectivity.
"""

from __future__ import annotations

import time
from typing import Annotated

import typer

from kctl_waha.core.callbacks import AppContext

app = typer.Typer(help="System overview dashboard.")


def _fetch_dashboard(ctx: AppContext, compact: bool = False) -> dict:
    """Collect all dashboard data."""
    c = ctx.client

    # WAHA version
    version = None
    try:
        health = c.check_health()
        if health:
            version = health.get("version")
    except Exception:
        pass

    if not version:
        try:
            ver_data = c.get("server/version")
            if isinstance(ver_data, dict):
                version = ver_data.get("version")
        except Exception:
            pass

    # Sessions
    sessions: list[dict] = []
    try:
        raw = c.get("sessions/", params={"all": "true"})
        if isinstance(raw, list):
            sessions = raw
    except Exception:
        pass

    # Per-session details (phone number from /me)
    session_details: list[dict] = []
    for s in sessions:
        detail = {
            "name": s.get("name", "unknown"),
            "status": s.get("status", "UNKNOWN"),
            "engine": s.get("config", {}).get("engine", s.get("engine", "NOWEB")),
        }

        if not compact and s.get("status") == "WORKING":
            try:
                me = c.get(f"sessions/{s['name']}/me")
                if isinstance(me, dict):
                    detail["phone"] = me.get("id", "").replace("@c.us", "")
                    detail["push_name"] = me.get("pushName", "")
            except Exception:
                detail["phone"] = ""
                detail["push_name"] = ""
        else:
            detail["phone"] = ""
            detail["push_name"] = ""

        session_details.append(detail)

    # Bridge status
    bridge_status = "disconnected"
    try:
        bridge_health = ctx.bridge.check_health()
        if bridge_health:
            bridge_status = "connected"
    except Exception:
        pass

    return {
        "version": version,
        "sessions": session_details,
        "bridge_status": bridge_status,
        "total_sessions": len(sessions),
        "working_sessions": sum(1 for s in session_details if s["status"] == "WORKING"),
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
        ver_kvs.append(("WAHA Version", str(ver)))
    else:
        ver_kvs.append(("WAHA Version", "[red]Unavailable[/red]"))
    ver_kvs.append(("Total Sessions", str(data.get("total_sessions", 0))))
    ver_kvs.append(("Working Sessions", str(data.get("working_sessions", 0))))
    sections.append(("Server", ver_kvs))

    # Sessions section
    session_kvs: list[tuple[str, str]] = []
    for s in data.get("sessions", []):
        status = s.get("status", "UNKNOWN")
        if status == "WORKING":
            status_display = "[green]WORKING[/green]"
        elif status == "SCAN_QR_CODE":
            status_display = "[yellow]SCAN_QR[/yellow]"
        elif status == "STOPPED":
            status_display = "[red]STOPPED[/red]"
        elif status == "STARTING":
            status_display = "[yellow]STARTING[/yellow]"
        elif status == "FAILED":
            status_display = "[red]FAILED[/red]"
        else:
            status_display = f"[dim]{status}[/dim]"

        name = s.get("name", "unknown")
        engine = s.get("engine", "")
        phone = s.get("phone", "")
        push_name = s.get("push_name", "")

        info_parts = [status_display, f"engine={engine}"]
        if phone:
            info_parts.append(f"phone={phone}")
        if push_name:
            info_parts.append(f"({push_name})")

        session_kvs.append((name, "  ".join(info_parts)))

    if not session_kvs:
        session_kvs.append(("(none)", "[dim]No sessions found[/dim]"))
    sections.append(("Sessions", session_kvs))

    # Bridge section
    bridge_status = data.get("bridge_status", "disconnected")
    if bridge_status == "connected":
        bridge_display = "[green]Connected[/green]"
    else:
        bridge_display = "[red]Disconnected[/red]"
    sections.append(
        (
            "Bridge Sidecar",
            [
                ("Status", bridge_display),
            ],
        )
    )

    out.detail("WAHA Dashboard", sections, data_for_json=data)


@app.callback(invoke_without_command=True)
def dashboard(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously refresh.")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Refresh interval in seconds.")] = 10,
    compact: Annotated[bool, typer.Option("--compact", "-c", help="Skip per-session /me lookups.")] = False,
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
