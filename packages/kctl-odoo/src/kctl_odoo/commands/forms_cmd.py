"""Form management commands — types, submissions, approvals."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Form requests: types, submissions, approval.")

_FORM_TYPE_MODEL = "form.type"
_FORM_REQUEST_MODEL = "form.request"
_FORM_HINT = "Form management module (form_management) is not installed."


def _m2o_name(val: object) -> str:
    if isinstance(val, list):
        return str(val[1])
    return str(val or "-")


# ===================================================================
# TYPES
# ===================================================================


@app.command("types")
def types(ctx: typer.Context) -> None:
    """List available form types.

    Examples:
        kctl-odoo forms types
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _FORM_TYPE_MODEL):
        out.warn(_FORM_HINT)
        return

    preferred_fields = ["display_name", "code", "active"]
    try:
        records = c.search_read(  # type: ignore[attr-defined]
            _FORM_TYPE_MODEL,
            domain=[],
            fields=preferred_fields,
            order="display_name asc",
        )
    except RPCError:
        try:
            records = c.search_read(  # type: ignore[attr-defined]
                _FORM_TYPE_MODEL,
                domain=[],
                fields=["display_name", "create_date"],
            )
        except RPCError as e:
            out.error(f"Failed to list form types: {e}")
            raise typer.Exit(1) from e

    if not records:
        out.info("No form types found.")
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
                str(r.get("code", "")),
                "Yes" if r.get("active") else "No",
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "display_name": r.get("display_name"),
                "code": r.get("code"),
                "active": r.get("active"),
            }
        )

    out.table(
        f"Form Types ({len(records)})",
        [("ID", "dim"), ("Name", "cyan"), ("Code", ""), ("Active", "")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# PENDING
# ===================================================================


@app.command("pending")
def pending(
    ctx: typer.Context,
    form_type: Annotated[str | None, typer.Option("--type", help="Filter by form type name (ilike)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List pending/draft form requests awaiting action.

    Examples:
        kctl-odoo forms pending
        kctl-odoo forms pending --type "Leave Request" --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _FORM_REQUEST_MODEL):
        out.warn(_FORM_HINT)
        return

    domain: list = [("state", "in", ["draft", "pending"])]
    if form_type:
        domain.append(("type_id.name", "ilike", form_type))

    preferred_fields = ["display_name", "form_type_id", "state", "create_date", "user_id"]
    try:
        records = c.search_read(  # type: ignore[attr-defined]
            _FORM_REQUEST_MODEL,
            domain=domain,
            fields=preferred_fields,
            limit=limit,
            order="create_date desc",
        )
    except RPCError:
        try:
            records = c.search_read(  # type: ignore[attr-defined]
                _FORM_REQUEST_MODEL,
                domain=domain,
                fields=["display_name", "state", "create_date"],
                limit=limit,
                order="create_date desc",
            )
        except RPCError as e:
            out.error(f"Failed to list pending form requests: {e}")
            raise typer.Exit(1) from e

    if not records:
        out.info("No pending form requests found.")
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
                _m2o_name(r.get("form_type_id")),
                _m2o_name(r.get("user_id")),
                str(r.get("state", "")),
                str(r.get("create_date", "")),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "display_name": r.get("display_name"),
                "form_type": _m2o_name(r.get("form_type_id")),
                "user": _m2o_name(r.get("user_id")),
                "state": r.get("state"),
                "create_date": r.get("create_date"),
            }
        )

    out.table(
        f"Pending Form Requests ({len(records)})",
        [("ID", "dim"), ("Name", "cyan"), ("Type", ""), ("Requested By", ""), ("State", ""), ("Created", "dim")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# GET
# ===================================================================


@app.command("get")
def get(
    ctx: typer.Context,
    request_id: Annotated[int, typer.Argument(help="Form request ID")],
) -> None:
    """Show form request detail with lines and attachments.

    Examples:
        kctl-odoo forms get 42
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _FORM_REQUEST_MODEL):
        out.warn(_FORM_HINT)
        return

    preferred_fields = ["display_name", "form_type_id", "user_id", "state", "create_date", "line_ids", "attachment_ids"]
    try:
        records = c.read(  # type: ignore[attr-defined]
            _FORM_REQUEST_MODEL,
            [request_id],
            preferred_fields,
        )
    except RPCError:
        try:
            records = c.read(  # type: ignore[attr-defined]
                _FORM_REQUEST_MODEL,
                [request_id],
                ["display_name", "state", "create_date"],
            )
        except RPCError as e:
            out.error(f"Failed to fetch form request {request_id}: {e}")
            raise typer.Exit(1) from e

    if not records:
        out.error(f"Form request not found: {request_id}")
        raise typer.Exit(1)

    rec = records[0]
    sections = [
        (
            "Form Request",
            [
                ("ID", str(rec["id"])),
                ("Name", rec.get("display_name", "")),
                ("Type", _m2o_name(rec.get("form_type_id"))),
                ("Requested By", _m2o_name(rec.get("user_id"))),
                ("State", str(rec.get("state", ""))),
                ("Created", str(rec.get("create_date", ""))),
                ("Lines", str(len(rec.get("line_ids", [])))),
                ("Attachments", str(len(rec.get("attachment_ids", [])))),
            ],
        )
    ]

    json_result: dict = {
        "id": rec["id"],
        "display_name": rec.get("display_name"),
        "form_type": _m2o_name(rec.get("form_type_id")),
        "user": _m2o_name(rec.get("user_id")),
        "state": rec.get("state"),
        "create_date": rec.get("create_date"),
    }

    out.detail("Form Request Detail", sections, data_for_json=json_result)


# ===================================================================
# APPROVE
# ===================================================================


@app.command("approve")
def approve(
    ctx: typer.Context,
    request_id: Annotated[int, typer.Argument(help="Form request ID")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation")] = False,
) -> None:
    """Approve a form request.

    Examples:
        kctl-odoo forms approve 42
        kctl-odoo forms approve 42 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _FORM_REQUEST_MODEL):
        out.warn(_FORM_HINT)
        return

    if not force and not typer.confirm(f"Approve form request {request_id}?"):
        raise typer.Exit(0)

    try:
        c.execute_kw(  # type: ignore[attr-defined]
            _FORM_REQUEST_MODEL, "action_approve", [[request_id]]
        )
    except RPCError:
        try:
            c.execute_kw(  # type: ignore[attr-defined]
                _FORM_REQUEST_MODEL, "action_confirm", [[request_id]]
            )
        except RPCError:
            try:
                c.write(_FORM_REQUEST_MODEL, [request_id], {"state": "approved"})  # type: ignore[attr-defined]
            except RPCError as e:
                out.error(f"Failed to approve form request {request_id}: {e}")
                raise typer.Exit(1) from e

    out.success(f"Form request {request_id} approved.")
    if actx.json_mode:
        out.raw_json({"id": request_id, "action": "approved"})


# ===================================================================
# REJECT
# ===================================================================


@app.command("reject")
def reject(
    ctx: typer.Context,
    request_id: Annotated[int, typer.Argument(help="Form request ID")],
    reason: Annotated[str | None, typer.Option("--reason", help="Rejection reason")] = None,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation")] = False,
) -> None:
    """Reject a form request.

    Examples:
        kctl-odoo forms reject 42 --reason "Missing documentation"
        kctl-odoo forms reject 42 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _FORM_REQUEST_MODEL):
        out.warn(_FORM_HINT)
        return

    if not force and not typer.confirm(f"Reject form request {request_id}?"):
        raise typer.Exit(0)

    try:
        if reason:
            # Try to write the reason field — ignore if field doesn't exist
            try:
                c.write(_FORM_REQUEST_MODEL, [request_id], {"rejection_reason": reason})  # type: ignore[attr-defined]
            except RPCError:
                pass
        try:
            c.execute_kw(  # type: ignore[attr-defined]
                _FORM_REQUEST_MODEL, "action_reject", [[request_id]]
            )
        except RPCError:
            try:
                c.execute_kw(  # type: ignore[attr-defined]
                    _FORM_REQUEST_MODEL, "action_refuse", [[request_id]]
                )
            except RPCError:
                c.write(_FORM_REQUEST_MODEL, [request_id], {"state": "rejected"})  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to reject form request {request_id}: {e}")
        raise typer.Exit(1) from e

    out.success(f"Form request {request_id} rejected.")
    if actx.json_mode:
        out.raw_json({"id": request_id, "action": "rejected", "reason": reason})
