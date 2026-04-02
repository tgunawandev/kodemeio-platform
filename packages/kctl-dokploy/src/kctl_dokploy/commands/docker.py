"""Docker management commands via Dokploy API."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Docker container and resource management.")


@app.command()
def containers(
    ctx: typer.Context,
    server_id: Annotated[str | None, typer.Option("--server", "-s", help="Server ID or name")] = None,
) -> None:
    """List Docker containers."""
    c: AppContext = ctx.obj
    payload: dict = {}
    if server_id:
        payload["serverId"] = server_id
    try:
        data = c.client.get("/docker.getContainers", params=payload)
    except Exception:
        data = []
    if not isinstance(data, list):
        data = []
    rows = []
    json_data = []
    for ct in data:
        cid = ct.get("containerId", ct.get("id", ""))
        name = ct.get("name", ct.get("Names", ""))
        name = (name[0].lstrip("/") if name else "") if isinstance(name, list) else str(name).lstrip("/")
        state = ct.get("state", ct.get("State", "unknown"))
        image = ct.get("image", ct.get("Image", "-"))
        rows.append([cid, name, state, image])
        json_data.append({"id": ct.get("containerId", ct.get("id", "")), "name": name, "state": state, "image": image})
    c.output.table(
        "Docker Containers",
        [("ID", "dim"), ("Name", "cyan"), ("State", ""), ("Image", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def images(ctx: typer.Context) -> None:
    """List Docker images (not available in current Dokploy API)."""
    c: AppContext = ctx.obj
    c.output.warn("Docker images endpoint is not available in this Dokploy version")
    c.output.info("Use 'docker images' on the server directly, or check the Dokploy dashboard")


@app.command()
def volumes(ctx: typer.Context) -> None:
    """List Docker volumes (not available in current Dokploy API)."""
    c: AppContext = ctx.obj
    c.output.warn("Docker volumes endpoint is not available in this Dokploy version")
    c.output.info("Use 'docker volume ls' on the server directly, or check the Dokploy dashboard")


@app.command()
def networks(ctx: typer.Context) -> None:
    """List Docker networks (not available in current Dokploy API)."""
    c: AppContext = ctx.obj
    c.output.warn("Docker networks endpoint is not available in this Dokploy version")
    c.output.info("Use 'docker network ls' on the server directly, or check the Dokploy dashboard")


@app.command()
def prune(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Prune unused Docker resources."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(
            "Prune unused Docker resources? This removes unused containers, images, and networks.", abort=True
        )
    result = c.client.post("/docker.prune")
    c.output.success("Docker prune completed")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def stats(ctx: typer.Context) -> None:
    """Show Docker disk usage statistics."""
    c: AppContext = ctx.obj
    c.output.warn("Docker disk usage endpoint is not available in this Dokploy version")
    c.output.info("Use 'docker system df' on the server directly, or check the Dokploy dashboard")


@app.command("restart")
def restart(
    ctx: typer.Context,
    container_id: Annotated[str, typer.Argument(help="Container ID or name")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Restart a Docker container (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Restart container '{container_id}'?", abort=True)
    result = c.client.post("/docker.restartContainer", json={"containerId": container_id})
    c.output.success(f"Container '{container_id}' restarted")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("config")
def config(
    ctx: typer.Context,
    container_id: Annotated[str, typer.Argument(help="Container ID or name")],
) -> None:
    """Show configuration for a Docker container."""
    c: AppContext = ctx.obj
    data = c.client.get("/docker.getConfig", params={"containerId": container_id})
    if c.json_mode:
        c.output.raw_json(data if isinstance(data, dict) else {"config": data})
    else:
        if isinstance(data, dict):
            sections = [
                (
                    "Container Configuration",
                    [(str(k), str(v)) for k, v in data.items()],
                ),
            ]
            c.output.detail(f"Config: {container_id}", sections, data_for_json=data)
        else:
            c.output.header(f"Config: {container_id}")
            c.output.text(str(data))


@app.command("find")
def find_(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Option("--app", "-a", help="Application name to search for")],
) -> None:
    """Find Docker containers by application name."""
    c: AppContext = ctx.obj
    data = c.client.get("/docker.getContainersByAppNameMatch", params={"appName": app_name})
    if not isinstance(data, list):
        data = []
    rows = []
    for ct in data:
        cid = ct.get("containerId", ct.get("id", ""))
        name = ct.get("name", ct.get("Names", ""))
        name = (name[0].lstrip("/") if name else "") if isinstance(name, list) else str(name).lstrip("/")
        state = ct.get("state", ct.get("State", "unknown"))
        image = ct.get("image", ct.get("Image", "-"))
        rows.append([cid, name, state, image])
    c.output.table(
        f"Containers matching '{app_name}'",
        [("ID", "dim"), ("Name", "cyan"), ("State", ""), ("Image", "dim")],
        rows,
        data_for_json=data,
    )
