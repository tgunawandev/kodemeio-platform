"""Index management commands: list, bloat, duplicate, invalid, missing, create-concurrently, reindex-concurrently."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_pg.core.callbacks import AppContext

app = typer.Typer(help="Index inspection and management.")


def _quote_ident(name: str) -> str:
    """Quote a SQL identifier safely."""
    return '"' + name.replace('"', '""') + '"'


@app.command("list")
def list_indexes(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
    table: Annotated[str | None, typer.Option("--table", "-t", help="Filter by table name")] = None,
) -> None:
    """List indexes with size, type, uniqueness, and partial predicate."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    c = actx.get_client(database=db)
    try:
        sql = """
            SELECT
                i.schemaname AS schema,
                i.tablename AS table_name,
                i.indexname AS index_name,
                am.amname AS index_type,
                pg_size_pretty(pg_relation_size(c.oid)) AS index_size,
                pg_relation_size(c.oid) AS index_size_bytes,
                ix.indisunique AS is_unique,
                ix.indisprimary AS is_primary,
                ix.indisvalid AS is_valid,
                pg_get_expr(ix.indpred, ix.indrelid) AS predicate,
                pg_get_indexdef(ix.indexrelid) AS definition
            FROM pg_indexes i
            JOIN pg_class c ON c.relname = i.indexname
                AND c.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = i.schemaname)
            JOIN pg_index ix ON ix.indexrelid = c.oid
            JOIN pg_am am ON am.oid = c.relam
            WHERE i.schemaname NOT IN ('pg_catalog', 'pg_toast', 'information_schema')
        """
        params: list = []
        if table:
            sql += " AND i.tablename = %s"
            params.append(table)
        sql += " ORDER BY pg_relation_size(c.oid) DESC"

        rows_data = c.fetchall(sql, tuple(params) if params else None)
    finally:
        c.close()

    if not rows_data:
        msg = f"No indexes found in '{db}'"
        if table:
            msg += f" for table '{table}'"
        out.info(msg)
        return

    rows = [
        [
            r["table_name"],
            r["index_name"],
            r["index_type"],
            r["index_size"],
            _bool_style(r["is_unique"], "UNIQUE", "-"),
            _bool_style(r["is_primary"], "PK", "-"),
            "[green]yes[/green]" if r["is_valid"] else "[red]INVALID[/red]",
            (r["predicate"] or "-")[:40],
        ]
        for r in rows_data
    ]

    title = f"Indexes — {db}"
    if table:
        title += f".{table}"
    title += f" ({len(rows_data)})"

    out.table(
        title,
        [
            ("Table", "cyan"),
            ("Index", ""),
            ("Type", "yellow"),
            ("Size", "green"),
            ("Unique", ""),
            ("PK", ""),
            ("Valid", ""),
            ("Predicate", "dim"),
        ],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def bloat(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
    top: Annotated[int, typer.Option("--top", "-n", help="Number of indexes to show")] = 20,
) -> None:
    """Estimate index bloat using actual vs expected size ratios."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    c = actx.get_client(database=db)
    try:
        rows_data = c.fetchall(
            """
            WITH index_info AS (
                SELECT
                    s.schemaname,
                    s.relname AS table_name,
                    s.indexrelname AS index_name,
                    pg_relation_size(s.indexrelid) AS actual_size,
                    pg_stat_get_live_tuples(s.relid) AS table_rows,
                    c.relpages,
                    am.amname AS index_type,
                    s.idx_scan
                FROM pg_stat_user_indexes s
                JOIN pg_class c ON c.oid = s.indexrelid
                JOIN pg_am am ON am.oid = c.relam
                WHERE pg_relation_size(s.indexrelid) > 0
            )
            SELECT
                schemaname || '.' || table_name AS table_name,
                index_name,
                index_type,
                pg_size_pretty(actual_size) AS actual_size,
                actual_size AS actual_bytes,
                relpages,
                table_rows,
                idx_scan AS scans,
                CASE
                    WHEN table_rows = 0 THEN 0
                    ELSE greatest(0, round(
                        100.0 * (1.0 - (table_rows * 8.0 / nullif(actual_size, 0)))
                    , 1))
                END AS bloat_estimate_pct,
                CASE
                    WHEN table_rows = 0 THEN 0
                    ELSE greatest(0, actual_size - (table_rows * 8))
                END AS bloat_bytes
            FROM index_info
            WHERE actual_size > 8192
            ORDER BY
                CASE
                    WHEN table_rows = 0 THEN 0
                    ELSE greatest(0, actual_size - (table_rows * 8))
                END DESC
            LIMIT %s
            """,
            (top,),
        )
    finally:
        c.close()

    if not rows_data:
        out.info(f"No indexes found in '{db}'")
        return

    rows = [
        [
            r["table_name"],
            r["index_name"],
            r["index_type"],
            r["actual_size"],
            pg_size_pretty_inline(r["bloat_bytes"]),
            _bloat_style(r["bloat_estimate_pct"]),
            str(r["scans"]),
        ]
        for r in rows_data
    ]

    out.table(
        f"Index Bloat Estimate — {db} (top {top})",
        [
            ("Table", "cyan"),
            ("Index", ""),
            ("Type", "dim"),
            ("Actual Size", "green"),
            ("Bloat Est.", "red"),
            ("Bloat %", ""),
            ("Scans", "dim"),
        ],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def duplicate(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
) -> None:
    """Find duplicate or overlapping indexes (same table, same leading columns)."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    c = actx.get_client(database=db)
    try:
        rows_data = c.fetchall(
            """
            WITH index_cols AS (
                SELECT
                    n.nspname AS schema_name,
                    ct.relname AS table_name,
                    ci.relname AS index_name,
                    ix.indisunique AS is_unique,
                    pg_relation_size(ci.oid) AS index_size,
                    pg_get_indexdef(ix.indexrelid) AS definition,
                    array_to_string(
                        ARRAY(
                            SELECT a.attname
                            FROM unnest(ix.indkey) WITH ORDINALITY AS k(attnum, ord)
                            JOIN pg_attribute a ON a.attrelid = ix.indrelid AND a.attnum = k.attnum
                            ORDER BY k.ord
                        ), ', '
                    ) AS column_list
                FROM pg_index ix
                JOIN pg_class ct ON ct.oid = ix.indrelid
                JOIN pg_class ci ON ci.oid = ix.indexrelid
                JOIN pg_namespace n ON n.oid = ct.relnamespace
                WHERE n.nspname NOT IN ('pg_catalog', 'pg_toast', 'information_schema')
                  AND ix.indisvalid
            )
            SELECT
                a.schema_name || '.' || a.table_name AS table_name,
                a.index_name AS index_a,
                a.column_list AS columns_a,
                pg_size_pretty(a.index_size) AS size_a,
                b.index_name AS index_b,
                b.column_list AS columns_b,
                pg_size_pretty(b.index_size) AS size_b,
                CASE
                    WHEN a.column_list = b.column_list THEN 'DUPLICATE'
                    WHEN starts_with(b.column_list, a.column_list) THEN 'OVERLAP'
                    WHEN starts_with(a.column_list, b.column_list) THEN 'OVERLAP'
                    ELSE 'PARTIAL'
                END AS overlap_type
            FROM index_cols a
            JOIN index_cols b ON a.table_name = b.table_name
                AND a.schema_name = b.schema_name
                AND a.index_name < b.index_name
                AND (
                    a.column_list = b.column_list
                    OR starts_with(a.column_list || ', ', b.column_list || ', ')
                    OR starts_with(b.column_list || ', ', a.column_list || ', ')
                )
            ORDER BY a.table_name, a.index_name
            """
        )
    finally:
        c.close()

    if not rows_data:
        out.success(f"No duplicate or overlapping indexes found in '{db}'")
        return

    rows = [
        [
            r["table_name"],
            r["index_a"],
            r["columns_a"],
            r["size_a"],
            r["index_b"],
            r["columns_b"],
            r["size_b"],
            _overlap_style(r["overlap_type"]),
        ]
        for r in rows_data
    ]

    out.table(
        f"Duplicate/Overlapping Indexes — {db} ({len(rows_data)} pairs)",
        [
            ("Table", "cyan"),
            ("Index A", ""),
            ("Columns A", "dim"),
            ("Size A", "green"),
            ("Index B", ""),
            ("Columns B", "dim"),
            ("Size B", "green"),
            ("Type", ""),
        ],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def invalid(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
) -> None:
    """Find invalid indexes (e.g., from failed REINDEX CONCURRENTLY)."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    c = actx.get_client(database=db)
    try:
        rows_data = c.fetchall(
            """
            SELECT
                n.nspname || '.' || ct.relname AS table_name,
                ci.relname AS index_name,
                pg_size_pretty(pg_relation_size(ci.oid)) AS index_size,
                pg_relation_size(ci.oid) AS index_bytes,
                am.amname AS index_type,
                pg_get_indexdef(ix.indexrelid) AS definition
            FROM pg_index ix
            JOIN pg_class ct ON ct.oid = ix.indrelid
            JOIN pg_class ci ON ci.oid = ix.indexrelid
            JOIN pg_namespace n ON n.oid = ct.relnamespace
            JOIN pg_am am ON am.oid = ci.relam
            WHERE NOT ix.indisvalid
              AND n.nspname NOT IN ('pg_catalog', 'pg_toast', 'information_schema')
            ORDER BY pg_relation_size(ci.oid) DESC
            """
        )
    finally:
        c.close()

    if not rows_data:
        out.success(f"No invalid indexes found in '{db}'")
        return

    rows = [
        [
            r["table_name"],
            r["index_name"],
            r["index_type"],
            r["index_size"],
            r["definition"][:80],
        ]
        for r in rows_data
    ]

    out.table(
        f"Invalid Indexes — {db} ({len(rows_data)})",
        [
            ("Table", "cyan"),
            ("Index", "red"),
            ("Type", "dim"),
            ("Size", "green"),
            ("Definition", "dim"),
        ],
        rows,
        data_for_json=rows_data,
    )

    out.warn("Fix invalid indexes with: kctl-pg indexes reindex-concurrently <index_name> --db " + db)


@app.command()
def missing(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
    min_size: Annotated[str, typer.Option("--min-size", help="Minimum table size (e.g. '10 MB')")] = "1 MB",
) -> None:
    """Find tables with high sequential scan counts suggesting missing indexes."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    c = actx.get_client(database=db)
    try:
        rows_data = c.fetchall(
            """
            SELECT
                s.schemaname || '.' || s.relname AS table_name,
                pg_size_pretty(pg_total_relation_size(s.relid)) AS table_size,
                pg_total_relation_size(s.relid) AS table_bytes,
                s.seq_scan,
                s.seq_tup_read,
                s.idx_scan,
                COALESCE(s.idx_tup_fetch, 0) AS idx_tup_fetch,
                s.n_live_tup AS row_estimate,
                CASE
                    WHEN s.seq_scan + COALESCE(s.idx_scan, 0) = 0 THEN 0
                    ELSE round(100.0 * s.seq_scan / (s.seq_scan + COALESCE(s.idx_scan, 0)), 1)
                END AS seq_scan_pct,
                (SELECT count(*)
                 FROM pg_index i
                 WHERE i.indrelid = s.relid
                   AND i.indisvalid) AS index_count
            FROM pg_stat_user_tables s
            WHERE s.seq_scan > 0
              AND s.n_live_tup > 100
              AND pg_total_relation_size(s.relid) >= pg_size_bytes(%s)
            ORDER BY s.seq_tup_read DESC
            """,
            (min_size,),
        )
    finally:
        c.close()

    if not rows_data:
        out.success(f"No tables with significant sequential scans found in '{db}'")
        return

    rows = [
        [
            r["table_name"],
            r["table_size"],
            f"{r['row_estimate']:,}",
            f"{r['seq_scan']:,}",
            f"{r['seq_tup_read']:,}",
            str(r["idx_scan"] or 0),
            _seq_pct_style(r["seq_scan_pct"]),
            str(r["index_count"]),
        ]
        for r in rows_data
    ]

    out.table(
        f"Potential Missing Indexes — {db} (tables >= {min_size})",
        [
            ("Table", "cyan"),
            ("Size", "green"),
            ("Rows", ""),
            ("Seq Scans", "red"),
            ("Seq Rows Read", "yellow"),
            ("Idx Scans", ""),
            ("Seq Scan %", ""),
            ("# Indexes", "dim"),
        ],
        rows,
        data_for_json=rows_data,
    )


@app.command("create-concurrently")
def create_concurrently(
    ctx: typer.Context,
    table: Annotated[str, typer.Argument(help="Table to create index on")],
    columns: Annotated[str, typer.Argument(help="Comma-separated column names")],
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Custom index name")] = None,
    unique: Annotated[bool, typer.Option("--unique", help="Create a UNIQUE index")] = False,
    schema: Annotated[str, typer.Option("--schema", "-s", help="Table schema")] = "public",
) -> None:
    """Create an index concurrently (non-blocking)."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    # Parse and quote column names
    col_list = [c.strip() for c in columns.split(",") if c.strip()]
    if not col_list:
        out.error("No columns specified")
        raise typer.Exit(1)

    quoted_cols = ", ".join(_quote_ident(c) for c in col_list)
    qualified_table = f"{_quote_ident(schema)}.{_quote_ident(table)}"

    # Generate index name if not provided
    if name:
        idx_name = _quote_ident(name)
    else:
        col_suffix = "_".join(col_list)
        idx_name = _quote_ident(f"idx_{table}_{col_suffix}")

    unique_str = "UNIQUE " if unique else ""
    sql = f"CREATE {unique_str}INDEX CONCURRENTLY {idx_name} ON {qualified_table} ({quoted_cols})"

    out.info(f"Running: {sql}")

    c = actx.get_client(database=db)
    try:
        c.execute(sql)
        out.success(f"Index {idx_name} created concurrently on {qualified_table}")
    finally:
        c.close()


@app.command("reindex-concurrently")
def reindex_concurrently(
    ctx: typer.Context,
    target: Annotated[str, typer.Argument(help="Index name or table name (with --table)")],
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
    is_table: Annotated[bool, typer.Option("--table", "-t", help="Reindex all indexes on a table")] = False,
) -> None:
    """Reindex an index or table concurrently (non-blocking)."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    if is_table:
        sql = f"REINDEX TABLE CONCURRENTLY {_quote_ident(target)}"
        label = f"table '{target}'"
    else:
        sql = f"REINDEX INDEX CONCURRENTLY {_quote_ident(target)}"
        label = f"index '{target}'"

    out.info(f"Running: {sql}")

    c = actx.get_client(database=db)
    try:
        c.execute(sql)
        out.success(f"REINDEX CONCURRENTLY completed on {label}")
    finally:
        c.close()


# --- Helper functions ---


def pg_size_pretty_inline(nbytes: object) -> str:
    """Convert bytes to human-readable size string (client-side)."""
    if nbytes is None:
        return "-"
    b = int(nbytes)
    if b < 0:
        return "0 bytes"
    for unit in ("bytes", "kB", "MB", "GB", "TB"):
        if abs(b) < 1024:
            if unit == "bytes":
                return f"{b} {unit}"
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def _bool_style(val: bool, true_label: str, false_label: str) -> str:
    """Style a boolean value."""
    if val:
        return f"[green]{true_label}[/green]"
    return false_label


def _bloat_style(pct: object) -> str:
    """Style bloat percentage with color coding."""
    if pct is None:
        return "-"
    p = float(pct)
    if p >= 50:
        return f"[red]{p}%[/red]"
    if p >= 30:
        return f"[yellow]{p}%[/yellow]"
    if p >= 10:
        return f"[cyan]{p}%[/cyan]"
    return f"[green]{p}%[/green]"


def _overlap_style(overlap_type: str) -> str:
    """Style overlap type."""
    if overlap_type == "DUPLICATE":
        return "[red]DUPLICATE[/red]"
    if overlap_type == "OVERLAP":
        return "[yellow]OVERLAP[/yellow]"
    return f"[dim]{overlap_type}[/dim]"


def _seq_pct_style(pct: object) -> str:
    """Style sequential scan percentage."""
    if pct is None:
        return "-"
    p = float(pct)
    if p >= 90:
        return f"[red]{p}%[/red]"
    if p >= 70:
        return f"[yellow]{p}%[/yellow]"
    if p >= 50:
        return f"[cyan]{p}%[/cyan]"
    return f"[green]{p}%[/green]"
