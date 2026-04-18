"""Health check commands.

Checks Authentik liveness, readiness, API version, and system info.
Calculates a composite health score.
"""

from __future__ import annotations

import time
from typing import Annotated

import typer

from kctl_ak.core.callbacks import AppContext

app = typer.Typer(help="Health checks and diagnostics.")


def _check_health(ctx: AppContext) -> dict:
    """Run all health checks and return results dict."""
    c = ctx.client

    results: dict = {
        "live": False,
        "ready": False,
        "version": None,
        "system": None,
        "score": 0,
    }

    # Liveness probe
    try:
        status = c.check_health("live")
        results["live"] = status == 200
    except Exception:
        results["live"] = False

    # Readiness probe
    try:
        status = c.check_health("ready")
        results["ready"] = status == 200
    except Exception:
        results["ready"] = False

    # API version
    try:
        results["version"] = c.get("admin/version/")
    except Exception:
        results["version"] = None

    # System info (requires admin)
    try:
        results["system"] = c.get("admin/system/")
    except Exception:
        results["system"] = None

    # Calculate score (0-100)
    score = 0
    if results["live"]:
        score += 30
    if results["ready"]:
        score += 30
    if results["version"]:
        score += 20
    if results["system"]:
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
        ("Liveness", status_icon(results["live"])),
        ("Readiness", status_icon(results["ready"])),
    ]
    sections.append(("Probes", probes))

    # Version
    version_kvs: list[tuple[str, str]] = []
    ver = results.get("version")
    if ver:
        version_kvs.append(("Version (installed)", ver.get("version_current", "unknown")))
        version_kvs.append(("Version (latest)", ver.get("version_latest", "unknown")))
        outdated = ver.get("outdated", False)
        version_kvs.append(("Outdated", "[yellow]Yes[/yellow]" if outdated else "[green]No[/green]"))
    else:
        version_kvs.append(("Status", "[red]Unavailable[/red]"))
    sections.append(("Version", version_kvs))

    # System info
    sys_kvs: list[tuple[str, str]] = []
    sys_info = results.get("system")
    if sys_info:
        runtime = sys_info.get("runtime", {})
        sys_kvs.append(("Python", runtime.get("python_version", "unknown")))
        sys_kvs.append(("Platform", runtime.get("platform", "unknown")))
        sys_kvs.append(("Uname", runtime.get("uname", "unknown")))
        embedded_outpost = sys_info.get("embedded_outpost_host", "")
        if embedded_outpost:
            sys_kvs.append(("Embedded Outpost", embedded_outpost))
    else:
        sys_kvs.append(("Status", "[red]Unavailable (admin required)[/red]"))
    sections.append(("System", sys_kvs))

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
        "live": results["live"],
        "ready": results["ready"],
        "version": results.get("version"),
        "system": results.get("system"),
        "score": score,
    }

    out.detail("Health Check", sections, data_for_json=json_data)


@app.callback(invoke_without_command=True)
def health(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously monitor health.")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Refresh interval in seconds.")] = 10,
) -> None:
    """Check Authentik health status."""
    actx: AppContext = ctx.obj

    if watch:
        try:
            while True:
                results = _check_health(actx)
                # Clear screen for watch mode
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
