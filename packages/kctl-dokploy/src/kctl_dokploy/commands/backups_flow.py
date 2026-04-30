"""Shared helpers for backup/restore workflow commands.

Commands that used SSH + docker exec (dump-compose, download, run-wait,
restore-local, refresh) were removed in the Dokploy-native redesign.
The helpers below are still used by ``backups restore`` (backups_restore.py).
"""

from __future__ import annotations

import secrets
from typing import Any

import typer

from kctl_dokploy.core.callbacks import AppContext
from kctl_lib.exceptions import APIError

app = typer.Typer(help="Backup/restore workflow commands.")


# ---------------------------------------------------------------------------
# Error helpers — typer.Exit takes an int code, not a string. These helpers
# emit a visible error and raise typer.Exit(1), avoiding the silent-failure
# footgun of `raise typer.Exit("some message")`.
# ---------------------------------------------------------------------------


def _die(c: AppContext, msg: str) -> None:
    """Print error via AppContext and exit 1."""
    c.output.error(msg)
    raise typer.Exit(1)


def _die_plain(msg: str) -> None:
    """Print error without an AppContext (for module-level helpers) and exit 1."""
    typer.echo(f"ERROR: {msg}", err=True)
    raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Shared helpers (used by backups_restore.py)
# ---------------------------------------------------------------------------


def _fetch_destination(c: AppContext, destination_id: str) -> dict[str, Any]:
    """Fetch destination details (creds + bucket) from Dokploy."""
    dest = c.client.get("/destination.one", params={"destinationId": destination_id})
    if not isinstance(dest, dict):
        _die(c, f"Destination '{destination_id}' not found")
    return dest  # type: ignore[return-value]


def _build_s3_client(dest: dict[str, Any]) -> Any:
    """Build a boto3 S3 client from a Dokploy destination record."""
    import boto3

    endpoint = dest.get("endpoint") or None
    region = dest.get("region") or "us-east-1"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=dest["accessKey"],
        aws_secret_access_key=dest["secretAccessKey"],
        region_name=region,
    )


def _list_s3_keys(s3: Any, bucket: str, prefix: str = "", contains: str = "") -> list[str]:
    """Recursively list all object keys in `bucket` under `prefix` via boto3.

    Handles pagination and filters by a case-sensitive substring. Works for
    any S3-compatible endpoint and doesn't go through Dokploy's broken
    listBackupFiles endpoint. Returns keys sorted by `LastModified` ascending
    — so callers wanting "the latest" can use `keys[-1]`.
    """
    rows: list[tuple[str, Any]] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []) or []:
            k = obj.get("Key")
            if not isinstance(k, str):
                continue
            if contains and contains not in k:
                continue
            rows.append((k, obj.get("LastModified")))
    # Sort by LastModified; tuples where LastModified is None sink to the top.
    rows.sort(key=lambda r: (r[1] is None, r[1]))
    return [k for k, _ in rows]


def _get_compose_one(c: AppContext, compose_id: str) -> dict[str, Any]:
    """Fetch /compose.one and fail loudly on bad shape."""
    data = c.client.get("/compose.one", params={"composeId": compose_id})
    if not isinstance(data, dict):
        _die(c, f"Compose '{compose_id}' not found")
    return data  # type: ignore[return-value]


def _get_compose_app_name(c: AppContext, compose_id: str) -> str:
    """Return the Dokploy-generated appName (used in container naming)."""
    data = _get_compose_one(c, compose_id)
    app_name = data.get("appName") or data.get("name") or ""
    if not app_name:
        _die(c, f"Compose '{compose_id}' has no appName")
    return str(app_name)


def _parse_env_str(env_str: str) -> dict[str, str]:
    """Parse a multi-line KEY=VALUE env block into a dict, stripping surrounding quotes."""
    values: dict[str, str] = {}
    for line in env_str.strip().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition("=")
            values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def _get_compose_db_creds(c: AppContext, compose_id: str) -> tuple[str, str, str]:
    """Return (postgres_user, postgres_password, postgres_db) from the compose env.

    Raises typer.Exit if POSTGRES_PASSWORD is missing — we need it for pg_dump/restore.
    """
    data = _get_compose_one(c, compose_id)
    env_str = data.get("env", "") if isinstance(data.get("env"), str) else ""
    values = _parse_env_str(env_str)
    user = values.get("POSTGRES_USER", "postgres")
    password = values.get("POSTGRES_PASSWORD", "")
    db = values.get("POSTGRES_DB", "postgres")
    if not password:
        _die(c, f"POSTGRES_PASSWORD not found in compose '{compose_id}' env")
    return user, password, db


# ---------------------------------------------------------------------------
# Compose / service introspection — used by `backups restore` pre-flight.
# ---------------------------------------------------------------------------


def _list_compose_services(c: AppContext, compose_id: str) -> list[str]:
    """Return service names declared in the compose. Empty list on failure
    rather than raising — pre-flight should report a friendly message."""
    try:
        services = c.client.get("/compose.loadServices", params={"composeId": compose_id})
    except APIError:
        return []
    if isinstance(services, list):
        out: list[str] = []
        for entry in services:
            if isinstance(entry, str):
                out.append(entry)
            elif isinstance(entry, dict):
                name = entry.get("name") or entry.get("serviceName")
                if isinstance(name, str):
                    out.append(name)
        return out
    return []


