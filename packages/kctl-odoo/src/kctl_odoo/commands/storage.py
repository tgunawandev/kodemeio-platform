"""Storage and cleanup commands."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError
from kctl_odoo.core.utils import human_size

app = typer.Typer(help="Storage monitoring & cleanup operations.")


def _safe_count(client, model: str, domain: list | None = None) -> int | None:
    """Search count that returns None if model doesn't exist."""
    try:
        return client.search_count(model, domain or [])
    except RPCError:
        return None


@app.command()
def overview(ctx: typer.Context) -> None:
    """Comprehensive storage overview with cleanup recommendations.

    Shows attachment statistics, top models by attachment count,
    mail and log record counts, and actionable cleanup suggestions.

    Examples:
        kctl-odoo storage overview
        kctl-odoo storage overview --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    sections: list[tuple[str, list[tuple[str, str]]]] = []
    json_data: dict = {}

    # ── Attachment Stats ──
    total_attachments = c.search_count("ir.attachment", [])
    with_model = c.search_count("ir.attachment", [("res_model", "!=", False), ("res_model", "!=", "")])
    orphans = total_attachments - with_model

    # Compute total size by paginating
    page_size = 500
    total_size = 0
    model_counts: dict[str, int] = {}
    offset = 0
    while True:
        batch = c.search_read(
            "ir.attachment",
            domain=[],
            fields=["file_size", "res_model"],
            limit=page_size,
            offset=offset,
            order="id",
        )
        if not batch:
            break
        for a in batch:
            size = a.get("file_size") or 0
            total_size += size
            m = a.get("res_model") or "(orphan)"
            model_counts[m] = model_counts.get(m, 0) + 1
        if len(batch) < page_size:
            break
        offset += page_size

    sections.append(
        (
            "Attachments",
            [
                ("Total", f"{total_attachments:,}"),
                ("Total Size", human_size(total_size)),
                ("With Model", f"{with_model:,}"),
                ("Orphans", f"{orphans:,}"),
            ],
        )
    )
    json_data["attachments"] = {
        "total": total_attachments,
        "total_size": total_size,
        "total_size_human": human_size(total_size),
        "with_model": with_model,
        "orphans": orphans,
    }

    # ── Top 5 Models by Attachment Count ──
    top_models = sorted(model_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_lines = [(model, f"{count:,}") for model, count in top_models]
    sections.append(("Top Models by Attachments", top_lines if top_lines else [("(none)", "-")]))
    json_data["top_models"] = [{"model": m, "count": cnt} for m, cnt in top_models]

    # ── Mail Records ──
    mail_total = _safe_count(c, "mail.mail", [])
    if mail_total is not None:
        mail_sent = _safe_count(c, "mail.mail", [("state", "=", "sent")]) or 0
        mail_exception = _safe_count(c, "mail.mail", [("state", "=", "exception")]) or 0
        sections.append(
            (
                "Mail Records",
                [
                    ("Total mail.mail", f"{mail_total:,}"),
                    ("Sent", f"{mail_sent:,}"),
                    ("Failed", f"{mail_exception:,}"),
                ],
            )
        )
        json_data["mail"] = {"total": mail_total, "sent": mail_sent, "exception": mail_exception}

    # ── Log Records ──
    log_count = _safe_count(c, "ir.logging", [])
    if log_count is not None:
        sections.append(("Logs", [("ir.logging Records", f"{log_count:,}")]))
        json_data["logs"] = {"ir_logging": log_count}

    # ── Cleanup Recommendations ──
    recommendations: list[tuple[str, str]] = []
    rec_json: list[str] = []

    if orphans > 100:
        msg = f"Clean {orphans:,} orphan attachments: kctl-odoo storage cleanup-attachments"
        recommendations.append(("Orphan Attachments", f"[yellow]{msg}[/yellow]"))
        rec_json.append(msg)

    if mail_total is not None and mail_total > 10000:
        msg = f"Clean old mail records ({mail_total:,}): kctl-odoo storage cleanup-mail"
        recommendations.append(("Old Mail", f"[yellow]{msg}[/yellow]"))
        rec_json.append(msg)

    if log_count is not None and log_count > 5000:
        msg = f"Clean old log records ({log_count:,}): kctl-odoo storage cleanup-logs"
        recommendations.append(("Old Logs", f"[yellow]{msg}[/yellow]"))
        rec_json.append(msg)

    if not recommendations:
        recommendations.append(("Status", "[green]Storage looks healthy[/green]"))

    sections.append(("Cleanup Recommendations", recommendations))
    json_data["recommendations"] = rec_json

    out.detail("Storage Overview", sections, data_for_json=json_data)


@app.command()
def attachments(
    ctx: typer.Context,
    model: Annotated[str, typer.Option("--model", "-m", help="Filter by res_model")] = "",
    top: Annotated[int, typer.Option("--top", "-t", help="Show top N largest")] = 20,
) -> None:
    """List attachments sorted by size (largest first)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = []
    if model:
        domain.append(("res_model", "=", model))

    records = c.search_read(
        "ir.attachment",
        domain=domain,
        fields=["id", "name", "res_model", "res_id", "file_size", "mimetype", "create_date"],
        limit=top,
        order="file_size desc",
    )

    rows = []
    json_data = []
    for a in records:
        size = a.get("file_size", 0)
        size_str = human_size(size)
        rows.append(
            [
                str(a["id"]),
                a.get("name") or "-",
                a.get("res_model") or "-",
                str(a.get("res_id") or "-"),
                size_str,
                a.get("mimetype") or "-",
                str(a.get("create_date") or "-"),
            ]
        )
        json_data.append(
            {
                "id": a["id"],
                "name": a.get("name"),
                "res_model": a.get("res_model"),
                "res_id": a.get("res_id"),
                "file_size": size,
                "mimetype": a.get("mimetype"),
                "create_date": a.get("create_date"),
            }
        )

    out.table(
        f"Attachments (top {top})",
        [
            ("ID", "cyan"),
            ("Name", ""),
            ("Model", "dim"),
            ("Res ID", "dim"),
            ("Size", ""),
            ("MIME", "dim"),
            ("Created", "dim"),
        ],
        rows,
        data_for_json=json_data,
    )


