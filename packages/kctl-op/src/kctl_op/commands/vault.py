"""Vault management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_op.core.callbacks import AppContext

app = typer.Typer(help="Vault management operations.")


@app.command()
def info(ctx: typer.Context) -> None:
    """Show vault details."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    try:
        data = client.vault_info()
    except Exception as e:
        out.error(f"Cannot access vault: {e}")
        raise typer.Exit(code=1) from None

    if out.json_mode:
        out.raw_json(data)
        return

    sections = [
        (
            "Vault Details",
            [
                ("ID", data.get("id", "unknown")),
                ("Name", data.get("name", "unknown")),
                ("Type", data.get("type", "unknown")),
                ("Items", str(data.get("items", 0))),
                ("Created", data.get("created_at", "unknown")),
                ("Updated", data.get("updated_at", "unknown")),
            ],
        ),
    ]
    out.detail("Vault Information", sections, data_for_json=data)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str | None, typer.Argument(help="Vault name.")] = None,
    description: Annotated[str, typer.Option("--description", "-d", help="Vault description.")] = "",
) -> None:
    """Create a new 1Password vault."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    vault_name = name or actx.service_config.vault
    if not vault_name:
        out.error("Specify a vault name or configure one via: kctl-op config init")
        raise typer.Exit(code=1)

    out.info(f"Creating vault '{vault_name}'...")
    try:
        result = client.create_vault(vault_name, description)
        out.success(f"Vault '{vault_name}' created.")
        if out.json_mode:
            out.raw_json(result)
    except Exception as e:
        out.error(f"Failed to create vault: {e}")
        raise typer.Exit(code=1) from None


@app.command()
def items(ctx: typer.Context) -> None:
    """List all items in the vault with metadata."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    try:
        item_list = client.list_items()
    except Exception as e:
        out.error(f"Cannot list items: {e}")
        raise typer.Exit(code=1) from None

    if not item_list:
        out.info("No items in vault.")
        return

    rows = []
    json_data = []
    for item in item_list:
        title = item.get("title", "untitled")
        category = item.get("category", "unknown")
        tags = ", ".join(item.get("tags", []))
        updated = item.get("updated_at", "unknown")
        vault_name = item.get("vault", {}).get("name", "")

        rows.append([title, category, tags, updated])
        json_data.append(
            {
                "title": title,
                "id": item.get("id", ""),
                "category": category,
                "tags": item.get("tags", []),
                "updated_at": updated,
                "vault": vault_name,
            }
        )

    out.table(
        title=f"Vault Items ({len(item_list)})",
        columns=[
            ("Title", "green"),
            ("Category", ""),
            ("Tags", "cyan"),
            ("Updated", "dim"),
        ],
        rows=rows,
        data_for_json=json_data,
    )
