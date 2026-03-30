"""HR commands — employees, departments, attendance, leaves, payroll, expenses."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Optional

import typer

from kctl_odoo.core.biz_helpers import model_available, module_hint
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError
from kctl_odoo.core.field_helpers import safe_fields
from kctl_odoo.core.utils import check_module_installed

app = typer.Typer(help="HR: employees, departments, attendance, leaves, payroll, expenses.")


def _safe_count(client: object, model: str, domain: list | None = None) -> int | None:
    """Search count that returns None if model doesn't exist."""
    try:
        return client.search_count(model, domain or [])  # type: ignore[union-attr]
    except RPCError:
        return None


def _m2o_name(val: object) -> str:
    """Extract display name from an M2O field value ([id, name] or False)."""
    if isinstance(val, list):
        return str(val[1])
    return str(val or "")


def _resolve(c: object, model: str, field: str, value: str, label: str) -> tuple[int, str]:
    """Resolve a record by numeric ID or name search.

    Returns (id, display_name).  Raises ``typer.BadParameter`` when not found.
    """
    if value.isdigit():
        recs = c.read(model, [int(value)], ["id", "display_name"])  # type: ignore[attr-defined]
    else:
        recs = c.search_read(  # type: ignore[attr-defined]
            model, [(field, "ilike", value)], ["id", "display_name"], limit=1
        )
    if not recs:
        raise typer.BadParameter(f"{label} not found: {value}")
    return recs[0]["id"], recs[0].get("display_name", str(recs[0]["id"]))


def _fmt_amount(amount: float) -> str:
    """Format a monetary amount with thousands separator."""
    if amount >= 0:
        return f"{amount:,.2f}"
    return f"-{abs(amount):,.2f}"


def _require_hr(client: object, out: object) -> None:
    """Check that HR module is installed, exit if not."""
    if not check_module_installed(client, "hr"):
        out.error("Module 'hr' is not installed.")  # type: ignore[union-attr]
        raise typer.Exit(1)


