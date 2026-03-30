"""Comprehensive dashboard overview command."""

from __future__ import annotations

import typer

from kctl_dokploy.core.callbacks import AppContext
from kctl_dokploy.core.utils import status_icon

app = typer.Typer(help="Dashboard overview of Dokploy instance.")


@app.command("show")
def show(ctx: typer.Context) -> None:
    """Show comprehensive Dokploy dashboard."""
    c: AppContext = ctx.obj
    out = c.output

    # Gather data from multiple endpoints
    projects: list = []
    servers: list = []
    try:
        projects = c.client.get("/project.all")
        if not isinstance(projects, list):
            projects = []
    except Exception:
        pass
    try:
        servers = c.client.get("/server.all")
        if not isinstance(servers, list):
            servers = []
    except Exception:
        pass

    # Count services by type and status
    compose_services: list[dict] = []
    applications: list[dict] = []
    databases: list[dict] = []
    status_counts: dict[str, int] = {}

    for p in projects:
        for comp in p.get("compose", []):
            comp["_project"] = p.get("name", "")
            compose_services.append(comp)
            s = comp.get("composeStatus", "unknown").lower()
            status_counts[s] = status_counts.get(s, 0) + 1
        for app_item in p.get("applications", []):
            app_item["_project"] = p.get("name", "")
            applications.append(app_item)
            s = app_item.get("applicationStatus", "unknown").lower()
            status_counts[s] = status_counts.get(s, 0) + 1
        for db_type in ("postgres", "redis", "mysql", "mariadb", "mongo"):
            for db in p.get(db_type, []):
                db["_type"] = db_type
                databases.append(db)

    total_services = len(compose_services) + len(applications)

    if c.json_mode:
        out.raw_json(
            {
                "projects": len(projects),
                "servers": len(servers),
                "compose_services": len(compose_services),
                "applications": len(applications),
                "databases": len(databases),
                "total_services": total_services,
                "status_counts": status_counts,
            }
        )
        return

    # Health check
    health_code = c.client.check_health()
    health_status = "[green]Healthy[/green]" if health_code == 200 else f"[red]Unhealthy ({health_code})[/red]"

    out.header("Dokploy Dashboard")
    out.text("")

    # Instance info
    sections = [
        (
            "Instance",
            [
                ("API", c.client.root_url),
                ("Health", health_status),
            ],
        ),
        (
            "Summary",
            [
                ("Projects", str(len(projects))),
                ("Servers", str(len(servers))),
                ("Compose Services", str(len(compose_services))),
                ("Applications", str(len(applications))),
                ("Databases", str(len(databases))),
                ("Total Services", str(total_services)),
            ],
        ),
    ]

    # Status breakdown
    if status_counts:
        status_kvs = []
        for status, count in sorted(status_counts.items()):
            icon = status_icon(status)
            status_kvs.append((f"{icon} {status.capitalize()}", str(count)))
        sections.append(("Service Health", status_kvs))

    out.detail("Dashboard", sections)

    # Recent services table
    if compose_services:
        out.text("")
        rows = []
        for s in compose_services[:15]:
            name = s.get("name", "")
            status = s.get("composeStatus", "unknown")
            project = s.get("_project", "")
            icon = status_icon(status)
            rows.append([name, f"{icon} {status}", project])
        out.table(
            "Compose Services",
            [("Name", "cyan"), ("Status", ""), ("Project", "green")],
            rows,
        )

    if applications:
        out.text("")
        rows = []
        for a in applications[:15]:
            name = a.get("name", "")
            status = a.get("applicationStatus", "unknown")
            project = a.get("_project", "")
            icon = status_icon(status)
            rows.append([name, f"{icon} {status}", project])
        out.table(
            "Applications",
            [("Name", "cyan"), ("Status", ""), ("Project", "green")],
            rows,
        )

    # Servers
    if servers:
        out.text("")
        rows = []
        for s in servers:
            name = s.get("name", "")
            ip = s.get("ipAddress", "-")
            status = s.get("serverStatus", "unknown")
            icon = status_icon(status)
            rows.append([name, ip, f"{icon} {status}"])
        out.table(
            "Servers",
            [("Name", "cyan"), ("IP", "dim"), ("Status", "")],
            rows,
        )
