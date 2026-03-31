"""S3-compatible object storage commands for Hetzner.

Uses boto3 if available, otherwise falls back to subprocess with aws CLI.
Hetzner S3 endpoint: https://<region>.your-objectstorage.com
"""

from __future__ import annotations

import os
import subprocess
from typing import Annotated

import typer

from kctl_hz.core.callbacks import AppContext

app = typer.Typer(help="Manage Hetzner S3-compatible object storage.")


# ---------------------------------------------------------------------------
# S3 credential resolution (profile config → env var → abort)
# ---------------------------------------------------------------------------


def _get_profile() -> str | None:
    """Get profile from current Typer context."""
    try:
        ctx = typer.Context
        import click

        ctx = click.get_current_context(silent=True)
        if ctx and ctx.obj is not None:
            return ctx.obj.profile
    except Exception:
        pass
    return None


def _require_creds() -> tuple[str, str, str, str]:
    """Resolve S3 credentials from profile config (with env var overrides) or abort."""
    from kctl_hz.core.config import resolve_s3_connection

    access_key, secret_key, endpoint, region = resolve_s3_connection(_get_profile())
    if not access_key or not secret_key:
        typer.echo(
            "S3 credentials not configured. Add s3_access_key/s3_secret_key to your "
            "hetzner profile, or set S3_SRC_ACCESS_KEY/S3_SRC_SECRET_KEY env vars.",
            err=True,
        )
        raise typer.Exit(1)
    return access_key, secret_key, endpoint, region


# ---------------------------------------------------------------------------
# boto3 / aws CLI abstraction
# ---------------------------------------------------------------------------

_BOTO3_AVAILABLE: bool | None = None


def _has_boto3() -> bool:
    global _BOTO3_AVAILABLE
    if _BOTO3_AVAILABLE is None:
        try:
            import boto3  # noqa: F401

            _BOTO3_AVAILABLE = True
        except ImportError:
            _BOTO3_AVAILABLE = False
    return _BOTO3_AVAILABLE


def _get_s3_client():  # type: ignore[no-untyped-def]
    """Return a boto3 S3 client configured for Hetzner."""
    import boto3

    access_key, secret_key, endpoint, region = _require_creds()
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )


