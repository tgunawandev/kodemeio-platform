"""Health check commands."""

from __future__ import annotations

import time
from typing import Annotated

import typer

from kctl_rmm.core.callbacks import AppContext
from kctl_rmm.core.config import resolve_mesh_url

app = typer.Typer(help="Health checks and diagnostics.")


def _check_health(ctx: AppContext) -> dict:
    c = ctx.client
    results: dict = {"api": False, "mesh": False, "score": 0}

    # API health
    try:
        status, body = c.check_health()
        results["api"] = status == 200 and body.get("status") == "ok"
        results["api_status"] = status
    except Exception:
        results["api"] = False
        results["api_status"] = 0

    # MeshCentral reachability
    mesh_url = resolve_mesh_url(ctx.profile)
    if mesh_url:
        import httpx
        try:
            r = httpx.get(mesh_url, timeout=5, follow_redirects=True, verify=False)
            results["mesh"] = r.status_code < 500
            results["mesh_status"] = r.status_code
        except Exception:
            results["mesh"] = False
            results["mesh_status"] = 0
    results["mesh_url"] = mesh_url

    # Score
    score = 0
    if results["api"]:
        score += 60
    if results["mesh"]:
        score += 40
    results["score"] = score

    return results


def _display_health(ctx: AppContext, results: dict) -> None:
    out = ctx.output

    def status_icon(ok: bool) -> str:
        return "[green]OK[/green]" if ok else "[red]FAIL[/red]"

    score = results["score"]
    score_color = "green" if score >= 80 else "yellow" if score >= 50 else "red"

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        ("Services", [
            ("API (health endpoint)", f"{status_icon(results['api'])} (HTTP {results.get('api_status', '?')})"),
            ("MeshCentral", f"{status_icon(results['mesh'])} ({results.get('mesh_url', 'not configured')})"),
        ]),
        ("Health Score", [
            ("Score", f"[{score_color}]{score}/100[/{score_color}]"),
        ]),
    ]

    out.detail("Health Check", sections, data_for_json=results)


@app.callback(invoke_without_command=True)
def health(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously monitor.")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Refresh interval in seconds.")] = 10,
) -> None:
    """Check Tactical RMM + MeshCentral health status."""
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
