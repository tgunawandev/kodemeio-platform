"""Budget management commands — planning and variance analysis."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Budget planning and variance analysis.")

_BUDGET_MODEL = "budget.budget"
_BUDGET_HINT = "Budget management module (budget_management) is not installed."


def _m2o_name(val: object) -> str:
    if isinstance(val, list):
        return str(val[1])
    return str(val or "-")


# ===================================================================
# LIST
# ===================================================================


@app.command("list")
def list_budgets(
    ctx: typer.Context,
    state: Annotated[
        str | None, typer.Option("--state", help="Filter by state: draft, confirm, validate, done")
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List budgets.

    Examples:
        kctl-odoo budget list
        kctl-odoo budget list --state validate --limit 10
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _BUDGET_MODEL):
        out.warn(_BUDGET_HINT)
        return

    domain: list = []
    if state:
        domain.append(("state", "=", state))

    try:
        records = c.search_read(  # type: ignore[attr-defined]
            _BUDGET_MODEL,
            domain=domain,
            fields=["name", "date_from", "date_to", "state", "company_id"],
            limit=limit,
            order="date_from desc",
        )
    except RPCError as e:
        out.error(f"Failed to list budgets: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No budgets found.")
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
                str(r.get("date_from", "")),
                str(r.get("date_to", "")),
                str(r.get("state", "")),
                _m2o_name(r.get("company_id")),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "date_from": r.get("date_from"),
                "date_to": r.get("date_to"),
                "state": r.get("state"),
                "company": _m2o_name(r.get("company_id")),
            }
        )

    out.table(
        f"Budgets ({len(records)})",
        [("ID", "dim"), ("Name", "cyan"), ("From", ""), ("To", ""), ("State", ""), ("Company", "")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# VARIANCE
# ===================================================================


@app.command("variance")
def variance(
    ctx: typer.Context,
    budget_id: Annotated[int, typer.Argument(help="Budget ID")],
) -> None:
    """Show budget vs actual variance per budget line.

    Examples:
        kctl-odoo budget variance 5
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _BUDGET_MODEL):
        out.warn(_BUDGET_HINT)
        return

    try:
        budgets = c.read(  # type: ignore[attr-defined]
            _BUDGET_MODEL,
            [budget_id],
            ["name", "date_from", "date_to", "state", "line_ids"],
        )
    except RPCError as e:
        out.error(f"Failed to fetch budget {budget_id}: {e}")
        raise typer.Exit(1) from e

    if not budgets:
        out.error(f"Budget not found: {budget_id}")
        raise typer.Exit(1)

    budget = budgets[0]
    line_ids = budget.get("line_ids", [])

    sections = [
        (
            "Budget",
            [
                ("ID", str(budget["id"])),
                ("Name", budget.get("name", "")),
                ("Period", f"{budget.get('date_from', '')} to {budget.get('date_to', '')}"),
                ("State", str(budget.get("state", ""))),
                ("Lines", str(len(line_ids))),
            ],
        )
    ]

    json_result: dict = {
        "id": budget["id"],
        "name": budget.get("name"),
        "date_from": budget.get("date_from"),
        "date_to": budget.get("date_to"),
        "state": budget.get("state"),
        "lines": [],
    }

    out.detail("Budget Detail", sections, data_for_json=json_result)

    if line_ids:
        try:
            lines = c.read(  # type: ignore[attr-defined]
                "budget.line",
                line_ids,
                ["name", "account_id", "planned_amount", "practical_amount", "theoric_amount"],
            )
        except RPCError as e:
            out.warn(f"Failed to read budget lines: {e}")
            return

        rows = []
        lines_json = []
        total_planned = total_actual = 0.0
        for ln in lines:
            planned = ln.get("planned_amount", 0.0) or 0.0
            actual = ln.get("practical_amount", 0.0) or 0.0
            variance_val = actual - planned
            total_planned += planned
            total_actual += actual
            var_str = f"{variance_val:+,.2f}"
            rows.append(
                [
                    ln.get("name", ""),
                    _m2o_name(ln.get("account_id")),
                    f"{planned:,.2f}",
                    f"{actual:,.2f}",
                    var_str,
                ]
            )
            lines_json.append(
                {
                    "name": ln.get("name"),
                    "account": _m2o_name(ln.get("account_id")),
                    "planned": planned,
                    "actual": actual,
                    "variance": variance_val,
                }
            )

        total_var = total_actual - total_planned
        rows.append(
            [
                "[bold]TOTAL[/bold]",
                "",
                f"[bold]{total_planned:,.2f}[/bold]",
                f"[bold]{total_actual:,.2f}[/bold]",
                f"[bold]{total_var:+,.2f}[/bold]",
            ]
        )
        json_result["lines"] = lines_json
        json_result["total_planned"] = total_planned
        json_result["total_actual"] = total_actual

        out.table(
            f"Budget Lines ({len(lines)})",
            [("Name", "cyan"), ("Account", ""), ("Planned", ""), ("Actual", ""), ("Variance", "")],
            rows,
            data_for_json=lines_json,
        )


# ===================================================================
# SUMMARY
# ===================================================================


@app.command("summary")
def summary(
    ctx: typer.Context,
    period: Annotated[str | None, typer.Option("--period", help="Filter by period substring (e.g. '2025')")] = None,
) -> None:
    """Overall budget utilization summary.

    Examples:
        kctl-odoo budget summary
        kctl-odoo budget summary --period 2025
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _BUDGET_MODEL):
        out.warn(_BUDGET_HINT)
        return

    domain: list = [("state", "in", ["confirm", "validate"])]
    if period:
        domain.append(("name", "ilike", period))

    try:
        records = c.search_read(  # type: ignore[attr-defined]
            _BUDGET_MODEL,
            domain=domain,
            fields=["name", "date_from", "date_to", "state"],
            order="date_from desc",
            limit=20,
        )
    except RPCError as e:
        out.error(f"Failed to fetch budgets for summary: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No active budgets found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        row_id = r["id"]
        try:
            lines = c.search_read(  # type: ignore[attr-defined]
                "budget.line",
                [("budget_id", "=", row_id)],
                ["planned_amount", "practical_amount"],
                limit=0,
            )
            planned = sum(ln.get("planned_amount", 0.0) or 0.0 for ln in lines)
            actual = sum(ln.get("practical_amount", 0.0) or 0.0 for ln in lines)
            pct = (actual / planned * 100) if planned else 0.0
        except RPCError:
            planned = actual = pct = 0.0

        rows.append([r.get("name", ""), str(r.get("state", "")), f"{planned:,.0f}", f"{actual:,.0f}", f"{pct:.1f}%"])
        json_data.append(
            {
                "name": r.get("name"),
                "state": r.get("state"),
                "planned": planned,
                "actual": actual,
                "utilization_pct": pct,
            }
        )

    out.table(
        "Budget Utilization Summary",
        [("Budget", "cyan"), ("State", ""), ("Planned", ""), ("Actual", ""), ("Utilization", "")],
        rows,
        data_for_json=json_data,
    )
