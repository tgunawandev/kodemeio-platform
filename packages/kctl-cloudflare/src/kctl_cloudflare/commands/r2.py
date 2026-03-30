"""Cloudflare R2 storage management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_cloudflare.core.callbacks import AppContext
from kctl_cloudflare.core.utils import human_size, require_account

app = typer.Typer(help="Manage R2 object storage buckets.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all R2 buckets."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    buckets = c.client.get(f"/accounts/{acct}/r2/buckets")
    if not isinstance(buckets, list):
        buckets = buckets.get("buckets", []) if isinstance(buckets, dict) else []
    rows = []
    for b in buckets:
        rows.append(
            [
                b.get("name", ""),
                b.get("location", ""),
                b.get("creation_date", "")[:19],
            ]
        )
    c.output.table(
        "R2 Buckets",
        [("Name", "cyan"), ("Location", ""), ("Created", "dim")],
        rows,
        data_for_json=buckets,
    )


@app.command()
def get(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Bucket name")],
) -> None:
    """Get R2 bucket details."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    data = c.client.get(f"/accounts/{acct}/r2/buckets/{name}")
    if not isinstance(data, dict):
        data = {}
    sections = [
        (
            "Bucket",
            [
                ("Name", data.get("name", name)),
                ("Location", data.get("location", "")),
                ("Created", data.get("creation_date", "")),
            ],
        )
    ]
    c.output.detail(f"R2 Bucket: {name}", sections, data_for_json=data)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Bucket name")],
    location: Annotated[
        str, typer.Option("--location", help="Location hint (auto, wnam, enam, weur, eeur, apac)")
    ] = "auto",
) -> None:
    """Create an R2 bucket."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    payload: dict = {"name": name}
    if location != "auto":
        payload["locationHint"] = location
    result = c.client.post(f"/accounts/{acct}/r2/buckets", json=payload)
    bucket_name = result.get("name", name) if isinstance(result, dict) else name
    c.output.success(f"R2 bucket created: {bucket_name}")


@app.command("delete")
def delete_(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Bucket name to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
) -> None:
    """Delete an R2 bucket. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    acct = require_account(c)
    c.client.delete(f"/accounts/{acct}/r2/buckets/{name}")
    c.output.success(f"R2 bucket deleted: {name}")


@app.command("list-objects")
def list_objects(
    ctx: typer.Context,
    bucket_name: Annotated[str, typer.Argument(help="Bucket name")],
    prefix: Annotated[str | None, typer.Option("--prefix", help="Key prefix filter")] = None,
    limit: Annotated[int, typer.Option("--limit", help="Maximum number of objects to return")] = 100,
) -> None:
    """List objects in an R2 bucket."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    params: dict = {"limit": limit}
    if prefix:
        params["prefix"] = prefix
    data = c.client.get(f"/accounts/{acct}/r2/buckets/{bucket_name}/objects", params=params)
    items = data if isinstance(data, list) else (data.get("objects", []) if isinstance(data, dict) else [])
    rows = []
    for obj in items:
        rows.append(
            [
                obj.get("key", ""),
                human_size(obj.get("size", 0)),
                (obj.get("last_modified") or obj.get("LastModified") or "")[:19],
                obj.get("etag", obj.get("ETag", "")),
            ]
        )
    c.output.table(
        f"Objects — {bucket_name}",
        [("Key", "cyan"), ("Size", ""), ("Last Modified", "dim"), ("ETag", "dim")],
        rows,
        data_for_json=items,
    )


@app.command("delete-object")
def delete_object(
    ctx: typer.Context,
    bucket_name: Annotated[str, typer.Argument(help="Bucket name")],
    key: Annotated[str, typer.Argument(help="Object key to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
) -> None:
    """Delete an object from an R2 bucket. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    acct = require_account(c)
    c.client.delete(f"/accounts/{acct}/r2/buckets/{bucket_name}/objects/{key}")
    c.output.success(f"Object deleted: {key}")


@app.command()
def usage(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Bucket name")],
) -> None:
    """Show R2 bucket usage statistics."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    data = c.client.get(f"/accounts/{acct}/r2/buckets/{name}/usage")
    if not isinstance(data, dict):
        data = {}
    sections = [
        (
            "Usage",
            [
                ("Payload Size", human_size(data.get("payloadSize", 0))),
                ("Metadata Size", human_size(data.get("metadataSize", 0))),
                ("Object Count", str(data.get("objectCount", 0))),
                ("Upload Count", str(data.get("uploadCount", 0))),
            ],
        )
    ]
    c.output.detail(f"R2 Bucket Usage: {name}", sections, data_for_json=data)
