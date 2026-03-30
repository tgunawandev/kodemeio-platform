"""History tracking commands for Odoo operations."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.history import (
    clear_all_history,
    get_backup_history,
    get_deployment_history,
    get_health_check_history,
    get_module_op_history,
)

app = typer.Typer(help="View local operation history (module ops, backups, health checks, deployments).")


def _bool_label(value: int | bool) -> str:
    """Format a boolean/int as a coloured label for Rich tables."""
    return "[green]yes[/green]" if value else "[red]no[/red]"


@app.command("modules")
def modules(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--database", "-d", help="Filter by database")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max rows to show")] = 20,
) -> None:
    """Show module install/update operation history.

    Examples:
        kctl-odoo history modules
        kctl-odoo history modules -d odoo_prod -n 50
        kctl-odoo history modules --json
    """
    actx: AppContext = ctx.obj
    out = actx.output

    rows = get_module_op_history(database=database, limit=limit)
    if not rows:
        out.info("No module operation history found.")
        return

    columns: list[tuple[str, str]] = [
        ("ID", "dim"),
        ("Timestamp", "cyan"),
        ("Operation", "yellow"),
        ("Modules", ""),
        ("Database", ""),
        ("Profile", "dim"),
        ("Success", ""),
        ("Duration", "dim"),
    ]
    table_rows = [
        [
            str(r["id"]),
            r["timestamp"],
            r["operation"],
            r["modules"],
            r.get("database") or "",
            r.get("profile") or "",
            _bool_label(r["success"]),
            f"{r['duration_s']:.1f}s" if r.get("duration_s") is not None else "",
        ]
        for r in rows
    ]
    out.table("Module Operations", columns, table_rows, data_for_json=rows)


@app.command("backups")
def backups(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--database", "-d", help="Filter by database")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max rows to show")] = 20,
) -> None:
    """Show backup operation history.

    Examples:
        kctl-odoo history backups
        kctl-odoo history backups -d odoo_prod
    """
    actx: AppContext = ctx.obj
    out = actx.output

    rows = get_backup_history(database=database, limit=limit)
    if not rows:
        out.info("No backup history found.")
        return

    columns: list[tuple[str, str]] = [
        ("ID", "dim"),
        ("Timestamp", "cyan"),
        ("Database", ""),
        ("Type", "yellow"),
        ("File", ""),
        ("Size", "dim"),
        ("Success", ""),
    ]

    def _fmt_size(size_bytes: int | None) -> str:
        if size_bytes is None:
            return ""
        if size_bytes >= 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        if size_bytes >= 1024:
            return f"{size_bytes / 1024:.1f} KB"
        return f"{size_bytes} B"

    table_rows = [
        [
            str(r["id"]),
            r["timestamp"],
            r["database"],
            r["backup_type"],
            r.get("file_path") or "",
            _fmt_size(r.get("size_bytes")),
            _bool_label(r["success"]),
        ]
        for r in rows
    ]
    out.table("Backup History", columns, table_rows, data_for_json=rows)


@app.command("health")
def health(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--database", "-d", help="Filter by database")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max rows to show")] = 20,
) -> None:
    """Show health check history.

    Examples:
        kctl-odoo history health
        kctl-odoo history health -d odoo_prod -n 10
    """
    actx: AppContext = ctx.obj
    out = actx.output

    rows = get_health_check_history(database=database, limit=limit)
    if not rows:
        out.info("No health check history found.")
        return

    columns: list[tuple[str, str]] = [
        ("ID", "dim"),
        ("Timestamp", "cyan"),
        ("Database", ""),
        ("Healthy", ""),
        ("Version", "dim"),
        ("Active Users", ""),
        ("Installed Modules", ""),
    ]
    table_rows = [
        [
            str(r["id"]),
            r["timestamp"],
            r["database"],
            _bool_label(r["healthy"]),
            r.get("version") or "",
            str(r["active_users"]) if r.get("active_users") is not None else "",
            str(r["installed_modules"]) if r.get("installed_modules") is not None else "",
        ]
        for r in rows
    ]
    out.table("Health Check History", columns, table_rows, data_for_json=rows)


@app.command("deployments")
def deployments(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--database", "-d", help="Filter by database")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max rows to show")] = 20,
) -> None:
    """Show deployment history.

    Examples:
        kctl-odoo history deployments
        kctl-odoo history deployments --json
    """
    actx: AppContext = ctx.obj
    out = actx.output

    rows = get_deployment_history(database=database, limit=limit)
    if not rows:
        out.info("No deployment history found.")
        return

    columns: list[tuple[str, str]] = [
        ("ID", "dim"),
        ("Timestamp", "cyan"),
        ("Database", ""),
        ("Profile", ""),
        ("Modules", ""),
        ("Success", ""),
        ("Notes", "dim"),
    ]
    table_rows = [
        [
            str(r["id"]),
            r["timestamp"],
            r.get("database") or "",
            r.get("profile") or "",
            r.get("modules") or "",
            _bool_label(r["success"]),
            r.get("notes") or "",
        ]
        for r in rows
    ]
    out.table("Deployment History", columns, table_rows, data_for_json=rows)


@app.command("clear")
def clear(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation")] = False,
) -> None:
    """Clear all operation history.

    Deletes all records from every history table. This action is irreversible.

    Examples:
        kctl-odoo history clear
        kctl-odoo history clear --force
    """
    actx: AppContext = ctx.obj
    out = actx.output

    if not force:
        confirm = typer.confirm("Delete ALL operation history? This cannot be undone")
        if not confirm:
            out.info("Cancelled.")
            return

    counts = clear_all_history()
    total = sum(counts.values())

    if actx.json_mode:
        out.raw_json({"cleared": counts, "total_rows": total})
    else:
        parts = [f"{table}: {n}" for table, n in counts.items() if n > 0]
        if parts:
            out.success(f"Cleared {total} rows ({', '.join(parts)})")
        else:
            out.info("History was already empty.")
