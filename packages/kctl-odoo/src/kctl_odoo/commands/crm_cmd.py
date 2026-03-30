"""CRM / Lead management commands — leads, opportunities, pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import fmt_amount, model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError
from kctl_odoo.core.field_helpers import safe_fields

app = typer.Typer(help="CRM: leads, opportunities, pipeline management.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _m2o_name(val: object) -> str:
    """Extract display name from an M2O field value ([id, name] or False)."""
    if isinstance(val, list):
        return str(val[1])
    return str(val or "-")


def _ensure_crm(c: object, out: object) -> bool:
    """Return False and print error if crm.lead is not available."""
    if not model_available(c, "crm.lead"):
        out.error("CRM module not installed. Install with: kctl-odoo modules install crm")  # type: ignore[attr-defined]
        return False
    return True


# ===================================================================
# LEADS
# ===================================================================


@app.command("leads")
def leads(
    ctx: typer.Context,
    stage: Annotated[str | None, typer.Option("--stage", "-s", help="Filter by stage name")] = None,
    user: Annotated[str | None, typer.Option("--user", "-u", help="Filter by salesperson name")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List CRM leads.

    Examples:
        kctl-odoo crm leads
        kctl-odoo crm leads --stage "New" --limit 20
        kctl-odoo crm leads --user "John"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _ensure_crm(c, out):
        raise typer.Exit(1)

    domain: list = [("type", "=", "lead")]
    if stage:
        domain.append(("stage_id.name", "ilike", stage))
    if user:
        domain.append(("user_id.name", "ilike", user))

    fields = safe_fields(
        c,
        "crm.lead",
        ["display_name", "partner_id", "user_id", "stage_id", "expected_revenue", "create_date", "priority"],
    )

    try:
        records = c.search_read("crm.lead", domain, fields, limit=limit)  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to list leads: {e}")
        raise typer.Exit(1)

    if not records:
        out.info("No leads found.")
        return

    if actx.json_mode:
        out.raw_json(records)
        return

    rows = [
        [
            r.get("display_name", "-"),
            _m2o_name(r.get("partner_id", False)),
            _m2o_name(r.get("user_id", False)),
            _m2o_name(r.get("stage_id", False)),
            fmt_amount(float(r.get("expected_revenue", 0))),
            (r.get("create_date", "-") or "-")[:10],
        ]
        for r in records
    ]

    out.table(
        f"Leads ({len(rows)})",
        [
            ("Name", ""),
            ("Partner", "dim"),
            ("Salesperson", "dim"),
            ("Stage", ""),
            ("Exp. Revenue", ""),
            ("Created", "dim"),
        ],
        rows,
    )


# ===================================================================
# OPPORTUNITIES
# ===================================================================


@app.command("opportunities")
def opportunities(
    ctx: typer.Context,
    stage: Annotated[str | None, typer.Option("--stage", "-s", help="Filter by stage name")] = None,
    user: Annotated[str | None, typer.Option("--user", "-u", help="Filter by salesperson name")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List CRM opportunities.

    Examples:
        kctl-odoo crm opportunities
        kctl-odoo crm opportunities --stage "Proposition"
        kctl-odoo crm opportunities --user "Anna" --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _ensure_crm(c, out):
        raise typer.Exit(1)

    domain: list = [("type", "=", "opportunity")]
    if stage:
        domain.append(("stage_id.name", "ilike", stage))
    if user:
        domain.append(("user_id.name", "ilike", user))

    fields = safe_fields(
        c,
        "crm.lead",
        ["display_name", "partner_id", "user_id", "stage_id", "expected_revenue", "create_date", "priority"],
    )

    try:
        records = c.search_read("crm.lead", domain, fields, limit=limit)  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to list opportunities: {e}")
        raise typer.Exit(1)

    if not records:
        out.info("No opportunities found.")
        return

    if actx.json_mode:
        out.raw_json(records)
        return

    rows = [
        [
            r.get("display_name", "-"),
            _m2o_name(r.get("partner_id", False)),
            _m2o_name(r.get("user_id", False)),
            _m2o_name(r.get("stage_id", False)),
            fmt_amount(float(r.get("expected_revenue", 0))),
            (r.get("create_date", "-") or "-")[:10],
        ]
        for r in records
    ]

    out.table(
        f"Opportunities ({len(rows)})",
        [
            ("Name", ""),
            ("Partner", "dim"),
            ("Salesperson", "dim"),
            ("Stage", ""),
            ("Exp. Revenue", ""),
            ("Created", "dim"),
        ],
        rows,
    )


# ===================================================================
# GET
# ===================================================================


@app.command("get")
def get_lead(
    ctx: typer.Context,
    lead_id: Annotated[int, typer.Argument(help="Lead/opportunity ID")],
) -> None:
    """Show full lead or opportunity detail.

    Examples:
        kctl-odoo crm get 42
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _ensure_crm(c, out):
        raise typer.Exit(1)

    detail_fields = [
        "name",
        "partner_id",
        "email_from",
        "phone",
        "stage_id",
        "expected_revenue",
        "probability",
        "user_id",
        "team_id",
        "source_id",
        "medium_id",
        "campaign_id",
        "description",
        "activity_ids",
        "type",
    ]
    fields = safe_fields(c, "crm.lead", detail_fields)

    try:
        records = c.read("crm.lead", [lead_id], fields)  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to read lead: {e}")
        raise typer.Exit(1)

    if not records:
        out.error(f"Lead #{lead_id} not found.")
        raise typer.Exit(1)

    r = records[0]
    activity_count = len(r.get("activity_ids", []))

    if actx.json_mode:
        out.raw_json({**r, "activity_count": activity_count})
        return

    rows = [
        ["Name", r.get("name", "-")],
        ["Type", r.get("type", "-")],
        ["Partner", _m2o_name(r.get("partner_id", False))],
        ["Email", r.get("email_from") or "-"],
        ["Phone", r.get("phone") or "-"],
        ["Stage", _m2o_name(r.get("stage_id", False))],
        ["Expected Revenue", fmt_amount(float(r.get("expected_revenue", 0)))],
        ["Probability", f"{r.get('probability', 0):.0f}%"],
        ["Salesperson", _m2o_name(r.get("user_id", False))],
        ["Sales Team", _m2o_name(r.get("team_id", False))],
        ["Source", _m2o_name(r.get("source_id", False))],
        ["Medium", _m2o_name(r.get("medium_id", False))],
        ["Campaign", _m2o_name(r.get("campaign_id", False))],
        ["Activities", str(activity_count)],
        ["Description", (r.get("description") or "-")[:80]],
    ]

    out.table(
        f"Lead/Opportunity #{lead_id}",
        [("Field", ""), ("Value", "")],
        rows,
    )


