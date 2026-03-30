"""Project management commands."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from kctl_glitchtip.core.callbacks import AppContext

app = typer.Typer(help="Manage GlitchTip projects.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all projects with DSNs."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    projects = c.get_list("projects/")

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for p in projects:
        org = p.get("organization", {})
        org_slug = org.get("slug", "") if isinstance(org, dict) else ""
        slug = p.get("slug", "")
        name = p.get("name", "")
        platform = p.get("platform") or "-"
        first_event = p.get("firstEvent") or p.get("first_event") or "-"

        # Get first DSN if available
        keys = p.get("keys", [])
        dsn = keys[0].get("dsn", {}).get("public", "-") if keys else "-"

        rows.append([name, slug, org_slug, platform, dsn[:60], str(first_event)[:10]])
        json_data.append(p)

    out.table(
        "Projects",
        [("Name", "cyan"), ("Slug", ""), ("Org", ""), ("Platform", "dim"), ("DSN", ""), ("First Event", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def get(
    ctx: typer.Context,
    org_slug: Annotated[str, typer.Argument(help="Organization slug")],
    project_slug: Annotated[str, typer.Argument(help="Project slug")],
) -> None:
    """Get project details."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    p = c.get(f"projects/{org_slug}/{project_slug}/")

    org = p.get("organization", {})
    teams = p.get("teams", [])
    team_names = ", ".join(t.get("slug", "") for t in teams) if teams else "-"

    sections = [
        (
            "Project",
            [
                ("Name", p.get("name", "")),
                ("Slug", p.get("slug", "")),
                ("Organization", org.get("slug", "") if isinstance(org, dict) else str(org)),
                ("Platform", p.get("platform") or "-"),
                ("Teams", team_names),
                ("Date Created", str(p.get("dateCreated", ""))),
                ("First Event", str(p.get("firstEvent") or p.get("first_event") or "-")),
            ],
        ),
    ]

    out.detail("Project Details", sections, data_for_json=p)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Project name")],
    org_slug: Annotated[str, typer.Option("--org", help="Organization slug")],
    team_slug: Annotated[str, typer.Option("--team", help="Team slug")],
    platform: Annotated[Optional[str], typer.Option("--platform", help="Platform (e.g. python, javascript)")] = None,
) -> None:
    """Create a new project (returns DSN)."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    payload: dict = {"name": name}
    if platform:
        payload["platform"] = platform

    p = c.post(f"teams/{org_slug}/{team_slug}/projects/", data=payload)

    keys = p.get("keys", [])
    dsn = keys[0].get("dsn", {}).get("public", "N/A") if keys else "N/A"

    out.success(f"Project '{name}' created")
    out.kv("Slug", p.get("slug", ""))
    out.kv("DSN", dsn)
    if out.json_mode:
        out.raw_json(p)


@app.command()
def update(
    ctx: typer.Context,
    org_slug: Annotated[str, typer.Argument(help="Organization slug")],
    project_slug: Annotated[str, typer.Argument(help="Project slug")],
    name: Annotated[Optional[str], typer.Option("--name", help="New project name")] = None,
    platform: Annotated[Optional[str], typer.Option("--platform", help="Platform (e.g. python, javascript)")] = None,
) -> None:
    """Update project name or platform."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    payload: dict = {}
    if name is not None:
        payload["name"] = name
    if platform is not None:
        payload["platform"] = platform

    if not payload:
        out.warn("No fields to update")
        raise typer.Exit(0)

    result = c.put(f"projects/{org_slug}/{project_slug}/", data=payload)
    out.success(f"Project '{project_slug}' updated")
    if out.json_mode:
        out.raw_json(result)


@app.command()
def delete(
    ctx: typer.Context,
    org_slug: Annotated[str, typer.Argument(help="Organization slug")],
    project_slug: Annotated[str, typer.Argument(help="Project slug")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a project."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    if not force:
        if not typer.confirm(f"Delete project '{project_slug}'?"):
            raise typer.Exit(0)

    c.delete(f"projects/{org_slug}/{project_slug}/")
    out.success(f"Project '{project_slug}' deleted")


@app.command()
def dsn(
    ctx: typer.Context,
    org_slug: Annotated[str, typer.Argument(help="Organization slug")],
    project_slug: Annotated[str, typer.Argument(help="Project slug")],
) -> None:
    """Show DSN keys for a project."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    keys = c.get_list(f"projects/{org_slug}/{project_slug}/keys/")

    rows: list[list[str]] = []
    for k in keys:
        dsn_data = k.get("dsn", {})
        rows.append(
            [
                k.get("label", k.get("name", "-")),
                k.get("id", "-"),
                dsn_data.get("public", "-"),
                "active" if k.get("isActive", k.get("is_active", True)) else "inactive",
            ]
        )

    out.table(
        f"DSN Keys — {org_slug}/{project_slug}",
        [("Label", "cyan"), ("ID", "dim"), ("DSN (Public)", ""), ("Status", "green")],
        rows,
        data_for_json=keys,
    )


@app.command("dsn-create")
def dsn_create(
    ctx: typer.Context,
    org_slug: Annotated[str, typer.Argument(help="Organization slug")],
    project_slug: Annotated[str, typer.Argument(help="Project slug")],
    label: Annotated[Optional[str], typer.Option("--label", help="Key label")] = None,
) -> None:
    """Create a new DSN key for a project."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    payload: dict = {}
    if label:
        payload["label"] = label

    key = c.post(f"projects/{org_slug}/{project_slug}/keys/", data=payload)

    dsn_data = key.get("dsn", {})
    out.success("DSN key created")
    out.kv("Public DSN", dsn_data.get("public", "N/A"))
    out.kv("Security DSN", dsn_data.get("security", "N/A"))
    if out.json_mode:
        out.raw_json(key)


@app.command()
def stats(
    ctx: typer.Context,
    org_slug: Annotated[str, typer.Argument(help="Organization slug")],
    project_slug: Annotated[str, typer.Argument(help="Project slug")],
) -> None:
    """Show event statistics for a project."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    # Get project details for event count info
    p = c.get(f"projects/{org_slug}/{project_slug}/")

    # Get recent issues count
    issues = c.get_list(f"projects/{org_slug}/{project_slug}/issues/")

    # Get recent events
    events = c.get_list(f"projects/{org_slug}/{project_slug}/events/")

    sections = [
        (
            "Project Statistics",
            [
                ("Project", f"{org_slug}/{project_slug}"),
                ("Open Issues", str(len(issues))),
                ("Recent Events", str(len(events))),
                ("First Event", str(p.get("firstEvent") or p.get("first_event") or "never")),
            ],
        ),
    ]

    out.detail(
        "Project Stats",
        sections,
        data_for_json={
            "project": f"{org_slug}/{project_slug}",
            "open_issues": len(issues),
            "recent_events": len(events),
            "project_data": p,
        },
    )
