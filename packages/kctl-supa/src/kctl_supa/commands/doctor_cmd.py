"""Diagnostic commands for kctl-supa."""

from __future__ import annotations

import socket

import httpx
import typer
from rich import print as rprint
from rich.table import Table

from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.docker import DockerOps
from kctl_supa.core.exceptions import DockerError

app = typer.Typer(help="Diagnose common issues.")

_PASS = "[green]PASS[/green]"
_FAIL = "[red]FAIL[/red]"


def _get_docker(actx: AppContext) -> DockerOps:
    return DockerOps(actx.config)


def _check_dns(hostname: str) -> tuple[bool, str]:
    """Resolve hostname via DNS."""
    try:
        results = socket.getaddrinfo(hostname, None)
        addr = results[0][4][0] if results else "unknown"
        return True, addr
    except socket.gaierror as exc:
        return False, str(exc)


def _check_http(url: str, timeout: float = 10.0) -> tuple[bool, str]:
    """Check HTTP connectivity."""
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True)
        return True, f"HTTP {resp.status_code}"
    except httpx.ConnectError as exc:
        return False, f"Connection error: {exc}"
    except httpx.TimeoutException:
        return False, "Timeout"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


@app.command()
def check(ctx: typer.Context) -> None:
    """Run all diagnostics."""
    actx: AppContext = ctx.obj
    cfg = actx.config

    table = Table(title="kctl-supa Diagnostics", show_header=True, header_style="bold cyan")
    table.add_column("Check", style="cyan", min_width=30)
    table.add_column("Result")
    table.add_column("Detail")

    rows: list[tuple[str, bool, str]] = []

    # 1. DNS resolution
    base_url = cfg.url.rstrip("/") if cfg.url else ""
    if base_url:
        try:
            from urllib.parse import urlparse
            hostname = urlparse(base_url).hostname or ""
        except Exception:
            hostname = ""
        if hostname:
            ok, detail = _check_dns(hostname)
            rows.append(("DNS resolution", ok, detail))
        else:
            rows.append(("DNS resolution", False, "No hostname in URL"))
    else:
        rows.append(("DNS resolution", False, "URL not configured"))

    # 2. HTTP connectivity to Kong
    if base_url:
        ok, detail = _check_http(base_url + "/")
        rows.append(("Kong HTTP", ok, detail))
    else:
        rows.append(("Kong HTTP", False, "URL not configured"))

    # 3. Auth service health
    if base_url:
        ok, detail = _check_http(base_url + "/auth/v1/health")
        rows.append(("Auth service", ok, detail))
    else:
        rows.append(("Auth service", False, "URL not configured"))

    # 4. REST service health
    if base_url:
        ok, detail = _check_http(base_url + "/rest/v1/")
        rows.append(("REST service", ok, detail))
    else:
        rows.append(("REST service", False, "URL not configured"))

    # 5. Storage service health
    if base_url:
        ok, detail = _check_http(base_url + "/storage/v1/status")
        rows.append(("Storage service", ok, detail))
    else:
        rows.append(("Storage service", False, "URL not configured"))

    # 6. DB connectivity via Docker
    db_ok = False
    db_detail = "SSH not configured"
    if cfg.ssh_host:
        try:
            docker = _get_docker(actx)
            docker.psql("SELECT 1")
            docker.close()
            db_ok = True
            db_detail = "SELECT 1 OK"
        except DockerError as exc:
            db_detail = str(exc)[:80]
    rows.append(("DB connectivity", db_ok, db_detail))

    # 7. Disk space
    disk_ok = False
    disk_detail = "SSH not configured"
    if cfg.ssh_host:
        try:
            docker = _get_docker(actx)
            disk_out = docker.exec("df -h /")
            docker.close()
            # Extract usage percentage from df output
            lines = [l for l in disk_out.splitlines() if "/" in l and "%" in l]
            disk_detail = lines[0].strip() if lines else disk_out.strip()[:80]
            disk_ok = True
        except DockerError as exc:
            disk_detail = str(exc)[:80]
    rows.append(("Disk space", disk_ok, disk_detail))

    # Build table
    all_passed = True
    for label, ok, detail in rows:
        status = _PASS if ok else _FAIL
        table.add_row(label, status, detail)
        if not ok:
            all_passed = False

    rprint(table)

    if all_passed:
        typer.echo("\nAll checks passed.")
    else:
        typer.echo("\nSome checks failed. Review the details above.")
        raise typer.Exit(1)
