"""Accurate → Odoo 1-click migration commands.

Thin wrappers over accurate.company JSON-RPC methods. Business logic
lives in the Odoo addon (`accurate_integration`); this CLI is a skin
over the same durable state machine that the UI drives.

See docs/superpowers/specs/2026-04-19-accurate-1click-migration-spine-design.md
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext

app = typer.Typer(help="Accurate → Odoo 1-click migration.")


def _resolve_accurate_company(client: object, identifier: str) -> dict:
    """Find an accurate.company by slug or numeric ID. Returns full record."""
    recs = client.search_read(  # type: ignore[attr-defined]
        "accurate.company",
        domain=[
            "|",
            ("slug", "=", identifier),
            ("id", "=", int(identifier)) if identifier.isdigit() else ("id", "=", 0),
        ],
        fields=[
            "id",
            "name",
            "slug",
            "db_id",
            "state",
            "current_phase",
            "current_phase_state",
            "progress_percent",
            "last_sync_at",
            "sync_enabled",
            "odoo_company_id",
        ],
        limit=1,
    )
    if not recs:
        raise typer.BadParameter(f"Accurate company not found: {identifier}")
    return recs[0]


# --- companies ---------------------------------------------------------


companies_app = typer.Typer(help="Manage Accurate company registrations.")


@companies_app.command("list")
def companies_list(
    ctx: typer.Context,
    state: Annotated[
        str | None,
        typer.Option("--state", "-s", help="Filter by state"),
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-l")] = 80,
) -> None:
    """List registered Accurate companies."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain = []
    if state:
        domain.append(("state", "=", state))

    recs = c.search_read(
        "accurate.company",
        domain=domain,
        fields=[
            "id",
            "slug",
            "name",
            "state",
            "current_phase",
            "progress_percent",
            "last_sync_at",
        ],
        limit=limit,
        order="name",
    )
    rows = [
        [
            str(r["id"]),
            r["slug"],
            r["name"],
            r["state"],
            r.get("current_phase") or "-",
            f"{r.get('progress_percent', 0)}%",
            str(r.get("last_sync_at") or "-"),
        ]
        for r in recs
    ]
    out.table(
        f"Accurate Companies ({len(recs)})",
        [
            ("ID", "cyan"),
            ("Slug", ""),
            ("Name", ""),
            ("State", ""),
            ("Phase", "dim"),
            ("Progress", "dim"),
            ("Last Sync", "dim"),
        ],
        rows,
        data_for_json=recs,
    )


@companies_app.command("show")
def companies_show(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Slug or ID")],
) -> None:
    """Show details for one Accurate company."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    rec = _resolve_accurate_company(c, identifier)
    # phase history
    phases = c.search_read(
        "accurate.company.phase",
        domain=[("company_id", "=", rec["id"])],
        fields=[
            "phase_code",
            "state",
            "started_at",
            "completed_at",
            "duration_s",
            "triggered_by",
        ],
        order="create_date desc",
        limit=20,
    )

    out.section(f"{rec['name']} ({rec['slug']})")
    out.kv(
        [
            ("State", rec["state"]),
            ("Current Phase", rec.get("current_phase") or "-"),
            ("Phase State", rec.get("current_phase_state") or "-"),
            ("Progress", f"{rec.get('progress_percent', 0)}%"),
            ("Sync Enabled", "yes" if rec.get("sync_enabled") else "no"),
            ("Last Sync", str(rec.get("last_sync_at") or "-")),
        ]
    )
    if phases:
        rows = [
            [
                p["phase_code"],
                p["state"],
                str(p.get("started_at") or "-"),
                str(p.get("completed_at") or "-"),
                f"{p.get('duration_s', 0):.1f}s",
            ]
            for p in phases
        ]
        out.table(
            "Recent Phases",
            [("Phase", ""), ("State", ""), ("Started", "dim"), ("Finished", "dim"), ("Dur", "dim")],
            rows,
        )


# --- phases ------------------------------------------------------------


@app.command("preflight")
def preflight(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Accurate company slug or ID")],
) -> None:
    """Run Phase 1 Preflight checks."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    rec = _resolve_accurate_company(c, identifier)
    out.info(f"Running preflight for {rec['slug']}...")
    report = c.execute_kw("accurate.company", "action_run_preflight", [[rec["id"]]])

    # report is either the return dict or None (if write-only model method)
    # action_run_preflight returns the report dict per our implementation
    if not isinstance(report, dict):
        # Refresh to read the persisted summary
        updated = c.search_read(
            "accurate.company.phase",
            domain=[
                ("company_id", "=", rec["id"]),
                ("phase_code", "=", "preflight"),
            ],
            fields=["state", "summary_json"],
            order="create_date desc",
            limit=1,
        )
        if updated and updated[0].get("summary_json"):
            report = json.loads(updated[0]["summary_json"])
        else:
            report = {"checks": [], "all_blockers_passed": False}

    rows = []
    for chk in report.get("checks", []):
        rows.append(
            [
                chk["name"],
                "✓" if chk["passed"] else "✗",
                chk["severity"],
                (chk.get("message") or "")[:80],
            ]
        )
    out.table(
        "Preflight Results",
        [("Check", ""), ("Result", ""), ("Severity", "dim"), ("Message", "dim")],
        rows,
    )
    if not report.get("all_blockers_passed"):
        out.error("Preflight BLOCKED — resolve issues and re-run.")
        raise typer.Exit(1)
    out.success("Preflight PASSED — ready for Setup phase.")


