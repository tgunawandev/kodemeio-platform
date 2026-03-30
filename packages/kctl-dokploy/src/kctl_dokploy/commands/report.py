"""Deployment reports and analytics commands."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext
from kctl_dokploy.core.utils import fmt_duration, status_icon

app = typer.Typer(help="Deployment reports and analytics.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_period(period: str) -> datetime | None:
    """Convert a period string to a UTC cutoff datetime, or None for 'all'."""
    now = datetime.now(tz=UTC)
    mapping: dict[str, timedelta] = {
        "last_24h": timedelta(hours=24),
        "last_7d": timedelta(days=7),
        "last_30d": timedelta(days=30),
    }
    delta = mapping.get(period)
    return (now - delta) if delta else None


def _parse_iso(iso_str: str | None) -> datetime | None:
    """Parse an ISO timestamp to a timezone-aware datetime, or None."""
    if not iso_str:
        return None
    try:
        import re

        cleaned = re.sub(r"Z$", "+00:00", iso_str)
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, TypeError):
        return None


def _collect_all_domains(c: AppContext) -> list[dict]:
    """Iterate projects and collect domains from compose + application services."""
    projects = c.client.get("/project.all")
    if not isinstance(projects, list):
        return []
    all_domains: list[dict] = []
    for p in projects:
        project_name = p.get("name", "")
        for comp in p.get("compose", []):
            cid = comp.get("composeId", "")
            comp_name = comp.get("name", "")
            try:
                detail = c.client.get("/compose.one", params={"composeId": cid})
            except Exception:
                continue
            if isinstance(detail, dict):
                for d in detail.get("domains", []):
                    d["serviceName"] = comp_name
                    d["serviceType"] = "compose"
                    d["projectName"] = project_name
                    all_domains.append(d)
        for app_item in p.get("applications", []):
            aid = app_item.get("applicationId", "")
            app_name = app_item.get("name", "")
            try:
                detail = c.client.get("/application.one", params={"applicationId": aid})
            except Exception:
                continue
            if isinstance(detail, dict):
                for d in detail.get("domains", []):
                    d["serviceName"] = app_name
                    d["serviceType"] = "application"
                    d["projectName"] = project_name
                    all_domains.append(d)
    return all_domains


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def summary(ctx: typer.Context) -> None:
    """Overall platform summary across all projects."""
    c: AppContext = ctx.obj

    projects = c.client.get("/project.all")
    if not isinstance(projects, list):
        projects = []

    total_compose = 0
    total_apps = 0
    total_dbs = 0
    status_counts: dict[str, int] = {}

    for p in projects:
        compose_list = p.get("compose", [])
        apps_list = p.get("applications", [])
        dbs_list = p.get("databases", p.get("mariadb", []))
        if not isinstance(dbs_list, list):
            dbs_list = []

        total_compose += len(compose_list)
        total_apps += len(apps_list)
        total_dbs += len(dbs_list)

        for comp in compose_list:
            st = comp.get("composeStatus", "idle").lower()
            status_counts[st] = status_counts.get(st, 0) + 1
        for app_item in apps_list:
            st = app_item.get("applicationStatus", "idle").lower()
            status_counts[st] = status_counts.get(st, 0) + 1

    # Domain count
    try:
        all_domains = _collect_all_domains(c)
        domain_count = len(all_domains)
    except Exception:
        domain_count = 0

    # Certificate count
    try:
        certs = c.client.get("/certificates.all")
        cert_count = len(certs) if isinstance(certs, list) else 0
    except Exception:
        cert_count = 0

    # Server count
    try:
        servers = c.client.get("/server.all")
        server_count = len(servers) if isinstance(servers, list) else 0
    except Exception:
        server_count = 0

    sections = [
        (
            "Platform Overview",
            [
                ("Projects", str(len(projects))),
                ("Compose Services", str(total_compose)),
                ("Applications", str(total_apps)),
                ("Databases", str(total_dbs)),
                ("Domains", str(domain_count)),
                ("Certificates", str(cert_count)),
                ("Servers", str(server_count)),
            ],
        ),
        (
            "Service Status Breakdown",
            [(k, str(v)) for k, v in sorted(status_counts.items())],
        ),
    ]

    json_data = {
        "projects": len(projects),
        "compose": total_compose,
        "applications": total_apps,
        "databases": total_dbs,
        "domains": domain_count,
        "certificates": cert_count,
        "servers": server_count,
        "statusBreakdown": status_counts,
    }

    c.output.detail("Platform Summary", sections, data_for_json=json_data)


@app.command()
def deployments(
    ctx: typer.Context,
    period: Annotated[
        str,
        typer.Option(
            "--period",
            "-p",
            help="Time period: last_24h, last_7d, last_30d, all",
        ),
    ] = "last_7d",
) -> None:
    """Deployment analytics with temporal filtering."""
    c: AppContext = ctx.obj

    cutoff = _parse_period(period)
    try:
        all_deployments = c.client.get("/deployment.allCentralized")
        if not isinstance(all_deployments, list):
            all_deployments = []
    except Exception:
        all_deployments = []

    # Filter by period
    filtered: list[dict] = []
    for d in all_deployments:
        if cutoff:
            created_dt = _parse_iso(d.get("createdAt"))
            if created_dt and created_dt < cutoff:
                continue
        filtered.append(d)

    total = len(filtered)
    success_count = sum(1 for d in filtered if d.get("status", "").lower() in ("done", "running"))
    failure_count = sum(1 for d in filtered if d.get("status", "").lower() in ("error", "failed"))
    other_count = total - success_count - failure_count
    success_rate = (success_count / total * 100) if total > 0 else 0.0

    # Calculate average duration from createdAt -> endedAt
    durations: list[float] = []
    for d in filtered:
        start_dt = _parse_iso(d.get("createdAt"))
        end_dt = _parse_iso(d.get("endedAt"))
        if start_dt and end_dt:
            dur = (end_dt - start_dt).total_seconds()
            if dur >= 0:
                durations.append(dur)

    avg_duration_s = sum(durations) / len(durations) if durations else 0.0

    # Group failures by error type / status
    failure_types: dict[str, int] = {}
    for d in filtered:
        st = d.get("status", "").lower()
        if st in ("error", "failed"):
            error_type = d.get("errorType", d.get("deploymentType", "unknown"))
            failure_types[error_type] = failure_types.get(error_type, 0) + 1

    rows = [
        [
            period,
            str(total),
            str(success_count),
            str(failure_count),
            str(other_count),
            f"{success_rate:.1f}%",
            fmt_duration(avg_duration_s),
        ],
    ]

    c.output.table(
        "Deployment Analytics",
        [
            ("Period", "cyan"),
            ("Total", ""),
            ("Success", "green"),
            ("Failed", "red"),
            ("Other", "dim"),
            ("Rate", ""),
            ("Avg Duration", ""),
        ],
        rows,
        data_for_json={
            "period": period,
            "total": total,
            "success": success_count,
            "failed": failure_count,
            "other": other_count,
            "successRate": round(success_rate, 1),
            "avgDurationSeconds": round(avg_duration_s, 1),
            "avgDuration": fmt_duration(avg_duration_s),
            "failureTypes": failure_types,
        },
    )

    # Show failure breakdown if any
    if failure_types and not c.json_mode:
        failure_rows = [[ft, str(cnt)] for ft, cnt in sorted(failure_types.items(), key=lambda x: -x[1])]
        c.output.table(
            "Failure Breakdown",
            [("Error Type", "red"), ("Count", "")],
            failure_rows,
        )


@app.command()
def domains(ctx: typer.Context) -> None:
    """Domain health report across all projects."""
    c: AppContext = ctx.obj

    all_domains = _collect_all_domains(c)

    rows = []
    warnings = 0
    for d in all_domains:
        host = d.get("host", "")
        is_https = d.get("https", False)
        https_label = "[green]yes[/green]" if is_https else "[red]no[/red]"
        cert_type = d.get("certificateType", "none")
        service = d.get("serviceName", "")
        project = d.get("projectName", "")
        svc_type = d.get("serviceType", "")

        if not is_https:
            warnings += 1
            host = f"[yellow]{host}[/yellow]"

        rows.append([host, https_label, cert_type, service, svc_type, project])

    c.output.table(
        f"Domain Health Report ({len(all_domains)} domains, {warnings} warnings)",
        [
            ("Host", "cyan"),
            ("HTTPS", ""),
            ("Certificate", ""),
            ("Service", "green"),
            ("Type", "dim"),
            ("Project", ""),
        ],
        rows,
        data_for_json=all_domains,
    )

    if warnings and not c.json_mode:
        c.output.warn(f"{warnings} domain(s) without HTTPS detected")


@app.command()
def resources(ctx: typer.Context) -> None:
    """Resource utilization summary across servers."""
    c: AppContext = ctx.obj

    # Fetch servers
    servers = c.client.get("/server.all")
    if not isinstance(servers, list):
        servers = []

    server_info: list[tuple[str, str]] = []
    for s in servers:
        name = s.get("name", "unknown")
        ip = s.get("ipAddress", "-")
        status = s.get("serverStatus", "unknown")
        docker_ver = s.get("dockerVersion", "-")
        server_info.append(
            (
                "Server",
                [
                    ("Name", name),
                    ("IP", ip),
                    ("Status", f"{status_icon(status)} {status}"),
                    ("Docker", str(docker_ver)),
                ],
            )
        )

    # Attempt to fetch docker disk usage
    disk_info: list[tuple[str, list[tuple[str, str]]]] = []
    disk_data: dict | None = None
    disk_info = [
        (
            "Docker Disk Usage",
            [("Status", "Not available via Dokploy API — use 'docker system df' on server")],
        ),
    ]

    sections = server_info + disk_info

    json_data = {
        "servers": servers,
        "diskUsage": disk_data,
    }

    c.output.detail("Resource Utilization", sections, data_for_json=json_data)
