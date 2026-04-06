"""Health check commands."""

from __future__ import annotations

import time

import typer
from typing import Annotated

from kctl_zulip.core.callbacks import AppContext
from kctl_lib.exceptions import KctlError

app = typer.Typer(help="Health checks and diagnostics.")


def _check_health(ctx: AppContext) -> dict:
    """Run all health checks and return results dict."""
    results: dict = {
        "server_settings": None,
        "api_reachable": False,
        "authenticated": False,
        "score": 0,
    }

    # Server settings (public, no auth needed)
    try:
        settings = ctx.client.check_health()
        if settings:
            results["server_settings"] = settings
            results["api_reachable"] = True
    except Exception:
        pass

    # Authenticated API test
    try:
        me = ctx.client.get("users/me")
        if me.get("user_id"):
            results["authenticated"] = True
            results["user"] = me
    except Exception:
        pass

    # Calculate score (0-100)
    score = 0
    if results["api_reachable"]:
        score += 40
    if results["authenticated"]:
        score += 40
    if results.get("server_settings", {}).get("push_notifications_enabled"):
        score += 10
    if results.get("server_settings"):
        score += 10
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

    # Connectivity
    sections.append(("Connectivity", [
        ("API Reachable", status_icon(results["api_reachable"])),
        ("Authenticated", status_icon(results["authenticated"])),
    ]))

    # Server info
    settings = results.get("server_settings") or {}
    if settings:
        sections.append(("Server", [
            ("Zulip Version", settings.get("zulip_version", "unknown")),
            ("Feature Level", str(settings.get("zulip_feature_level", "unknown"))),
            ("Realm", settings.get("realm_name", "unknown")),
            ("Push Notifications", status_icon(settings.get("push_notifications_enabled", False))),
        ]))
    else:
        sections.append(("Server", [("Status", "[red]Unreachable[/red]")]))

    # Authenticated user
    user = results.get("user")
    if user:
        sections.append(("Authenticated As", [
            ("Email", user.get("email", "")),
            ("Name", user.get("full_name", "")),
            ("Role", str(user.get("role", ""))),
        ]))

    # Score
    sections.append(("Health Score", [
        ("Score", f"[{score_color}]{score}/100[/{score_color}]"),
    ]))

    out.detail("Health Check", sections, data_for_json=results)


@app.callback(invoke_without_command=True)
def health(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously monitor health.")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Refresh interval in seconds.")] = 10,
) -> None:
    """Check Zulip health status."""
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