def _check_s3_object_exists(s3: Any, bucket: str, key: str) -> tuple[bool, str | None]:
    """head_object the S3 key. Returns (exists, error_message_if_any)."""
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True, None
    except Exception as exc:  # noqa: BLE001 — boto/botocore exceptions are diverse
        return False, str(exc)


# ---------------------------------------------------------------------------
# Run-on-remote helper — schedules a one-off command inside a compose
# service container, runs it via Dokploy's runManually endpoint, and cleans
# up the schedule afterward. This is the only available mechanism (today)
# for executing arbitrary commands inside a Dokploy-managed container
# without SSH access — Dokploy has no `compose exec` API.
# ---------------------------------------------------------------------------


def _run_remote_command(
    c: AppContext,
    *,
    compose_id: str,
    service_name: str,
    command: str,
    name_hint: str = "kctl-oneoff",
    shell: str = "sh",
) -> tuple[bool, str]:
    """Run *command* inside the named compose service container.

    Returns ``(ok, message)``. ``ok=True`` means Dokploy reported the schedule
    run as successful (remote command exit 0). ``ok=False`` covers both
    remote-non-zero and transport errors — the *message* carries the API
    detail. The temporary schedule is always deleted on the way out.

    Why this dance instead of SSH:
      Dokploy doesn't expose a `compose exec` endpoint. Schedules are the
      only API surface that runs `docker exec sh -c "<command>"` inside
      a service container. A successful runManually call means exit 0;
      a 500 from the API means non-zero exit (Dokploy collapses pg_restore
      stderr — see surface_logs in the failure path of backups restore).

    Caveats:
      * Dokploy's schedule.update endpoint rejects shell metacharacters
        in the *command* field with HTTP 400. We therefore always
        delete + recreate, never update.
      * `createdb` exits 1 if the DB already exists. Callers that need
        idempotent behavior should wrap the command (e.g. prepend a
        `psql -c "SELECT 1 FROM pg_database WHERE datname='X'" | grep -q 1 ||`
        guard, or follow with a SELECT to verify state).
    """
    name = f"{name_hint}-{secrets.token_hex(4)}"
    payload: dict[str, Any] = {
        "name": name,
        "cronExpression": "0 0 31 12 0",  # never auto-fires
        "command": command,
        "scheduleType": "compose",
        "composeId": compose_id,
        "serviceName": service_name,
        "shellType": shell,
    }
    try:
        created = c.client.post("/schedule.create", json=payload)
    except APIError as exc:
        return False, f"schedule.create failed: {exc}"
    sid = created.get("scheduleId", "") if isinstance(created, dict) else ""
    if not sid:
        return False, "schedule.create returned no scheduleId"
    try:
        try:
            c.client.post("/schedule.runManually", json={"scheduleId": sid})
            return True, "ok"
        except APIError as exc:
            # Dokploy returns 500 with "Remote command failed with exit code N"
            # for ANY non-zero exit from the docker exec. We can't read stderr.
            return False, str(exc)
    finally:
        try:
            c.client.post("/schedule.delete", json={"scheduleId": sid})
        except APIError:
            pass  # best-effort cleanup; surface a warning rather than fail loud


def _check_db_exists(
    c: AppContext,
    *,
    compose_id: str,
    service_name: str,
    database_user: str,
    database_name: str,
) -> bool:
    """Return True if the named DB exists on the compose's postgres container.

    Implementation: runs ``psql -tAc "SELECT 1 FROM pg_database WHERE datname=$$X$$" | grep -q 1``
    via Dokploy schedules. Schedule run exit 0 (Dokploy 200) → DB exists.
    Anything else → assume missing (the caller should treat this as "create
    me one"). Safe to false-negative — over-creates are guarded by callers.

    Uses PostgreSQL dollar-quoting (``$$X$$``) instead of single quotes for
    SQL string literals, with the leading dollars shell-escaped (``\\$\\$``)
    so the shell preserves them rather than expanding ``$$`` to PID. Dokploy's
    schedule API silently mangles single-quote-containing SQL inside
    double-quoted shell args (empirically observed on tpp-infra-postgres),
    so this is the only encoding that survives transport intact.
    """
    cmd = (
        f"psql -U {database_user} -d postgres -tAc "
        f'"SELECT 1 FROM pg_database WHERE datname=\\$\\${database_name}\\$\\$" '
        f"| grep -q 1"
    )
    ok, _ = _run_remote_command(
        c,
        compose_id=compose_id,
        service_name=service_name,
        command=cmd,
        name_hint=f"check-db-{database_name}",
    )
    return ok


