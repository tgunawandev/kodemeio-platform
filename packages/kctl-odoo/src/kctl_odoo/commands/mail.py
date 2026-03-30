"""Mail system management commands."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Manage Odoo mail system.")


@app.command()
def queue(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously monitor")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Watch interval in seconds")] = 15,
) -> None:
    """Show mail queue summary by state."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    def _run_once() -> None:
        states = ["outgoing", "sent", "exception", "cancel"]
        rows = []
        json_data = []

        for state in states:
            count = c.search_count("mail.mail", [("state", "=", state)])
            rows.append([state, str(count), _state_color(state)])
            json_data.append({"state": state, "count": count})

        total = sum(d["count"] for d in json_data)
        rows.append(["[bold]total[/bold]", f"[bold]{total}[/bold]", ""])
        json_data.append({"state": "total", "count": total})

        out.table(
            "Mail Queue Summary",
            [("State", ""), ("Count", "cyan"), ("Status", "")],
            rows,
            data_for_json=json_data,
        )

    _run_once()
    if watch:
        import time

        try:
            while True:
                time.sleep(interval)
                out.header(f"Refresh at {time.strftime('%H:%M:%S')}")
                _run_once()
        except KeyboardInterrupt:
            out.info("Stopped watching")


@app.command()
def failed(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 20,
) -> None:
    """Show failed emails with error details."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    mails = c.search_read(
        "mail.mail",
        domain=[("state", "=", "exception")],
        fields=["id", "subject", "email_to", "failure_reason", "create_date"],
        limit=limit,
        order="create_date desc",
    )

    if not mails:
        out.info("No failed emails found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for m in mails:
        subject = (m.get("subject") or "")[:40]
        email_to = (m.get("email_to") or "")[:30]
        reason = (m.get("failure_reason") or "Unknown")[:50]
        rows.append(
            [
                str(m["id"]),
                subject,
                email_to,
                reason,
                str(m.get("create_date", "")),
            ]
        )
        json_data.append(
            {
                "id": m["id"],
                "subject": m.get("subject"),
                "email_to": m.get("email_to"),
                "failure_reason": m.get("failure_reason"),
                "create_date": m.get("create_date"),
            }
        )

    out.table(
        f"Failed Emails ({len(mails)})",
        [("ID", "cyan"), ("Subject", ""), ("Recipient", ""), ("Error", "red"), ("Created", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def retry(
    ctx: typer.Context,
    ids: Annotated[str, typer.Argument(help="Comma-separated mail IDs or 'all'")],
) -> None:
    """Retry failed emails by resetting state to outgoing."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if ids.lower() == "all":
        mail_ids = c.search("mail.mail", [("state", "=", "exception")])
        if not mail_ids:
            out.info("No failed emails to retry.")
            return
    else:
        mail_ids = [int(i.strip()) for i in ids.split(",")]

    c.write("mail.mail", mail_ids, {"state": "outgoing", "failure_reason": False})
    out.success(f"Reset {len(mail_ids)} email(s) to outgoing state")

    # Trigger the mail scheduler to process the queue
    try:
        cron_ids = c.search("ir.cron", [("name", "ilike", "Mail: Email Queue Manager")], limit=1)
        if cron_ids:
            c.execute_kw("ir.cron", "method_direct_trigger", [cron_ids])
            out.info("Triggered mail queue processing")
    except RPCError:
        out.warn("Could not trigger mail queue automatically. Emails will be sent on next cron run.")


