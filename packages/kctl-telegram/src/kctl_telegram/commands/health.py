"""Health check commands.

Checks Telegram gateway health, readiness, bot count, and group count.
Calculates a composite health score.
"""

from __future__ import annotations

import time
from typing import Annotated

import typer

from kctl_telegram.core.callbacks import AppContext

app = typer.Typer(help="Health checks and diagnostics.")


def _check_health(ctx: AppContext) -> dict:
    """Run all health checks and return results dict."""
    c = ctx.client

    results: dict = {
        "healthy": False,
        "ready": False,
        "has_bots": False,
        "has_groups": False,
        "health_data": None,
        "ready_data": None,
        "bot_count": 0,
        "group_count": 0,
        "score": 0,
    }

    # Health endpoint (30pts)
    try:
        health_data = c.check_health()
        results["health_data"] = health_data
        status = health_data.get("status", "")
        results["healthy"] = status in ("healthy", "ok")
    except Exception:
        results["healthy"] = False

    # Ready endpoint (30pts)
    try:
        ready_data = c.check_ready()
        results["ready_data"] = ready_data
        status = ready_data.get("status", "")
        results["ready"] = status in ("ready", "ok")
    except Exception:
        results["ready"] = False

    # Bot count > 0 (20pts)
    try:
        bots_data = c.get("bots", params={"page_size": 1})
        count = bots_data.get("pagination", {}).get("count", len(bots_data.get("results", [])))
        results["bot_count"] = count
        results["has_bots"] = count > 0
    except Exception:
        results["bot_count"] = 0

    # Group count > 0 (20pts)
    try:
        groups_data = c.get("groups", params={"page_size": 1})
        count = groups_data.get("pagination", {}).get("count", len(groups_data.get("results", [])))
        results["group_count"] = count
        results["has_groups"] = count > 0
    except Exception:
        results["group_count"] = 0

    # Calculate score (0-100)
    score = 0
    if results["healthy"]:
        score += 30
    if results["ready"]:
        score += 30
    if results["has_bots"]:
        score += 20
    if results["has_groups"]:
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

    # Probes
    probes = [
        ("Health", status_icon(results["healthy"])),
        ("Ready", status_icon(results["ready"])),
    ]
    sections.append(("Probes", probes))

    # Version from health response
    version_kvs: list[tuple[str, str]] = []
    health_data = results.get("health_data")
    if health_data:
        version = health_data.get("version", "unknown")
        version_kvs.append(("Version", version))
        status = health_data.get("status", "unknown")
        version_kvs.append(("Status", status))
    else:
        version_kvs.append(("Status", "[red]Unavailable[/red]"))
    sections.append(("Version", version_kvs))

    # Resources
    bots_suffix = "[green](OK)[/green]" if results["has_bots"] else "[yellow](none)[/yellow]"
    groups_suffix = "[green](OK)[/green]" if results["has_groups"] else "[yellow](none)[/yellow]"
    resource_kvs: list[tuple[str, str]] = [
        ("Bots", f"{results['bot_count']} {bots_suffix}"),
        ("Groups", f"{results['group_count']} {groups_suffix}"),
    ]
    sections.append(("Resources", resource_kvs))

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
        "healthy": results["healthy"],
        "ready": results["ready"],
        "health_data": results.get("health_data"),
        "ready_data": results.get("ready_data"),
        "bot_count": results["bot_count"],
        "group_count": results["group_count"],
        "score": score,
    }

    out.detail("Health Check", sections, data_for_json=json_data)


@app.callback(invoke_without_command=True)
def health(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously monitor health.")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Refresh interval in seconds.")] = 10,
) -> None:
    """Check Telegram gateway health status."""
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
