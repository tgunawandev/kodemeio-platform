"""`kctl-dokploy backups restore` — Dokploy-native restore via tRPC SSE.

Wraps Dokploy's ``backup.restoreBackupWithLogs`` subscription. Streams the
server-side log lines to stdout prefixed with ``[Dokploy]``. Exit codes:

  - 0: stream ended with a success marker (``Restore completed successfully``)
       AND the post-restore verification passed (target DB has user tables).
  - 1: stream emitted ``Error:`` / ``❌``, or stream closed without success,
       or pre-flight / post-restore verification failed.
  - 2: transport / auth failure — never reached the Dokploy log stream.

Robustness features (added 2026-04-30 after a real-world TPP staging restore
failed silently with "Remote command failed exit 1"):

  * Pre-flight checks: compose exists + service name valid + S3 key
    reachable + target DB exists (or can be auto-created).
  * ``--ensure-db`` (default ON for postgres): runs ``createdb`` on the
    target before pg_restore if the DB doesn't exist. Idempotent.
  * ``--force``: drops + recreates the target DB before restore. Required
    when a previous partial restore left stale rows that would violate
    FK constraints during ``pg_restore --clean --if-exists``.
  * ``--stop-compose <id>``: stops a downstream compose (e.g. an Odoo
    staging app) before drop, so its persistent connections don't block
    ``DROP DATABASE``. Compose is restarted at the end.
  * Post-restore verification: confirms the restored DB has at least one
    user table — catches silent partial restores.
  * Failure diagnostics: on Dokploy "Remote command failed exit N" (which
    swallows pg_restore stderr), tails the postgres container logs via
    ``compose service-logs`` and prints them so the operator has
    something to debug.
"""

from __future__ import annotations

import asyncio
import time
from typing import Annotated, Any

import typer

from kctl_dokploy.commands.backups_flow import (
    _build_s3_client,
    _check_s3_object_exists,
    _die,
    _drop_and_recreate_db,
    _ensure_db_exists,
    _fetch_destination,
    _get_compose_one,
    _list_compose_services,
    _list_s3_keys,
    _verify_restore_populated,
)
from kctl_dokploy.core.async_client import build_async_dokploy_client
from kctl_dokploy.core.callbacks import AppContext
from kctl_lib.exceptions import APIError

SUCCESS_MARKERS = (
    "Restore completed successfully",
    "Backup done ✅",
    "✅ Restore completed",
)
ERROR_MARKERS = ("Error:", "❌")


