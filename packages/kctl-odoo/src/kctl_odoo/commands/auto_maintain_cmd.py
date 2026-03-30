"""Automated maintenance: cleanup, retry, auto-fix."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext

app = typer.Typer(help="Automated maintenance: cleanup, retry, auto-fix.")


@app.command("run")
def run(
    ctx: typer.Context,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be done without making changes")] = False,
) -> None:
    """Full maintenance pass.

    Actions in order:
    1. Count and delete sent mail.mail older than 30 days
    2. Count and delete ir.logging older than 30 days
    3. Retry failed mail.mail less than 24h old (set state='outgoing')
    4. Reset modules stuck in 'to upgrade' (set state='installed')

    Use --dry-run to preview without making changes.

    Examples:
        kctl-odoo auto-maintain run --dry-run
        kctl-odoo auto-maintain run
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    now = datetime.now(tz=UTC)
    cutoff_30d = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_24h = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

    mode = "[DRY RUN] " if dry_run else ""

    results: dict[str, int] = {}

    # 1. Sent mail older than 30 days
    try:
        old_sent = c.search(
            "mail.mail",
            [("state", "=", "sent"), ("date", "<", cutoff_30d)],
        )
        count_sent = len(old_sent)
        results["sent_mail_deleted"] = count_sent
        if count_sent:
            if not dry_run:
                c.unlink("mail.mail", old_sent)
            out.info(
                f"{mode}Sent mail older than 30 days: {count_sent} {'would be deleted' if dry_run else 'deleted'}."
            )
        else:
            out.info("No old sent mail to clean.")
    except Exception as e:
        out.warn(f"Could not clean sent mail: {e}")
        results["sent_mail_deleted"] = 0

    # 2. ir.logging older than 30 days
    try:
        old_logs = c.search(
            "ir.logging",
            [("create_date", "<", cutoff_30d)],
        )
        count_logs = len(old_logs)
        results["logging_deleted"] = count_logs
        if count_logs:
            if not dry_run:
                c.unlink("ir.logging", old_logs)
            out.info(
                f"{mode}ir.logging records older than 30 days: {count_logs}"
                f" {'would be deleted' if dry_run else 'deleted'}."
            )
        else:
            out.info("No old ir.logging records to clean.")
    except Exception as e:
        out.warn(f"Could not clean ir.logging: {e}")
        results["logging_deleted"] = 0

    # 3. Retry failed mail less than 24h old
    try:
        failed_recent = c.search(
            "mail.mail",
            [("state", "=", "exception"), ("date", ">=", cutoff_24h)],
        )
        count_retry = len(failed_recent)
        results["mail_retried"] = count_retry
        if count_retry:
            if not dry_run:
                c.write("mail.mail", failed_recent, {"state": "outgoing"})
            out.info(
                f"{mode}Failed mail (<24h): {count_retry}"
                f" {'would be retried' if dry_run else 'retried (set to outgoing)'}."
            )
        else:
            out.info("No recent failed mail to retry.")
    except Exception as e:
        out.warn(f"Could not retry failed mail: {e}")
        results["mail_retried"] = 0

    # 4. Reset modules stuck in 'to upgrade'
    try:
        stuck = c.search(
            "ir.module.module",
            [("state", "=", "to upgrade")],
        )
        count_stuck = len(stuck)
        results["modules_reset"] = count_stuck
        if count_stuck:
            if not dry_run:
                c.write("ir.module.module", stuck, {"state": "installed"})
            out.info(
                f"{mode}Modules stuck in 'to upgrade': {count_stuck}"
                f" {'would be reset' if dry_run else 'reset to installed'}."
            )
        else:
            out.info("No modules stuck in 'to upgrade'.")
    except Exception as e:
        out.warn(f"Could not reset stuck modules: {e}")
        results["modules_reset"] = 0

    total_actions = sum(results.values())
    out.success(f"{'Dry-run complete' if dry_run else 'Maintenance complete'}. Total actions: {total_actions}.")

    if actx.json_mode:
        out.raw_json({**results, "dry_run": dry_run, "total_actions": total_actions})


