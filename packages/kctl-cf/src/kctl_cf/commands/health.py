"""Comprehensive health check commands for Cloudflare infrastructure."""

from __future__ import annotations

import os
import socket
import time
from dataclasses import dataclass, field
from typing import Annotated, Any

import typer

from kctl_cloudflare.core.callbacks import AppContext
from kctl_cloudflare.core.config import resolve_active_profile_name
from kctl_cloudflare.core.exceptions import KctlError
from kctl_cloudflare.core.utils import status_color, tunnel_status_color

app = typer.Typer(help="Health checks.")


# ---------------------------------------------------------------------------
# Health check result model
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    """Single health check outcome."""

    name: str
    passed: bool
    summary: str
    details: list[tuple[str, str]] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RICH_STRIP_TAGS = (
    "[green]",
    "[/green]",
    "[red]",
    "[/red]",
    "[yellow]",
    "[/yellow]",
    "[dim]",
    "[/dim]",
    "[bold green]",
    "[/bold green]",
    "[bold yellow]",
    "[/bold yellow]",
    "[bold red]",
    "[/bold red]",
)


def _colored(text: str, *, ok: bool) -> str:
    """Wrap *text* in green (ok=True) or red (ok=False) Rich markup."""
    tag = "green" if ok else "red"
    return f"[{tag}]{text}[/{tag}]"


def _warn_colored(text: str) -> str:
    """Wrap *text* in yellow Rich markup."""
    return f"[yellow]{text}[/yellow]"


def _strip_rich(text: str) -> str:
    """Remove Rich markup tags for plain-text output (webhooks)."""
    result = text
    for tag in _RICH_STRIP_TAGS:
        result = result.replace(tag, "")
    return result


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_token(c: AppContext) -> CheckResult:
    """Verify the API token is active via /user/tokens/verify."""
    name = "API Token"
    try:
        result = c.client.check_health()
        token_status = result.get("status", "unknown") if isinstance(result, dict) else "unknown"
        passed = token_status == "active"
        styled = _colored(token_status, ok=passed)
        return CheckResult(
            name=name,
            passed=passed,
            summary=styled,
            details=[("Token status", styled)] if not passed else [],
            data={"token_status": token_status},
        )
    except KctlError as exc:
        return CheckResult(
            name=name,
            passed=False,
            summary="[red]unreachable[/red]",
            details=[("Error", str(exc))],
            data={"error": str(exc)},
        )


def _check_account(c: AppContext) -> CheckResult:
    """Verify the configured account ID resolves."""
    name = "Account Access"
    account_id = c.client.account_id
    if not account_id:
        return CheckResult(
            name=name,
            passed=False,
            summary="[red]not configured[/red]",
            details=[("Account ID", "[dim]not set[/dim]")],
            data={"configured": False},
        )
    try:
        result = c.client.get(f"/accounts/{account_id}")
        acct_name = result.get("name", "unknown") if isinstance(result, dict) else "unknown"
        return CheckResult(
            name=name,
            passed=True,
            summary=_colored(acct_name, ok=True),
            details=[],
            data={"account_id": account_id, "account_name": acct_name},
        )
    except KctlError as exc:
        return CheckResult(
            name=name,
            passed=False,
            summary="[red]inaccessible[/red]",
            details=[("Error", str(exc))],
            data={"account_id": account_id, "error": str(exc)},
        )


def _check_zones(c: AppContext) -> CheckResult:
    """Count active zones and list them."""
    name = "Zone Health"
    try:
        zones = c.client.get("/zones", params={"per_page": 50})
        zone_list: list[dict[str, Any]] = zones if isinstance(zones, list) else []
        active = [z for z in zone_list if z.get("status") == "active"]
        total = len(zone_list)
        active_count = len(active)

        details: list[tuple[str, str]] = []
        for z in zone_list:
            zname = z.get("name", "?")
            zstatus = z.get("status", "unknown")
            details.append((zname, status_color(zstatus)))

        passed = active_count > 0
        label = f"{active_count}/{total} active"
        if active_count == total:
            summary = _colored(label, ok=True)
        else:
            summary = _warn_colored(label)

        return CheckResult(
            name=name,
            passed=passed,
            summary=summary,
            details=details,
            data={
                "total": total,
                "active": active_count,
                "zones": [{"name": z.get("name"), "status": z.get("status")} for z in zone_list],
            },
        )
    except KctlError as exc:
        return CheckResult(
            name=name,
            passed=False,
            summary="[red]failed[/red]",
            details=[("Error", str(exc))],
            data={"error": str(exc)},
        )


