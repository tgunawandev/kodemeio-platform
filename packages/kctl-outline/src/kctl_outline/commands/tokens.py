"""API token management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_outline.core.callbacks import AppContext

app = typer.Typer(help="API token management.")


@app.command("list")
def list_(
    ctx: typer.Context,
) -> None:
    """List API tokens."""
    c: AppContext = ctx.obj
    result = c.client.post("apiKeys.list")
    keys = result.get("data", [])

    rows = []
    for k in keys:
        kid = str(k.get("id", ""))[:8]
        name = k.get("name", "")
        secret = str(k.get("secret", ""))[:8] + "..." if k.get("secret") else ""
        created = (k.get("createdAt", "") or "")[:10]
        last_used = (k.get("lastActiveAt", "") or "")[:10]
        rows.append([kid, name, secret, created, last_used])

    c.output.table(
        f"API Tokens ({len(keys)})",
        [("ID", "cyan"), ("Name", "green"), ("Secret", "dim"), ("Created", "dim"), ("Last Used", "dim")],
        rows,
        data_for_json=keys,
    )


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Token name")],
) -> None:
    """Create a new API token."""
    c: AppContext = ctx.obj
    result = c.client.post("apiKeys.create", data={"name": name})
    key = result.get("data", {})

    c.output.detail(
        "API Token Created",
        [
            (
                "Details",
                [
                    ("ID", key.get("id", "")),
                    ("Name", key.get("name", "")),
                    ("Secret", key.get("secret", "")),
                ],
            )
        ],
        data_for_json=key,
    )
    c.output.warn("Save the secret now - it will not be shown again.")


@app.command()
def delete(
    ctx: typer.Context,
    token_id: Annotated[str, typer.Argument(help="API token ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete an API token."""
    c: AppContext = ctx.obj

    if not force:
        if not typer.confirm(f"Delete API token {token_id[:8]}?"):
            raise typer.Abort()

    c.client.post("apiKeys.delete", data={"id": token_id})
    c.output.success(f"API token {token_id[:8]} deleted")
