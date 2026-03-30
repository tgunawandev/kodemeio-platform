"""KPI report commands — wraps OCA MIS Builder framework."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="KPI reports via MIS Builder framework.")

_MIS_REPORT_MODEL = "mis.report"
_MIS_INSTANCE_MODEL = "mis.report.instance"
_KPI_HINT = "OCA MIS Builder module (mis_builder) is not installed."


def _m2o_name(val: object) -> str:
    if isinstance(val, list):
        return str(val[1])
    return str(val or "-")


# ===================================================================
# LIST
# ===================================================================


@app.command("list")
def list_reports(ctx: typer.Context) -> None:
    """List MIS report templates.

    Examples:
        kctl-odoo kpi list
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _MIS_REPORT_MODEL):
        out.warn(_KPI_HINT)
        return

    try:
        records = c.search_read(  # type: ignore[attr-defined]
            _MIS_REPORT_MODEL,
            domain=[],
            fields=["name", "description"],
            order="name asc",
        )
    except RPCError as e:
        out.error(f"Failed to list MIS reports: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No MIS report templates found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append([str(r["id"]), r.get("name", ""), str(r.get("description", "") or "")])
        json_data.append({"id": r["id"], "name": r.get("name"), "description": r.get("description")})

    out.table(
        f"MIS Report Templates ({len(records)})",
        [("ID", "dim"), ("Name", "cyan"), ("Description", "")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# INSTANCES
# ===================================================================


@app.command("instances")
def instances(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List MIS report instances (configured reports with date ranges).

    Examples:
        kctl-odoo kpi instances
        kctl-odoo kpi instances --limit 10
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _MIS_INSTANCE_MODEL):
        out.warn(_KPI_HINT)
        return

    try:
        records = c.search_read(  # type: ignore[attr-defined]
            _MIS_INSTANCE_MODEL,
            domain=[],
            fields=["name", "report_id", "date_from", "date_to", "company_id"],
            limit=limit,
            order="name asc",
        )
    except RPCError as e:
        out.error(f"Failed to list MIS report instances: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No MIS report instances found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                str(r["id"]),
                r.get("name", ""),
                _m2o_name(r.get("report_id")),
                str(r.get("date_from", "")),
                str(r.get("date_to", "")),
                _m2o_name(r.get("company_id")),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "report": _m2o_name(r.get("report_id")),
                "date_from": r.get("date_from"),
                "date_to": r.get("date_to"),
                "company": _m2o_name(r.get("company_id")),
            }
        )

    out.table(
        f"MIS Report Instances ({len(records)})",
        [("ID", "dim"), ("Name", "cyan"), ("Template", ""), ("From", ""), ("To", ""), ("Company", "")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# RUN
# ===================================================================


@app.command("run")
def run(
    ctx: typer.Context,
    instance_id: Annotated[int, typer.Argument(help="MIS report instance ID")],
) -> None:
    """Compute and display a MIS report instance result.

    Examples:
        kctl-odoo kpi run 3
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _MIS_INSTANCE_MODEL):
        out.warn(_KPI_HINT)
        return

    try:
        instances_data = c.read(  # type: ignore[attr-defined]
            _MIS_INSTANCE_MODEL,
            [instance_id],
            ["name", "report_id", "date_from", "date_to"],
        )
    except RPCError as e:
        out.error(f"Failed to fetch instance {instance_id}: {e}")
        raise typer.Exit(1) from e

    if not instances_data:
        out.error(f"MIS report instance not found: {instance_id}")
        raise typer.Exit(1)

    inst = instances_data[0]
    out.info(f"Computing MIS report: {inst.get('name', '')} ({inst.get('date_from', '')} to {inst.get('date_to', '')})")

    try:
        result = c.execute_kw(  # type: ignore[attr-defined]
            _MIS_INSTANCE_MODEL, "compute", [[instance_id]]
        )
        out.success(f"Report computed. Instance ID: {instance_id}")
        if result and isinstance(result, dict):
            rows = []
            json_data = []
            for key, val in result.items():
                rows.append([str(key), str(val)])
                json_data.append({"key": key, "value": val})
            if rows:
                out.table(
                    "Report Results",
                    [("KPI", "cyan"), ("Value", "")],
                    rows,
                    data_for_json=json_data,
                )
        else:
            out.info(f"Result: {result}")
            if actx.json_mode:
                out.raw_json({"instance_id": instance_id, "name": inst.get("name"), "result": result})
    except RPCError as e:
        out.warn(f"Could not auto-compute via execute_kw: {e}")
        out.info(
            f"To view this report manually:\n"
            f"  Accounting > Reporting > MIS Reports > {inst.get('name', '')} > Compute\n"
            f"  Instance ID: {instance_id}"
        )
