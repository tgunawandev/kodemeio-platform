"""Deployment reports and analytics commands."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext
from kctl_dokploy.core.helpers import collect_all_services
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
    data = collect_all_services(c.client)
    all_domains: list[dict] = []
    for d in data["domains"]:
        d["serviceName"] = d.get("_service", "")
        d["serviceType"] = d.get("_serviceType", "")
        d["projectName"] = d.get("_project", "")
        all_domains.append(d)
    return all_domains


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def summary(ctx: typer.Context) -> None:
    """Overall platform summary across all projects."""
    c: AppContext = ctx.obj

    data = collect_all_services(c.client)
    s = data["summary"]

    total_compose = s.get("composes", 0)
    total_apps = s.get("applications", 0)
    domain_count = s.get("domains", 0)
    num_projects = s.get("projects", 0)

    # Count databases from environments
    total_dbs = 0
    try:
        raw_projects = c.client.get("/project.all")
        if isinstance(raw_projects, list):
            for p in raw_projects:
                for env in p.get("environments", [p]):
                    dbs_list = env.get("databases", env.get("mariadb", []))
                    if isinstance(dbs_list, list):
                        total_dbs += len(dbs_list)
    except Exception:
        pass

    # Status counts from collected services
    status_counts: dict[str, int] = {}
    for comp in data["composes"]:
        st = comp.get("composeStatus", "idle").lower()
        status_counts[st] = status_counts.get(st, 0) + 1
    for app_item in data["applications"]:
        st = app_item.get("applicationStatus", "idle").lower()
        status_counts[st] = status_counts.get(st, 0) + 1

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
                ("Projects", str(num_projects)),
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
        "projects": num_projects,
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


_INVENTORY_SORT_KEYS = {
    "name": "service",
    "service": "service",
    "server": "server",
    "project": "project",
    "status": "status",
    "domain": "domain",
    "ip": "ip",
}


@app.command()
def inventory(
    ctx: typer.Context,
    sort: Annotated[
        str,
        typer.Option("--sort", "-s", help="Sort by: name, server, project, status, domain, ip"),
    ] = "server",
    filter_server: Annotated[
        str | None,
        typer.Option("--server", help="Filter by server name or IP (substring match)"),
    ] = None,
    filter_project: Annotated[
        str | None,
        typer.Option("--project", help="Filter by project name"),
    ] = None,
    filter_status: Annotated[
        str | None,
        typer.Option("--status", help="Filter by status: online, offline"),
    ] = None,
) -> None:
    """Service inventory: service, domain, server, IP, project, status."""
    c: AppContext = ctx.obj

    data = collect_all_services(c.client)

    # Build server lookup: serverId -> {name, ip}
    server_map: dict[str, dict[str, str]] = {}
    try:
        servers = c.client.get("/server.all")
        if isinstance(servers, list):
            for s in servers:
                sid = s.get("serverId", "")
                if sid:
                    server_map[sid] = {
                        "name": s.get("name", ""),
                        "ip": s.get("ipAddress", ""),
                    }
    except Exception:
        pass

    items: list[dict] = []

    for comp in data["composes"]:
        name = comp.get("name", "")
        project = comp.get("_project", "")
        status = comp.get("composeStatus", "unknown").lower()

        sid = comp.get("serverId")
        srv = server_map.get(sid, {}) if sid else {}
        server_name = srv.get("name", "dokploy-host")
        server_ip = srv.get("ip", "-")

        domains = comp.get("domains", [])
        domain_str = ", ".join(d.get("host", "") for d in domains) if domains else "-"
        raw_status = "online" if status == "done" else "offline"
        has_https = all(d.get("https", False) for d in domains) if domains else False
        source = comp.get("sourceType", "-")
        auto_deploy = comp.get("autoDeploy", False)

        items.append(
            {
                "service": name,
                "domain": domain_str,
                "domains": [d.get("host", "") for d in domains],
                "server": server_name,
                "ip": server_ip,
                "project": project,
                "status": raw_status,
                "https": has_https,
                "source": source,
                "auto_deploy": auto_deploy,
                "type": "compose",
            }
        )

    for app_item in data["applications"]:
        name = app_item.get("name", "")
        project = app_item.get("_project", "")
        status = app_item.get("applicationStatus", "unknown").lower()

        sid = app_item.get("serverId")
        srv = server_map.get(sid, {}) if sid else {}
        server_name = srv.get("name", "dokploy-host")
        server_ip = srv.get("ip", "-")

        domains = app_item.get("domains", [])
        domain_str = ", ".join(d.get("host", "") for d in domains) if domains else "-"
        raw_status = "online" if status in ("done", "running") else "offline"
        has_https = all(d.get("https", False) for d in domains) if domains else False
        auto_deploy = app_item.get("autoDeploy", False)

        items.append(
            {
                "service": name,
                "domain": domain_str,
                "domains": [d.get("host", "") for d in domains],
                "server": server_name,
                "ip": server_ip,
                "project": project,
                "status": raw_status,
                "https": has_https,
                "source": "-",
                "auto_deploy": auto_deploy,
                "type": "app",
            }
        )

    # Filter
    if filter_server:
        q = filter_server.lower()
        items = [i for i in items if q in i["server"].lower() or q in i["ip"].lower()]
    if filter_project:
        q = filter_project.lower()
        items = [i for i in items if q in i["project"].lower()]
    if filter_status:
        q = filter_status.lower()
        items = [i for i in items if i["status"] == q]

    # Sort
    sort_key = _INVENTORY_SORT_KEYS.get(sort.lower(), "server")
    items.sort(key=lambda x: (x.get(sort_key, ""), x.get("service", "")))

    # Count summary
    online_count = sum(1 for i in items if i["status"] == "online")
    offline_count = len(items) - online_count

    rows: list[list[str]] = []
    json_data: list[dict] = []
    for item in items:
        status_label = "[green]online[/green]" if item["status"] == "online" else "[red]offline[/red]"
        https_label = "[green]yes[/green]" if item["https"] else ("[red]no[/red]" if item["domains"] else "-")
        deploy_label = "[green]auto[/green]" if item["auto_deploy"] else "manual"
        rows.append(
            [
                item["service"],
                item["domain"],
                item["server"],
                item["ip"],
                item["project"],
                https_label,
                deploy_label,
                status_label,
            ]
        )
        json_data.append(
            {
                "service": item["service"],
                "domains": item["domains"],
                "server": item["server"],
                "ip": item["ip"],
                "project": item["project"],
                "https": item["https"],
                "source": item["source"],
                "auto_deploy": item["auto_deploy"],
                "type": item["type"],
                "status": item["status"],
            }
        )

    title_parts = [f"{len(items)} services"]
    if offline_count:
        title_parts.append(f"{offline_count} offline")
    title_parts.append(f"sorted by {sort_key}")

    c.output.table(
        f"Service Inventory ({', '.join(title_parts)})",
        [
            ("Service", "cyan"),
            ("Domain", ""),
            ("Server", "green"),
            ("IP", "dim"),
            ("Project", ""),
            ("HTTPS", ""),
            ("Deploy", ""),
            ("Status", ""),
        ],
        rows,
        data_for_json=json_data,
    )


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