@app.command("schedule")
def schedule(ctx: typer.Context) -> None:
    """Show instructions for scheduling auto-maintain via system cron.

    Outputs the crontab entry to run maintenance daily at 3 AM, and
    checks if an equivalent Odoo cron already exists.

    Examples:
        kctl-odoo auto-maintain schedule
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    out.info("To schedule auto-maintain daily at 3 AM, add to crontab (crontab -e):")
    out.info("")
    out.info("  0 3 * * * kctl-odoo auto-maintain run")
    out.info("")
    out.info("This will run a full maintenance pass every night.")

    # Check for equivalent Odoo cron
    try:
        odoo_crons = c.search_read(
            "ir.cron",
            domain=["|", ("name", "ilike", "mail"), ("name", "ilike", "clean")],
            fields=["name", "active", "nextcall", "interval_number", "interval_type"],
            limit=10,
        )
        if odoo_crons:
            out.info("")
            out.info("Related Odoo scheduled actions found:")
            for cron in odoo_crons:
                status = "active" if cron.get("active") else "inactive"
                interval = f"{cron.get('interval_number', '')} {cron.get('interval_type', '')}"
                out.info(f"  - [{status}] {cron['name']} (every {interval}, next: {cron.get('nextcall', 'N/A')})")
        else:
            out.info("No related Odoo scheduled actions found.")
    except Exception as e:
        out.warn(f"Could not query Odoo crons: {e}")

    if actx.json_mode:
        out.raw_json({"crontab_entry": "0 3 * * * kctl-odoo auto-maintain run"})


@app.command("report")
def report(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", "-d", help="Look back N days for stats")] = 7,
) -> None:
    """Show current maintenance stats.

    Displays counts of actionable items:
    - Sent mail (>30 days old)
    - ir.logging records (>30 days old)
    - Failed mail (<24h old, eligible for retry)
    - Modules stuck in 'to upgrade'

    Examples:
        kctl-odoo auto-maintain report
        kctl-odoo auto-maintain report --days 14
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    now = datetime.now(tz=UTC)
    cutoff_30d = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_24h = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_days = (now - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    stats: dict[str, int] = {}

    # Sent mail older than 30 days
    try:
        stats["old_sent_mail"] = c.search_count("mail.mail", [("state", "=", "sent"), ("date", "<", cutoff_30d)])
    except Exception:
        stats["old_sent_mail"] = -1

    # ir.logging older than 30 days
    try:
        stats["old_logging"] = c.search_count("ir.logging", [("create_date", "<", cutoff_30d)])
    except Exception:
        stats["old_logging"] = -1

    # Failed mail in last 24h (eligible for retry)
    try:
        stats["failed_mail_24h"] = c.search_count(
            "mail.mail", [("state", "=", "exception"), ("date", ">=", cutoff_24h)]
        )
    except Exception:
        stats["failed_mail_24h"] = -1

    # Stuck modules
    try:
        stats["stuck_modules"] = c.search_count("ir.module.module", [("state", "=", "to upgrade")])
    except Exception:
        stats["stuck_modules"] = -1

    # Mail sent in recent N days
    try:
        stats[f"sent_last_{days}d"] = c.search_count("mail.mail", [("state", "=", "sent"), ("date", ">=", cutoff_days)])
    except Exception:
        stats[f"sent_last_{days}d"] = -1

    out.info("Auto-Maintain Status Report")
    out.info("=" * 40)
    for key, val in stats.items():
        label = key.replace("_", " ").title()
        display = str(val) if val >= 0 else "N/A"
        out.info(f"  {label}: {display}")

    needs_attention = (
        stats.get("old_sent_mail", 0) > 0
        or stats.get("old_logging", 0) > 0
        or stats.get("failed_mail_24h", 0) > 0
        or stats.get("stuck_modules", 0) > 0
    )
    if needs_attention:
        out.warn("Action recommended: run 'kctl-odoo auto-maintain run' to clean up.")
    else:
        out.success("No immediate maintenance needed.")

    if actx.json_mode:
        out.raw_json({"stats": stats, "days": days, "needs_attention": needs_attention})