@app.command("setup")
def setup(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Accurate company slug or ID")],
    coa_template: Annotated[
        str,
        typer.Option(
            "--coa-template",
            help="Odoo CoA template XML ID to install",
        ),
    ] = "l10n_id.l10n_id_chart_template_amd",
) -> None:
    """Run Phase 2 Setup — install CoA + resolve PPh accounts."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    rec = _resolve_accurate_company(c, identifier)
    out.info(f"Running setup for {rec['slug']} (CoA: {coa_template})...")
    summary = c.execute_kw(
        "accurate.company",
        "action_run_setup",
        [[rec["id"]]],
        {"coa_template_xmlid": coa_template},
    )
    out.success("Setup PASSED.")
    out.kv(
        [
            ("CoA Installed", str(summary.get("coa_installed", "-"))),
            ("Mapping Rows Seeded", str(summary.get("mapping_rows_seeded", 0))),
        ]
    )
    pph = summary.get("pph_accounts") or {}
    if pph:
        rows = []
        for field_name, val in pph.items():
            if val:
                rows.append([field_name, val.get("code", "-"), val.get("name", "-")])
            else:
                rows.append([field_name, "-", "NOT FOUND"])
        out.table(
            "PPh Accounts Resolved",
            [("Type", ""), ("Code", ""), ("Name", "dim")],
            rows,
        )


@app.command("phases")
def phases(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Accurate company slug or ID")],
    phase: Annotated[
        str | None,
        typer.Option("--phase", help="Filter by phase_code"),
    ] = None,
    state: Annotated[
        str | None,
        typer.Option("--state", help="Filter by state"),
    ] = None,
) -> None:
    """Show phase execution history for one Accurate company."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    rec = _resolve_accurate_company(c, identifier)
    domain = [("company_id", "=", rec["id"])]
    if phase:
        domain.append(("phase_code", "=", phase))
    if state:
        domain.append(("state", "=", state))
    phases_ = c.search_read(
        "accurate.company.phase",
        domain=domain,
        fields=[
            "phase_code",
            "state",
            "started_at",
            "completed_at",
            "duration_s",
            "triggered_by",
            "error_log",
        ],
        order="create_date desc",
        limit=50,
    )
    rows = []
    for p in phases_:
        rows.append(
            [
                p["phase_code"],
                p["state"],
                str(p.get("started_at") or "-"),
                f"{p.get('duration_s', 0):.1f}s",
                (p.get("error_log") or "")[:50],
            ]
        )
    out.table(
        f"Phase History — {rec['slug']} ({len(phases_)})",
        [("Phase", ""), ("State", ""), ("Started", "dim"), ("Dur", "dim"), ("Error", "dim")],
        rows,
        data_for_json=phases_,
    )


