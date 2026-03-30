"""Database management commands for kctl-api.

Direct DB queries, Alembic migrations, psql shell, seeding, and analysis.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.utils import find_project_root

app = typer.Typer(name="db", help="Database management — tables, migrations, queries, shell.", no_args_is_help=True)


# ---------------------------------------------------------------------------
# tables
# ---------------------------------------------------------------------------
@app.command()
def tables(ctx: typer.Context) -> None:
    """List database tables via direct async query."""
    actx: AppContext = ctx.obj
    out = actx.output

    db_url = actx.database_url
    if not db_url:
        out.error("No database_url configured.")
        raise typer.Exit(1)

    async def _run() -> list[dict]:
        from kctl_api.core.db import dispose_engine, execute_query

        try:
            rows = await execute_query(
                db_url,
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name",
            )
            return rows
        finally:
            await dispose_engine()

    try:
        rows = asyncio.run(_run())
    except ImportError as e:
        out.error(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        out.error(f"Query failed: {e}")
        raise typer.Exit(1) from None

    table_rows: list[list[str]] = [[r.get("table_name", "")] for r in rows]

    out.table(
        title=f"Database Tables ({len(rows)})",
        columns=[("Table", "bold")],
        rows=table_rows,
        data_for_json=rows,
    )


# ---------------------------------------------------------------------------
# count
# ---------------------------------------------------------------------------
@app.command()
def count(
    ctx: typer.Context,
    table: Annotated[str, typer.Argument(help="Table name.")],
) -> None:
    """Count rows in a table via direct async query."""
    actx: AppContext = ctx.obj
    out = actx.output

    db_url = actx.database_url
    if not db_url:
        out.error("No database_url configured.")
        raise typer.Exit(1)

    async def _run() -> list[dict]:
        from kctl_api.core.db import dispose_engine, execute_query, validate_identifier

        try:
            safe_table = validate_identifier(table)
            return await execute_query(db_url, f"SELECT COUNT(*) AS cnt FROM {safe_table}")
        finally:
            await dispose_engine()

    try:
        rows = asyncio.run(_run())
    except Exception as e:
        out.error(f"Query failed: {e}")
        raise typer.Exit(1) from None

    cnt = rows[0].get("cnt", 0) if rows else 0
    out.success(f"{table}: {cnt} rows")
    if actx.json_mode:
        out.raw_json({"table": table, "count": cnt})


# ---------------------------------------------------------------------------
# migrate
# ---------------------------------------------------------------------------
@app.command()
def migrate(ctx: typer.Context) -> None:
    """Run Alembic upgrade head via scripts/db migrate."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    script = root / "scripts" / "db"

    out.info("Running database migration ...")
    result = subprocess.run([str(script), "migrate"], cwd=str(root), capture_output=False)
    if result.returncode != 0:
        out.error("Migration failed.")
        raise typer.Exit(result.returncode)
    out.success("Migration complete.")


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------
@app.command()
def generate(
    ctx: typer.Context,
    message: Annotated[str, typer.Argument(help="Migration revision message.")],
) -> None:
    """Generate a new Alembic migration via scripts/db generate."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    script = root / "scripts" / "db"

    out.info(f"Generating migration: {message}")
    result = subprocess.run([str(script), "generate", message], cwd=str(root), capture_output=False)
    if result.returncode != 0:
        out.error("Generation failed.")
        raise typer.Exit(result.returncode)
    out.success("Migration generated.")


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------
@app.command()
def history(ctx: typer.Context) -> None:
    """Show Alembic migration history via scripts/db history."""
    root = find_project_root()
    script = root / "scripts" / "db"
    subprocess.run([str(script), "history"], cwd=str(root), capture_output=False)


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------
@app.command()
def downgrade(
    ctx: typer.Context,
    revision: Annotated[str, typer.Argument(help="Target revision (or '-1' for one step back).")] = "-1",
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation.")] = False,
) -> None:
    """Downgrade database to a previous migration revision."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not force:
        confirm = typer.confirm(f"Downgrade to revision '{revision}'?", default=False)
        if not confirm:
            out.info("Cancelled.")
            raise typer.Exit(0)

    root = find_project_root()
    script = root / "scripts" / "db"

    out.info(f"Downgrading to {revision} ...")
    result = subprocess.run([str(script), "downgrade", revision], cwd=str(root), capture_output=False)
    if result.returncode != 0:
        out.error("Downgrade failed.")
        raise typer.Exit(result.returncode)
    out.success("Downgrade complete.")


