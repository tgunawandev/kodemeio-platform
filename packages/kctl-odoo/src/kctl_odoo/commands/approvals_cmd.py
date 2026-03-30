"""Approval center: pending requests, approve, reject, delegate."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Approval center: pending requests, approve, reject, delegate.")


def _m2o_name(val):
    if isinstance(val, list):
        return str(val[1])
    return str(val or "-")


def _has_tier_validation(c) -> bool:
    return model_available(c, "tier.review")


def _has_approval_management(c) -> bool:
    return model_available(c, "approval.delegation")


@app.command("summary")
def summary(ctx: typer.Context) -> None:
    """Show summary of pending approvals and SLA violations.

    Counts pending tier reviews and SLA violations (if approval_management installed).

    Examples:
        kctl-odoo approvals summary
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _has_tier_validation(c):
        out.warn("tier.review model not available. Install base_tier_validation OCA module.")
        raise typer.Exit(1)

    pending_count = c.search_count("tier.review", [("status", "=", "pending")])
    validated_count = c.search_count("tier.review", [("status", "=", "approved")])
    rejected_count = c.search_count("tier.review", [("status", "=", "rejected")])

    out.info(f"Pending approvals:  {pending_count}")
    out.info(f"Approved (total):   {validated_count}")
    out.info(f"Rejected (total):   {rejected_count}")

    # SLA violations if approval_management installed
    if model_available(c, "approval.sla.violation"):
        try:
            sla_violations = c.search_count("approval.sla.violation", [])
            out.info(f"SLA violations:     {sla_violations}")
        except (RPCError, Exception):
            pass

    if actx.json_mode:
        out.raw_json(
            {
                "pending": pending_count,
                "approved": validated_count,
                "rejected": rejected_count,
            }
        )


