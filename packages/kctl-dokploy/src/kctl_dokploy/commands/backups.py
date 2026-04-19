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
        bid = b.get("backupId", "")
        status = b.get("status", "unknown")
        schedule = b.get("schedule", b.get("backupSchedule", "-"))
        enabled = "yes" if b.get("enabled", False) else "no"
        dest = b.get("destinationId", b.get("destination", "-"))
        if isinstance(dest, str) and len(dest) > 16:
            dest = dest[:16] + "..."
        rows.append([bid, status, schedule, enabled, str(dest)])
    c.output.table(
        "Backups",
        [("ID", "dim"), ("Status", "cyan"), ("Schedule", ""), ("Enabled", ""), ("Destination", "")],
        rows,
        data_for_json=backups,
    )


def _build_compose_metadata(
    db_type: str,
    database_user: str | None,
    database_password: str | None,
) -> dict | None:
    """Build the `metadata` payload Dokploy requires for compose-type backups.

    For compose backups, Dokploy resolves the dump command from
    `backup.metadata.<db_type>.databaseUser` (and password for mysql/mariadb/mongo).
    If not provided, Dokploy's shell template emits `null` as the backup command,
    producing `bash: line 15: null: command not found` at run time.
    """
    if db_type == "postgres":
        if not database_user:
            return None
        return {"postgres": {"databaseUser": database_user}}
    if db_type == "mariadb":
        if not database_user or not database_password:
            return None
        return {"mariadb": {"databaseUser": database_user, "databasePassword": database_password}}
    if db_type == "mysql":
        if not database_password:
            return None
        return {"mysql": {"databaseRootPassword": database_password}}
    if db_type == "mongo":
        if not database_user or not database_password:
            return None
        return {"mongo": {"databaseUser": database_user, "databasePassword": database_password}}
    return None


@app.command("create")
def create(
    ctx: typer.Context,
    destination_id: Annotated[str, typer.Option("--destination", "-d", help="S3 destination ID")],
    database: Annotated[str, typer.Option("--database", help="Database name to back up")],
    db_type: Annotated[
        str, typer.Option("--type", "-t", help="Database type: postgres, mysql, mariadb, mongo, web-server")
    ] = "postgres",
    postgres_id: Annotated[str | None, typer.Option("--postgres-id", help="Postgres managed DB ID")] = None,
    mysql_id: Annotated[str | None, typer.Option("--mysql-id", help="MySQL managed DB ID")] = None,
    mariadb_id: Annotated[str | None, typer.Option("--mariadb-id", help="MariaDB managed DB ID")] = None,
    mongo_id: Annotated[str | None, typer.Option("--mongo-id", help="MongoDB managed DB ID")] = None,
    compose_id: Annotated[
        str | None, typer.Option("--compose", "-c", help="Compose service ID (for compose backups)")
    ] = None,
    service_name: Annotated[
        str | None, typer.Option("--service", help="Service name in compose (e.g. 'postgres')")
    ] = None,
    database_user: Annotated[
        str | None,
        typer.Option(
            "--database-user",
            "-u",
            help="DB role/user used inside pg_dump/mysqldump. REQUIRED for compose backups of postgres/mariadb/mongo.",
        ),
    ] = None,
    database_password: Annotated[
        str | None,
        typer.Option(
            "--database-password",
            help="DB user password — REQUIRED for compose backups of mysql/mariadb/mongo (not postgres).",
        ),
    ] = None,
    schedule: Annotated[str, typer.Option("--schedule", "-s", help="Cron schedule")] = "0 2 * * *",
    prefix: Annotated[str, typer.Option("--prefix", help="Backup file prefix")] = "backup",
    enabled: Annotated[bool, typer.Option("--enabled/--disabled", help="Enable backup schedule")] = True,
) -> None:
    """Create a backup configuration for a database or compose service."""
    c: AppContext = ctx.obj
    backup_type = "compose" if compose_id else "database"
    payload: dict = {
        "schedule": schedule,
        "prefix": prefix,
        "destinationId": destination_id,
        "database": database,
        "databaseType": db_type,
        "backupType": backup_type,
        "enabled": enabled,
    }
    if postgres_id:
        payload["postgresId"] = postgres_id
    if mysql_id:
        payload["mysqlId"] = mysql_id
    if mariadb_id:
        payload["mariadbId"] = mariadb_id
    if mongo_id:
        payload["mongoId"] = mongo_id
    if compose_id:
        payload["composeId"] = compose_id
    if service_name:
        payload["serviceName"] = service_name

    # Compose backups REQUIRE metadata.<db_type>.databaseUser (and password for
    # mysql/mariadb/mongo). Without it Dokploy's runtime emits a null command.
    if backup_type == "compose" and db_type in {"postgres", "mariadb", "mysql", "mongo"}:
        metadata = _build_compose_metadata(db_type, database_user, database_password)
        if metadata is None:
            c.output.error(
                f"Compose backups of type '{db_type}' require --database-user"
                + (" and --database-password" if db_type in {"mariadb", "mysql", "mongo"} else "")
                + ". Without it, Dokploy's backup script fails with 'null: command not found' at runtime."
            )
            raise typer.Exit(1)
        payload["metadata"] = metadata

    result = c.client.post("/backup.create", json=payload)
    bid = result.get("backupId", "") if isinstance(result, dict) else ""
    c.output.success(f"Backup config created: {bid}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def get(
    ctx: typer.Context,
    backup_id: Annotated[str, typer.Argument(help="Backup config ID")],
) -> None:
    """Get details for a backup configuration."""
    c: AppContext = ctx.obj
    data = c.client.get("/backup.one", params={"backupId": backup_id})
    if not isinstance(data, dict):
        c.output.error(f"Backup '{backup_id}' not found")
        raise typer.Exit(1)
    sections = [
        (
            "Backup",
            [
                ("ID", data.get("backupId", "")),
                ("Schedule", data.get("schedule", "-")),
                ("Prefix", data.get("prefix", "-")),
                ("Database", data.get("database", "-")),
                ("DB Type", data.get("databaseType", "-")),
                ("Backup Type", data.get("backupType", "-")),
                ("Destination ID", data.get("destinationId", "-")),
                ("Enabled", str(data.get("enabled", "-"))),
                ("Created", data.get("createdAt", "-")),
            ],
        ),
    ]
    c.output.detail(f"Backup: {data.get('backupId', '')}", sections, data_for_json=data)


