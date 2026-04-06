"""Linkifier management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_zulip.core.callbacks import AppContext

app = typer.Typer(help="Linkifier management.")


@app.command("list")
def list_(
    ctx: typer.Context,
) -> None:
    """List realm linkifiers."""
    c: AppContext = ctx.obj
    data = c.client.get("realm/linkifiers")
    linkifiers = data.get("linkifiers", [])

    rows = []
    for lf in linkifiers:
        lid = str(lf.get("id", ""))
        pattern = lf.get("pattern", "")
        url_template = lf.get("url_template", lf.get("url_format_string", ""))
        rows.append([lid, pattern, url_template])

    c.output.table(
        f"Linkifiers ({len(linkifiers)})",
        [("ID", "cyan"), ("Pattern", "green"), ("URL Template", "")],
        rows,
        data_for_json=linkifiers,
    )


@app.command()
def create(
    ctx: typer.Context,
    pattern: Annotated[str, typer.Option("--pattern", help="Regex pattern to match")],
    url_template: Annotated[str, typer.Option("--url-template", help="URL template with {id} placeholder")],
) -> None:
    """Create a linkifier."""
    c: AppContext = ctx.obj
    result = c.client.post(
        "realm/filters",
        data={
            "pattern": pattern,
            "url_template": url_template,
        },
    )
    lid = result.get("id", "")
    c.output.success(f"Linkifier created (ID: {lid})")


@app.command()
def delete(
    ctx: typer.Context,
    linkifier_id: Annotated[int, typer.Argument(help="Linkifier ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a linkifier."""
    c: AppContext = ctx.obj

    if not force:
        if not typer.confirm(f"Delete linkifier {linkifier_id}?"):
            raise typer.Abort()

    c.client.delete(f"realm/filters/{linkifier_id}")
    c.output.success(f"Linkifier {linkifier_id} deleted")
