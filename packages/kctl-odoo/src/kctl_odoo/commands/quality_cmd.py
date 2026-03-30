"""Quality management commands — checks, inspections, alerts."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Quality control: checks, inspections, alerts.")

_QUALITY_CHECK_MODEL = "quality.check"
_QUALITY_INSPECTION_MODEL = "quality.inspection"
_QUALITY_HINT = "Quality management module (quality_management or quality_control) is not installed."


def _m2o_name(val: object) -> str:
    if isinstance(val, list):
        return str(val[1])
    return str(val or "-")


def _get_quality_model(c: object) -> tuple[str, list[str]]:
    """Return available quality model and its fields."""
    if model_available(c, _QUALITY_CHECK_MODEL):
        return _QUALITY_CHECK_MODEL, ["display_name", "product_id", "quality_state", "result"]
    if model_available(c, _QUALITY_INSPECTION_MODEL):
        return _QUALITY_INSPECTION_MODEL, ["display_name", "product_id", "state", "result"]
    return "", []


# ===================================================================
# CHECKS
# ===================================================================


@app.command("checks")
def checks(
    ctx: typer.Context,
    state: Annotated[str | None, typer.Option("--state", help="Filter by state: none, pass, fail")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List quality checks or inspections.

    Examples:
        kctl-odoo quality checks
        kctl-odoo quality checks --state fail --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    model, fields = _get_quality_model(c)
    if not model:
        out.warn(_QUALITY_HINT)
        return

    domain: list = []
    state_field = "quality_state" if model == _QUALITY_CHECK_MODEL else "state"
    if state:
        domain.append((state_field, "=", state))

    try:
        records = c.search_read(  # type: ignore[attr-defined]
            model,
            domain=domain,
            fields=fields,
            limit=limit,
            order="id desc",
        )
    except RPCError:
        try:
            records = c.search_read(  # type: ignore[attr-defined]
                model,
                domain=domain,
                fields=["display_name", "create_date"],
                limit=limit,
                order="id desc",
            )
        except RPCError as e:
            out.error(f"Failed to list quality records: {e}")
            raise typer.Exit(1) from e

    if not records:
        out.info("No quality records found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        record_state = r.get("quality_state") or r.get("state") or ""
        rows.append(
            [
                str(r["id"]),
                r.get("display_name", ""),
                _m2o_name(r.get("product_id")),
                str(record_state),
                str(r.get("result", "")),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "display_name": r.get("display_name"),
                "product": _m2o_name(r.get("product_id")),
                "state": record_state,
                "result": r.get("result"),
            }
        )

    out.table(
        f"Quality Checks ({len(records)}) [{model}]",
        [("ID", "dim"), ("Name", "cyan"), ("Product", ""), ("State", ""), ("Result", "")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# ALERTS
# ===================================================================


@app.command("alerts")
def alerts(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List quality checks/inspections in failed state.

    Examples:
        kctl-odoo quality alerts
        kctl-odoo quality alerts --limit 10
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    model, fields = _get_quality_model(c)
    if not model:
        out.warn(_QUALITY_HINT)
        return

    state_field = "quality_state" if model == _QUALITY_CHECK_MODEL else "state"
    domain = [(state_field, "=", "fail")]

    try:
        records = c.search_read(  # type: ignore[attr-defined]
            model,
            domain=domain,
            fields=fields,
            limit=limit,
            order="id desc",
        )
    except RPCError:
        try:
            records = c.search_read(  # type: ignore[attr-defined]
                model,
                domain=domain,
                fields=["display_name", "create_date"],
                limit=limit,
                order="id desc",
            )
        except RPCError as e:
            out.error(f"Failed to list quality alerts: {e}")
            raise typer.Exit(1) from e

    if not records:
        out.info("No quality failures found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                str(r["id"]),
                r.get("display_name", ""),
                _m2o_name(r.get("product_id")),
                str(r.get("result", "")),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "display_name": r.get("display_name"),
                "product": _m2o_name(r.get("product_id")),
                "result": r.get("result"),
            }
        )

    out.table(
        f"Quality Alerts - Failures ({len(records)})",
        [("ID", "dim"), ("Name", "red"), ("Product", ""), ("Result", "")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# STATS
# ===================================================================


@app.command("stats")
def stats(ctx: typer.Context) -> None:
    """Quality statistics: count by state (pass/fail/pending).

    Examples:
        kctl-odoo quality stats
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    model, _ = _get_quality_model(c)
    if not model:
        out.warn(_QUALITY_HINT)
        return

    state_field = "quality_state" if model == _QUALITY_CHECK_MODEL else "state"

    try:
        total = c.search_count(model, [])
    except RPCError as e:
        out.error(f"Failed to fetch quality stats: {e}")
        raise typer.Exit(1) from e

    if total == 0:
        out.info("No quality records found.")
        if actx.json_mode:
            out.raw_json({"total": 0})
        return

    # Count by state using search_count (read_group not available via JSON-RPC)
    rows = []
    json_data = []
    states = [("pass", "Pass"), ("fail", "Fail"), ("pending", "Pending"), ("draft", "Draft"), ("done", "Done")]
    for state_val, state_label in states:
        try:
            count = c.search_count(model, [(state_field, "=", state_val)])
        except (RPCError, Exception):
            count = 0
        if count > 0:
            pct = f"{count / total * 100:.1f}%" if total else "0%"
            color = "red" if state_val == "fail" else "green" if state_val == "pass" else ""
            display = f"[{color}]{state_label}[/{color}]" if color else state_label
            rows.append([display, str(count), pct])
            json_data.append({"state": state_val, "count": count})

    rows.append(["[bold]TOTAL[/bold]", f"[bold]{total}[/bold]", "100%"])

    out.table(
        f"Quality Statistics [{model}]",
        [("State", ""), ("Count", "cyan"), ("Percentage", "")],
        rows,
        data_for_json={"states": json_data, "total": total},
    )
