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
        cid = ct.get("containerId", ct.get("id", ""))[:12]
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
    """List Docker images."""
    c: AppContext = ctx.obj
    try:
        data = c.client.get("/docker.getImages")
    except Exception:
        data = []
    if not isinstance(data, list):
        data = []
    rows = []
    for img in data:
        iid = img.get("id", "")[:12]
        tags = ", ".join(img.get("tags", img.get("RepoTags", []))) or "<none>"
        size = img.get("size", img.get("Size", 0))
        size_mb = f"{size / 1024 / 1024:.1f} MB" if isinstance(size, (int, float)) else str(size)
        rows.append([iid, tags, size_mb])
    c.output.table(
        "Docker Images",
        [("ID", "dim"), ("Tags", "cyan"), ("Size", "")],
        rows,
        data_for_json=data,
    )


@app.command()
def volumes(ctx: typer.Context) -> None:
    """List Docker volumes."""
    c: AppContext = ctx.obj
    try:
        data = c.client.get("/docker.getVolumes")
    except Exception:
        data = []
    items = (data.get("Volumes", []) if isinstance(data, dict) else []) if not isinstance(data, list) else data
    rows = []
    for v in items:
        name = v.get("Name", v.get("name", ""))
        driver = v.get("Driver", v.get("driver", "-"))
        rows.append([name, driver])
    c.output.table(
        "Docker Volumes",
        [("Name", "cyan"), ("Driver", "dim")],
        rows,
        data_for_json=items,
    )


@app.command()
def networks(ctx: typer.Context) -> None:
    """List Docker networks."""
    c: AppContext = ctx.obj
    try:
        data = c.client.get("/docker.getNetworks")
    except Exception:
        data = []
    if not isinstance(data, list):
        data = []
    rows = []
    for n in data:
        name = n.get("Name", n.get("name", ""))
        driver = n.get("Driver", n.get("driver", "-"))
        scope = n.get("Scope", n.get("scope", "-"))
        rows.append([name, driver, scope])
    c.output.table(
        "Docker Networks",
        [("Name", "cyan"), ("Driver", ""), ("Scope", "dim")],
        rows,
        data_for_json=data,
    )


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
    try:
        data = c.client.get("/docker.getDiskUsage")
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    sections = [
        (
            "Disk Usage",
            [
                ("Images", str(data.get("images", data.get("Images", "-")))),
                ("Containers", str(data.get("containers", data.get("Containers", "-")))),
                ("Volumes", str(data.get("volumes", data.get("Volumes", "-")))),
                ("Build Cache", str(data.get("buildCache", data.get("BuildCache", "-")))),
                ("Total", str(data.get("total", data.get("Total", "-")))),
            ],
        )
    ]
    c.output.detail("Docker Disk Usage", sections, data_for_json=data)


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
        cid = ct.get("containerId", ct.get("id", ""))[:12]
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
