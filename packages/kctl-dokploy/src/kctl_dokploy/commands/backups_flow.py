"""Backup/restore workflow commands: dump-compose, download, run-wait, restore-local, refresh.

Complements backups.py with operations Dokploy's HTTP API cannot do directly:
- Dumping a compose's postgres database to S3 via SSH+docker exec (bypasses Dokploy's
  unreliable /backup.manualBackupCompose endpoint).
- Downloading backup files from S3 to local disk.
- Waiting for a manual backup to appear in S3.
- Restoring a dump into a Dokploy-managed compose's postgres container.
- Orchestrating a full prod-to-local refresh.
"""

from __future__ import annotations

import datetime
import gzip
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Annotated, Any

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
# Shared helpers
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


def _list_backup_keys(c: AppContext, destination_id: str, search: str = "") -> list[str]:
    """List backup file keys in S3 via Dokploy API."""
    params: dict[str, Any] = {"destinationId": destination_id, "search": search}
    data = c.client.get("/backup.listBackupFiles", params=params)
    if not isinstance(data, list):
        return []
    keys: list[str] = []
    for f in data:
        if isinstance(f, str):
            keys.append(f)
        elif isinstance(f, dict):
            name = f.get("name") or f.get("key")
            if isinstance(name, str):
                keys.append(name)
    return keys


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


def _resolve_server_ssh(c: AppContext, compose_id: str) -> str | None:
    """Return ssh host string (user@ip) for the compose's serverId, or None if local."""
    data = _get_compose_one(c, compose_id)
    server_id = data.get("serverId")
    if not server_id:
        return None
    server = c.client.get("/server.one", params={"serverId": server_id})
    if not isinstance(server, dict):
        return None
    ip = server.get("ipAddress")
    if not ip:
        return None
    user = server.get("username") or "root"
    return f"{user}@{ip}"


_DOCKER_PS_FORMAT = '{{.Names}}\t{{.Label "com.docker.compose.service"}}'


def _find_container(ssh_host: str | None, app_name: str, service: str) -> str:
    """Find running container name for compose's service, locally or over SSH.

    `app_name` is the Dokploy-generated prefix; containers named `<app_name>*-<service>-*`
    will match. We filter by the `com.docker.compose.service` label to be precise.
    """
    if ssh_host:
        # For SSH, build a single shell-quoted command so the format template
        # (which contains embedded quotes) survives ssh argv joining.
        remote = r"""docker ps --format '{{.Names}}	{{.Label "com.docker.compose.service"}}'"""
        cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "BatchMode=yes",
            ssh_host,
            remote,
        ]
    else:
        cmd = ["docker", "ps", "--format", _DOCKER_PS_FORMAT]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        _die_plain(f"docker ps failed: {result.stderr.strip()}")
    for line in result.stdout.strip().splitlines():
        name, _, svc = line.partition("\t")
        if svc == service and app_name in name:
            return name
    _die_plain(f"No container found for compose '{app_name}' service '{service}'")
    return ""  # unreachable; _die_plain raises


