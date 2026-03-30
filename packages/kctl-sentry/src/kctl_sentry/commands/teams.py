"""Team management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_sentry.core.callbacks import AppContext
from kctl_sentry.core.exceptions import KctlError

app = typer.Typer(help="Manage teams.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all teams in the organization."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        teams = c.client.org_get("/teams/")
        if not isinstance(teams, list):
            teams = []

        rows: list[list[str]] = []
        for team in teams:
            slug = team.get("slug", "")
            name = team.get("name", "")
            member_count = str(team.get("memberCount", 0))
            has_access = "Yes" if team.get("hasAccess", False) else "No"
            rows.append([slug, name, member_count, has_access])

        out.table(
            "Teams",
            [
                ("Slug", "cyan"),
                ("Name", ""),
                ("Members", ""),
                ("Access", "green"),
            ],
            rows,
            data_for_json=teams,
        )
    except KctlError as e:
        out.error(f"Failed to list teams: {e}")
        raise typer.Exit(1) from e


@app.command("show")
def show(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Team slug")],
) -> None:
    """Show team details, members, and assigned projects."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        team = c.client.get(f"/teams/{c.client.organization}/{slug}/")
        if not isinstance(team, dict):
            team = {}

        # Fetch team members
        try:
            members = c.client.get(f"/teams/{c.client.organization}/{slug}/members/")
            if not isinstance(members, list):
                members = []
        except Exception:
            members = []

        # Fetch team projects
        try:
            projects = c.client.get(f"/teams/{c.client.organization}/{slug}/projects/")
            if not isinstance(projects, list):
                projects = []
        except Exception:
            projects = []

        sections = [
            (
                "Team",
                [
                    ("Slug", team.get("slug", "")),
                    ("Name", team.get("name", "")),
                    ("Members", str(team.get("memberCount", len(members)))),
                    ("Date created", (team.get("dateCreated", "") or "")[:19]),
                ],
            ),
        ]

        # Members section
        if members:
            member_kvs: list[tuple[str, str]] = []
            for member in members[:20]:
                if isinstance(member, dict):
                    email = member.get("email", "")
                    name = member.get("name", email)
                    role = member.get("role", member.get("teamRole", ""))
                    member_kvs.append((name, f"{email} ({role})" if role else email))
            if member_kvs:
                sections.append(("Members", member_kvs))

        # Projects section
        if projects:
            project_kvs: list[tuple[str, str]] = []
            for proj in projects[:20]:
                if isinstance(proj, dict):
                    project_kvs.append((proj.get("slug", ""), proj.get("platform", "") or ""))
            if project_kvs:
                sections.append(("Projects", project_kvs))

        out.detail(
            f"Team: {slug}",
            sections,
            data_for_json={"team": team, "members": members, "projects": projects},
        )
    except KctlError as e:
        out.error(f"Failed to show team: {e}")
        raise typer.Exit(1) from e
