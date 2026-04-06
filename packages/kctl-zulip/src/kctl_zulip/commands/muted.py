"""Muted topics and users commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_zulip.core.callbacks import AppContext

app = typer.Typer(help="Muted topics and users.")


@app.command()
def topics(
    ctx: typer.Context,
) -> None:
    """List muted topics."""
    c: AppContext = ctx.obj
    data = c.client.get("users/me/subscriptions")
    muted = data.get("muted_topics", [])

    rows = []
    for item in muted:
        # muted_topics is a list of [stream_name, topic_name, timestamp]
        if isinstance(item, list) and len(item) >= 2:
            rows.append([str(item[0]), str(item[1]), str(item[2]) if len(item) > 2 else ""])
        elif isinstance(item, dict):
            rows.append(
                [
                    str(item.get("stream", item.get("stream_name", ""))),
                    str(item.get("topic", item.get("topic_name", ""))),
                    str(item.get("date_muted", "")),
                ]
            )

    c.output.table(
        f"Muted Topics ({len(rows)})",
        [("Stream", "cyan"), ("Topic", "green"), ("Muted At", "dim")],
        rows,
        data_for_json=muted,
    )


@app.command("mute-topic")
def mute_topic(
    ctx: typer.Context,
    stream: Annotated[str, typer.Argument(help="Stream name")],
    topic: Annotated[str, typer.Argument(help="Topic name")],
) -> None:
    """Mute a topic."""
    c: AppContext = ctx.obj

    c.client.patch(
        "users/me/subscriptions/muted_topics",
        data={
            "stream": stream,
            "topic": topic,
            "op": "add",
        },
    )
    c.output.success(f"Muted topic '{topic}' in #{stream}")


@app.command("unmute-topic")
def unmute_topic(
    ctx: typer.Context,
    stream: Annotated[str, typer.Argument(help="Stream name")],
    topic: Annotated[str, typer.Argument(help="Topic name")],
) -> None:
    """Unmute a topic."""
    c: AppContext = ctx.obj

    c.client.patch(
        "users/me/subscriptions/muted_topics",
        data={
            "stream": stream,
            "topic": topic,
            "op": "remove",
        },
    )
    c.output.success(f"Unmuted topic '{topic}' in #{stream}")


@app.command("mute-user")
def mute_user(
    ctx: typer.Context,
    user_id: Annotated[int, typer.Argument(help="User ID to mute")],
) -> None:
    """Mute a user."""
    c: AppContext = ctx.obj
    c.client.post(f"users/me/muted_users/{user_id}")
    c.output.success(f"User {user_id} muted")


@app.command("unmute-user")
def unmute_user(
    ctx: typer.Context,
    user_id: Annotated[int, typer.Argument(help="User ID to unmute")],
) -> None:
    """Unmute a user."""
    c: AppContext = ctx.obj
    c.client.delete(f"users/me/muted_users/{user_id}")
    c.output.success(f"User {user_id} unmuted")
