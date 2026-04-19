"""`kctl-dokploy backups pull / download / run-wait` — smooth backup+restore flow.

These commands re-introduce the "download a dump file from S3 and restore it
locally" convenience workflow that was removed during the Dokploy-native
redesign. The native `backups restore` command is still the right tool for
restoring INTO a Dokploy-managed compose on the same host. These commands are
for the common dev-loop case of pulling a production dump onto a developer's
workstation (a raw postgres, not Dokploy-managed).

Shared helpers (`_fetch_destination`, `_build_s3_client`,
`_get_compose_app_name`) live in ``backups_flow.py``.
"""

from __future__ import annotations

import gzip
import os
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer

from kctl_dokploy.commands.backups_flow import (
    _build_s3_client,
    _die,
    _fetch_destination,
    _get_compose_app_name,
)
from kctl_dokploy.core.callbacks import AppContext


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fetch_backup(c: AppContext, backup_id: str) -> dict[str, Any]:
    data = c.client.get("/backup.one", params={"backupId": backup_id})
    if not isinstance(data, dict):
        _die(c, f"Backup '{backup_id}' not found")
    return data  # type: ignore[return-value]


def _get_search_prefixes(c: AppContext, backup: dict[str, Any]) -> list[str]:
    """Return the list of candidate S3 prefixes to search for this backup config.

    Dokploy's S3 path convention changed across versions:

    * OLD (flat, legacy):
      ``<backup.prefix>-<timestamp>.<ext>``  — e.g.
      ``tpp-infra-postgres/tpp_odoo_erp-2026-04-18T04-09-13Z.dump``
    * NEW (hierarchical, current Dokploy):
      ``<compose.appName>_<serviceName>/<backup.prefix>/<timestamp>.<ext>`` — e.g.
      ``compose-foo_postgres/tpp-infra-postgres/tpp_odoo_erp/2026-04-19T11-24-29Z.sql.gz``

    When ``serviceName`` is absent we also try ``<appName>/`` as a looser
    fallback. The prefix is used verbatim (no forced trailing slash): the
    OLD layout concatenates ``<prefix>-<timestamp>`` with a ``-`` separator,
    while the NEW layout puts the prefix inside a directory and appends a
    bare ``<timestamp>.<ext>`` filename.

    For compose backups we return BOTH new/old candidates, de-duplicated,
    new-first. For non-compose backup types (postgres/mysql/mariadb/mongo)
    there is no compose wrapping, so we return just the stored prefix.
    """
    raw_prefix = (backup.get("prefix") or "").strip("/")
    old_prefix = raw_prefix

    compose_id = backup.get("composeId")
    if not compose_id or not isinstance(compose_id, str):
        return [old_prefix] if old_prefix else []

    app_name = _get_compose_app_name(c, compose_id).strip("/")
    if not app_name:
        return [old_prefix] if old_prefix else []

    service_name = (backup.get("serviceName") or "").strip("/")
    # Build the NEW hierarchical directory prefix. Prefer
    # "<appName>_<serviceName>/" (matches observed Dokploy behavior);
    # also try the bare "<appName>/" as a looser fallback.
    new_dirs: list[str] = []
    if service_name:
        new_dirs.append(f"{app_name}_{service_name}")
    new_dirs.append(app_name)

    candidates: list[str] = []
    for d in new_dirs:
        candidates.append(f"{d}/{raw_prefix}/" if raw_prefix else f"{d}/")
    candidates.append(old_prefix)

    # De-dup while preserving order (new first — prefer hierarchical layout).
    seen: set[str] = set()
    out: list[str] = []
    for p in candidates:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _collect_s3_objects_under_prefixes(
    s3: Any,
    bucket: str,
    prefixes: list[str],
    contains: str = "",
) -> list[tuple[str, datetime]]:
    """Return ``(key, LastModified)`` tuples across all candidate prefixes.

    Missing / empty prefixes are silently skipped. If ``contains`` is set,
    only keys whose name contains that substring are included (defense-in-depth
    filter for DB name).
    """
    rows: list[tuple[str, datetime]] = []
    paginator = s3.get_paginator("list_objects_v2")
    for prefix in prefixes:
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []) or []:
                k = obj.get("Key")
                lm = obj.get("LastModified")
                if not isinstance(k, str) or lm is None:
                    continue
                if contains and contains not in k:
                    continue
                if lm.tzinfo is None:
                    lm = lm.replace(tzinfo=UTC)
                rows.append((k, lm))
    return rows


