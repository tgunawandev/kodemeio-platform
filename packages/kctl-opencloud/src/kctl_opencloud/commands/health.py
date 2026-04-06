"""Health check commands for kctl-opencloud."""

from __future__ import annotations

import time
from typing import Annotated, Any

import httpx
import typer

from kctl_opencloud.core.callbacks import AppContext

app = typer.Typer(help="Health checks and monitoring.")


def _check_endpoint(base_url: str, path: str) -> int:
    """Check an endpoint, return HTTP status code."""
    try:
        r = httpx.get(f"{base_url}{path}", timeout=5, follow_redirects=True)
        return r.status_code
    except httpx.HTTPError:
        return 0


def _run_health_check(c: AppContext) -> dict[str, Any]:
    """Run all health checks and return results."""
    base_url = c.client.root_url
    score = 0
    checks: dict[str, str] = {}

    # OCS capabilities (30 pts)
    status = _check_endpoint(base_url, "/ocs/v1.php/cloud/capabilities")
    if status == 200:
        score += 30
        checks["ocs"] = "ok"
    else:
        checks["ocs"] = "fail"

    # Web UI (20 pts)
    status = _check_endpoint(base_url, "/")
    if status in (200, 302):
        score += 20
        checks["web"] = "ok"
    else:
        checks["web"] = "fail"

    # Graph API (20 pts)
    status = _check_endpoint(base_url, "/graph/v1.0/me")
    if status in (200, 401):
        score += 20
        checks["graph"] = "ok"
    else:
        checks["graph"] = "fail"

    # WebDAV (15 pts)
    status = _check_endpoint(base_url, "/remote.php/dav/")
    if status in (200, 401, 207):
        score += 15
        checks["dav"] = "ok"
    else:
        checks["dav"] = "fail"

    # OIDC discovery (15 pts)
    status = _check_endpoint(base_url, "/.well-known/openid-configuration")
    if status in (200, 301, 302):
        score += 15
        checks["oidc"] = "ok"
    else:
        checks["oidc"] = "fail"

    overall = "healthy" if score >= 80 else "degraded" if score >= 50 else "unhealthy"

    return {"score": score, "status": overall, "checks": checks, "url": base_url}


def _display_health(c: AppContext, result: dict[str, Any]) -> None:
    """Display health check results."""
    out = c.output

    if c.json_mode:
        out.raw_json(result)
        return

    out.header("OpenCloud Health Check")
    out.kv("URL", result["url"])

    check_labels = {
        "ocs": ("OCS capabilities", 30),
        "web": ("Web UI reachable", 20),
        "graph": ("Graph API", 20),
        "dav": ("WebDAV", 15),
        "oidc": ("OIDC discovery", 15),
    }

    for key, (label, pts) in check_labels.items():
        status = result["checks"][key]
        if status == "ok":
            out.success(f"{label} ({pts} pts)")
        else:
            out.error(f"{label} (0/{pts} pts)")

    score = result["score"]
    overall = result["status"]
    if overall == "healthy":
        out.success(f"Score: {score}/100 — Healthy")
    elif overall == "degraded":
        out.warn(f"Score: {score}/100 — Degraded")
    else:
        out.error(f"Score: {score}/100 — Unhealthy")


@app.callback(invoke_without_command=True)
def check(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuous monitoring")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Watch interval in seconds")] = 10,
) -> None:
    """Run health checks."""
    c: AppContext = ctx.obj

    if watch:
        try:
            while True:
                result = _run_health_check(c)
                _display_health(c, result)
                time.sleep(interval)
        except KeyboardInterrupt:
            pass
    else:
        result = _run_health_check(c)
        _display_health(c, result)
        if result["score"] < 50:
            raise typer.Exit(code=2)
        elif result["score"] < 80:
            raise typer.Exit(code=1)