# --- cutover ------------------------------------------------------------


@app.command("cutover")
def cutover(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Slug or ID")],
    cutover_date: Annotated[str, typer.Option("--date", help="YYYY-MM-DD")],
    mode: Annotated[str, typer.Option("--mode")] = "cutover",
) -> None:
    """Phase 3 Cutover Config — commits the cutover date + mode."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    rec = _resolve_accurate_company(c, identifier)
    out.info(f"Configuring cutover for {rec['slug']} — date={cutover_date} mode={mode}")
    summary = c.execute_kw(
        "accurate.company",
        "action_run_cutover_config",
        [[rec["id"]]],
        {"cutover_date": cutover_date, "mode": mode},
    )
    out.success("Cutover config committed.")
    out.kv(
        [
            ("Cutover Date", summary.get("cutover_date", "-")),
            ("Current FY Start", summary.get("current_fy_start", "-")),
            ("Mode", summary.get("mode", "-")),
        ]
    )


# --- foundation --------------------------------------------------------


@app.command("foundation")
def foundation(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Slug or ID")],
) -> None:
    """Phase 4 Foundation Sync."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    rec = _resolve_accurate_company(c, identifier)
    out.info(f"Running Foundation sync for {rec['slug']}...")
    try:
        summary = c.execute_kw("accurate.company", "action_run_foundation", [[rec["id"]]])
    except Exception as exc:
        out.error(f"Foundation failed: {exc}")
        raise typer.Exit(1)
    out.success("Foundation PASSED.")
    mods = summary.get("modules", {})
    rows = [[name, str(v)] for name, v in mods.items()]
    out.table("Foundation Modules", [("Module", ""), ("Result", "")], rows)


# --- transactions ------------------------------------------------------


@app.command("transactions")
def transactions(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Slug or ID")],
    phase: Annotated[str, typer.Option("--phase", help="prior|current|both")] = "both",
) -> None:
    """Phase 5+6 Transaction imports."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    rec = _resolve_accurate_company(c, identifier)
    if phase in ("prior", "both"):
        out.info("Running Transactions — Prior-FY Opens...")
        c.execute_kw("accurate.company", "action_run_transactions_prior", [[rec["id"]]])
        out.success("Prior-FY opens imported.")
    if phase in ("current", "both"):
        out.info("Running Transactions — Current FY...")
        c.execute_kw("accurate.company", "action_run_transactions_current", [[rec["id"]]])
        out.success("Current-FY transactions imported.")


# --- verify / sign-off / go-live ---------------------------------------


@app.command("verify")
def verify(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Slug or ID")],
) -> None:
    """Phase 7 Verification — generates parity report."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    rec = _resolve_accurate_company(c, identifier)
    out.info(f"Generating verification report for {rec['slug']}...")
    report_id = c.execute_kw("accurate.company", "action_run_verification", [[rec["id"]]])
    # Read report back
    if isinstance(report_id, dict):
        report_id = report_id.get("id")
    elif hasattr(report_id, "id"):
        report_id = report_id.id
    if not isinstance(report_id, int):
        # The method returns the report record — some RPC flavours return {}
        rep = c.search_read(
            "accurate.verification.report",
            domain=[("company_id", "=", rec["id"])],
            fields=["id", "all_passed"],
            limit=1,
            order="create_date desc",
        )
        if not rep:
            out.error("No verification report found.")
            raise typer.Exit(1)
        report_id = rep[0]["id"]
    lines = c.search_read(
        "accurate.verification.line",
        domain=[("report_id", "=", report_id)],
        fields=["check_name", "scope", "accurate_value", "odoo_value", "delta", "passed", "message"],
        order="sequence,id",
    )
    rows = [
        [
            l["check_name"],
            l.get("scope") or "-",
            l.get("accurate_value") or "-",
            l.get("odoo_value") or "-",
            l.get("delta") or "-",
            "✓" if l["passed"] else "✗",
            (l.get("message") or "")[:60],
        ]
        for l in lines
    ]
    out.table(
        f"Verification Report ({len(lines)} checks)",
        [("Check", ""), ("Scope", ""), ("Accurate", ""), ("Odoo", ""), ("Delta", ""), ("Pass", ""), ("Message", "dim")],
        rows,
    )
    failed = [l for l in lines if not l["passed"]]
    if failed:
        out.error(f"{len(failed)} checks FAILED — resolve before sign-off.")
        raise typer.Exit(1)
    out.success("All checks PASSED.")


