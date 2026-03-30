"""Database management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_pg.core.callbacks import AppContext

app = typer.Typer(help="Manage databases.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all databases with size and owner."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    rows_data = c.fetchall("""
        SELECT
            d.datname AS name,
            pg_catalog.pg_get_userbyid(d.datdba) AS owner,
            pg_catalog.pg_encoding_to_char(d.encoding) AS encoding,
            pg_catalog.pg_size_pretty(pg_catalog.pg_database_size(d.datname)) AS size,
            pg_catalog.pg_database_size(d.datname) AS size_bytes,
            (SELECT count(*) FROM pg_stat_activity WHERE datname = d.datname) AS connections
        FROM pg_catalog.pg_database d
        WHERE d.datistemplate = false
        ORDER BY pg_catalog.pg_database_size(d.datname) DESC
    """)

    rows = [[r["name"], r["owner"], r["encoding"], r["size"], str(r["connections"])] for r in rows_data]

    out.table(
        "Databases",
        [("Name", "cyan"), ("Owner", ""), ("Encoding", "dim"), ("Size", "green"), ("Conns", "")],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Database name")],
    owner: Annotated[str | None, typer.Option("--owner", "-O", help="Database owner")] = None,
    encoding: Annotated[str, typer.Option("--encoding", help="Character encoding")] = "UTF8",
) -> None:
    """Create a new database."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Check if exists
    exists = c.fetchval("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
    if exists:
        out.error(f"Database '{name}' already exists")
        raise typer.Exit(1)

    owner_clause = f" OWNER {_quote_ident(owner)}" if owner else ""
    c.execute(f"CREATE DATABASE {_quote_ident(name)}{owner_clause} ENCODING '{encoding}'")
    out.success(f"Database '{name}' created")
    if owner:
        out.kv("Owner", owner)


@app.command()
def drop(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Database name")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Drop a database."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Check if exists
    exists = c.fetchval("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
    if not exists:
        out.error(f"Database '{name}' does not exist")
        raise typer.Exit(1)

    # Safety: prevent dropping system databases
    if name in ("postgres", "template0", "template1"):
        out.error(f"Cannot drop system database '{name}'")
        raise typer.Exit(1)

    size = c.fetchval("SELECT pg_size_pretty(pg_database_size(%s))", (name,))

    if not force:
        if not typer.confirm(f"Drop database '{name}' ({size})? This cannot be undone"):
            raise typer.Exit(0)

    # Terminate active connections
    c.execute(
        """
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = %s AND pid <> pg_backend_pid()
    """,
        (name,),
    )

    c.execute(f"DROP DATABASE {_quote_ident(name)}")
    out.success(f"Database '{name}' dropped")


@app.command()
def size(ctx: typer.Context) -> None:
    """Show database sizes sorted by size."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    rows_data = c.fetchall("""
        SELECT
            datname AS name,
            pg_size_pretty(pg_database_size(datname)) AS size,
            pg_database_size(datname) AS size_bytes
        FROM pg_database
        WHERE datistemplate = false
        ORDER BY pg_database_size(datname) DESC
    """)

    total = sum(r["size_bytes"] for r in rows_data)
    rows = [[r["name"], r["size"]] for r in rows_data]

    # Add total row
    total_pretty = c.fetchval("SELECT pg_size_pretty(%s::bigint)", (total,))
    rows.append(["[bold]TOTAL[/bold]", f"[bold]{total_pretty}[/bold]"])

    out.table(
        "Database Sizes",
        [("Database", "cyan"), ("Size", "green")],
        rows,
        data_for_json=[*rows_data, {"name": "TOTAL", "size": total_pretty, "size_bytes": total}],
    )


@app.command()
def info(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Database name")],
) -> None:
    """Show detailed info about a database."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    db = c.fetchone(
        """
        SELECT
            d.datname AS name,
            pg_catalog.pg_get_userbyid(d.datdba) AS owner,
            pg_catalog.pg_encoding_to_char(d.encoding) AS encoding,
            d.datcollate AS collation,
            d.datctype AS ctype,
            pg_size_pretty(pg_database_size(d.datname)) AS size,
            d.datconnlimit AS conn_limit,
            d.datallowconn AS allow_connections
        FROM pg_database d
        WHERE d.datname = %s
    """,
        (name,),
    )

    if not db:
        out.error(f"Database '{name}' not found")
        raise typer.Exit(1)

    # Get connection count
    conns = c.fetchval("SELECT count(*) FROM pg_stat_activity WHERE datname = %s", (name,))

    # Get table count (connect to that database)
    try:
        db_client = actx.get_client(database=name)
        table_count = db_client.fetchval("""
            SELECT count(*) FROM information_schema.tables
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        """)
        db_client.close()
    except Exception:
        table_count = "N/A"

    sections = [
        (
            "Database",
            [
                ("Name", db["name"]),
                ("Owner", db["owner"]),
                ("Encoding", db["encoding"]),
                ("Collation", db["collation"]),
                ("Ctype", db["ctype"]),
                ("Size", db["size"]),
            ],
        ),
        (
            "Connections",
            [
                ("Active", str(conns)),
                ("Limit", str(db["conn_limit"]) if db["conn_limit"] >= 0 else "unlimited"),
                ("Allow", str(db["allow_connections"])),
            ],
        ),
        (
            "Objects",
            [
                ("Tables", str(table_count)),
            ],
        ),
    ]

    out.detail(f"Database: {name}", sections, data_for_json={**db, "connections": conns, "tables": table_count})


@app.command()
def rename(
    ctx: typer.Context,
    old_name: Annotated[str, typer.Argument(help="Current database name")],
    new_name: Annotated[str, typer.Argument(help="New database name")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Rename a database (terminates active connections first)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Check source exists
    exists = c.fetchval("SELECT 1 FROM pg_database WHERE datname = %s", (old_name,))
    if not exists:
        out.error(f"Database '{old_name}' does not exist")
        raise typer.Exit(1)

    # Safety: prevent renaming system databases
    if old_name in ("postgres", "template0", "template1"):
        out.error(f"Cannot rename system database '{old_name}'")
        raise typer.Exit(1)

    # Check target doesn't exist
    target_exists = c.fetchval("SELECT 1 FROM pg_database WHERE datname = %s", (new_name,))
    if target_exists:
        out.error(f"Database '{new_name}' already exists")
        raise typer.Exit(1)

    conns = c.fetchval(
        "SELECT count(*) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
        (old_name,),
    )

    if not force:
        msg = f"Rename '{old_name}' to '{new_name}'?"
        if conns:
            msg += f" ({conns} active connections will be terminated)"
        if not typer.confirm(msg):
            raise typer.Exit(0)

    # Terminate connections
    if conns:
        c.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = %s AND pid <> pg_backend_pid()
        """,
            (old_name,),
        )
        out.info(f"Terminated {conns} connections")

    c.execute(f"ALTER DATABASE {_quote_ident(old_name)} RENAME TO {_quote_ident(new_name)}")
    out.success(f"Database renamed: '{old_name}' -> '{new_name}'")


@app.command()
def copy(
    ctx: typer.Context,
    source: Annotated[str, typer.Argument(help="Source database (used as template)")],
    target: Annotated[str, typer.Argument(help="New database name")],
    owner: Annotated[str | None, typer.Option("--owner", "-O", help="Owner of the new database")] = None,
) -> None:
    """Copy a database using CREATE DATABASE ... TEMPLATE (terminates connections to source)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Check source exists
    exists = c.fetchval("SELECT 1 FROM pg_database WHERE datname = %s", (source,))
    if not exists:
        out.error(f"Source database '{source}' does not exist")
        raise typer.Exit(1)

    # Check target doesn't exist
    target_exists = c.fetchval("SELECT 1 FROM pg_database WHERE datname = %s", (target,))
    if target_exists:
        out.error(f"Target database '{target}' already exists")
        raise typer.Exit(1)

    # Terminate connections to source (required for TEMPLATE)
    conns = c.fetchval(
        "SELECT count(*) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
        (source,),
    )
    if conns:
        c.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = %s AND pid <> pg_backend_pid()
        """,
            (source,),
        )
        out.info(f"Terminated {conns} connections to '{source}'")

    source_size = c.fetchval("SELECT pg_size_pretty(pg_database_size(%s))", (source,))
    out.info(f"Copying '{source}' ({source_size}) to '{target}'...")

    owner_clause = f" OWNER {_quote_ident(owner)}" if owner else ""
    c.execute(f"CREATE DATABASE {_quote_ident(target)} TEMPLATE {_quote_ident(source)}{owner_clause}")
    out.success(f"Database '{target}' created from template '{source}'")


@app.command()
def owner(
    ctx: typer.Context,
    database: Annotated[str, typer.Argument(help="Database name")],
    new_owner: Annotated[str, typer.Argument(help="New owner role")],
) -> None:
    """Change the owner of a database."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Check database exists
    exists = c.fetchval("SELECT 1 FROM pg_database WHERE datname = %s", (database,))
    if not exists:
        out.error(f"Database '{database}' does not exist")
        raise typer.Exit(1)

    # Check role exists
    role_exists = c.fetchval("SELECT 1 FROM pg_roles WHERE rolname = %s", (new_owner,))
    if not role_exists:
        out.error(f"Role '{new_owner}' does not exist")
        raise typer.Exit(1)

    c.execute(f"ALTER DATABASE {_quote_ident(database)} OWNER TO {_quote_ident(new_owner)}")
    out.success(f"Database '{database}' owner changed to '{new_owner}'")


def _quote_ident(name: str) -> str:
    """Quote a SQL identifier safely (prevent injection)."""
    # Double any existing double quotes, then wrap in double quotes
    return '"' + name.replace('"', '""') + '"'
