"""Database maintenance commands: vacuum, analyze, reindex, bloat, autovacuum."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_pg.core.callbacks import AppContext

app = typer.Typer(help="Database maintenance operations.")


def _quote_ident(name: str) -> str:
    """Quote a SQL identifier safely."""
    return '"' + name.replace('"', '""') + '"'


@app.command()
def vacuum(
    ctx: typer.Context,
    database: Annotated[str, typer.Argument(help="Target database")],
    table: Annotated[str | None, typer.Option("--table", "-t", help="Specific table to vacuum")] = None,
    full: Annotated[bool, typer.Option("--full", help="Run VACUUM FULL (rewrites table, locks exclusively)")] = False,
    analyze: Annotated[bool, typer.Option("--analyze", help="Update planner statistics after vacuum")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", help="Print detailed vacuum activity")] = False,
) -> None:
    """Run VACUUM on a database or table."""
    actx: AppContext = ctx.obj
    out = actx.output

    c = actx.get_client(database=database)
    try:
        # Build VACUUM statement
        options: list[str] = []
        if full:
            options.append("FULL")
        if analyze:
            options.append("ANALYZE")
        if verbose:
            options.append("VERBOSE")

        option_str = f" ({', '.join(options)})" if options else ""
        table_str = f" {_quote_ident(table)}" if table else ""
        sql = f"VACUUM{option_str}{table_str}"

        out.info(f"Running: {sql}")
        c.execute(sql)
        target = f"table '{table}'" if table else f"database '{database}'"
        out.success(f"VACUUM completed on {target}")
    finally:
        c.close()


@app.command("analyze")
def analyze_cmd(
    ctx: typer.Context,
    database: Annotated[str, typer.Argument(help="Target database")],
    table: Annotated[str | None, typer.Option("--table", "-t", help="Specific table to analyze")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", help="Print detailed analyze activity")] = False,
) -> None:
    """Update planner statistics (ANALYZE) on a database or table."""
    actx: AppContext = ctx.obj
    out = actx.output

    c = actx.get_client(database=database)
    try:
        verbose_str = " VERBOSE" if verbose else ""
        table_str = f" {_quote_ident(table)}" if table else ""
        sql = f"ANALYZE{verbose_str}{table_str}"

        out.info(f"Running: {sql}")
        c.execute(sql)
        target = f"table '{table}'" if table else f"database '{database}'"
        out.success(f"ANALYZE completed on {target}")
    finally:
        c.close()


@app.command()
def reindex(
    ctx: typer.Context,
    database: Annotated[str, typer.Argument(help="Target database")],
    table: Annotated[str | None, typer.Option("--table", "-t", help="Reindex a specific table")] = None,
    index: Annotated[str | None, typer.Option("--index", "-i", help="Reindex a specific index")] = None,
    system: Annotated[bool, typer.Option("--system", help="Reindex system catalogs")] = False,
) -> None:
    """Rebuild indexes on a database, table, or specific index."""
    actx: AppContext = ctx.obj
    out = actx.output

    c = actx.get_client(database=database)
    try:
        if index:
            sql = f"REINDEX INDEX {_quote_ident(index)}"
            target = f"index '{index}'"
        elif table:
            sql = f"REINDEX TABLE {_quote_ident(table)}"
            target = f"table '{table}'"
        elif system:
            sql = "REINDEX SYSTEM " + _quote_ident(database)
            target = f"system catalogs in '{database}'"
        else:
            sql = "REINDEX DATABASE " + _quote_ident(database)
            target = f"database '{database}'"

        out.info(f"Running: {sql}")
        c.execute(sql)
        out.success(f"REINDEX completed on {target}")
    finally:
        c.close()


@app.command("autovacuum")
def autovacuum_status(
    ctx: typer.Context,
    database: Annotated[str, typer.Option("--db", "-d", help="Target database")] = "postgres",
) -> None:
    """Show autovacuum settings and last vacuum/analyze times per table."""
    actx: AppContext = ctx.obj
    out = actx.output

    c = actx.get_client(database=database)
    try:
        # Global autovacuum settings
        settings = c.fetchall("""
            SELECT name, setting, unit, short_desc
            FROM pg_settings
            WHERE name LIKE 'autovacuum%%'
            ORDER BY name
        """)

        # Per-table stats
        tables = c.fetchall("""
            SELECT
                schemaname || '.' || relname AS table_name,
                n_live_tup,
                n_dead_tup,
                last_vacuum,
                last_autovacuum,
                last_analyze,
                last_autoanalyze,
                vacuum_count,
                autovacuum_count,
                analyze_count,
                autoanalyze_count
            FROM pg_stat_user_tables
            ORDER BY n_dead_tup DESC
        """)
    finally:
        c.close()

    # Show global settings
    setting_rows = [[r["name"], r["setting"], r["unit"] or "", (r["short_desc"] or "")[:60]] for r in settings]

    out.table(
        "Autovacuum Settings",
        [("Setting", "cyan"), ("Value", "green"), ("Unit", "dim"), ("Description", "dim")],
        setting_rows,
        data_for_json=settings,
    )

    if not tables:
        out.info(f"No user tables found in '{database}'")
        return

    table_rows = [
        [
            r["table_name"],
            str(r["n_dead_tup"]),
            _format_ts(r["last_vacuum"]) or "never",
            _format_ts(r["last_autovacuum"]) or "never",
            _format_ts(r["last_analyze"]) or "never",
            _format_ts(r["last_autoanalyze"]) or "never",
            str(r["vacuum_count"]) + "/" + str(r["autovacuum_count"]),
            str(r["analyze_count"]) + "/" + str(r["autoanalyze_count"]),
        ]
        for r in tables
    ]

    out.table(
        f"Table Vacuum/Analyze Status — {database}",
        [
            ("Table", "cyan"),
            ("Dead Tuples", "red"),
            ("Last Vacuum", ""),
            ("Last Auto-Vacuum", ""),
            ("Last Analyze", ""),
            ("Last Auto-Analyze", ""),
            ("Vac/Auto", "dim"),
            ("Ana/Auto", "dim"),
        ],
        table_rows,
        data_for_json=tables,
    )


def _format_ts(ts: object) -> str:
    """Format a timestamp for display, returning empty string for None."""
    if ts is None:
        return ""
    return str(ts).split(".")[0]


@app.command("freeze")
def vacuum_freeze(
    ctx: typer.Context,
    database: Annotated[str, typer.Argument(help="Target database")],
    table: Annotated[str | None, typer.Option("--table", "-t", help="Specific table to vacuum freeze")] = None,
) -> None:
    """Run VACUUM FREEZE to aggressively freeze old row versions."""
    actx: AppContext = ctx.obj
    out = actx.output

    c = actx.get_client(database=database)
    try:
        table_str = f" {_quote_ident(table)}" if table else ""
        sql = f"VACUUM (FREEZE){table_str}"

        out.info(f"Running: {sql}")
        c.execute(sql)
        target = f"table '{table}'" if table else f"database '{database}'"
        out.success(f"VACUUM FREEZE completed on {target}")
    finally:
        c.close()


@app.command()
def cluster(
    ctx: typer.Context,
    database: Annotated[str, typer.Argument(help="Target database")],
    table: Annotated[str, typer.Argument(help="Table to cluster")],
    index: Annotated[str, typer.Argument(help="Index to cluster by")],
    force: Annotated[
        bool, typer.Option("--force", help="Skip confirmation (CLUSTER locks the table exclusively)")
    ] = False,
) -> None:
    """Physically reorder a table by an index (requires exclusive lock)."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not force:
        if not typer.confirm(
            f"CLUSTER '{table}' USING '{index}'? This locks the table exclusively and may take a long time"
        ):
            raise typer.Exit(0)

    c = actx.get_client(database=database)
    try:
        sql = f"CLUSTER {_quote_ident(table)} USING {_quote_ident(index)}"
        out.info(f"Running: {sql}")
        c.execute(sql)
        out.success(f"CLUSTER completed on table '{table}' using index '{index}'")
    finally:
        c.close()