# ---------------------------------------------------------------------------
# shell
# ---------------------------------------------------------------------------
@app.command()
def shell(ctx: typer.Context) -> None:
    """Open an interactive psql shell to the configured database."""
    actx: AppContext = ctx.obj
    out = actx.output

    db_url = actx.database_url
    if not db_url:
        out.error("No database_url configured.")
        raise typer.Exit(1)

    # Convert async URL to sync for psql
    psql_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    out.info("Opening psql shell ...")
    result = subprocess.run(["psql", psql_url], capture_output=False)
    sys.exit(result.returncode)


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------
@app.command()
def query(
    ctx: typer.Context,
    sql: Annotated[str, typer.Argument(help="SQL query to execute.")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation for write queries.")] = False,
) -> None:
    """Execute a raw SQL query via async engine."""
    actx: AppContext = ctx.obj
    out = actx.output

    db_url = actx.database_url
    if not db_url:
        out.error("No database_url configured.")
        raise typer.Exit(1)

    # Warn on write queries
    sql_upper = sql.strip().upper()
    is_write = any(sql_upper.startswith(kw) for kw in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE"))
    if is_write and not force:
        confirm = typer.confirm("This looks like a write query. Proceed?", default=False)
        if not confirm:
            out.info("Cancelled.")
            raise typer.Exit(0)

    async def _run() -> list[dict]:
        from kctl_api.core.db import dispose_engine, execute_query

        try:
            return await execute_query(db_url, sql)
        finally:
            await dispose_engine()

    try:
        rows = asyncio.run(_run())
    except Exception as e:
        out.error(f"Query failed: {e}")
        raise typer.Exit(1) from None

    if not rows:
        out.info("Query returned no rows.")
        if actx.json_mode:
            out.raw_json([])
        return

    # Auto-detect columns from first row
    cols = list(rows[0].keys())
    table_rows = [[str(r.get(c, "")) for c in cols] for r in rows]

    out.table(
        title=f"Query Results ({len(rows)} rows)",
        columns=[(c, "") for c in cols],
        rows=table_rows,
        data_for_json=rows,
    )


# ---------------------------------------------------------------------------
# seed
# ---------------------------------------------------------------------------
@app.command()
def seed(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name to seed (default: api-main).")] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation.")] = False,
) -> None:
    """Seed the database with test/dev data via scripts/db seed."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not force:
        confirm = typer.confirm("Seed the database with test data?", default=False)
        if not confirm:
            out.info("Cancelled.")
            raise typer.Exit(0)

    root = find_project_root()
    script = root / "scripts" / "db"
    cmd = [str(script), "seed"]
    if app_name:
        cmd.append(app_name)

    out.info(f"Seeding database{f' ({app_name})' if app_name else ''} ...")
    result = subprocess.run(cmd, cwd=str(root), capture_output=False)
    if result.returncode != 0:
        out.error("Seeding failed.")
        raise typer.Exit(result.returncode)
    out.success("Database seeded.")


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------
@app.command()
def reset(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation.")] = False,
    skip_seed: Annotated[bool, typer.Option("--no-seed", help="Skip seeding after reset.")] = False,
) -> None:
    """Drop + recreate + migrate + seed the database."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not force:
        confirm = typer.confirm(
            "[red]WARNING[/red]: This will DROP and recreate the database. Proceed?",
            default=False,
        )
        if not confirm:
            out.info("Cancelled.")
            raise typer.Exit(0)

    root = find_project_root()
    script = root / "scripts" / "db"

    # Drop and recreate
    out.info("Dropping and recreating database ...")
    result = subprocess.run([str(script), "reset"], cwd=str(root), capture_output=False)
    if result.returncode != 0:
        # Try migrate as fallback
        out.warn("Reset script not found, running migrate ...")
        result = subprocess.run([str(script), "migrate"], cwd=str(root), capture_output=False)

    if result.returncode != 0:
        out.error("Reset failed.")
        raise typer.Exit(result.returncode)

    if not skip_seed:
        out.info("Seeding database ...")
        subprocess.run([str(script), "seed"], cwd=str(root), capture_output=False)

    out.success("Database reset complete.")


