"""Volume and bind mount management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Manage volume and bind mounts.")


@app.command("list")
def list_(
    ctx: typer.Context,
    application_id: Annotated[str, typer.Option("--application", "-a", help="Application ID")],
) -> None:
    """List all named mounts for an application."""
    c: AppContext = ctx.obj
    data = c.client.get("/mounts.allNamedByApplicationId", params={"applicationId": application_id})
    if not isinstance(data, list):
        data = []
    rows = []
    for m in data:
        mid = m.get("mountId", "")[:12]
        mtype = m.get("type", "")
        host_path = m.get("hostPath", "-")
        mount_path = m.get("mountPath", "-")
        rows.append([mid, mtype, host_path, mount_path])
    c.output.table(
        f"Mounts for {application_id}",
        [("ID", "dim"), ("Type", "cyan"), ("Host Path", ""), ("Mount Path", "green")],
        rows,
        data_for_json=data,
    )


@app.command("list-by-service")
def list_by_service(
    ctx: typer.Context,
    service_id: Annotated[str, typer.Option("--service", "-s", help="Service ID")],
    mount_type: Annotated[str, typer.Option("--type", "-t", help="Mount type (bind, volume, file)")],
) -> None:
    """List mounts by service ID and type."""
    c: AppContext = ctx.obj
    data = c.client.get("/mounts.listByServiceId", params={"serviceId": service_id, "type": mount_type})
    if not isinstance(data, list):
        data = []
    rows = []
    for m in data:
        mid = m.get("mountId", "")[:12]
        mtype = m.get("type", "")
        host_path = m.get("hostPath", "-")
        mount_path = m.get("mountPath", "-")
        rows.append([mid, mtype, host_path, mount_path])
    c.output.table(
        f"Mounts for service {service_id} (type={mount_type})",
        [("ID", "dim"), ("Type", "cyan"), ("Host Path", ""), ("Mount Path", "green")],
        rows,
        data_for_json=data,
    )


@app.command()
def get(
    ctx: typer.Context,
    mount_id: Annotated[str, typer.Argument(help="Mount ID")],
) -> None:
    """Get mount details."""
    c: AppContext = ctx.obj
    data = c.client.get("/mounts.one", params={"mountId": mount_id})
    if not isinstance(data, dict):
        c.output.error(f"Mount '{mount_id}' not found")
        raise typer.Exit(1)
    sections = [
        (
            "Mount",
            [
                ("ID", data.get("mountId", "")),
                ("Type", data.get("type", "")),
                ("Host Path", data.get("hostPath", "-")),
                ("Mount Path", data.get("mountPath", "-")),
                ("Application ID", data.get("applicationId", "-")),
                ("Created", data.get("createdAt", "-")),
            ],
        ),
    ]
    c.output.detail(f"Mount: {data.get('mountId', '')}", sections, data_for_json=data)


@app.command()
def create(
    ctx: typer.Context,
    application_id: Annotated[str, typer.Option("--application", "-a", help="Application ID")],
    mount_type: Annotated[str, typer.Option("--type", "-t", help="Mount type (bind, volume, file)")],
    host_path: Annotated[str, typer.Option("--host-path", help="Host path")],
    mount_path: Annotated[str, typer.Option("--mount-path", help="Container mount path")],
) -> None:
    """Create a new mount."""
    c: AppContext = ctx.obj
    payload: dict = {
        "applicationId": application_id,
        "type": mount_type,
        "hostPath": host_path,
        "mountPath": mount_path,
    }
    result = c.client.post("/mounts.create", json=payload)
    mid = result.get("mountId", "") if isinstance(result, dict) else ""
    c.output.success(f"Mount created: {mid}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def update(
    ctx: typer.Context,
    mount_id: Annotated[str, typer.Argument(help="Mount ID")],
    host_path: Annotated[str | None, typer.Option("--host-path", help="New host path")] = None,
    mount_path: Annotated[str | None, typer.Option("--mount-path", help="New mount path")] = None,
) -> None:
    """Update a mount configuration."""
    c: AppContext = ctx.obj
    payload: dict = {"mountId": mount_id}
    if host_path is not None:
        payload["hostPath"] = host_path
    if mount_path is not None:
        payload["mountPath"] = mount_path
    if len(payload) == 1:
        c.output.error("No update options provided.")
        raise typer.Exit(1)
    result = c.client.post("/mounts.update", json=payload)
    c.output.success(f"Mount '{mount_id}' updated")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def remove(
    ctx: typer.Context,
    mount_id: Annotated[str, typer.Argument(help="Mount ID to remove")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Remove a mount (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Remove mount '{mount_id}'? This cannot be undone.", abort=True)
    result = c.client.post("/mounts.remove", json={"mountId": mount_id})
    c.output.success(f"Mount '{mount_id}' removed")
    if c.json_mode:
        c.output.raw_json(result)
