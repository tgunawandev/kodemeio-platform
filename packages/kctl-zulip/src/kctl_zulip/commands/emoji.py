"""Custom emoji management commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from kctl_zulip.core.callbacks import AppContext

app = typer.Typer(help="Custom emoji management.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all custom emoji."""
    c: AppContext = ctx.obj
    data = c.client.get("realm/emoji")
    emoji_dict = data.get("emoji", {})

    rows = [
        [
            eid,
            e.get("name", ""),
            str(e.get("author_id", "")),
            "yes" if e.get("deactivated", False) else "no",
        ]
        for eid, e in emoji_dict.items()
    ]

    c.output.table(
        f"Custom Emoji ({len(rows)})",
        [("ID", "cyan"), ("Name", "green"), ("Author ID", ""), ("Deactivated", "dim")],
        rows,
        data_for_json=list(emoji_dict.values()),
    )


@app.command()
def upload(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Emoji name (no colons)")],
    file_path: Annotated[Path, typer.Argument(help="Path to image file")],
) -> None:
    """Upload a custom emoji."""
    c: AppContext = ctx.obj

    if not file_path.exists():
        c.output.error(f"File not found: {file_path}")
        raise typer.Exit(1)

    with open(file_path, "rb") as f:
        c.client.post_multipart(f"realm/emoji/{name}", files={"filename": (file_path.name, f)})

    c.output.success(f"Emoji :{name}: uploaded")


@app.command()
def delete(
    ctx: typer.Context,
    emoji_name: Annotated[str, typer.Argument(help="Emoji name")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete (deactivate) a custom emoji."""
    c: AppContext = ctx.obj

    # Find emoji ID by name
    data = c.client.get("realm/emoji")
    emoji_dict = data.get("emoji", {})
    emoji_id = None
    for eid, e in emoji_dict.items():
        if e.get("name") == emoji_name:
            emoji_id = eid
            break

    if emoji_id is None:
        c.output.error(f"Emoji :{emoji_name}: not found")
        raise typer.Exit(1)

    if not force:
        if not typer.confirm(f"Delete emoji :{emoji_name}:?"):
            raise typer.Abort()

    c.client.delete(f"realm/emoji/{emoji_id}")
    c.output.success(f"Emoji :{emoji_name}: deleted")
