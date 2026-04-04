"""Spam whitelist/blacklist policy management."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage spam whitelist/blacklist policies.")


@app.command("list")
def list_(
    ctx: typer.Context,
    domain: Annotated[str | None, typer.Option("--domain", "-d", help="Filter by domain")] = None,
    mailbox: Annotated[str | None, typer.Option("--mailbox", "-m", help="Filter by mailbox")] = None,
) -> None:
    """List whitelist/blacklist policies."""
    c: AppContext = ctx.obj
    all_items: list[dict] = []

    if domain:
        for ptype in ("wl", "bl"):
            data = c.client.mc_get(f"policy_{ptype}_domain/{domain}")
            if isinstance(data, list):
                for item in data:
                    item["_policy_type"] = "whitelist" if ptype == "wl" else "blacklist"
                    item["_scope"] = "domain"
                all_items.extend(data)
    elif mailbox:
        for ptype in ("wl", "bl"):
            data = c.client.mc_get(f"policy_{ptype}_mailbox/{mailbox}")
            if isinstance(data, list):
                for item in data:
                    item["_policy_type"] = "whitelist" if ptype == "wl" else "blacklist"
                    item["_scope"] = "mailbox"
                all_items.extend(data)
    else:
        c.output.error("Specify --domain or --mailbox")
        raise typer.Exit(1)

    if not all_items:
        c.output.info("No policies found.")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for item in all_items:
        rows.append(
            [
                str(item.get("prefid", "")),
                item.get("_policy_type", ""),
                item.get("_scope", ""),
                item.get("object", ""),
                item.get("value", ""),
            ]
        )

    c.output.table(
        "Policies",
        [("ID", "dim"), ("Type", "cyan"), ("Scope", ""), ("Object", ""), ("Value", "")],
        rows,
        data_for_json=all_items,
    )


@app.command("add-whitelist")
def add_whitelist(
    ctx: typer.Context,
    object_: Annotated[str, typer.Argument(help="Domain or mailbox to apply policy to")],
    value: Annotated[str, typer.Argument(help="Address/domain to whitelist")],
) -> None:
    """Add a whitelist entry."""
    c: AppContext = ctx.obj
    payload = {"object": object_, "value": value, "type": "wl"}
    result = c.client.mc_add("domain-policy", payload)
    handle_result(c, result, f"Whitelist added: {value} for {object_}")


@app.command("add-blacklist")
def add_blacklist(
    ctx: typer.Context,
    object_: Annotated[str, typer.Argument(help="Domain or mailbox to apply policy to")],
    value: Annotated[str, typer.Argument(help="Address/domain to blacklist")],
) -> None:
    """Add a blacklist entry."""
    c: AppContext = ctx.obj
    payload = {"object": object_, "value": value, "type": "bl"}
    result = c.client.mc_add("domain-policy", payload)
    handle_result(c, result, f"Blacklist added: {value} for {object_}")


@app.command()
def delete(
    ctx: typer.Context,
    policy_id: Annotated[str, typer.Argument(help="Policy ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a policy entry."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete policy {policy_id}?"):
            raise typer.Exit(0)
    result = c.client.mc_delete("domain-policy", [policy_id])
    handle_result(c, result, f"Policy {policy_id} deleted")
