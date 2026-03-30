"""Domain management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Manage Dokploy domains.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all domains across all projects."""
    c: AppContext = ctx.obj
    projects = c.client.get("/project.all")
    if not isinstance(projects, list):
        projects = []
    all_domains: list[dict] = []
    for p in projects:
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
                    d["projectName"] = p.get("name", "")
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
                    d["projectName"] = p.get("name", "")
                    all_domains.append(d)
    rows = []
    for d in all_domains:
        host = d.get("host", "")
        port = str(d.get("port", "80"))
        https = "yes" if d.get("https") else "no"
        cert = d.get("certificateType", "none")
        service = d.get("serviceName", "")
        rows.append([host, port, https, cert, service])
    c.output.table(
        "Domains",
        [("Host", "cyan"), ("Port", ""), ("HTTPS", ""), ("Certificate", ""), ("Service", "green")],
        rows,
        data_for_json=all_domains,
    )


@app.command()
def get(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
) -> None:
    """Get domains for a specific compose service."""
    c: AppContext = ctx.obj
    data = c.client.get("/domain.byComposeId", params={"composeId": compose_id})
    if not isinstance(data, list):
        data = []
    rows = []
    for d in data:
        host = d.get("host", "")
        port = str(d.get("port", "80"))
        https = "yes" if d.get("https") else "no"
        cert = d.get("certificateType", "none")
        did = d.get("domainId", "")[:12]
        rows.append([did, host, port, https, cert])
    c.output.table(
        f"Domains for {compose_id}",
        [("ID", "dim"), ("Host", "cyan"), ("Port", ""), ("HTTPS", ""), ("Certificate", "")],
        rows,
        data_for_json=data,
    )


@app.command()
def create(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
    host: Annotated[str, typer.Option("--host", "-h", help="Hostname (e.g. app.example.com)")],
    port: Annotated[int, typer.Option("--port", "-p", help="Port number")] = 80,
    https: Annotated[bool, typer.Option("--https/--no-https", help="Enable HTTPS")] = True,
    cert_type: Annotated[str, typer.Option("--cert", help="Certificate type")] = "letsencrypt",
    service_name: Annotated[str | None, typer.Option("--service", help="Docker Compose service name")] = None,
) -> None:
    """Add a domain to a compose service."""
    c: AppContext = ctx.obj
    payload: dict = {
        "composeId": compose_id,
        "host": host,
        "port": port,
        "https": https,
        "certificateType": cert_type,
    }
    if service_name:
        payload["serviceName"] = service_name
    result = c.client.post("/domain.create", json=payload)
    did = result.get("domainId", "") if isinstance(result, dict) else ""
    c.output.success(f"Domain '{host}' added: {did}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def delete(
    ctx: typer.Context,
    domain_id: Annotated[str, typer.Argument(help="Domain ID to remove")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Remove a domain."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Remove domain '{domain_id}'?", abort=True)
    result = c.client.delete("/domain.delete", json={"domainId": domain_id})
    c.output.success(f"Domain '{domain_id}' removed")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def update(
    ctx: typer.Context,
    domain_id: Annotated[str, typer.Argument(help="Domain ID to update")],
    host: Annotated[str | None, typer.Option("--host", "-h", help="New hostname")] = None,
    port: Annotated[int | None, typer.Option("--port", "-p", help="New port")] = None,
    https: Annotated[bool | None, typer.Option("--https/--no-https", help="Enable/disable HTTPS")] = None,
    cert_type: Annotated[str | None, typer.Option("--cert", help="Certificate type")] = None,
    service_name: Annotated[str | None, typer.Option("--service", help="Docker Compose service name")] = None,
) -> None:
    """Update a domain configuration."""
    c: AppContext = ctx.obj
    payload: dict = {"domainId": domain_id}
    if host is not None:
        payload["host"] = host
    if port is not None:
        payload["port"] = port
    if https is not None:
        payload["https"] = https
    if cert_type is not None:
        payload["certificateType"] = cert_type
    if service_name is not None:
        payload["serviceName"] = service_name
    if len(payload) == 1:
        c.output.error("No update options provided.")
        raise typer.Exit(1)
    result = c.client.post("/domain.update", json=payload)
    c.output.success(f"Domain '{domain_id}' updated")
    if c.json_mode:
        c.output.raw_json(result)