@app.command()
def checkpoint(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Force a WAL checkpoint."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not force:
        if not typer.confirm("Force a CHECKPOINT? This may cause I/O spike"):
            raise typer.Exit(0)

    c = actx.client
    c.execute("CHECKPOINT")
    out.success("CHECKPOINT completed")


@app.command("frozen-xid")
def frozen_xid(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database for table-level info")] = None,
    top: Annotated[int, typer.Option("--top", "-n", help="Number of tables to show")] = 20,
) -> None:
    """Show transaction ID freeze status (XID age) per database and per table."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Per-database XID age
    db_data = c.fetchall("""
        SELECT
            datname,
            age(datfrozenxid) AS xid_age,
            datfrozenxid::text AS frozen_xid,
            pg_size_pretty(pg_database_size(datname)) AS size
        FROM pg_database
        WHERE datistemplate = false
        ORDER BY age(datfrozenxid) DESC
    """)

    db_rows = [
        [
            r["datname"],
            _xid_age_style(r["xid_age"]),
            r["frozen_xid"],
            r["size"],
        ]
        for r in db_data
    ]

    out.table(
        "Database XID Age (transaction ID freeze status)",
        [
            ("Database", "cyan"),
            ("XID Age", ""),
            ("Frozen XID", "dim"),
            ("Size", "green"),
        ],
        db_rows,
        data_for_json=db_data,
    )

    # Per-table XID age (if database specified)
    if database:
        tc = actx.get_client(database=database)
        try:
            table_data = tc.fetchall(
                """
                SELECT
                    schemaname || '.' || relname AS table_name,
                    age(relfrozenxid) AS xid_age,
                    relfrozenxid::text AS frozen_xid,
                    pg_size_pretty(pg_total_relation_size(relid)) AS size,
                    n_live_tup
                FROM pg_stat_user_tables
                JOIN pg_class ON pg_class.oid = relid
                ORDER BY age(relfrozenxid) DESC
                LIMIT %s
            """,
                (top,),
            )
        finally:
            tc.close()

        if table_data:
            table_rows = [
                [
                    r["table_name"],
                    _xid_age_style(r["xid_age"]),
                    r["frozen_xid"],
                    r["size"],
                    str(r["n_live_tup"]),
                ]
                for r in table_data
            ]

            out.table(
                f"Table XID Age — {database} (top {top})",
                [
                    ("Table", "cyan"),
                    ("XID Age", ""),
                    ("Frozen XID", "dim"),
                    ("Size", "green"),
                    ("Live Tuples", ""),
                ],
                table_rows,
                data_for_json=table_data,
            )
        else:
            out.info(f"No user tables found in '{database}'")


def _xid_age_style(age: int) -> str:
    """Style XID age with color based on proximity to wraparound."""
    if age >= 1_200_000_000:
        return f"[bold red]{age:,}[/bold red] DANGER"
    if age >= 1_000_000_000:
        return f"[red]{age:,}[/red] WARNING"
    if age >= 500_000_000:
        return f"[yellow]{age:,}[/yellow]"
    return f"[green]{age:,}[/green]"
