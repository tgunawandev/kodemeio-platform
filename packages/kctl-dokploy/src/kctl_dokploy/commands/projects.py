"""Project management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Manage Dokploy projects.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all projects."""
    c: AppContext = ctx.obj
    projects = c.client.get("/project.all")
    if not isinstance(projects, list):
        projects = []
    rows = []
    for p in projects:
        name = p.get("name", "")
        pid = p.get("projectId", "")
        compose = str(len(p.get("compose", [])))
        apps = str(len(p.get("applications", [])))
        rows.append([pid, name, compose, apps])
    c.output.table(
        "Projects",
        [("ID", "dim"), ("Name", "cyan"), ("Compose", ""), ("Apps", "")],
        rows,
        data_for_json=projects,
    )


@app.command()
def get(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Project name")],
) -> None:
    """Get project details."""
    c: AppContext = ctx.obj
    projects = c.client.get("/project.all")
    if not isinstance(projects, list):
        projects = []
    match = [p for p in projects if p.get("name", "").lower() == name.lower()]
    if not match:
        c.output.error(f"Project '{name}' not found")
        raise typer.Exit(1)
    p = match[0]
    sections = [
        (
            "Project",
            [
                ("Name", p.get("name", "")),
                ("ID", p.get("projectId", "")),
                ("Description", p.get("description", "") or "-"),
            ],
        )
    ]
    # Show environments with IDs (needed for database creation)
    for env in p.get("environments", []):
        env_name = env.get("name", "default")
        env_id = env.get("environmentId", "")
        is_default = " (default)" if env.get("isDefault") else ""
        db_types = ("postgres", "redis", "mysql", "mariadb", "mongo")
        db_count = sum(len(env.get(dt, [])) for dt in db_types)
        compose_count = len(env.get("compose", []))
        app_count = len(env.get("applications", []))
        sections.append(
            (
                f"Environment: {env_name}{is_default}",
                [
                    ("ID", env_id),
                    ("Compose", str(compose_count)),
                    ("Applications", str(app_count)),
                    ("Databases", str(db_count)),
                ],
            )
        )
        # Show compose services in this environment
        for comp in env.get("compose", []):
            sections.append(
                (
                    f"  Compose: {comp.get('name', '')}",
                    [
                        ("ID", comp.get("composeId", "")),
                        ("Status", comp.get("composeStatus", "unknown")),
                    ],
                )
            )
        # Show databases in this environment
        for dt in db_types:
            for db in env.get(dt, []):
                id_field = f"{dt}Id"
                sections.append(
                    (
                        f"  {dt.capitalize()}: {db.get('name', '')}",
                        [
                            ("ID", db.get(id_field, "")),
                            ("Status", db.get(f"{dt}Status", "unknown")),
                        ],
                    )
                )
    c.output.detail(f"Project: {p.get('name')}", sections, data_for_json=p)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Project name")],
    description: Annotated[str | None, typer.Option("--description", "-d", help="Project description")] = None,
) -> None:
    """Create a new project."""
    c: AppContext = ctx.obj
    payload: dict = {"name": name}
    if description:
        payload["description"] = description
    result = c.client.post("/project.create", json=payload)
    pid = result.get("projectId", "") if isinstance(result, dict) else ""
    c.output.success(f"Project '{name}' created: {pid}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def update(
    ctx: typer.Context,
    project_id: Annotated[str, typer.Argument(help="Project ID")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="New name")] = None,
    description: Annotated[str | None, typer.Option("--description", "-d", help="New description")] = None,
) -> None:
    """Update a project."""
    c: AppContext = ctx.obj
    payload: dict = {"projectId": project_id}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    if len(payload) == 1:
        c.output.error("No update options provided. Use --name or --description.")
        raise typer.Exit(1)
    result = c.client.post("/project.update", json=payload)
    c.output.success(f"Project '{project_id}' updated")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def delete(
    ctx: typer.Context,
    project_id: Annotated[str, typer.Argument(help="Project ID to delete")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete a project (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete project '{project_id}'? All services will be removed.", abort=True)
    result = c.client.delete("/project.remove", json={"projectId": project_id})
    c.output.success(f"Project '{project_id}' deleted")
    if c.json_mode:
        c.output.raw_json(result)