@app.command()
def cancel(
    ctx: typer.Context,
    ids: Annotated[str, typer.Argument(help="Comma-separated mail IDs or 'failed' for all failed")],
) -> None:
    """Cancel emails by setting state to cancel."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if ids.lower() == "failed":
        mail_ids = c.search("mail.mail", [("state", "=", "exception")])
        if not mail_ids:
            out.info("No failed emails to cancel.")
            return
    else:
        mail_ids = [int(i.strip()) for i in ids.split(",")]

    c.write("mail.mail", mail_ids, {"state": "cancel"})
    out.success(f"Cancelled {len(mail_ids)} email(s)")


@app.command()
def cleanup(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", "-d", help="Delete emails older than N days")] = 30,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete old sent and cancelled emails."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    cutoff = (datetime.now(tz=UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    sent_ids = c.search("mail.mail", [("state", "=", "sent"), ("create_date", "<", cutoff)])
    cancel_ids = c.search("mail.mail", [("state", "=", "cancel"), ("create_date", "<", cutoff)])
    exception_ids = c.search("mail.mail", [("state", "=", "exception"), ("create_date", "<", cutoff)])

    total = len(sent_ids) + len(cancel_ids) + len(exception_ids)

    json_result = {
        "cutoff_days": days,
        "sent_count": len(sent_ids),
        "cancel_count": len(cancel_ids),
        "exception_count": len(exception_ids),
        "total": total,
    }

    if total == 0:
        if actx.json_mode:
            json_result["deleted"] = 0
            out.raw_json(json_result)
            return
        out.info("Nothing to clean.")
        return

    out.info(f"Records older than {days} days:")
    out.kv("Sent", str(len(sent_ids)))
    out.kv("Cancelled", str(len(cancel_ids)))
    out.kv("Exceptions", str(len(exception_ids)))
    out.kv("Total", str(total))

    if not force and not typer.confirm(f"Delete {total} email records?"):
        raise typer.Exit(0)

    all_ids = sent_ids + cancel_ids + exception_ids
    # Delete in batches to avoid timeouts
    batch_size = 500
    deleted = 0
    for i in range(0, len(all_ids), batch_size):
        batch = all_ids[i : i + batch_size]
        c.unlink("mail.mail", batch)
        deleted += len(batch)

    if actx.json_mode:
        json_result["deleted"] = deleted
        out.raw_json(json_result)
    else:
        out.success(f"Deleted {deleted} email records")


# Mail server listing moved to: kctl-odoo server mail-outgoing
# (Previously: kctl-odoo mail servers)


@app.command()
def templates(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List email templates."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    tpls = c.search_read(
        "mail.template",
        domain=[],
        fields=["id", "name", "model_id", "subject", "use_default_to"],
        limit=limit,
        order="model_id, name",
    )

    if not tpls:
        out.info("No email templates found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for t in tpls:
        model = t.get("model_id")
        model_name = model[1] if isinstance(model, list) else str(model or "-")
        recipient = "default" if t.get("use_default_to") else "custom"
        subject = (t.get("subject") or "")[:40]
        rows.append(
            [
                str(t["id"]),
                t.get("name", "")[:35],
                model_name,
                subject,
                recipient,
            ]
        )
        json_data.append(
            {
                "id": t["id"],
                "name": t.get("name"),
                "model": model_name,
                "subject": t.get("subject"),
                "use_default_to": t.get("use_default_to"),
            }
        )

    out.table(
        f"Email Templates ({len(tpls)})",
        [("ID", "cyan"), ("Name", ""), ("Model", ""), ("Subject", ""), ("Recipient", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def test(
    ctx: typer.Context,
    server_id: Annotated[int, typer.Argument(help="SMTP server ID to test")],
    to: Annotated[str, typer.Option("--to", help="Email address to send test to")] = "",
) -> None:
    """Test SMTP server connection."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Verify server exists
    servers_found = c.search_read(
        "ir.mail_server",
        domain=[("id", "=", server_id)],
        fields=["id", "name", "smtp_host", "smtp_port"],
    )
    if not servers_found:
        out.error(f"SMTP server ID {server_id} not found.")
        raise typer.Exit(1)

    server_info = servers_found[0]
    out.info(f"Testing SMTP server: {server_info['name']} ({server_info['smtp_host']}:{server_info['smtp_port']})")

    try:
        c.execute_kw("ir.mail_server", "test_smtp_connection", [[server_id]])
        out.success(f"SMTP connection test passed for server '{server_info['name']}'")
        if actx.json_mode:
            out.raw_json({"server_id": server_id, "status": "ok", "name": server_info["name"]})
    except RPCError as e:
        out.error(f"SMTP test failed: {e.detail}")
        if actx.json_mode:
            out.raw_json({"server_id": server_id, "status": "error", "error": e.detail})
        raise typer.Exit(1) from e


