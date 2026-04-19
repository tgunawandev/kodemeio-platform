"""`kctl-dokploy backups restore` — Dokploy-native restore via tRPC SSE.

Wraps Dokploy's `backup.restoreBackupWithLogs` subscription. Streams the
server-side log lines to stdout prefixed with `[Dokploy]`. Exit codes:

  - 0: stream ended with a success marker (`Restore completed successfully`)
  - 1: stream emitted `Error:` / `❌`, or stream closed without success
  - 2: transport / auth failure — never reached the Dokploy log stream
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

import typer

from kctl_dokploy.core.async_client import build_async_dokploy_client
from kctl_dokploy.core.callbacks import AppContext
from kctl_lib.exceptions import APIError

SUCCESS_MARKERS = (
    "Restore completed successfully",
    "Backup done ✅",
    "✅ Restore completed",
)
ERROR_MARKERS = ("Error:", "❌")


def restore(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Option("--compose", "-c", help="Target compose ID on current Dokploy.")],
    destination_id: Annotated[str, typer.Option("--destination", "-d", help="S3 destination ID on current Dokploy.")],
    database_name: Annotated[
        str,
        typer.Option(
            "--database-name",
            help="Target database name inside the compose's postgres container. Required.",
        ),
    ],
    backup_file: Annotated[
        str | None,
        typer.Option("--file", help="S3 object key to restore. Required unless --latest is given."),
    ] = None,
    latest_for: Annotated[
        str | None,
        typer.Option(
            "--latest",
            help="Pick the newest S3 key (by LastModified) containing this substring.",
        ),
    ] = None,
    backup_type: Annotated[str, typer.Option("--backup-type", help="'compose' (default) or 'database'.")] = "compose",
    db_type: Annotated[str, typer.Option("--db-type", help="postgres|mysql|mariadb|mongo|libsql.")] = "postgres",
) -> None:
    """Restore a database from S3 into a compose via Dokploy's native API.

    Streams the Dokploy server-side restore log lines to stdout prefixed with
    [Dokploy]. Exits 0 on success, 1 on restore error, 2 on transport failure.
    """
    c: AppContext = ctx.obj

    if not backup_file and not latest_for:
        c.output.error("Provide exactly one of --file <s3-key> or --latest <substring>.")
        raise typer.Exit(2)
    if backup_file and latest_for:
        c.output.error("Use EITHER --file OR --latest, not both.")
        raise typer.Exit(2)

    if latest_for:
        from kctl_dokploy.commands.backups_flow import (
            _build_s3_client,
            _fetch_destination,
            _list_s3_keys,
        )

        dest = _fetch_destination(c, destination_id)
        s3 = _build_s3_client(dest)
        keys = _list_s3_keys(s3, dest["bucket"], prefix="", contains=latest_for)
        if not keys:
            c.output.error(f"No S3 objects in bucket '{dest['bucket']}' contain '{latest_for}'.")
            raise typer.Exit(1)
        backup_file = keys[-1]
        c.output.info(f"--latest resolved to: {backup_file}")

    payload: dict[str, Any] = {
        "json": {
            "backupType": backup_type,
            "databaseType": db_type,
            "databaseId": compose_id,
            "destinationId": destination_id,
            "databaseName": database_name,
            "backupFile": backup_file,
        }
    }

    async def _run() -> int:
        saw_success = False
        saw_error = False
        async with build_async_dokploy_client(c.profile) as client:
            try:
                async for line in client.stream_subscription("/trpc/backup.restoreBackupWithLogs", payload):
                    typer.echo(f"[Dokploy] {line}")
                    if any(m in line for m in SUCCESS_MARKERS):
                        saw_success = True
                    if any(m in line for m in ERROR_MARKERS):
                        saw_error = True
            except APIError as exc:
                c.output.error(f"Transport error ({exc.status_code}): {exc}")
                return 2

        if saw_error:
            return 1
        if saw_success:
            c.output.success("Restore finished")
            return 0
        c.output.warn("Stream closed without a success marker")
        return 1

    rc = asyncio.run(_run())
    raise typer.Exit(rc)
