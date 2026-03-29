"""HTTP-based monitoring utilities for kctl-* CLI tools."""

from __future__ import annotations

import socket
import ssl
from datetime import UTC, datetime

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]


def health_check_url(url: str, timeout: int = 10) -> dict:  # type: ignore[type-arg]
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=timeout)  # type: ignore[union-attr]
        return {
            "url": url,
            "status_code": resp.status_code,
            "healthy": 200 <= resp.status_code < 400,
            "latency_ms": round(resp.elapsed.total_seconds() * 1000, 1),
            "body_preview": resp.text[:200],
        }
    except Exception as e:
        return {"url": url, "status_code": 0, "healthy": False, "latency_ms": 0, "error": str(e)}


def ssl_check(domain: str, port: int = 443) -> dict:  # type: ignore[type-arg]
    try:
        ctx = ssl.create_default_context()
        with (
            socket.create_connection((domain, port), timeout=10) as sock,
            ctx.wrap_socket(sock, server_hostname=domain) as ssock,
        ):
            cert = ssock.getpeercert()
        if not cert:
            return {"domain": domain, "valid": False, "error": "No certificate"}
        not_after = cert.get("notAfter", "")
        try:
            expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=UTC)
            days_remaining = (expiry - datetime.now(UTC)).days
        except (ValueError, TypeError):
            days_remaining = -1
        issuer = ""
        for item in cert.get("issuer", ()):
            for key, value in item:
                if key == "organizationName":
                    issuer = value
                    break
        return {
            "domain": domain,
            "valid": True,
            "expiry": not_after,
            "days_remaining": days_remaining,
            "issuer": issuer,
        }
    except Exception as e:
        return {"domain": domain, "valid": False, "error": str(e)}


def dns_check(domain: str) -> dict:  # type: ignore[type-arg]
    try:
        results = socket.getaddrinfo(domain, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
        if results:
            return {"domain": domain, "resolved": True, "ip": results[0][4][0], "records": len(results)}
        return {"domain": domain, "resolved": False, "error": "No records"}
    except OSError as e:
        return {"domain": domain, "resolved": False, "error": str(e)}
