"""Stream management commands."""

from __future__ import annotations

import json
from typing import Annotated, Optional

import typer

from kctl_zulip.core.callbacks import AppContext

app = typer.Typer(help="Stream management.")


def _resolve_stream_id(client, name_or_id: str) -> int:
    """Resolve stream name to ID."""
    try:
        return int(name_or_id)
    except ValueError:
        data = client.get("get_stream_id", params={"stream": name_or_id})
        return data["stream_id"]


@app.command("list")
def list_(
    ctx: typer.Context,
    include_public: Annotated[bool, typer.Option("--public", help="Include public streams")] = True,
    include_subscribed: Annotated[bool, typer.Option("--subscribed", help="Only subscribed streams")] = False,
    include_web_public: Annotated[bool, typer.Option("--web-public", help="Include web-public streams")] = False,
) -> None:
    """List all streams."""
    c: AppContext = ctx.obj

    if include_subscribed:
        data = c.client.get("users/me/subscriptions")
        streams = data.get("subscriptions", [])
    else:
        data = c.client.get("streams", params={"include_web_public": str(include_web_public).lower()})
        streams = data.get("streams", [])

    rows = [
        [
            str(s.get("stream_id", "")),
            s.get("name", ""),
            s.get("description", "")[:50],
            "yes" if s.get("invite_only") else "no",
            str(s.get("stream_weekly_traffic", 0)),
        ]
        for s in streams
    ]

    c.output.table(
        f"Streams ({len(streams)})",
        [("ID", "cyan"), ("Name", "green"), ("Description", ""), ("Private", ""), ("Weekly Traffic", "dim")],
        rows,
        data_for_json=streams,
    )


@app.command()
def get(
    ctx: typer.Context,
    stream: Annotated[str, typer.Argument(help="Stream ID or name")],
) -> None:
    """Get detailed stream info."""
    c: AppContext = ctx.obj
    stream_id = _resolve_stream_id(c.client, stream)
    data = c.client.get(f"streams/{stream_id}")
    s = data.get("stream", {})

    # Get subscriber count
    try:
        sub_data = c.client.get(f"streams/{stream_id}/members")
        subscriber_count = len(sub_data.get("subscribers", []))
    except Exception:
        subscriber_count = -1

    c.output.detail(
        f"Stream: {s.get('name', '')}",
        [
            (
                "Details",
                [
                    ("ID", str(s.get("stream_id", ""))),
                    ("Name", s.get("name", "")),
                    ("Description", s.get("description", "")),
                    ("Private", str(s.get("invite_only", False))),
                    ("Web Public", str(s.get("is_web_public", False))),
                    ("History Public", str(s.get("history_public_to_subscribers", True))),
                ],
            ),
            (
                "Activity",
                [
                    ("Subscribers", str(subscriber_count) if subscriber_count >= 0 else "unknown"),
                    ("Weekly Traffic", str(s.get("stream_weekly_traffic", 0))),
                    ("Date Created", s.get("date_created", "")),
                    ("First Message ID", str(s.get("first_message_id", ""))),
                ],
            ),
        ],
        data_for_json=s,
    )


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Stream name")],
    description: Annotated[str, typer.Option("--description", "-d", help="Stream description")] = "",
    private: Annotated[bool, typer.Option("--private", help="Make stream private")] = False,
    history_public: Annotated[bool, typer.Option("--history-public", help="History visible to new subscribers")] = True,
) -> None:
    """Create a new stream."""
    c: AppContext = ctx.obj

    subscriptions = [{"name": name, "description": description}]
    result = c.client.post(
        "users/me/subscriptions",
        data={
            "subscriptions": json.dumps(subscriptions),
            "invite_only": json.dumps(private),
            "history_public_to_subscribers": json.dumps(history_public),
        },
    )

    c.output.success(f"Stream '{name}' created")
    if result.get("subscribed"):
        c.output.kv("Subscribed", ", ".join(email for email, streams in result["subscribed"].items()))


@app.command()
def update(
    ctx: typer.Context,
    stream: Annotated[str, typer.Argument(help="Stream ID or name")],
    new_name: Annotated[Optional[str], typer.Option("--name", help="New stream name")] = None,
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="New description")] = None,
    private: Annotated[Optional[bool], typer.Option("--private/--public", help="Toggle privacy")] = None,
) -> None:
    """Update stream settings."""
    c: AppContext = ctx.obj
    stream_id = _resolve_stream_id(c.client, stream)

    payload: dict = {}
    if new_name is not None:
        payload["new_name"] = json.dumps(new_name)
    if description is not None:
        payload["description"] = json.dumps(description)
    if private is not None:
        payload["is_private"] = json.dumps(private)

    if not payload:
        c.output.warn("No fields to update")
        return

    c.client.patch(f"streams/{stream_id}", data=payload)
    c.output.success(f"Stream {stream_id} updated")


@app.command()
def delete(
    ctx: typer.Context,
    stream: Annotated[str, typer.Argument(help="Stream ID or name")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete (archive) a stream."""
    c: AppContext = ctx.obj
    stream_id = _resolve_stream_id(c.client, stream)

    if not force:
        data = c.client.get(f"streams/{stream_id}")
        s = data.get("stream", {})
        if not typer.confirm(f"Delete stream '{s.get('name', stream_id)}'?"):
            raise typer.Abort()

    c.client.delete(f"streams/{stream_id}")
    c.output.success(f"Stream {stream_id} deleted (archived)")


@app.command()
def subscribe(
    ctx: typer.Context,
    stream: Annotated[str, typer.Argument(help="Stream name")],
    principals: Annotated[
        Optional[str], typer.Option("--users", help="Comma-separated user IDs or emails to subscribe")
    ] = None,
) -> None:
    """Subscribe users to a stream."""
    c: AppContext = ctx.obj

    subscriptions = [{"name": stream}]
    payload: dict = {"subscriptions": json.dumps(subscriptions)}

    if principals:
        principal_list = []
        for p in principals.split(","):
            p = p.strip()
            try:
                principal_list.append(int(p))
            except ValueError:
                principal_list.append(p)
        payload["principals"] = json.dumps(principal_list)

    result = c.client.post("users/me/subscriptions", data=payload)
    subscribed = result.get("subscribed", {})
    already = result.get("already_subscribed", {})

    if subscribed:
        c.output.success(f"Subscribed to '{stream}'")
        for email, streams in subscribed.items():
            c.output.kv("User", email)
    if already:
        for email, streams in already.items():
            c.output.info(f"Already subscribed: {email}")


@app.command()
def unsubscribe(
    ctx: typer.Context,
    stream: Annotated[str, typer.Argument(help="Stream name")],
    principals: Annotated[
        Optional[str], typer.Option("--users", help="Comma-separated user IDs or emails to unsubscribe")
    ] = None,
) -> None:
    """Unsubscribe users from a stream."""
    c: AppContext = ctx.obj

    payload: dict = {"subscriptions": json.dumps([stream])}

    if principals:
        principal_list = []
        for p in principals.split(","):
            p = p.strip()
            try:
                principal_list.append(int(p))
            except ValueError:
                principal_list.append(p)
        payload["principals"] = json.dumps(principal_list)

    c.client.post("users/me/subscriptions/delete", data=payload)
    c.output.success(f"Unsubscribed from '{stream}'")
