"""Group management commands.

List, inspect, and update Telegram groups.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_telegram.core.callbacks import AppContext

app = typer.Typer(help="Manage Telegram groups.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all tracked groups."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    data = c.get("groups")
    groups = data.get("results", []) if isinstance(data, dict) else data if isinstance(data, list) else []

    if not groups:
        out.warn("No groups found.")
        return

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for group in groups:
        gid = str(group.get("id", ""))
        chat_id = str(group.get("chat_id", ""))
        title = group.get("title", "")
        group_type = group.get("type", "")

        rows.append([gid, chat_id, title, group_type])
        json_data.append(group)

    out.table(
        "Groups",
        [("ID", "cyan"), ("Chat ID", ""), ("Title", ""), ("Type", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def get(
    ctx: typer.Context,
    group_id: Annotated[int, typer.Argument(help="Group ID")],
) -> None:
    """Show group details."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    group = c.get(f"groups/{group_id}")

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    info_kvs: list[tuple[str, str]] = [
        ("ID", str(group.get("id", ""))),
        ("Chat ID", str(group.get("chat_id", ""))),
        ("Title", group.get("title", "")),
        ("Type", group.get("type", "")),
    ]

    # Optional fields
    if group.get("description"):
        info_kvs.append(("Description", group["description"]))
    if group.get("invite_link"):
        info_kvs.append(("Invite Link", group["invite_link"]))
    if group.get("member_count") is not None:
        info_kvs.append(("Members", str(group["member_count"])))

    sections.append(("Group Info", info_kvs))

    # Bot association
    if group.get("bot_id") or group.get("bot"):
        bot_kvs: list[tuple[str, str]] = []
        bot_kvs.append(("Bot ID", str(group.get("bot_id", group.get("bot", {}).get("id", "")))))
        if isinstance(group.get("bot"), dict):
            bot_kvs.append(("Bot Username", f"@{group['bot'].get('username', '')}"))
        sections.append(("Associated Bot", bot_kvs))

    # Timestamps
    ts_kvs: list[tuple[str, str]] = []
    if group.get("created_at"):
        ts_kvs.append(("Created", group["created_at"]))
    if group.get("updated_at"):
        ts_kvs.append(("Updated", group["updated_at"]))
    if ts_kvs:
        sections.append(("Timestamps", ts_kvs))

    out.detail(f"Group: {group.get('title', group_id)}", sections, data_for_json=group)


@app.command()
def update(
    ctx: typer.Context,
    group_id: Annotated[int, typer.Argument(help="Group ID")],
    field: Annotated[str, typer.Option("--field", help="Field name to update.")],
    value: Annotated[str, typer.Option("--value", help="New value for the field.")],
) -> None:
    """Update a group field.

    Example: kctl-telegram groups update 1 --field title --value "New Title"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    payload = {field: value}
    group = c.patch(f"groups/{group_id}", json=payload)

    out.success(f"Group {group_id} updated")
    out.kv("Field", field)
    out.kv("Value", value)

    if actx.output.json_mode:
        out.raw_json(group)
