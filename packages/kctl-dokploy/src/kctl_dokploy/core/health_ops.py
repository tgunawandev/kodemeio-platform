"""Health check orchestration for Dokploy deployments.

Provides two complementary health verification channels:
1. Dokploy API polling (compose status)
2. HTTP endpoint availability probing with service-specific paths

Ported from lib/health.sh, redesigned for Python.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

# Service-specific health endpoints for common applications
HEALTH_PATHS: dict[str, str] = {
    "n8n": "/healthz",
    "odoo": "/web/health",
    "frappe": "/api/method/frappe.ping",
    "authentik": "/-/health/live/",
    "mattermost": "/api/v4/system/ping",
    "grafana": "/api/health",
    "prometheus": "/-/healthy",
    "metabase": "/api/health",
    "gitea": "/api/healthz",
    "drone": "/healthz",
    "traefik": "/ping",
    "outline": "/api/info",
    "minio": "/minio/health/live",
    "redis": "/",
    "postgres": "/",
}


def get_health_url(base_url: str, service_hint: str | None = None) -> str:
    """Build the health check URL for a service.

    If service_hint matches a known service, its specific health path is used.
    Otherwise falls back to the base URL root.
    """
    base = base_url.rstrip("/")

    if not service_hint:
        # Try to extract hint from hostname (e.g., "n8n.kodeme.io" -> "n8n")
        try:
            from urllib.parse import urlparse

            hostname = urlparse(base).hostname or ""
            service_hint = hostname.split(".")[0]
        except Exception:
            service_hint = ""

    path = HEALTH_PATHS.get(service_hint.lower(), "/") if service_hint else "/"
    return f"{base}{path}"


def wait_for_dokploy(
    client: Any,
    compose_id: str,
    timeout: float = 300,
    interval: float = 10,
) -> tuple[bool, str]:
    """Poll Dokploy API until compose reaches a terminal state.

    Returns (success, final_status).
    Terminal success states: "done", "running"
    Terminal failure states: "error", "stopped"
    """
    start = time.monotonic()
    last_status = "unknown"

    while (time.monotonic() - start) < timeout:
        try:
            data = client.get("/compose.one", params={"composeId": compose_id})
            last_status = data.get("composeStatus", "unknown").lower() if isinstance(data, dict) else "unknown"
        except Exception:
            last_status = "unreachable"

        if last_status in ("done", "running"):
            return True, last_status
        if last_status in ("error", "stopped"):
            return False, last_status

        time.sleep(interval)

    return False, f"timeout ({last_status})"


def wait_for_http(
    url: str,
    timeout: float = 120,
    interval: float = 10,
    expected_codes: tuple[int, ...] = (200, 201, 204, 301, 302),
) -> tuple[bool, int]:
    """Poll an HTTP endpoint until it responds with an expected status code.

    Returns (success, last_http_code).
    """
    start = time.monotonic()
    last_code = 0

    while (time.monotonic() - start) < timeout:
        try:
            resp = httpx.get(url, timeout=10, follow_redirects=True)
            last_code = resp.status_code
            if last_code in expected_codes:
                return True, last_code
        except httpx.HTTPError:
            last_code = 0

        time.sleep(interval)

    return False, last_code


def wait_for_healthy(
    client: Any,
    compose_id: str,
    hostname: str | None = None,
    service_hint: str | None = None,
    deploy_timeout: float = 300,
    http_timeout: float = 120,
    interval: float = 10,
) -> tuple[bool, str]:
    """Combined health check: Dokploy status + HTTP endpoint.

    Returns (success, description).
    """
    # Phase 1: Wait for Dokploy to report success
    ok, status = wait_for_dokploy(client, compose_id, deploy_timeout, interval)
    if not ok:
        return False, f"Dokploy status: {status}"

    # Phase 2: If hostname provided, probe HTTP endpoint
    if hostname:
        scheme = "https" if "https" in hostname or "." in hostname else "http"
        base_url = hostname if hostname.startswith("http") else f"{scheme}://{hostname}"
        health_url = get_health_url(base_url, service_hint)

        http_ok, code = wait_for_http(health_url, http_timeout, interval)
        if not http_ok:
            return False, f"HTTP probe failed: {health_url} (code={code})"
        return True, f"Healthy (Dokploy: {status}, HTTP: {code})"

    return True, f"Dokploy: {status}"


def quick_health_check(client: Any, compose_id: str) -> str:
    """Non-blocking single check of compose status. Returns status string."""
    try:
        data = client.get("/compose.one", params={"composeId": compose_id})
        if isinstance(data, dict):
            return data.get("composeStatus", "unknown")
        return "unknown"
    except Exception:
        return "unreachable"