@app.command("update")
def update(
    ctx: typer.Context,
    backup_id: Annotated[str, typer.Argument(help="Backup config ID")],
    schedule: Annotated[str | None, typer.Option("--schedule", "-s", help="New cron schedule")] = None,
    prefix: Annotated[str | None, typer.Option("--prefix", help="New backup file prefix")] = None,
    enabled: Annotated[bool | None, typer.Option("--enabled/--disabled", help="Enable or disable")] = None,
    destination_id: Annotated[str | None, typer.Option("--destination", "-d", help="New destination ID")] = None,
    database_user: Annotated[
        str | None,
        typer.Option(
            "--database-user",
            "-u",
            help="DB role/user for compose backups (sets metadata.<db_type>.databaseUser).",
        ),
    ] = None,
    database_password: Annotated[
        str | None,
        typer.Option(
            "--database-password",
            help="DB user password for compose backups of mysql/mariadb/mongo.",
        ),
    ] = None,
) -> None:
    """Update a backup configuration.

    Dokploy's /backup.update requires the full backup record (not just diffs),
    so we GET the existing record, apply overrides, and PUT it back. This
    matches the UI's behavior and avoids 400 validation errors from sending
    partial payloads.
    """
    c: AppContext = ctx.obj

    if all(v is None for v in (schedule, prefix, enabled, destination_id, database_user, database_password)):
        c.output.error("Nothing to update. Provide at least one option.")
        raise typer.Exit(1)

    # Dokploy's update endpoint requires all primary fields — fetch then merge.
    existing = c.client.get("/backup.one", params={"backupId": backup_id})
    if not isinstance(existing, dict):
        c.output.error(f"Backup '{backup_id}' not found")
        raise typer.Exit(1)

    # Keep only primitive fields + `metadata` from the existing record.
    payload = {k: v for k, v in existing.items() if not isinstance(v, (dict, list)) or k == "metadata"}

    if schedule is not None:
        payload["schedule"] = schedule
    if prefix is not None:
        payload["prefix"] = prefix
    if enabled is not None:
        payload["enabled"] = enabled
    if destination_id is not None:
        payload["destinationId"] = destination_id

    # Update metadata for compose backups when the DB user/password changes.
    if database_user is not None or database_password is not None:
        db_type = existing.get("databaseType", "")
        backup_type = existing.get("backupType", "")
        if backup_type != "compose":
            c.output.warn("--database-user / --database-password only apply to compose backups; ignoring.")
        else:
            existing_meta = existing.get("metadata") or {}
            db_meta = (existing_meta.get(db_type) or {}).copy()
            if database_user is not None:
                if db_type in {"postgres", "mariadb", "mongo"}:
                    db_meta["databaseUser"] = database_user
            if database_password is not None:
                if db_type == "mysql":
                    db_meta["databaseRootPassword"] = database_password
                elif db_type in {"mariadb", "mongo"}:
                    db_meta["databasePassword"] = database_password
            if db_meta:
                payload["metadata"] = {db_type: db_meta}

    result = c.client.post("/backup.update", json=payload)
    c.output.success(f"Backup '{backup_id}' updated")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("remove")
