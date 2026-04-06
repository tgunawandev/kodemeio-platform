"""Message reaction commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_zulip.core.callbacks import AppContext

app = typer.Typer(help="Message reactions.")


@app.command()
def add(
    ctx: typer.Context,
    message_id: Annotated[int, typer.Argument(help="Message ID")],
    emoji_name: Annotated[str, typer.Argument(help="Emoji name (e.g. thumbs_up)")],
) -> None:
    """Add a reaction to a message."""
    c: AppContext = ctx.obj
    c.client.post(f"messages/{message_id}/reactions", data={"emoji_name": emoji_name})
    c.output.success(f"Reaction :{emoji_name}: added to message {message_id}")


@app.command()
def remove(
    ctx: typer.Context,
    message_id: Annotated[int, typer.Argument(help="Message ID")],
    emoji_name: Annotated[str, typer.Argument(help="Emoji name (e.g. thumbs_up)")],
) -> None:
    """Remove a reaction from a message."""
    c: AppContext = ctx.obj
    c.client.request("DELETE", f"messages/{message_id}/reactions", data={"emoji_name": emoji_name})
    c.output.success(f"Reaction :{emoji_name}: removed from message {message_id}")


@app.command("list")
def list_(
    ctx: typer.Context,
    message_id: Annotated[int, typer.Argument(help="Message ID")],
) -> None:
    """List reactions on a message."""
    import json

    c: AppContext = ctx.obj
    data = c.client.get(
        "messages",
        params={
            "anchor": str(message_id),
            "num_before": "0",
            "num_after": "0",
            "narrow": json.dumps([{"operator": "id", "operand": message_id}]),
        },
    )
    messages = data.get("messages", [])
    if not messages:
        c.output.warn(f"Message {message_id} not found")
        return

    reactions = messages[0].get("reactions", [])

    rows = []
    for r in reactions:
        rows.append(
            [
                r.get("emoji_name", ""),
                r.get("emoji_code", ""),
                str(r.get("user_id", "")),
                r.get("reaction_type", ""),
            ]
        )

    c.output.table(
        f"Reactions on message {message_id} ({len(reactions)})",
        [("Emoji", "cyan"), ("Code", "dim"), ("User ID", "green"), ("Type", "dim")],
        rows,
        data_for_json=reactions,
    )