def _docker_exec(container: str, cmd: list[str]) -> None:
    """Run a command inside a container and raise on failure (captures stderr)."""
    full = ["docker", "exec", container, *cmd]
    result = subprocess.run(full, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        _die_plain(f"docker command failed: {result.stderr.strip()}")


def _looks_like_custom_dump(path: Path) -> bool:
    """pg_dump custom-format files start with the magic 'PGDMP'."""
    try:
        with path.open("rb") as f:
            return f.read(5) == b"PGDMP"
    except OSError:
        return False


def _build_source_client(profile_name: str) -> Any:
    """Construct a DokployClient for a named profile (used by refresh)."""
    from kctl_dokploy.core.client import DokployClient
    from kctl_dokploy.core.config import get_service_config

    svc = get_service_config(profile_name)
    if not svc.url or not svc.api_key:
        _die_plain(f"Profile '{profile_name}' has no Dokploy URL/api_key configured")
    return DokployClient(base_url=svc.url, api_key=svc.api_key)


def _stream_pg_dump_to_s3(
    cmd: list[str],
    s3: Any,
    bucket: str,
    s3_key: str,
    timeout: int = 3600,
) -> int:
    """Run pg_dump (via subprocess) and stream stdout straight to S3.

    Returns the bytes uploaded. Ensures the child is waited on (no zombies) even
    when upload_fileobj raises.
    """
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.stdout is None:  # pragma: no cover — defensive
        _die_plain("Failed to open pg_dump stdout pipe")
    try:
        s3.upload_fileobj(proc.stdout, bucket, s3_key)
        rc = proc.wait(timeout=timeout)
        stderr = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
        if rc != 0:
            _die_plain(f"pg_dump failed (exit {rc}):\n{stderr[-2000:]}")
    finally:
        # Always wait to avoid zombies if we terminated above.
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
    head = s3.head_object(Bucket=bucket, Key=s3_key)
    return int(head.get("ContentLength", 0))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("dump-compose")
def dump_compose(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Option("--compose", "-c", help="Compose ID to dump from")],
    destination_id: Annotated[str, typer.Option("--destination", "-d", help="S3 destination ID")],
    database: Annotated[str, typer.Option("--database", help="Database name inside the postgres container")],
    service: Annotated[str, typer.Option("--service", "-s", help="Postgres service name in compose")] = "postgres",
    fmt: Annotated[str, typer.Option("--format", "-F", help="pg_dump format: c=custom, p=plain, d=directory")] = "c",
    key_prefix: Annotated[str, typer.Option("--key-prefix", help="S3 key prefix (default: compose/db-timestamp)")] = "",
    ssh_host: Annotated[
        str | None,
        typer.Option("--ssh-host", help="SSH target user@ip (default: auto-resolve from compose's serverId)"),
    ] = None,
    no_ssh: Annotated[bool, typer.Option("--no-ssh", help="Run docker locally instead of via SSH")] = False,
) -> None:
    """Dump a database from a compose's postgres container and upload to S3.

    Bypasses Dokploy's /backup.manualBackupCompose (which is fragile) by running
    pg_dump directly via docker exec, piping straight to S3. Works for remote
    (via SSH to the compose's server) or local composes (--no-ssh).
    """
    c: AppContext = ctx.obj
    data = _get_compose_one(c, compose_id)
    app_name = data.get("appName") or data.get("name") or ""
    if not app_name:
        _die(c, f"Compose '{compose_id}' has no appName")

    _, password, _ = _get_compose_db_creds(c, compose_id)

    # Resolve SSH host (None = local docker)
    if no_ssh:
        host: str | None = None
    elif ssh_host:
        host = ssh_host
    else:
        host = _resolve_server_ssh(c, compose_id)

    container = _find_container(host, str(app_name), service)
    c.output.info(f"Source container: {container} ({'local' if not host else host})")

    # S3 key
    ext = {"c": "dump", "p": "sql", "d": "dir"}.get(fmt, "dump")
    if not key_prefix:
        ts = datetime.datetime.now(tz=datetime.UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
        key_prefix = f"{data.get('name', 'compose')}/{database}-{ts}"
    # NOTE: pg_dump custom format (-F c) is already internally compressed —
    # do NOT append .gz or tooling will try to gunzip a non-gzip file.
    s3_key = f"{key_prefix}.{ext}"

    pg_dump_cmd = [
        "docker",
        "exec",
        "-e",
        f"PGPASSWORD={password}",
        container,
        "pg_dump",
        "-U",
        "postgres",
        "-d",
        database,
        "-F",
        fmt,
    ]
    full_cmd = (
        ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", host, *pg_dump_cmd] if host else pg_dump_cmd
    )

    dest = _fetch_destination(c, destination_id)
    bucket = dest.get("bucket", "")
    if not bucket:
        _die(c, "Destination has no bucket configured")
    s3 = _build_s3_client(dest)

    c.output.info(f"Dumping {database} to s3://{bucket}/{s3_key}")
    size = _stream_pg_dump_to_s3(full_cmd, s3, bucket, s3_key)
    c.output.success(f"Uploaded {size:,} bytes to s3://{bucket}/{s3_key}")
    typer.echo(s3_key)


@app.command("download")
def download(
    ctx: typer.Context,
    backup_file: Annotated[str, typer.Argument(help="Backup file key (from 'backups list-files')")],
    destination_id: Annotated[str, typer.Option("--destination", "-d", help="S3 destination ID")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Local output path")],
) -> None:
    """Download a backup file from S3 to local disk.

    Reads S3 credentials from the Dokploy destination record — no extra setup.
    """
    c: AppContext = ctx.obj
    dest = _fetch_destination(c, destination_id)
    bucket = dest.get("bucket", "")
    if not bucket:
        _die(c, f"Destination '{destination_id}' has no bucket configured")
    s3 = _build_s3_client(dest)
    output.parent.mkdir(parents=True, exist_ok=True)
    c.output.info(f"Downloading s3://{bucket}/{backup_file} to {output}")
    s3.download_file(bucket, backup_file, str(output))
    size = output.stat().st_size
    c.output.success(f"Downloaded {size:,} bytes to {output}")


@app.command("run-wait")
def run_wait(
    ctx: typer.Context,
    backup_id: Annotated[str, typer.Argument(help="Backup config ID")],
    destination_id: Annotated[str, typer.Option("--destination", "-d", help="S3 destination ID to watch")],
    backup_type: Annotated[str, typer.Option("--type", "-t", help="Backup type")] = "compose",
    timeout: Annotated[int, typer.Option("--timeout", help="Max seconds to wait")] = 900,
    poll_interval: Annotated[int, typer.Option("--poll", help="Poll interval seconds")] = 10,
    search: Annotated[str, typer.Option("--search", help="Filter for list-files")] = "",
) -> str:
    """Trigger a Dokploy manual backup and wait for a new file in the destination.

    Useful when Dokploy's native backup works (managed DBs, scheduled jobs). For
    compose-embedded postgres prefer `dump-compose`, which is more reliable.
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
    endpoint = endpoint_map.get(backup_type)
    if not endpoint:
        _die(c, f"Unknown backup type '{backup_type}'. Use: {', '.join(endpoint_map)}")

    before = set(_list_backup_keys(c, destination_id, search))
    c.output.info(f"{len(before)} existing files. Triggering backup...")
    c.client.post(endpoint, json={"backupId": backup_id})

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(poll_interval)
        current = set(_list_backup_keys(c, destination_id, search))
        new = current - before
        if new:
            new_file = sorted(new)[-1]
            c.output.success(f"New backup: {new_file}")
            typer.echo(new_file)
            return new_file
        remaining = int(deadline - time.monotonic())
        c.output.info(f"...still waiting ({remaining}s left)")
    _die(c, f"Timeout after {timeout}s")
    return ""  # unreachable


@app.command("restore-local")
def restore_local(
    ctx: typer.Context,
    backup_file: Annotated[Path, typer.Argument(help="Local backup file (.sql / .sql.gz / .dump)")],
    compose_id: Annotated[str, typer.Option("--compose", "-c", help="Target compose ID")],
    service: Annotated[str, typer.Option("--service", "-s", help="Postgres service name")] = "postgres",
    db_name: Annotated[str | None, typer.Option("--db-name", help="Target database (default: from env)")] = None,
    drop_recreate: Annotated[
        bool, typer.Option("--drop-recreate/--no-drop-recreate", help="DROP + CREATE database before restore")
    ] = True,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Restore a local dump file into a compose's postgres container.

    Auto-resolves the container via `docker ps`. The target Dokploy must share
    the docker socket with this host. Uses pg_restore for custom-format dumps
    (magic 'PGDMP'), psql for plain SQL (with ON_ERROR_STOP=1).
    """
    c: AppContext = ctx.obj
    if not backup_file.exists():
        _die(c, f"Backup file not found: {backup_file}")

    app_name = _get_compose_app_name(c, compose_id)
    user, password, env_db = _get_compose_db_creds(c, compose_id)
    target_db = db_name or env_db

    container = _find_container(None, app_name, service)
    c.output.info(f"Target container: {container}  db={target_db}  user={user}")

    if not force:
        typer.confirm(
            f"Restore '{backup_file.name}' into {container}:{target_db}? Existing data will be replaced.",
            abort=True,
        )

    tmp_dir = Path(tempfile.mkdtemp(prefix="kctl-dokploy-restore-"))
    try:
        # Decompress if .gz; otherwise use the file directly.
        if backup_file.suffix == ".gz":
            plain = tmp_dir / backup_file.stem
            c.output.info(f"Decompressing to {plain}")
            with gzip.open(backup_file, "rb") as src, plain.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            dump_file = plain
        else:
            dump_file = backup_file

        is_custom = dump_file.suffix in (".dump", ".pg_dump") or _looks_like_custom_dump(dump_file)
        env_prefix = ["env", f"PGPASSWORD={password}"]

        if drop_recreate:
            c.output.info(f"Dropping + recreating database '{target_db}'")
            _docker_exec(
                container,
                [
                    *env_prefix,
                    "psql",
                    "-U",
                    user,
                    "-d",
                    "postgres",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-c",
                    f'DROP DATABASE IF EXISTS "{target_db}" WITH (FORCE)',
                ],
            )
            _docker_exec(
                container,
                [
                    *env_prefix,
                    "psql",
                    "-U",
                    user,
                    "-d",
                    "postgres",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-c",
                    f'CREATE DATABASE "{target_db}" OWNER "{user}"',
                ],
            )

        c.output.info(f"Restoring {dump_file.name} into {target_db}...")
        if is_custom:
            cmd = [
                "docker",
                "exec",
                "-i",
                container,
                *env_prefix,
                "pg_restore",
                "--no-owner",
                "--exit-on-error",
                "-d",
                target_db,
                "-U",
                user,
            ]
        else:
            cmd = [
                "docker",
                "exec",
                "-i",
                container,
                *env_prefix,
                "psql",
                "-U",
                user,
                "-d",
                target_db,
                "-v",
                "ON_ERROR_STOP=1",
            ]

        with dump_file.open("rb") as stdin:
            result = subprocess.run(cmd, stdin=stdin, capture_output=True, check=False)
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace")
            # pg_restore prints NOTICE/WARNING lines even on success when --exit-on-error
            # is off. With --exit-on-error set, a non-zero rc here is a real failure.
            _die(c, f"Restore failed (exit {result.returncode}):\n{stderr[-2000:]}")

        c.output.success(f"Restored '{backup_file.name}' into {container}:{target_db}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.command("refresh")
def refresh(
    ctx: typer.Context,
    source_profile: Annotated[str, typer.Option("--source-profile", help="Source kctl-dokploy profile")],
    source_compose: Annotated[str, typer.Option("--source-compose", help="Source compose ID (pg host)")],
    source_destination_id: Annotated[str, typer.Option("--source-destination", help="S3 destination on source")],
    target_compose: Annotated[str, typer.Option("--target-compose", help="Target compose ID (current profile)")],
    database: Annotated[str, typer.Option("--database", help="Database name to dump+restore")],
    source_service: Annotated[str, typer.Option("--source-service", help="Source postgres service")] = "postgres",
    target_service: Annotated[str, typer.Option("--target-service", help="Target postgres service")] = "postgres",
    target_db: Annotated[
        str | None, typer.Option("--target-db", help="Target database name (default: same as --database)")
    ] = None,
    keep_download: Annotated[
        Path | None, typer.Option("--keep-download", help="Keep downloaded file at this path")
    ] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """End-to-end: dump source compose's DB to S3, download, restore into target compose.

    Bypasses Dokploy's /backup.manualBackupCompose (which is fragile) by running
    pg_dump via SSH directly. The S3 bucket must be registered as a destination
    on both the source profile (for upload) and the current profile (for download).
    """
    c: AppContext = ctx.obj
    source_client = _build_source_client(source_profile)

    # --- 1) Resolve source compose + SSH target
    c.output.info(f"[{source_profile}] Dumping {database} from compose {source_compose}...")
    src_data = source_client.get("/compose.one", params={"composeId": source_compose})
    if not isinstance(src_data, dict):
        _die(c, f"Source compose '{source_compose}' not found")
    src_app_name = src_data.get("appName") or src_data.get("name") or ""
    src_env = src_data.get("env", "") if isinstance(src_data.get("env"), str) else ""
    src_password = _parse_env_str(src_env).get("POSTGRES_PASSWORD", "")
    if not src_password:
        _die(c, "Source compose has no POSTGRES_PASSWORD")

    server_id = src_data.get("serverId")
    ssh_host: str | None = None
    if server_id:
        srv = source_client.get("/server.one", params={"serverId": server_id})
        if isinstance(srv, dict) and srv.get("ipAddress"):
            ssh_host = f"{srv.get('username') or 'root'}@{srv['ipAddress']}"

    container = _find_container(ssh_host, str(src_app_name), source_service)
    c.output.info(f"  source container: {container} ({'local' if not ssh_host else ssh_host})")

    source_dest = source_client.get("/destination.one", params={"destinationId": source_destination_id})
    if not isinstance(source_dest, dict) or not source_dest.get("bucket"):
        _die(c, "Source destination missing or has no bucket")
    bucket = source_dest["bucket"]
    s3 = _build_s3_client(source_dest)

    ts = datetime.datetime.now(tz=datetime.UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    s3_key = f"{src_data.get('name', 'compose')}/{database}-{ts}.dump"

    pg_dump_cmd = [
        "docker",
        "exec",
        "-e",
        f"PGPASSWORD={src_password}",
        container,
        "pg_dump",
        "-U",
        "postgres",
        "-d",
        database,
        "-F",
        "c",
    ]
    full_cmd = (
        ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", ssh_host, *pg_dump_cmd]
        if ssh_host
        else pg_dump_cmd
    )

    c.output.info(f"  uploading to s3://{bucket}/{s3_key}")
    size = _stream_pg_dump_to_s3(full_cmd, s3, bucket, s3_key)
    c.output.success(f"  uploaded {size:,} bytes")

    # --- 2) Download to local
    if keep_download:
        local_path = keep_download
        local_path.parent.mkdir(parents=True, exist_ok=True)
        cleanup_dir: Path | None = None
    else:
        tmpdir = Path(tempfile.mkdtemp(prefix="kctl-dokploy-refresh-"))
        local_path = tmpdir / Path(s3_key).name
        cleanup_dir = tmpdir

    c.output.info(f"Downloading to {local_path}")
    s3.download_file(bucket, s3_key, str(local_path))
    c.output.success(f"Downloaded {local_path.stat().st_size:,} bytes")

    # --- 3) Restore to target
    try:
        restore_local(
            ctx=ctx,
            backup_file=local_path,
            compose_id=target_compose,
            service=target_service,
            db_name=target_db or database,
            drop_recreate=True,
            force=force,
        )
    finally:
        if cleanup_dir is not None:
            shutil.rmtree(cleanup_dir, ignore_errors=True)
