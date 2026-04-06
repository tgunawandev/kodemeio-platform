"""Invitation management commands."""

from __future__ import annotations

import json
from typing import Annotated, Optional

import typer

from kctl_zulip.core.callbacks import AppContext

app = typer.Typer(help="Invitation management.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all invitations."""
    c: AppContext = ctx.obj
    data = c.client.get("invites")
    invites = data.get("invites", [])

    rows = [
        [
            str(inv.get("id", "")),
            inv.get("email", ""),
            inv.get("invited_by", {}).get("email", "") if isinstance(inv.get("invited_by"), dict) else str(inv.get("invited_by", "")),
            "yes" if inv.get("is_multiuse") else "no",
            str(inv.get("invited_at", "")),
        ]
        for inv in invites
    ]

    c.output.table(
        f"Invitations ({len(invites)})",
        [("ID", "cyan"), ("Email", "green"), ("Invited By", ""), ("Multi-use", ""), ("Created", "dim")],
        rows,
        data_for_json=invites,
    )


@app.command()
def create(
    ctx: typer.Context,
    emails: Annotated[str, typer.Argument(help="Comma-separated email addresses")],
    streams: Annotated[Optional[str], typer.Option("--streams", "-s", help="Comma-separated stream IDs to auto-subscribe")] = None,
    message: Annotated[Optional[str], typer.Option("--message", "-m", help="Invitation message")] = None,
    invite_expires_in_minutes: Annotated[int, typer.Option("--expires", help="Invitation expiry in minutes (0=never)")] = 10080,
) -> None:
    """Send email invitations to join the Zulip organization."""
    c: AppContext = ctx.obj

    email_list = [e.strip() for e in emails.split(",") if e.strip()]
    stream_ids = []
    if streams:
        stream_ids = [int(s.strip()) for s in streams.split(",") if s.strip()]

    payload: dict = {
        "invitee_emails": "\n".join(email_list),
        "stream_ids": json.dumps(stream_ids),
        "invite_expires_in_minutes": str(invite_expires_in_minutes),
        "invite_as": "400",  # member role
    }
    if message:
        payload["message"] = message

    result = c.client.post("invites", data=payload)
    c.output.success(f"Invitations sent to {len(email_list)} email(s)")


@app.command()
def revoke(
    ctx: typer.Context,
    invite_id: Annotated[int, typer.Argument(help="Invitation ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Revoke an invitation."""
    c: AppContext = ctx.obj

    if not force:
        if not typer.confirm(f"Revoke invitation {invite_id}?"):
            raise typer.Abort()

    c.client.delete(f"invites/{invite_id}")
    c.output.success(f"Invitation {invite_id} revoked")
