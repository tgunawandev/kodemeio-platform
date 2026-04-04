"""Forwarding host management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage forwarding hosts.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all forwarding hosts."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("fwdhost/all")
    items = data if isinstance(data, list) else (list(data.values()) if isinstance(data, dict) else [])

    if not items:
        c.output.info("No forwarding hosts configured")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for h in items:
        if isinstance(h, dict):
            rows.append(
                [
                    h.get("host", str(h)),
                    h.get("source", ""),
                    h.get("filter_spam", ""),
                ]
            )
        else:
            rows.append([str(h), "", ""])

    c.output.table(
        "Forwarding Hosts",
        [("Host", "cyan"), ("Source", ""), ("Filter Spam", "")],
        rows,
        data_for_json=items if items and isinstance(items[0], dict) else [{"host": h} for h in items],
    )


@app.command()
def add(
    ctx: typer.Context,
    hostname: Annotated[str, typer.Argument(help="Hostname or IP address")],
    filter_spam: Annotated[
        bool, typer.Option("--filter-spam/--no-filter-spam", help="Filter spam from this host")
    ] = False,
) -> None:
    """Add a forwarding host."""
    c: AppContext = ctx.obj
    payload = {
        "hostname": hostname,
        "filter_spam": "1" if filter_spam else "0",
    }
    result = c.client.mc_add("fwdhost", payload)
    handle_result(c, result, f"Forwarding host '{hostname}' added")


@app.command()
def delete(
    ctx: typer.Context,
    hostname: Annotated[str, typer.Argument(help="Hostname to remove")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a forwarding host."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Remove forwarding host '{hostname}'?"):
            raise typer.Exit(0)

    result = c.client.mc_delete("fwdhost", [hostname])
    handle_result(c, result, f"Forwarding host '{hostname}' removed")
