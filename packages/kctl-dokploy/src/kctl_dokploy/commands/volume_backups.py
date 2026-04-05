"""Volume-level backup management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Manage volume-level backups.")


@app.command("list")
def list_(
    ctx: typer.Context,
    resource_id: Annotated[str, typer.Option("--resource-id", "-r", help="Resource ID")],
    backup_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Backup type: application, compose, postgres, mysql, mariadb, mongo, redis"),
    ],
) -> None:
    """List volume backups for a resource."""
    c: AppContext = ctx.obj
    backups = c.client.get("/volumeBackups.list", params={"id": resource_id, "volumeBackupType": backup_type})
    if not isinstance(backups, list):
        backups = []
    rows = []
    for b in backups:
        bid = b.get("volumeBackupId", "")
        name = b.get("name", "")
        cron = b.get("cronExpression", "-")
        btype = b.get("backupType", "")
        destination = b.get("destinationId", "-")
        rows.append([bid, name, cron, btype, destination])
    c.output.table(
        "Volume Backups",
        [("ID", "dim"), ("Name", "cyan"), ("Cron", ""), ("Type", ""), ("Destination", "dim")],
        rows,
        data_for_json=backups,
    )


@app.command()
def get(
    ctx: typer.Context,
    backup_id: Annotated[str, typer.Argument(help="Volume backup ID")],
) -> None:
    """Get volume backup details."""
    c: AppContext = ctx.obj
    data = c.client.get("/volumeBackups.one", params={"volumeBackupId": backup_id})
    if not isinstance(data, dict):
        c.output.error(f"Volume backup '{backup_id}' not found")
        raise typer.Exit(1)
    sections = [
        (
            "Volume Backup",
            [
                ("ID", data.get("volumeBackupId", "")),
                ("Name", data.get("name", "")),
                ("Cron", data.get("cronExpression", "-")),
                ("Type", data.get("backupType", "")),
                ("Destination ID", data.get("destinationId", "-")),
                ("Enabled", str(data.get("enabled", "-"))),
                ("Last Run", data.get("lastRun", "-")),
                ("Created", data.get("createdAt", "-")),
            ],
        ),
    ]
    c.output.detail(f"Volume Backup: {data.get('name', '')}", sections, data_for_json=data)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Backup name (auto-generated if omitted)")] = None,
    cron: Annotated[str | None, typer.Option("--cron", help="Cron expression")] = None,
    schedule: Annotated[str | None, typer.Option("--schedule", help="Cron expression (alias for --cron)")] = None,
    backup_type: Annotated[
        str | None,
        typer.Option("--type", "-t", help="Backup type: application, compose, postgres, mysql, mariadb, mongo, redis"),
    ] = None,
    destination_id: Annotated[str | None, typer.Option("--destination-id", "-d", help="Destination ID")] = None,
    destination: Annotated[
        str | None, typer.Option("--destination", help="Destination ID (alias for --destination-id)")
    ] = None,
    resource_id: Annotated[str | None, typer.Option("--resource-id", "-r", help="Resource ID")] = None,
    compose_id: Annotated[
        str | None, typer.Option("--compose", "-c", help="Compose service ID (sets type=compose)")
    ] = None,
    service_name: Annotated[str | None, typer.Option("--service", help="Service name in compose")] = None,
    prefix: Annotated[str | None, typer.Option("--prefix", help="Backup file prefix")] = None,
) -> None:
    """Create a new volume backup."""
    c: AppContext = ctx.obj

    # Resolve aliases
    effective_cron = cron or schedule
    if not effective_cron:
        c.output.error("--cron or --schedule is required")
        raise typer.Exit(1)

    effective_dest = destination_id or destination
    if not effective_dest:
        c.output.error("--destination-id or --destination is required")
        raise typer.Exit(1)

    effective_resource = resource_id or compose_id
    effective_type = backup_type or ("compose" if compose_id else None)
    if not effective_type:
        c.output.error("--type is required (or use --compose to auto-set type=compose)")
        raise typer.Exit(1)

    effective_name = name or f"vb-{effective_type}-{effective_resource or 'default'}"

    payload: dict = {
        "name": effective_name,
        "cronExpression": effective_cron,
        "backupType": effective_type,
        "destinationId": effective_dest,
    }
    if effective_resource is not None:
        payload["id"] = effective_resource
    if service_name is not None:
        payload["serviceName"] = service_name
    if prefix is not None:
        payload["prefix"] = prefix
    result = c.client.post("/volumeBackups.create", json=payload)
    bid = result.get("volumeBackupId", "") if isinstance(result, dict) else ""
    c.output.success(f"Volume backup '{effective_name}' created: {bid}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def update(
    ctx: typer.Context,
    backup_id: Annotated[str, typer.Argument(help="Volume backup ID")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="New name")] = None,
    cron: Annotated[str | None, typer.Option("--cron", help="New cron expression")] = None,
    enabled: Annotated[bool | None, typer.Option("--enabled/--disabled", help="Enable or disable")] = None,
) -> None:
    """Update a volume backup."""
    c: AppContext = ctx.obj
    payload: dict = {"volumeBackupId": backup_id}
    if name is not None:
        payload["name"] = name
    if cron is not None:
        payload["cronExpression"] = cron
    if enabled is not None:
        payload["enabled"] = enabled
    if len(payload) == 1:
        c.output.error("Nothing to update. Provide at least one option.")
        raise typer.Exit(1)
    result = c.client.post("/volumeBackups.update", json=payload)
    c.output.success(f"Volume backup '{backup_id}' updated")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def delete(
    ctx: typer.Context,
    backup_id: Annotated[str, typer.Argument(help="Volume backup ID to delete")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete a volume backup (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete volume backup '{backup_id}'? This cannot be undone.", abort=True)
    result = c.client.post("/volumeBackups.delete", json={"volumeBackupId": backup_id})
    c.output.success(f"Volume backup '{backup_id}' deleted")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def run(
    ctx: typer.Context,
    backup_id: Annotated[str, typer.Argument(help="Volume backup ID to run")],
) -> None:
    """Manually trigger a volume backup."""
    c: AppContext = ctx.obj
    result = c.client.post("/volumeBackups.runManually", json={"volumeBackupId": backup_id})
    c.output.success("Volume backup triggered")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def restore(
    ctx: typer.Context,
    backup_file: Annotated[str, typer.Argument(help="Backup file name")],
    destination_id: Annotated[str, typer.Option("--destination", "-d", help="S3 destination ID")],
    volume_name: Annotated[str, typer.Option("--volume", "-v", help="Docker volume name to restore into")],
    resource_id: Annotated[str, typer.Option("--resource-id", "-r", help="Resource ID (compose/application)")],
    service_type: Annotated[
        str, typer.Option("--service-type", "-t", help="Service type: application, compose")
    ] = "compose",
    server_id: Annotated[str | None, typer.Option("--server", help="Server ID (for remote servers)")] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Restore a volume from a backup file (destructive).

    NOTE: Dokploy volume restore uses WebSocket streaming. This command attempts
    to initiate the restore via the API. Monitor progress in the Dokploy UI.
    """
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(
            f"Restore '{backup_file}' into volume '{volume_name}'? This will overwrite current data.",
            abort=True,
        )
    c.output.info(f"Initiating volume restore of '{backup_file}'...")
    payload: dict = {
        "backupFileName": backup_file,
        "destinationId": destination_id,
        "volumeName": volume_name,
        "id": resource_id,
        "serviceType": service_type,
    }
    if server_id:
        payload["serverId"] = server_id
    try:
        result = c.client.post("/volumeBackups.restoreVolumeBackupWithLogs", json=payload)
        c.output.success(f"Volume restore initiated for '{backup_file}' — check Dokploy UI for progress")
        if c.json_mode:
            c.output.raw_json(result)
    except Exception as exc:
        error_msg = str(exc)
        if "subscription" in error_msg.lower() or "upgrade" in error_msg.lower() or "405" in error_msg:
            c.output.warn(
                "Volume restore requires WebSocket (Dokploy subscription). Use the Dokploy UI to restore volumes."
            )
        else:
            c.output.error(f"Volume restore failed: {exc}")
            raise typer.Exit(1)
