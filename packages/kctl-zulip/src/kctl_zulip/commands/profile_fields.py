"""Custom profile fields management commands."""

from __future__ import annotations

import json
from typing import Annotated, Optional

import typer

from kctl_zulip.core.callbacks import AppContext

app = typer.Typer(help="Custom profile fields.")


@app.command("list")
def list_(
    ctx: typer.Context,
) -> None:
    """List custom profile fields."""
    c: AppContext = ctx.obj
    data = c.client.get("realm/profile_fields")
    fields = data.get("custom_fields", [])

    rows = []
    for f in fields:
        fid = str(f.get("id", ""))
        name = f.get("name", "")
        ftype = str(f.get("type", ""))
        hint = f.get("hint", "") or ""
        order = str(f.get("order", ""))
        rows.append([fid, name, ftype, hint, order])

    c.output.table(
        f"Profile Fields ({len(fields)})",
        [("ID", "cyan"), ("Name", "green"), ("Type", ""), ("Hint", "dim"), ("Order", "dim")],
        rows,
        data_for_json=fields,
    )


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="Field name")],
    field_type: Annotated[
        int,
        typer.Option(
            "--type",
            help="Field type (1=short text, 2=long text, 3=list, 4=date, 5=link, 6=pronouns, 7=external account)",
        ),
    ],
    hint: Annotated[Optional[str], typer.Option("--hint", help="Field hint text")] = None,
    field_data: Annotated[
        Optional[str], typer.Option("--field-data", help="Field data as JSON (for list type)")
    ] = None,
) -> None:
    """Create a custom profile field."""
    c: AppContext = ctx.obj

    payload: dict = {
        "name": name,
        "field_type": str(field_type),
    }
    if hint:
        payload["hint"] = hint
    if field_data:
        payload["field_data"] = field_data

    result = c.client.post("realm/profile_fields", data=payload)
    field_id = result.get("id", "")
    c.output.success(f"Profile field created (ID: {field_id})")


@app.command()
def update(
    ctx: typer.Context,
    field_id: Annotated[int, typer.Argument(help="Field ID")],
    name: Annotated[Optional[str], typer.Option("--name", help="New name")] = None,
    hint: Annotated[Optional[str], typer.Option("--hint", help="New hint")] = None,
) -> None:
    """Update a custom profile field."""
    c: AppContext = ctx.obj

    payload: dict = {}
    if name is not None:
        payload["name"] = name
    if hint is not None:
        payload["hint"] = hint

    if not payload:
        c.output.warn("No fields to update")
        return

    c.client.patch(f"realm/profile_fields/{field_id}", data=payload)
    c.output.success(f"Profile field {field_id} updated")


@app.command()
def delete(
    ctx: typer.Context,
    field_id: Annotated[int, typer.Argument(help="Field ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a custom profile field."""
    c: AppContext = ctx.obj

    if not force:
        if not typer.confirm(f"Delete profile field {field_id}?"):
            raise typer.Abort()

    c.client.delete(f"realm/profile_fields/{field_id}")
    c.output.success(f"Profile field {field_id} deleted")


@app.command()
def reorder(
    ctx: typer.Context,
    order: Annotated[str, typer.Option("--order", help="Comma-separated field IDs in desired order")],
) -> None:
    """Reorder custom profile fields."""
    c: AppContext = ctx.obj

    field_ids = [int(fid.strip()) for fid in order.split(",")]
    c.client.patch("realm/profile_fields", data={"order": json.dumps(field_ids)})
    c.output.success(f"Profile fields reordered: {field_ids}")
