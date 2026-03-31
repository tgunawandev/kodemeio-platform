"""Hetzner Storage Box management commands.

Storage Boxes are managed via the Hetzner Robot API (https://robot-ws.your-server.de).
Requires Robot API credentials (username/password), separate from Cloud API token.
"""

from __future__ import annotations

import os
from typing import Annotated

import httpx
import typer

from kctl_hz.core.callbacks import AppContext
from kctl_hz.core.utils import human_size

app = typer.Typer(help="Manage Hetzner Storage Boxes (Robot API).")

_ROBOT_API = "https://robot-ws.your-server.de"


def _robot_creds() -> tuple[str, str]:
    """Resolve Robot API credentials from env."""
    user = os.environ.get("HETZNER_ROBOT_USER", "")
    password = os.environ.get("HETZNER_ROBOT_PASSWORD", "")
    return user, password


def _require_robot() -> tuple[str, str]:
    """Require Robot API credentials or abort."""
    user, password = _robot_creds()
    if not user or not password:
        typer.echo(
            "Robot API credentials not configured. Set HETZNER_ROBOT_USER and HETZNER_ROBOT_PASSWORD.",
            err=True,
        )
        raise typer.Exit(1)
    return user, password


def _robot_get(path: str) -> dict:
    """GET from Robot API with basic auth."""
    user, password = _require_robot()
    resp = httpx.get(f"{_ROBOT_API}{path}", auth=(user, password), timeout=30)
    if resp.status_code == 401:
        typer.echo("Robot API authentication failed. Check HETZNER_ROBOT_USER/PASSWORD.", err=True)
        raise typer.Exit(1)
    if resp.status_code >= 400:
        typer.echo(f"Robot API error {resp.status_code}: {resp.text[:200]}", err=True)
        raise typer.Exit(1)
    return resp.json()