def _check_ssl(c: AppContext) -> CheckResult:
    """Check SSL/TLS mode for each zone (warn if not full or strict)."""
    name = "SSL Configuration"
    try:
        zones = c.client.get("/zones", params={"per_page": 50})
        zone_list: list[dict[str, Any]] = zones if isinstance(zones, list) else []
        if not zone_list:
            return CheckResult(
                name=name,
                passed=True,
                summary="[dim]no zones[/dim]",
                data={"zones": []},
            )

        details: list[tuple[str, str]] = []
        zone_ssl: list[dict[str, str]] = []
        warnings = 0

        for z in zone_list:
            zone_id = z.get("id", "")
            zone_name = z.get("name", "?")
            try:
                ssl_result = c.client.get(f"/zones/{zone_id}/settings/ssl")
                ssl_mode = ssl_result.get("value", "unknown") if isinstance(ssl_result, dict) else "unknown"
            except Exception:
                ssl_mode = "unknown"

            secure = ssl_mode in ("full", "strict")
            if not secure:
                warnings += 1
            styled = _colored(ssl_mode, ok=secure) if secure else _warn_colored(ssl_mode)
            details.append((zone_name, styled))
            zone_ssl.append({"zone": zone_name, "ssl_mode": ssl_mode})

        passed = warnings == 0
        if passed:
            summary = _colored(f"all {len(zone_list)} zones secure", ok=True)
        else:
            summary = _warn_colored(f"{warnings}/{len(zone_list)} zones insecure")

        return CheckResult(
            name=name,
            passed=passed,
            summary=summary,
            details=details,
            data={"zones": zone_ssl, "warnings": warnings},
        )
    except KctlError as exc:
        return CheckResult(
            name=name,
            passed=False,
            summary="[red]failed[/red]",
            details=[("Error", str(exc))],
            data={"error": str(exc)},
        )


def _check_tunnels(c: AppContext) -> CheckResult:
    """List tunnels and check healthy vs total."""
    name = "Tunnel Health"
    account_id = c.client.account_id
    if not account_id:
        return CheckResult(
            name=name,
            passed=True,
            summary="[dim]no account ID[/dim]",
            data={"skipped": True},
        )
    try:
        tunnels = c.client.get(
            f"/accounts/{account_id}/cfd_tunnel",
            params={"is_deleted": False, "per_page": 50},
        )
        tunnel_list: list[dict[str, Any]] = tunnels if isinstance(tunnels, list) else []
        if not tunnel_list:
            return CheckResult(
                name=name,
                passed=True,
                summary="[dim]no tunnels[/dim]",
                data={"total": 0},
            )

        details: list[tuple[str, str]] = []
        healthy_count = 0
        tunnel_data: list[dict[str, str]] = []

        for t in tunnel_list:
            tname = t.get("name", "?")
            status = t.get("status", "unknown")
            conns = t.get("connections", [])
            # Derive health from active connections if status field is absent
            if status == "unknown" and isinstance(conns, list) and conns:
                status = "healthy"
            elif status == "unknown" and not conns:
                status = "inactive"

            if status.lower() in ("healthy", "active"):
                healthy_count += 1
            details.append((tname, tunnel_status_color(status)))
            tunnel_data.append({"name": tname, "status": status})

        total = len(tunnel_list)
        passed = healthy_count == total
        label = f"{healthy_count}/{total} healthy"
        summary = _colored(label, ok=True) if passed else _warn_colored(label)

        return CheckResult(
            name=name,
            passed=passed,
            summary=summary,
            details=details,
            data={"total": total, "healthy": healthy_count, "tunnels": tunnel_data},
        )
    except KctlError as exc:
        return CheckResult(
            name=name,
            passed=False,
            summary="[red]failed[/red]",
            details=[("Error", str(exc))],
            data={"error": str(exc)},
        )


