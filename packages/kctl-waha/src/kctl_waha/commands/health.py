"""Health check commands.

Checks WAHA API health, active sessions, server version, and bridge status.
Calculates a composite health score.
"""

from __future__ import annotations

import time
from typing import Annotated

import typer

from kctl_waha.core.callbacks import AppContext

app = typer.Typer(help="Health checks and diagnostics.")


def _check_health(ctx: AppContext) -> dict:
    """Run all health checks and return results dict."""
    c = ctx.client

    results: dict = {
        "waha_health": False,
        "active_sessions": False,
        "server_version": None,
        "bridge_health": False,
        "session_count": 0,
        "score": 0,
    }

    # WAHA health (30pts) -- GET /api/health
    try:
        health = c.check_health()
        results["waha_health"] = bool(health)
        if health:
            results["server_version"] = health.get("version")
    except Exception:
        results["waha_health"] = False

    # Active sessions > 0 (30pts) -- GET /api/sessions/
    try:
        sessions = c.get("sessions/", params={"all": "true"})
        if isinstance(sessions, list):
            active = [s for s in sessions if s.get("status") == "WORKING"]
            results["session_count"] = len(active)
            results["active_sessions"] = len(active) > 0
            results["total_sessions"] = len(sessions)
    except Exception:
        results["active_sessions"] = False

    # Server version accessible (20pts)
    if not results["server_version"]:
        try:
            version_data = c.get("server/version")
            if isinstance(version_data, dict):
                results["server_version"] = version_data.get("version")
        except Exception:
            pass

    # Bridge health (20pts)
    try:
        bridge_health = ctx.bridge.check_health()
        results["bridge_health"] = bool(bridge_health)
    except Exception:
        results["bridge_health"] = False

    # Calculate score (0-100)
    score = 0
    if results["waha_health"]:
        score += 30
    if results["active_sessions"]:
        score += 30
    if results["server_version"]:
        score += 20
    if results["bridge_health"]:
        score += 20
    results["score"] = score

    return results


def _display_health(ctx: AppContext, results: dict) -> None:
    """Display health results."""
    out = ctx.output

    def status_icon(ok: bool) -> str:
        return "[green]OK[/green]" if ok else "[red]FAIL[/red]"

    score = results["score"]
    if score >= 80:
        score_color = "green"
    elif score >= 50:
        score_color = "yellow"
    else:
        score_color = "red"

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    # WAHA API
    waha_kvs: list[tuple[str, str]] = [
        ("API Health", status_icon(results["waha_health"])),
        ("Active Sessions", status_icon(results["active_sessions"])),
    ]
    session_count = results.get("session_count", 0)
    total_sessions = results.get("total_sessions", 0)
    waha_kvs.append(("Sessions", f"{session_count} active / {total_sessions} total"))
    sections.append(("WAHA API", waha_kvs))

    # Version
    version_kvs: list[tuple[str, str]] = []
    ver = results.get("server_version")
    if ver:
        version_kvs.append(("Version", str(ver)))
    else:
        version_kvs.append(("Version", "[red]Unavailable[/red]"))
    sections.append(("Server", version_kvs))

    # Bridge
    bridge_kvs: list[tuple[str, str]] = [
        ("Bridge Health", status_icon(results["bridge_health"])),
    ]
    sections.append(("Bridge Sidecar", bridge_kvs))

    # Score
    sections.append(
        (
            "Health Score",
            [
                ("Score", f"[{score_color}]{score}/100[/{score_color}]"),
            ],
        )
    )

    json_data = {
        "waha_health": results["waha_health"],
        "active_sessions": results["active_sessions"],
        "session_count": results.get("session_count", 0),
        "total_sessions": results.get("total_sessions", 0),
        "server_version": results.get("server_version"),
        "bridge_health": results["bridge_health"],
        "score": score,
    }

    out.detail("Health Check", sections, data_for_json=json_data)


@app.callback(invoke_without_command=True)
def health(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously monitor health.")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Refresh interval in seconds.")] = 10,
) -> None:
    """Check WAHA health status."""
    actx: AppContext = ctx.obj

    if watch:
        try:
            while True:
                results = _check_health(actx)
                actx.output.console.clear()
                _display_health(actx, results)
                actx.output.text(f"\n[dim]Refreshing every {interval}s. Press Ctrl+C to stop.[/dim]")
                time.sleep(interval)
        except KeyboardInterrupt:
            actx.output.info("Stopped watching.")
    else:
        results = _check_health(actx)
        _display_health(actx, results)
        if results["score"] < 50:
            raise typer.Exit(code=1)
