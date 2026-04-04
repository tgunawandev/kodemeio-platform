"""Rspamd settings management (spam filter tuning)."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage rspamd filter settings.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all rspamd settings."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("rsetting/all")
    items = data if isinstance(data, list) else []
    if not items:
        c.output.info("No rspamd settings configured.")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for item in items:
        active = "[green]yes[/green]" if str(item.get("active")) == "1" else "[red]no[/red]"
        rows.append([str(item.get("id", "")), item.get("desc", ""), item.get("content", "")[:60], active])

    c.output.table(
        "Rspamd Settings",
        [("ID", "dim"), ("Description", "cyan"), ("Content", "dim"), ("Active", "")],
        rows,
        data_for_json=items,
    )


@app.command()
def create(
    ctx: typer.Context,
    desc: Annotated[str, typer.Option("--desc", help="Setting description")],
    content: Annotated[str, typer.Option("--content", help="Rspamd setting content or @filepath")],
    active: Annotated[bool, typer.Option("--active/--inactive")] = True,
) -> None:
    """Create an rspamd setting."""
    c: AppContext = ctx.obj
    if content.startswith("@"):
        from pathlib import Path

        path = Path(content[1:])
        if not path.exists():
            c.output.error(f"File not found: {path}")
            raise typer.Exit(1)
        content = path.read_text()

    payload = {"desc": desc, "content": content, "active": "1" if active else "0"}
    result = c.client.mc_add("rsetting", payload)
    handle_result(c, result, f"Rspamd setting '{desc}' created")


@app.command()
def update(
    ctx: typer.Context,
    setting_id: Annotated[str, typer.Argument(help="Setting ID")],
    desc: Annotated[str | None, typer.Option("--desc")] = None,
    content: Annotated[str | None, typer.Option("--content")] = None,
    active: Annotated[bool | None, typer.Option("--active/--inactive")] = None,
) -> None:
    """Update an rspamd setting."""
    c: AppContext = ctx.obj
    attr: dict = {}
    if desc is not None:
        attr["desc"] = desc
    if content is not None:
        if content.startswith("@"):
            from pathlib import Path

            path = Path(content[1:])
            if not path.exists():
                c.output.error(f"File not found: {path}")
                raise typer.Exit(1)
            content = path.read_text()
        attr["content"] = content
    if active is not None:
        attr["active"] = "1" if active else "0"
    if not attr:
        c.output.warn("No fields to update")
        raise typer.Exit(0)
    result = c.client.mc_edit("rsetting", {"items": [setting_id], "attr": attr})
    handle_result(c, result, f"Rspamd setting {setting_id} updated")


@app.command()
def delete(
    ctx: typer.Context,
    setting_id: Annotated[str, typer.Argument(help="Setting ID")],
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Delete an rspamd setting."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete rspamd setting {setting_id}?"):
            raise typer.Exit(0)
    result = c.client.mc_delete("rsetting", [setting_id])
    handle_result(c, result, f"Rspamd setting {setting_id} deleted")