def _aws_cmd(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run aws CLI with Hetzner credentials."""
    access_key, secret_key, endpoint, region = _require_creds()
    env = {
        **os.environ,
        "AWS_ACCESS_KEY_ID": access_key,
        "AWS_SECRET_ACCESS_KEY": secret_key,
    }
    cmd = ["aws", "--endpoint-url", endpoint, "--region", region, *args]
    return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=300)


# ---------------------------------------------------------------------------
# Helper: format bytes
# ---------------------------------------------------------------------------


def _human_size(nbytes: int) -> str:
    """Format bytes to human-readable."""
    if nbytes >= 1073741824:
        return f"{nbytes / 1073741824:.2f} GB"
    elif nbytes >= 1048576:
        return f"{nbytes / 1048576:.2f} MB"
    elif nbytes >= 1024:
        return f"{nbytes / 1024:.2f} KB"
    return f"{nbytes} B"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def buckets(ctx: typer.Context) -> None:
    """List all S3 buckets."""
    c: AppContext = ctx.obj

    if _has_boto3():
        client = _get_s3_client()
        response = client.list_buckets()
        bucket_list = response.get("Buckets", [])

        if c.output.json_mode:
            c.output.raw_json([{"name": b["Name"], "created": str(b.get("CreationDate", ""))} for b in bucket_list])
            return

        rows = []
        for b in bucket_list:
            rows.append([b["Name"], str(b.get("CreationDate", "-"))])
        c.output.table(
            "S3 Buckets",
            [("Name", "cyan"), ("Created", "dim")],
            rows,
        )
    else:
        result = _aws_cmd(["s3", "ls"])
        if result.returncode != 0:
            c.output.error(f"aws s3 ls failed: {result.stderr.strip()}")
            raise typer.Exit(1)

        if c.output.json_mode:
            names = [line.split()[-1] for line in result.stdout.strip().splitlines() if line.strip()]
            c.output.raw_json(names)
            return

        rows = []
        for line in result.stdout.strip().splitlines():
            parts = line.split()
            if len(parts) >= 3:
                rows.append([parts[2], f"{parts[0]} {parts[1]}"])
            elif parts:
                rows.append([parts[-1], "-"])
        c.output.table(
            "S3 Buckets",
            [("Name", "cyan"), ("Created", "dim")],
            rows,
        )


@app.command()
def ls(
    ctx: typer.Context,
    bucket: Annotated[str, typer.Argument(help="Bucket name")],
    prefix: Annotated[str, typer.Option("--prefix", help="Object key prefix filter")] = "",
) -> None:
    """List objects in an S3 bucket."""
    c: AppContext = ctx.obj

    if _has_boto3():
        client = _get_s3_client()
        kwargs: dict = {"Bucket": bucket}
        if prefix:
            kwargs["Prefix"] = prefix

        all_objects: list[dict] = []
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(**kwargs):
            for obj in page.get("Contents", []):
                all_objects.append(obj)

        if c.output.json_mode:
            c.output.raw_json(
                [
                    {"key": o["Key"], "size": o["Size"], "last_modified": str(o.get("LastModified", ""))}
                    for o in all_objects
                ]
            )
            return

        rows = []
        for o in all_objects:
            rows.append([o["Key"], _human_size(o["Size"]), str(o.get("LastModified", "-"))])
        c.output.table(
            f"Objects in s3://{bucket}/{prefix}",
            [("Key", "cyan"), ("Size", ""), ("Modified", "dim")],
            rows,
        )
    else:
        s3_path = f"s3://{bucket}/{prefix}" if prefix else f"s3://{bucket}/"
        result = _aws_cmd(["s3", "ls", s3_path, "--recursive"])
        if result.returncode != 0:
            c.output.error(f"aws s3 ls failed: {result.stderr.strip()}")
            raise typer.Exit(1)

        if c.output.json_mode:
            objects = []
            for line in result.stdout.strip().splitlines():
                parts = line.split(None, 3)
                if len(parts) >= 4:
                    objects.append({"key": parts[3], "size": parts[2], "last_modified": f"{parts[0]} {parts[1]}"})
            c.output.raw_json(objects)
            return

        rows = []
        for line in result.stdout.strip().splitlines():
            parts = line.split(None, 3)
            if len(parts) >= 4:
                rows.append([parts[3], parts[2], f"{parts[0]} {parts[1]}"])
        c.output.table(
            f"Objects in s3://{bucket}/{prefix}",
            [("Key", "cyan"), ("Size", ""), ("Modified", "dim")],
            rows,
        )


@app.command()
def size(
    ctx: typer.Context,
    bucket: Annotated[str, typer.Argument(help="Bucket name")],
) -> None:
    """Calculate total size of an S3 bucket."""
    c: AppContext = ctx.obj

    if _has_boto3():
        client = _get_s3_client()
        total_size = 0
        total_objects = 0
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket):
            for obj in page.get("Contents", []):
                total_size += obj["Size"]
                total_objects += 1

        if c.output.json_mode:
            c.output.raw_json({"bucket": bucket, "total_bytes": total_size, "total_objects": total_objects})
            return

        sections = [
            (
                "Bucket Size",
                [
                    ("Bucket", bucket),
                    ("Total Size", _human_size(total_size)),
                    ("Total Bytes", f"{total_size:,}"),
                    ("Objects", str(total_objects)),
                ],
            )
        ]
        c.output.detail(f"Bucket: {bucket}", sections)
    else:
        result = _aws_cmd(["s3", "ls", f"s3://{bucket}/", "--recursive", "--summarize"])
        if result.returncode != 0:
            c.output.error(f"aws s3 ls failed: {result.stderr.strip()}")
            raise typer.Exit(1)

        if c.output.json_mode:
            # Parse summary lines
            total_objects = "0"
            total_size = "0"
            for line in result.stdout.strip().splitlines():
                if "Total Objects:" in line:
                    total_objects = line.split(":")[-1].strip()
                elif "Total Size:" in line:
                    total_size = line.split(":")[-1].strip()
            c.output.raw_json({"bucket": bucket, "total_size": total_size, "total_objects": total_objects})
            return

        c.output.info(f"Bucket size for s3://{bucket}:")
        for line in result.stdout.strip().splitlines():
            if "Total" in line:
                c.output.text(f"  {line.strip()}")


@app.command()
def cp(
    ctx: typer.Context,
    src: Annotated[str, typer.Argument(help="Source path (local or s3://bucket/key)")],
    dst: Annotated[str, typer.Argument(help="Destination path (local or s3://bucket/key)")],
    recursive: Annotated[bool, typer.Option("--recursive", "-r", help="Copy recursively")] = False,
) -> None:
    """Copy files to/from S3."""
    c: AppContext = ctx.obj
    _require_creds()

    args = ["s3", "cp", src, dst]
    if recursive:
        args.append("--recursive")

    result = _aws_cmd(args)
    if result.returncode != 0:
        c.output.error(f"aws s3 cp failed: {result.stderr.strip()}")
        raise typer.Exit(1)

    if c.output.json_mode:
        c.output.raw_json({"status": "ok", "src": src, "dst": dst})
        return

    c.output.success(f"Copied {src} -> {dst}")
    if result.stdout.strip():
        c.output.text(result.stdout.strip())


@app.command()
def sync(
    ctx: typer.Context,
    src: Annotated[str, typer.Argument(help="Source path (local or s3://bucket/prefix)")],
    dst: Annotated[str, typer.Argument(help="Destination path (local or s3://bucket/prefix)")],
    delete: Annotated[bool, typer.Option("--delete", help="Delete files in dst not in src")] = False,
) -> None:
    """Sync directories to/from S3 (incremental)."""
    c: AppContext = ctx.obj
    _require_creds()

    args = ["s3", "sync", src, dst]
    if delete:
        args.append("--delete")

    result = _aws_cmd(args)
    if result.returncode != 0:
        c.output.error(f"aws s3 sync failed: {result.stderr.strip()}")
        raise typer.Exit(1)

    if c.output.json_mode:
        c.output.raw_json({"status": "ok", "src": src, "dst": dst, "delete": delete})
        return

    c.output.success(f"Synced {src} -> {dst}")
    if result.stdout.strip():
        c.output.text(result.stdout.strip())


@app.command()
def mb(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Bucket name to create")],
) -> None:
    """Create a new S3 bucket."""
    c: AppContext = ctx.obj

    if _has_boto3():
        client = _get_s3_client()
        client.create_bucket(Bucket=name)
        c.output.success(f"Bucket '{name}' created")
        if c.output.json_mode:
            c.output.raw_json({"status": "created", "bucket": name})
    else:
        result = _aws_cmd(["s3", "mb", f"s3://{name}"])
        if result.returncode != 0:
            c.output.error(f"aws s3 mb failed: {result.stderr.strip()}")
            raise typer.Exit(1)
        c.output.success(f"Bucket '{name}' created")
        if c.output.json_mode:
            c.output.raw_json({"status": "created", "bucket": name})


@app.command()
def rb(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Bucket name to remove")],
    force: Annotated[bool, typer.Option("--force", help="Delete all objects first, then remove bucket")] = False,
) -> None:
    """Remove an S3 bucket."""
    c: AppContext = ctx.obj

    if not force:
        typer.confirm(f"Delete S3 bucket '{name}'?", abort=True)

    if _has_boto3():
        client = _get_s3_client()

        if force:
            # Delete all objects first
            paginator = client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=name):
                objects = page.get("Contents", [])
                if objects:
                    delete_keys = [{"Key": obj["Key"]} for obj in objects]
                    client.delete_objects(Bucket=name, Delete={"Objects": delete_keys})

        client.delete_bucket(Bucket=name)
        c.output.success(f"Bucket '{name}' removed")
        if c.output.json_mode:
            c.output.raw_json({"status": "deleted", "bucket": name})
    else:
        args = ["s3", "rb", f"s3://{name}"]
        if force:
            args.append("--force")
        result = _aws_cmd(args)
        if result.returncode != 0:
            c.output.error(f"aws s3 rb failed: {result.stderr.strip()}")
            raise typer.Exit(1)
        c.output.success(f"Bucket '{name}' removed")
        if c.output.json_mode:
            c.output.raw_json({"status": "deleted", "bucket": name})
