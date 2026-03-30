"""Backup management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Manage Dokploy backups and S3 destinations.")


@app.command("list")
def list_(
    ctx: typer.Context,
    compose_id: Annotated[str | None, typer.Option("--compose", "-c", help="Filter by compose ID")] = None,
) -> None:
    """List all backup configurations."""
    c: AppContext = ctx.obj
    if not compose_id:
        c.output.error("--compose is required (backups are scoped to compose services)")
        raise typer.Exit(1)
    # Fetch compose detail and extract backup config
    compose_data = c.client.get("/compose.one", params={"composeId": compose_id})
    backups = compose_data.get("backups", []) if isinstance(compose_data, dict) else []
    if not isinstance(backups, list):
        backups = []
    rows = []
    for b in backups:
        bid = b.get("backupId", "")[:12]
        status = b.get("status", "unknown")
        schedule = b.get("schedule", b.get("backupSchedule", "-"))
        enabled = "yes" if b.get("enabled", False) else "no"
        dest = b.get("destinationId", b.get("destination", "-"))
        if isinstance(dest, str) and len(dest) > 16:
            dest = dest[:12] + "..."
        rows.append([bid, status, schedule, enabled, str(dest)])
    c.output.table(
        "Backups",
        [("ID", "dim"), ("Status", "cyan"), ("Schedule", ""), ("Enabled", ""), ("Destination", "")],
        rows,
        data_for_json=backups,
    )


@app.command()
def trigger(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID to back up")],
    destination_id: Annotated[str | None, typer.Option("--destination", "-d", help="Destination ID")] = None,
) -> None:
    """Trigger a manual backup for a compose service."""
    c: AppContext = ctx.obj
    out = c.output
    # If no destination given, try to find the first available one
    if not destination_id:
        destinations = c.client.get("/destination.all")
        if isinstance(destinations, list) and destinations:
            destination_id = destinations[0].get("destinationId", "")
        if not destination_id:
            out.error("No backup destination configured. Create one first with: kctl-dokploy backups add-destination")
            raise typer.Exit(1)
    out.info(f"Triggering backup for compose '{compose_id}' -> destination '{destination_id}'...")
    result = c.client.post(
        "/backup.create",
        json={
            "composeId": compose_id,
            "destinationId": destination_id,
        },
    )
    out.success(f"Backup triggered for compose '{compose_id}'")
    if c.json_mode:
        out.raw_json(result)


@app.command()
def restore(
    ctx: typer.Context,
    backup_id: Annotated[str, typer.Argument(help="Backup ID to restore from")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Restore from a backup snapshot (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(
            f"Restore from backup '{backup_id}'? This will overwrite the current state.",
            abort=True,
        )
    c.output.info(f"Restoring from backup '{backup_id}'...")
    result = c.client.post("/rollback.rollback", json={"backupId": backup_id})
    c.output.success(f"Restore initiated from backup '{backup_id}'")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def destinations(ctx: typer.Context) -> None:
    """List all S3 backup destinations."""
    c: AppContext = ctx.obj
    data = c.client.get("/destination.all")
    if not isinstance(data, list):
        data = []
    rows = []
    for d in data:
        did = d.get("destinationId", "")
        name = d.get("name", "")
        endpoint = d.get("endpoint", "(AWS default)")
        bucket = d.get("bucket", "")
        region = d.get("region", "")
        rows.append([did[:12], name, endpoint, bucket, region])
    c.output.table(
        "S3 Backup Destinations",
        [("ID", "dim"), ("Name", "cyan"), ("Endpoint", ""), ("Bucket", "green"), ("Region", "")],
        rows,
        data_for_json=data,
    )


@app.command("add-destination")
def add_destination(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Destination name")],
    bucket: Annotated[str, typer.Option("--bucket", "-b", help="S3 bucket name")],
    access_key: Annotated[str, typer.Option("--access-key", help="S3 access key ID")],
    secret_key: Annotated[str, typer.Option("--secret-key", help="S3 secret access key")],
    region: Annotated[str, typer.Option("--region", "-r", help="S3 region")] = "us-east-1",
    endpoint: Annotated[str | None, typer.Option("--endpoint", "-e", help="S3-compatible endpoint URL")] = None,
) -> None:
    """Add an S3 backup destination."""
    c: AppContext = ctx.obj
    payload: dict = {
        "name": name,
        "accessKey": access_key,
        "secretAccessKey": secret_key,
        "bucket": bucket,
        "region": region,
    }
    if endpoint:
        payload["endpoint"] = endpoint
    result = c.client.post("/destination.create", json=payload)
    did = result.get("destinationId", "") if isinstance(result, dict) else ""
    c.output.success(f"Destination '{name}' created: {did}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("test-destination")
def test_destination(
    ctx: typer.Context,
    destination_id: Annotated[str, typer.Argument(help="Destination ID to test")],
) -> None:
    """Test S3 connection for a destination."""
    c: AppContext = ctx.obj
    c.output.info(f"Testing S3 connection for destination '{destination_id}'...")
    result = c.client.post("/destination.testConnection", json={"destinationId": destination_id})
    c.output.success(f"S3 connection test passed for destination '{destination_id}'")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("delete-destination")
def delete_destination(
    ctx: typer.Context,
    destination_id: Annotated[str, typer.Argument(help="Destination ID to delete")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete an S3 backup destination."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete destination '{destination_id}'?", abort=True)
    result = c.client.post("/destination.remove", json={"destinationId": destination_id})
    c.output.success(f"Destination '{destination_id}' deleted")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("update-destination")
def update_destination(
    ctx: typer.Context,
    destination_id: Annotated[str, typer.Argument(help="Destination ID to update")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="New name")] = None,
    bucket: Annotated[str | None, typer.Option("--bucket", "-b", help="New bucket")] = None,
    region: Annotated[str | None, typer.Option("--region", "-r", help="New region")] = None,
    endpoint: Annotated[str | None, typer.Option("--endpoint", "-e", help="New endpoint URL")] = None,
    access_key: Annotated[str | None, typer.Option("--access-key", help="New access key")] = None,
    secret_key: Annotated[str | None, typer.Option("--secret-key", help="New secret key")] = None,
) -> None:
    """Update an S3 backup destination."""
    c: AppContext = ctx.obj
    payload: dict = {"destinationId": destination_id}
    if name is not None:
        payload["name"] = name
    if bucket is not None:
        payload["bucket"] = bucket
    if region is not None:
        payload["region"] = region
    if endpoint is not None:
        payload["endpoint"] = endpoint
    if access_key is not None:
        payload["accessKey"] = access_key
    if secret_key is not None:
        payload["secretAccessKey"] = secret_key
    if len(payload) == 1:
        c.output.error("No update options provided.")
        raise typer.Exit(1)
    result = c.client.post("/destination.update", json=payload)
    c.output.success(f"Destination '{destination_id}' updated")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("rollback")
def rollback(
    ctx: typer.Context,
    rollback_id: Annotated[str, typer.Argument(help="Rollback ID")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Rollback to a previous state (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Rollback '{rollback_id}'? This will restore a previous state.", abort=True)
    c.output.info(f"Rolling back '{rollback_id}'...")
    result = c.client.post("/rollback.rollback", json={"rollbackId": rollback_id})
    c.output.success(f"Rollback '{rollback_id}' completed")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("delete-rollback")
def rollback_delete(
    ctx: typer.Context,
    rollback_id: Annotated[str, typer.Argument(help="Rollback ID")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete a rollback record (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete rollback '{rollback_id}'? This cannot be undone.", abort=True)
    result = c.client.post("/rollback.delete", json={"rollbackId": rollback_id})
    c.output.success(f"Rollback '{rollback_id}' deleted")
    if c.json_mode:
        c.output.raw_json(result)
