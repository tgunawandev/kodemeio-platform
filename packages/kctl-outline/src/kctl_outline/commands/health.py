"""Health check commands."""

from __future__ import annotations

import time
from typing import Annotated

import typer

from kctl_outline.core.callbacks import AppContext

app = typer.Typer(help="Health checks and diagnostics.")


def _check_health(ctx: AppContext) -> dict:
    """Run all health checks and return results dict."""
    c = ctx.client

    results: dict = {
        "healthy": False,
        "auth": None,
        "team": None,
        "score": 0,
    }

    # Health endpoint
    try:
        status = c.check_health()
        results["healthy"] = status == 200
    except Exception:
        results["healthy"] = False

    # Auth info (validates token + API)
    try:
        auth_data = c.post("auth.info")
        data = auth_data.get("data", {})
        results["auth"] = {
            "user": data.get("user", {}).get("name", "unknown"),
            "role": data.get("user", {}).get("role", "unknown"),
        }
        results["team"] = {
            "name": data.get("team", {}).get("name", "unknown"),
            "members": data.get("team", {}).get("memberCount", 0),
            "documents": data.get("team", {}).get("documentCount", 0),
            "collections": data.get("team", {}).get("collectionCount", 0),
        }
    except Exception:
        results["auth"] = None

    # Calculate score (0-100)
    score = 0
    if results["healthy"]:
        score += 50
    if results["auth"]:
        score += 30
    if results["team"]:
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

    # Health probe
    sections.append(
        (
            "Probes",
            [
                ("Health endpoint", status_icon(results["healthy"])),
                ("API auth", status_icon(results["auth"] is not None)),
            ],
        )
    )

    # Auth info
    auth = results.get("auth")
    if auth:
        sections.append(
            (
                "Authentication",
                [
                    ("User", auth.get("user", "unknown")),
                    ("Role", auth.get("role", "unknown")),
                ],
            )
        )

    # Team info
    team = results.get("team")
    if team:
        sections.append(
            (
                "Team",
                [
                    ("Name", team.get("name", "unknown")),
                    ("Members", str(team.get("members", 0))),
                    ("Documents", str(team.get("documents", 0))),
                    ("Collections", str(team.get("collections", 0))),
                ],
            )
        )

    # Score
    sections.append(
        (
            "Health Score",
            [
                ("Score", f"[{score_color}]{score}/100[/{score_color}]"),
            ],
        )
    )

    out.detail("Health Check", sections, data_for_json=results)


@app.callback(invoke_without_command=True)
def health(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously monitor health.")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Refresh interval in seconds.")] = 10,
) -> None:
    """Check Outline health status."""
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
