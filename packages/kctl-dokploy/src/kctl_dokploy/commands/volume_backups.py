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
    backups = c.client.get("/volumeBackups.list", params={"id": resource_id, "backupType": backup_type})
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
    name: Annotated[str, typer.Option("--name", "-n", help="Backup name")],
    cron: Annotated[str, typer.Option("--cron", help="Cron expression")],
    backup_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Backup type: application, compose, postgres, mysql, mariadb, mongo, redis"),
    ],
    destination_id: Annotated[str, typer.Option("--destination-id", "-d", help="Destination ID")],
    resource_id: Annotated[str | None, typer.Option("--resource-id", "-r", help="Resource ID")] = None,
) -> None:
    """Create a new volume backup."""
    c: AppContext = ctx.obj
    payload: dict = {
        "name": name,
        "cronExpression": cron,
        "backupType": backup_type,
        "destinationId": destination_id,
    }
    if resource_id is not None:
        payload["id"] = resource_id
    result = c.client.post("/volumeBackups.create", json=payload)
    bid = result.get("volumeBackupId", "") if isinstance(result, dict) else ""
    c.output.success(f"Volume backup '{name}' created: {bid}")
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
