"""HTTP basic auth protection commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Manage HTTP basic auth protection.")


@app.command()
def get(
    ctx: typer.Context,
    security_id: Annotated[str, typer.Argument(help="Security entry ID")],
) -> None:
    """Get security entry details."""
    c: AppContext = ctx.obj
    data = c.client.get("/security.one", params={"securityId": security_id})
    if not isinstance(data, dict):
        c.output.error(f"Security entry '{security_id}' not found")
        raise typer.Exit(1)
    sections = [
        (
            "Security",
            [
                ("ID", data.get("securityId", "")),
                ("Username", data.get("username", "")),
                ("Application ID", data.get("applicationId", "-")),
                ("Created", data.get("createdAt", "-")),
            ],
        ),
    ]
    c.output.detail(f"Security: {data.get('securityId', '')}", sections, data_for_json=data)


@app.command()
def create(
    ctx: typer.Context,
    application_id: Annotated[str, typer.Option("--application", "-a", help="Application ID")],
    username: Annotated[str, typer.Option("--username", "-u", help="Basic auth username")],
    password: Annotated[str, typer.Option("--password", help="Basic auth password", prompt=True, hide_input=True)],
) -> None:
    """Create a new HTTP basic auth entry."""
    c: AppContext = ctx.obj
    payload: dict = {
        "applicationId": application_id,
        "username": username,
        "password": password,
    }
    result = c.client.post("/security.create", json=payload)
    sid = result.get("securityId", "") if isinstance(result, dict) else ""
    c.output.success(f"Security entry created: {sid}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def update(
    ctx: typer.Context,
    security_id: Annotated[str, typer.Argument(help="Security entry ID")],
    username: Annotated[str | None, typer.Option("--username", "-u", help="New username")] = None,
    password: Annotated[str | None, typer.Option("--password", help="New password")] = None,
) -> None:
    """Update a security entry."""
    c: AppContext = ctx.obj
    payload: dict = {"securityId": security_id}
    if username is not None:
        payload["username"] = username
    if password is not None:
        payload["password"] = password
    if len(payload) == 1:
        c.output.error("No update options provided.")
        raise typer.Exit(1)
    result = c.client.post("/security.update", json=payload)
    c.output.success(f"Security entry '{security_id}' updated")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def delete(
    ctx: typer.Context,
    security_id: Annotated[str, typer.Argument(help="Security entry ID to delete")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete a security entry (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete security entry '{security_id}'? This cannot be undone.", abort=True)
    result = c.client.post("/security.delete", json={"securityId": security_id})
    c.output.success(f"Security entry '{security_id}' deleted")
    if c.json_mode:
        c.output.raw_json(result)
