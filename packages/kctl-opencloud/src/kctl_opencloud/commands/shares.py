"""Sharing and permission commands for kctl-opencloud."""

# NOTE: Shares/permissions API uses the beta endpoint /graph/v1beta1.
# Since API_PREFIX="/graph/v1.0", we use "../v1beta1/" to traverse one
# segment up. This is verified to work with httpx URL resolution.

from __future__ import annotations

from typing import Annotated, Any

import typer

from kctl_opencloud.core.callbacks import AppContext

app = typer.Typer(help="Sharing and permission management.")


@app.command("list")
def list_(
    ctx: typer.Context,
    space_id: Annotated[str, typer.Argument(help="Space/drive ID")],
    item_id: Annotated[str, typer.Argument(help="Item (file/folder) ID")],
) -> None:
    """List permissions on a file or folder."""
    c: AppContext = ctx.obj
    # Use beta API for permissions
    client = c.client
    data = client.get(f"../v1beta1/drives/{space_id}/items/{item_id}/permissions")
    permissions = data.get("value", []) if isinstance(data, dict) else []

    rows = []
    for p in permissions:
        link = p.get("link", {})
        granted = p.get("grantedToV2", {})
        user = granted.get("user", {})
        rows.append(
            [
                p.get("id", ""),
                user.get("displayName", link.get("type", "-")),
                ", ".join(p.get("roles", [])),
                link.get("webUrl", "-"),
            ]
        )

    c.output.table(
        "Permissions",
        [("ID", "cyan"), ("Granted To", "green"), ("Roles", "yellow"), ("Link", "white")],
        rows,
        data_for_json=permissions,
    )


@app.command("create-link")
def create_link(
    ctx: typer.Context,
    space_id: Annotated[str, typer.Argument(help="Space/drive ID")],
    item_id: Annotated[str, typer.Argument(help="Item ID")],
    type_: Annotated[str, typer.Option("--type", "-t", help="Link type: view, edit")] = "view",
    password: Annotated[str | None, typer.Option("--password", help="Link password")] = None,
) -> None:
    """Create a sharing link."""
    c: AppContext = ctx.obj
    link_data: dict[str, Any] = {
        "type": type_,
    }
    if password:
        link_data["password"] = password

    result = c.client.post(
        f"../v1beta1/drives/{space_id}/items/{item_id}/createLink",
        data=link_data,
    )
    link_url = result.get("link", {}).get("webUrl", "")
    c.output.success(f"Link created: {link_url}")


@app.command()
def invite(
    ctx: typer.Context,
    space_id: Annotated[str, typer.Argument(help="Space/drive ID")],
    item_id: Annotated[str, typer.Argument(help="Item ID")],
    user_id: Annotated[str, typer.Option("--user", "-u", help="User ID to invite")],
    role: Annotated[str, typer.Option("--role", "-r", help="Role: viewer, editor")] = "viewer",
) -> None:
    """Invite a user to access a file or folder."""
    c: AppContext = ctx.obj
    invite_data: dict[str, Any] = {
        "recipients": [{"objectId": user_id}],
        "roles": [role],
    }

    c.client.post(
        f"../v1beta1/drives/{space_id}/items/{item_id}/invite",
        data=invite_data,
    )
    c.output.success(f"User {user_id} invited with role '{role}'")


@app.command("delete")
def delete_permission(
    ctx: typer.Context,
    space_id: Annotated[str, typer.Argument(help="Space/drive ID")],
    item_id: Annotated[str, typer.Argument(help="Item ID")],
    permission_id: Annotated[str, typer.Argument(help="Permission ID")],
) -> None:
    """Remove a permission from a file or folder."""
    c: AppContext = ctx.obj
    c.client.delete(f"../v1beta1/drives/{space_id}/items/{item_id}/permissions/{permission_id}")
    c.output.success(f"Permission {permission_id} removed")