# ===================================================================
# CREATE-LEAD
# ===================================================================


@app.command("create-lead")
def create_lead(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Lead name/subject")],
    partner: Annotated[str | None, typer.Option("--partner", help="Partner name or ID")] = None,
    email: Annotated[str | None, typer.Option("--email", help="Contact email")] = None,
    phone: Annotated[str | None, typer.Option("--phone", help="Contact phone")] = None,
    user: Annotated[str | None, typer.Option("--user", help="Salesperson name")] = None,
    team: Annotated[str | None, typer.Option("--team", help="Sales team name")] = None,
) -> None:
    """Create a new CRM lead.

    Examples:
        kctl-odoo crm create-lead "New prospect from website"
        kctl-odoo crm create-lead "PT Maju inquiry" --partner "PT Maju" --email "info@ptmaju.com"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _ensure_crm(c, out):
        raise typer.Exit(1)

    vals: dict = {"name": name, "type": "lead"}

    if email:
        vals["email_from"] = email
    if phone:
        vals["phone"] = phone

    # Resolve partner
    if partner:
        if partner.isdigit():
            vals["partner_id"] = int(partner)
        else:
            recs = c.search_read("res.partner", [("name", "ilike", partner)], ["id", "name"], limit=1)  # type: ignore[attr-defined]
            if recs:
                vals["partner_id"] = recs[0]["id"]
            else:
                out.warn(f"Partner '{partner}' not found, skipping.")

    # Resolve user
    if user:
        recs = c.search_read("res.users", [("name", "ilike", user)], ["id", "name"], limit=1)  # type: ignore[attr-defined]
        if recs:
            vals["user_id"] = recs[0]["id"]
        else:
            out.warn(f"User '{user}' not found, skipping.")

    # Resolve team
    if team:
        recs = c.search_read("crm.team", [("name", "ilike", team)], ["id", "name"], limit=1)  # type: ignore[attr-defined]
        if recs:
            vals["team_id"] = recs[0]["id"]
        else:
            out.warn(f"Team '{team}' not found, skipping.")

    try:
        lead_id = c.execute_kw("crm.lead", "create", [vals])  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to create lead: {e}")
        raise typer.Exit(1)

    out.success(f"Created lead #{lead_id}: {name}")


# ===================================================================
# CONVERT
# ===================================================================


@app.command("convert")
def convert_lead(
    ctx: typer.Context,
    lead_id: Annotated[int, typer.Argument(help="Lead ID to convert")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation")] = False,
) -> None:
    """Convert a lead to an opportunity.

    Examples:
        kctl-odoo crm convert 42
        kctl-odoo crm convert 42 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _ensure_crm(c, out):
        raise typer.Exit(1)

    if not force:
        typer.confirm(f"Convert lead #{lead_id} to opportunity?", abort=True)

    try:
        c.execute_kw("crm.lead", "convert_opportunity", [[lead_id], {}])  # type: ignore[attr-defined]
        out.success(f"Lead #{lead_id} converted to opportunity.")
    except RPCError as e:
        out.error(f"Failed to convert lead: {e}")
        raise typer.Exit(1)