def _robot_post(path: str, data: dict | None = None) -> dict:
    """POST to Robot API with basic auth (form-encoded)."""
    user, password = _require_robot()
    resp = httpx.post(f"{_ROBOT_API}{path}", auth=(user, password), data=data or {}, timeout=30)
    if resp.status_code == 401:
        typer.echo("Robot API authentication failed. Check HETZNER_ROBOT_USER/PASSWORD.", err=True)
        raise typer.Exit(1)
    if resp.status_code >= 400:
        typer.echo(f"Robot API error {resp.status_code}: {resp.text[:200]}", err=True)
        raise typer.Exit(1)
    return resp.json() if resp.content else {}


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all Storage Boxes."""
    c: AppContext = ctx.obj
    data = _robot_get("/storagebox")
    boxes = [item.get("storagebox", item) for item in data] if isinstance(data, list) else []

    rows = []
    for sb in boxes:
        disk_quota = sb.get("disk_quota", 0)
        disk_usage = sb.get("disk_usage", 0)
        rows.append(
            [
                str(sb.get("id", "")),
                sb.get("name", sb.get("login", "")),
                sb.get("login", ""),
                sb.get("server", sb.get("location", "")),
                human_size(disk_quota * 1024 * 1024) if disk_quota else "-",
                human_size(disk_usage * 1024 * 1024) if disk_usage else "-",
            ]
        )
    c.output.table(
        "Storage Boxes",
        [("ID", "dim"), ("Name", "cyan"), ("Login", ""), ("Server", ""), ("Quota", ""), ("Used", "")],
        rows,
        data_for_json=boxes,
    )


@app.command()
def get(
    ctx: typer.Context,
    storagebox_id: Annotated[int, typer.Argument(help="Storage Box ID")],
) -> None:
    """Get Storage Box details."""
    c: AppContext = ctx.obj
    data = _robot_get(f"/storagebox/{storagebox_id}")
    sb = data.get("storagebox", data)

    disk_quota = sb.get("disk_quota", 0)
    disk_usage = sb.get("disk_usage", 0)
    pct = f"{(disk_usage / disk_quota * 100):.1f}%" if disk_quota else "-"

    sections = [
        (
            "Storage Box",
            [
                ("ID", str(sb.get("id", ""))),
                ("Name", sb.get("name", "")),
                ("Login", sb.get("login", "")),
                ("Server", sb.get("server", "")),
                ("Quota", human_size(disk_quota * 1024 * 1024) if disk_quota else "-"),
                ("Used", human_size(disk_usage * 1024 * 1024) if disk_usage else "-"),
                ("Usage %", pct),
                ("Cancelled", str(sb.get("cancelled", False))),
                ("Paid Until", sb.get("paid_until", "-")),
            ],
        ),
        (
            "Access Settings",
            [
                ("WebDAV", str(sb.get("webdav", False))),
                ("Samba", str(sb.get("samba", False))),
                ("SSH", str(sb.get("ssh", False))),
                ("External Reachability", str(sb.get("external_reachability", False))),
                ("ZFS", str(sb.get("zfs", False))),
            ],
        ),
    ]
    c.output.detail(f"Storage Box: {storagebox_id}", sections, data_for_json=sb)


@app.command()
def update(
    ctx: typer.Context,
    storagebox_id: Annotated[int, typer.Argument(help="Storage Box ID")],
    name: Annotated[str | None, typer.Option("--name", help="New name")] = None,
    webdav: Annotated[bool | None, typer.Option("--webdav/--no-webdav", help="Enable/disable WebDAV")] = None,
    samba: Annotated[bool | None, typer.Option("--samba/--no-samba", help="Enable/disable Samba")] = None,
    ssh: Annotated[bool | None, typer.Option("--ssh/--no-ssh", help="Enable/disable SSH")] = None,
    external_reachability: Annotated[
        bool | None,
        typer.Option("--external/--no-external", help="Enable/disable external reachability"),
    ] = None,
    zfs: Annotated[bool | None, typer.Option("--zfs/--no-zfs", help="Enable/disable ZFS")] = None,
) -> None:
    """Update Storage Box settings."""
    c: AppContext = ctx.obj
    form: dict = {}
    if name is not None:
        form["storagebox_name"] = name
    if webdav is not None:
        form["webdav"] = "true" if webdav else "false"
    if samba is not None:
        form["samba"] = "true" if samba else "false"
    if ssh is not None:
        form["ssh"] = "true" if ssh else "false"
    if external_reachability is not None:
        form["external_reachability"] = "true" if external_reachability else "false"
    if zfs is not None:
        form["zfs"] = "true" if zfs else "false"

    if not form:
        c.output.error("Provide at least one option to update")
        raise typer.Exit(1)

    _robot_post(f"/storagebox/{storagebox_id}", data=form)
    c.output.success(f"Storage Box {storagebox_id} updated")


@app.command()
def snapshots(
    ctx: typer.Context,
    storagebox_id: Annotated[int, typer.Argument(help="Storage Box ID")],
) -> None:
    """List snapshots of a Storage Box."""
    c: AppContext = ctx.obj
    data = _robot_get(f"/storagebox/{storagebox_id}/snapshot")
    snap_list = [item.get("snapshot", item) for item in data] if isinstance(data, list) else []

    rows = []
    for snap in snap_list:
        rows.append(
            [
                snap.get("name", ""),
                snap.get("timestamp", ""),
                human_size(snap.get("size", 0) * 1024 * 1024),
            ]
        )
    c.output.table(
        f"Snapshots: Storage Box {storagebox_id}",
        [("Name", "cyan"), ("Timestamp", ""), ("Size", "")],
        rows,
        data_for_json=snap_list,
    )


@app.command("create-snapshot")
def create_snapshot(
    ctx: typer.Context,
    storagebox_id: Annotated[int, typer.Argument(help="Storage Box ID")],
) -> None:
    """Create a snapshot of a Storage Box."""
    c: AppContext = ctx.obj
    _robot_post(f"/storagebox/{storagebox_id}/snapshot")
    c.output.success(f"Snapshot created for Storage Box {storagebox_id}")


@app.command("delete-snapshot")
def delete_snapshot(
    ctx: typer.Context,
    storagebox_id: Annotated[int, typer.Argument(help="Storage Box ID")],
    snapshot_name: Annotated[str, typer.Argument(help="Snapshot name")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a Storage Box snapshot."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete snapshot '{snapshot_name}' from Storage Box {storagebox_id}?", abort=True)

    user, password = _require_robot()
    resp = httpx.delete(
        f"{_ROBOT_API}/storagebox/{storagebox_id}/snapshot/{snapshot_name}",
        auth=(user, password),
        timeout=30,
    )
    if resp.status_code >= 400:
        c.output.error(f"Failed to delete snapshot: {resp.text[:200]}")
        raise typer.Exit(1)
    c.output.success(f"Snapshot '{snapshot_name}' deleted from Storage Box {storagebox_id}")


@app.command("reset-password")
def reset_password(
    ctx: typer.Context,
    storagebox_id: Annotated[int, typer.Argument(help="Storage Box ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Reset the password of a Storage Box."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Reset password for Storage Box {storagebox_id}?", abort=True)

    data = _robot_post(f"/storagebox/{storagebox_id}/password")
    new_password = data.get("password", "")
    c.output.success(f"Password reset for Storage Box {storagebox_id}")
    if new_password:
        c.output.info(f"New password: {new_password}")
    if c.output.json_mode:
        c.output.raw_json(data)


@app.command("subaccounts")
def list_subaccounts(
    ctx: typer.Context,
    storagebox_id: Annotated[int, typer.Argument(help="Storage Box ID")],
) -> None:
    """List sub-accounts of a Storage Box."""
    c: AppContext = ctx.obj
    data = _robot_get(f"/storagebox/{storagebox_id}/subaccount")
    accounts = [item.get("subaccount", item) for item in data] if isinstance(data, list) else []

    rows = []
    for acc in accounts:
        rows.append(
            [
                acc.get("username", ""),
                acc.get("homedirectory", ""),
                str(acc.get("webdav", False)),
                str(acc.get("samba", False)),
                str(acc.get("ssh", False)),
                str(acc.get("readonly", False)),
            ]
        )
    c.output.table(
        f"Sub-accounts: Storage Box {storagebox_id}",
        [("Username", "cyan"), ("Home Dir", ""), ("WebDAV", ""), ("Samba", ""), ("SSH", ""), ("Read-only", "")],
        rows,
        data_for_json=accounts,
    )
