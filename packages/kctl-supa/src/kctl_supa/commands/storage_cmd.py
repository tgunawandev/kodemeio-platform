"""File storage commands for kctl-supa.

File storage operations.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich import print as rprint
from rich.table import Table

from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.client import SupabaseClient
from kctl_supa.core.docker import DockerOps
from kctl_supa.core.exceptions import DockerError, SupabaseError

app = typer.Typer(help="File storage operations.")


def _get_client(actx: AppContext) -> SupabaseClient:
    cfg = actx.config
    return SupabaseClient(base_url=cfg.url, service_role_key=cfg.service_role_key, anon_key=cfg.anon_key)


def _get_docker(actx: AppContext) -> DockerOps:
    return DockerOps(actx.config)


@app.command()
def buckets(ctx: typer.Context) -> None:
    """List storage buckets."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        client = _get_client(actx)
        result = client.storage_list_buckets()
        client.close()
    except SupabaseError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    if not isinstance(result, list) or not result:
        out.warn("No buckets found.")
        return

    table = Table(title="Storage Buckets", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Public")
    table.add_column("Created At")

    for bucket in result:
        bid = bucket.get("id", "")
        name = bucket.get("name", "")
        public = "[green]yes[/green]" if bucket.get("public") else "[dim]no[/dim]"
        created = bucket.get("created_at", "")[:19] if bucket.get("created_at") else ""
        table.add_row(bid, name, public, created)

    rprint(table)


@app.command("create-bucket")
def create_bucket(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Bucket name")],
    public: Annotated[bool, typer.Option("--public", help="Make bucket publicly accessible")] = False,
) -> None:
    """Create a storage bucket."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        client = _get_client(actx)
        client.storage_create_bucket(name=name, public=public)
        client.close()
    except SupabaseError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    out.success(f"Bucket '{name}' created")
    out.kv("Public", "yes" if public else "no")


@app.command("delete-bucket")
def delete_bucket(
    ctx: typer.Context,
    bucket_id: Annotated[str, typer.Argument(help="Bucket ID to delete")],
) -> None:
    """Delete a storage bucket."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not typer.confirm(f"Delete bucket '{bucket_id}'? All objects will be lost."):
        raise typer.Exit(0)

    try:
        client = _get_client(actx)
        client.storage_delete_bucket(bucket_id)
        client.close()
    except SupabaseError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    out.success(f"Bucket '{bucket_id}' deleted")


@app.command()
def objects(
    ctx: typer.Context,
    bucket_id: Annotated[str, typer.Argument(help="Bucket ID to list objects from")],
) -> None:
    """List objects in a bucket."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        client = _get_client(actx)
        result = client.storage_list_objects(bucket_id)
        client.close()
    except SupabaseError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    if not isinstance(result, list) or not result:
        out.warn(f"No objects found in bucket '{bucket_id}'.")
        return

    table = Table(title=f"Objects in '{bucket_id}'", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="cyan")
    table.add_column("Size")
    table.add_column("Updated At")

    for obj in result:
        name = obj.get("name", "")
        meta = obj.get("metadata") or {}
        size = str(meta.get("size", "")) if meta else ""
        updated = obj.get("updated_at", "")[:19] if obj.get("updated_at") else ""
        table.add_row(name, size, updated)

    rprint(table)


@app.command()
def usage(ctx: typer.Context) -> None:
    """Show storage usage."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        docker = _get_docker(actx)
        result = docker.psql("SELECT pg_size_pretty(pg_total_relation_size('storage.objects'))")
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    typer.echo(result)