def _check_dns_resolution(c: AppContext) -> CheckResult:
    """Verify the primary domain resolves via socket lookup."""
    name = "DNS Resolution"
    try:
        zones = c.client.get("/zones", params={"per_page": 1, "status": "active"})
        zone_list: list[dict[str, Any]] = zones if isinstance(zones, list) else []
        if not zone_list:
            return CheckResult(
                name=name,
                passed=True,
                summary="[dim]no zones to check[/dim]",
                data={"skipped": True},
            )

        domain = zone_list[0].get("name", "")
        if not domain:
            return CheckResult(
                name=name,
                passed=False,
                summary="[red]no domain found[/red]",
                data={"error": "empty zone name"},
            )

        try:
            addrs = socket.getaddrinfo(domain, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            ips = sorted({addr[4][0] for addr in addrs})
            ip_display = ", ".join(ips[:3])
            return CheckResult(
                name=name,
                passed=True,
                summary=_colored(f"{domain} -> {ip_display}", ok=True),
                details=[(domain, ip) for ip in ips],
                data={"domain": domain, "ips": ips},
            )
        except socket.gaierror as exc:
            return CheckResult(
                name=name,
                passed=False,
                summary=_colored(f"{domain} unresolvable", ok=False),
                details=[("Error", str(exc))],
                data={"domain": domain, "error": str(exc)},
            )
    except KctlError as exc:
        return CheckResult(
            name=name,
            passed=False,
            summary="[red]failed[/red]",
            details=[("Error", str(exc))],
            data={"error": str(exc)},
        )


# ---------------------------------------------------------------------------
# Webhook notification
# ---------------------------------------------------------------------------


def _send_webhook_notification(
    results: list[CheckResult],
    passed: int,
    total: int,
    profile: str,
) -> str | None:
    """Send health check results to a Mattermost-compatible webhook.

    Returns error message on failure, None on success.
    """
    webhook_url = os.environ.get("KCTL_CLOUDFLARE_WEBHOOK_URL") or os.environ.get("MATTERMOST_WEBHOOK_URL")
    if not webhook_url:
        return "No webhook URL configured (set KCTL_CLOUDFLARE_WEBHOOK_URL or MATTERMOST_WEBHOOK_URL)"

    channel = os.environ.get("KCTL_CLOUDFLARE_WEBHOOK_CHANNEL") or os.environ.get("MATTERMOST_CHANNEL")

    icon = ":white_check_mark:" if passed == total else ":warning:"
    lines = [
        f"{icon} **Cloudflare Health: {passed}/{total} checks passed** (profile: `{profile}`)",
        "",
    ]
    for r in results:
        mark = ":white_check_mark:" if r.passed else ":x:"
        clean_summary = _strip_rich(r.summary)
        lines.append(f"- {mark} **{r.name}**: {clean_summary}")

    payload: dict[str, Any] = {"text": "\n".join(lines)}
    if channel:
        payload["channel"] = channel

    try:
        import httpx

        resp = httpx.post(webhook_url, json=payload, timeout=10.0)
        resp.raise_for_status()
    except Exception as exc:
        return f"Webhook failed: {exc}"
    return None


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------


@app.command("check")
def check(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously monitor")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Watch interval in seconds")] = 10,
    notify: Annotated[
        bool,
        typer.Option("--notify", "-n", help="Send results via webhook (Mattermost-compatible)"),
    ] = False,
) -> None:
    """Run comprehensive Cloudflare health checks (6 checks, scored)."""
    c: AppContext = ctx.obj
    out = c.output
    active = resolve_active_profile_name(c.profile)

    def _run_checks() -> None:
        checks = [
            _check_token(c),
            _check_account(c),
            _check_zones(c),
            _check_ssl(c),
            _check_tunnels(c),
            _check_dns_resolution(c),
        ]

        passed_count = sum(1 for r in checks if r.passed)
        total = len(checks)

        # Build summary section rows
        summary_rows: list[tuple[str, str]] = [("Profile", active)]
        for r in checks:
            mark = _colored("PASS", ok=True) if r.passed else _colored("FAIL", ok=False)
            summary_rows.append((r.name, f"{mark}  {r.summary}"))

        # Score with color
        score_label = f"{passed_count}/{total}"
        if passed_count == total:
            score_display = f"[bold green]{score_label}[/bold green]"
        elif passed_count >= total - 1:
            score_display = f"[bold yellow]{score_label}[/bold yellow]"
        else:
            score_display = f"[bold red]{score_label}[/bold red]"
        summary_rows.append(("Score", score_display))

        # Detail sections for checks that have extra info
        sections: list[tuple[str, list[tuple[str, str]]]] = [("Summary", summary_rows)]
        for r in checks:
            if r.details:
                sections.append((r.name, r.details))

        # JSON data
        json_data: dict[str, Any] = {
            "healthy": passed_count == total,
            "score": score_label,
            "passed": passed_count,
            "total": total,
            "profile": active,
            "checks": {r.name.lower().replace(" ", "_"): r.data for r in checks},
        }

        out.detail("Cloudflare Health", sections, data_for_json=json_data)

        # Print final score line in pretty mode
        if passed_count == total:
            out.success(f"All {total} checks passed")
        elif passed_count >= total - 1:
            out.warn(f"{passed_count}/{total} checks passed")
        else:
            out.error(f"{passed_count}/{total} checks passed")

        # Webhook notification
        if notify:
            err = _send_webhook_notification(checks, passed_count, total, active)
            if err:
                out.warn(f"Notification: {err}")
            else:
                out.info("Notification sent to webhook")

        # Exit with failure if any check failed (unless watching)
        if passed_count < total and not watch:
            raise typer.Exit(1)

    try:
        _run_checks()
    except KctlError as exc:
        out.error(f"Health check error: {exc}")
        if not watch:
            raise typer.Exit(1) from exc

    if watch:
        try:
            while True:
                time.sleep(interval)
                out.header(f"Check at {time.strftime('%H:%M:%S')}")
                try:
                    _run_checks()
                except KctlError as exc:
                    out.error(f"Health check error: {exc}")
        except KeyboardInterrupt:
            out.info("Stopped watching")
