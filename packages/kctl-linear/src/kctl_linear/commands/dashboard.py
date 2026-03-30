"""Dashboard — quick overview of my issues, current cycle, active projects."""

from __future__ import annotations

import typer

from kctl_linear.core.callbacks import AppContext
from kctl_linear.core.client import DASHBOARD_QUERY

app = typer.Typer(help="Quick overview dashboard.")


@app.callback(invoke_without_command=True)
def dashboard(ctx: typer.Context) -> None:
    """Show my issues, current cycle progress, and active projects."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    variables: dict[str, str | None] = {"teamKey": actx.default_team}
    data = client.query(DASHBOARD_QUERY, variables)

    viewer = data.get("viewer", {})
    my_issues = viewer.get("assignedIssues", {}).get("nodes", [])
    cycles = data.get("cycles", {}).get("nodes", [])
    projects = data.get("projects", {}).get("nodes", [])

    if out.json_mode:
        out.raw_json(
            {
                "viewer": {"name": viewer.get("name"), "email": viewer.get("email")},
                "my_issues": my_issues,
                "current_cycle": cycles[0] if cycles else None,
                "active_projects": projects,
            }
        )
        return

    # My issues
    out.header(f"My Issues ({len(my_issues)})")
    if my_issues:
        rows = [
            [
                issue.get("identifier", ""),
                issue.get("title", "")[:60],
                str(issue.get("priority", "")),
                issue.get("state", {}).get("name", ""),
            ]
            for issue in my_issues
        ]
        out.table(
            "",
            [("ID", "cyan"), ("Title", "white"), ("Priority", "yellow"), ("State", "green")],
            rows,
        )
    else:
        out.info("No active issues assigned to you")

    # Current cycle
    if cycles:
        cycle = cycles[0]
        progress = cycle.get("progress", 0)
        progress_pct = f"{progress * 100:.0f}%" if isinstance(progress, (int, float)) else str(progress)
        out.header("Current Cycle")
        out.kv("Name", cycle.get("name") or f"Cycle {cycle.get('number', '?')}")
        out.kv("Progress", progress_pct)
        out.kv("Starts", cycle.get("startsAt", "")[:10])
        out.kv("Ends", cycle.get("endsAt", "")[:10])
    else:
        out.header("Current Cycle")
        out.info("No active cycle")

    # Active projects
    if projects:
        out.header(f"Active Projects ({len(projects)})")
        rows = [
            [
                proj.get("name", ""),
                f"{(proj.get('progress', 0) or 0) * 100:.0f}%",
                (proj.get("targetDate") or "")[:10],
            ]
            for proj in projects
        ]
        out.table("", [("Name", "cyan"), ("Progress", "green"), ("Target", "yellow")], rows)
