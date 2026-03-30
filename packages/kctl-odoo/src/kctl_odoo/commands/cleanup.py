"""Stale data cleanup and auto-fix commands."""

from __future__ import annotations

from datetime import UTC
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext

app = typer.Typer(help="Stale data cleanup, transient purge, and auto-fix operations.")


@app.command("transients")
def cleanup_transients(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", "-d", help="Delete transients older than N days")] = 1,
) -> None:
    """Delete old transient model records (wizards).

    Transient records accumulate over time and can bloat the database.
    Odoo's autovacuum handles this normally, but this forces cleanup
    of any transient records older than N days.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    from datetime import datetime, timedelta

    cutoff = (datetime.now(tz=UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    # Find transient models
    try:
        transient_models = c.search_read(
            "ir.model",
            domain=[("transient", "=", True)],
            fields=["model"],
        )
    except Exception as e:
        out.error(f"Failed to query transient models: {e}")
        raise typer.Exit(1) from e

    total_deleted = 0
    for tm in transient_models:
        model_name = tm["model"]
        try:
            old_ids = c.search(model_name, [("create_date", "<", cutoff)], limit=1000)
            if old_ids:
                c.unlink(model_name, old_ids)
                total_deleted += len(old_ids)
        except Exception:
            pass  # Some transient models may not be accessible

    out.success(
        f"Cleaned {total_deleted} transient records from {len(transient_models)} models (older than {days} day(s))."
    )
    if actx.json_mode:
        out.raw_json({"deleted": total_deleted, "models_checked": len(transient_models), "days": days})


@app.command("auto-fix")
def auto_fix(
    ctx: typer.Context,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be done without making changes")] = False,
) -> None:
    """Safe auto-fix for common maintenance issues.

    Actions:
    1. Retry failed emails older than 1 hour
    2. Clean sent mail older than 30 days
    3. Clean ir.logging older than 30 days
    4. Reset modules stuck in 'to upgrade' state

    In --dry-run mode, only shows what WOULD be done.

    Examples:
        kctl-odoo cleanup auto-fix --dry-run
        kctl-odoo cleanup auto-fix
        kctl-odoo cleanup auto-fix --json
    """
    from datetime import datetime, timedelta

    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    now = datetime.now(tz=UTC)
    rows: list[list[str]] = []
    json_data: list[dict] = []
    mode_label = "[yellow]DRY RUN[/yellow]" if dry_run else "[green]LIVE[/green]"

    def _fix(name: str, model: str, domain: list, action: str) -> None:
        """Run a fix action: count matching records, optionally execute."""
        try:
            count = c.search_count(model, domain)
        except Exception:
            rows.append([name, "[dim]skip[/dim]", "0", "Model not accessible"])
            json_data.append({"action": name, "status": "skipped", "count": 0, "detail": "Model not accessible"})
            return

        if count == 0:
            rows.append([name, "[green]clean[/green]", "0", "Nothing to do"])
            json_data.append({"action": name, "status": "clean", "count": 0})
            return

        if dry_run:
            rows.append([name, "[yellow]would fix[/yellow]", str(count), f"Would {action}"])
            json_data.append({"action": name, "status": "would_fix", "count": count, "detail": f"Would {action}"})
        else:
            try:
                ids = c.search(model, domain, limit=5000)
                if action == "retry":
                    c.write(model, ids, {"state": "outgoing"})
                elif action == "delete":
                    c.unlink(model, ids)
                elif action == "reset_state":
                    c.write(model, ids, {"state": "installed"})
                rows.append([name, "[green]fixed[/green]", str(len(ids)), f"{action}: {len(ids)} record(s)"])
                json_data.append({"action": name, "status": "fixed", "count": len(ids)})
            except Exception as e:
                rows.append([name, "[red]error[/red]", str(count), str(e)[:80]])
                json_data.append({"action": name, "status": "error", "count": count, "detail": str(e)[:80]})

    # 1. Retry failed emails older than 1h
    cutoff_1h = (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    _fix(
        "Retry failed emails (>1h)",
        "mail.mail",
        [("state", "=", "exception"), ("write_date", "<", cutoff_1h)],
        "retry",
    )

    # 2. Clean sent mail older than 30 days
    cutoff_30d = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    _fix(
        "Clean sent mail (>30d)",
        "mail.mail",
        [("state", "=", "sent"), ("write_date", "<", cutoff_30d)],
        "delete",
    )

    # 3. Clean ir.logging older than 30 days
    _fix(
        "Clean ir.logging (>30d)",
        "ir.logging",
        [("create_date", "<", cutoff_30d)],
        "delete",
    )

    # 4. Reset modules stuck in 'to upgrade'
    _fix(
        "Reset stuck modules",
        "ir.module.module",
        [("state", "=", "to upgrade")],
        "reset_state",
    )

    title = f"Auto-Fix {mode_label} ({len(rows)} actions)"
    out.table(
        title,
        [("Action", ""), ("Status", ""), ("Count", "cyan"), ("Detail", "dim")],
        rows,
        data_for_json=json_data,
    )
