"""Quarantine management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext

app = typer.Typer(help="Manage quarantined messages.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List quarantined messages."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("quarantine/all")
    items = data if isinstance(data, list) else []

    if not items:
        c.output.info("Quarantine is empty")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for q in items:
        rows.append(
            [
                str(q.get("id", "")),
                q.get("sender", ""),
                q.get("rcpt", q.get("recipients", "")),
                q.get("subject", ""),
                q.get("created", q.get("arrived", "")),
                q.get("action", ""),
            ]
        )

    c.output.table(
        "Quarantine",
        [("ID", "dim"), ("Sender", ""), ("Recipient", "cyan"), ("Subject", ""), ("Date", ""), ("Action", "")],
        rows,
        data_for_json=items,
    )


@app.command()
def release(
    ctx: typer.Context,
    qid: Annotated[str, typer.Argument(help="Quarantine message ID")],
) -> None:
    """Release a quarantined message."""
    c: AppContext = ctx.obj
    payload = {
        "items": [qid],
        "attr": {"action": "release"},
    }
    result = c.client.mc_edit("quarantine", payload)

    if isinstance(result, list):
        errors = [r for r in result if isinstance(r, dict) and r.get("type") == "danger"]
        if errors:
            for e in errors:
                c.output.error(str(e.get("msg", e)))
            raise typer.Exit(1)

    c.output.success(f"Message {qid} released from quarantine")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def delete(
    ctx: typer.Context,
    qid: Annotated[str, typer.Argument(help="Quarantine message ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a quarantined message."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete quarantined message {qid}?"):
            raise typer.Exit(0)

    result = c.client.mc_delete("quarantine", [qid])

    if isinstance(result, list):
        errors = [r for r in result if isinstance(r, dict) and r.get("type") == "danger"]
        if errors:
            for e in errors:
                c.output.error(str(e.get("msg", e)))
            raise typer.Exit(1)

    c.output.success(f"Quarantined message {qid} deleted")
    if c.json_mode:
        c.output.raw_json(result)
