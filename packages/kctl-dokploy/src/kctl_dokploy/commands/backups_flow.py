"""Shared helpers for backup/restore workflow commands.

Commands that used SSH + docker exec (dump-compose, download, run-wait,
restore-local, refresh) were removed in the Dokploy-native redesign.
The helpers below are still used by ``backups restore`` (backups_restore.py).
"""

from __future__ import annotations

from typing import Any

import typer

from kctl_dokploy.core.callbacks import AppContext

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
