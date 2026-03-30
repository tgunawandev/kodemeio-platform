"""Organization management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_glitchtip.core.callbacks import AppContext

app = typer.Typer(help="Manage GlitchTip organizations.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List organizations."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    orgs = c.get_list("organizations/")

    rows: list[list[str]] = []
    for o in orgs:
        slug = o.get("slug", "")
        name = o.get("name", "")
        created = str(o.get("dateCreated", ""))[:10]
        rows.append([name, slug, created])

    out.table(
        "Organizations",
        [("Name", "cyan"), ("Slug", ""), ("Created", "dim")],
        rows,
        data_for_json=orgs,
    )


@app.command()
def get(
    ctx: typer.Context,
    org_slug: Annotated[str, typer.Argument(help="Organization slug")],
) -> None:
    """Get organization details."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    org = c.get(f"organizations/{org_slug}/")

    sections = [
        ("Organization", [
            ("Name", org.get("name", "")),
            ("Slug", org.get("slug", "")),
            ("Date Created", str(org.get("dateCreated", ""))),
            ("Open Membership", str(org.get("openMembership", ""))),
        ]),
    ]

    # Get members
    try:
        members = c.get_list(f"organizations/{org_slug}/members/")
        if members:
            member_kvs = []
            for m in members:
                user = m.get("user", {}) or {}
                email = m.get("email") or user.get("email", "")
                role = m.get("orgRole") or m.get("role", "")
                pending = " (pending)" if m.get("pending") else ""
                member_kvs.append((email, f"{role}{pending}"))
            sections.append(("Members", member_kvs))
    except Exception:
        pass

    out.detail("Organization Details", sections, data_for_json=org)
