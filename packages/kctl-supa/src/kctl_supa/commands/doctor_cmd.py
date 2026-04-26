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

    # 6. DB connectivity + 7. Disk space (reuse single SSH connection)
    db_ok = False
    db_detail = "SSH not configured"
    disk_ok = False
    disk_detail = "SSH not configured"
    if cfg.ssh_host:
        docker = _get_docker(actx)
        try:
            docker.psql("SELECT 1")
            db_ok = True
            db_detail = "SELECT 1 OK"
        except DockerError as exc:
            db_detail = str(exc)[:80]

        try:
            disk_out = docker.exec("df -h /")
            lines = [line for line in disk_out.splitlines() if "/" in line and "%" in line]
            disk_detail = lines[0].strip() if lines else disk_out.strip()[:80]
            disk_ok = True
        except DockerError as exc:
            disk_detail = str(exc)[:80]
        finally:
            docker.close()
    rows.append(("DB connectivity", db_ok, db_detail))
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


def _api_check(base_url: str, path: str, key: str, method: str = "GET", **kwargs: object) -> tuple[bool, int, str]:
    try:
        headers = {"apikey": key, "Authorization": f"Bearer {key}"}
        resp = httpx.request(method, f"{base_url}/{path.lstrip('/')}", headers=headers, timeout=10, **kwargs)
        body = resp.text[:120]
        return resp.status_code < 400, resp.status_code, body
    except Exception as exc:  # noqa: BLE001
        return False, 0, str(exc)[:80]


@app.command()
def validate(ctx: typer.Context) -> None:
    """Validate Supabase is ready for frontend apps (React/Vite/Next.js)."""
    actx: AppContext = ctx.obj
    cfg = actx.config
    out = actx.output
    base = cfg.url.rstrip("/") if cfg.url else ""

    if not base:
        out.error("No Supabase URL configured")
        raise typer.Exit(1)

    table = Table(title="Frontend Readiness Check", show_header=True, header_style="bold cyan")
    table.add_column("Check", style="cyan", min_width=28)
    table.add_column("Result")
    table.add_column("Detail")

    rows: list[tuple[str, bool, str]] = []
    anon = cfg.anon_key
    svc = cfg.service_role_key

    ok, code, body = _api_check(base, "/auth/v1/health", anon)
    rows.append(("Auth API (anon key)", ok or code == 401, f"HTTP {code}"))

    ok, code, body = _api_check(base, "/auth/v1/settings", anon)
    rows.append(("Auth settings", ok, f"HTTP {code}"))

    ok, code, body = _api_check(base, "/rest/v1/", anon)
    rows.append(("REST API (PostgREST)", ok or code == 401, f"HTTP {code}"))

    ok, code, body = _api_check(base, "/storage/v1/bucket", svc)
    rows.append(("Storage API (buckets)", ok, f"HTTP {code}"))

    ok, code, body = _api_check(base, "/storage/v1/status", anon)
    rows.append(("Storage status", ok or code == 401, f"HTTP {code}"))

    try:
        resp = httpx.options(
            f"{base}/auth/v1/signup",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "apikey,authorization,content-type",
            },
            timeout=10,
        )
        cors_origin = resp.headers.get("access-control-allow-origin", "")
        cors_ok = cors_origin in ("*", "http://localhost:5173")
        rows.append(("CORS (localhost:5173)", cors_ok, cors_origin or "not set"))
    except Exception as exc:  # noqa: BLE001
        rows.append(("CORS (localhost:5173)", False, str(exc)[:60]))

    import time as _time

    ok, code, body = _api_check(
        base,
        "/auth/v1/signup",
        anon,
        method="POST",
        json={"email": f"validate-{_time.time_ns()}@test.invalid", "password": "Val1date!Test#2026"},
    )
    smtp_fail = "error sending" in body.lower()
    if smtp_fail:
        rows.append(("SMTP (email delivery)", False, "Auth failed to send email"))
    elif ok or "confirmation" in body.lower():
        rows.append(("SMTP (email delivery)", True, "Signup + email OK"))
    else:
        rows.append(("SMTP (email delivery)", False, f"HTTP {code}: {body[:60]}"))

    if cfg.ssh_host:
        docker = _get_docker(actx)
        try:
            backend = docker.docker_exec("storage", "printenv STORAGE_BACKEND")
            is_s3 = "s3" in backend.lower()
            rows.append(("Storage backend", True, "S3" if is_s3 else f"local ({backend.strip()})"))
        except DockerError:
            rows.append(("Storage backend", False, "Cannot read config"))

        try:
            result = docker.psql(
                "SELECT extname FROM pg_extension WHERE extname IN ('pg_cron','pg_net') ORDER BY extname",
            )
            exts = [line.strip() for line in result.splitlines() if line.strip() and line.strip()[0].isalpha()]
            has_cron = any("pg_cron" in e for e in exts)
            has_net = any("pg_net" in e for e in exts)
            rows.append(("pg_cron extension", has_cron, "installed" if has_cron else "missing"))
            rows.append(("pg_net extension", has_net, "installed" if has_net else "missing"))
        except DockerError:
            rows.append(("PG extensions", False, "Cannot query"))

        try:
            result = docker.psql(
                "SELECT count(*) FROM pg_tables WHERE schemaname = 'public' "
                "AND tablename NOT IN (SELECT DISTINCT tablename FROM pg_policies WHERE schemaname = 'public')",
            )
            val = [line.strip() for line in result.splitlines() if line.strip().isdigit()]
            n = int(val[0]) if val else 0
            rows.append(("RLS coverage (public)", n == 0, f"{n} unprotected" if n > 0 else "all covered"))
        except DockerError:
            rows.append(("RLS coverage", False, "Cannot query"))

        try:
            site_url = docker.docker_exec("auth", "printenv GOTRUE_SITE_URL").strip()
            rows.append(("Auth SITE_URL", bool(site_url), site_url or "not set"))
        except DockerError:
            rows.append(("Auth SITE_URL", False, "Cannot read"))

        try:
            uri_list = docker.docker_exec("auth", "printenv GOTRUE_URI_ALLOW_LIST").strip()
            has_localhost = "localhost" in uri_list
            rows.append(
                ("Auth redirect URLs", True, f"{'+ localhost' if has_localhost else 'prod only'}: {uri_list[:50]}")
            )
        except DockerError:
            rows.append(("Auth redirect URLs", False, "Cannot read"))

        docker.close()

    all_passed = True
    for label, ok, detail in rows:
        table.add_row(label, _PASS if ok else _FAIL, detail)
        if not ok:
            all_passed = False

    rprint(table)
    if all_passed:
        out.success("Supabase is ready for frontend apps!")
    else:
        out.warn("Some checks failed - review above before connecting your app.")
        raise typer.Exit(1)