def _find_latest_s3_key(
    s3: Any,
    bucket: str,
    prefixes: list[str],
    contains: str = "",
) -> str | None:
    """Return the newest ``Key`` across all candidate prefixes, or ``None``."""
    rows = _collect_s3_objects_under_prefixes(s3, bucket, prefixes, contains=contains)
    if not rows:
        return None
    rows.sort(key=lambda r: r[1])
    return rows[-1][0]


def _run_backup_now(c: AppContext, existing: dict[str, Any], backup_id: str) -> None:
    """Trigger the appropriate /backup.manualBackup* endpoint for this config."""
    endpoint_map = {
        "postgres": "/backup.manualBackupPostgres",
        "mysql": "/backup.manualBackupMySql",
        "mariadb": "/backup.manualBackupMariadb",
        "mongo": "/backup.manualBackupMongo",
        "compose": "/backup.manualBackupCompose",
        "web-server": "/backup.manualBackupWebServer",
        "libsql": "/backup.manualBackupLibsql",
    }
    bt = existing.get("backupType")
    dt = existing.get("databaseType")
    if bt == "compose":
        endpoint = endpoint_map["compose"]
        # Pre-flight: compose templates need metadata.<db_type>.databaseUser
        # (and optionally password for mysql/mariadb/mongo).
        if dt in {"postgres", "mariadb", "mysql", "mongo"}:
            meta = (existing.get("metadata") or {}).get(dt)
            if not meta:
                _die(
                    c,
                    f"Backup '{backup_id}' (compose, {dt}) has no metadata.{dt} set. "
                    f"Run: kctl-dokploy backups update {backup_id} --database-user <role>"
                    + (" --database-password <pass>" if dt in {"mariadb", "mysql", "mongo"} else ""),
                )
    elif bt == "database":
        endpoint = endpoint_map.get(dt or "postgres", endpoint_map["postgres"])
    else:
        endpoint = endpoint_map["postgres"]

    c.output.info(f"Triggering manual backup via {endpoint} ...")
    c.client.post(endpoint, json={"backupId": backup_id})


def _wait_for_new_object(
    c: AppContext,
    s3: Any,
    bucket: str,
    prefixes: list[str],
    after: datetime,
    timeout: int,
    poll_interval: int,
    contains: str = "",
) -> str:
    """Poll S3 until an object whose ``LastModified`` is strictly after ``after`` appears.

    Scans all candidate prefixes (new hierarchical + old flat) and returns
    the newest matching key found under ANY of them. Exits 1 on timeout.
    """
    deadline = time.time() + timeout
    attempt = 0
    pretty_prefixes = ", ".join(repr(p) for p in prefixes) or "''"
    while time.time() < deadline:
        attempt += 1
        all_rows = _collect_s3_objects_under_prefixes(s3, bucket, prefixes, contains=contains)
        candidates = [(k, lm) for k, lm in all_rows if lm > after]
        if candidates:
            candidates.sort(key=lambda r: r[1])
            newest = candidates[-1][0]
            c.output.success(f"New backup file detected: {newest}")
            return newest
        remaining = max(0, int(deadline - time.time()))
        c.output.info(
            f"  poll #{attempt}: no new files under {pretty_prefixes} yet "
            f"(elapsed {attempt * poll_interval}s, {remaining}s remaining)"
        )
        time.sleep(poll_interval)
    _die(c, f"Timed out after {timeout}s waiting for a new backup under prefixes {pretty_prefixes}")
    return ""  # unreachable — _die raises


