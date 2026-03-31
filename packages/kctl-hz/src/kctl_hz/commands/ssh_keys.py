"""SSH key management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_hz.core.callbacks import AppContext
from kctl_hz.core.utils import parse_labels

app = typer.Typer(help="Manage Hetzner Cloud SSH keys.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all SSH keys."""
    c: AppContext = ctx.obj
    keys = c.client.get_all("/ssh_keys", "ssh_keys")
    rows = []
    for k in keys:
        rows.append(
            [
                str(k.get("id", "")),
                k.get("name", ""),
                k.get("fingerprint", ""),
            ]
        )
    c.output.table(
        "SSH Keys",
        [("ID", "dim"), ("Name", "cyan"), ("Fingerprint", "")],
        rows,
        data_for_json=keys,
    )


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="SSH key name")],
    public_key: Annotated[str, typer.Option("--public-key", help="Public key string")],
) -> None:
    """Create (register) a new SSH key."""
    c: AppContext = ctx.obj
    result = c.client.post("/ssh_keys", json={"name": name, "public_key": public_key})
    key = result.get("ssh_key", {})
    c.output.success(f"SSH key '{key.get('name')}' created (ID: {key.get('id')})")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command()
def update(
    ctx: typer.Context,
    key_id: Annotated[int, typer.Argument(help="SSH key ID")],
    name: Annotated[str | None, typer.Option("--name", help="New SSH key name")] = None,
    labels: Annotated[str | None, typer.Option("--labels", help="Labels as key=val,key=val")] = None,
) -> None:
    """Update an SSH key (name, labels)."""
    c: AppContext = ctx.obj
    payload: dict = {}
    if name is not None:
        payload["name"] = name
    if labels is not None:
        payload["labels"] = parse_labels(labels)
    if not payload:
        c.output.error("Provide at least one option to update (--name, --labels)")
        raise typer.Exit(1)
    result = c.client.put(f"/ssh_keys/{key_id}", json=payload)
    c.output.success(f"SSH key {key_id} updated")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command()
def delete(
    ctx: typer.Context,
    key_id: Annotated[int, typer.Argument(help="SSH key ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete an SSH key."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete SSH key {key_id}?", abort=True)
    c.client.delete(f"/ssh_keys/{key_id}")
    c.output.success(f"SSH key {key_id} deleted")
