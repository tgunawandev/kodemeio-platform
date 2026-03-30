"""Backup management commands."""

from __future__ import annotations

from datetime import UTC
from pathlib import Path
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext

app = typer.Typer(help="Database backup and restore operations.")


@app.command()
def create(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--database", "-d", help="Database name (default: active)")] = None,
    fmt: Annotated[str, typer.Option("--format", "-f", help="Backup format: zip or dump")] = "zip",
    output: Annotated[str | None, typer.Option("--output", "-o", help="Output file path")] = None,
) -> None:
    """Create a database backup.

    Downloads a backup via the Odoo database management endpoint.
    The backup is saved locally as a zip or dump file.

    Examples:
        kctl-odoo backup create
        kctl-odoo backup create --database odoo_prod --format dump
        kctl-odoo backup create -o /backups/daily.zip
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    db_name = database or c.database
    if not db_name:
        out.error("No database specified and no default configured.")
        raise typer.Exit(1)

    out.info(f"Creating {fmt} backup of '{db_name}'...")

    try:
        data = c.db_backup(db_name, backup_format=fmt)
    except Exception as exc:
        out.error(f"Backup failed: {exc}")
        raise typer.Exit(1) from exc

    ext = "zip" if fmt == "zip" else "dump"
    outfile = output or f"{db_name}_backup.{ext}"
    Path(outfile).write_bytes(data)
    size_mb = len(data) / (1024 * 1024)

    if actx.json_mode:
        out.raw_json(
            {
                "database": db_name,
                "format": fmt,
                "file": outfile,
                "size_mb": round(size_mb, 2),
            }
        )
    else:
        out.success(f"Backup saved: {outfile} ({size_mb:.1f} MB)")


@app.command()
def restore(
    ctx: typer.Context,
    backup_file: Annotated[str, typer.Argument(help="Path to backup file")],
    database: Annotated[str | None, typer.Option("--database", "-d", help="Target database name")] = None,
    copy: Annotated[bool, typer.Option("--copy/--move", help="Neutralize restored database (copy mode)")] = True,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Restore a database from a backup file.

    Examples:
        kctl-odoo backup restore mydb_backup.zip --database mydb_restored
        kctl-odoo backup restore backup.dump --database staging --move
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    path = Path(backup_file)
    if not path.exists():
        out.error(f"File not found: {backup_file}")
        raise typer.Exit(1)

    db_name = database or path.stem.replace("_backup", "")
    if not db_name:
        out.error("Could not determine target database name. Use --database.")
        raise typer.Exit(1)

    mode = "copy" if copy else "move"
    size_mb = path.stat().st_size / (1024 * 1024)

    if not force and not typer.confirm(
        f"Restore '{path.name}' ({size_mb:.1f} MB) as database '{db_name}' (mode: {mode})?"
    ):
        raise typer.Exit(0)

    out.info(f"Restoring '{path.name}' -> '{db_name}' ({mode} mode)...")

    try:
        data = path.read_bytes()
        c.db_restore(db_name, data, copy=copy)
    except Exception as exc:
        out.error(f"Restore failed: {exc}")
        raise typer.Exit(1) from exc

    if actx.json_mode:
        out.raw_json(
            {
                "database": db_name,
                "source": str(path),
                "copy": copy,
            }
        )
    else:
        out.success(f"Database '{db_name}' restored from {path.name}")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List databases with availability info.

    Uses the Odoo database service to enumerate available databases.

    Examples:
        kctl-odoo backup list
        kctl-odoo backup list --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        databases = c.db_list()
    except Exception as exc:
        out.error(f"Failed to list databases: {exc}")
        raise typer.Exit(1) from exc

    current_db = c.database

    rows = []
    json_data = []
    for db in sorted(databases):
        marker = "[green]active[/green]" if db == current_db else ""
        rows.append([db, marker])
        json_data.append({"name": db, "current": db == current_db})

    out.table(
        f"Databases ({len(databases)})",
        [("Name", "cyan"), ("Status", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def schedule(ctx: typer.Context) -> None:
    """Show backup-related scheduled actions from ir.cron.

    Searches for cron jobs with backup-related names to show the
    current backup schedule configuration.

    Examples:
        kctl-odoo backup schedule
        kctl-odoo backup schedule --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        c.authenticate()
    except Exception as exc:
        out.error(f"Authentication failed: {exc}")
        raise typer.Exit(1) from exc

    # Search for backup-related cron jobs
    domain = [
        "|",
        "|",
        "|",
        ("name", "ilike", "backup"),
        ("name", "ilike", "dump"),
        ("name", "ilike", "archive"),
        ("name", "ilike", "snapshot"),
    ]

    try:
        crons = c.search_read(
            "ir.cron",
            domain=domain,
            fields=[
                "id",
                "name",
                "active",
                "interval_number",
                "interval_type",
                "nextcall",
                "lastcall",
            ],
            limit=50,
            order="name",
        )
    except Exception as exc:
        out.error(f"Failed to query ir.cron: {exc}")
        raise typer.Exit(1) from exc

    if not crons:
        out.info("No backup-related scheduled actions found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for cr in crons:
        status = "[green]active[/green]" if cr.get("active") else "[dim]inactive[/dim]"
        interval = f"{cr.get('interval_number', '')} {cr.get('interval_type', '')}"
        rows.append(
            [
                str(cr["id"]),
                cr["name"],
                status,
                interval,
                str(cr.get("nextcall", "")),
                str(cr.get("lastcall") or "-"),
            ]
        )
        json_data.append(
            {
                "id": cr["id"],
                "name": cr["name"],
                "active": cr.get("active"),
                "interval": interval,
                "nextcall": cr.get("nextcall"),
                "lastcall": cr.get("lastcall"),
            }
        )

    out.table(
        f"Backup Schedules ({len(crons)})",
        [
            ("ID", "cyan"),
            ("Name", ""),
            ("Status", ""),
            ("Interval", ""),
            ("Next Call", ""),
            ("Last Call", "dim"),
        ],
        rows,
        data_for_json=json_data,
    )


@app.command("dr-status")
def dr_status(
    ctx: typer.Context,
    rpo_hours: Annotated[int, typer.Option("--rpo", help="RPO threshold in hours")] = 24,
) -> None:
    """Disaster recovery readiness report.

    Checks backup health, RPO compliance, and 3-2-1 rule readiness.
    RPO = Recovery Point Objective (max acceptable data loss).

    3-2-1 Rule:
      3 copies of data
      2 different storage media
      1 offsite copy
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    from datetime import datetime

    now = datetime.now(tz=UTC)
    sections: list[tuple[str, list[tuple[str, str]]]] = []
    json_data: dict = {}
    issues: list[str] = []

    # --- Database Info ---
    try:
        dbs = c.db_list()
        db_name = c.database
        sections.append(
            (
                "Database",
                [
                    ("Current", db_name),
                    ("Available", str(len(dbs))),
                ],
            )
        )
        json_data["database"] = db_name
        json_data["databases_available"] = len(dbs)
    except Exception:
        sections.append(("Database", [("Status", "[red]Cannot connect[/red]")]))
        issues.append("Cannot connect to database service")

    # --- Backup Cron Status (RPO check) ---
    backup_crons = c.search_read(
        "ir.cron",
        domain=[("name", "ilike", "backup")],
        fields=["name", "active", "lastcall", "nextcall", "interval_number", "interval_type"],
    )

    if not backup_crons:
        # Also check for dump/archive patterns
        backup_crons = c.search_read(
            "ir.cron",
            domain=["|", ("name", "ilike", "dump"), ("name", "ilike", "archive")],
            fields=["name", "active", "lastcall", "nextcall", "interval_number", "interval_type"],
        )

    rpo_ok = False
    last_backup_age = "Unknown"

    if backup_crons:
        active_crons = [cr for cr in backup_crons if cr.get("active")]
        cron_info = []
        for cr in backup_crons:
            status = "[green]active[/green]" if cr.get("active") else "[red]inactive[/red]"
            interval = f"{cr.get('interval_number', '?')} {cr.get('interval_type', '?')}"
            cron_info.append((cr["name"], f"{status}, every {interval}"))

            # Check last backup time for RPO
            lastcall = cr.get("lastcall")
            if lastcall and cr.get("active"):
                try:
                    last_dt = datetime.strptime(str(lastcall)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
                    age = now - last_dt
                    age_hours = age.total_seconds() / 3600
                    last_backup_age = f"{age_hours:.1f} hours ago"
                    if age_hours <= rpo_hours:
                        rpo_ok = True
                except (ValueError, TypeError):
                    pass

        sections.append(("Backup Crons", cron_info))
        json_data["backup_crons"] = len(active_crons)
    else:
        sections.append(("Backup Crons", [("Status", "[red]No backup cron found[/red]")]))
        issues.append("No automated backup cron configured")
        json_data["backup_crons"] = 0

    # --- RPO Assessment ---
    rpo_status = f"[green]PASS ({last_backup_age})[/green]" if rpo_ok else f"[red]FAIL ({last_backup_age})[/red]"
    sections.append(
        (
            "RPO (Recovery Point Objective)",
            [
                ("Threshold", f"{rpo_hours} hours"),
                ("Last backup", last_backup_age),
                ("Status", rpo_status),
            ],
        )
    )
    json_data["rpo"] = {"threshold_hours": rpo_hours, "last_backup_age": last_backup_age, "compliant": rpo_ok}

    if not rpo_ok:
        issues.append(f"RPO violation: last backup {last_backup_age} exceeds {rpo_hours}h threshold")

    # --- RTO Assessment ---
    sections.append(
        (
            "RTO (Recovery Time Objective)",
            [
                ("Restore method", "kctl-odoo backup restore <file>"),
                ("Estimated", "Depends on DB size — test with: kctl-odoo backup create + restore"),
                ("Last tested", "[yellow]Not tracked[/yellow] — schedule periodic restore tests"),
            ],
        )
    )
    json_data["rto"] = {"method": "backup restore", "last_tested": None}
    issues.append("RTO not measured — run periodic restore test to establish baseline")

    # --- 3-2-1 Rule ---
    # Check S3 configuration
    s3_keys = ["AWS_S3_BUCKET", "AWS_ENDPOINT_URL", "AWS_ACCESS_KEY_ID"]
    s3_params = {}
    for key in s3_keys:
        result = c.search_read("ir.config_parameter", [("key", "=", key.lower())], fields=["value"])
        s3_params[key] = bool(result and result[0].get("value"))

    has_s3 = all(s3_params.values())

    copy_1 = "[green]YES[/green] — Odoo database (primary)"
    copy_2 = (
        "[green]YES[/green] — Dokploy scheduled backup (if configured)"
        if backup_crons
        else "[red]NO[/red] — no automated backup"
    )
    copy_3 = "[green]YES[/green] — S3 offsite storage" if has_s3 else "[red]NO[/red] — S3 not configured"

    media_1 = "[green]Disk[/green] — local server storage"
    media_2 = (
        "[green]Object storage[/green] — S3/MinIO" if has_s3 else "[red]Missing[/red] — need S3 or different media"
    )

    offsite = "[green]YES[/green] — S3 offsite" if has_s3 else "[red]NO[/red] — all copies are local"

    rule_score = sum([bool(backup_crons), has_s3, True])  # Primary always counts

    sections.append(
        (
            "3-2-1 Backup Rule",
            [
                ("Copy 1", copy_1),
                ("Copy 2", copy_2),
                ("Copy 3", copy_3),
                ("Media 1", media_1),
                ("Media 2", media_2),
                ("Offsite", offsite),
                (
                    "Score",
                    f"{rule_score}/3 — {'[green]COMPLIANT[/green]' if rule_score == 3 else '[red]NOT COMPLIANT[/red]'}",
                ),
            ],
        )
    )
    json_data["rule_321"] = {
        "copies": rule_score,
        "has_s3": has_s3,
        "has_cron": bool(backup_crons),
        "compliant": rule_score == 3,
    }

    if not has_s3:
        issues.append("3-2-1: No offsite storage — configure S3 for offsite backups")
    if not backup_crons:
        issues.append("3-2-1: No automated backup — only live database exists")

    # --- Recommendations ---
    rec = []
    if not backup_crons:
        rec.append(("Set up backup cron", "Configure automated backup in Dokploy or via Odoo scheduled action"))
    if not has_s3:
        rec.append(("Configure S3 storage", "Set AWS_S3_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY in .env"))
    if not rpo_ok:
        rec.append(("Fix RPO compliance", f"Ensure backup runs at least every {rpo_hours} hours"))
    rec.append(
        ("Test restore quarterly", "kctl-odoo backup create && kctl-odoo backup restore <file> --database test_restore")
    )
    rec.append(("Monitor with kctl-pg", "kctl-pg maintenance autovacuum-status, kctl-pg perf wal-status"))

    if rec:
        sections.append(("Recommendations", rec))

    # --- Summary ---
    summary = f"[yellow]{len(issues)} issues[/yellow]" if issues else "[green]DR ready[/green]"
    sections.insert(
        0,
        (
            "DR Status",
            [
                ("Overall", summary),
                ("RPO", rpo_status),
                ("3-2-1", f"{rule_score}/3"),
                ("Timestamp", now.strftime("%Y-%m-%d %H:%M UTC")),
            ],
        ),
    )

    json_data["issues"] = issues
    json_data["issue_count"] = len(issues)

    out.detail(f"Disaster Recovery Status — {c.database}", sections, json_data)