@app.command()
def status(ctx: typer.Context) -> None:
    """Comprehensive mail system health overview.

    Shows SMTP servers, queue summary, 24h failure rate, and top errors.

    Examples:
        kctl-odoo mail status
        kctl-odoo mail status --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    sections: list[tuple[str, list[tuple[str, str]]]] = []
    json_data: dict = {}

    # ── SMTP Servers ──
    try:
        servers = c.search_read(
            "ir.mail_server",
            domain=[],
            fields=["id", "name", "smtp_host", "smtp_port", "smtp_encryption", "active"],
        )
    except RPCError:
        servers = []

    active_servers = [s for s in servers if s.get("active")]
    server_names = ", ".join(s["name"] for s in active_servers) if active_servers else "(none)"
    sections.append(
        (
            "SMTP Servers",
            [
                ("Active / Total", f"{len(active_servers)} / {len(servers)}"),
                ("Servers", server_names),
            ],
        )
    )
    json_data["smtp_servers"] = {
        "active": len(active_servers),
        "total": len(servers),
        "names": [s["name"] for s in active_servers],
        "details": [
            {
                "id": s["id"],
                "name": s["name"],
                "host": s.get("smtp_host"),
                "port": s.get("smtp_port"),
                "encryption": s.get("smtp_encryption"),
                "active": s.get("active"),
            }
            for s in servers
        ],
    }

    # ── Queue Summary ──
    queue_states = ["outgoing", "sent", "exception", "cancel"]
    queue_counts: dict[str, int] = {}
    for state in queue_states:
        try:
            queue_counts[state] = c.search_count("mail.mail", [("state", "=", state)])
        except RPCError:
            queue_counts[state] = 0

    outgoing = queue_counts["outgoing"]
    exception = queue_counts["exception"]
    exc_color = "red" if exception else "green"
    sections.append(
        (
            "Queue Summary",
            [
                ("Outgoing", str(outgoing)),
                ("Sent", str(queue_counts["sent"])),
                ("Failed", f"[{exc_color}]{exception}[/{exc_color}]"),
                ("Cancelled", str(queue_counts["cancel"])),
            ],
        )
    )
    json_data["queue"] = queue_counts

    # ── 24h Failure Rate ──
    cutoff_24h = (datetime.now(tz=UTC) - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        sent_24h = c.search_count("mail.mail", [("state", "=", "sent"), ("write_date", ">", cutoff_24h)])
        failed_24h = c.search_count("mail.mail", [("state", "=", "exception"), ("write_date", ">", cutoff_24h)])
        total_24h = sent_24h + failed_24h
        rate = round(failed_24h / total_24h * 100, 1) if total_24h > 0 else 0.0
        rate_color = "red" if rate > 10 else "yellow" if rate > 5 else "green"
        sections.append(
            (
                "Last 24 Hours",
                [
                    ("Sent", str(sent_24h)),
                    ("Failed", str(failed_24h)),
                    ("Failure Rate", f"[{rate_color}]{rate}%[/{rate_color}]"),
                ],
            )
        )
        json_data["last_24h"] = {
            "sent": sent_24h,
            "failed": failed_24h,
            "failure_rate_pct": rate,
        }
    except RPCError:
        pass

    # ── Top Error Messages ──
    try:
        failed_mails = c.search_read(
            "mail.mail",
            domain=[("state", "=", "exception"), ("failure_reason", "!=", False)],
            fields=["failure_reason"],
            limit=100,
            order="create_date desc",
        )
        if failed_mails:
            error_counts: dict[str, int] = {}
            for m in failed_mails:
                reason = (m.get("failure_reason") or "Unknown")[:80]
                error_counts[reason] = error_counts.get(reason, 0) + 1
            top_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            error_lines = [(reason, str(count)) for reason, count in top_errors]
            sections.append(("Top Errors", error_lines))
            json_data["top_errors"] = [{"message": r, "count": cnt} for r, cnt in top_errors]
        else:
            sections.append(("Top Errors", [("(none)", "No failed emails")]))
            json_data["top_errors"] = []
    except RPCError:
        pass

    out.detail("Mail System Status", sections, data_for_json=json_data)


@app.command()
def send(
    ctx: typer.Context,
    to: Annotated[str, typer.Argument(help="Recipient email address")],
    subject: Annotated[str, typer.Option("--subject", "-s", help="Email subject")] = "Test from kctl-odoo",
    body: Annotated[
        str, typer.Option("--body", "-b", help="Email body (HTML allowed)")
    ] = "<p>Test email sent via kctl-odoo CLI.</p>",
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show what would be sent without actually sending")
    ] = False,
) -> None:
    """Send an email via Odoo mail.mail.

    Creates a mail.mail record and triggers immediate delivery.

    Examples:
        kctl-odoo mail send user@example.com
        kctl-odoo mail send user@example.com --subject "Alert" --body "<p>Hello</p>"
        kctl-odoo mail send user@example.com --dry-run
        kctl-odoo mail send user@example.com --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    mail_vals = {
        "email_to": to,
        "subject": subject,
        "body_html": body,
        "state": "outgoing",
        "auto_delete": False,
    }

    if dry_run:
        result = {"action": "dry_run", "email_to": to, "subject": subject, "body_html": body}
        if actx.json_mode:
            out.raw_json(result)
        else:
            out.info("Dry run — would send:")
            out.kv("To", to)
            out.kv("Subject", subject)
            out.kv("Body", body[:100])
        return

    try:
        mail_id = c.create("mail.mail", mail_vals)
    except RPCError as e:
        out.error(f"Failed to create mail record: {e.detail}")
        raise typer.Exit(1) from e

    # Trigger immediate send
    try:
        c.execute_kw("mail.mail", "send", [[mail_id]])
        # Re-read to check state
        result = c.search_read("mail.mail", [("id", "=", mail_id)], fields=["id", "state", "failure_reason"])
        mail_record = result[0] if result else {}
        state = mail_record.get("state", "unknown")
        if state == "sent":
            out.success(f"Email sent to {to} (mail.mail ID {mail_id})")
        elif state == "exception":
            reason = mail_record.get("failure_reason") or "Unknown error"
            out.error(f"Email send failed: {reason}")
        else:
            out.info(f"Email queued (state={state}, mail.mail ID {mail_id})")

        if actx.json_mode:
            out.raw_json({"id": mail_id, "state": state, "email_to": to, "subject": subject})
    except RPCError:
        out.info(f"Email created (mail.mail ID {mail_id}). It will be sent by the mail cron.")
        if actx.json_mode:
            out.raw_json({"id": mail_id, "state": "outgoing", "email_to": to, "subject": subject})


def _state_color(state: str) -> str:
    colors = {
        "outgoing": "[yellow]outgoing[/yellow]",
        "sent": "[green]sent[/green]",
        "exception": "[red]exception[/red]",
        "cancel": "[dim]cancel[/dim]",
    }
    return colors.get(state, state)
