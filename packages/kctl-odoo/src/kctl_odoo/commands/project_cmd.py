"""Project & task management commands."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError
from kctl_odoo.core.utils import check_module_installed

app = typer.Typer(help="Project & task management.")


def _safe_count(client: object, model: str, domain: list | None = None) -> int | None:
    """Search count that returns None if model doesn't exist."""
    try:
        return client.search_count(model, domain or [])  # type: ignore[union-attr]
    except RPCError:
        return None


def _resolve_project(client: object, ref: str) -> int:
    """Resolve a project by name or numeric ID, returning the project ID."""
    if ref.isdigit():
        return int(ref)
    projects = client.search_read(  # type: ignore[union-attr]
        "project.project",
        domain=[("name", "ilike", ref)],
        fields=["id", "name"],
        limit=1,
    )
    if not projects:
        raise typer.BadParameter(f"Project not found: {ref}")
    return projects[0]["id"]


@app.command("list")
def list_projects(
    ctx: typer.Context,
    state: Annotated[str | None, typer.Option("--state", "-s", help="Filter: active or archived")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 100,
) -> None:
    """List projects (project.project).

    Examples:
        kctl-odoo project list
        kctl-odoo project list --state archived
        kctl-odoo project list --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not check_module_installed(c, "project"):
        out.error("Module 'project' is not installed.")
        raise typer.Exit(1)

    domain: list = []
    if state == "active":
        domain.append(("active", "=", True))
    elif state == "archived":
        domain.append(("active", "=", False))

    records = c.search_read(
        "project.project",
        domain=domain,
        fields=["id", "name", "user_id", "partner_id", "task_count", "active"],
        limit=limit,
        order="name",
    )

    rows: list[list[str]] = []
    json_data: list[dict] = []
    for r in records:
        user = r.get("user_id")
        user_name = user[1] if isinstance(user, list) else str(user or "-")
        partner = r.get("partner_id")
        partner_name = partner[1] if isinstance(partner, list) else str(partner or "-")
        active_label = "[green]active[/green]" if r.get("active") else "[dim]archived[/dim]"

        rows.append(
            [
                str(r["id"]),
                r.get("name", ""),
                user_name,
                partner_name,
                str(r.get("task_count", 0)),
                active_label,
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "manager": user_name,
                "partner": partner_name,
                "task_count": r.get("task_count", 0),
                "active": r.get("active"),
            }
        )

    out.table(
        f"Projects ({len(records)})",
        [("ID", "cyan"), ("Name", ""), ("Manager", "dim"), ("Partner", "dim"), ("Tasks", ""), ("Status", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def tasks(
    ctx: typer.Context,
    project: Annotated[str, typer.Argument(help="Project name or ID")],
    stage: Annotated[str | None, typer.Option("--stage", help="Filter by stage name")] = None,
    user: Annotated[str | None, typer.Option("--user", help="Filter by assigned user name")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 100,
) -> None:
    """List tasks for a project.

    Examples:
        kctl-odoo project tasks "My Project"
        kctl-odoo project tasks 5 --stage "In Progress"
        kctl-odoo project tasks 5 --user admin --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not check_module_installed(c, "project"):
        out.error("Module 'project' is not installed.")
        raise typer.Exit(1)

    project_id = _resolve_project(c, project)

    domain: list = [("project_id", "=", project_id)]
    if stage:
        domain.append(("stage_id.name", "ilike", stage))
    if user:
        domain.append(("user_ids.name", "ilike", user))

    records = c.search_read(
        "project.task",
        domain=domain,
        fields=["id", "name", "stage_id", "user_ids", "date_deadline", "priority"],
        limit=limit,
        order="priority desc, date_deadline asc",
    )

    rows: list[list[str]] = []
    json_data: list[dict] = []
    for t in records:
        stage_val = t.get("stage_id")
        stage_name = stage_val[1] if isinstance(stage_val, list) else str(stage_val or "-")
        users_ids = t.get("user_ids", [])
        user_label = f"{len(users_ids)} user(s)" if users_ids else "-"
        deadline = str(t.get("date_deadline") or "-")
        prio = t.get("priority", "0")
        prio_label = {"0": "Normal", "1": "[yellow]High[/yellow]"}.get(str(prio), str(prio))

        rows.append([str(t["id"]), t.get("name", ""), stage_name, user_label, deadline, prio_label])
        json_data.append(
            {
                "id": t["id"],
                "name": t.get("name"),
                "stage": stage_name,
                "assignees": len(users_ids),
                "deadline": t.get("date_deadline"),
                "priority": prio,
            }
        )

    out.table(
        f"Tasks for Project #{project_id} ({len(records)})",
        [("ID", "cyan"), ("Name", ""), ("Stage", ""), ("Assignees", "dim"), ("Deadline", "dim"), ("Priority", "")],
        rows,
        data_for_json=json_data,
    )


@app.command("overdue")
def overdue_tasks(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", "-d", help="Days past deadline to flag")] = 7,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 100,
) -> None:
    """Tasks past their deadline.

    Examples:
        kctl-odoo project overdue-tasks
        kctl-odoo project overdue-tasks --days 30
        kctl-odoo project overdue-tasks --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not check_module_installed(c, "project"):
        out.error("Module 'project' is not installed.")
        raise typer.Exit(1)

    now = datetime.now(tz=UTC)
    (now - timedelta(days=days)).strftime("%Y-%m-%d")

    domain: list = [
        ("date_deadline", "!=", False),
        ("date_deadline", "<", now.strftime("%Y-%m-%d")),
        ("stage_id.fold", "=", False),  # exclude done/folded stages
    ]

    records = c.search_read(
        "project.task",
        domain=domain,
        fields=["id", "name", "project_id", "stage_id", "user_ids", "date_deadline"],
        limit=limit,
        order="date_deadline asc",
    )

    rows: list[list[str]] = []
    json_data: list[dict] = []
    for t in records:
        proj = t.get("project_id")
        proj_name = proj[1] if isinstance(proj, list) else str(proj or "-")
        stage_val = t.get("stage_id")
        stage_name = stage_val[1] if isinstance(stage_val, list) else str(stage_val or "-")
        deadline = str(t.get("date_deadline") or "-")
        # Calculate overdue days
        if t.get("date_deadline"):
            try:
                dl = datetime.strptime(str(t["date_deadline"]), "%Y-%m-%d")
                overdue_days = (now.replace(tzinfo=None) - dl).days
                overdue_label = f"[red]{overdue_days}d[/red]"
            except ValueError:
                overdue_label = "-"
        else:
            overdue_label = "-"

        rows.append([str(t["id"]), t.get("name", ""), proj_name, stage_name, deadline, overdue_label])
        json_data.append(
            {
                "id": t["id"],
                "name": t.get("name"),
                "project": proj_name,
                "stage": stage_name,
                "deadline": t.get("date_deadline"),
            }
        )

    out.table(
        f"Overdue Tasks ({len(records)})",
        [("ID", "cyan"), ("Name", ""), ("Project", "dim"), ("Stage", ""), ("Deadline", "dim"), ("Overdue", "red")],
        rows,
        data_for_json=json_data,
    )


@app.command("timesheets")
def timesheet_summary(
    ctx: typer.Context,
    user: Annotated[str | None, typer.Option("--user", help="Filter by employee/user name")] = None,
    period: Annotated[str, typer.Option("--period", help="Period: month, quarter, year")] = "month",
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 100,
) -> None:
    """Timesheet hours summary (account.analytic.line).

    Examples:
        kctl-odoo project timesheet-summary
        kctl-odoo project timesheet-summary --user "John" --period quarter
        kctl-odoo project timesheet-summary --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    ts_count = _safe_count(c, "account.analytic.line", [("project_id", "!=", False)])
    if ts_count is None:
        out.error("Timesheet (account.analytic.line) not accessible. Is the 'project' module installed?")
        raise typer.Exit(1)

    now = datetime.now(tz=UTC)
    if period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "quarter":
        q_month = ((now.month - 1) // 3) * 3 + 1
        start = now.replace(month=q_month, day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "year":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    domain: list = [
        ("project_id", "!=", False),
        ("date", ">=", start.strftime("%Y-%m-%d")),
    ]
    if user:
        domain.append(("user_id.name", "ilike", user))

    records = c.search_read(
        "account.analytic.line",
        domain=domain,
        fields=["employee_id", "project_id", "unit_amount"],
        limit=5000,
    )

    # Aggregate by employee
    by_employee: dict[str, float] = {}
    by_project: dict[str, float] = {}
    for r in records:
        emp = r.get("employee_id")
        emp_name = emp[1] if isinstance(emp, list) else str(emp or "Unknown")
        proj = r.get("project_id")
        proj_name = proj[1] if isinstance(proj, list) else str(proj or "Unknown")
        hours = r.get("unit_amount", 0.0)
        by_employee[emp_name] = by_employee.get(emp_name, 0.0) + hours
        by_project[proj_name] = by_project.get(proj_name, 0.0) + hours

    total_hours = sum(by_employee.values())

    rows: list[list[str]] = []
    json_data: list[dict] = []
    for emp_name, hours in sorted(by_employee.items(), key=lambda x: -x[1])[:limit]:
        rows.append([emp_name, f"{hours:.1f}"])
        json_data.append({"employee": emp_name, "hours": round(hours, 1)})

    rows.append(["[bold]Total[/bold]", f"[bold]{total_hours:.1f}[/bold]"])

    out.table(
        f"Timesheet Summary ({period}) — {total_hours:.1f}h total",
        [("Employee", ""), ("Hours", "cyan")],
        rows,
        data_for_json=json_data,
    )