def _ensure_db_exists(
    c: AppContext,
    *,
    compose_id: str,
    service_name: str,
    database_user: str,
    database_name: str,
) -> tuple[bool, str]:
    """Create *database_name* on the compose's postgres if it doesn't exist.

    Idempotent. Returns (success, message). Verifies post-condition via
    ``_check_db_exists`` so a misleading createdb exit code (it returns 1
    on "already exists") is interpreted correctly.
    """
    if _check_db_exists(
        c,
        compose_id=compose_id,
        service_name=service_name,
        database_user=database_user,
        database_name=database_name,
    ):
        return True, "already exists"
    cmd = f"createdb -U {database_user} -O {database_user} {database_name}"
    _run_remote_command(
        c,
        compose_id=compose_id,
        service_name=service_name,
        command=cmd,
        name_hint=f"createdb-{database_name}",
    )
    # Trust the post-state check, not the createdb exit code.
    if _check_db_exists(
        c,
        compose_id=compose_id,
        service_name=service_name,
        database_user=database_user,
        database_name=database_name,
    ):
        return True, "created"
    return False, "createdb did not result in an existing database"


def _drop_and_recreate_db(
    c: AppContext,
    *,
    compose_id: str,
    service_name: str,
    database_user: str,
    database_name: str,
    max_attempts: int = 3,
) -> tuple[bool, str]:
    """Force-recreate the DB. Terminates active sessions and drops first.

    If active sessions persist (e.g. a downstream app like Odoo keeps
    reconnecting), retries up to *max_attempts* times. Returns
    ``(ok, message)``; on failure the caller should suggest stopping the
    consuming compose with --stop-compose.
    """
    revoke = (
        f"psql -U {database_user} -d postgres -c "
        f'"REVOKE CONNECT ON DATABASE {database_name} FROM PUBLIC, {database_user};"'
    )
    # Dollar-quoted DB name (\$\$X\$\$) survives Dokploy's command transport
    # where 'X'-style SQL string literals get mangled. See _check_db_exists.
    terminate = (
        f"psql -U {database_user} -d postgres -c "
        f'"SELECT pg_terminate_backend(pid) FROM pg_stat_activity '
        f'WHERE datname=\\$\\${database_name}\\$\\$ AND pid<>pg_backend_pid();"'
    )
    drop = f"dropdb -U {database_user} --if-exists {database_name}"
    create = f"createdb -U {database_user} -O {database_user} {database_name}"
    grant = (
        f"psql -U {database_user} -d postgres -c "
        f'"GRANT CONNECT ON DATABASE {database_name} TO PUBLIC, {database_user};"'
    )

    last_msg = ""
    for attempt in range(1, max_attempts + 1):
        # revoke + terminate are best-effort; failures are non-fatal
        _run_remote_command(
            c, compose_id=compose_id, service_name=service_name, command=revoke, name_hint=f"revoke-{database_name}"
        )
        _run_remote_command(
            c,
            compose_id=compose_id,
            service_name=service_name,
            command=terminate,
            name_hint=f"terminate-{database_name}",
        )
        ok, msg = _run_remote_command(
            c, compose_id=compose_id, service_name=service_name, command=drop, name_hint=f"drop-{database_name}"
        )
        if not ok:
            last_msg = msg
            if attempt < max_attempts:
                continue
            # Always re-grant before bailing so we don't leave the DB locked.
            _run_remote_command(
                c, compose_id=compose_id, service_name=service_name, command=grant, name_hint=f"grant-{database_name}"
            )
            return False, (
                f"dropdb failed after {max_attempts} attempts (active sessions persist?): {msg}. "
                f"Stop the consuming compose first or pass --stop-compose <id>."
            )
        ok, msg = _run_remote_command(
            c, compose_id=compose_id, service_name=service_name, command=create, name_hint=f"create-{database_name}"
        )
        # Always re-grant whether create succeeded or not.
        _run_remote_command(
            c, compose_id=compose_id, service_name=service_name, command=grant, name_hint=f"grant-{database_name}"
        )
        if not ok:
            return False, f"createdb failed: {msg}"
        return True, f"recreated (attempt {attempt})"
    return False, last_msg or "drop+recreate exhausted retries"


def _verify_restore_populated(
    c: AppContext,
    *,
    compose_id: str,
    service_name: str,
    database_user: str,
    database_name: str,
) -> bool:
    """Sanity-check that the restored DB has at least one user table.

    A "successful" Dokploy restore that produced an empty DB is a silent
    failure — pg_restore can claim victory after dropping objects but
    failing to recreate them. This catches that.
    """
    # Use ``current_schema()`` instead of a string literal ``'public'`` so
    # the SQL has no embedded single quotes. Dokploy's command transport
    # silently mangles ``'X'``-style SQL inside double-quoted shell args
    # (see _check_db_exists for the workaround story). For a default psql
    # session against an Odoo DB, current_schema() resolves to 'public'.
    sql = "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname=current_schema()"
    cmd = f'count=$(psql -U {database_user} -d {database_name} -tAc "{sql}") && [ "$count" -gt 0 ]'
    ok, _ = _run_remote_command(
        c,
        compose_id=compose_id,
        service_name=service_name,
        command=cmd,
        name_hint=f"verify-{database_name}",
    )
    return ok