# ===================================================================
# PIPELINE
# ===================================================================


@app.command("pipeline")
def pipeline(
    ctx: typer.Context,
) -> None:
    """Show pipeline summary: opportunities by stage with counts and expected revenue.

    Examples:
        kctl-odoo crm pipeline
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "crm.lead"):
        out.info("CRM module not installed.")
        return

    try:
        records = c.search_read(  # type: ignore[attr-defined]
            "crm.lead",
            [("type", "=", "opportunity"), ("active", "=", True)],
            ["stage_id", "expected_revenue"],
            limit=0,
        )
    except RPCError as e:
        out.error(f"Failed to fetch pipeline: {e}")
        raise typer.Exit(1)

    # Aggregate by stage
    stage_data: dict[str, dict] = {}
    for r in records:
        stage = _m2o_name(r.get("stage_id", False)) or "No Stage"
        if stage not in stage_data:
            stage_data[stage] = {"count": 0, "revenue": 0.0}
        stage_data[stage]["count"] += 1
        stage_data[stage]["revenue"] += float(r.get("expected_revenue", 0))

    total = len(records)
    total_rev = sum(v["revenue"] for v in stage_data.values())

    if not stage_data:
        out.info("No open opportunities in pipeline.")
        return

    if actx.json_mode:
        out.raw_json(
            {
                "total": total,
                "total_expected_revenue": total_rev,
                "stages": [
                    {"stage": s, "count": d["count"], "expected_revenue": d["revenue"]} for s, d in stage_data.items()
                ],
            }
        )
        return

    rows = [[stage, str(d["count"]), fmt_amount(d["revenue"])] for stage, d in stage_data.items()]
    rows.append(["TOTAL", str(total), fmt_amount(total_rev)])

    out.table(
        "Pipeline Summary",
        [("Stage", ""), ("Count", ""), ("Expected Revenue", "")],
        rows,
    )


# ===================================================================
# WON
# ===================================================================


@app.command("won")
def won(
    ctx: typer.Context,
    lead_id: Annotated[int, typer.Argument(help="Opportunity ID")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation")] = False,
) -> None:
    """Mark an opportunity as won.

    Examples:
        kctl-odoo crm won 42
        kctl-odoo crm won 42 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _ensure_crm(c, out):
        raise typer.Exit(1)

    if not force:
        typer.confirm(f"Mark opportunity #{lead_id} as WON?", abort=True)

    try:
        c.execute_kw("crm.lead", "action_set_won", [[lead_id]])  # type: ignore[attr-defined]
        out.success(f"Opportunity #{lead_id} marked as WON.")
    except RPCError as e:
        out.error(f"Failed to mark as won: {e}")
        raise typer.Exit(1)


