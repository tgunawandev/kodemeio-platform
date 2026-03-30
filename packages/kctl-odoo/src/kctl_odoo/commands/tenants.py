"""SaaS tenant operations (multi-database)."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext

app = typer.Typer(help="SaaS tenant/multi-database operations.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all tenant databases."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    databases = c.db_list()
    current_db = c.database

    rows = []
    json_data = []
    for db in sorted(databases):
        marker = "[green]current[/green]" if db == current_db else ""
        rows.append([db, marker])
        json_data.append({"name": db, "current": db == current_db})

    out.table(
        f"Tenant Databases ({len(databases)})",
        [("Database", "cyan"), ("Status", "green")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="New tenant database name")],
    template: Annotated[
        str | None, typer.Option("--template", "-t", help="Template database to duplicate from")
    ] = None,
    modules: Annotated[
        str | None, typer.Option("--modules", "-m", help="Comma-separated modules to install after creation")
    ] = None,
) -> None:
    """Create a new tenant database."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Check if database already exists
    existing = c.db_list()
    if name in existing:
        out.error(f"Database '{name}' already exists.")
        raise typer.Exit(1)

    if template:
        # Duplicate from template
        if template not in existing:
            out.error(f"Template database '{template}' not found.")
            raise typer.Exit(1)
        out.info(f"Creating tenant '{name}' from template '{template}'...")
        c.db_duplicate(template, name)
        out.success(f"Tenant '{name}' created from template '{template}'.")
    else:
        # Create blank database via JSON-RPC db service
        out.info(f"Creating tenant '{name}'...")
        try:
            c.db_create(name)
            out.success(f"Tenant '{name}' created.")
        except Exception as e:
            out.error(f"Failed to create database: {e}")
            raise typer.Exit(1) from e

    # Install modules if specified
    if modules:
        module_list = [m.strip() for m in modules.split(",")]
        out.info(f"Installing modules on '{name}': {', '.join(module_list)}")
        # Connect to the new database
        tenant_client = c.for_database(name)
        try:
            for mod in module_list:
                ids = tenant_client.search("ir.module.module", [("name", "=", mod)])
                if ids:
                    tenant_client.execute_kw("ir.module.module", "button_immediate_install", [ids])
                    out.success(f"  Installed: {mod}")
                else:
                    out.warn(f"  Module not found: {mod}")
        finally:
            tenant_client.close()