@app.command()
def employees(
    ctx: typer.Context,
    department: Annotated[str | None, typer.Option("--department", "-d", help="Filter by department name")] = None,
    active: Annotated[bool, typer.Option("--active/--all", help="Show only active employees")] = True,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 200,
) -> None:
    """Employee directory (hr.employee).

    Examples:
        kctl-odoo hr employees
        kctl-odoo hr employees --department Sales
        kctl-odoo hr employees --all --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _require_hr(c, out)

    domain: list = []
    if active:
        domain.append(("active", "=", True))
    if department:
        domain.append(("department_id.name", "ilike", department))

    records = c.search_read(
        "hr.employee",
        domain=domain,
        fields=["id", "name", "job_title", "department_id", "work_email", "active"],
        limit=limit,
        order="name",
    )

    rows: list[list[str]] = []
    json_data: list[dict] = []
    for r in records:
        dept = r.get("department_id")
        dept_name = dept[1] if isinstance(dept, list) else str(dept or "-")
        status = "[green]active[/green]" if r.get("active") else "[dim]inactive[/dim]"
        rows.append(
            [
                str(r["id"]),
                r.get("name", ""),
                r.get("job_title") or "-",
                dept_name,
                r.get("work_email") or "-",
                status,
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "job_title": r.get("job_title"),
                "department": dept_name,
                "work_email": r.get("work_email"),
                "active": r.get("active"),
            }
        )

    out.table(
        f"Employees ({len(records)})",
        [("ID", "cyan"), ("Name", ""), ("Job Title", ""), ("Department", "dim"), ("Email", "dim"), ("Status", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def departments(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 100,
) -> None:
    """Department list (hr.department).

    Examples:
        kctl-odoo hr departments
        kctl-odoo hr departments --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _require_hr(c, out)

    records = c.search_read(
        "hr.department",
        domain=[],
        fields=["id", "name", "manager_id", "parent_id", "total_employee"],
        limit=limit,
        order="name",
    )

    rows: list[list[str]] = []
    json_data: list[dict] = []
    for r in records:
        mgr = r.get("manager_id")
        mgr_name = mgr[1] if isinstance(mgr, list) else str(mgr or "-")
        parent = r.get("parent_id")
        parent_name = parent[1] if isinstance(parent, list) else str(parent or "-")
        rows.append(
            [
                str(r["id"]),
                r.get("name", ""),
                mgr_name,
                parent_name,
                str(r.get("total_employee", 0)),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "manager": mgr_name,
                "parent": parent_name,
                "employees": r.get("total_employee", 0),
            }
        )

    out.table(
        f"Departments ({len(records)})",
        [("ID", "cyan"), ("Name", ""), ("Manager", "dim"), ("Parent", "dim"), ("Employees", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def contracts(
    ctx: typer.Context,
    state: Annotated[str | None, typer.Option("--state", "-s", help="Filter: open, close, draft, cancel")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 100,
) -> None:
    """Contract status (hr.contract).

    Examples:
        kctl-odoo hr contracts
        kctl-odoo hr contracts --state open
        kctl-odoo hr contracts --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _require_hr(c, out)

    if not check_module_installed(c, "hr_contract"):
        out.error("Module 'hr_contract' is not installed.")
        raise typer.Exit(1)

    domain: list = []
    if state:
        domain.append(("state", "=", state))

    records = c.search_read(
        "hr.contract",
        domain=domain,
        fields=["id", "name", "employee_id", "state", "date_start", "date_end", "wage"],
        limit=limit,
        order="employee_id",
    )

    state_labels = {"draft": "New", "open": "Running", "close": "Expired", "cancel": "Cancelled"}
    rows: list[list[str]] = []
    json_data: list[dict] = []
    for r in records:
        emp = r.get("employee_id")
        emp_name = emp[1] if isinstance(emp, list) else str(emp or "-")
        st = r.get("state", "")
        st_label = state_labels.get(st, st)
        color = {"open": "green", "draft": "yellow", "close": "dim", "cancel": "red"}.get(st, "")
        st_display = f"[{color}]{st_label}[/{color}]" if color else st_label

        rows.append(
            [
                str(r["id"]),
                r.get("name", ""),
                emp_name,
                st_display,
                str(r.get("date_start") or "-"),
                str(r.get("date_end") or "-"),
                f"{r.get('wage', 0):,.0f}",
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "employee": emp_name,
                "state": st,
                "date_start": r.get("date_start"),
                "date_end": r.get("date_end"),
                "wage": r.get("wage"),
            }
        )

    out.table(
        f"Contracts ({len(records)})",
        [("ID", "cyan"), ("Name", ""), ("Employee", ""), ("State", ""), ("Start", "dim"), ("End", "dim"), ("Wage", "")],
        rows,
        data_for_json=json_data,
    )


@app.command("attendance-today")
def attendance_today(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 200,
) -> None:
    """Who's checked in today (hr.attendance).

    Examples:
        kctl-odoo hr attendance-today
        kctl-odoo hr attendance-today --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _require_hr(c, out)

    attn_count = _safe_count(c, "hr.attendance", [])
    if attn_count is None:
        out.error("Module 'hr_attendance' is not installed.")
        raise typer.Exit(1)

    today_str = datetime.now(tz=UTC).strftime("%Y-%m-%d 00:00:00")

    records = c.search_read(
        "hr.attendance",
        domain=[("check_in", ">=", today_str)],
        fields=["id", "employee_id", "check_in", "check_out", "worked_hours"],
        limit=limit,
        order="check_in desc",
    )

    rows: list[list[str]] = []
    json_data: list[dict] = []
    for r in records:
        emp = r.get("employee_id")
        emp_name = emp[1] if isinstance(emp, list) else str(emp or "-")
        check_in = str(r.get("check_in") or "-")
        check_out = str(r.get("check_out") or "[yellow]still in[/yellow]")
        hours = r.get("worked_hours", 0)
        hours_str = f"{hours:.1f}h" if hours else "-"

        rows.append([str(r["id"]), emp_name, check_in, check_out, hours_str])
        json_data.append(
            {
                "id": r["id"],
                "employee": emp_name,
                "check_in": r.get("check_in"),
                "check_out": r.get("check_out"),
                "worked_hours": hours,
            }
        )

    checked_in = sum(1 for r in records if not r.get("check_out"))
    out.table(
        f"Attendance Today ({len(records)} records, {checked_in} still checked in)",
        [("ID", "cyan"), ("Employee", ""), ("Check In", "dim"), ("Check Out", "dim"), ("Hours", "")],
        rows,
        data_for_json=json_data,
    )


@app.command("leave-balance")
def leave_balance(
    ctx: typer.Context,
    employee: Annotated[str | None, typer.Option("--employee", "-e", help="Employee name")] = None,
    leave_type: Annotated[str | None, typer.Option("--type", "-t", help="Leave type name")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 200,
) -> None:
    """Leave balances (hr.leave.allocation).

    Examples:
        kctl-odoo hr leave-balance
        kctl-odoo hr leave-balance --employee "John"
        kctl-odoo hr leave-balance --type "Annual Leave" --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _require_hr(c, out)

    alloc_count = _safe_count(c, "hr.leave.allocation", [])
    if alloc_count is None:
        out.error("Module 'hr_holidays' is not installed.")
        raise typer.Exit(1)

    domain: list = [("state", "=", "validate")]
    if employee:
        domain.append(("employee_id.name", "ilike", employee))
    if leave_type:
        domain.append(("holiday_status_id.name", "ilike", leave_type))

    records = c.search_read(
        "hr.leave.allocation",
        domain=domain,
        fields=["id", "employee_id", "holiday_status_id", "number_of_days", "leaves_taken"],
        limit=limit,
        order="employee_id",
    )

    rows: list[list[str]] = []
    json_data: list[dict] = []
    for r in records:
        emp = r.get("employee_id")
        emp_name = emp[1] if isinstance(emp, list) else str(emp or "-")
        lt = r.get("holiday_status_id")
        lt_name = lt[1] if isinstance(lt, list) else str(lt or "-")
        allocated = r.get("number_of_days", 0)
        taken = r.get("leaves_taken", 0)
        remaining = allocated - taken

        remaining_color = "red" if remaining <= 0 else "green"
        rows.append(
            [
                str(r["id"]),
                emp_name,
                lt_name,
                f"{allocated:.1f}",
                f"{taken:.1f}",
                f"[{remaining_color}]{remaining:.1f}[/{remaining_color}]",
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "employee": emp_name,
                "leave_type": lt_name,
                "allocated": allocated,
                "taken": taken,
                "remaining": remaining,
            }
        )

    out.table(
        f"Leave Balances ({len(records)})",
        [("ID", "cyan"), ("Employee", ""), ("Type", ""), ("Allocated", ""), ("Taken", ""), ("Remaining", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def birthdays(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", "-d", help="Look ahead N days")] = 30,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 100,
) -> None:
    """Upcoming employee birthdays.

    Examples:
        kctl-odoo hr birthdays
        kctl-odoo hr birthdays --days 7
        kctl-odoo hr birthdays --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _require_hr(c, out)

    # Fetch all active employees with birthdays
    records = c.search_read(
        "hr.employee",
        domain=[("active", "=", True), ("birthday", "!=", False)],
        fields=["id", "name", "department_id", "birthday"],
        limit=2000,
        order="name",
    )

    now = datetime.now(tz=UTC)
    upcoming: list[dict] = []
    for r in records:
        bday_str = r.get("birthday")
        if not bday_str:
            continue
        try:
            bday = datetime.strptime(str(bday_str), "%Y-%m-%d")
            # This year's birthday
            this_year_bday = bday.replace(year=now.year)
            if this_year_bday.date() < now.date():
                this_year_bday = bday.replace(year=now.year + 1)
            delta = (this_year_bday.date() - now.date()).days
            if 0 <= delta <= days:
                r["_days_until"] = delta
                r["_this_bday"] = this_year_bday.strftime("%Y-%m-%d")
                upcoming.append(r)
        except ValueError:
            continue

    upcoming.sort(key=lambda x: x["_days_until"])
    upcoming = upcoming[:limit]

    rows: list[list[str]] = []
    json_data: list[dict] = []
    for r in upcoming:
        dept = r.get("department_id")
        dept_name = dept[1] if isinstance(dept, list) else str(dept or "-")
        days_until = r["_days_until"]
        if days_until == 0:
            days_label = "[green]TODAY[/green]"
        elif days_until <= 7:
            days_label = f"[yellow]{days_until}d[/yellow]"
        else:
            days_label = f"{days_until}d"

        rows.append([str(r["id"]), r.get("name", ""), dept_name, r["_this_bday"], days_label])
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "department": dept_name,
                "birthday": r.get("birthday"),
                "days_until": days_until,
            }
        )

    out.table(
        f"Upcoming Birthdays ({len(upcoming)} in next {days} days)",
        [("ID", "cyan"), ("Name", ""), ("Department", "dim"), ("Date", ""), ("In", "")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# LEAVE REQUEST — CREATE
# ===================================================================


@app.command("request-leave")
def leave_request(
    ctx: typer.Context,
    employee: Annotated[str, typer.Option("--employee", help="Employee name or ID")],
    leave_type: Annotated[str, typer.Option("--type", help="Leave type name (e.g. 'Annual Leave')")],
    date_from: Annotated[str, typer.Option("--date-from", help="Start date (YYYY-MM-DD)")],
    date_to: Annotated[str, typer.Option("--date-to", help="End date (YYYY-MM-DD)")],
    reason: Annotated[str | None, typer.Option("--reason", help="Leave reason / description")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without creating")] = False,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Create a leave request (hr.leave).

    Resolves employee and leave type by name or numeric ID.

    Examples:
        kctl-odoo hr request-leave --employee "John" --type "Annual Leave" --date-from 2026-04-01 --date-to 2026-04-05
        kctl-odoo hr request-leave --employee 15 --type "Sick Leave" --date-from 2026-04-01 --date-to 2026-04-01 --force
        kctl-odoo hr request-leave --employee "Jane" --type "Annual Leave" \\
            --date-from 2026-05-01 --date-to 2026-05-03 --dry-run
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _require_hr(c, out)

    try:
        emp_id, emp_display = _resolve(c, "hr.employee", "name", employee, "Employee")
        lt_id, lt_display = _resolve(c, "hr.leave.type", "name", leave_type, "Leave type")
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    vals = {
        "employee_id": emp_id,
        "holiday_status_id": lt_id,
        "date_from": f"{date_from} 00:00:00",
        "date_to": f"{date_to} 23:59:59",
    }
    if reason:
        vals["name"] = reason

    summary = {
        "employee": emp_display,
        "leave_type": lt_display,
        "date_from": date_from,
        "date_to": date_to,
        "reason": reason or "",
    }

    if dry_run:
        out.info("Dry run — leave request will NOT be created.")
        out.detail(
            "Leave Request Preview",
            [
                (
                    "Leave Request",
                    [
                        ("Employee", emp_display),
                        ("Leave Type", lt_display),
                        ("From", date_from),
                        ("To", date_to),
                        ("Reason", reason or "-"),
                    ],
                )
            ],
            data_for_json=summary,
        )
        return

    if not force:
        out.info(f"Create leave: employee={emp_display}, type={lt_display}, {date_from} to {date_to}")
        if not typer.confirm("Create this leave request?"):
            raise typer.Exit(0)

    try:
        leave_id = c.create("hr.leave", vals)
    except RPCError as e:
        out.error(f"Failed to create leave request: {e}")
        raise typer.Exit(1) from e

    out.success(f"Created leave request id={leave_id} for {emp_display}")

    if actx.json_mode:
        out.raw_json({"id": leave_id, **summary})


# ===================================================================
# LEAVE APPROVE
# ===================================================================


@app.command("approve-leave")
def leave_approve(
    ctx: typer.Context,
    leave_id: Annotated[int, typer.Argument(help="Leave request ID to approve")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Approve a leave request by ID.

    Calls ``action_approve`` on the ``hr.leave`` record.

    Examples:
        kctl-odoo hr leave-approve 42 --force
        kctl-odoo hr leave-approve 42
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _require_hr(c, out)

    if not force and not typer.confirm(f"Approve leave request id={leave_id}?"):
        raise typer.Exit(0)

    try:
        c.execute_kw("hr.leave", "action_approve", [[leave_id]])
    except RPCError as e:
        out.error(f"Failed to approve leave {leave_id}: {e}")
        raise typer.Exit(1) from e

    out.success(f"Approved leave request id={leave_id}")

    if actx.json_mode:
        out.raw_json({"id": leave_id, "action": "approved"})


# ===================================================================
# LEAVE REFUSE
# ===================================================================


@app.command("refuse-leave")
def leave_refuse(
    ctx: typer.Context,
    leave_id: Annotated[int, typer.Argument(help="Leave request ID to refuse")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Refuse a leave request by ID.

    Calls ``action_refuse`` on the ``hr.leave`` record.

    Examples:
        kctl-odoo hr leave-refuse 42 --force
        kctl-odoo hr leave-refuse 42
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _require_hr(c, out)

    if not force and not typer.confirm(f"Refuse leave request id={leave_id}?"):
        raise typer.Exit(0)

    try:
        c.execute_kw("hr.leave", "action_refuse", [[leave_id]])
    except RPCError as e:
        out.error(f"Failed to refuse leave {leave_id}: {e}")
        raise typer.Exit(1) from e

    out.success(f"Refused leave request id={leave_id}")

    if actx.json_mode:
        out.raw_json({"id": leave_id, "action": "refused"})


# ===================================================================
# LIST LEAVES
# ===================================================================


@app.command("leaves")
def leaves(
    ctx: typer.Context,
    state: Annotated[
        str | None, typer.Option("--state", "-s", help="Filter by state: draft, confirm, validate, refuse")
    ] = None,
    employee: Annotated[str | None, typer.Option("--employee", "-e", help="Filter by employee name")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List leave requests (hr.leave).

    Examples:
        kctl-odoo hr leaves
        kctl-odoo hr leaves --state confirm
        kctl-odoo hr leaves --employee "John" --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _require_hr(c, out)

    domain: list = []
    if state:
        domain.append(("state", "=", state))
    if employee:
        domain.append(("employee_id.name", "ilike", employee))

    try:
        records = c.search_read(
            "hr.leave",
            domain=domain,
            fields=["id", "employee_id", "holiday_status_id", "date_from", "date_to", "number_of_days", "state"],
            limit=limit,
            order="date_from desc",
        )
    except RPCError as e:
        out.error(f"Failed to list leave requests: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No leave requests found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows: list[list[str]] = []
    json_data: list[dict] = []
    for r in records:
        rows.append(
            [
                str(r["id"]),
                _m2o_name(r.get("employee_id")),
                _m2o_name(r.get("holiday_status_id")),
                str(r.get("date_from", "")),
                str(r.get("date_to", "")),
                str(r.get("number_of_days", 0)),
                r.get("state", ""),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "employee": _m2o_name(r.get("employee_id")),
                "leave_type": _m2o_name(r.get("holiday_status_id")),
                "date_from": r.get("date_from"),
                "date_to": r.get("date_to"),
                "number_of_days": r.get("number_of_days", 0),
                "state": r.get("state"),
            }
        )

    out.table(
        f"Leave Requests ({len(records)})",
        [
            ("ID", "cyan"),
            ("Employee", ""),
            ("Leave Type", ""),
            ("From", "dim"),
            ("To", "dim"),
            ("Days", ""),
            ("State", ""),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# GET EMPLOYEE DETAIL
# ===================================================================


@app.command("get-employee")
def get_employee(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Employee name (partial match) or numeric ID")],
) -> None:
    """Get employee details by name or ID.

    Examples:
        kctl-odoo hr get-employee "John"
        kctl-odoo hr get-employee 15
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _require_hr(c, out)

    try:
        emp_id, _ = _resolve(c, "hr.employee", "name", identifier, "Employee")
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    fields = safe_fields(
        c,
        "hr.employee",
        [
            "name",
            "job_id",
            "job_title",
            "department_id",
            "work_email",
            "work_phone",
            "coach_id",
            "parent_id",
            "company_id",
            "identification_id",
            "active",
        ],
    )

    try:
        records = c.read("hr.employee", [emp_id], fields)
    except RPCError as e:
        out.error(f"Failed to fetch employee {emp_id}: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.error(f"Employee not found: {identifier}")
        raise typer.Exit(1)

    rec = records[0]
    fields_list = [
        ("Name", rec.get("name", "")),
        ("Job Position", _m2o_name(rec.get("job_id"))),
        ("Job Title", str(rec.get("job_title") or "")),
        ("Department", _m2o_name(rec.get("department_id"))),
        ("Email", str(rec.get("work_email") or "")),
        ("Phone", str(rec.get("work_phone") or "")),
        ("Manager", _m2o_name(rec.get("parent_id"))),
        ("Coach", _m2o_name(rec.get("coach_id"))),
        ("Company", _m2o_name(rec.get("company_id"))),
        ("ID Number", str(rec.get("identification_id") or "")),
        ("Active", "Yes" if rec.get("active") else "No"),
    ]

    json_result = {
        "id": emp_id,
        "name": rec.get("name"),
        "job": _m2o_name(rec.get("job_id")),
        "job_title": rec.get("job_title"),
        "department": _m2o_name(rec.get("department_id")),
        "work_email": rec.get("work_email"),
        "work_phone": rec.get("work_phone"),
        "manager": _m2o_name(rec.get("parent_id")),
        "coach": _m2o_name(rec.get("coach_id")),
        "company": _m2o_name(rec.get("company_id")),
        "identification_id": rec.get("identification_id"),
        "active": rec.get("active"),
    }

    out.detail(
        "Employee Detail",
        [("Employee", fields_list)],
        data_for_json=json_result,
    )


# ===================================================================
# ATTENDANCE REPORT
# ===================================================================


@app.command("attendance-report")
def attendance_report(
    ctx: typer.Context,
    date_from: Annotated[Optional[str], typer.Option("--date-from", help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[Optional[str], typer.Option("--date-to", help="End date (YYYY-MM-DD)")] = None,
    employee: Annotated[Optional[str], typer.Option("--employee", "-e", help="Filter by employee name")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """Attendance report for a date range.

    Examples:
        kctl-odoo hr attendance-report --date-from 2026-03-01 --date-to 2026-03-31
        kctl-odoo hr attendance-report --employee "John"
        kctl-odoo hr attendance-report --date-from 2026-03-01 --employee "John" --limit 100
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _require_hr(c, out)

    if not model_available(c, "hr.attendance"):
        out.warn("Attendance module (hr_attendance) is not installed.")
        return

    domain: list = []
    if date_from:
        domain.append(("check_in", ">=", f"{date_from} 00:00:00"))
    if date_to:
        domain.append(("check_in", "<=", f"{date_to} 23:59:59"))
    if employee:
        domain.append(("employee_id.name", "ilike", employee))

    fields = safe_fields(
        c,
        "hr.attendance",
        ["employee_id", "check_in", "check_out", "worked_hours"],
    )

    try:
        records = c.search_read(
            "hr.attendance",
            domain=domain,
            fields=fields,
            limit=limit,
            order="check_in desc",
        )
    except RPCError as e:
        out.error(f"Failed to fetch attendance: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No attendance records found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows: list[list[str]] = []
    json_data: list[dict] = []
    for r in records:
        emp_name = _m2o_name(r.get("employee_id"))
        check_in = str(r.get("check_in", ""))
        check_out = str(r.get("check_out", ""))
        worked = r.get("worked_hours", 0.0)
        rows.append([emp_name, check_in, check_out, f"{worked:.2f}"])
        json_data.append(
            {
                "employee": emp_name,
                "check_in": r.get("check_in"),
                "check_out": r.get("check_out"),
                "worked_hours": worked,
            }
        )

    title_parts = ["Attendance Report"]
    if date_from or date_to:
        title_parts.append(f"({date_from or '...'} → {date_to or '...'})")
    if employee:
        title_parts.append(f"[{employee}]")
    title_parts.append(f"({len(records)} records)")

    out.table(
        " ".join(title_parts),
        [
            ("Employee", "cyan"),
            ("Check In", ""),
            ("Check Out", ""),
            ("Hours", "green"),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# GET PAYSLIP DETAIL
# ===================================================================


@app.command("get-payslip")
def get_payslip(
    ctx: typer.Context,
    payslip_id: Annotated[int, typer.Argument(help="Payslip ID")],
) -> None:
    """Get payslip detail by ID.

    Shows payslip header and salary computation lines.

    Examples:
        kctl-odoo hr get-payslip 1
        kctl-odoo hr get-payslip 42
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _require_hr(c, out)

    if not model_available(c, "hr.payslip"):
        out.warn("Payroll module (hr_payroll) is not installed.")
        return

    header_fields = safe_fields(
        c,
        "hr.payslip",
        [
            "name",
            "employee_id",
            "date_from",
            "date_to",
            "state",
            "struct_id",
            "company_id",
            "number",
        ],
    )

    try:
        records = c.read("hr.payslip", [payslip_id], header_fields)
    except RPCError as e:
        out.error(f"Failed to fetch payslip {payslip_id}: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.error(f"Payslip not found: {payslip_id}")
        raise typer.Exit(1)

    rec = records[0]

    header_sections = [
        (
            "Payslip",
            [
                ("ID", str(rec["id"])),
                ("Reference", str(rec.get("number") or "")),
                ("Name", str(rec.get("name") or "")),
                ("Employee", _m2o_name(rec.get("employee_id"))),
                ("Period", f"{rec.get('date_from', '')} to {rec.get('date_to', '')}"),
                ("Structure", _m2o_name(rec.get("struct_id"))),
                ("Company", _m2o_name(rec.get("company_id"))),
                ("State", str(rec.get("state") or "")),
            ],
        )
    ]

    json_result: dict = {
        "id": rec["id"],
        "number": rec.get("number"),
        "name": rec.get("name"),
        "employee": _m2o_name(rec.get("employee_id")),
        "date_from": rec.get("date_from"),
        "date_to": rec.get("date_to"),
        "struct": _m2o_name(rec.get("struct_id")),
        "company": _m2o_name(rec.get("company_id")),
        "state": rec.get("state"),
        "lines": [],
    }

    out.detail("Payslip Detail", header_sections, data_for_json=json_result)

    # Salary lines
    try:
        line_ids = c.search("hr.payslip.line", [("slip_id", "=", payslip_id)])
        if line_ids:
            line_fields = safe_fields(
                c,
                "hr.payslip.line",
                ["name", "code", "category_id", "quantity", "amount", "total"],
            )
            lines = c.read("hr.payslip.line", line_ids, line_fields)

            rows: list[list[str]] = []
            lines_json: list[dict] = []
            for ln in lines:
                rows.append(
                    [
                        str(ln.get("code", "")),
                        str(ln.get("name", "")),
                        _m2o_name(ln.get("category_id")),
                        f"{ln.get('quantity', 0):.2f}",
                        f"{ln.get('amount', 0):,.2f}",
                        f"{ln.get('total', 0):,.2f}",
                    ]
                )
                lines_json.append(
                    {
                        "code": ln.get("code"),
                        "name": ln.get("name"),
                        "category": _m2o_name(ln.get("category_id")),
                        "quantity": ln.get("quantity", 0),
                        "amount": ln.get("amount", 0),
                        "total": ln.get("total", 0),
                    }
                )

            json_result["lines"] = lines_json

            out.table(
                "Salary Lines",
                [
                    ("Code", "dim"),
                    ("Name", ""),
                    ("Category", "dim"),
                    ("Qty", ""),
                    ("Amount", ""),
                    ("Total", "cyan"),
                ],
                rows,
                data_for_json=lines_json,
            )
    except RPCError as e:
        out.warn(f"Failed to read payslip lines: {e}")


# ===================================================================
# LEAVE SUMMARY BY DEPARTMENT
# ===================================================================


@app.command("leave-summary")
def leave_summary(
    ctx: typer.Context,
    department: Annotated[Optional[str], typer.Option("--department", "-d", help="Filter by department name")] = None,
) -> None:
    """Leave summary by department — approved leaves count and total days.

    Examples:
        kctl-odoo hr leave-summary
        kctl-odoo hr leave-summary --department "Sales"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _require_hr(c, out)

    domain: list = [("state", "=", "validate")]
    if department:
        domain.append(("department_id.name", "ilike", department))

    try:
        records = c.search_read(
            "hr.leave",
            domain=domain,
            fields=["employee_id", "department_id", "number_of_days"],
            limit=0,  # fetch all
        )
    except RPCError as e:
        out.error(f"Failed to fetch leave data: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No approved leaves found.")
        if actx.json_mode:
            out.raw_json([])
        return

    # Aggregate by department
    dept_data: dict[str, dict] = {}
    for r in records:
        dept = r.get("department_id")
        if isinstance(dept, list):
            dept_key = dept[1]
        elif dept:
            dept_key = str(dept)
        else:
            dept_key = "(No Department)"

        if dept_key not in dept_data:
            dept_data[dept_key] = {"count": 0, "total_days": 0.0}

        dept_data[dept_key]["count"] += 1
        dept_data[dept_key]["total_days"] += r.get("number_of_days", 0.0)

    # Sort by department name
    sorted_depts = sorted(dept_data.items(), key=lambda x: x[0])

    rows: list[list[str]] = []
    json_data: list[dict] = []
    total_count = 0
    total_days = 0.0

    for dept_name, data in sorted_depts:
        count = data["count"]
        days_sum = data["total_days"]
        total_count += count
        total_days += days_sum
        rows.append([dept_name, str(count), f"{days_sum:.1f}"])
        json_data.append({"department": dept_name, "approved_leaves": count, "total_days": days_sum})

    rows.append(["[bold]TOTAL[/bold]", f"[bold]{total_count}[/bold]", f"[bold]{total_days:.1f}[/bold]"])

    title = "Leave Summary by Department"
    if department:
        title += f" [{department}]"

    out.table(
        title,
        [
            ("Department", "cyan"),
            ("Approved Leaves", ""),
            ("Total Days", "green"),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# LIST PAYSLIPS
# ===================================================================


@app.command("payslips")
def payslips(
    ctx: typer.Context,
    state: Annotated[str | None, typer.Option("--state", "-s", help="Filter by state: draft, done, paid")] = None,
    employee: Annotated[str | None, typer.Option("--employee", "-e", help="Filter by employee name")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List payslips (hr.payslip).

    Requires the ``hr_payroll`` module to be installed.

    Examples:
        kctl-odoo hr payslips
        kctl-odoo hr payslips --state done --employee "John"
        kctl-odoo hr payslips --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not check_module_installed(c, "hr_payroll"):
        out.info("Module 'hr_payroll' is not installed — skipping payslips.")
        if actx.json_mode:
            out.raw_json([])
        return

    domain: list = []
    if state:
        domain.append(("state", "=", state))
    if employee:
        domain.append(("employee_id.name", "ilike", employee))

    try:
        records = c.search_read(
            "hr.payslip",
            domain=domain,
            fields=["id", "number", "employee_id", "date_from", "date_to", "net_wage", "state"],
            limit=limit,
            order="date_from desc",
        )
    except RPCError as e:
        out.error(f"Failed to list payslips: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No payslips found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows: list[list[str]] = []
    json_data: list[dict] = []
    for r in records:
        rows.append(
            [
                str(r.get("number") or r["id"]),
                _m2o_name(r.get("employee_id")),
                str(r.get("date_from", "")),
                str(r.get("date_to", "")),
                _fmt_amount(r.get("net_wage", 0)),
                r.get("state", ""),
            ]
        )
        json_data.append(
            {
                "number": r.get("number"),
                "employee": _m2o_name(r.get("employee_id")),
                "date_from": r.get("date_from"),
                "date_to": r.get("date_to"),
                "net_wage": r.get("net_wage", 0),
                "state": r.get("state"),
            }
        )

    out.table(
        f"Payslips ({len(records)})",
        [
            ("Number", "cyan"),
            ("Employee", ""),
            ("From", "dim"),
            ("To", "dim"),
            ("Net Wage", ""),
            ("State", ""),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# EXPENSE CREATE
# ===================================================================


@app.command("create-expense")
def expense_create(
    ctx: typer.Context,
    employee: Annotated[str, typer.Option("--employee", help="Employee name or ID")],
    product: Annotated[str, typer.Option("--product", help="Expense product/category name or ID")],
    amount: Annotated[float, typer.Option("--amount", help="Expense amount")],
    description: Annotated[str | None, typer.Option("--description", help="Expense description")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without creating")] = False,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Create an expense record (hr.expense).

    Resolves employee and product by name or numeric ID.

    Examples:
        kctl-odoo hr create-expense --employee "John" --product "Travel" --amount 500000
        kctl-odoo hr create-expense --employee 15 --product "Meals" --amount 150000 --description "Client lunch" --force
        kctl-odoo hr create-expense --employee "Jane" --product "Travel" --amount 1000000 --dry-run
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not check_module_installed(c, "hr_expense"):
        out.info("Module 'hr_expense' is not installed — cannot create expenses.")
        return

    try:
        emp_id, emp_display = _resolve(c, "hr.employee", "name", employee, "Employee")
        prod_id, prod_display = _resolve(c, "product.product", "name", product, "Product")
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    vals = {
        "employee_id": emp_id,
        "product_id": prod_id,
        "total_amount_currency": amount,
        "name": description or prod_display,
    }

    summary = {
        "employee": emp_display,
        "product": prod_display,
        "amount": amount,
        "description": description or prod_display,
    }

    if dry_run:
        out.info("Dry run — expense will NOT be created.")
        out.detail(
            "Expense Preview",
            [
                (
                    "Expense",
                    [
                        ("Employee", emp_display),
                        ("Product", prod_display),
                        ("Amount", _fmt_amount(amount)),
                        ("Description", description or prod_display),
                    ],
                )
            ],
            data_for_json=summary,
        )
        return

    if not force:
        out.info(f"Create expense: employee={emp_display}, product={prod_display}, amount={_fmt_amount(amount)}")
        if not typer.confirm("Create this expense?"):
            raise typer.Exit(0)

    try:
        expense_id = c.create("hr.expense", vals)
    except RPCError as e:
        out.error(f"Failed to create expense: {e}")
        raise typer.Exit(1) from e

    out.success(f"Created expense id={expense_id} for {emp_display}")

    if actx.json_mode:
        out.raw_json({"id": expense_id, **summary})


# ===================================================================
# EXPENSE APPROVE
# ===================================================================


@app.command("approve-expense")
def expense_approve(
    ctx: typer.Context,
    sheet_id: Annotated[int, typer.Argument(help="Expense sheet ID to approve")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Approve an expense sheet (hr.expense.sheet).

    Calls ``approve_expense_sheets`` on the expense sheet record.

    Examples:
        kctl-odoo hr expense-approve 10 --force
        kctl-odoo hr expense-approve 10
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not check_module_installed(c, "hr_expense"):
        out.info("Module 'hr_expense' is not installed — cannot approve expenses.")
        return

    if not force and not typer.confirm(f"Approve expense sheet id={sheet_id}?"):
        raise typer.Exit(0)

    try:
        c.execute_kw("hr.expense.sheet", "approve_expense_sheets", [[sheet_id]])
    except RPCError as e:
        out.error(f"Failed to approve expense sheet {sheet_id}: {e}")
        raise typer.Exit(1) from e

    out.success(f"Approved expense sheet id={sheet_id}")

    if actx.json_mode:
        out.raw_json({"id": sheet_id, "action": "approved"})


# ===================================================================
# LIST EXPENSES
# ===================================================================


@app.command("expenses")
def expenses(
    ctx: typer.Context,
    state: Annotated[
        str | None, typer.Option("--state", "-s", help="Filter by state: draft, reported, approved, done")
    ] = None,
    employee: Annotated[str | None, typer.Option("--employee", "-e", help="Filter by employee name")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List expense sheets (hr.expense.sheet).

    Requires the ``hr_expense`` module to be installed.

    Examples:
        kctl-odoo hr expenses
        kctl-odoo hr expenses --state approved
        kctl-odoo hr expenses --employee "John" --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not check_module_installed(c, "hr_expense"):
        out.info("Module 'hr_expense' is not installed — skipping expenses.")
        if actx.json_mode:
            out.raw_json([])
        return

    domain: list = []
    if state:
        domain.append(("state", "=", state))
    if employee:
        domain.append(("employee_id.name", "ilike", employee))

    try:
        records = c.search_read(
            "hr.expense.sheet",
            domain=domain,
            fields=["id", "name", "employee_id", "total_amount", "state"],
            limit=limit,
            order="create_date desc",
        )
    except RPCError as e:
        out.error(f"Failed to list expense sheets: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No expense sheets found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows: list[list[str]] = []
    json_data: list[dict] = []
    for r in records:
        rows.append(
            [
                str(r["id"]),
                r.get("name", ""),
                _m2o_name(r.get("employee_id")),
                _fmt_amount(r.get("total_amount", 0)),
                r.get("state", ""),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "employee": _m2o_name(r.get("employee_id")),
                "total_amount": r.get("total_amount", 0),
                "state": r.get("state"),
            }
        )

    out.table(
        f"Expense Sheets ({len(records)})",
        [
            ("ID", "cyan"),
            ("Name", ""),
            ("Employee", ""),
            ("Total", ""),
            ("State", ""),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# PAYSLIP GENERATE
# ===================================================================


def _parse_month(month_str: str) -> tuple[str, str]:
    """Parse YYYY-MM into (date_from, date_to) ISO strings.

    Returns first and last day of the month.
    """
    import calendar

    try:
        parts = month_str.split("-")
        year = int(parts[0])
        month = int(parts[1])
    except (IndexError, ValueError) as e:
        raise typer.BadParameter(f"Invalid month format '{month_str}', expected YYYY-MM") from e

    last_day = calendar.monthrange(year, month)[1]
    date_from = f"{year:04d}-{month:02d}-01"
    date_to = f"{year:04d}-{month:02d}-{last_day:02d}"
    return date_from, date_to


@app.command("generate-payslip")
def payslip_generate(
    ctx: typer.Context,
    month: Annotated[str, typer.Option("--month", help="Period month (YYYY-MM)")],
    employee: Annotated[
        str | None, typer.Option("--employee", "-e", help="Employee name or ID (default: all with contracts)")
    ] = None,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Generate payslips for a period.

    Creates payslips for all employees with open contracts, computes salary rules.

    Examples:
        kctl-odoo hr generate-payslip --month 2026-03
        kctl-odoo hr generate-payslip --month 2026-03 --employee "John"
        kctl-odoo hr generate-payslip --month 2026-03 -y
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not check_module_installed(c, "hr_payroll"):
        out.error("Module 'hr_payroll' is not installed.")
        raise typer.Exit(1)

    try:
        date_from, date_to = _parse_month(month)
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    # Find employees with open contracts
    contract_domain: list = [("state", "=", "open")]
    if employee:
        if employee.isdigit():
            contract_domain.append(("employee_id", "=", int(employee)))
        else:
            contract_domain.append(("employee_id.name", "ilike", employee))

    try:
        contracts = c.search_read(
            "hr.contract",
            domain=contract_domain,
            fields=["id", "employee_id"],
            limit=5000,
        )
    except RPCError as e:
        out.error(f"Failed to search contracts: {e}")
        raise typer.Exit(1) from e

    if not contracts:
        out.info("No employees with open contracts found.")
        return

    # Deduplicate by employee_id
    emp_map: dict[int, str] = {}
    for ct in contracts:
        emp = ct.get("employee_id")
        if isinstance(emp, list):
            emp_map[emp[0]] = emp[1]

    if not force:
        out.info(f"Will create payslips for {len(emp_map)} employee(s) for {month}.")
        if not typer.confirm("Proceed?"):
            raise typer.Exit(0)

    created_ids: list[int] = []
    for emp_id, emp_name in emp_map.items():
        vals = {
            "employee_id": emp_id,
            "date_from": date_from,
            "date_to": date_to,
        }
        try:
            payslip_id = c.create("hr.payslip", vals)
            created_ids.append(payslip_id)
        except RPCError as e:
            out.warn(f"Failed to create payslip for {emp_name}: {e}")

    if not created_ids:
        out.error("No payslips were created.")
        raise typer.Exit(1)

    # Compute salary rules on all created payslips
    try:
        c.execute_kw("hr.payslip", "compute_sheet", [created_ids])
    except RPCError as e:
        out.warn(f"compute_sheet failed (payslips still created): {e}")

    out.success(f"Created {len(created_ids)} payslip(s) for {month}")

    if actx.json_mode:
        out.raw_json({"month": month, "created": len(created_ids), "payslip_ids": created_ids})


# ===================================================================
# PAYSLIP CONFIRM
# ===================================================================


@app.command("confirm-payslip")
def payslip_confirm(
    ctx: typer.Context,
    month: Annotated[str | None, typer.Option("--month", help="Period month to confirm (YYYY-MM)")] = None,
    ids: Annotated[str | None, typer.Option("--ids", help="Specific payslip IDs (comma-separated)")] = None,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Confirm (set to done) draft/verify payslips.

    Either --month or --ids must be provided.

    Examples:
        kctl-odoo hr confirm-payslip --month 2026-03
        kctl-odoo hr confirm-payslip --ids 1,2,3 -y
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not check_module_installed(c, "hr_payroll"):
        out.error("Module 'hr_payroll' is not installed.")
        raise typer.Exit(1)

    if not month and not ids:
        out.error("Provide --month or --ids.")
        raise typer.Exit(1)

    domain: list = [("state", "in", ["draft", "verify"])]

    if month:
        try:
            date_from, date_to = _parse_month(month)
        except typer.BadParameter as e:
            out.error(str(e))
            raise typer.Exit(1) from e
        domain.append(("date_from", ">=", date_from))
        domain.append(("date_to", "<=", date_to))

    if ids:
        try:
            payslip_ids = [int(i.strip()) for i in ids.split(",") if i.strip()]
        except ValueError:
            out.error("Invalid IDs: must be comma-separated integers")
            raise typer.Exit(1) from None
        domain.append(("id", "in", payslip_ids))

    try:
        records = c.search_read(
            "hr.payslip",
            domain=domain,
            fields=["id", "number", "employee_id", "state"],
            limit=5000,
        )
    except RPCError as e:
        out.error(f"Failed to search payslips: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No draft/verify payslips found for the given criteria.")
        return

    if not force:
        out.info(f"Will confirm {len(records)} payslip(s).")
        if not typer.confirm("Proceed?"):
            raise typer.Exit(0)

    confirmed = 0
    record_ids = [r["id"] for r in records]
    for rid in record_ids:
        try:
            c.execute_kw("hr.payslip", "action_payslip_done", [[rid]])
            confirmed += 1
        except RPCError as e:
            emp = _m2o_name(next((r.get("employee_id") for r in records if r["id"] == rid), ""))
            out.warn(f"Failed to confirm payslip {rid} ({emp}): {e}")

    out.success(f"Confirmed {confirmed} payslip(s)")

    if actx.json_mode:
        out.raw_json({"confirmed": confirmed, "total": len(records)})


# ===================================================================
# ATTENDANCE IMPORT
# ===================================================================


@app.command("import-attendance")
def attendance_import(
    ctx: typer.Context,
    file: Annotated[str, typer.Argument(help="CSV file path")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without importing")] = False,
) -> None:
    """Import attendance records from CSV.

    CSV format: employee_name,check_in,check_out
    Dates in YYYY-MM-DD HH:MM:SS format.

    Examples:
        kctl-odoo hr attendance-import attendance.csv
        kctl-odoo hr attendance-import attendance.csv --dry-run
    """
    import csv
    from pathlib import Path

    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    _require_hr(c, out)

    attn_count = _safe_count(c, "hr.attendance", [])
    if attn_count is None:
        out.error("Module 'hr_attendance' is not installed.")
        raise typer.Exit(1)

    file_path = Path(file)
    if not file_path.exists():
        out.error(f"File not found: {file}")
        raise typer.Exit(1)

    rows_parsed: list[dict] = []
    errors: list[str] = []
    with file_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader, start=2):
            emp_name = (row.get("employee_name") or "").strip()
            check_in = (row.get("check_in") or "").strip()
            check_out = (row.get("check_out") or "").strip()

            if not emp_name or not check_in:
                errors.append(f"Row {i}: missing employee_name or check_in")
                continue

            # Resolve employee
            try:
                emp_id, emp_display = _resolve(c, "hr.employee", "name", emp_name, "Employee")
            except typer.BadParameter:
                errors.append(f"Row {i}: employee not found '{emp_name}'")
                continue

            entry: dict = {
                "employee_id": emp_id,
                "employee_name": emp_display,
                "check_in": check_in,
            }
            if check_out:
                entry["check_out"] = check_out
            rows_parsed.append(entry)

    if errors:
        for err in errors:
            out.warn(err)

    if not rows_parsed:
        out.error("No valid rows to import.")
        raise typer.Exit(1)

    if dry_run:
        out.info(f"Dry run: {len(rows_parsed)} attendance record(s) would be imported ({len(errors)} skipped).")
        table_rows = []
        for r in rows_parsed[:20]:
            table_rows.append(
                [
                    r["employee_name"],
                    r["check_in"],
                    r.get("check_out", "-"),
                ]
            )
        out.table(
            f"Preview ({min(len(rows_parsed), 20)} of {len(rows_parsed)})",
            [("Employee", ""), ("Check In", ""), ("Check Out", "")],
            table_rows,
            data_for_json=rows_parsed,
        )
        return

    created = 0
    for entry in rows_parsed:
        vals: dict = {
            "employee_id": entry["employee_id"],
            "check_in": entry["check_in"],
        }
        if "check_out" in entry:
            vals["check_out"] = entry["check_out"]
        try:
            c.create("hr.attendance", vals)
            created += 1
        except RPCError as e:
            out.warn(f"Failed for {entry['employee_name']}: {e}")

    out.success(f"Imported {created} attendance record(s) ({len(errors)} skipped)")

    if actx.json_mode:
        out.raw_json({"imported": created, "skipped": len(errors)})


# ===================================================================
# SUMMARY DASHBOARD
# ===================================================================


@app.command("summary")
def hr_summary(ctx: typer.Context) -> None:
    """HR dashboard — employees and leave requests."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "hr.employee"):
        out.error(module_hint("hr.employee"))
        raise typer.Exit(1)

    total_employees = c.search_count("hr.employee", [])

    leave_available = model_available(c, "hr.leave")
    pending_leaves = 0
    approved_this_month = 0
    if leave_available:
        pending_leaves = c.search_count("hr.leave", [("state", "in", ["draft", "confirm"])])
        now = datetime.now(tz=UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
        approved_this_month = c.search_count(
            "hr.leave",
            [("state", "=", "validate"), ("write_date", ">=", month_start)],
        )

    sections = [
        (
            "Employees",
            [("Total Active", str(total_employees))],
        ),
    ]

    json_out: dict = {"total_employees": total_employees}

    if leave_available:
        sections.append(
            (
                "Leave Requests",
                [
                    ("Pending", str(pending_leaves)),
                    ("Approved this month", str(approved_this_month)),
                ],
            )
        )
        json_out["pending_leaves"] = pending_leaves
        json_out["approved_this_month"] = approved_this_month
    else:
        sections.append(("Leave Requests", [("(hr_holidays not installed)", "-")]))

    out.detail("HR Summary", sections, data_for_json=json_out)


# ===================================================================
# EXPENSE WORKFLOW COMMANDS
# ===================================================================


@app.command("submit-expense")
def submit_expense(
    ctx: typer.Context,
    sheet_id: Annotated[int, typer.Argument(help="Expense sheet ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip state check")] = False,
) -> None:
    """Submit an expense report for approval.

    Calls action_submit_sheet on hr.expense.sheet.

    Examples:
        kctl-odoo hr submit-expense 10
        kctl-odoo hr submit-expense 10 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "hr.expense.sheet"):
        out.error(module_hint("hr.expense.sheet"))
        raise typer.Exit(1)

    sheet_fields = safe_fields(
        c,
        "hr.expense.sheet",
        ["id", "name", "state", "employee_id", "total_amount"],
    )

    try:
        sheets = c.read("hr.expense.sheet", [sheet_id], sheet_fields)
    except RPCError as e:
        out.error(f"Failed to read expense sheet {sheet_id}: {e.detail}")
        raise typer.Exit(1) from e

    if not sheets:
        out.error(f"Expense sheet not found: ID {sheet_id}")
        raise typer.Exit(1)

    sheet = sheets[0]
    name = sheet.get("name") or f"Sheet #{sheet_id}"
    state = sheet.get("state") or ""
    employee = sheet.get("employee_id")
    employee_name = employee[1] if isinstance(employee, list) else "-"

    if not force and state != "draft":
        out.error(f"Sheet '{name}' is in state '{state}', expected 'draft'. Use --force to override.")
        raise typer.Exit(1)

    try:
        c.execute_kw("hr.expense.sheet", "action_submit_sheet", [[sheet_id]])
    except RPCError as e:
        out.error(f"Failed to submit expense sheet: {e.detail}")
        raise typer.Exit(1) from e

    out.success(f"Expense sheet '{name}' (employee: {employee_name}) submitted for approval.")
    if actx.json_mode:
        out.raw_json({"sheet_id": sheet_id, "name": name, "action": "submitted"})


@app.command("reimburse-expense")
def reimburse_expense(
    ctx: typer.Context,
    sheet_id: Annotated[int, typer.Argument(help="Expense sheet ID")],
    journal: Annotated[str | None, typer.Option("--journal", help="Journal name or code (optional)")] = None,
    force: Annotated[bool, typer.Option("--force", help="Skip state check")] = False,
) -> None:
    """Register reimbursement for an approved expense sheet.

    Creates the journal entry for the approved expense sheet.

    Examples:
        kctl-odoo hr reimburse-expense 10
        kctl-odoo hr reimburse-expense 10 --journal MISC
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "hr.expense.sheet"):
        out.error(module_hint("hr.expense.sheet"))
        raise typer.Exit(1)

    sheet_fields = safe_fields(
        c,
        "hr.expense.sheet",
        ["id", "name", "state", "employee_id", "total_amount", "account_move_id"],
    )

    try:
        sheets = c.read("hr.expense.sheet", [sheet_id], sheet_fields)
    except RPCError as e:
        out.error(f"Failed to read expense sheet {sheet_id}: {e.detail}")
        raise typer.Exit(1) from e

    if not sheets:
        out.error(f"Expense sheet not found: ID {sheet_id}")
        raise typer.Exit(1)

    sheet = sheets[0]
    name = sheet.get("name") or f"Sheet #{sheet_id}"
    state = sheet.get("state") or ""
    employee = sheet.get("employee_id")
    employee_name = employee[1] if isinstance(employee, list) else "-"

    if not force and state != "approve":
        out.error(f"Sheet '{name}' is in state '{state}', expected 'approve'. Use --force to override.")
        raise typer.Exit(1)

    # Optionally set journal before posting
    if journal:
        try:
            journals = c.search_read(
                "account.journal",
                domain=[("code", "=", journal)],
                fields=["id", "name"],
                limit=1,
            )
            if not journals:
                journals = c.search_read(
                    "account.journal",
                    domain=[("name", "ilike", journal)],
                    fields=["id", "name"],
                    limit=1,
                )
            if journals:
                c.write("hr.expense.sheet", [sheet_id], {"journal_id": journals[0]["id"]})
            else:
                out.warn(f"Journal '{journal}' not found, proceeding with default.")
        except RPCError as e:
            out.warn(f"Could not set journal: {e.detail}")

    try:
        c.execute_kw("hr.expense.sheet", "action_sheet_move_create", [[sheet_id]])
    except RPCError as e:
        out.error(f"Failed to create journal entry for expense sheet: {e.detail}")
        raise typer.Exit(1) from e

    # Re-read to get move reference
    move_ref = "-"
    try:
        updated = c.read(
            "hr.expense.sheet",
            [sheet_id],
            safe_fields(c, "hr.expense.sheet", ["account_move_id"]),
        )
        if updated:
            move = updated[0].get("account_move_id")
            move_ref = move[1] if isinstance(move, list) else "-"
    except RPCError:
        pass

    out.success(f"Reimbursement journal entry created for '{name}' (employee: {employee_name}). Move: {move_ref}")
    if actx.json_mode:
        out.raw_json({"sheet_id": sheet_id, "name": name, "move_reference": move_ref, "action": "reimbursed"})


@app.command("expense-summary")
def expense_summary(
    ctx: typer.Context,
    period: Annotated[str, typer.Option("--period", help="Period: month, quarter, year")] = "month",
) -> None:
    """Expense dashboard — sheets by state, total amounts.

    Examples:
        kctl-odoo hr expense-summary
        kctl-odoo hr expense-summary --period quarter
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "hr.expense.sheet"):
        out.error(module_hint("hr.expense.sheet"))
        raise typer.Exit(1)

    # Determine date filter
    now = datetime.now(tz=UTC)
    if period == "quarter":
        quarter_start_month = ((now.month - 1) // 3) * 3 + 1
        date_from = now.replace(month=quarter_start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "year":
        date_from = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:  # month (default)
        date_from = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    date_from_str = date_from.strftime("%Y-%m-%d %H:%M:%S")

    sheet_fields = safe_fields(
        c,
        "hr.expense.sheet",
        ["id", "name", "state", "total_amount", "employee_id"],
    )

    try:
        sheets = c.search_read(
            "hr.expense.sheet",
            domain=[("write_date", ">=", date_from_str)],
            fields=sheet_fields,
        )
    except RPCError as e:
        out.error(f"Failed to fetch expense sheets: {e.detail}")
        raise typer.Exit(1) from e

    # Aggregate by state
    state_labels = {
        "draft": "Draft",
        "submit": "Submitted",
        "approve": "Approved",
        "post": "Posted",
        "done": "Done / Paid",
        "cancel": "Cancelled",
    }

    state_counts: dict[str, int] = {}
    state_totals: dict[str, float] = {}

    for sheet in sheets:
        state = sheet.get("state") or "draft"
        amount = sheet.get("total_amount", 0.0) or 0.0
        state_counts[state] = state_counts.get(state, 0) + 1
        state_totals[state] = state_totals.get(state, 0.0) + amount

    all_states = list(state_labels.keys())
    rows = []
    json_data: list[dict] = []

    for state in all_states:
        count = state_counts.get(state, 0)
        total = state_totals.get(state, 0.0)
        if count == 0:
            continue
        label = state_labels.get(state, state.capitalize())
        rows.append([label, str(count), _fmt_amount(total)])
        json_data.append({"state": state, "label": label, "sheets": count, "total_amount": total})

    grand_total = sum(state_totals.values())
    total_sheets = sum(state_counts.values())

    if not rows:
        out.info(f"No expense sheets found for this {period}.")
        return

    # Add totals row
    rows.append(["TOTAL", str(total_sheets), _fmt_amount(grand_total)])

    period_label = {"month": "This Month", "quarter": "This Quarter", "year": "This Year"}.get(period, period)
    out.table(
        f"Expense Summary — {period_label} (from {date_from.strftime('%Y-%m-%d')})",
        [
            ("State", "cyan"),
            ("Sheets", ""),
            ("Total Amount", "yellow"),
        ],
        rows,
        data_for_json=json_data,
    )
