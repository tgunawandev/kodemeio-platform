"""properties — list / show / verify GSC properties."""

from __future__ import annotations

import typer
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]
from kctl_lib.exceptions import NotFoundError

app = typer.Typer(help="GSC property browsing.")


@app.command("list")
def list_cmd(ctx: typer.Context) -> None:
    """List all properties visible to the service account."""
    actx = ctx.obj
    out = actx.output
    data = actx.client.sites().list().execute() or {}
    entries = data.get("siteEntry", [])
    rows = [[e.get("siteUrl", ""), e.get("permissionLevel", "")] for e in entries]
    data_for_json = [{"property": e.get("siteUrl", ""), "permission": e.get("permissionLevel", "")} for e in entries]
    out.table(
        "Properties",
        [("property", "cyan"), ("permission", "")],
        rows,
        data_for_json=data_for_json,
    )


@app.command()
def show(ctx: typer.Context, property_uri: str) -> None:
    """Show metadata for one property."""
    actx = ctx.obj
    try:
        data = actx.client.sites().get(siteUrl=property_uri).execute()
    except HttpError as e:
        if getattr(e.resp, "status", 0) == 404:
            raise NotFoundError("property", property_uri) from e
        raise
    data = data or {}
    sections = [
        (
            "Property",
            [
                ("siteUrl", str(data.get("siteUrl", ""))),
                ("permissionLevel", str(data.get("permissionLevel", ""))),
            ],
        )
    ]
    actx.output.detail(f"Property: {property_uri}", sections, data_for_json=data)


@app.command()
def verify(ctx: typer.Context, property_uri: str) -> None:
    """Attempt a read on a property to verify SA permission."""
    actx = ctx.obj
    out = actx.output
    try:
        actx.client.searchanalytics().query(
            siteUrl=property_uri,
            body={"startDate": "2024-01-01", "endDate": "2024-01-02", "rowLimit": 1},
        ).execute()
    except HttpError as e:
        status = getattr(e.resp, "status", 0)
        out.error(f"verify failed: HTTP {status}")
        raise typer.Exit(code=1) from e
    sa_email = getattr(actx.client, "service_account_email", "") or "(unknown SA)"
    out.success(f"{property_uri} accessible by {sa_email}")