@app.command()
def suspend(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Tenant database name")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Suspend a tenant by disabling all cron jobs."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Verify database exists
    existing = c.db_list()
    if name not in existing:
        out.error(f"Database '{name}' not found.")
        raise typer.Exit(1)

    if not force and not typer.confirm(f"Suspend tenant '{name}'? This will disable all cron jobs."):
        raise typer.Exit(0)

    # Connect to the tenant database
    tenant_client = c.for_database(name)
    try:
        # Disable all active cron jobs
        cron_ids = tenant_client.search("ir.cron", [("active", "=", True)])
        if cron_ids:
            tenant_client.write("ir.cron", cron_ids, {"active": False})
            out.info(f"Disabled {len(cron_ids)} cron jobs.")

        # Set a config parameter to mark as suspended
        with contextlib.suppress(Exception):
            tenant_client.execute_kw(
                "ir.config_parameter",
                "set_param",
                ["kctl.tenant.suspended", "true"],
            )

        out.success(f"Tenant '{name}' suspended.")
    finally:
        tenant_client.close()


@app.command()
def reactivate(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Tenant database name")],
) -> None:
    """Reactivate a suspended tenant by re-enabling cron jobs."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    existing = c.db_list()
    if name not in existing:
        out.error(f"Database '{name}' not found.")
        raise typer.Exit(1)

    tenant_client = c.for_database(name)
    try:
        # Re-enable cron jobs (only standard ones, not custom disabled ones)
        # We re-enable all inactive crons - admin can fine-tune later
        cron_ids = tenant_client.search("ir.cron", [("active", "=", False)])
        if cron_ids:
            tenant_client.write("ir.cron", cron_ids, {"active": True})
            out.info(f"Re-enabled {len(cron_ids)} cron jobs.")

        # Remove suspension marker
        with contextlib.suppress(Exception):
            tenant_client.execute_kw(
                "ir.config_parameter",
                "set_param",
                ["kctl.tenant.suspended", "false"],
            )

        out.success(f"Tenant '{name}' reactivated.")
    finally:
        tenant_client.close()


@app.command()
def delete(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Tenant database name to delete")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a tenant database. This is irreversible."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    existing = c.db_list()
    if name not in existing:
        out.error(f"Database '{name}' not found.")
        raise typer.Exit(1)

    if name == c.database:
        out.error("Cannot delete the currently connected database.")
        raise typer.Exit(1)

    if not force and not typer.confirm(f"DELETE tenant '{name}'? This is IRREVERSIBLE and all data will be lost."):
        raise typer.Exit(0)

    out.info(f"Deleting tenant '{name}'...")
    try:
        c.db_drop(name)
        out.success(f"Tenant '{name}' deleted.")
    except Exception as e:
        out.error(f"Failed to delete database: {e}")
        raise typer.Exit(1) from e


@app.command()
def backup(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Tenant database name")],
    output: Annotated[str | None, typer.Option("--output", "-o", help="Output file path")] = None,
    fmt: Annotated[str, typer.Option("--format", "-f", help="Backup format: zip or dump")] = "zip",
) -> None:
    """Backup a tenant database."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    existing = c.db_list()
    if name not in existing:
        out.error(f"Database '{name}' not found.")
        raise typer.Exit(1)

    out.info(f"Backing up tenant '{name}'...")
    data = c.db_backup(name, backup_format=fmt)

    ext = "zip" if fmt == "zip" else "dump"
    outfile = output or f"{name}_backup.{ext}"
    Path(outfile).write_bytes(data)
    size_mb = len(data) / (1024 * 1024)
    out.success(f"Backup saved: {outfile} ({size_mb:.1f} MB)")


@app.command()
def info(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Tenant database name")],
) -> None:
    """Show information about a tenant database."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    existing = c.db_list()
    if name not in existing:
        out.error(f"Database '{name}' not found.")
        raise typer.Exit(1)

    tenant_client = c.for_database(name)
    try:
        ok, version = tenant_client.check_health()
        if not ok:
            out.error(f"Cannot connect to tenant '{name}': {version}")
            raise typer.Exit(1)

        users_count = tenant_client.search_count("res.users", [("active", "=", True)])
        internal_count = tenant_client.search_count("res.users", [("active", "=", True), ("share", "=", False)])
        modules_count = tenant_client.search_count("ir.module.module", [("state", "=", "installed")])
        partners_count = tenant_client.search_count("res.partner", [])
        companies_count = tenant_client.search_count("res.company", [])
        attachments_count = tenant_client.search_count("ir.attachment", [])

        # Check suspension status
        suspended = "unknown"
        try:
            result = tenant_client.execute_kw(
                "ir.config_parameter",
                "get_param",
                ["kctl.tenant.suspended"],
            )
            suspended = "yes" if result == "true" else "no"
        except Exception:
            pass

        # Active crons
        active_crons = tenant_client.search_count("ir.cron", [("active", "=", True)])

        json_out = {
            "database": name,
            "version": version,
            "suspended": suspended,
            "users_active": users_count,
            "users_internal": internal_count,
            "installed_modules": modules_count,
            "partners": partners_count,
            "companies": companies_count,
            "attachments": attachments_count,
            "active_crons": active_crons,
        }

        sections = [
            (
                "Tenant Info",
                [
                    ("Database", name),
                    ("Odoo Version", version),
                    ("Suspended", suspended),
                ],
            ),
            (
                "Counts",
                [
                    ("Active Users", str(users_count)),
                    ("Internal Users", str(internal_count)),
                    ("Installed Modules", str(modules_count)),
                    ("Partners", str(partners_count)),
                    ("Companies", str(companies_count)),
                    ("Attachments", str(attachments_count)),
                    ("Active Crons", str(active_crons)),
                ],
            ),
        ]

        out.detail(f"Tenant: {name}", sections, data_for_json=json_out)
    finally:
        tenant_client.close()
