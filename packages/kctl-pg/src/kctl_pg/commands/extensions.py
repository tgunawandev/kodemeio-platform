"""PostgreSQL extension management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_pg.core.callbacks import AppContext

app = typer.Typer(help="Manage PostgreSQL extensions.")


@app.command("list")
def list_(
    ctx: typer.Context,
    database: Annotated[str, typer.Option("--db", "-d", help="Target database")] = "postgres",
    available: Annotated[bool, typer.Option("--available", help="Show all available (not just installed)")] = False,
) -> None:
    """List installed or available extensions."""
    actx: AppContext = ctx.obj
    out = actx.output

    c = actx.get_client(database=database)
    try:
        if available:
            rows_data = c.fetchall("""
                SELECT
                    name,
                    default_version AS version,
                    installed_version,
                    comment AS description
                FROM pg_available_extensions
                ORDER BY name
            """)
        else:
            rows_data = c.fetchall("""
                SELECT
                    extname AS name,
                    extversion AS version,
                    n.nspname AS schema
                FROM pg_extension e
                JOIN pg_namespace n ON e.extnamespace = n.oid
                ORDER BY extname
            """)
    finally:
        c.close()

    if available:
        rows = [
            [
                r["name"],
                r["version"] or "-",
                r["installed_version"] or "[dim]-[/dim]",
                (r["description"] or "")[:60],
            ]
            for r in rows_data
        ]
        out.table(
            f"Available Extensions ({len(rows_data)})",
            [("Name", "cyan"), ("Version", ""), ("Installed", "green"), ("Description", "dim")],
            rows,
            data_for_json=rows_data,
        )
    else:
        rows = [[r["name"], r["version"], r["schema"]] for r in rows_data]
        out.table(
            f"Installed Extensions ({len(rows_data)})",
            [("Name", "cyan"), ("Version", "green"), ("Schema", "dim")],
            rows,
            data_for_json=rows_data,
        )


@app.command()
def install(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Extension name")],
    database: Annotated[str, typer.Option("--db", "-d", help="Target database")] = "postgres",
    schema: Annotated[str, typer.Option("--schema", help="Schema to install into")] = "public",
) -> None:
    """Install an extension."""
    actx: AppContext = ctx.obj
    out = actx.output

    c = actx.get_client(database=database)
    try:
        c.execute(f"CREATE EXTENSION IF NOT EXISTS {_quote_ident(name)} SCHEMA {_quote_ident(schema)}")
    finally:
        c.close()

    out.success(f"Extension '{name}' installed in {database}.{schema}")


@app.command()
def uninstall(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Extension name")],
    database: Annotated[str, typer.Option("--db", "-d", help="Target database")] = "postgres",
    cascade: Annotated[bool, typer.Option("--cascade", help="Drop dependent objects")] = False,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Uninstall an extension."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not force:
        msg = f"Uninstall extension '{name}' from {database}?"
        if cascade:
            msg += " (CASCADE: dependent objects will be dropped)"
        if not typer.confirm(msg):
            raise typer.Exit(0)

    c = actx.get_client(database=database)
    try:
        cascade_str = " CASCADE" if cascade else ""
        c.execute(f"DROP EXTENSION IF EXISTS {_quote_ident(name)}{cascade_str}")
    finally:
        c.close()

    out.success(f"Extension '{name}' removed from {database}")


def _quote_ident(name: str) -> str:
    """Quote a SQL identifier safely."""
    return '"' + name.replace('"', '""') + '"'
