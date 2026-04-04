"""Sync job management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext

app = typer.Typer(help="Manage IMAP sync jobs.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all sync jobs."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("syncjobs/all/no_log")
    items = data if isinstance(data, list) else []

    if not items:
        c.output.info("No sync jobs configured")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for j in items:
        active = "[green]yes[/green]" if str(j.get("active")) == "1" else "[red]no[/red]"
        rows.append(
            [
                str(j.get("id", "")),
                j.get("user2", ""),
                f"{j.get('user1', '')}@{j.get('host1', '')}",
                active,
                str(j.get("mins_interval", "")),
            ]
        )

    c.output.table(
        "Sync Jobs",
        [("ID", "dim"), ("Local Mailbox", "cyan"), ("Remote", ""), ("Active", ""), ("Interval (min)", "")],
        rows,
        data_for_json=items,
    )


@app.command()
def add(
    ctx: typer.Context,
    local_mailbox: Annotated[str, typer.Argument(help="Local mailbox email")],
    remote_host: Annotated[str, typer.Option("--host", help="Remote IMAP host")],
    remote_user: Annotated[str, typer.Option("--user", help="Remote IMAP username")],
    remote_password: Annotated[
        str, typer.Option("--password", help="Remote IMAP password", prompt=True, hide_input=True)
    ],
    remote_port: Annotated[int, typer.Option("--port", help="Remote IMAP port")] = 993,
    mins_interval: Annotated[int, typer.Option("--interval", help="Sync interval in minutes")] = 20,
    enc1: Annotated[str, typer.Option("--enc", help="Encryption: SSL, TLS, PLAIN")] = "SSL",
    delete2duplicates: Annotated[bool, typer.Option("--delete-duplicates")] = True,
    active: Annotated[bool, typer.Option("--active/--inactive")] = True,
) -> None:
    """Add a new sync job."""
    c: AppContext = ctx.obj
    payload = {
        "username": local_mailbox,
        "host1": remote_host,
        "port1": str(remote_port),
        "user1": remote_user,
        "password1": remote_password,
        "enc1": enc1,
        "mins_interval": str(mins_interval),
        "delete2duplicates": "1" if delete2duplicates else "0",
        "active": "1" if active else "0",
    }
    result = c.client.mc_add("syncjob", payload)

    if isinstance(result, list):
        errors = [r for r in result if isinstance(r, dict) and r.get("type") == "danger"]
        if errors:
            for e in errors:
                c.output.error(str(e.get("msg", e)))
            raise typer.Exit(1)

    c.output.success(f"Sync job added for {local_mailbox}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def delete(
    ctx: typer.Context,
    job_id: Annotated[str, typer.Argument(help="Sync job ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a sync job."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete sync job {job_id}?"):
            raise typer.Exit(0)

    result = c.client.mc_delete("syncjob", [job_id])

    if isinstance(result, list):
        errors = [r for r in result if isinstance(r, dict) and r.get("type") == "danger"]
        if errors:
            for e in errors:
                c.output.error(str(e.get("msg", e)))
            raise typer.Exit(1)

    c.output.success(f"Sync job {job_id} deleted")
    if c.json_mode:
        c.output.raw_json(result)
