"""Waiting Room management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_cf.core.callbacks import AppContext
from kctl_cf.core.utils import resolve_zone

app = typer.Typer(help="Manage Waiting Rooms.")


@app.command("list")
def list_(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """List waiting rooms."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    result = c.client.get(f"/zones/{zone_id}/waiting_rooms")
    if not isinstance(result, list):
        result = []
    rows = []
    for r in result:
        rows.append(
            [
                r.get("id", "")[:12],
                r.get("name", ""),
                r.get("host", ""),
                r.get("path", "/"),
                str(r.get("total_active_users", "")),
                str(r.get("new_users_per_minute", "")),
                r.get("status", ""),
            ]
        )
    c.output.table(
        f"Waiting Rooms — {zone}",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("Host", "green"),
            ("Path", ""),
            ("Active Users", ""),
            ("New Users/Min", ""),
            ("Status", "green"),
        ],
        rows,
        data_for_json=result,
    )


@app.command()
def get(
    ctx: typer.Context,
    room_id: Annotated[str, typer.Argument(help="Waiting room ID")],
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Get waiting room details."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    result = c.client.get(f"/zones/{zone_id}/waiting_rooms/{room_id}")
    if not isinstance(result, dict):
        result = {}
    sections = [
        (
            "Waiting Room",
            [
                ("ID", result.get("id", "")),
                ("Name", result.get("name", "")),
                ("Description", result.get("description", "")),
                ("Host", result.get("host", "")),
                ("Path", result.get("path", "/")),
            ],
        ),
        (
            "Capacity",
            [
                ("Total Active Users", str(result.get("total_active_users", ""))),
                ("New Users Per Minute", str(result.get("new_users_per_minute", ""))),
                ("Session Duration", str(result.get("session_duration", ""))),
                ("Queue All", str(result.get("queue_all", False))),
                ("Disable Session Renewal", str(result.get("disable_session_renewal", False))),
            ],
        ),
        (
            "Timestamps",
            [
                ("Created", (result.get("created_on") or "")[:19]),
                ("Modified", (result.get("modified_on") or "")[:19]),
            ],
        ),
    ]
    c.output.detail(f"Waiting Room — {result.get('name', room_id)}", sections, data_for_json=result)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="Waiting room name")],
    host: Annotated[str, typer.Option("--host", help="Hostname to attach the waiting room to")],
    total_active_users: Annotated[int, typer.Option("--total-active-users", help="Max concurrent active users")],
    new_users_per_minute: Annotated[int, typer.Option("--new-users-per-minute", help="New users allowed per minute")],
    path: Annotated[str, typer.Option("--path", help="Path to protect")] = "/",
    session_duration: Annotated[int, typer.Option("--session-duration", help="Session duration in minutes")] = 5,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Create a waiting room."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    payload: dict = {
        "name": name,
        "host": host,
        "total_active_users": total_active_users,
        "new_users_per_minute": new_users_per_minute,
        "path": path,
        "session_duration": session_duration,
    }
    result = c.client.post(f"/zones/{zone_id}/waiting_rooms", json=payload)
    wr_id = result.get("id", "") if isinstance(result, dict) else ""
    c.output.success(f"Waiting room created: {wr_id}")


@app.command()
def update(
    ctx: typer.Context,
    room_id: Annotated[str, typer.Argument(help="Waiting room ID to update")],
    name: Annotated[str | None, typer.Option("--name", help="Waiting room name")] = None,
    total_active_users: Annotated[
        int | None, typer.Option("--total-active-users", help="Max concurrent active users")
    ] = None,
    new_users_per_minute: Annotated[
        int | None, typer.Option("--new-users-per-minute", help="New users allowed per minute")
    ] = None,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Update a waiting room (merges with existing settings)."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    existing = c.client.get(f"/zones/{zone_id}/waiting_rooms/{room_id}")
    if not isinstance(existing, dict):
        existing = {}
    payload: dict = {
        "name": name or existing.get("name", ""),
        "host": existing.get("host", ""),
        "total_active_users": total_active_users
        if total_active_users is not None
        else existing.get("total_active_users", 200),
        "new_users_per_minute": new_users_per_minute
        if new_users_per_minute is not None
        else existing.get("new_users_per_minute", 200),
    }
    c.client.put(f"/zones/{zone_id}/waiting_rooms/{room_id}", json=payload)
    c.output.success(f"Waiting room updated: {room_id}")


@app.command("delete")
def delete_(
    ctx: typer.Context,
    room_id: Annotated[str, typer.Argument(help="Waiting room ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Delete a waiting room. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    c.client.delete(f"/zones/{zone_id}/waiting_rooms/{room_id}")
    c.output.success(f"Waiting room deleted: {room_id}")
