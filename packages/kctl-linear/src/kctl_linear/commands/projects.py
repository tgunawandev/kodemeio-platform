"""Project tracking commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_linear.core.callbacks import AppContext
from kctl_linear.core.client import PROJECT_SHOW_QUERY, PROJECTS_LIST_QUERY

app = typer.Typer(help="Project tracking.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List active projects with progress."""
    actx: AppContext = ctx.obj
    out = actx.output

    data = actx.client.query(PROJECTS_LIST_QUERY)
    projects = data.get("projects", {}).get("nodes", [])

    if out.json_mode:
        out.raw_json(projects)
        return

    if not projects:
        out.info("No projects found")
        return

    rows = [
        [
            p.get("name", ""),
            p.get("state", ""),
            f"{(p.get('progress', 0) or 0) * 100:.0f}%",
            (p.get("lead") or {}).get("name", "-"),
            (p.get("targetDate") or "-")[:10],
        ]
        for p in projects
    ]
    out.table(
        f"Projects ({len(projects)})",
        [("Name", "cyan"), ("State", "green"), ("Progress", "yellow"), ("Lead", "magenta"), ("Target", "white")],
        rows,
    )


@app.command()
def show(
    ctx: typer.Context,
    project_id: Annotated[str, typer.Argument(help="Project ID (UUID)")],
) -> None:
    """Show project details, milestones, and member issues."""
    actx: AppContext = ctx.obj
    out = actx.output

    data = actx.client.query(PROJECT_SHOW_QUERY, {"id": project_id})
    project = data.get("project", {})

    if out.json_mode:
        out.raw_json(project)
        return

    teams = [t.get("name", "") for t in project.get("teams", {}).get("nodes", [])]
    members = [m.get("name", "") for m in project.get("members", {}).get("nodes", [])]
    milestones = project.get("projectMilestones", {}).get("nodes", [])
    issues = project.get("issues", {}).get("nodes", [])

    sections = [
        (
            "Project",
            [
                ("Name", project.get("name", "")),
                ("State", project.get("state", "")),
                ("Progress", f"{(project.get('progress', 0) or 0) * 100:.0f}%"),
                ("Lead", (project.get("lead") or {}).get("name", "-")),
                ("Start", (project.get("startDate") or "-")[:10]),
                ("Target", (project.get("targetDate") or "-")[:10]),
                ("Teams", ", ".join(teams) if teams else "-"),
                ("Members", ", ".join(members) if members else "-"),
                ("URL", project.get("url", "")),
            ],
        ),
    ]

    if project.get("description"):
        sections.append(("Description", [("", project["description"][:500])]))

    if milestones:
        ms_rows = [(m.get("name", ""), (m.get("targetDate") or "-")[:10]) for m in milestones]
        sections.append(("Milestones", ms_rows))

    out.detail(project.get("name", "Project"), sections)

    if issues:
        rows = [
            [
                i.get("identifier", ""),
                i.get("title", "")[:50],
                i.get("state", {}).get("name", ""),
                (i.get("assignee") or {}).get("name", ""),
            ]
            for i in issues[:20]
        ]
        out.table(
            f"Issues ({len(issues)})",
            [("ID", "cyan"), ("Title", "white"), ("State", "green"), ("Assignee", "magenta")],
            rows,
        )
