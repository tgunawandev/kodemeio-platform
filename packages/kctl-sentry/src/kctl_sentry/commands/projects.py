"""Project management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_sentry.core.callbacks import AppContext
from kctl_sentry.core.exceptions import KctlError

app = typer.Typer(help="Manage Sentry projects.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all projects with issue counts."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        projects = c.client.org_get("/projects/")
        if not isinstance(projects, list):
            projects = []

        rows: list[list[str]] = []
        for proj in projects:
            slug = proj.get("slug", "")
            name = proj.get("name", "")
            platform = proj.get("platform", "") or ""
            status = proj.get("status", "")
            team = ""
            if proj.get("team") and isinstance(proj["team"], dict):
                team = proj["team"].get("slug", "")
            elif proj.get("teams") and isinstance(proj["teams"], list) and proj["teams"]:
                team = proj["teams"][0].get("slug", "") if isinstance(proj["teams"][0], dict) else ""

            rows.append([slug, name, platform, team, status])

        out.table(
            "Projects",
            [
                ("Slug", "cyan"),
                ("Name", ""),
                ("Platform", ""),
                ("Team", "dim"),
                ("Status", "green"),
            ],
            rows,
            data_for_json=projects,
        )
    except KctlError as e:
        out.error(f"Failed to list projects: {e}")
        raise typer.Exit(1) from e


@app.command("show")
def show(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Project slug")],
) -> None:
    """Show project details."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        proj = c.client.project_get(slug, "/")
        if not isinstance(proj, dict):
            proj = {}

        teams = proj.get("teams", [])
        team_names = (
            ", ".join(t.get("slug", "") for t in teams if isinstance(t, dict)) if isinstance(teams, list) else ""
        )

        features = proj.get("features", [])
        feature_str = ", ".join(features[:10]) if isinstance(features, list) else ""

        sections = [
            (
                "Project",
                [
                    ("Slug", proj.get("slug", "")),
                    ("Name", proj.get("name", "")),
                    ("Platform", proj.get("platform", "") or ""),
                    ("Status", proj.get("status", "")),
                    ("Teams", team_names),
                    ("Date created", (proj.get("dateCreated", "") or "")[:19]),
                    ("Features", feature_str or "[dim]none[/dim]"),
                ],
            ),
        ]

        out.detail(
            f"Project: {slug}",
            sections,
            data_for_json=proj,
        )
    except KctlError as e:
        out.error(f"Failed to show project: {e}")
        raise typer.Exit(1) from e


@app.command("dsn")
def dsn(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Project slug")],
) -> None:
    """Get DSN key for SDK configuration."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        keys = c.client.project_get(slug, "/keys/")
        if not isinstance(keys, list):
            keys = []

        rows: list[list[str]] = []
        for key in keys:
            label = key.get("label", key.get("name", ""))
            dsn_public = key.get("dsn", {}).get("public", "") if isinstance(key.get("dsn"), dict) else ""
            is_active = "Yes" if key.get("isActive", True) else "No"
            rows.append([label, dsn_public, is_active])

        out.table(
            f"DSN Keys — {slug}",
            [
                ("Label", "cyan"),
                ("DSN (Public)", "green"),
                ("Active", ""),
            ],
            rows,
            data_for_json=keys,
        )
    except KctlError as e:
        out.error(f"Failed to get DSN: {e}")
        raise typer.Exit(1) from e


@app.command("create")
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Project name")],
    team: Annotated[str, typer.Option("--team", "-t", help="Team slug")],
    platform: Annotated[str, typer.Option("--platform", help="Platform (e.g. python, javascript, node)")] = "",
) -> None:
    """Create a new project."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        payload: dict[str, str] = {"name": name}
        if platform:
            payload["platform"] = platform

        result = c.client.post(
            f"/teams/{c.client.organization}/{team}/projects/",
            json=payload,
        )
        if not isinstance(result, dict):
            result = {}

        slug = result.get("slug", "")
        if out.json_mode:
            out.raw_json(result)
        else:
            out.success(f"Project created: {slug}")
            out.kv("Name", result.get("name", ""))
            out.kv("Slug", slug)
            out.kv("Platform", result.get("platform", "") or "")
    except KctlError as e:
        out.error(f"Failed to create project: {e}")
        raise typer.Exit(1) from e
