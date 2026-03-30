"""Deployment environment management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Manage deployment environments (dev/staging/prod).")


@app.command("list")
def list_(
    ctx: typer.Context,
    project: Annotated[str, typer.Option("--project", "-p", help="Project ID")],
) -> None:
    """List environments for a project."""
    c: AppContext = ctx.obj
    envs = c.client.get("/environment.byProjectId", params={"projectId": project})
    if not isinstance(envs, list):
        envs = []
    rows = []
    for env in envs:
        eid = env.get("environmentId", "")[:12]
        name = env.get("name", "")
        description = env.get("description", "-")
        proj = env.get("projectId", "")[:12]
        rows.append([eid, name, description, proj])
    c.output.table(
        "Environments",
        [("ID", "dim"), ("Name", "cyan"), ("Description", ""), ("Project", "dim")],
        rows,
        data_for_json=envs,
    )


@app.command()
def get(
    ctx: typer.Context,
    env_id: Annotated[str, typer.Argument(help="Environment ID")],
) -> None:
    """Get environment details."""
    c: AppContext = ctx.obj
    data = c.client.get("/environment.one", params={"environmentId": env_id})
    if not isinstance(data, dict):
        c.output.error(f"Environment '{env_id}' not found")
        raise typer.Exit(1)
    sections = [
        (
            "Environment",
            [
                ("ID", data.get("environmentId", "")),
                ("Name", data.get("name", "")),
                ("Description", data.get("description", "-")),
                ("Project ID", data.get("projectId", "-")),
                ("Created", data.get("createdAt", "-")),
                ("Updated", data.get("updatedAt", "-")),
            ],
        ),
    ]
    c.output.detail(f"Environment: {data.get('name', '')}", sections, data_for_json=data)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Environment name")],
    project: Annotated[str, typer.Option("--project", "-p", help="Project ID")],
    description: Annotated[str | None, typer.Option("--description", "-d", help="Environment description")] = None,
) -> None:
    """Create a new environment."""
    c: AppContext = ctx.obj
    payload: dict = {"name": name, "projectId": project}
    if description is not None:
        payload["description"] = description
    result = c.client.post("/environment.create", json=payload)
    eid = result.get("environmentId", "") if isinstance(result, dict) else ""
    c.output.success(f"Environment '{name}' created: {eid}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def update(
    ctx: typer.Context,
    env_id: Annotated[str, typer.Argument(help="Environment ID")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="New name")] = None,
    description: Annotated[str | None, typer.Option("--description", "-d", help="New description")] = None,
) -> None:
    """Update an environment."""
    c: AppContext = ctx.obj
    payload: dict = {"environmentId": env_id}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    if len(payload) == 1:
        c.output.error("Nothing to update. Provide --name or --description.")
        raise typer.Exit(1)
    result = c.client.post("/environment.update", json=payload)
    c.output.success(f"Environment '{env_id}' updated")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def remove(
    ctx: typer.Context,
    env_id: Annotated[str, typer.Argument(help="Environment ID to remove")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Remove an environment (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Remove environment '{env_id}'? This cannot be undone.", abort=True)
    result = c.client.post("/environment.remove", json={"environmentId": env_id})
    c.output.success(f"Environment '{env_id}' removed")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def duplicate(
    ctx: typer.Context,
    env_id: Annotated[str, typer.Argument(help="Environment ID to duplicate")],
    name: Annotated[str, typer.Option("--name", "-n", help="Name for the new environment")],
) -> None:
    """Duplicate an environment."""
    c: AppContext = ctx.obj
    result = c.client.post("/environment.duplicate", json={"environmentId": env_id, "name": name})
    eid = result.get("environmentId", "") if isinstance(result, dict) else ""
    c.output.success(f"Environment '{env_id}' duplicated as '{name}': {eid}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def search(
    ctx: typer.Context,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Filter by name")] = None,
    project: Annotated[str | None, typer.Option("--project", "-p", help="Filter by project ID")] = None,
) -> None:
    """Search environments by name or project."""
    c: AppContext = ctx.obj
    params: dict = {}
    if name is not None:
        params["name"] = name
    if project is not None:
        params["projectId"] = project
    envs = c.client.get("/environment.search", params=params)
    if not isinstance(envs, list):
        envs = []
    rows = []
    for env in envs:
        eid = env.get("environmentId", "")[:12]
        ename = env.get("name", "")
        description = env.get("description", "-")
        proj = env.get("projectId", "")[:12]
        rows.append([eid, ename, description, proj])
    c.output.table(
        "Search Results",
        [("ID", "dim"), ("Name", "cyan"), ("Description", ""), ("Project", "dim")],
        rows,
        data_for_json=envs,
    )
