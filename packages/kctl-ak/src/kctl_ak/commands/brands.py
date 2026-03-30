"""Brand/tenant management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_ak.core.callbacks import AppContext

app = typer.Typer(help="Brand (tenant) management.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all brands."""
    c: AppContext = ctx.obj
    brands = c.client.get_all("core/brands/")

    rows = []
    for b in brands:
        rows.append(
            [
                str(b.get("brand_uuid", b.get("pk", ""))),
                b.get("domain", ""),
                b.get("branding_title", ""),
                str(b.get("default", False)),
            ]
        )

    c.output.table(
        "Brands",
        [("ID", "cyan"), ("Domain", ""), ("Title", ""), ("Default", "dim")],
        rows,
        data_for_json=brands,
    )


@app.command()
def get(
    ctx: typer.Context,
    id_: Annotated[str, typer.Argument(metavar="ID", help="Brand UUID")],
) -> None:
    """Get brand details."""
    c: AppContext = ctx.obj
    b = c.client.get(f"core/brands/{id_}/")

    flow_kvs: list[tuple[str, str]] = []
    for key in [
        "flow_authentication",
        "flow_invalidation",
        "flow_recovery",
        "flow_unenrollment",
        "flow_user_settings",
        "flow_device_code",
    ]:
        val = b.get(key, "")
        flow_kvs.append((key.replace("flow_", "").replace("_", " ").title(), str(val) or "[dim]none[/dim]"))

    c.output.detail(
        f"Brand: {b.get('domain', str(id_))}",
        [
            (
                "Brand",
                [
                    ("ID", str(b.get("brand_uuid", b.get("pk", "")))),
                    ("Domain", b.get("domain", "")),
                    ("Default", str(b.get("default", False))),
                    ("Branding Title", b.get("branding_title", "")),
                    ("Branding Logo", b.get("branding_logo", "") or "-"),
                    ("Branding Favicon", b.get("branding_favicon", "") or "-"),
                ],
            ),
            ("Flows", flow_kvs),
        ],
        data_for_json=b,
    )


@app.command()
def create(
    ctx: typer.Context,
    domain: Annotated[str, typer.Argument(help="Brand domain")],
    name: Annotated[str, typer.Option("--name", help="Branding title")] = "",
    flow_authentication: Annotated[
        str | None, typer.Option("--flow-authentication", help="Authentication flow slug")
    ] = None,
    flow_invalidation: Annotated[
        str | None, typer.Option("--flow-invalidation", help="Invalidation flow slug")
    ] = None,
) -> None:
    """Create a brand."""
    c: AppContext = ctx.obj
    payload: dict = {
        "domain": domain,
    }
    if name:
        payload["branding_title"] = name
    if flow_authentication:
        payload["flow_authentication"] = flow_authentication
    if flow_invalidation:
        payload["flow_invalidation"] = flow_invalidation

    result = c.client.post("core/brands/", data=payload)
    c.output.success(
        f"Created brand '{result.get('domain', domain)}' (ID: {result.get('brand_uuid', result.get('pk', '?'))})"
    )


@app.command()
def update(
    ctx: typer.Context,
    id_: Annotated[str, typer.Argument(metavar="ID", help="Brand UUID")],
    name: Annotated[str | None, typer.Option("--name", help="New branding title")] = None,
    branding_title: Annotated[str | None, typer.Option("--branding-title", help="Branding title")] = None,
    branding_logo: Annotated[str | None, typer.Option("--branding-logo", help="Branding logo URL")] = None,
    branding_favicon: Annotated[str | None, typer.Option("--branding-favicon", help="Branding favicon URL")] = None,
    flow_authentication: Annotated[
        str | None, typer.Option("--flow-authentication", help="Authentication flow slug")
    ] = None,
    flow_invalidation: Annotated[
        str | None, typer.Option("--flow-invalidation", help="Invalidation flow slug")
    ] = None,
) -> None:
    """Update a brand."""
    c: AppContext = ctx.obj

    # Fetch current to merge (PUT requires full object)
    current = c.client.get(f"core/brands/{id_}/")
    payload: dict = {
        "domain": current.get("domain", ""),
    }

    title = branding_title or name
    if title is not None:
        payload["branding_title"] = title
    if branding_logo is not None:
        payload["branding_logo"] = branding_logo
    if branding_favicon is not None:
        payload["branding_favicon"] = branding_favicon
    if flow_authentication is not None:
        payload["flow_authentication"] = flow_authentication
    if flow_invalidation is not None:
        payload["flow_invalidation"] = flow_invalidation

    result = c.client.put(f"core/brands/{id_}/", data=payload)
    c.output.success(f"Updated brand '{result.get('domain', id_)}'")


@app.command()
def delete(
    ctx: typer.Context,
    id_: Annotated[str, typer.Argument(metavar="ID", help="Brand UUID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a brand."""
    if not force:
        typer.confirm(f"Delete brand {id_}?", abort=True)
    c: AppContext = ctx.obj
    c.client.delete(f"core/brands/{id_}/")
    c.output.success(f"Deleted brand {id_}")


@app.command()
def current(ctx: typer.Context) -> None:
    """Show the current brand (for this domain)."""
    c: AppContext = ctx.obj
    b = c.client.get("core/brands/current/")

    flow_kvs: list[tuple[str, str]] = []
    for key in [
        "flow_authentication",
        "flow_invalidation",
        "flow_recovery",
        "flow_unenrollment",
        "flow_user_settings",
        "flow_device_code",
    ]:
        val = b.get(key, "")
        flow_kvs.append((key.replace("flow_", "").replace("_", " ").title(), str(val) or "[dim]none[/dim]"))

    c.output.detail(
        f"Current Brand: {b.get('domain', '?')}",
        [
            (
                "Brand",
                [
                    ("ID", str(b.get("brand_uuid", b.get("pk", "")))),
                    ("Domain", b.get("domain", "")),
                    ("Default", str(b.get("default", False))),
                    ("Branding Title", b.get("branding_title", "")),
                    ("Branding Logo", b.get("branding_logo", "") or "-"),
                    ("Branding Favicon", b.get("branding_favicon", "") or "-"),
                ],
            ),
            ("Flows", flow_kvs),
        ],
        data_for_json=b,
    )
