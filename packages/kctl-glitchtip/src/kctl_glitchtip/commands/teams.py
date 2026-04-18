"""Team management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_glitchtip.core.callbacks import AppContext

app = typer.Typer(help="Manage GlitchTip teams.")


@app.command("list")
def list_(
    ctx: typer.Context,
    org_slug: Annotated[str, typer.Option("--org", help="Organization slug")],
) -> None:
    """List teams."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    teams = c.get_list(f"organizations/{org_slug}/teams/")

    rows: list[list[str]] = []
    for t in teams:
        slug = t.get("slug", "")
        name = t.get("name", "")
        member_count = str(t.get("memberCount", t.get("member_count", "-")))
        projects = t.get("projects", [])
        proj_names = ", ".join(p.get("slug", "") for p in projects) if projects else "-"
        created = str(t.get("dateCreated", ""))[:10]
        rows.append([name, slug, member_count, proj_names, created])

    out.table(
        "Teams",
        [("Name", "cyan"), ("Slug", ""), ("Members", ""), ("Projects", "dim"), ("Created", "dim")],
        rows,
        data_for_json=teams,
    )


@app.command()
def get(
    ctx: typer.Context,
    org_slug: Annotated[str, typer.Option("--org", help="Organization slug")],
    team_slug: Annotated[str, typer.Argument(help="Team slug")],
) -> None:
    """Get team details with members."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    team = c.get(f"teams/{org_slug}/{team_slug}/")
    members = c.get_list(f"teams/{org_slug}/{team_slug}/members/")

    projects = team.get("projects", [])
    proj_names = ", ".join(p.get("slug", "") for p in projects) if projects else "-"

    sections = [
        (
            "Team",
            [
                ("Name", team.get("name", "")),
                ("Slug", team.get("slug", "")),
                ("Created", str(team.get("dateCreated", ""))),
                ("Projects", proj_names),
            ],
        ),
    ]

    if members:
        member_kvs = []
        for m in members:
            user = m.get("user", {}) or {}
            email = m.get("email") or user.get("email", "")
            role = m.get("orgRole") or m.get("role", "")
            member_kvs.append((email, role))
        sections.append(("Members", member_kvs))

    out.detail("Team Details", sections, data_for_json={**team, "members": members})


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Team name")],
    org_slug: Annotated[str, typer.Option("--org", help="Organization slug")],
) -> None:
    """Create a new team."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    team = c.post(f"organizations/{org_slug}/teams/", data={"slug": name.lower().replace(" ", "-")})
    out.success(f"Team '{team.get('slug', name)}' created")
    if out.json_mode:
        out.raw_json(team)


@app.command()
def delete(
    ctx: typer.Context,
    org_slug: Annotated[str, typer.Option("--org", help="Organization slug")],
    team_slug: Annotated[str, typer.Argument(help="Team slug")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a team."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    if not force and not typer.confirm(f"Delete team '{team_slug}'?"):
        raise typer.Exit(0)

    c.delete(f"teams/{org_slug}/{team_slug}/")
    out.success(f"Team '{team_slug}' deleted")


@app.command("add-member")
def add_member(
    ctx: typer.Context,
    org_slug: Annotated[str, typer.Option("--org", help="Organization slug")],
    team_slug: Annotated[str, typer.Argument(help="Team slug")],
    email: Annotated[str, typer.Argument(help="Member email")],
) -> None:
    """Add a member to a team."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    # Find member ID by email
    members = c.get_list(f"organizations/{org_slug}/members/")
    member_id = None
    for m in members:
        user = m.get("user", {}) or {}
        if m.get("email") == email or user.get("email") == email:
            member_id = m.get("id")
            break

    if not member_id:
        out.error(f"Member with email '{email}' not found in organization")
        raise typer.Exit(1)

    result = c.post(f"organizations/{org_slug}/members/{member_id}/teams/{team_slug}/")
    out.success(f"Added {email} to team '{team_slug}'")
    if out.json_mode:
        out.raw_json(result)


@app.command("remove-member")
def remove_member(
    ctx: typer.Context,
    org_slug: Annotated[str, typer.Option("--org", help="Organization slug")],
    team_slug: Annotated[str, typer.Argument(help="Team slug")],
    email: Annotated[str, typer.Argument(help="Member email")],
) -> None:
    """Remove a member from a team."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    # Find member ID by email
    members = c.get_list(f"organizations/{org_slug}/members/")
    member_id = None
    for m in members:
        user = m.get("user", {}) or {}
        if m.get("email") == email or user.get("email") == email:
            member_id = m.get("id")
            break

    if not member_id:
        out.error(f"Member with email '{email}' not found")
        raise typer.Exit(1)

    c.delete(f"organizations/{org_slug}/members/{member_id}/teams/{team_slug}/")
    out.success(f"Removed {email} from team '{team_slug}'")