@app.command("pending")
def pending(
    ctx: typer.Context,
    review_type: Annotated[str | None, typer.Option("--type", "-t", help="Filter by review type / model")] = None,
    user: Annotated[str | None, typer.Option("--user", "-u", help="Filter by reviewer user name or ID")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum records to list")] = 50,
) -> None:
    """List pending tier review requests.

    Shows tier.review records in pending state with model, record ID, requester and date.

    Examples:
        kctl-odoo approvals pending
        kctl-odoo approvals pending --type sale.order
        kctl-odoo approvals pending --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _has_tier_validation(c):
        out.warn("tier.review model not available. Install base_tier_validation OCA module.")
        raise typer.Exit(1)

    domain: list = [("status", "=", "pending")]
    if review_type:
        domain.append(("model", "ilike", review_type))

    # User filter — look up user ID if string given
    if user:
        try:
            user_id = int(user)
            domain.append(("reviewer_ids", "in", [user_id]))
        except ValueError:
            users = c.search_read(
                "res.users",
                domain=[("name", "ilike", user)],
                fields=["id", "name"],
                limit=5,
            )
            if users:
                domain.append(("reviewer_ids", "in", [u["id"] for u in users]))
            else:
                out.warn(f"No users found matching '{user}'.")

    reviews = c.search_read(
        "tier.review",
        domain=domain,
        fields=["model", "res_id", "requested_by", "status", "create_date"],
        limit=limit,
        order="id desc",
    )

    if not reviews:
        out.info("No pending tier reviews found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    for r in reviews:
        requested_by = _m2o_name(r.get("requested_by"))
        date_val = r.get("create_date") or "-"
        rows.append(
            [
                str(r.get("id", "")),
                r.get("model", ""),
                str(r.get("res_id", "")),
                requested_by,
                r.get("status", ""),
                str(date_val)[:16],
            ]
        )

    out.table(
        f"Pending Tier Reviews ({len(reviews)} found)",
        [
            ("ID", "dim"),
            ("Model", "cyan"),
            ("Record ID", ""),
            ("Requested By", ""),
            ("Status", "yellow"),
            ("Date", "dim"),
        ],
        rows,
        data_for_json=reviews,
    )

    if actx.json_mode:
        out.raw_json(reviews)


@app.command("approve")
def approve(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Model name (e.g. sale.order)")],
    res_id: Annotated[int, typer.Argument(help="Record ID to approve")],
    comment: Annotated[str | None, typer.Option("--comment", "-c", help="Approval comment")] = None,
    force: Annotated[bool, typer.Option("--force", help="Force approval even if not reviewer")] = False,
) -> None:
    """Approve a tier validation for a record.

    Calls validate_tier on the given model record.

    Examples:
        kctl-odoo approvals approve sale.order 42
        kctl-odoo approvals approve sale.order 42 --comment "Approved by manager"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _has_tier_validation(c):
        out.warn("tier.review model not available. Install base_tier_validation OCA module.")
        raise typer.Exit(1)

    try:
        c.execute_kw(model, "validate_tier", [[res_id]])
        if comment:
            # Post a message with the comment
            with contextlib.suppress(RPCError, Exception):
                c.execute_kw(
                    model,
                    "message_post",
                    [[res_id]],
                    {"body": f"Approval comment: {comment}", "message_type": "comment"},
                )
        out.success(f"Approved: {model} #{res_id}")
    except RPCError as e:
        if force:
            out.warn(f"Approve failed (force mode): {e}")
        else:
            out.error(f"Failed to approve {model} #{res_id}: {e}")
            raise typer.Exit(1) from e
    except Exception as e:
        out.error(f"Failed to approve {model} #{res_id}: {e}")
        raise typer.Exit(1) from e

    if actx.json_mode:
        out.raw_json({"model": model, "res_id": res_id, "action": "approved"})


@app.command("reject")
def reject(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Model name (e.g. sale.order)")],
    res_id: Annotated[int, typer.Argument(help="Record ID to reject")],
    reason: Annotated[str | None, typer.Option("--reason", "-r", help="Rejection reason")] = None,
    force: Annotated[bool, typer.Option("--force", help="Force rejection even if not reviewer")] = False,
) -> None:
    """Reject a tier validation for a record.

    Calls reject_tier on the given model record.

    Examples:
        kctl-odoo approvals reject sale.order 42
        kctl-odoo approvals reject sale.order 42 --reason "Budget exceeded"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _has_tier_validation(c):
        out.warn("tier.review model not available. Install base_tier_validation OCA module.")
        raise typer.Exit(1)

    try:
        c.execute_kw(model, "reject_tier", [[res_id]])
        if reason:
            with contextlib.suppress(RPCError, Exception):
                c.execute_kw(
                    model,
                    "message_post",
                    [[res_id]],
                    {"body": f"Rejection reason: {reason}", "message_type": "comment"},
                )
        out.success(f"Rejected: {model} #{res_id}")
    except RPCError as e:
        if force:
            out.warn(f"Reject failed (force mode): {e}")
        else:
            out.error(f"Failed to reject {model} #{res_id}: {e}")
            raise typer.Exit(1) from e
    except Exception as e:
        out.error(f"Failed to reject {model} #{res_id}: {e}")
        raise typer.Exit(1) from e

    if actx.json_mode:
        out.raw_json({"model": model, "res_id": res_id, "action": "rejected"})


@app.command("delegate")
def delegate(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Model name (e.g. sale.order)")],
    res_id: Annotated[int, typer.Argument(help="Record ID")],
    to_user: Annotated[str, typer.Argument(help="Username or ID to delegate to")],
) -> None:
    """Delegate an approval to another user.

    Requires approval_management module. Falls back to a warning if not installed.

    Examples:
        kctl-odoo approvals delegate sale.order 42 john.doe
        kctl-odoo approvals delegate sale.order 42 5
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _has_approval_management(c):
        out.warn(
            "approval.delegation model not available. Delegation requires approval_management module to be installed."
        )
        raise typer.Exit(1)

    # Resolve user
    try:
        user_id = int(to_user)
    except ValueError:
        users = c.search_read(
            "res.users",
            domain=[("name", "ilike", to_user)],
            fields=["id", "name"],
            limit=1,
        )
        if not users:
            out.error(f"User not found: '{to_user}'")
            raise typer.Exit(1) from None
        user_id = users[0]["id"]
        out.info(f"Delegating to: {users[0]['name']} (ID: {user_id})")

    try:
        c.execute_kw(
            "approval.delegation",
            "create",
            [
                [
                    {
                        "model_name": model,
                        "res_id": res_id,
                        "delegate_user_id": user_id,
                    }
                ]
            ],
        )
        out.success(f"Delegated {model} #{res_id} to user #{user_id}")
    except RPCError as e:
        out.error(f"Failed to create delegation: {e}")
        raise typer.Exit(1) from e

    if actx.json_mode:
        out.raw_json({"model": model, "res_id": res_id, "delegated_to": user_id})


@app.command("history")
def history(
    ctx: typer.Context,
    user: Annotated[str | None, typer.Option("--user", "-u", help="Filter by user name or ID")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum records to list")] = 50,
) -> None:
    """List validated or rejected tier reviews (approval history).

    Examples:
        kctl-odoo approvals history
        kctl-odoo approvals history --user admin --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _has_tier_validation(c):
        out.warn("tier.review model not available. Install base_tier_validation OCA module.")
        raise typer.Exit(1)

    domain: list = [("status", "in", ["approved", "rejected"])]

    if user:
        try:
            user_id = int(user)
            domain.append(("reviewer_ids", "in", [user_id]))
        except ValueError:
            users = c.search_read(
                "res.users",
                domain=[("name", "ilike", user)],
                fields=["id", "name"],
                limit=5,
            )
            if users:
                domain.append(("reviewer_ids", "in", [u["id"] for u in users]))
            else:
                out.warn(f"No users found matching '{user}'.")

    reviews = c.search_read(
        "tier.review",
        domain=domain,
        fields=["model", "res_id", "requested_by", "status", "create_date"],
        limit=limit,
        order="id desc",
    )

    if not reviews:
        out.info("No approval history found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    for r in reviews:
        requested_by = _m2o_name(r.get("requested_by"))
        date_val = r.get("create_date") or "-"
        status = r.get("status", "")
        status_display = f"[green]{status}[/green]" if status == "approved" else f"[red]{status}[/red]"
        rows.append(
            [
                str(r.get("id", "")),
                r.get("model", ""),
                str(r.get("res_id", "")),
                requested_by,
                status_display,
                str(date_val)[:16],
            ]
        )

    out.table(
        f"Approval History ({len(reviews)} found)",
        [
            ("ID", "dim"),
            ("Model", "cyan"),
            ("Record ID", ""),
            ("Requested By", ""),
            ("Status", ""),
            ("Date", "dim"),
        ],
        rows,
        data_for_json=reviews,
    )

    if actx.json_mode:
        out.raw_json(reviews)


@app.command("sla-status")
def sla_status(ctx: typer.Context) -> None:
    """Show SLA statistics for approvals.

    Shows SLA violation details if approval_management is installed,
    otherwise shows a tier review summary by model.

    Examples:
        kctl-odoo approvals sla-status
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _has_tier_validation(c):
        out.warn("tier.review model not available. Install base_tier_validation OCA module.")
        raise typer.Exit(1)

    if model_available(c, "approval.sla.violation"):
        # Full SLA stats from approval_management
        try:
            violations = c.search_read(
                "approval.sla.violation",
                domain=[],
                fields=["name", "model", "res_id", "sla_deadline", "violated_at"],
                limit=50,
                order="violated_at desc",
            )
            if not violations:
                out.success("No SLA violations found.")
                return

            rows = []
            for v in violations:
                rows.append(
                    [
                        v.get("name", ""),
                        v.get("model", ""),
                        str(v.get("res_id", "")),
                        str(v.get("sla_deadline", "") or "")[:16],
                        str(v.get("violated_at", "") or "")[:16],
                    ]
                )

            out.table(
                f"SLA Violations ({len(violations)} found)",
                [
                    ("Name", ""),
                    ("Model", "cyan"),
                    ("Record ID", ""),
                    ("Deadline", "yellow"),
                    ("Violated At", "red"),
                ],
                rows,
                data_for_json=violations,
            )

            if actx.json_mode:
                out.raw_json(violations)
            return
        except (RPCError, Exception):
            pass

    # Fallback: tier review summary by model
    try:
        pending_reviews = c.search_read(
            "tier.review",
            domain=[("status", "=", "pending")],
            fields=["model", "res_id"],
            limit=500,
        )
    except (RPCError, Exception) as e:
        out.error(f"Failed to read tier reviews: {e}")
        raise typer.Exit(1) from None

    if not pending_reviews:
        out.success("No pending tier reviews.")
        return

    # Group by model
    model_counts: dict[str, int] = {}
    for r in pending_reviews:
        m = r.get("model", "unknown")
        model_counts[m] = model_counts.get(m, 0) + 1

    rows = [[model, str(count)] for model, count in sorted(model_counts.items(), key=lambda x: -x[1])]

    out.table(
        "Pending Reviews by Model",
        [("Model", "cyan"), ("Pending Count", "yellow")],
        rows,
        data_for_json=[{"model": m, "pending": c_} for m, c_ in model_counts.items()],
    )

    if actx.json_mode:
        out.raw_json([{"model": m, "pending": c_} for m, c_ in model_counts.items()])


@app.command("escalated")
def escalated(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum records to list")] = 50,
) -> None:
    """List tier reviews that are past their review deadline.

    Shows pending reviews that have been waiting longer than expected.

    Examples:
        kctl-odoo approvals escalated
        kctl-odoo approvals escalated --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _has_tier_validation(c):
        out.warn("tier.review model not available. Install base_tier_validation OCA module.")
        raise typer.Exit(1)

    # Consider reviews older than 2 days as escalated
    cutoff = (datetime.now(tz=UTC) - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")

    domain: list = [("status", "=", "pending"), ("create_date", "<=", cutoff)]
    try:
        reviews = c.search_read(
            "tier.review",
            domain=domain,
            fields=["model", "res_id", "requested_by", "status", "create_date"],
            limit=limit,
            order="create_date asc",
        )
    except (RPCError, Exception) as e:
        out.error(f"Failed to read escalated reviews: {e}")
        raise typer.Exit(1) from None

    if not reviews:
        out.success("No escalated tier reviews found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    for r in reviews:
        requested_by = _m2o_name(r.get("requested_by"))
        date_val = r.get("create_date") or "-"
        rows.append(
            [
                str(r.get("id", "")),
                r.get("model", ""),
                str(r.get("res_id", "")),
                requested_by,
                str(date_val)[:16],
            ]
        )

    out.table(
        f"Escalated Reviews ({len(reviews)} found — pending >2 days)",
        [
            ("ID", "dim"),
            ("Model", "cyan"),
            ("Record ID", ""),
            ("Requested By", ""),
            ("Date", "red"),
        ],
        rows,
        data_for_json=reviews,
    )

    if actx.json_mode:
        out.raw_json(reviews)