def _tail_postgres_logs(c: AppContext, compose_id: str, service_name: str, lines: int = 80) -> str:
    """Fetch tail of the postgres service container logs. Returns "" on failure."""
    try:
        # /compose.serviceLogs is the same endpoint the `compose service-logs` command uses.
        # The exact API shape may vary by Dokploy version; we try a couple of candidates.
        for endpoint, params in (
            ("/compose.serviceLogs", {"composeId": compose_id, "serviceName": service_name, "tail": lines}),
            ("/compose.logs", {"composeId": compose_id, "serviceName": service_name, "tail": lines}),
        ):
            try:
                data = c.client.get(endpoint, params=params)
            except APIError:
                continue
            if isinstance(data, str):
                return data
            if isinstance(data, dict) and "logs" in data and isinstance(data["logs"], str):
                return data["logs"]
    except Exception:  # noqa: BLE001 — best effort
        pass
    return ""


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
    service_name: Annotated[
        str | None,
        typer.Option(
            "--service-name",
            help=(
                "Compose service name for the target database container — REQUIRED "
                "for compose-embedded databases (e.g. 'postgres')."
            ),
        ),
    ] = None,
    database_user: Annotated[
        str | None,
        typer.Option(
            "--database-user",
            help="Database username for restore — REQUIRED for postgres/mariadb/mongo.",
        ),
    ] = None,
    database_password: Annotated[
        str | None,
        typer.Option(
            "--database-password",
            help=("Database password for restore — REQUIRED for mariadb/mongo; MySQL uses this as the root password."),
        ),
    ] = None,
    ensure_db: Annotated[
        bool,
        typer.Option(
            "--ensure-db/--no-ensure-db",
            help=("Pre-create the target database if it doesn't exist (postgres only). Idempotent. Default ON."),
        ),
    ] = True,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help=(
                "DESTRUCTIVE: drop + recreate the target database before pg_restore. "
                "Use when a previous partial restore left stale rows that cause FK errors."
            ),
        ),
    ] = False,
    stop_compose: Annotated[
        str | None,
        typer.Option(
            "--stop-compose",
            help=(
                "Compose ID to stop before --force drops the DB (e.g. the staging Odoo "
                "compose). Restarted automatically at the end."
            ),
        ),
    ] = None,
    skip_preflight: Annotated[
        bool,
        typer.Option("--skip-preflight", help="Skip compose/S3/DB pre-flight checks (not recommended)."),
    ] = False,
    skip_verify: Annotated[
        bool,
        typer.Option("--skip-verify", help="Skip post-restore verification that target DB has user tables."),
    ] = False,
) -> None:
    """Restore a database from S3 into a compose via Dokploy's native API.

    Streams the Dokploy server-side restore log lines to stdout prefixed with
    ``[Dokploy]``. Exits 0 on success, 1 on restore error or failed
    verification, 2 on transport failure.
    """
    c: AppContext = ctx.obj

    if not backup_file and not latest_for:
        c.output.error("Provide exactly one of --file <s3-key> or --latest <substring>.")
        raise typer.Exit(2)
    if backup_file and latest_for:
        c.output.error("Use EITHER --file OR --latest, not both.")
        raise typer.Exit(2)

    # Fail-fast metadata validation.
    if backup_type == "compose" and service_name is None:
        _die(c, "--service-name is required when restoring a compose-embedded backup")
    if db_type == "postgres" and database_user is None:
        _die(c, "--database-user is required for postgres restores")
    if force and not stop_compose and db_type == "postgres":
        c.output.warn(
            "--force without --stop-compose may fail to drop the DB if a downstream "
            "compose (e.g. Odoo) is keeping connections open."
        )

    # Resolve --latest into a concrete S3 key.
    if latest_for:
        dest = _fetch_destination(c, destination_id)
        s3 = _build_s3_client(dest)
        keys = _list_s3_keys(s3, dest["bucket"], prefix="", contains=latest_for)
        if not keys:
            c.output.error(f"No S3 objects in bucket '{dest['bucket']}' contain '{latest_for}'.")
            raise typer.Exit(1)
        backup_file = keys[-1]
        c.output.info(f"--latest resolved to: {backup_file}")

    # ---- Pre-flight checks (compose + service + S3 key + DB) ------------
    if not skip_preflight:
        c.output.info("Pre-flight: validating compose, service, S3 key, and target DB ...")
        compose = _get_compose_one(c, compose_id)
        compose_status = compose.get("composeStatus") or compose.get("applicationStatus") or "unknown"
        if compose_status not in ("done", "running", "idle"):
            c.output.warn(f"Pre-flight: compose status is '{compose_status}' (expected 'done').")
        if backup_type == "compose" and service_name is not None:
            services = _list_compose_services(c, compose_id)
            if services and service_name not in services:
                _die(
                    c,
                    f"Pre-flight: service '{service_name}' not in compose services {services}. "
                    f"Pass the exact service name from the compose YAML.",
                )
        # S3 key reachability
        try:
            dest = _fetch_destination(c, destination_id)
            s3 = _build_s3_client(dest)
            ok, err = _check_s3_object_exists(s3, dest["bucket"], backup_file)  # type: ignore[arg-type]
            if not ok:
                _die(c, f"Pre-flight: S3 key not reachable: {backup_file}: {err}")
        except APIError as exc:
            _die(c, f"Pre-flight: cannot fetch destination '{destination_id}': {exc}")
        # DB existence (postgres only) — handled by --ensure-db / --force below
        c.output.success("Pre-flight passed.")

    # ---- Optional: stop the consuming compose before destructive ops ----
    stopped_compose = False
    if force and stop_compose:
        c.output.info(f"Stopping consuming compose '{stop_compose}' to release DB sessions ...")
        try:
            c.client.post("/compose.stop", json={"composeId": stop_compose})
            stopped_compose = True
            time.sleep(5)  # give it a moment to actually disconnect
        except APIError as exc:
            c.output.warn(f"Failed to stop compose '{stop_compose}': {exc}. Continuing anyway.")

    try:
        # ---- Force drop+recreate, OR ensure-db ------------------------------
        if db_type == "postgres" and service_name is not None and database_user is not None:
            if force:
                c.output.info(f"--force: dropping and recreating '{database_name}' ...")
                ok, msg = _drop_and_recreate_db(
                    c,
                    compose_id=compose_id,
                    service_name=service_name,
                    database_user=database_user,
                    database_name=database_name,
                )
                if not ok:
                    _die(c, f"--force drop+recreate failed: {msg}")
                c.output.success(f"Database recreated ({msg}).")
            elif ensure_db:
                ok, msg = _ensure_db_exists(
                    c,
                    compose_id=compose_id,
                    service_name=service_name,
                    database_user=database_user,
                    database_name=database_name,
                )
                if not ok:
                    _die(c, f"--ensure-db failed: {msg}")
                c.output.info(f"Target DB '{database_name}': {msg}.")

        # ---- Build and dispatch the Dokploy restore SSE ---------------------
        metadata: dict[str, Any] = {}
        if service_name is not None:
            metadata["serviceName"] = service_name
        if db_type == "postgres":
            if database_user is not None:
                metadata["postgres"] = {"databaseUser": database_user}
        elif db_type == "mariadb":
            if database_user is not None or database_password is not None:
                metadata["mariadb"] = {
                    "databaseUser": database_user or "",
                    "databasePassword": database_password or "",
                }
        elif db_type == "mongo":
            if database_user is not None or database_password is not None:
                metadata["mongo"] = {
                    "databaseUser": database_user or "",
                    "databasePassword": database_password or "",
                }
        elif db_type == "mysql":
            if database_password is not None:
                metadata["mysql"] = {"databaseRootPassword": database_password}

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
        if metadata:
            payload["json"]["metadata"] = metadata

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
                return 0
            c.output.warn("Stream closed without a success marker")
            return 1

        rc = asyncio.run(_run())

        # ---- On failure: surface postgres container logs --------------------
        if rc == 1 and service_name is not None:
            c.output.warn(
                "Restore reported failure. Dokploy collapses pg_restore stderr to a single exit code; "
                f"fetching last 80 lines of '{service_name}' container logs to help diagnose ..."
            )
            log_tail = _tail_postgres_logs(c, compose_id, service_name, lines=80)
            if log_tail:
                typer.echo("---- postgres container logs (tail) ----")
                typer.echo(log_tail)
                typer.echo("---- end logs ----")
            else:
                c.output.warn("Could not fetch container logs via Dokploy API.")
            if not force:
                c.output.info(
                    "Common cause: the target DB exists with stale data and "
                    "pg_restore --clean --if-exists hits FK violations. "
                    "Re-run with --force (and --stop-compose <id> if a downstream "
                    "compose holds connections) to drop+recreate the DB cleanly."
                )

        # ---- Post-restore verification --------------------------------------
        if (
            rc == 0
            and not skip_verify
            and db_type == "postgres"
            and service_name is not None
            and database_user is not None
        ):
            c.output.info("Verifying restored DB is populated ...")
            if _verify_restore_populated(
                c,
                compose_id=compose_id,
                service_name=service_name,
                database_user=database_user,
                database_name=database_name,
            ):
                c.output.success(f"Verification passed: '{database_name}' has user tables.")
            else:
                c.output.error(
                    f"Verification FAILED: '{database_name}' has no user tables after a 'successful' "
                    "restore. This indicates a silent partial failure inside Dokploy's restore."
                )
                rc = 1

        if rc == 0:
            c.output.success("Restore finished")

        raise typer.Exit(rc)

    finally:
        if stopped_compose and stop_compose:
            c.output.info(f"Restarting consuming compose '{stop_compose}' ...")
            try:
                c.client.post("/compose.start", json={"composeId": stop_compose})
            except APIError as exc:
                c.output.warn(f"Failed to restart compose '{stop_compose}': {exc}")