def _human_size(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024.0:
            return f"{f:.1f} {unit}" if unit != "B" else f"{int(f)} {unit}"
        f /= 1024.0
    return f"{f:.1f} PB"


def _download_key(c: AppContext, s3: Any, bucket: str, key: str, dest_path: Path) -> int:
    """Download `key` from `bucket` to `dest_path`. Returns downloaded size in bytes."""
    c.output.info(f"Downloading s3://{bucket}/{key} -> {dest_path} ...")
    t0 = time.time()
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    s3.download_file(bucket, key, str(dest_path))
    size = dest_path.stat().st_size
    elapsed = time.time() - t0
    rate = size / elapsed if elapsed > 0 else size
    c.output.success(f"Downloaded {_human_size(size)} in {elapsed:.1f}s ({_human_size(int(rate))}/s)")
    return size


def _maybe_decompress(c: AppContext, src: Path) -> Path:
    """If `src` ends in .gz, gunzip to a sibling file and return that path.

    If not gzipped, return `src` unchanged.
    """
    if src.suffix != ".gz":
        return src
    dest = src.with_suffix("")  # strip .gz
    c.output.info(f"Decompressing {src.name} -> {dest.name} ...")
    with gzip.open(src, "rb") as gz_in, open(dest, "wb") as out:
        shutil.copyfileobj(gz_in, out)
    return dest


def _detect_format(path: Path) -> str:
    """Return 'custom' if PGDMP magic header is present, else 'plain'."""
    try:
        with open(path, "rb") as f:
            magic = f.read(5)
        return "custom" if magic.startswith(b"PGDMP") else "plain"
    except OSError:
        return "plain"


def _resolve_compose_postgres_container(
    c: AppContext,
    compose_id: str,
    service: str,
) -> str:
    """Find the running postgres container ID for a Dokploy-managed compose.

    Uses `docker ps` with compose project + service labels.
    """
    from kctl_dokploy.commands.backups_flow import _get_compose_app_name

    app_name = _get_compose_app_name(c, compose_id)
    cmd = [
        "docker",
        "ps",
        "-q",
        "--filter",
        "status=running",
        "--filter",
        f"label=com.docker.compose.project={app_name}",
        "--filter",
        f"label=com.docker.compose.service={service}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)  # noqa: S603
    if proc.returncode != 0:
        _die(c, f"docker ps failed: {proc.stderr.strip()}")
    cid = proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else ""
    if not cid:
        _die(
            c,
            f"No running postgres container found for compose '{compose_id}' (project={app_name}, service={service}).",
        )
    return cid


def _terminate_and_recreate_db(
    c: AppContext,
    *,
    host: str,
    port: int,
    admin_user: str,
    admin_password: str,
    target_db: str,
    owner: str | None,
    force: bool,
) -> None:
    """Drop target DB (terminating active connections) and recreate it."""
    if not force:
        typer.confirm(
            f"Drop and recreate database '{target_db}' on {host}:{port}? All data in this DB will be lost.",
            abort=True,
        )

    env = os.environ.copy()
    env["PGPASSWORD"] = admin_password

    def run_sql(sql: str) -> None:
        cmd = [
            "psql",
            "-h",
            host,
            "-p",
            str(port),
            "-U",
            admin_user,
            "-d",
            "postgres",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            sql,
        ]
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True)  # noqa: S603
        if proc.returncode != 0:
            _die(
                c,
                f"psql failed while running {sql!r}: {proc.stderr.strip() or proc.stdout.strip()}",
            )

    # Disconnect anyone still using it.
    run_sql(
        f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname = '{target_db}' AND pid <> pg_backend_pid()"
    )
    run_sql(f'DROP DATABASE IF EXISTS "{target_db}"')
    if owner:
        run_sql(f'CREATE DATABASE "{target_db}" OWNER "{owner}"')
    else:
        run_sql(f'CREATE DATABASE "{target_db}"')
    c.output.success(f"Target database '{target_db}' recreated.")


def _restore_to_raw_host(
    c: AppContext,
    *,
    dump_path: Path,
    fmt: str,
    host: str,
    port: int,
    user: str,
    password: str,
    target_db: str,
) -> None:
    """Run pg_restore (custom) or psql (plain) against a raw postgres host."""
    env = os.environ.copy()
    env["PGPASSWORD"] = password

    if fmt == "custom":
        cmd = [
            "pg_restore",
            "--no-owner",
            "--no-privileges",
            "--clean",
            "--if-exists",
            "-h",
            host,
            "-p",
            str(port),
            "-U",
            user,
            "-d",
            target_db,
            str(dump_path),
        ]
        c.output.info(f"Running pg_restore (custom format) -> {host}:{port}/{target_db} ...")
        proc = subprocess.run(cmd, env=env)  # noqa: S603
    else:
        cmd = [
            "psql",
            "-h",
            host,
            "-p",
            str(port),
            "-U",
            user,
            "-d",
            target_db,
            "-v",
            "ON_ERROR_STOP=1",
            "-f",
            str(dump_path),
        ]
        c.output.info(f"Running psql (plain SQL) -> {host}:{port}/{target_db} ...")
        proc = subprocess.run(cmd, env=env)  # noqa: S603

    # pg_restore often exits 1 on "errors ignored" from --clean --if-exists;
    # treat any non-zero as failure. Users should use --force only when they
    # know the source DB is clean.
    if proc.returncode != 0:
        _die(c, f"Restore command failed with exit code {proc.returncode}")
    c.output.success("Restore completed.")


def _restore_to_compose(
    c: AppContext,
    *,
    dump_path: Path,
    fmt: str,
    container_id: str,
    target_db: str,
    user: str,
) -> None:
    """Stream the dump through `docker exec -i <container> ...`."""
    if fmt == "custom":
        inner = [
            "pg_restore",
            "--no-owner",
            "--no-privileges",
            "--clean",
            "--if-exists",
            "-U",
            user,
            "-d",
            target_db,
        ]
        c.output.info(f"Running pg_restore via docker exec -> {container_id}:{target_db} ...")
    else:
        inner = ["psql", "-U", user, "-d", target_db, "-v", "ON_ERROR_STOP=1"]
        c.output.info(f"Running psql via docker exec -> {container_id}:{target_db} ...")

    cmd = ["docker", "exec", "-i", container_id, *inner]
    with open(dump_path, "rb") as f:
        proc = subprocess.run(cmd, stdin=f)  # noqa: S603
    if proc.returncode != 0:
        _die(c, f"Restore via docker exec failed with exit code {proc.returncode}")
    c.output.success("Restore completed.")


def _smoke_test_row_count(
    c: AppContext,
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    target_db: str,
) -> None:
    """Best-effort post-restore smoke test: row count on common tables."""
    env = os.environ.copy()
    env["PGPASSWORD"] = password
    for table in ("res_users", "public.res_users", "users"):
        cmd = [
            "psql",
            "-h",
            host,
            "-p",
            str(port),
            "-U",
            user,
            "-d",
            target_db,
            "-tAc",
            f"SELECT count(*) FROM {table}",
        ]
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True)  # noqa: S603
        if proc.returncode == 0:
            count = proc.stdout.strip()
            c.output.info(f"Smoke test: {table} has {count} rows")
            return
    # None succeeded — silent, not an error.


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


