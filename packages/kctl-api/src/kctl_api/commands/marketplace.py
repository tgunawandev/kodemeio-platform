"""Marketplace commands for kctl-api.

Browse, search, install, and manage extensions.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.exceptions import APIError, AuthenticationError
from kctl_api.core.exceptions import ConnectionError as KctlConnectionError

app = typer.Typer(name="marketplace", help="Extension marketplace — browse, install, publish.", no_args_is_help=True)

_BASE = "/api/v1/marketplace/extensions"


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------
@app.command(name="list")
def list_extensions(
    ctx: typer.Context,
    page: Annotated[int, typer.Option("--page", "-p", help="Page number.")] = 1,
    per_page: Annotated[int, typer.Option("--per-page", "-n", help="Items per page.")] = 20,
    category: Annotated[str | None, typer.Option("--category", "-c", help="Filter by category.")] = None,
) -> None:
    """List marketplace extensions."""
    actx: AppContext = ctx.obj
    out = actx.output

    params: dict[str, str | int] = {"page": page, "per_page": per_page}
    if category:
        params["category"] = category

    try:
        data = actx.client.get(_BASE, params=params)
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    items = data.get("items", []) if isinstance(data, dict) else []
    total = data.get("total", len(items)) if isinstance(data, dict) else len(items)

    rows: list[list[str]] = []
    for ext in items:
        rows.append(
            [
                str(ext.get("id", "")),
                ext.get("name", ""),
                ext.get("version", ""),
                ext.get("author", ""),
                ext.get("category", ""),
                "[green]yes[/green]" if ext.get("installed") else "[dim]no[/dim]",
            ]
        )

    out.table(
        title=f"Marketplace Extensions (page {page}, {total} total)",
        columns=[
            ("ID", "bold"),
            ("Name", ""),
            ("Version", ""),
            ("Author", "dim"),
            ("Category", ""),
            ("Installed", ""),
        ],
        rows=rows,
        data_for_json=items,
    )


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------
@app.command()
def search(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Search query.")],
    page: Annotated[int, typer.Option("--page", "-p", help="Page number.")] = 1,
    per_page: Annotated[int, typer.Option("--per-page", "-n", help="Items per page.")] = 20,
) -> None:
    """Search marketplace extensions by name or description."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        data = actx.client.get(_BASE, params={"search": query, "page": page, "per_page": per_page})
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    items = data.get("items", []) if isinstance(data, dict) else []
    total = data.get("total", len(items)) if isinstance(data, dict) else len(items)

    rows: list[list[str]] = []
    for ext in items:
        rows.append(
            [
                str(ext.get("id", "")),
                ext.get("name", ""),
                ext.get("version", ""),
                ext.get("description", "")[:60],
            ]
        )

    out.table(
        title=f"Search: '{query}' ({total} results)",
        columns=[
            ("ID", "bold"),
            ("Name", ""),
            ("Version", ""),
            ("Description", "dim"),
        ],
        rows=rows,
        data_for_json=items,
    )


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------
@app.command(name="get")
def get_extension(
    ctx: typer.Context,
    extension_id: Annotated[str, typer.Argument(help="Extension ID.")],
) -> None:
    """Get extension details."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        data = actx.client.get(f"{_BASE}/{extension_id}")
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    if not data:
        out.error(f"Extension not found: {extension_id}")
        raise typer.Exit(1)

    out.detail(
        title=f"Extension: {data.get('name', extension_id)}",
        sections=[
            ("Details", [(k, str(v)) for k, v in data.items()]),
        ],
        data_for_json=data,
    )


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------
@app.command()
def install(
    ctx: typer.Context,
    extension_id: Annotated[str, typer.Argument(help="Extension ID to install.")],
) -> None:
    """Install a marketplace extension via POST."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        result = actx.client.post(f"{_BASE}/{extension_id}/install")
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"Extension {extension_id} installed.")
    if actx.json_mode:
        out.raw_json(result)


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------
@app.command()
def uninstall(
    ctx: typer.Context,
    extension_id: Annotated[str, typer.Argument(help="Extension ID to uninstall.")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation.")] = False,
) -> None:
    """Uninstall a marketplace extension via DELETE."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not force:
        confirm = typer.confirm(f"Uninstall extension {extension_id}?", default=False)
        if not confirm:
            out.info("Cancelled.")
            raise typer.Exit(0)

    try:
        result = actx.client.delete(f"{_BASE}/{extension_id}/install")
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"Extension {extension_id} uninstalled.")
    if actx.json_mode:
        out.raw_json(result)


# ---------------------------------------------------------------------------
# publish
# ---------------------------------------------------------------------------
@app.command()
def publish(
    ctx: typer.Context,
    manifest_path: Annotated[str, typer.Argument(help="Path to extension manifest JSON.")],
) -> None:
    """Publish a new extension via POST /api/v1/marketplace/extensions."""
    actx: AppContext = ctx.obj
    out = actx.output

    import json
    from pathlib import Path

    manifest_file = Path(manifest_path)
    if not manifest_file.exists():
        out.error(f"Manifest file not found: {manifest_path}")
        raise typer.Exit(1)

    try:
        payload = json.loads(manifest_file.read_text())
    except json.JSONDecodeError as e:
        out.error(f"Invalid JSON manifest: {e}")
        raise typer.Exit(1) from None

    try:
        result = actx.client.post(_BASE, json=payload)
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"Extension published: {payload.get('name', 'unknown')}")
    if actx.json_mode:
        out.raw_json(result)


# ---------------------------------------------------------------------------
# review
# ---------------------------------------------------------------------------
@app.command()
def review(
    ctx: typer.Context,
    extension_id: Annotated[str, typer.Argument(help="Extension ID to review.")],
    rating: Annotated[int, typer.Option("--rating", "-r", help="Rating (1-5).")],
    comment: Annotated[str | None, typer.Option("--comment", "-c", help="Review comment.")] = None,
) -> None:
    """Submit a review for an extension via POST."""
    actx: AppContext = ctx.obj
    out = actx.output

    if rating < 1 or rating > 5:
        out.error("Rating must be between 1 and 5.")
        raise typer.Exit(1)

    payload: dict = {"rating": rating}
    if comment:
        payload["comment"] = comment

    try:
        result = actx.client.post(f"{_BASE}/{extension_id}/reviews", json=payload)
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"Review submitted for extension {extension_id}.")
    if actx.json_mode:
        out.raw_json(result)


# ---------------------------------------------------------------------------
# versions
# ---------------------------------------------------------------------------
@app.command()
def versions(
    ctx: typer.Context,
    extension_id: Annotated[str, typer.Argument(help="Extension ID.")],
) -> None:
    """List available versions for an extension via GET."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        data = actx.client.get(f"{_BASE}/{extension_id}/versions")
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    items = data if isinstance(data, list) else data.get("items", []) if isinstance(data, dict) else []

    rows: list[list[str]] = []
    for v in items:
        rows.append(
            [
                v.get("version", ""),
                str(v.get("released_at", "")),
                v.get("changelog", "")[:60],
            ]
        )

    out.table(
        title=f"Versions: Extension {extension_id}",
        columns=[
            ("Version", "bold"),
            ("Released", "dim"),
            ("Changelog", ""),
        ],
        rows=rows,
        data_for_json=items,
    )
