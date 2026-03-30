"""Redirect and Bulk Redirect management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_cloudflare.core.callbacks import AppContext
from kctl_cloudflare.core.utils import require_account, resolve_zone

app = typer.Typer(help="Manage Cloudflare Redirect and Bulk Redirect rules.")


@app.command("lists")
def lists_(ctx: typer.Context) -> None:
    """List bulk redirect lists."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    result = c.client.get(f"/accounts/{acct}/rules/lists")
    if not isinstance(result, list):
        result = []
    # Filter to redirect type lists
    redirect_lists = [lst for lst in result if lst.get("kind", "") == "redirect"]
    rows = []
    for lst in redirect_lists:
        rows.append(
            [
                lst.get("id", "")[:12],
                lst.get("name", ""),
                str(lst.get("num_items", 0)),
                lst.get("created_on", "")[:19],
                lst.get("modified_on", "")[:19],
            ]
        )
    c.output.table(
        "Bulk Redirect Lists",
        [("ID", "dim"), ("Name", "cyan"), ("Items", "green"), ("Created", "dim"), ("Modified", "dim")],
        rows,
        data_for_json=redirect_lists,
    )


@app.command("list-items")
def list_items(
    ctx: typer.Context,
    list_id: Annotated[str, typer.Argument(help="List ID")],
) -> None:
    """List items in a bulk redirect list."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    result = c.client.get(f"/accounts/{acct}/rules/lists/{list_id}/items")
    if not isinstance(result, list):
        result = []
    rows = []
    for item in result:
        redirect = item.get("redirect", {})
        rows.append(
            [
                item.get("id", "")[:12],
                redirect.get("source_url", "")[:40],
                redirect.get("target_url", "")[:40],
                str(redirect.get("status_code", 301)),
                "yes" if redirect.get("preserve_query_string") else "no",
            ]
        )
    c.output.table(
        f"Redirect List Items — {list_id[:12]}",
        [("ID", "dim"), ("Source", "cyan"), ("Target", "green"), ("Status", ""), ("Preserve QS", "dim")],
        rows,
        data_for_json=result,
    )


@app.command("create-list")
def create_list(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="Redirect list name")],
    description: Annotated[str | None, typer.Option("--description", help="List description")] = None,
) -> None:
    """Create a bulk redirect list."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    payload: dict = {"name": name, "kind": "redirect"}
    if description:
        payload["description"] = description
    result = c.client.post(f"/accounts/{acct}/rules/lists", json=payload)
    list_id = result.get("id", "") if isinstance(result, dict) else ""
    c.output.success(f"Redirect list created: {list_id}")


@app.command("delete-list")
def delete_list(
    ctx: typer.Context,
    list_id: Annotated[str, typer.Argument(help="List ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
) -> None:
    """Delete a bulk redirect list. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    acct = require_account(c)
    c.client.delete(f"/accounts/{acct}/rules/lists/{list_id}")
    c.output.success(f"Redirect list deleted: {list_id}")


@app.command("create-item")
def create_item(
    ctx: typer.Context,
    list_id: Annotated[str, typer.Argument(help="List ID")],
    source: Annotated[str, typer.Option("--source", help="Source URL pattern")],
    target: Annotated[str, typer.Option("--target", help="Target URL")],
    status_code: Annotated[int, typer.Option("--status-code", help="HTTP status code (301, 302, 307, 308)")] = 301,
) -> None:
    """Add a redirect item to a bulk redirect list."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    payload = [
        {
            "redirect": {
                "source_url": source,
                "target_url": target,
                "status_code": status_code,
            }
        }
    ]
    result = c.client.post(f"/accounts/{acct}/rules/lists/{list_id}/items", json=payload)
    op_id = result.get("operation_id", "") if isinstance(result, dict) else ""
    c.output.success(f"Redirect item created (operation: {op_id})")


@app.command("delete-item")
def delete_item(
    ctx: typer.Context,
    list_id: Annotated[str, typer.Argument(help="List ID")],
    item_id: Annotated[str, typer.Argument(help="Item ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
) -> None:
    """Delete a redirect item from a bulk redirect list. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    acct = require_account(c)
    payload = {"items": [{"id": item_id}]}
    c.client.request("DELETE", f"/accounts/{acct}/rules/lists/{list_id}/items", json=payload)
    c.output.success(f"Redirect item deleted: {item_id}")


@app.command()
def rulesets(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """List rulesets for a zone (filtered to redirect phase)."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    result = c.client.get(f"/zones/{zone_id}/rulesets")
    if not isinstance(result, list):
        result = []
    # Filter for redirect-related rulesets
    redirect_rulesets = [
        rs for rs in result if "redirect" in rs.get("phase", "").lower() or "redirect" in rs.get("name", "").lower()
    ]
    rows = []
    for rs in redirect_rulesets:
        rows.append(
            [
                rs.get("id", "")[:12],
                rs.get("name", ""),
                rs.get("phase", ""),
                str(rs.get("version", "")),
                rs.get("last_updated", "")[:19],
            ]
        )
    c.output.table(
        f"Redirect Rulesets — {zone}",
        [("ID", "dim"), ("Name", "cyan"), ("Phase", "green"), ("Version", "dim"), ("Updated", "dim")],
        rows,
        data_for_json=redirect_rulesets,
    )
