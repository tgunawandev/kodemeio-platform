"""Application management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Manage Dokploy applications.")


@app.command("list")
def list_(
    ctx: typer.Context,
    project: Annotated[str | None, typer.Option("--project", "-p", help="Filter by project name")] = None,
) -> None:
    """List all applications across projects."""
    c: AppContext = ctx.obj
    projects = c.client.get("/project.all")
    if not isinstance(projects, list):
        projects = []
    rows = []
    json_data = []
    for p in projects:
        proj_name = p.get("name", "")
        if project and proj_name.lower() != project.lower():
            continue
        for a in p.get("applications", []):
            aid = a.get("applicationId", "")
            name = a.get("name", "")
            status = a.get("applicationStatus", "unknown")
            rows.append([aid[:12], proj_name, name, status])
            json_data.append(
                {
                    "applicationId": aid,
                    "project": proj_name,
                    "name": name,
                    "status": status,
                }
            )
    c.output.table(
        "Applications",
        [("ID", "dim"), ("Project", "cyan"), ("Name", "green"), ("Status", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def get(
    ctx: typer.Context,
    application_id: Annotated[str, typer.Argument(help="Application ID")],
) -> None:
    """Get application details."""
    c: AppContext = ctx.obj
    data = c.client.get("/application.one", params={"applicationId": application_id})
    if not isinstance(data, dict):
        c.output.error(f"Application '{application_id}' not found")
        raise typer.Exit(1)
    name = data.get("name", "unknown")
    status = data.get("applicationStatus", "unknown")
    app_type = data.get("applicationType", "unknown")
    updated = data.get("updatedAt", data.get("createdAt", "-"))
    registry = data.get("registry", data.get("dockerImage", "-"))
    sections = [
        (
            "Application",
            [
                ("ID", data.get("applicationId", "")),
                ("Name", name),
                ("Status", status),
                ("Type", app_type),
                ("Registry/Image", str(registry)),
                ("Updated", updated),
            ],
        ),
    ]
    domains = data.get("domains", [])
    if domains:
        domain_kvs = [(d.get("host", ""), str(d.get("port", ""))) for d in domains]
        sections.append(("Domains", domain_kvs))
    c.output.detail(f"Application: {name}", sections, data_for_json=data)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Application name")],
    project_id: Annotated[str, typer.Option("--project", "-p", help="Project ID")],
    description: Annotated[str | None, typer.Option("--description", "-d", help="Description")] = None,
    server_id: Annotated[str | None, typer.Option("--server", help="Server ID")] = None,
) -> None:
    """Create a new application."""
    c: AppContext = ctx.obj
    payload: dict = {"name": name, "projectId": project_id}
    if description:
        payload["description"] = description
    if server_id:
        payload["serverId"] = server_id
    result = c.client.post("/application.create", json=payload)
    aid = result.get("applicationId", "") if isinstance(result, dict) else ""
    c.output.success(f"Application '{name}' created: {aid}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def update(
    ctx: typer.Context,
    application_id: Annotated[str, typer.Argument(help="Application ID")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="New name")] = None,
    description: Annotated[str | None, typer.Option("--description", "-d", help="New description")] = None,
    docker_image: Annotated[str | None, typer.Option("--image", help="Docker image")] = None,
) -> None:
    """Update an application configuration."""
    c: AppContext = ctx.obj
    payload: dict = {"applicationId": application_id}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    if docker_image is not None:
        payload["dockerImage"] = docker_image
    if len(payload) == 1:
        c.output.error("No update options provided. Use --name, --description, or --image.")
        raise typer.Exit(1)
    result = c.client.post("/application.update", json=payload)
    c.output.success(f"Application '{application_id}' updated")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def delete(
    ctx: typer.Context,
    application_id: Annotated[str, typer.Argument(help="Application ID")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete an application (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete application '{application_id}'? This cannot be undone.", abort=True)
    result = c.client.delete("/application.remove", json={"applicationId": application_id})
    c.output.success(f"Application '{application_id}' deleted")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def deploy(
    ctx: typer.Context,
    application_id: Annotated[str, typer.Argument(help="Application ID")],
) -> None:
    """Trigger deployment for an application."""
    c: AppContext = ctx.obj
    c.output.info(f"Deploying application '{application_id}'...")
    result = c.client.post("/application.deploy", json={"applicationId": application_id})
    c.output.success(f"Deployment triggered for application '{application_id}'")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def stop(
    ctx: typer.Context,
    application_id: Annotated[str, typer.Argument(help="Application ID")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Stop a running application."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Stop application '{application_id}'?", abort=True)
    result = c.client.post("/application.stop", json={"applicationId": application_id})
    c.output.success(f"Application '{application_id}' stopped")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def start(
    ctx: typer.Context,
    application_id: Annotated[str, typer.Argument(help="Application ID")],
) -> None:
    """Start (deploy) a stopped application."""
    c: AppContext = ctx.obj
    c.output.info(f"Starting application '{application_id}'...")
    result = c.client.post("/application.deploy", json={"applicationId": application_id})
    c.output.success(f"Application '{application_id}' started")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def redeploy(
    ctx: typer.Context,
    application_id: Annotated[str, typer.Argument(help="Application ID")],
) -> None:
    """Stop and redeploy an application."""
    c: AppContext = ctx.obj
    out = c.output
    out.info(f"Redeploying application '{application_id}'...")
    try:
        c.client.post("/application.stop", json={"applicationId": application_id})
        out.info("Stopped. Triggering deployment...")
    except Exception:
        out.warn("Stop failed or application was not running; proceeding with deploy")
    result = c.client.post("/application.deploy", json={"applicationId": application_id})
    out.success(f"Application '{application_id}' redeployed")
    if c.json_mode:
        out.raw_json(result)


@app.command("cancel")
def cancel(
    ctx: typer.Context,
    app_id: Annotated[str, typer.Argument(help="Application ID")],
) -> None:
    """Cancel a running deployment for an application."""
    c: AppContext = ctx.obj
    c.output.info(f"Cancelling deployment for application '{app_id}'...")
    result = c.client.post("/application.cancelDeployment", json={"applicationId": app_id})
    c.output.success(f"Deployment cancelled for application '{app_id}'")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("monitoring")
def monitoring(
    ctx: typer.Context,
    app_id: Annotated[str, typer.Argument(help="Application ID")],
) -> None:
    """Show monitoring data for an application."""
    c: AppContext = ctx.obj
    data = c.client.get("/application.readAppMonitoring", params={"applicationId": app_id})
    if not isinstance(data, dict):
        data = {"raw": data}
    sections = [
        (
            "Application Monitoring",
            [(str(k), str(v)) for k, v in data.items()],
        ),
    ]
    c.output.detail(f"Monitoring: {app_id}", sections, data_for_json=data)


@app.command("search")
def search(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Search query")],
) -> None:
    """Search applications by name."""
    c: AppContext = ctx.obj
    data = c.client.get("/application.search", params={"name": name})
    if not isinstance(data, list):
        data = []
    rows = []
    for a in data:
        aid = a.get("applicationId", "")[:12]
        aname = a.get("name", "")
        status = a.get("applicationStatus", "unknown")
        rows.append([aid, aname, status])
    c.output.table(
        f"Search Results: '{name}'",
        [("ID", "dim"), ("Name", "cyan"), ("Status", "")],
        rows,
        data_for_json=data,
    )


@app.command("kill-build")
def kill_build(
    ctx: typer.Context,
    app_id: Annotated[str, typer.Argument(help="Application ID")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Kill a running build for an application (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Kill build for application '{app_id}'?", abort=True)
    result = c.client.post("/application.killBuild", json={"applicationId": app_id})
    c.output.success(f"Build killed for application '{app_id}'")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("clear-deployments")
def clear_deployments(
    ctx: typer.Context,
    app_id: Annotated[str, typer.Argument(help="Application ID")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Clear all deployment history for an application (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Clear all deployments for application '{app_id}'? This cannot be undone.", abort=True)
    result = c.client.post("/application.clearDeployments", json={"applicationId": app_id})
    c.output.success(f"Deployments cleared for application '{app_id}'")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("move")
def move(
    ctx: typer.Context,
    app_id: Annotated[str, typer.Argument(help="Application ID")],
    environment: Annotated[str, typer.Option("--environment", "-e", help="Target environment ID")],
) -> None:
    """Move an application to a different environment."""
    c: AppContext = ctx.obj
    result = c.client.post("/application.move", json={"applicationId": app_id, "environmentId": environment})
    c.output.success(f"Application '{app_id}' moved to environment '{environment}'")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("show-traefik")
def traefik_config(
    ctx: typer.Context,
    app_id: Annotated[str, typer.Argument(help="Application ID")],
) -> None:
    """Show Traefik configuration for an application."""
    c: AppContext = ctx.obj
    data = c.client.get("/application.readTraefikConfig", params={"applicationId": app_id})
    if c.json_mode:
        c.output.raw_json(data if isinstance(data, dict) else {"config": data})
    else:
        if isinstance(data, dict):
            sections = [
                (
                    "Traefik Configuration",
                    [(str(k), str(v)) for k, v in data.items()],
                ),
            ]
            c.output.detail(f"Traefik Config: {app_id}", sections, data_for_json=data)
        else:
            c.output.header(f"Traefik Config: {app_id}")
            c.output.text(str(data))