@app.command("sign-off")
def sign_off(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Slug or ID")],
    confirm: Annotated[bool, typer.Option("--confirm")] = False,
) -> None:
    """Sign off verification — required before go-live."""
    if not confirm:
        raise typer.BadParameter("Add --confirm to proceed (destructive gate).")
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    rec = _resolve_accurate_company(c, identifier)
    c.execute_kw("accurate.company", "action_sign_off_verification", [[rec["id"]]])
    out.success(f"Verification signed off for {rec['slug']} by {actx.username_override or 'current user'}.")


@app.command("go-live")
def go_live(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Slug or ID")],
) -> None:
    """Phase 8 Go-Live — enable cron sync, state=live."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    rec = _resolve_accurate_company(c, identifier)
    c.execute_kw("accurate.company", "action_run_go_live", [[rec["id"]]])
    out.success(f"{rec['slug']} is LIVE — incremental cron sync enabled.")


@app.command("attachments")
def attachments(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Slug or ID")],
) -> None:
    """Phase 9 Attachments — migrate Accurate attachments to ir.attachment.

    Optional phase. Requires accurate.company.attachments_enabled=True.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    rec = _resolve_accurate_company(c, identifier)
    out.info(f"Running attachments phase for {rec['slug']}...")
    try:
        summary = c.execute_kw(
            "accurate.company",
            "action_run_attachments",
            [[rec["id"]]],
        )
    except Exception as exc:
        out.error(f"Attachments failed: {exc}")
        raise typer.Exit(1)
    if summary and summary.get("skipped"):
        out.warn("Attachments phase skipped — attachments_enabled=False.")
    else:
        out.success("Attachments phase complete.")
        if isinstance(summary, dict):
            out.kv(
                [
                    ("Migrated", str(summary.get("migrated_count", 0))),
                    ("Skipped", str(summary.get("skipped_count", 0))),
                ]
            )


# --- migrate convenience -----------------------------------------------


@app.command("migrate")
def migrate(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Slug or ID")],
    until: Annotated[str, typer.Option("--until", help="Stop at this phase")] = "verify",
) -> None:
    """Run phases in sequence up to --until (default: verify, stopping before sign-off)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    rec = _resolve_accurate_company(c, identifier)
    sequence = [
        ("preflight", "action_run_preflight"),
        ("setup", "action_run_setup"),
        ("cutover", "action_run_cutover_config"),
        ("foundation", "action_run_foundation"),
        ("transactions_prior", "action_run_transactions_prior"),
        ("transactions_current", "action_run_transactions_current"),
        ("attachments", "action_run_attachments"),
        ("verify", "action_run_verification"),
        ("go-live", "action_run_go_live"),
    ]
    for label, method in sequence:
        if label == "cutover":
            out.warn("`migrate` cannot run cutover non-interactively — call `cutover` manually first.")
            if not rec.get("current_phase") or rec.get("current_phase") == "preflight":
                out.error("Cutover not yet configured; aborting.")
                raise typer.Exit(2)
            continue
        out.info(f"→ {label}")
        try:
            c.execute_kw("accurate.company", method, [[rec["id"]]])
        except Exception as exc:
            out.error(f"{label} FAILED: {exc}")
            raise typer.Exit(1)
        if label == until:
            out.success(f"Stopped at {until} as requested.")
            return
    out.success("All phases complete.")


# --- errors ------------------------------------------------------------


errors_app = typer.Typer(help="Migration-error inspection and bulk retry.")


@errors_app.command("list")
def errors_list(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Company slug or ID")],
    error_kind: Annotated[
        str | None,
        typer.Option("--error-kind", help="Filter by error_kind"),
    ] = None,
    error_class: Annotated[
        str | None,
        typer.Option(
            "--error-class",
            help="transient|rate_limited|data_integrity|config_broken|unknown",
        ),
    ] = None,
    retry_status: Annotated[
        str | None,
        typer.Option("--retry-status", help="pending|ignored|retried|succeeded|abandoned"),
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-l")] = 50,
) -> None:
    """List migration errors for a company."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    rec = _resolve_accurate_company(c, identifier)
    domain = [("company_id", "=", rec["id"])]
    if error_kind:
        domain.append(("error_kind", "=", error_kind))
    if error_class:
        domain.append(("error_class", "=", error_class))
    if retry_status:
        domain.append(("retry_status", "=", retry_status))
    errors = c.search_read(
        "accurate.migration.error",
        domain=domain,
        fields=[
            "id",
            "module",
            "accurate_id",
            "error_class",
            "error_kind",
            "error_message",
            "retry_status",
            "retry_count",
            "create_date",
        ],
        limit=limit,
        order="create_date desc",
    )
    rows = [
        [
            str(e["id"]),
            e["module"],
            str(e.get("accurate_id") or "-"),
            e["error_class"],
            e.get("error_kind") or "-",
            (e.get("error_message") or "")[:40],
            e["retry_status"],
            str(e.get("retry_count") or 0),
        ]
        for e in errors
    ]
    out.table(
        f"Migration Errors — {rec['slug']} ({len(errors)})",
        [
            ("ID", "cyan"),
            ("Module", ""),
            ("Accurate ID", "dim"),
            ("Class", ""),
            ("Kind", "dim"),
            ("Message", "dim"),
            ("Retry Status", ""),
            ("Retries", "dim"),
        ],
        rows,
        data_for_json=errors,
    )


