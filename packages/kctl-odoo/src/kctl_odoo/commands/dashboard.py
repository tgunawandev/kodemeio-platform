"""Dashboard command — comprehensive overview of the Odoo instance."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available, module_hint
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Instance dashboard and overview.")


def _safe_count(client, model: str, domain: list | None = None) -> int | None:
    """Search count that returns None if model doesn't exist."""
    try:
        return client.search_count(model, domain or [])
    except RPCError:
        return None


@app.command()
def info(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously refresh the dashboard")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Watch interval in seconds")] = 30,
) -> None:
    """Show comprehensive Odoo instance overview.

    Displays server health, module status, mail queue, cron health,
    queue jobs, storage, and business pulse in a single view.

    Examples:
        kctl-odoo dashboard info
        kctl-odoo --profile production dashboard info
        kctl-odoo dashboard info --json
        kctl-odoo dashboard info --watch
        kctl-odoo dashboard info --watch --interval 60
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    def _run_once() -> None:
        sections: list[tuple[str, list[tuple[str, str]]]] = []
        json_data: dict = {}

        # ── Server & Health ──
        start = time.monotonic()
        ver_info = c.version_info()
        rpc_ms = round((time.monotonic() - start) * 1000)
        uid = c.authenticate()

        users = c.read("res.users", [uid], ["login", "name", "company_id"])
        current_user = users[0] if users else {}
        company = current_user.get("company_id")
        company_name = company[1] if isinstance(company, list) else str(company or "")

        rpc_color = "green" if rpc_ms < 500 else "yellow" if rpc_ms < 2000 else "red"

        sections.append(
            (
                "Server",
                [
                    ("Version", ver_info.get("server_version", "unknown")),
                    ("Database", c.database),
                    ("RPC Latency", f"[{rpc_color}]{rpc_ms}ms[/{rpc_color}]"),
                    ("User", f"{current_user.get('name', '')} ({current_user.get('login', '')})"),
                    ("Company", company_name),
                ],
            )
        )
        json_data["server"] = {
            "version": ver_info.get("server_version"),
            "database": c.database,
            "rpc_latency_ms": rpc_ms,
            "uid": uid,
            "user": current_user.get("login"),
            "company": company_name,
        }

        # ── Modules ──
        installed = c.search_count("ir.module.module", [("state", "=", "installed")])
        to_upgrade = c.search_count("ir.module.module", [("state", "=", "to upgrade")])
        to_install = c.search_count("ir.module.module", [("state", "=", "to install")])
        to_remove = c.search_count("ir.module.module", [("state", "=", "to remove")])
        broken_total = to_upgrade + to_install + to_remove

        module_status = f"[green]{installed}[/green]"
        if broken_total:
            module_status += f" [red](+{broken_total} pending)[/red]"

        # Count private vs OCA vs core
        private_count = 0
        oca_count = 0
        try:
            all_installed = c.search_read(
                "ir.module.module",
                [("state", "=", "installed")],
                ["name", "author"],
                limit=0,
            )
            for m in all_installed:
                author = (m.get("author") or "").lower()
                if "kodemeio" in author or "kodeme" in author:
                    private_count += 1
                elif "oca" in author or "odoo community" in author:
                    oca_count += 1
        except RPCError:
            pass
        core_count = installed - private_count - oca_count

        sections.append(
            (
                "Modules",
                [
                    ("Installed", module_status),
                    ("Core/OCA/Private", f"{core_count} / {oca_count} / {private_count}"),
                    (
                        "Pending Upgrade",
                        f"[{'red' if to_upgrade else 'green'}]{to_upgrade}[/{'red' if to_upgrade else 'green'}]",
                    ),
                    ("Pending Install", str(to_install)),
                    ("Pending Remove", str(to_remove)),
                ],
            )
        )
        json_data["modules"] = {
            "installed": installed,
            "core": core_count,
            "oca": oca_count,
            "private": private_count,
            "to_upgrade": to_upgrade,
            "to_install": to_install,
            "to_remove": to_remove,
        }

        # ── Users & Partners ──
        active_users = c.search_count("res.users", [("active", "=", True), ("share", "=", False)])
        portal_users = c.search_count("res.users", [("active", "=", True), ("share", "=", True)])
        partners = c.search_count("res.partner", [("active", "=", True)])
        companies = c.search_count("res.company", [])

        sections.append(
            (
                "Users & Partners",
                [
                    ("Internal Users", str(active_users)),
                    ("Portal Users", str(portal_users)),
                    ("Active Partners", str(partners)),
                    ("Companies", str(companies)),
                ],
            )
        )
        json_data["users"] = {
            "internal": active_users,
            "portal": portal_users,
            "partners": partners,
            "companies": companies,
        }

        # ── Mail Queue ──
        mail_outgoing = _safe_count(c, "mail.mail", [("state", "=", "outgoing")])
        mail_exception = _safe_count(c, "mail.mail", [("state", "=", "exception")])

        if mail_outgoing is not None:
            exception_color = "red" if mail_exception else "green"
            sections.append(
                (
                    "Mail Queue",
                    [
                        ("Outgoing", str(mail_outgoing)),
                        ("Failed", f"[{exception_color}]{mail_exception}[/{exception_color}]"),
                    ],
                )
            )
            json_data["mail"] = {"outgoing": mail_outgoing, "exception": mail_exception}

        # ── Cron Health ──
        cron_total = c.search_count("ir.cron", [])
        cron_active = c.search_count("ir.cron", [("active", "=", True)])
        cutoff_48h = (datetime.now(tz=UTC) - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
        cron_stale = c.search_count("ir.cron", [("active", "=", True), ("lastcall", "<", cutoff_48h)])

        stale_color = "red" if cron_stale else "green"
        sections.append(
            (
                "Cron Jobs",
                [
                    ("Active / Total", f"{cron_active} / {cron_total}"),
                    ("Stale (>48h)", f"[{stale_color}]{cron_stale}[/{stale_color}]"),
                ],
            )
        )
        json_data["crons"] = {"total": cron_total, "active": cron_active, "stale": cron_stale}

        # ── Queue Jobs (if installed) ──
        jobs_pending = _safe_count(c, "queue.job", [("state", "=", "pending")])
        if jobs_pending is not None:
            jobs_failed = _safe_count(c, "queue.job", [("state", "=", "failed")]) or 0
            jobs_started = _safe_count(c, "queue.job", [("state", "=", "started")]) or 0
            failed_color = "red" if jobs_failed else "green"
            sections.append(
                (
                    "Queue Jobs",
                    [
                        ("Pending", str(jobs_pending)),
                        ("Running", str(jobs_started)),
                        ("Failed", f"[{failed_color}]{jobs_failed}[/{failed_color}]"),
                    ],
                )
            )
            json_data["queue_jobs"] = {"pending": jobs_pending, "started": jobs_started, "failed": jobs_failed}

        # ── Storage ──
        attachment_count = _safe_count(c, "ir.attachment", [])
        if attachment_count is not None:
            sections.append(
                (
                    "Storage",
                    [
                        ("Attachments", f"{attachment_count:,}"),
                    ],
                )
            )
            json_data["storage"] = {"attachments": attachment_count}

        # ── Business Pulse (only if modules are installed) ──
        biz_items: list[tuple[str, str]] = []
        biz_json: dict = {}

        sale_count = _safe_count(c, "sale.order", [("state", "=", "sale")])
        if sale_count is not None:
            biz_items.append(("Confirmed Sales", f"{sale_count:,}"))
            biz_json["confirmed_sales"] = sale_count

        invoice_count = _safe_count(c, "account.move", [("move_type", "=", "out_invoice"), ("state", "=", "posted")])
        if invoice_count is not None:
            biz_items.append(("Posted Invoices", f"{invoice_count:,}"))
            biz_json["posted_invoices"] = invoice_count

        product_count = _safe_count(c, "product.product", [("active", "=", True)])
        if product_count is not None:
            biz_items.append(("Active Products", f"{product_count:,}"))
            biz_json["active_products"] = product_count

        picking_count = _safe_count(c, "stock.picking", [("state", "in", ["assigned", "waiting"])])
        if picking_count is not None:
            biz_items.append(("Pending Transfers", f"{picking_count:,}"))
            biz_json["pending_transfers"] = picking_count

        mo_count = _safe_count(c, "mrp.production", [("state", "in", ["confirmed", "progress"])])
        if mo_count is not None:
            biz_items.append(("Active MOs", f"{mo_count:,}"))
            biz_json["active_mos"] = mo_count

        employee_count = _safe_count(c, "hr.employee", [("active", "=", True)])
        if employee_count is not None:
            biz_items.append(("Employees", f"{employee_count:,}"))
            biz_json["employees"] = employee_count

        if biz_items:
            sections.append(("Business Pulse", biz_items))
            json_data["business"] = biz_json

        # ── Alerts ──
        alerts: list[tuple[str, str]] = []
        alert_json: list[str] = []

        if broken_total:
            alerts.append(("Modules", f"[red]{broken_total} module(s) in pending state[/red]"))
            alert_json.append(f"{broken_total} modules pending")
        if mail_exception and mail_exception > 0:
            alerts.append(("Mail", f"[red]{mail_exception} failed email(s) in queue[/red]"))
            alert_json.append(f"{mail_exception} failed emails")
        if cron_stale:
            alerts.append(("Crons", f"[yellow]{cron_stale} stale cron(s) (>48h since last run)[/yellow]"))
            alert_json.append(f"{cron_stale} stale crons")
        if jobs_pending is not None and jobs_failed:
            alerts.append(("Jobs", f"[red]{jobs_failed} failed queue job(s)[/red]"))
            alert_json.append(f"{jobs_failed} failed jobs")

        if alerts:
            sections.append(("Alerts", alerts))
        else:
            sections.append(("Status", [("Health", "[green]All systems healthy[/green]")]))
        json_data["alerts"] = alert_json

        out.detail("Odoo Dashboard", sections, data_for_json=json_data)

    _run_once()

    if watch:
        try:
            while True:
                time.sleep(interval)
                out.header(f"Dashboard at {time.strftime('%H:%M:%S')}")
                _run_once()
        except KeyboardInterrupt:
            out.info("Stopped watching")


# ===================================================================
# DAILY DIGEST
# ===================================================================


@app.command("digest")
def daily_digest(ctx: typer.Context) -> None:
    """Morning coffee command — key business metrics at a glance.

    Combines: sales confirmed today, pending transfers, overdue AR,
    failed mail, stale crons, and failed queue jobs into one view.

    Examples:
        kctl-odoo dashboard digest
        kctl-odoo dashboard digest --json
        kctl-odoo --profile production dashboard digest
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    sections: list[tuple[str, list[tuple[str, str]]]] = []
    json_data: dict = {}
    now = datetime.now(tz=UTC)
    today_str = now.strftime("%Y-%m-%d 00:00:00")

    # -- Sales Today --
    if model_available(c, "sale.order"):
        confirmed_today = c.search_count(
            "sale.order",
            [("state", "=", "sale"), ("date_order", ">=", today_str)],
        )
        draft_count = c.search_count("sale.order", [("state", "=", "draft")])
        sections.append(
            (
                "Sales",
                [
                    ("Confirmed Today", str(confirmed_today)),
                    ("Draft Quotations", str(draft_count)),
                ],
            )
        )
        json_data["sales"] = {"confirmed_today": confirmed_today, "draft": draft_count}
    else:
        out.info("sale module not installed, skipping sales.")

    # -- Pending Transfers --
    if model_available(c, "stock.picking"):
        pending_transfers = c.search_count("stock.picking", [("state", "in", ["assigned", "waiting", "confirmed"])])
        late_transfers = c.search_count(
            "stock.picking",
            [
                ("state", "in", ["assigned", "waiting", "confirmed"]),
                ("scheduled_date", "<", now.strftime("%Y-%m-%d %H:%M:%S")),
            ],
        )
        late_color = "red" if late_transfers else "green"
        sections.append(
            (
                "Inventory",
                [
                    ("Pending Transfers", str(pending_transfers)),
                    ("Late Transfers", f"[{late_color}]{late_transfers}[/{late_color}]"),
                ],
            )
        )
        json_data["inventory"] = {"pending_transfers": pending_transfers, "late_transfers": late_transfers}

    # -- Overdue AR --
    if model_available(c, "account.move"):
        overdue_inv_count = c.search_count(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("payment_state", "in", ["not_paid", "partial"]),
                ("invoice_date_due", "<", now.strftime("%Y-%m-%d")),
            ],
        )
        overdue_color = "red" if overdue_inv_count else "green"
        sections.append(
            (
                "Receivables",
                [
                    (
                        "Overdue Invoices",
                        f"[{overdue_color}]{overdue_inv_count}[/{overdue_color}]",
                    ),
                ],
            )
        )
        json_data["receivables"] = {"overdue_invoices": overdue_inv_count}

    # -- Failed Mail --
    try:
        mail_exception = c.search_count("mail.mail", [("state", "=", "exception")])
        mail_outgoing = c.search_count("mail.mail", [("state", "=", "outgoing")])
        exc_color = "red" if mail_exception else "green"
        sections.append(
            (
                "Mail",
                [
                    ("Outgoing", str(mail_outgoing)),
                    ("Failed", f"[{exc_color}]{mail_exception}[/{exc_color}]"),
                ],
            )
        )
        json_data["mail"] = {"outgoing": mail_outgoing, "exception": mail_exception}
    except RPCError:
        pass

    # -- Stale Crons --
    cutoff_48h = (now - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        stale_crons = c.search_count("ir.cron", [("active", "=", True), ("lastcall", "<", cutoff_48h)])
        stale_color = "red" if stale_crons else "green"
        sections.append(
            (
                "Cron Jobs",
                [
                    ("Stale (>48h)", f"[{stale_color}]{stale_crons}[/{stale_color}]"),
                ],
            )
        )
        json_data["crons"] = {"stale": stale_crons}
    except RPCError:
        pass

    # -- Failed Queue Jobs --
    try:
        failed_jobs = c.search_count("queue.job", [("state", "=", "failed")])
        pending_jobs = c.search_count("queue.job", [("state", "=", "pending")])
        failed_color = "red" if failed_jobs else "green"
        sections.append(
            (
                "Queue Jobs",
                [
                    ("Pending", str(pending_jobs)),
                    ("Failed", f"[{failed_color}]{failed_jobs}[/{failed_color}]"),
                ],
            )
        )
        json_data["queue_jobs"] = {"pending": pending_jobs, "failed": failed_jobs}
    except RPCError:
        pass  # queue_job module not installed

    # -- Overall Status --
    alerts: list[str] = []
    if json_data.get("mail", {}).get("exception", 0) > 0:
        alerts.append(f"{json_data['mail']['exception']} failed email(s)")
    if json_data.get("crons", {}).get("stale", 0) > 0:
        alerts.append(f"{json_data['crons']['stale']} stale cron(s)")
    if json_data.get("queue_jobs", {}).get("failed", 0) > 0:
        alerts.append(f"{json_data['queue_jobs']['failed']} failed queue job(s)")
    if json_data.get("receivables", {}).get("overdue_invoices", 0) > 0:
        alerts.append(f"{json_data['receivables']['overdue_invoices']} overdue invoice(s)")
    if json_data.get("inventory", {}).get("late_transfers", 0) > 0:
        alerts.append(f"{json_data['inventory']['late_transfers']} late transfer(s)")

    if alerts:
        alert_lines = [(f"[red]{a}[/red]", "") for a in alerts]
        sections.append(("Attention Required", alert_lines))
    else:
        sections.append(("Status", [("Health", "[green]All clear[/green]")]))
    json_data["alerts"] = alerts

    out.detail("Daily Digest", sections, data_for_json=json_data)


# ===================================================================
# KPI SCORECARD
# ===================================================================


@app.command("kpi")
def kpi(ctx: typer.Context) -> None:
    """Business KPI scorecard with pass/warn/fail thresholds.

    Default KPIs:
    - Order fulfillment rate (confirmed SO with done picking / total confirmed SO)
    - AR aging (receivable > 30 days / total receivable)
    - Email health (failure rate in last 24h)
    - Data quality (products with internal_ref / total products)

    Examples:
        kctl-odoo dashboard kpi
        kctl-odoo dashboard kpi --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    rows: list[list[str]] = []
    json_data: list[dict] = []

    def _add_kpi(
        name: str,
        value: float,
        unit: str,
        threshold_warn: float,
        threshold_fail: float,
        higher_is_better: bool = True,
    ) -> None:
        if higher_is_better:
            if value >= threshold_warn:
                status = "[green]PASS[/green]"
                status_raw = "PASS"
            elif value >= threshold_fail:
                status = "[yellow]WARN[/yellow]"
                status_raw = "WARN"
            else:
                status = "[red]FAIL[/red]"
                status_raw = "FAIL"
        else:
            if value <= threshold_warn:
                status = "[green]PASS[/green]"
                status_raw = "PASS"
            elif value <= threshold_fail:
                status = "[yellow]WARN[/yellow]"
                status_raw = "WARN"
            else:
                status = "[red]FAIL[/red]"
                status_raw = "FAIL"

        threshold_str = f"warn={threshold_warn}{unit} fail={threshold_fail}{unit}"
        rows.append([name, f"{value:.1f}{unit}", threshold_str, status])
        json_data.append(
            {
                "kpi": name,
                "value": round(value, 1),
                "unit": unit,
                "threshold_warn": threshold_warn,
                "threshold_fail": threshold_fail,
                "status": status_raw,
            }
        )

    # 1. Order Fulfillment Rate
    if model_available(c, "sale.order") and model_available(c, "stock.picking"):
        confirmed_so = c.search_count("sale.order", [("state", "=", "sale")])
        if confirmed_so > 0:
            so_with_done = c.search_count(
                "sale.order",
                [("state", "=", "sale"), ("picking_ids.state", "=", "done")],
            )
            fulfillment = (so_with_done / confirmed_so) * 100
        else:
            fulfillment = 100.0
        _add_kpi("Order Fulfillment", fulfillment, "%", 80.0, 60.0, higher_is_better=True)

    # 2. AR Aging (receivable >30 days / total receivable)
    if model_available(c, "account.move"):
        now = datetime.now(tz=UTC)
        cutoff_30d = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        total_receivable = c.search_count(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("payment_state", "in", ["not_paid", "partial"]),
            ],
        )
        if total_receivable > 0:
            overdue_receivable = c.search_count(
                "account.move",
                [
                    ("move_type", "=", "out_invoice"),
                    ("state", "=", "posted"),
                    ("payment_state", "in", ["not_paid", "partial"]),
                    ("invoice_date_due", "<", cutoff_30d),
                ],
            )
            ar_aging = (overdue_receivable / total_receivable) * 100
        else:
            ar_aging = 0.0
        _add_kpi("AR Aging (>30d)", ar_aging, "%", 20.0, 40.0, higher_is_better=False)

    # 3. Email Health (failure rate in last 24h)
    try:
        now = datetime.now(tz=UTC)
        cutoff_24h = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        total_mail = c.search_count("mail.mail", [("create_date", ">=", cutoff_24h)])
        if total_mail > 0:
            failed_mail = c.search_count("mail.mail", [("create_date", ">=", cutoff_24h), ("state", "=", "exception")])
            failure_rate = (failed_mail / total_mail) * 100
        else:
            failure_rate = 0.0
        _add_kpi("Email Failure Rate", failure_rate, "%", 5.0, 15.0, higher_is_better=False)
    except RPCError:
        pass

    # 4. Data Quality (products with internal_ref / total products)
    if model_available(c, "product.template"):
        total_products = c.search_count("product.template", [("sale_ok", "=", True)])
        if total_products > 0:
            with_ref = c.search_count(
                "product.template",
                [("sale_ok", "=", True), ("default_code", "!=", False), ("default_code", "!=", "")],
            )
            data_quality = (with_ref / total_products) * 100
        else:
            data_quality = 100.0
        _add_kpi("Product Data Quality", data_quality, "%", 80.0, 60.0, higher_is_better=True)

    if not rows:
        out.info("No KPI data available. Check that relevant modules are installed.")
        return

    # Calculate overall score
    pass_count = sum(1 for d in json_data if d["status"] == "PASS")
    total_count = len(json_data)
    score = (pass_count / total_count) * 100 if total_count else 0

    score_color = "green" if score >= 75 else "yellow" if score >= 50 else "red"
    title = f"Business KPIs — [{score_color}]{score:.0f}% healthy[/{score_color}] ({pass_count}/{total_count} pass)"

    out.table(
        title,
        [("KPI", ""), ("Value", "cyan"), ("Threshold", "dim"), ("Status", "")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# PENDING APPROVALS
# ===================================================================


@app.command("pending-approvals")
def pending_approvals(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """Records awaiting approval across modules."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    rows: list[list[str]] = []
    json_data: list[dict] = []

    # Purchase orders to approve
    if model_available(c, "purchase.order"):
        pos = c.search_read(
            "purchase.order",
            domain=[("state", "=", "to approve")],
            fields=["name", "partner_id", "create_date", "amount_total"],
            limit=limit,
        )
        for po in pos:
            partner = po.get("partner_id")
            partner_name = partner[1] if isinstance(partner, list) else str(partner or "-")
            rows.append(["Purchase Order", po.get("name", ""), partner_name, str(po.get("create_date", ""))[:10]])
            json_data.append(
                {
                    "type": "purchase.order",
                    "reference": po.get("name"),
                    "requestor": partner_name,
                    "date": str(po.get("create_date", ""))[:10],
                    "amount": po.get("amount_total"),
                }
            )

    # Leave requests to approve
    if model_available(c, "hr.leave"):
        leaves = c.search_read(
            "hr.leave",
            domain=[("state", "=", "confirm")],
            fields=["display_name", "employee_id", "create_date"],
            limit=limit,
        )
        for lv in leaves:
            emp = lv.get("employee_id")
            emp_name = emp[1] if isinstance(emp, list) else str(emp or "-")
            rows.append(["Leave Request", lv.get("display_name", ""), emp_name, str(lv.get("create_date", ""))[:10]])
            json_data.append(
                {
                    "type": "hr.leave",
                    "reference": lv.get("display_name"),
                    "requestor": emp_name,
                    "date": str(lv.get("create_date", ""))[:10],
                }
            )

    # Expense sheets to approve
    if model_available(c, "hr.expense.sheet"):
        expenses = c.search_read(
            "hr.expense.sheet",
            domain=[("state", "=", "submit")],
            fields=["name", "employee_id", "create_date", "total_amount"],
            limit=limit,
        )
        for ex in expenses:
            emp = ex.get("employee_id")
            emp_name = emp[1] if isinstance(emp, list) else str(emp or "-")
            rows.append(["Expense Report", ex.get("name", ""), emp_name, str(ex.get("create_date", ""))[:10]])
            json_data.append(
                {
                    "type": "hr.expense.sheet",
                    "reference": ex.get("name"),
                    "requestor": emp_name,
                    "date": str(ex.get("create_date", ""))[:10],
                    "amount": ex.get("total_amount"),
                }
            )

    if not rows:
        out.info("No pending approvals found.")
        return

    out.table(
        f"Pending Approvals — {len(rows)} items",
        [("Type", ""), ("Reference", "cyan"), ("Requestor", ""), ("Date", "dim")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# FAILED EMAILS
# ===================================================================


@app.command("failed-emails")
def failed_emails(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """Emails that failed to send."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "mail.mail"):
        out.error(module_hint("mail.mail"))
        raise typer.Exit(1)

    mails = c.search_read(
        "mail.mail",
        domain=[("state", "=", "exception")],
        fields=["subject", "email_to", "failure_reason", "date"],
        limit=limit,
        order="date desc",
    )

    if not mails:
        out.info("No failed emails found.")
        return

    rows = []
    json_data: list[dict] = []
    for m in mails:
        rows.append(
            [
                m.get("subject") or "(no subject)",
                m.get("email_to") or "-",
                (m.get("failure_reason") or "-")[:60],
                str(m.get("date", ""))[:16],
            ]
        )
        json_data.append(
            {
                "subject": m.get("subject"),
                "recipient": m.get("email_to"),
                "error": m.get("failure_reason"),
                "date": m.get("date"),
            }
        )

    out.table(
        f"Failed Emails — {len(mails)} found",
        [("Subject", ""), ("Recipient", "dim"), ("Error", "red"), ("Date", "dim")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# EXECUTIVE SUMMARY
# ===================================================================


@app.command("exec-summary")
def exec_summary(ctx: typer.Context) -> None:
    """Executive summary — all key metrics in one view.

    Combines: revenue, AR/AP, cash position, inventory value,
    order fulfillment, HR headcount, and alerts into a single report.

    Examples:
        kctl-odoo dashboard exec-summary
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    from kctl_odoo.core.field_helpers import safe_fields  # noqa: F401

    sections = []

    # Revenue (confirmed sales this month)
    try:
        from datetime import datetime

        now = datetime.now()
        month_start = f"{now.year}-{now.month:02d}-01"
        sales = c.search_read(
            "sale.order",
            domain=[("state", "=", "sale"), ("date_order", ">=", month_start)],
            fields=["amount_total"],
            limit=5000,
        )
        revenue = sum(s.get("amount_total", 0) for s in sales)
        order_count = len(sales)
        sections.append(("Revenue (this month)", f"{revenue:,.2f} ({order_count} orders)"))
    except Exception:
        sections.append(("Revenue", "N/A"))

    # AR / AP
    try:
        ar = c.search_read(
            "account.move.line",
            domain=[
                ("account_id.account_type", "=", "asset_receivable"),
                ("parent_state", "=", "posted"),
                ("reconciled", "=", False),
            ],
            fields=["amount_residual"],
            limit=5000,
        )
        total_ar = sum(abs(l.get("amount_residual", 0)) for l in ar)
        sections.append(("Accounts Receivable", f"{total_ar:,.2f}"))
    except Exception:
        sections.append(("Accounts Receivable", "N/A"))

    try:
        ap = c.search_read(
            "account.move.line",
            domain=[
                ("account_id.account_type", "=", "liability_payable"),
                ("parent_state", "=", "posted"),
                ("reconciled", "=", False),
            ],
            fields=["amount_residual"],
            limit=5000,
        )
        total_ap = sum(abs(l.get("amount_residual", 0)) for l in ap)
        sections.append(("Accounts Payable", f"{total_ap:,.2f}"))
    except Exception:
        sections.append(("Accounts Payable", "N/A"))

    # Inventory value
    try:
        products = c.search_read(
            "product.product",
            domain=[("qty_available", ">", 0)],
            fields=["qty_available", "standard_price"],
            limit=5000,
        )
        inv_value = sum(p.get("qty_available", 0) * p.get("standard_price", 0) for p in products)
        sections.append(("Inventory Value", f"{inv_value:,.2f}"))
    except Exception:
        sections.append(("Inventory Value", "N/A"))

    # HR
    try:
        emp_count = c.search_count("hr.employee", [("active", "=", True)])
        sections.append(("Active Employees", str(emp_count)))
    except Exception:
        sections.append(("Employees", "N/A"))

    # Pending
    try:
        pending_so = c.search_count("sale.order", [("state", "=", "draft")])
        pending_po = c.search_count("purchase.order", [("state", "=", "draft")])
        pending_picks = c.search_count("stock.picking", [("state", "in", ["assigned", "confirmed"])])
        sections.append(("Pending Quotations", str(pending_so)))
        sections.append(("Pending RFQs", str(pending_po)))
        sections.append(("Pending Transfers", str(pending_picks)))
    except Exception:
        pass

    # Alerts
    try:
        failed_mail = c.search_count("mail.mail", [("state", "=", "exception")])
        if failed_mail > 0:
            sections.append(("⚠ Failed Emails", str(failed_mail)))
    except Exception:
        pass

    rows = [[k, v] for k, v in sections]
    out.table(
        "Executive Summary",
        [("Metric", ""), ("Value", "")],
        rows,
    )


# ===================================================================
# GROSS MARGIN
# ===================================================================


@app.command("gross-margin")
def gross_margin(ctx: typer.Context, date_from: str | None = None, date_to: str | None = None, limit: int = 20) -> None:
    """Gross margin report — revenue vs COGS per product.

    Calculates margin from confirmed sale order lines.

    Examples:
        kctl-odoo dashboard gross-margin
        kctl-odoo dashboard gross-margin --date-from 2026-03-01
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    from kctl_odoo.core.field_helpers import safe_fields

    domain = [("order_id.state", "=", "sale")]
    if date_from:
        domain.append(("order_id.date_order", ">=", date_from))
    if date_to:
        domain.append(("order_id.date_order", "<=", date_to))

    preferred = ["product_id", "product_uom_qty", "price_subtotal", "purchase_price"]
    fields = safe_fields(c, "sale.order.line", preferred)

    try:
        lines = c.search_read("sale.order.line", domain=domain, fields=fields, limit=10000)
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1)

    if not lines:
        out.info("No confirmed sale order lines found.")
        return

    # Aggregate by product
    products: dict = {}
    for line in lines:
        pid = line.get("product_id")
        pname = pid[1] if isinstance(pid, list) else str(pid or "Unknown")
        if pname not in products:
            products[pname] = {"revenue": 0, "cost": 0, "qty": 0}
        products[pname]["revenue"] += line.get("price_subtotal", 0) or 0
        products[pname]["cost"] += (line.get("purchase_price", 0) or 0) * (line.get("product_uom_qty", 0) or 0)
        products[pname]["qty"] += line.get("product_uom_qty", 0) or 0

    # Sort by revenue desc
    sorted_products = sorted(products.items(), key=lambda x: -x[1]["revenue"])[:limit]

    rows = []
    total_revenue = 0.0
    total_cost = 0.0
    for name, data in sorted_products:
        revenue = data["revenue"]
        cost = data["cost"]
        margin = revenue - cost
        margin_pct = (margin / revenue * 100) if revenue else 0
        total_revenue += revenue
        total_cost += cost
        rows.append([name, f"{revenue:,.2f}", f"{cost:,.2f}", f"{margin:,.2f}", f"{margin_pct:.1f}%"])

    total_margin = total_revenue - total_cost
    total_pct = (total_margin / total_revenue * 100) if total_revenue else 0
    rows.append(["TOTAL", f"{total_revenue:,.2f}", f"{total_cost:,.2f}", f"{total_margin:,.2f}", f"{total_pct:.1f}%"])

    out.table(
        f"Gross Margin Report ({len(sorted_products)} products)",
        [("Product", ""), ("Revenue", ""), ("COGS", ""), ("Margin", ""), ("Margin %", "")],
        rows,
    )
