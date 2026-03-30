"""Schema management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_pg.core.callbacks import AppContext

app = typer.Typer(help="Manage schemas.")


def _quote_ident(name: str) -> str:
    """Quote a SQL identifier safely."""
    return '"' + name.replace('"', '""') + '"'


@app.command("list")
def list_(
    ctx: typer.Context,
    database: Annotated[str, typer.Option("--db", "-d", help="Target database")] = "postgres",
) -> None:
    """List all schemas with sizes."""
    actx: AppContext = ctx.obj
    out = actx.output

    c = actx.get_client(database=database)
    try:
        rows_data = c.fetchall("""
            SELECT
                n.nspname AS name,
                pg_catalog.pg_get_userbyid(n.nspowner) AS owner,
                COALESCE(
                    pg_size_pretty(
                        sum(pg_total_relation_size(c.oid))
                    ),
                    '0 bytes'
                ) AS size,
                COALESCE(sum(pg_total_relation_size(c.oid)), 0) AS size_bytes,
                count(c.oid) AS table_count
            FROM pg_catalog.pg_namespace n
            LEFT JOIN pg_catalog.pg_class c
                ON c.relnamespace = n.oid
                AND c.relkind IN ('r', 'p')
            WHERE n.nspname !~ '^pg_'
              AND n.nspname <> 'information_schema'
            GROUP BY n.nspname, n.nspowner
            ORDER BY COALESCE(sum(pg_total_relation_size(c.oid)), 0) DESC
        """)
    finally:
        c.close()

    if not rows_data:
        out.info(f"No schemas found in '{database}'")
        return

    rows = [[r["name"], r["owner"], r["size"], str(r["table_count"])] for r in rows_data]

    out.table(
        f"Schemas — {database}",
        [("Name", "cyan"), ("Owner", ""), ("Size", "green"), ("Tables", "")],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Schema name")],
    database: Annotated[str, typer.Option("--db", "-d", help="Target database")] = "postgres",
    owner: Annotated[str | None, typer.Option("--owner", "-O", help="Schema owner")] = None,
) -> None:
    """Create a new schema."""
    actx: AppContext = ctx.obj
    out = actx.output

    c = actx.get_client(database=database)
    try:
        # Check if exists
        exists = c.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = %s", (name,))
        if exists:
            out.error(f"Schema '{name}' already exists in '{database}'")
            raise typer.Exit(1)

        auth_clause = f" AUTHORIZATION {_quote_ident(owner)}" if owner else ""
        c.execute(f"CREATE SCHEMA {_quote_ident(name)}{auth_clause}")
        out.success(f"Schema '{name}' created in '{database}'")
        if owner:
            out.kv("Owner", owner)
    finally:
        c.close()


@app.command()
def drop(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Schema name")],
    database: Annotated[str, typer.Option("--db", "-d", help="Target database")] = "postgres",
    cascade: Annotated[bool, typer.Option("--cascade", help="Drop all objects in the schema")] = False,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Drop a schema."""
    actx: AppContext = ctx.obj
    out = actx.output

    # Safety: prevent dropping system schemas
    if name in ("public", "pg_catalog", "information_schema", "pg_toast"):
        out.error(f"Cannot drop system schema '{name}'")
        raise typer.Exit(1)

    c = actx.get_client(database=database)
    try:
        exists = c.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = %s", (name,))
        if not exists:
            out.error(f"Schema '{name}' does not exist in '{database}'")
            raise typer.Exit(1)

        # Count objects
        obj_count = c.fetchval(
            """
            SELECT count(*)
            FROM pg_class c
            JOIN pg_namespace n ON c.relnamespace = n.oid
            WHERE n.nspname = %s
        """,
            (name,),
        )

        cascade_str = " CASCADE" if cascade else ""
        label = f" (CASCADE, {obj_count} objects)" if cascade else f" ({obj_count} objects)"

        if not force:
            if not typer.confirm(f"Drop schema '{name}'{label} in '{database}'? This cannot be undone"):
                raise typer.Exit(0)

        c.execute(f"DROP SCHEMA {_quote_ident(name)}{cascade_str}")
        out.success(f"Schema '{name}' dropped from '{database}'")
    finally:
        c.close()


@app.command()
def size(
    ctx: typer.Context,
    database: Annotated[str, typer.Option("--db", "-d", help="Target database")] = "postgres",
) -> None:
    """Show per-schema size breakdown."""
    actx: AppContext = ctx.obj
    out = actx.output

    c = actx.get_client(database=database)
    try:
        rows_data = c.fetchall("""
            SELECT
                n.nspname AS schema_name,
                pg_size_pretty(COALESCE(sum(pg_total_relation_size(c.oid)), 0)) AS size,
                COALESCE(sum(pg_total_relation_size(c.oid)), 0) AS size_bytes,
                count(c.oid) FILTER (WHERE c.relkind IN ('r', 'p')) AS tables,
                count(c.oid) FILTER (WHERE c.relkind = 'i') AS indexes,
                count(c.oid) FILTER (WHERE c.relkind = 'S') AS sequences
            FROM pg_catalog.pg_namespace n
            LEFT JOIN pg_catalog.pg_class c
                ON c.relnamespace = n.oid
                AND c.relkind IN ('r', 'p', 'i', 'S')
            WHERE n.nspname !~ '^pg_'
              AND n.nspname <> 'information_schema'
            GROUP BY n.nspname
            ORDER BY COALESCE(sum(pg_total_relation_size(c.oid)), 0) DESC
        """)

        total = sum(r["size_bytes"] for r in rows_data)
        total_pretty = c.fetchval("SELECT pg_size_pretty(%s::bigint)", (total,))
    finally:
        c.close()

    if not rows_data:
        out.info(f"No schemas found in '{database}'")
        return

    rows = [
        [
            r["schema_name"],
            r["size"],
            str(r["tables"]),
            str(r["indexes"]),
            str(r["sequences"]),
        ]
        for r in rows_data
    ]
    rows.append(
        [
            "[bold]TOTAL[/bold]",
            f"[bold]{total_pretty}[/bold]",
            "",
            "",
            "",
        ]
    )

    out.table(
        f"Schema Sizes — {database}",
        [
            ("Schema", "cyan"),
            ("Size", "green"),
            ("Tables", ""),
            ("Indexes", ""),
            ("Sequences", "dim"),
        ],
        rows,
        data_for_json=[
            *rows_data,
            {"schema_name": "TOTAL", "size": total_pretty, "size_bytes": total},
        ],
    )