@errors_app.command("retry")
def errors_retry(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Company slug or ID")],
    ids: Annotated[
        str | None,
        typer.Option("--ids", help="Comma-separated error IDs"),
    ] = None,
    error_kind: Annotated[
        str | None,
        typer.Option("--error-kind", help="Retry all errors matching this kind"),
    ] = None,
) -> None:
    """Retry selected errors (by IDs or filtered by error_kind)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    rec = _resolve_accurate_company(c, identifier)
    domain = [("company_id", "=", rec["id"]), ("retry_status", "=", "pending")]
    if ids:
        id_list = [int(x) for x in ids.split(",") if x.strip()]
        domain.append(("id", "in", id_list))
    elif error_kind:
        domain.append(("error_kind", "=", error_kind))
    else:
        out.error("Provide either --ids or --error-kind to select errors to retry.")
        raise typer.Exit(2)
    error_ids = c.search("accurate.migration.error", domain=domain, limit=500)
    if not error_ids:
        out.warn("No matching errors found.")
        return
    c.execute_kw(
        "accurate.migration.error",
        "action_retry_selected",
        [error_ids],
    )
    out.success(f"Queued retry of {len(error_ids)} error(s) for {rec['slug']}.")


@errors_app.command("ignore")
def errors_ignore(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Company slug or ID")],
    ids: Annotated[str, typer.Option("--ids", help="Comma-separated error IDs")],
    reason: Annotated[str, typer.Option("--reason", help="Ignore reason (audit trail)")],
) -> None:
    """Mark selected errors as ignored (exclude from phase-failure threshold)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    rec = _resolve_accurate_company(c, identifier)
    id_list = [int(x) for x in ids.split(",") if x.strip()]
    if not id_list:
        out.error("Empty --ids.")
        raise typer.Exit(2)
    # Verify all belong to this company
    belong = c.search(
        "accurate.migration.error",
        domain=[("id", "in", id_list), ("company_id", "=", rec["id"])],
    )
    if len(belong) != len(id_list):
        out.error(f"Some IDs do not belong to {rec['slug']} (found {len(belong)} of {len(id_list)}).")
        raise typer.Exit(2)
    c.write("accurate.migration.error", id_list, {"retry_status": "ignored", "ignore_reason": reason})
    out.success(f"Marked {len(id_list)} error(s) as ignored for {rec['slug']}.")


# --- attach sub-apps ---------------------------------------------------


app.add_typer(companies_app, name="companies")
app.add_typer(errors_app, name="errors")
