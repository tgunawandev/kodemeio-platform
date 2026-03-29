"""Backup and restore commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_rustdesk.core.callbacks import AppContext

app = typer.Typer(help="Backup and restore RustDesk server data.")

BACKUP_DIR = "/opt/kodemeio-rustdesk/backups"
DATA_DIR = "/root"


@app.command()
def create(ctx: typer.Context) -> None:
    """Create a backup of keys and database."""
    c: AppContext = ctx.obj
    out = c.output
    ex = c.executor

    out.info("Creating backup...")
    ex.shell(["mkdir", "-p", BACKUP_DIR])

    timestamp = ex.shell(["date", "+%Y%m%d-%H%M%S"])
    backup_name = f"rustdesk-backup-{timestamp}.tar.gz"
    backup_path = f"{BACKUP_DIR}/{backup_name}"

    ex.exec_hbbs(
        [
            "tar",
            "czf",
            f"/tmp/{backup_name}",
            "-C",
            DATA_DIR,
            "id_ed25519",
            "id_ed25519.pub",
            "db_v2.sqlite3",
        ]
    )

    container_name = f"{ex.config.project_name}-hbbs-1"
    ex.shell(["docker", "cp", f"{container_name}:/tmp/{backup_name}", backup_path])
    ex.exec_hbbs(["rm", "-f", f"/tmp/{backup_name}"], check=False)

    out.success(f"Backup created: {backup_path}")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List available backups."""
    c: AppContext = ctx.obj
    ex = c.executor

    output = ex.shell(
        ["find", BACKUP_DIR, "-name", "rustdesk-backup-*.tar.gz", "-printf", r"%f\t%s\t%T+\n"],
        check=False,
    )

    if not output.strip():
        c.output.info("No backups found.")
        return

    rows: list[list[str]] = []
    for line in output.strip().splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            name = parts[0]
            size_bytes = int(parts[1]) if parts[1].isdigit() else 0
            if size_bytes < 1048576:
                size = f"{size_bytes / 1024:.1f} KB"
            else:
                size = f"{size_bytes / 1048576:.1f} MB"
            date = parts[2][:19].replace("T", " ")
            rows.append([name, size, date])

    c.output.table(
        "Backups",
        [("File", "cyan"), ("Size", ""), ("Date", "dim")],
        rows,
    )


@app.command()
def restore(
    ctx: typer.Context,
    backup_file: Annotated[str, typer.Argument(help="Backup filename or full path")],
) -> None:
    """Restore from a backup file."""
    c: AppContext = ctx.obj
    out = c.output
    ex = c.executor

    if "/" not in backup_file:
        backup_file = f"{BACKUP_DIR}/{backup_file}"

    if not typer.confirm(f"Restore from {backup_file}? This will overwrite current data."):
        out.info("Restore cancelled.")
        raise typer.Exit()

    out.info(f"Restoring from {backup_file}...")

    container_name = f"{ex.config.project_name}-hbbs-1"
    ex.shell(["docker", "cp", backup_file, f"{container_name}:/tmp/restore.tar.gz"])
    ex.exec_hbbs(["tar", "xzf", "/tmp/restore.tar.gz", "-C", DATA_DIR])
    ex.exec_hbbs(["rm", "-f", "/tmp/restore.tar.gz"])

    out.info("Restarting services...")
    ex.shell([*ex._dc_cmd(), "restart"])

    out.success("Restore complete. Services restarted.")


@app.command()
def clean(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", "-d", help="Delete backups older than N days")] = 30,
) -> None:
    """Remove old backups."""
    c: AppContext = ctx.obj
    out = c.output
    ex = c.executor

    old_files = ex.shell(
        ["find", BACKUP_DIR, "-name", "rustdesk-backup-*.tar.gz", "-mtime", f"+{days}"],
        check=False,
    )

    if not old_files.strip():
        out.info(f"No backups older than {days} days.")
        return

    file_count = len(old_files.strip().splitlines())
    if not typer.confirm(f"Delete {file_count} backup(s) older than {days} days?"):
        out.info("Cleanup cancelled.")
        raise typer.Exit()

    ex.shell(
        [
            "find",
            BACKUP_DIR,
            "-name",
            "rustdesk-backup-*.tar.gz",
            "-mtime",
            f"+{days}",
            "-delete",
        ]
    )
    out.success(f"Deleted {file_count} old backup(s).")