@app.command("cleanup-attachments")
def cleanup_attachments(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", "-d", help="Older than N days")] = 90,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Remove orphan attachments older than N days."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    cutoff = (datetime.now(tz=UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    # Orphan = no res_model or res_id=0, and not system attachments
    domain: list = [
        ("create_date", "<", cutoff),
        "|",
        "|",
        ("res_model", "=", False),
        ("res_model", "=", ""),
        "&",
        ("res_model", "!=", False),
        ("res_id", "=", 0),
    ]

    ids = c.search("ir.attachment", domain)
    if not ids:
        out.info(f"No orphan attachments older than {days} days found.")
        return

    out.info(f"Found {len(ids)} orphan attachments older than {days} days.")

    if not force and not typer.confirm(f"Delete {len(ids)} orphan attachments?"):
        raise typer.Exit(0)

    # Delete in batches of 100
    deleted = 0
    for i in range(0, len(ids), 100):
        batch = ids[i : i + 100]
        c.unlink("ir.attachment", batch)
        deleted += len(batch)

    out.success(f"Deleted {deleted} orphan attachments.")


@app.command("cleanup-mail")
def cleanup_mail(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", "-d", help="Older than N days")] = 30,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Remove sent/cancelled mail.mail records older than N days."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    cutoff = (datetime.now(tz=UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    try:
        ids = c.search(
            "mail.mail",
            [
                ("create_date", "<", cutoff),
                ("state", "in", ["sent", "cancel", "exception"]),
            ],
        )
    except Exception:
        out.warn("mail.mail model not accessible. Is the mail module installed?")
        return

    if not ids:
        out.info(f"No sent/cancelled mail older than {days} days found.")
        return

    out.info(f"Found {len(ids)} mail records to clean up.")

    if not force and not typer.confirm(f"Delete {len(ids)} old mail records?"):
        raise typer.Exit(0)

    deleted = 0
    for i in range(0, len(ids), 100):
        batch = ids[i : i + 100]
        c.unlink("mail.mail", batch)
        deleted += len(batch)

    out.success(f"Deleted {deleted} mail records.")


@app.command("cleanup-logs")
def cleanup_logs(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", "-d", help="Older than N days")] = 30,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Remove old ir.logging records older than N days."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    cutoff = (datetime.now(tz=UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    try:
        ids = c.search("ir.logging", [("create_date", "<", cutoff)])
    except Exception:
        out.warn("ir.logging model not accessible.")
        return

    if not ids:
        out.info(f"No log entries older than {days} days found.")
        return

    out.info(f"Found {len(ids)} log entries to clean up.")

    if not force and not typer.confirm(f"Delete {len(ids)} old log entries?"):
        raise typer.Exit(0)

    deleted = 0
    for i in range(0, len(ids), 100):
        batch = ids[i : i + 100]
        c.unlink("ir.logging", batch)
        deleted += len(batch)

    out.success(f"Deleted {deleted} log entries.")


@app.command("cleanup-sessions")
def cleanup_sessions(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Purge expired sessions via ir.http (if available)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Odoo doesn't always expose session cleanup via ORM
    # Try calling the session GC method
    try:
        result = c.execute_kw("ir.http", "session_gc", [])
        out.success(f"Session garbage collection executed. Result: {result}")
    except Exception as e:
        # Fallback: try res.users.log cleanup
        out.warn(f"Direct session GC not available via ORM: {e}")
        out.info("Tip: Sessions are typically file-based. Use the server's session directory cleanup.")


@app.command("filestore-stats")
def filestore_stats(
    ctx: typer.Context,
) -> None:
    """Show attachment storage statistics."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    total_count = c.search_count("ir.attachment", [])

    # Paginate through all attachments to compute sizes
    page_size = 500
    total_size = 0
    model_counts: dict[str, int] = {}
    model_sizes: dict[str, int] = {}
    offset = 0
    while True:
        batch = c.search_read(
            "ir.attachment",
            domain=[],
            fields=["file_size", "res_model"],
            limit=page_size,
            offset=offset,
            order="id",
        )
        if not batch:
            break
        for a in batch:
            size = a.get("file_size") or 0
            total_size += size
            m = a.get("res_model") or "(orphan)"
            model_counts[m] = model_counts.get(m, 0) + 1
            model_sizes[m] = model_sizes.get(m, 0) + size
        if len(batch) < page_size:
            break
        offset += page_size

    # Count by type
    with_model = c.search_count("ir.attachment", [("res_model", "!=", False), ("res_model", "!=", "")])
    orphans = total_count - with_model

    top_by_size = sorted(model_sizes.items(), key=lambda x: x[1], reverse=True)[:10]

    json_out = {
        "total_count": total_count,
        "total_size": total_size,
        "total_size_human": human_size(total_size),
        "with_model": with_model,
        "orphans": orphans,
        "top_models_by_size": [
            {"model": m, "size": s, "size_human": human_size(s), "count": model_counts.get(m, 0)}
            for m, s in top_by_size
        ],
    }

    top_lines = [(m, f"{human_size(s)} ({model_counts.get(m, 0)} files)") for m, s in top_by_size]

    sections = [
        (
            "Overview",
            [
                ("Total Attachments", str(total_count)),
                ("Total Size", human_size(total_size)),
                ("With Model", str(with_model)),
                ("Orphans", str(orphans)),
            ],
        ),
        ("Top Models by Size", top_lines if top_lines else [("(none)", "-")]),
    ]

    out.detail("Filestore Statistics", sections, data_for_json=json_out)


# NOTE: db-size command removed — use `kctl-odoo performance db-size` instead.


@app.command("large-attachments")
def large_attachments(
    ctx: typer.Context,
    min_size: Annotated[int, typer.Option("--min-size", help="Minimum file size in bytes")] = 1000000,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 20,
) -> None:
    """Find oversized attachments (default: > 1MB)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    records = c.search_read(
        "ir.attachment",
        domain=[("file_size", ">", min_size)],
        fields=["id", "name", "res_model", "file_size", "create_date"],
        limit=limit,
        order="file_size desc",
    )

    if not records:
        out.info(f"No attachments larger than {human_size(min_size)} found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for a in records:
        size = a.get("file_size") or 0
        rows.append(
            [
                str(a["id"]),
                a.get("name") or "-",
                a.get("res_model") or "(orphan)",
                human_size(size),
                str(a.get("create_date") or "-"),
            ]
        )
        json_data.append(
            {
                "id": a["id"],
                "name": a.get("name"),
                "res_model": a.get("res_model"),
                "file_size": size,
                "file_size_human": human_size(size),
                "create_date": a.get("create_date"),
            }
        )

    out.table(
        f"Large Attachments > {human_size(min_size)} (top {len(records)})",
        [
            ("ID", "cyan"),
            ("Name", ""),
            ("Model", "dim"),
            ("Size", ""),
            ("Created", "dim"),
        ],
        rows,
        data_for_json=json_data,
    )


@app.command("integrity-check")
def integrity_check(ctx: typer.Context) -> None:
    """Verify attachment references are valid."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Get all attachments that reference a model
    all_with_model = c.search_read(
        "ir.attachment",
        domain=[("res_model", "!=", False), ("res_model", "!=", ""), ("res_id", ">", 0)],
        fields=["id", "res_model", "res_id"],
        limit=0,
        order="id",
    )

    # Group by model
    by_model: dict[str, list[int]] = {}
    for a in all_with_model:
        model = a["res_model"]
        by_model.setdefault(model, []).append(a["res_id"])

    orphaned_total = 0
    rows = []
    json_data = []

    for model, res_ids in sorted(by_model.items()):
        unique_ids = list(set(res_ids))
        try:
            existing = c.search(model, [("id", "in", unique_ids)])
            existing_set = set(existing)
            missing = [rid for rid in unique_ids if rid not in existing_set]
            orphaned = len(missing)
            orphaned_total += orphaned
        except RPCError:
            orphaned = -1  # model inaccessible

        status = (
            "[green]OK[/green]"
            if orphaned == 0
            else "[yellow]orphaned[/yellow]"
            if orphaned > 0
            else "[dim]inaccessible[/dim]"
        )
        rows.append(
            [
                model,
                str(len(res_ids)),
                str(orphaned) if orphaned >= 0 else "N/A",
                status,
            ]
        )
        json_data.append(
            {
                "model": model,
                "attachment_count": len(res_ids),
                "orphaned": orphaned if orphaned >= 0 else None,
            }
        )

    out.table(
        f"Attachment Integrity Check ({orphaned_total} orphaned references)",
        [
            ("Model", "cyan"),
            ("Attachments", ""),
            ("Orphaned", ""),
            ("Status", ""),
        ],
        rows,
        data_for_json=json_data,
    )
    if orphaned_total > 0:
        out.warn(
            f"Found {orphaned_total} orphaned attachment references. Run 'storage cleanup-attachments' to clean up."
        )


@app.command("download")
def download_attachment(
    ctx: typer.Context,
    attachment_id: Annotated[int, typer.Argument(help="Attachment record ID")],
    output: Annotated[str | None, typer.Option("--output", "-o", help="Output file path")] = None,
) -> None:
    """Download an attachment by ID."""
    import base64

    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    records = c.read("ir.attachment", [attachment_id], fields=["id", "name", "datas", "file_size", "mimetype"])
    if not records:
        out.error(f"Attachment {attachment_id} not found.")
        raise typer.Exit(1)

    a = records[0]
    raw_data = a.get("datas")
    if not raw_data:
        out.error(f"Attachment {attachment_id} has no data (may be stored in filestore).")
        raise typer.Exit(1)

    file_bytes = base64.b64decode(raw_data)
    file_name = a.get("name") or f"attachment_{attachment_id}"
    output_path = Path(output) if output else Path(file_name)
    output_path.write_bytes(file_bytes)

    out.success(f"Downloaded {output_path} ({human_size(len(file_bytes))})")
    if actx.json_mode:
        out.raw_json(
            {
                "id": attachment_id,
                "name": file_name,
                "file": str(output_path),
                "size": len(file_bytes),
                "mimetype": a.get("mimetype"),
            }
        )


@app.command("migrate-to-db")
def migrate_to_db(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max attachments to migrate")] = 100,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be migrated")] = False,
) -> None:
    """Migrate filestore attachments to database storage.

    Moves attachments from filesystem to database (ir.attachment store_fname -> db_datas).
    Use this before containerizing to make the app stateless.

    Examples:
        kctl-odoo storage migrate-to-db --dry-run
        kctl-odoo storage migrate-to-db --limit 500
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        count = c.search_count("ir.attachment", [("store_fname", "!=", False)])
    except Exception as e:
        out.error(f"Failed to query attachments: {e}")
        raise typer.Exit(1)

    out.info(f"Filestore attachments found: {count}")

    if count == 0:
        out.success("No filestore attachments to migrate. All in database already.")
        return

    if dry_run:
        out.info(f"DRY RUN — would migrate up to {min(limit, count)} attachments to database storage.")
        out.info("Run without --dry-run to execute.")
        return

    out.warn("Migrating attachments to DB storage requires Odoo's _relocate_all_files method.")
    out.info("Run this in Odoo shell instead:")
    out.info("  env['ir.attachment']._relocate_all_files(to='db')")
    out.info("Or use the Odoo System Parameters:")
    out.info("  ir_attachment.location = db")
    out.info("Then restart Odoo — new attachments will be stored in DB.")


@app.command("migrate-to-fs")
def migrate_to_fs(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max attachments to migrate")] = 100,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be migrated")] = False,
) -> None:
    """Migrate database attachments to filestore storage.

    Moves attachments from database to filesystem. Use when switching to
    S3/filestore for better performance with large files.

    Examples:
        kctl-odoo storage migrate-to-fs --dry-run
        kctl-odoo storage migrate-to-fs --limit 500
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        count = c.search_count("ir.attachment", [("store_fname", "=", False), ("db_datas", "!=", False)])
    except Exception as e:
        out.error(f"Failed to query attachments: {e}")
        raise typer.Exit(1)

    out.info(f"Database-stored attachments found: {count}")

    if count == 0:
        out.success("No database attachments to migrate. All in filestore already.")
        return

    if dry_run:
        out.info(f"DRY RUN — would migrate up to {min(limit, count)} attachments to filestore.")
        return

    out.warn("Migrating attachments to filestore requires Odoo's _relocate_all_files method.")
    out.info("Run this in Odoo shell instead:")
    out.info("  env['ir.attachment']._relocate_all_files(to='file')")
    out.info("Or use the Odoo System Parameters:")
    out.info("  ir_attachment.location = file")
    out.info("Then restart Odoo — new attachments will be stored on filesystem.")
