"""Folder management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_grafana.core.callbacks import AppContext

app = typer.Typer(help="Folder organization.")


@app.command("list")
def list_folders(ctx: typer.Context) -> None:
    """List all folders."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    folders = client.get("/folders")

    rows: list[list[str]] = []
    for f in folders:
        uid = f.get("uid", "")
        title = f.get("title", "")
        folder_id = str(f.get("id", ""))
        url = f.get("url", "")
        rows.append([uid, title, folder_id, url])

    out.table(
        f"Folders ({len(folders)})",
        [("UID", "cyan"), ("Title", ""), ("ID", "dim"), ("URL", "dim")],
        rows,
        data_for_json=folders,
    )


@app.command("create")
def create_folder(
    ctx: typer.Context,
    title: Annotated[str, typer.Argument(help="Folder name")],
    uid: Annotated[str | None, typer.Option("--uid", help="Custom UID (auto-generated if omitted)")] = None,
) -> None:
    """Create a new folder."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    payload: dict = {"title": title}
    if uid:
        payload["uid"] = uid

    result = client.post("/folders", json_body=payload)
    out.success(f"Folder created: {result.get('title', title)} (uid: {result.get('uid', '')})")


@app.command("delete")
def delete_folder(
    ctx: typer.Context,
    uid: Annotated[str, typer.Argument(help="Folder UID")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete a folder and all its dashboards."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    if not force:
        typer.confirm(f"Delete folder '{uid}' and ALL its dashboards?", abort=True)

    client.delete(f"/folders/{uid}")
    out.success(f"Folder '{uid}' deleted")
