"""Deployment history commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Manage Dokploy deployments.")


@app.command("list")
def list_(
    ctx: typer.Context,
    compose_id: Annotated[str | None, typer.Option("--compose", "-c", help="Filter by compose ID")] = None,
    application_id: Annotated[str | None, typer.Option("--application", "-a", help="Filter by application ID")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum number of deployments")] = 20,
) -> None:
    """List deployments, optionally filtered by compose or application."""
    c: AppContext = ctx.obj
    if compose_id:
        deployments = c.client.get("/deployment.allByCompose", params={"composeId": compose_id})
    elif application_id:
        deployments = c.client.get("/deployment.all", params={"applicationId": application_id})
    else:
        c.output.error("Either --compose or --application is required")
        raise typer.Exit(1)
    if not isinstance(deployments, list):
        deployments = []
    # Sort newest first and apply limit
    deployments = sorted(deployments, key=lambda d: d.get("createdAt", ""), reverse=True)[:limit]
    rows = []
    for d in deployments:
        did = d.get("deploymentId", "")[:12]
        status = d.get("status", "unknown")
        deploy_type = d.get("deploymentType", "-")
        created = d.get("createdAt", "")
        title = d.get("title", d.get("description", "-"))
        rows.append([did, status, deploy_type, created, str(title)])
    c.output.table(
        "Deployments",
        [("ID", "dim"), ("Status", "cyan"), ("Type", ""), ("Created", ""), ("Title", "")],
        rows,
        data_for_json=deployments,
    )


@app.command()
def get(
    ctx: typer.Context,
    deployment_id: Annotated[str, typer.Argument(help="Deployment ID")],
) -> None:
    """Get deployment details."""
    c: AppContext = ctx.obj
    # deployment.one is not available; fetch all centralized and filter
    all_deps = c.client.get("/deployment.allCentralized")
    data = next(
        (d for d in (all_deps if isinstance(all_deps, list) else []) if d.get("deploymentId") == deployment_id), None
    )
    if not isinstance(data, dict):
        c.output.error(f"Deployment '{deployment_id}' not found")
        raise typer.Exit(1)
    status = data.get("status", "unknown")
    deploy_type = data.get("deploymentType", "unknown")
    created = data.get("createdAt", "-")
    ended = data.get("endedAt", "-")
    title = data.get("title", data.get("description", "-"))
    sections = [
        (
            "Deployment",
            [
                ("ID", data.get("deploymentId", "")),
                ("Status", status),
                ("Type", deploy_type),
                ("Created", created),
                ("Ended", str(ended)),
                ("Title", str(title)),
            ],
        ),
    ]
    c.output.detail(f"Deployment: {deployment_id}", sections, data_for_json=data)


@app.command("logs")
def logs_(
    ctx: typer.Context,
    deployment_id: Annotated[str, typer.Argument(help="Deployment ID")],
) -> None:
    """Show logs for a specific deployment."""
    c: AppContext = ctx.obj
    # deployment.log is not available; fetch from centralized list
    all_deps = c.client.get("/deployment.allCentralized")
    dep = next(
        (d for d in (all_deps if isinstance(all_deps, list) else []) if d.get("deploymentId") == deployment_id), None
    )
    log_text = dep.get("logPath", dep.get("log", dep.get("logs", ""))) if isinstance(dep, dict) else ""
    if c.json_mode:
        c.output.raw_json({"deploymentId": deployment_id, "logs": log_text})
    else:
        c.output.header(f"Deployment Logs: {deployment_id}")
        c.output.text(str(log_text))


@app.command()
def redeploy(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID to redeploy")],
) -> None:
    """Trigger a redeployment for a compose service (stop + deploy)."""
    c: AppContext = ctx.obj
    out = c.output
    out.info(f"Redeploying compose '{compose_id}'...")
    try:
        c.client.post("/compose.stop", json={"composeId": compose_id})
        out.info("Stopped. Triggering deployment...")
    except Exception:
        out.warn("Stop failed or service was not running; proceeding with deploy")
    result = c.client.post("/compose.deploy", json={"composeId": compose_id})
    out.success(f"Compose '{compose_id}' redeployed")
    if c.json_mode:
        out.raw_json(result)


@app.command()
def cancel(
    ctx: typer.Context,
    deployment_id: Annotated[str, typer.Argument(help="Deployment ID to cancel")],
) -> None:
    """Cancel a running deployment."""
    c: AppContext = ctx.obj
    c.output.info(f"Cancelling deployment '{deployment_id}'...")
    result = c.client.post("/deployment.killProcess", json={"deploymentId": deployment_id})
    c.output.success(f"Deployment '{deployment_id}' cancelled")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("by-server")
def by_server(
    ctx: typer.Context,
    server: Annotated[str, typer.Option("--server", "-s", help="Server ID")],
) -> None:
    """List all deployments for a specific server."""
    c: AppContext = ctx.obj
    data = c.client.get("/deployment.allByServer", params={"serverId": server})
    if not isinstance(data, list):
        data = []
    rows = []
    for d in data:
        did = d.get("deploymentId", "")[:12]
        status = d.get("status", "unknown")
        deploy_type = d.get("deploymentType", "-")
        created = d.get("createdAt", "")
        title = d.get("title", d.get("description", "-"))
        rows.append([did, status, deploy_type, created, str(title)])
    c.output.table(
        f"Deployments for Server: {server}",
        [("ID", "dim"), ("Status", "cyan"), ("Type", ""), ("Created", ""), ("Title", "")],
        rows,
        data_for_json=data,
    )


@app.command("queue")
def queue(ctx: typer.Context) -> None:
    """List queued deployments."""
    c: AppContext = ctx.obj
    data = c.client.get("/deployment.queueList")
    if not isinstance(data, list):
        data = []
    rows = []
    for d in data:
        did = d.get("deploymentId", "")[:12]
        status = d.get("status", "unknown")
        deploy_type = d.get("deploymentType", "-")
        created = d.get("createdAt", "")
        title = d.get("title", d.get("description", "-"))
        rows.append([did, status, deploy_type, created, str(title)])
    c.output.table(
        "Deployment Queue",
        [("ID", "dim"), ("Status", "cyan"), ("Type", ""), ("Created", ""), ("Title", "")],
        rows,
        data_for_json=data,
    )


@app.command("by-type")
def by_type(
    ctx: typer.Context,
    type_: Annotated[
        str, typer.Option("--type", "-t", help="Deployment type (application, compose, server, schedule)")
    ],
) -> None:
    """List deployments filtered by type."""
    c: AppContext = ctx.obj
    data = c.client.get("/deployment.allByType", params={"type": type_})
    if not isinstance(data, list):
        data = []
    rows = []
    for d in data:
        did = d.get("deploymentId", "")[:12]
        status = d.get("status", "unknown")
        deploy_type = d.get("deploymentType", "-")
        created = d.get("createdAt", "")
        title = d.get("title", d.get("description", "-"))
        rows.append([did, status, deploy_type, created, str(title)])
    c.output.table(
        f"Deployments by Type: {type_}",
        [("ID", "dim"), ("Status", "cyan"), ("Type", ""), ("Created", ""), ("Title", "")],
        rows,
        data_for_json=data,
    )


@app.command("kill")
def kill(
    ctx: typer.Context,
    deployment_id: Annotated[str, typer.Argument(help="Deployment ID")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Kill a running deployment process (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Kill deployment process '{deployment_id}'?", abort=True)
    result = c.client.post("/deployment.killProcess", json={"deploymentId": deployment_id})
    c.output.success(f"Deployment process '{deployment_id}' killed")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("remove")
def remove(
    ctx: typer.Context,
    deployment_id: Annotated[str, typer.Argument(help="Deployment ID")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Remove a deployment record (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Remove deployment '{deployment_id}'? This cannot be undone.", abort=True)
    result = c.client.post("/deployment.removeDeployment", json={"deploymentId": deployment_id})
    c.output.success(f"Deployment '{deployment_id}' removed")
    if c.json_mode:
        c.output.raw_json(result)