def remove(
    ctx: typer.Context,
    backup_id: Annotated[str, typer.Argument(help="Backup config ID to remove")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Remove a backup configuration (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Remove backup config '{backup_id}'? This cannot be undone.", abort=True)
    result = c.client.post("/backup.remove", json={"backupId": backup_id})
    c.output.success(f"Backup config '{backup_id}' removed")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("run")
def run_backup(
    ctx: typer.Context,
    backup_id: Annotated[str, typer.Argument(help="Backup config ID")],
    backup_type: Annotated[
        str | None,
        typer.Option(
            "--type",
            "-t",
            help="Override auto-detection. Values: postgres, mysql, mariadb, mongo, compose, web-server, libsql.",
        ),
    ] = None,
) -> None:
    """Trigger a manual backup run.

    Auto-detects the backup type by looking up the config via /backup.one when
    --type isn't given. For `backupType=compose`, Dokploy uses
    /backup.manualBackupCompose — this endpoint requires the backup's
    metadata.<db_type>.databaseUser field to be populated (otherwise the
    resulting shell script runs `$(null ...)` and fails with
    `bash: line 15: null: command not found`).
    """
    c: AppContext = ctx.obj
    endpoint_map = {
        "postgres": "/backup.manualBackupPostgres",
        "mysql": "/backup.manualBackupMySql",
        "mariadb": "/backup.manualBackupMariadb",
        "mongo": "/backup.manualBackupMongo",
        "compose": "/backup.manualBackupCompose",
        "web-server": "/backup.manualBackupWebServer",
        "libsql": "/backup.manualBackupLibsql",
    }

    # Auto-detect when --type not given.
    if backup_type is None:
        existing = c.client.get("/backup.one", params={"backupId": backup_id})
        if not isinstance(existing, dict):
            c.output.error(f"Backup '{backup_id}' not found")
            raise typer.Exit(1)
        bt = existing.get("backupType")
        dt = existing.get("databaseType")
        if bt == "compose":
            backup_type = "compose"
            # Pre-flight check: Dokploy's compose-backup template needs metadata.
            if dt in {"postgres", "mariadb", "mysql", "mongo"}:
                meta = (existing.get("metadata") or {}).get(dt)
                if not meta:
                    c.output.error(
                        f"Backup '{backup_id}' (compose, {dt}) has no metadata.{dt} set.\n"
                        f"Dokploy's template will emit a null command. Run:\n"
                        f"  kctl-dokploy backups update {backup_id} --database-user <role>"
                        + (" --database-password <pass>" if dt in {"mariadb", "mysql", "mongo"} else "")
                    )
                    raise typer.Exit(1)
        elif bt == "database":
            backup_type = dt or "postgres"
        else:
            backup_type = "postgres"

    endpoint = endpoint_map.get(backup_type)
    if not endpoint:
        c.output.error(f"Unknown backup type '{backup_type}'. Use: {', '.join(endpoint_map)}")
        raise typer.Exit(1)
    c.output.info(f"Running {backup_type} backup '{backup_id}'...")
    result = c.client.post(endpoint, json={"backupId": backup_id})
    c.output.success(f"Backup '{backup_id}' triggered successfully")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("list-files")
def list_files(
    ctx: typer.Context,
    destination_id: Annotated[str, typer.Option("--destination", "-d", help="S3 destination ID")],
    search: Annotated[
        str,
        typer.Option("--search", "-s", help="Case-sensitive substring filter on the key (empty = list all)"),
    ] = "",
    prefix: Annotated[str, typer.Option("--prefix", help="S3-side prefix filter (e.g. 'compose-foo/postgres/')")] = "",
    limit: Annotated[int, typer.Option("--limit", help="Max rows to show (default 200, 0=unlimited)")] = 200,
) -> None:
    """List backup files in an S3 destination via boto3 (bypasses Dokploy's buggy endpoint).

    Dokploy's native ``/backup.listBackupFiles`` rejects empty searches with
    "Input validation failed" and silently truncates results for compose
    backups. This command talks directly to S3 using the destination's stored
    credentials and paginates through the full bucket.
    """
    from kctl_dokploy.commands.backups_flow import _build_s3_client, _fetch_destination

    c: AppContext = ctx.obj
    dest = _fetch_destination(c, destination_id)
    bucket = dest.get("bucket") or ""
    if not bucket:
        c.output.error(f"Destination '{destination_id}' has no bucket")
        raise typer.Exit(1)
    s3 = _build_s3_client(dest)

    # Paginate list_objects_v2 under `prefix`, filter by `search` substring,
    # collect (key, size, lastmod). Sort by lastmod desc.
    entries: list[tuple[str, int, object]] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []) or []:
            k = obj.get("Key")
            if not isinstance(k, str):
                continue
            if search and search not in k:
                continue
            size = int(obj.get("Size") or 0)
            lm = obj.get("LastModified")
            entries.append((k, size, lm))
    # Newest first
    entries.sort(key=lambda r: (r[2] is None, r[2]), reverse=True)
    if limit and limit > 0:
        entries = entries[:limit]

    def _fmt_size(n: int) -> str:
        f = float(n)
        for unit in ("B", "KB", "MB", "GB"):
            if f < 1024.0:
                return f"{f:.1f} {unit}" if unit != "B" else f"{int(f)} B"
            f /= 1024.0
        return f"{f:.1f} TB"

    rows = [[k, _fmt_size(size), str(lm) if lm is not None else "-"] for k, size, lm in entries]
    data_for_json = [
        {"key": k, "size": size, "lastModified": str(lm) if lm is not None else None} for k, size, lm in entries
    ]
    c.output.table(
        f"Backup Files in s3://{bucket}/{prefix}",
        [("Key", "cyan"), ("Size", ""), ("Last Modified", "dim")],
        rows,
        data_for_json=data_for_json,
    )


from kctl_dokploy.commands.backups_pull import (  # noqa: E402
    download as _download_impl,
    pull as _pull_impl,
    run_wait as _run_wait_impl,
)
from kctl_dokploy.commands.backups_restore import restore as _restore_impl  # noqa: E402

app.command("restore")(_restore_impl)
app.command("pull")(_pull_impl)
app.command("download")(_download_impl)
app.command("run-wait")(_run_wait_impl)


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
        rows.append([did, name, endpoint, bucket, region])
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
        "provider": "s3",
        "accessKey": access_key,
        "secretAccessKey": secret_key,
        "bucket": bucket,
        "region": region,
        "endpoint": endpoint or "",
    }
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
    # Fetch full destination details first (API requires all fields for test)
    try:
        dest = c.client.get("/destination.one", params={"destinationId": destination_id})
        if not isinstance(dest, dict):
            c.output.error("Destination not found")
            raise typer.Exit(1)
    except Exception as e:
        c.output.error(f"Failed to fetch destination: {e}")
        raise typer.Exit(1)
    payload = {
        "name": dest.get("name", ""),
        "bucket": dest.get("bucket", ""),
        "endpoint": dest.get("endpoint", ""),
        "accessKey": dest.get("accessKey", ""),
        "secretAccessKey": dest.get("secretAccessKey", ""),
        "region": dest.get("region", ""),
        "provider": dest.get("provider", ""),
    }
    result = c.client.post("/destination.testConnection", json=payload)
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
