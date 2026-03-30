"""Application management commands."""

from __future__ import annotations

from typing import Annotated

import typer

app = typer.Typer(help="Application management")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all applications."""
    c = ctx.obj
    apps = c.client.get_all("core/applications/")
    rows = []
    for a in apps:
        provider = a.get("provider_obj", {}) or {}
        rows.append(
            [
                a.get("slug", ""),
                a.get("name", ""),
                provider.get("name", "-"),
                a.get("meta_launch_url", "") or "-",
            ]
        )
    c.output.table(
        "Applications",
        [("Slug", "cyan"), ("Name", ""), ("Provider", "dim"), ("Launch URL", "dim")],
        rows,
        data_for_json=apps,
    )


@app.command()
def get(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Application slug")],
) -> None:
    """Get application details."""
    c = ctx.obj
    a = c.client.get(f"core/applications/{slug}/")
    provider = a.get("provider_obj", {}) or {}
    c.output.detail(
        a.get("name", slug),
        [
            (
                "Application",
                [
                    ("Slug", a.get("slug", "")),
                    ("Name", a.get("name", "")),
                    ("Description", a.get("meta_description", "") or "-"),
                    ("Launch URL", a.get("meta_launch_url", "") or "-"),
                    ("Open in new tab", str(a.get("open_in_new_tab", False))),
                ],
            ),
            (
                "Provider",
                [
                    ("ID", str(a.get("provider", "-"))),
                    ("Name", provider.get("name", "-")),
                    ("Type", provider.get("verbose_name", "-")),
                ],
            ),
            (
                "Policy",
                [
                    ("Engine mode", a.get("policy_engine_mode", "-")),
                    ("Backchannel providers", str(len(a.get("backchannel_providers", [])))),
                ],
            ),
        ],
        data_for_json=a,
    )


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Application name")],
    slug: Annotated[str, typer.Argument(help="Application slug")],
    provider: Annotated[int | None, typer.Option("--provider", help="Provider ID")] = None,
    launch_url: Annotated[str | None, typer.Option("--launch-url", help="Launch URL")] = None,
    description: Annotated[str | None, typer.Option("--description", help="Description")] = None,
) -> None:
    """Create a new application."""
    c = ctx.obj
    payload: dict = {"name": name, "slug": slug}
    if provider is not None:
        payload["provider"] = provider
    if launch_url is not None:
        payload["meta_launch_url"] = launch_url
    if description is not None:
        payload["meta_description"] = description

    result = c.client.post("core/applications/", data=payload)
    c.output.success(f"Created application '{result.get('name', name)}' (slug: {result.get('slug', slug)})")


@app.command()
def update(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Application slug")],
    field: Annotated[str, typer.Argument(help="Field to update")],
    value: Annotated[str, typer.Argument(help="New value")],
) -> None:
    """Update an application field."""
    c = ctx.obj
    result = c.client.patch(f"core/applications/{slug}/", data={field: value})
    c.output.success(f"Updated '{slug}' field '{field}'")


@app.command()
def delete(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Application slug")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete an application."""
    if not force:
        typer.confirm(f"Delete application '{slug}'?", abort=True)
    c = ctx.obj
    c.client.delete(f"core/applications/{slug}/")
    c.output.success(f"Deleted application '{slug}'")


@app.command("launch-urls")
def launch_urls(ctx: typer.Context) -> None:
    """List all applications with their launch URLs."""
    c = ctx.obj
    apps = c.client.get_all("core/applications/")
    rows = []
    for a in apps:
        rows.append(
            [
                a.get("slug", ""),
                a.get("name", ""),
                a.get("meta_launch_url", "") or "-",
            ]
        )
    c.output.table(
        "Launch URLs",
        [("Slug", "cyan"), ("Name", ""), ("Launch URL", "green")],
        rows,
        data_for_json=[
            {"slug": a["slug"], "name": a["name"], "launch_url": a.get("meta_launch_url", "")} for a in apps
        ],
    )


@app.command()
def access(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Application slug")],
) -> None:
    """Show which groups and policies can access an application."""
    c = ctx.obj
    a = c.client.get(f"core/applications/{slug}/")
    c.output.header(f"Access: {a.get('name', slug)}")
    c.output.info(f"Policy engine mode: {a.get('policy_engine_mode', 'unknown')}")

    bindings = c.client.get_all(
        "policies/bindings/",
        params={"target": a.get("pk", "")},
    )

    if not bindings:
        c.output.info("No policy bindings found (app may be open to all)")
        if c.output.json_mode:
            c.output.raw_json({"application": slug, "bindings": []})
        return

    rows = []
    for b in bindings:
        group = b.get("group_obj", {}) or {}
        user = b.get("user_obj", {}) or {}
        policy = b.get("policy_obj", {}) or {}
        target_type = "group" if group else ("user" if user else ("policy" if policy else "unknown"))
        target_name = group.get("name", "") or user.get("username", "") or policy.get("name", "") or "-"
        rows.append(
            [
                target_type,
                target_name,
                str(b.get("enabled", True)),
                str(b.get("order", 0)),
                str(b.get("negate", False)),
            ]
        )

    c.output.table(
        f"Access Bindings: {a.get('name', slug)}",
        [("Type", "cyan"), ("Target", ""), ("Enabled", ""), ("Order", "dim"), ("Negate", "dim")],
        rows,
        data_for_json=bindings,
    )