# ---------------------------------------------------------------------------
# check-safety
# ---------------------------------------------------------------------------
@app.command(name="check-safety")
def check_safety(ctx: typer.Context) -> None:
    """Analyze pending Alembic migrations for destructive operations."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()

    # Find migration files

    migration_dirs = list(root.rglob("versions"))
    if not migration_dirs:
        out.warn("No Alembic versions directory found.")
        raise typer.Exit(1)

    destructive_patterns = [
        ("drop_table", "Table deletion"),
        ("drop_column", "Column deletion"),
        ("drop_index", "Index deletion"),
        ("drop_constraint", "Constraint deletion"),
        ("execute.*DROP", "Raw DROP statement"),
        ("execute.*TRUNCATE", "TRUNCATE statement"),
        ("execute.*DELETE", "DELETE without WHERE"),
    ]

    import re

    issues: list[dict] = []
    for versions_dir in migration_dirs:
        for migration_file in sorted(versions_dir.glob("*.py")):
            content = migration_file.read_text(encoding="utf-8", errors="ignore")
            # Only check upgrade() function
            upgrade_match = re.search(r"def upgrade\(\):(.*?)(?=def downgrade|\Z)", content, re.DOTALL)
            if not upgrade_match:
                continue
            upgrade_body = upgrade_match.group(1)

            for pattern, label in destructive_patterns:
                if re.search(pattern, upgrade_body, re.IGNORECASE):
                    issues.append(
                        {
                            "file": migration_file.name,
                            "operation": label,
                            "severity": "WARNING",
                        }
                    )

    if not issues:
        out.success("No destructive operations found in pending migrations.")
        return

    rows = [[i["file"], i["operation"], i["severity"]] for i in issues]
    out.table(
        title=f"Destructive Migration Operations ({len(issues)})",
        columns=[("File", "bold"), ("Operation", "red"), ("Severity", "yellow")],
        rows=rows,
        data_for_json=issues,
    )
    out.warn("Review these migrations carefully before applying to production.")


# ---------------------------------------------------------------------------
# size
# ---------------------------------------------------------------------------
@app.command()
def size(ctx: typer.Context) -> None:
    """Show database size per table."""
    actx: AppContext = ctx.obj
    out = actx.output

    db_url = actx.database_url
    if not db_url:
        out.error("No database_url configured.")
        raise typer.Exit(1)

    async def _run() -> list[dict]:
        from kctl_api.core.db import dispose_engine, execute_query

        try:
            return await execute_query(
                db_url,
                """
                SELECT
                    table_name,
                    pg_size_pretty(pg_total_relation_size(quote_ident(table_name))) AS total_size,
                    pg_size_pretty(pg_relation_size(quote_ident(table_name))) AS table_size,
                    pg_size_pretty(
                        pg_total_relation_size(quote_ident(table_name))
                        - pg_relation_size(quote_ident(table_name))
                    ) AS index_size,
                    (SELECT COUNT(*) FROM information_schema.columns
                     WHERE table_name = t.table_name
                     AND table_schema = 'public') AS columns
                FROM information_schema.tables t
                WHERE table_schema = 'public'
                ORDER BY pg_total_relation_size(quote_ident(table_name)) DESC
                """,
            )
        finally:
            await dispose_engine()

    try:
        rows_data = asyncio.run(_run())
    except Exception as e:
        out.error(f"Query failed: {e}")
        raise typer.Exit(1) from None

    rows = [
        [r.get("table_name", ""), r.get("total_size", ""), r.get("table_size", ""), r.get("index_size", "")]
        for r in rows_data
    ]
    out.table(
        title="Database Table Sizes",
        columns=[("Table", "bold"), ("Total", ""), ("Data", ""), ("Indexes", "")],
        rows=rows,
        data_for_json=rows_data,
    )


# ---------------------------------------------------------------------------
# connections
# ---------------------------------------------------------------------------
@app.command()
def connections(ctx: typer.Context) -> None:
    """Show active database connections."""
    actx: AppContext = ctx.obj
    out = actx.output

    db_url = actx.database_url
    if not db_url:
        out.error("No database_url configured.")
        raise typer.Exit(1)

    async def _run() -> list[dict]:
        from kctl_api.core.db import dispose_engine, execute_query

        try:
            return await execute_query(
                db_url,
                """
                SELECT
                    pid,
                    usename AS username,
                    application_name,
                    client_addr,
                    state,
                    wait_event_type,
                    wait_event,
                    LEFT(query, 80) AS query_preview
                FROM pg_stat_activity
                WHERE datname = current_database()
                  AND pid <> pg_backend_pid()
                ORDER BY state, pid
                """,
            )
        finally:
            await dispose_engine()

    try:
        rows_data = asyncio.run(_run())
    except Exception as e:
        out.error(f"Query failed: {e}")
        raise typer.Exit(1) from None

    rows = [
        [
            str(r.get("pid", "")),
            r.get("username", ""),
            r.get("application_name", ""),
            r.get("state", ""),
            r.get("query_preview", "")[:60],
        ]
        for r in rows_data
    ]
    out.table(
        title=f"Active DB Connections ({len(rows_data)})",
        columns=[("PID", ""), ("User", "bold"), ("App", ""), ("State", ""), ("Query", "dim")],
        rows=rows,
        data_for_json=rows_data,
    )


# ---------------------------------------------------------------------------
# slow-queries
# ---------------------------------------------------------------------------
@app.command(name="slow-queries")
def slow_queries(
    ctx: typer.Context,
    min_ms: Annotated[int, typer.Option("--min-ms", help="Minimum mean time in ms to include.")] = 100,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max queries to show.")] = 20,
) -> None:
    """Show slow queries from pg_stat_statements (requires pg_stat_statements extension)."""
    actx: AppContext = ctx.obj
    out = actx.output

    db_url = actx.database_url
    if not db_url:
        out.error("No database_url configured.")
        raise typer.Exit(1)

    async def _run() -> list[dict]:
        from kctl_api.core.db import dispose_engine, execute_query

        try:
            return await execute_query(
                db_url,
                f"""
                SELECT
                    ROUND(mean_exec_time::numeric, 2) AS mean_ms,
                    calls,
                    ROUND(total_exec_time::numeric, 2) AS total_ms,
                    LEFT(query, 100) AS query_preview
                FROM pg_stat_statements
                WHERE mean_exec_time >= {min_ms}
                ORDER BY mean_exec_time DESC
                LIMIT {limit}
                """,
            )
        finally:
            await dispose_engine()

    try:
        rows_data = asyncio.run(_run())
    except Exception as e:
        if "pg_stat_statements" in str(e):
            out.warn("pg_stat_statements extension not enabled.")
            out.info("Enable it: CREATE EXTENSION IF NOT EXISTS pg_stat_statements;")
            out.info("Also add to postgresql.conf: shared_preload_libraries = 'pg_stat_statements'")
            raise typer.Exit(1) from None
        out.error(f"Query failed: {e}")
        raise typer.Exit(1) from None

    if not rows_data:
        out.success(f"No queries with mean time >= {min_ms}ms found.")
        return

    rows = [
        [
            f"{r.get('mean_ms', 0)}ms",
            str(r.get("calls", "")),
            f"{r.get('total_ms', 0)}ms",
            r.get("query_preview", "")[:80],
        ]
        for r in rows_data
    ]
    out.table(
        title=f"Slow Queries (mean >= {min_ms}ms)",
        columns=[("Mean", "bold"), ("Calls", ""), ("Total", ""), ("Query", "dim")],
        rows=rows,
        data_for_json=rows_data,
    )
