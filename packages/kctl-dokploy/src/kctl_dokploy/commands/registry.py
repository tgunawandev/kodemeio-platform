"""Docker registry management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Manage Docker registries.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all configured Docker registries."""
    c: AppContext = ctx.obj
    registries = c.client.get("/registry.all")
    if not isinstance(registries, list):
        registries = []
    rows = []
    for r in registries:
        rid = r.get("registryId", "")
        name = r.get("registryName", r.get("name", ""))
        url = r.get("registryUrl", r.get("imagePrefix", ""))
        username = r.get("username", "-")
        rtype = r.get("registryType", "unknown")
        rows.append([rid, name, url, username, rtype])
    c.output.table(
        "Docker Registries",
        [("ID", "dim"), ("Name", "cyan"), ("URL", ""), ("Username", "dim"), ("Type", "")],
        rows,
        data_for_json=registries,
    )


@app.command()
def get(
    ctx: typer.Context,
    registry_id: Annotated[str, typer.Argument(help="Registry ID")],
) -> None:
    """Get registry details."""
    c: AppContext = ctx.obj
    data = c.client.get("/registry.one", params={"registryId": registry_id})
    if not isinstance(data, dict):
        c.output.error(f"Registry '{registry_id}' not found")
        raise typer.Exit(1)
    sections = [
        (
            "Registry",
            [
                ("ID", data.get("registryId", "")),
                ("Name", data.get("registryName", data.get("name", ""))),
                ("URL", data.get("registryUrl", data.get("imagePrefix", ""))),
                ("Username", data.get("username", "-")),
                ("Type", data.get("registryType", "unknown")),
                ("Created", data.get("createdAt", "-")),
            ],
        ),
    ]
    c.output.detail(f"Registry: {data.get('registryName', data.get('name', ''))}", sections, data_for_json=data)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Registry name")],
    url: Annotated[str, typer.Option("--url", help="Registry URL")],
    username: Annotated[str, typer.Option("--username", "-u", help="Registry username")],
    password: Annotated[str, typer.Option("--password", help="Registry password", prompt=True, hide_input=True)],
    registry_type: Annotated[
        str, typer.Option("--type", "-t", help="Registry type (selfHosted, docker, etc.)")
    ] = "selfHosted",
) -> None:
    """Create a new Docker registry."""
    c: AppContext = ctx.obj
    payload: dict = {
        "registryName": name,
        "registryUrl": url,
        "username": username,
        "password": password,
        "registryType": registry_type,
        "imagePrefix": url,
    }
    result = c.client.post("/registry.create", json=payload)
    rid = result.get("registryId", "") if isinstance(result, dict) else ""
    c.output.success(f"Registry '{name}' created: {rid}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def update(
    ctx: typer.Context,
    registry_id: Annotated[str, typer.Argument(help="Registry ID")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="New name")] = None,
    url: Annotated[str | None, typer.Option("--url", help="New URL")] = None,
    username: Annotated[str | None, typer.Option("--username", "-u", help="New username")] = None,
    password: Annotated[str | None, typer.Option("--password", help="New password")] = None,
) -> None:
    """Update a Docker registry."""
    c: AppContext = ctx.obj
    payload: dict = {"registryId": registry_id}
    if name is not None:
        payload["registryName"] = name
    if url is not None:
        payload["registryUrl"] = url
        payload["imagePrefix"] = url
    if username is not None:
        payload["username"] = username
    if password is not None:
        payload["password"] = password
    result = c.client.post("/registry.update", json=payload)
    c.output.success(f"Registry '{registry_id}' updated")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def remove(
    ctx: typer.Context,
    registry_id: Annotated[str, typer.Argument(help="Registry ID to remove")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Remove a Docker registry (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Remove registry '{registry_id}'? This cannot be undone.", abort=True)
    result = c.client.post("/registry.remove", json={"registryId": registry_id})
    c.output.success(f"Registry '{registry_id}' removed")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("test")
def test_connection(
    ctx: typer.Context,
    registry_id: Annotated[str, typer.Argument(help="Registry ID to test")],
) -> None:
    """Test connection to a Docker registry."""
    c: AppContext = ctx.obj
    c.output.info(f"Testing connection to registry '{registry_id}'...")
    result = c.client.post("/registry.testRegistry", json={"registryId": registry_id})
    c.output.success(f"Registry '{registry_id}' connection test passed")
    if c.json_mode:
        c.output.raw_json(result)
