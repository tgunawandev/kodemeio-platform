"""Per-mailbox Sieve filter management."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage per-mailbox Sieve filters.")


@app.command("list")
def list_(
    ctx: typer.Context,
    mailbox: Annotated[str, typer.Argument(help="Mailbox email address")],
) -> None:
    """List Sieve filters for a mailbox."""
    c: AppContext = ctx.obj
    data = c.client.mc_get(f"filters/{mailbox}")
    items = data if isinstance(data, list) else []

    if not items:
        c.output.info(f"No filters for {mailbox}.")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for item in items:
        active = "[green]yes[/green]" if str(item.get("active")) == "1" else "[red]no[/red]"
        rows.append(
            [
                str(item.get("id", "")),
                item.get("script_desc", ""),
                active,
            ]
        )

    c.output.table(
        f"Filters: {mailbox}",
        [("ID", "dim"), ("Description", "cyan"), ("Active", "")],
        rows,
        data_for_json=items,
    )


@app.command()
def create(
    ctx: typer.Context,
    mailbox: Annotated[str, typer.Argument(help="Mailbox email address")],
    script_desc: Annotated[str, typer.Option("--desc", help="Filter description")],
    script_data: Annotated[str, typer.Option("--script", help="Sieve script content or @filepath")],
    active: Annotated[bool, typer.Option("--active/--inactive")] = True,
) -> None:
    """Create a Sieve filter for a mailbox."""
    c: AppContext = ctx.obj

    # Support @filepath for script content
    if script_data.startswith("@"):
        from pathlib import Path

        path = Path(script_data[1:])
        if not path.exists():
            c.output.error(f"File not found: {path}")
            raise typer.Exit(1)
        script_data = path.read_text()

    payload = {
        "username": mailbox,
        "script_desc": script_desc,
        "script_data": script_data,
        "active": "1" if active else "0",
    }
    result = c.client.mc_add("filter", payload)
    handle_result(c, result, f"Filter '{script_desc}' created for {mailbox}")


@app.command()
def update(
    ctx: typer.Context,
    filter_id: Annotated[str, typer.Argument(help="Filter ID")],
    script_desc: Annotated[str | None, typer.Option("--desc")] = None,
    script_data: Annotated[str | None, typer.Option("--script")] = None,
    active: Annotated[bool | None, typer.Option("--active/--inactive")] = None,
) -> None:
    """Update a Sieve filter."""
    c: AppContext = ctx.obj
    attr: dict = {}
    if script_desc is not None:
        attr["script_desc"] = script_desc
    if script_data is not None:
        if script_data.startswith("@"):
            from pathlib import Path

            path = Path(script_data[1:])
            if not path.exists():
                c.output.error(f"File not found: {path}")
                raise typer.Exit(1)
            script_data = path.read_text()
        attr["script_data"] = script_data
    if active is not None:
        attr["active"] = "1" if active else "0"

    if not attr:
        c.output.warn("No fields to update")
        raise typer.Exit(0)

    payload = {"items": [filter_id], "attr": attr}
    result = c.client.mc_edit("filter", payload)
    handle_result(c, result, f"Filter {filter_id} updated")


@app.command()
def delete(
    ctx: typer.Context,
    filter_id: Annotated[str, typer.Argument(help="Filter ID")],
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Delete a Sieve filter."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete filter {filter_id}?"):
            raise typer.Exit(0)
    result = c.client.mc_delete("filter", [filter_id])
    handle_result(c, result, f"Filter {filter_id} deleted")