def pull(
    ctx: typer.Context,
    backup_id: Annotated[str, typer.Argument(help="Backup config ID on the SOURCE Dokploy")],
    target_db: Annotated[str, typer.Option("--target-db", help="Target database name to restore into")],
    target_compose: Annotated[
        str | None,
        typer.Option(
            "--target-compose",
            help="Target compose ID (Dokploy-managed, same profile as --profile). "
            "Mutually exclusive with --target-host.",
        ),
    ] = None,
    target_host: Annotated[
        str | None,
        typer.Option("--target-host", help="Raw postgres host (for local dev targets)"),
    ] = None,
    target_port: Annotated[int, typer.Option("--target-port", help="Raw postgres port")] = 5432,
    target_user: Annotated[
        str, typer.Option("--target-user", help="Postgres admin user for the raw target host")
    ] = "postgres",
    target_password: Annotated[
        str | None,
        typer.Option(
            "--target-password",
            help="Postgres password; defaults to PGPASSWORD env var if unset.",
        ),
    ] = None,
    target_service: Annotated[
        str,
        typer.Option("--target-service", help="Compose service name for the target postgres container"),
    ] = "postgres",
    trigger: Annotated[
        bool,
        typer.Option("--trigger", help="Trigger a fresh manual backup before pulling; otherwise use latest existing."),
    ] = False,
    wait_timeout: Annotated[
        int,
        typer.Option("--wait-timeout", help="Seconds to wait for a --trigger-ed backup to appear."),
    ] = 300,
    poll_interval: Annotated[int, typer.Option("--poll-interval", help="Seconds between S3 polls while waiting.")] = 10,
    keep_download: Annotated[
        bool, typer.Option("--keep-download", help="Keep the downloaded dump file after restore.")
    ] = False,
    download_path: Annotated[
        str, typer.Option("--download-path", help="Directory to store the downloaded dump.")
    ] = "/tmp",
    owner: Annotated[
        str | None,
        typer.Option("--owner", help="OWNER for the recreated DB (defaults to --target-user)."),
    ] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip drop-and-recreate confirmation.")] = False,
    smoke_test: Annotated[
        bool, typer.Option("--smoke-test/--no-smoke-test", help="Post-restore row-count sanity check.")
    ] = True,
) -> None:
    """End-to-end: trigger (optional) -> wait -> download -> restore.

    This is the one-command flow for pulling a production postgres dump down
    to a local/raw database. For restoring INTO a Dokploy-managed compose on
    the same host, prefer ``backups restore`` which uses Dokploy's native SSE
    log stream.

    Exit codes: 0 success, 1 any step failed.
    """
    c: AppContext = ctx.obj

    if target_compose and target_host:
        _die(c, "Use EITHER --target-compose OR --target-host, not both.")
    if not target_compose and not target_host:
        _die(c, "Provide --target-host (raw postgres) or --target-compose (Dokploy-managed).")

    backup = _fetch_backup(c, backup_id)
    destination_id = backup.get("destinationId")
    source_db = backup.get("database", "-")
    if not isinstance(destination_id, str) or not destination_id:
        _die(c, f"Backup '{backup_id}' has no destinationId")
    # mypy: destinationId is str now
    dest = _fetch_destination(c, str(destination_id))
    bucket = dest.get("bucket") or ""
    if not bucket:
        _die(c, f"Destination '{destination_id}' has no bucket")
    s3 = _build_s3_client(dest)

    # Build candidate prefixes (new hierarchical first, old flat fallback).
    prefixes = _get_search_prefixes(c, backup)
    # Filter to only keys containing the DB name (defense-in-depth against a
    # bucket that holds multiple DBs under the same compose appName).
    db_contains = source_db if isinstance(source_db, str) and source_db and source_db != "-" else ""

    c.output.info(f"Source backup: {backup_id} (db={source_db})")
    c.output.info(f"Search prefixes: {prefixes}")
    c.output.info(f"S3 destination: {destination_id} (bucket={bucket})")

    # --- Decide which key to fetch ---------------------------------------
    if trigger:
        trigger_time = datetime.now(UTC)
        _run_backup_now(c, backup, backup_id)
        key = _wait_for_new_object(
            c,
            s3,
            bucket,
            prefixes,
            trigger_time,
            wait_timeout,
            poll_interval,
            contains=db_contains,
        )
    else:
        key = _find_latest_s3_key(s3, bucket, prefixes, contains=db_contains)
        if not key:
            _die(
                c,
                f"No S3 objects found under prefixes {prefixes}. Run with --trigger to create one.",
            )
        c.output.info(f"Using latest existing S3 key: {key}")

    # --- Download --------------------------------------------------------
    basename = Path(key).name
    dl_dir = Path(download_path)
    dl_dir.mkdir(parents=True, exist_ok=True)
    local_gz = dl_dir / basename
    _download_key(c, s3, bucket, key, local_gz)
    local_file = _maybe_decompress(c, local_gz)
    fmt = _detect_format(local_file)
    c.output.info(f"Detected format: {fmt}")

    # --- Restore ---------------------------------------------------------
    effective_password = target_password or os.environ.get("PGPASSWORD", "")
    if target_host and not effective_password:
        _die(c, "--target-password not provided and PGPASSWORD is unset.")

    effective_owner = owner or target_user

    if target_host:
        _terminate_and_recreate_db(
            c,
            host=target_host,
            port=target_port,
            admin_user=target_user,
            admin_password=effective_password,
            target_db=target_db,
            owner=effective_owner,
            force=force,
        )
        _restore_to_raw_host(
            c,
            dump_path=local_file,
            fmt=fmt,
            host=target_host,
            port=target_port,
            user=target_user,
            password=effective_password,
            target_db=target_db,
        )
        if smoke_test:
            _smoke_test_row_count(
                c,
                host=target_host,
                port=target_port,
                user=target_user,
                password=effective_password,
                target_db=target_db,
            )
    else:
        # target_compose path: we do drop-recreate INSIDE the container.
        cid = _resolve_compose_postgres_container(c, str(target_compose), target_service)
        if not force:
            typer.confirm(
                f"Drop and recreate database '{target_db}' inside compose container {cid[:12]}? All data will be lost.",
                abort=True,
            )
        # Kill connections + DROP/CREATE inside the container via docker exec.
        psql_exec = [
            "docker",
            "exec",
            "-i",
            cid,
            "psql",
            "-U",
            target_user,
            "-d",
            "postgres",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
        ]
        for sql in (
            (
                f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = '{target_db}' AND pid <> pg_backend_pid()"
            ),
            f'DROP DATABASE IF EXISTS "{target_db}"',
            f'CREATE DATABASE "{target_db}" OWNER "{effective_owner}"',
        ):
            proc = subprocess.run([*psql_exec, sql])  # noqa: S603
            if proc.returncode != 0:
                _die(c, f"psql in container failed: {sql}")
        _restore_to_compose(
            c,
            dump_path=local_file,
            fmt=fmt,
            container_id=cid,
            target_db=target_db,
            user=target_user,
        )

    # --- Cleanup ---------------------------------------------------------
    if not keep_download:
        try:
            if local_file.exists():
                local_file.unlink()
            if local_gz.exists() and local_gz != local_file:
                local_gz.unlink()
            c.output.info("Cleaned up downloaded files.")
        except OSError as exc:
            c.output.warn(f"Could not clean up downloads: {exc}")
    else:
        c.output.info(f"Kept download at {local_file}")

    c.output.success(f"Pull complete: {backup_id} -> {target_db}")


