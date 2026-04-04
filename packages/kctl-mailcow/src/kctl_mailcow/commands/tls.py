"""TLS policy management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage TLS policy maps.")


_handle_result = handle_result


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all TLS policy maps."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("tls-policy-map/all")
    items = data if isinstance(data, list) else []

    if not items:
        c.output.info("No TLS policy maps found.")
        return

    rows = []
    for item in items:
        active = "[green]yes[/green]" if str(item.get("active")) == "1" else "[red]no[/red]"
        rows.append(
            [
                str(item.get("id", "")),
                item.get("dest", ""),
                item.get("policy", ""),
                item.get("parameters", "-") or "-",
                active,
            ]
        )

    c.output.table(
        f"TLS Policy Maps ({len(items)})",
        [("ID", "dim"), ("Destination", "cyan"), ("Policy", ""), ("Parameters", "dim"), ("Active", "")],
        rows,
        data_for_json=items,
    )


@app.command()
def create(
    ctx: typer.Context,
    domain: Annotated[str, typer.Argument(help="Destination domain")],
    policy: Annotated[
        str,
        typer.Option("--policy", help="TLS policy (none, may, encrypt, dane, dane-only, fingerprint, verify, secure)"),
    ] = "dane",
    parameters: Annotated[str, typer.Option("--parameters", help="Additional parameters")] = "",
    active: Annotated[bool, typer.Option("--active/--inactive", help="Active state")] = True,
) -> None:
    """Create a TLS policy map entry."""
    c: AppContext = ctx.obj
    payload = {
        "dest": domain,
        "policy": policy,
        "parameters": parameters,
        "active": "1" if active else "0",
    }
    result = c.client.mc_add("tls-policy-map", payload)
    _handle_result(c, result, f"TLS policy map for '{domain}' created (policy: {policy})")


@app.command()
def delete(
    ctx: typer.Context,
    tls_id: Annotated[str, typer.Argument(help="TLS policy map ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a TLS policy map entry."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete TLS policy map '{tls_id}'?"):
            raise typer.Exit(0)

    result = c.client.mc_delete("tls-policy-map", [tls_id])
    _handle_result(c, result, f"TLS policy map '{tls_id}' deleted")