# ===================================================================
# LOST
# ===================================================================


@app.command("lost")
def lost(
    ctx: typer.Context,
    lead_id: Annotated[int, typer.Argument(help="Opportunity ID")],
    reason: Annotated[str | None, typer.Option("--reason", help="Lost reason")] = None,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation")] = False,
) -> None:
    """Mark an opportunity as lost.

    Examples:
        kctl-odoo crm lost 42
        kctl-odoo crm lost 42 --reason "Budget constraints" --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _ensure_crm(c, out):
        raise typer.Exit(1)

    if not force:
        typer.confirm(f"Mark opportunity #{lead_id} as LOST?", abort=True)

    kwargs: dict = {}
    if reason:
        # Try to find or create a lost reason
        try:
            recs = c.search_read(  # type: ignore[attr-defined]
                "crm.lost.reason", [("name", "ilike", reason)], ["id", "name"], limit=1
            )
            if recs:
                kwargs["lost_reason_id"] = recs[0]["id"]
        except RPCError:
            pass  # Lost reason model may not exist in all Odoo versions

    try:
        c.execute_kw("crm.lead", "action_set_lost", [[lead_id]], kwargs)  # type: ignore[attr-defined]
        out.success(f"Opportunity #{lead_id} marked as LOST.")
    except RPCError as e:
        out.error(f"Failed to mark as lost: {e}")
        raise typer.Exit(1)


# ===================================================================
# ACTIVITIES
# ===================================================================


@app.command("activities")
def activities(
    ctx: typer.Context,
    user: Annotated[str | None, typer.Option("--user", "-u", help="Filter by user name")] = None,
    overdue: Annotated[bool, typer.Option("--overdue", help="Show only overdue activities")] = False,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List CRM-related activities.

    Examples:
        kctl-odoo crm activities
        kctl-odoo crm activities --overdue
        kctl-odoo crm activities --user "John" --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = [("res_model", "=", "crm.lead")]
    if user:
        domain.append(("user_id.name", "ilike", user))
    if overdue:
        today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        domain.append(("date_deadline", "<", today))

    fields = safe_fields(
        c,
        "mail.activity",
        ["display_name", "res_model_id", "res_id", "user_id", "date_deadline", "activity_type_id", "summary"],
    )

    try:
        records = c.search_read("mail.activity", domain, fields, limit=limit)  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to list activities: {e}")
        raise typer.Exit(1)

    if not records:
        out.info("No activities found.")
        return

    if actx.json_mode:
        out.raw_json(records)
        return

    rows = [
        [
            _m2o_name(r.get("activity_type_id", False)),
            r.get("summary") or "-",
            _m2o_name(r.get("user_id", False)),
            r.get("date_deadline", "-") or "-",
            str(r.get("res_id", "-")),
        ]
        for r in records
    ]

    title = "Overdue Activities" if overdue else f"CRM Activities ({len(rows)})"
    out.table(
        title,
        [("Type", ""), ("Summary", "dim"), ("User", ""), ("Deadline", ""), ("Record ID", "dim")],
        rows,
    )