def download(
    ctx: typer.Context,
    s3_key: Annotated[str, typer.Argument(help="S3 object key to download")],
    destination_id: Annotated[str, typer.Option("--destination", "-d", help="S3 destination ID")],
    output: Annotated[
        str | None,
        typer.Option("--output", "-o", help="Output file path (default: ./<basename>)"),
    ] = None,
) -> None:
    """Download an S3 object using a Dokploy destination's credentials."""
    c: AppContext = ctx.obj
    dest = _fetch_destination(c, destination_id)
    bucket = dest.get("bucket") or ""
    if not bucket:
        _die(c, f"Destination '{destination_id}' has no bucket")
    s3 = _build_s3_client(dest)
    out_path = Path(output) if output else Path.cwd() / Path(s3_key).name
    _download_key(c, s3, bucket, s3_key, out_path)
    if c.json_mode:
        c.output.raw_json(
            {
                "s3_key": s3_key,
                "bucket": bucket,
                "local_path": str(out_path),
                "size_bytes": out_path.stat().st_size,
            }
        )


def run_wait(
    ctx: typer.Context,
    backup_id: Annotated[str, typer.Argument(help="Backup config ID")],
    timeout: Annotated[int, typer.Option("--timeout", help="Seconds to wait for new backup")] = 300,
    poll_interval: Annotated[int, typer.Option("--poll-interval", help="Seconds between S3 polls")] = 10,
) -> None:
    """Trigger a manual backup and poll S3 until the new file appears.

    Prints the resulting S3 key on success. Exits 1 on timeout or trigger error.
    """
    c: AppContext = ctx.obj
    backup = _fetch_backup(c, backup_id)
    destination_id = backup.get("destinationId")
    source_db = backup.get("database", "-")
    if not isinstance(destination_id, str) or not destination_id:
        _die(c, f"Backup '{backup_id}' has no destinationId")
    dest = _fetch_destination(c, str(destination_id))
    bucket = dest.get("bucket") or ""
    if not bucket:
        _die(c, f"Destination '{destination_id}' has no bucket")
    s3 = _build_s3_client(dest)

    prefixes = _get_search_prefixes(c, backup)
    db_contains = source_db if isinstance(source_db, str) and source_db and source_db != "-" else ""

    trigger_time = datetime.now(UTC)
    _run_backup_now(c, backup, backup_id)
    key = _wait_for_new_object(
        c,
        s3,
        bucket,
        prefixes,
        trigger_time,
        timeout,
        poll_interval,
        contains=db_contains,
    )
    c.output.success(f"New backup available: s3://{bucket}/{key}")
    if c.json_mode:
        c.output.raw_json({"backupId": backup_id, "bucket": bucket, "key": key})
