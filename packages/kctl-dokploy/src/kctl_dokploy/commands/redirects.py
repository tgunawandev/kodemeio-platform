"""URL redirect rule management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Manage URL redirect rules.")


@app.command()
def get(
    ctx: typer.Context,
    redirect_id: Annotated[str, typer.Argument(help="Redirect rule ID")],
) -> None:
    """Get redirect rule details."""
    c: AppContext = ctx.obj
    data = c.client.get("/redirects.one", params={"redirectId": redirect_id})
    if not isinstance(data, dict):
        c.output.error(f"Redirect '{redirect_id}' not found")
        raise typer.Exit(1)
    sections = [
        (
            "Redirect",
            [
                ("ID", data.get("redirectId", "")),
                ("Regex", data.get("regex", "")),
                ("Replacement", data.get("replacement", "")),
                ("Permanent", "yes" if data.get("permanent") else "no"),
                ("Application ID", data.get("applicationId", "-")),
                ("Created", data.get("createdAt", "-")),
            ],
        ),
    ]
    c.output.detail(f"Redirect: {data.get('redirectId', '')}", sections, data_for_json=data)


@app.command()
def create(
    ctx: typer.Context,
    application_id: Annotated[str, typer.Option("--application", "-a", help="Application ID")],
    regex: Annotated[str, typer.Option("--regex", "-r", help="Regex pattern to match")],
    replacement: Annotated[str, typer.Option("--replacement", help="Replacement URL")],
    permanent: Annotated[
        bool, typer.Option("--permanent/--no-permanent", help="Use 301 (permanent) or 302 (temporary)")
    ] = False,
) -> None:
    """Create a new URL redirect rule."""
    c: AppContext = ctx.obj
    payload: dict = {
        "applicationId": application_id,
        "regex": regex,
        "replacement": replacement,
        "permanent": permanent,
    }
    result = c.client.post("/redirects.create", json=payload)
    rid = result.get("redirectId", "") if isinstance(result, dict) else ""
    c.output.success(f"Redirect created: {rid}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def update(
    ctx: typer.Context,
    redirect_id: Annotated[str, typer.Argument(help="Redirect rule ID")],
    regex: Annotated[str | None, typer.Option("--regex", "-r", help="New regex pattern")] = None,
    replacement: Annotated[str | None, typer.Option("--replacement", help="New replacement URL")] = None,
    permanent: Annotated[bool | None, typer.Option("--permanent/--no-permanent", help="301 or 302")] = None,
) -> None:
    """Update a redirect rule."""
    c: AppContext = ctx.obj
    payload: dict = {"redirectId": redirect_id}
    if regex is not None:
        payload["regex"] = regex
    if replacement is not None:
        payload["replacement"] = replacement
    if permanent is not None:
        payload["permanent"] = permanent
    if len(payload) == 1:
        c.output.error("No update options provided.")
        raise typer.Exit(1)
    result = c.client.post("/redirects.update", json=payload)
    c.output.success(f"Redirect '{redirect_id}' updated")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def delete(
    ctx: typer.Context,
    redirect_id: Annotated[str, typer.Argument(help="Redirect rule ID to delete")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete a redirect rule (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete redirect '{redirect_id}'? This cannot be undone.", abort=True)
    result = c.client.post("/redirects.delete", json={"redirectId": redirect_id})
    c.output.success(f"Redirect '{redirect_id}' deleted")
    if c.json_mode:
        c.output.raw_json(result)
