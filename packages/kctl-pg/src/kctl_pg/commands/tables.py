"""Table management commands: list, describe, size, partitions, constraints, triggers, dependencies, toast, sequences."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_pg.core.callbacks import AppContext

app = typer.Typer(help="Table inspection and management.")


def _quote_ident(name: str) -> str:
    """Quote a SQL identifier safely."""
    return '"' + name.replace('"', '""') + '"'


def _format_ts(ts: object) -> str:
    """Format a timestamp for display, returning '-' for None."""
    if ts is None:
        return "-"
    return str(ts).split(".")[0]


@app.command("list")
def list_tables(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
    schema: Annotated[str, typer.Option("--schema", "-s", help="Schema to list tables from")] = "public",
) -> None:
    """List tables with sizes in a database."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    c = actx.get_client(database=db)
    try:
        rows_data = c.fetchall(
            """
            SELECT
                t.schemaname AS schema,
                t.tablename AS table_name,
                t.tableowner AS owner,
                pg_size_pretty(pg_total_relation_size(quote_ident(t.schemaname) || '.' || quote_ident(t.tablename))) AS total_size,
                pg_total_relation_size(quote_ident(t.schemaname) || '.' || quote_ident(t.tablename)) AS total_size_bytes,
                pg_size_pretty(pg_relation_size(quote_ident(t.schemaname) || '.' || quote_ident(t.tablename))) AS table_size,
                COALESCE(s.n_live_tup, 0) AS row_estimate,
                CASE WHEN t.tablename LIKE '%%_partition%%' OR EXISTS (
                    SELECT 1 FROM pg_inherits i
                    JOIN pg_class pc ON pc.oid = i.inhparent
                    JOIN pg_namespace pn ON pn.oid = pc.relnamespace
                    WHERE pn.nspname = t.schemaname AND pc.relname = t.tablename
                ) THEN 'yes' ELSE 'no' END AS has_children
            FROM pg_tables t
            LEFT JOIN pg_stat_user_tables s
                ON s.schemaname = t.schemaname AND s.relname = t.tablename
            WHERE t.schemaname = %s
            ORDER BY pg_total_relation_size(quote_ident(t.schemaname) || '.' || quote_ident(t.tablename)) DESC
            """,
            (schema,),
        )
    finally:
        c.close()

    if not rows_data:
        out.info(f"No tables found in '{db}' schema '{schema}'")
        return

    rows = [
        [
            r["table_name"],
            r["owner"],
            r["total_size"],
            r["table_size"],
            f"{r['row_estimate']:,}",
            r["has_children"],
        ]
        for r in rows_data
    ]

    out.table(
        f"Tables — {db}.{schema} ({len(rows_data)} tables)",
        [
            ("Table", "cyan"),
            ("Owner", "dim"),
            ("Total Size", "green"),
            ("Table Size", ""),
            ("Row Estimate", ""),
            ("Partitioned", "dim"),
        ],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def describe(
    ctx: typer.Context,
    table: Annotated[str, typer.Argument(help="Table name to describe")],
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
    schema: Annotated[str, typer.Option("--schema", "-s", help="Table schema")] = "public",
) -> None:
    """Show table structure: columns, types, constraints, defaults."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    c = actx.get_client(database=db)
    try:
        # Columns
        columns_data = c.fetchall(
            """
            SELECT
                c.column_name,
                c.data_type,
                c.character_maximum_length,
                c.numeric_precision,
                c.numeric_scale,
                c.is_nullable,
                c.column_default,
                c.ordinal_position
            FROM information_schema.columns c
            WHERE c.table_schema = %s AND c.table_name = %s
            ORDER BY c.ordinal_position
            """,
            (schema, table),
        )

        if not columns_data:
            out.error(f"Table '{schema}.{table}' not found in '{db}'")
            return

        # Constraints
        constraints_data = c.fetchall(
            """
            SELECT
                con.conname AS constraint_name,
                con.contype AS constraint_type,
                pg_get_constraintdef(con.oid) AS definition
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            WHERE nsp.nspname = %s AND rel.relname = %s
            ORDER BY con.contype, con.conname
            """,
            (schema, table),
        )

        # Table size
        size_info = c.fetchone(
            """
            SELECT
                pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
                pg_size_pretty(pg_relation_size(c.oid)) AS table_size,
                pg_size_pretty(pg_indexes_size(c.oid)) AS indexes_size,
                COALESCE(s.n_live_tup, 0) AS row_estimate
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
            WHERE n.nspname = %s AND c.relname = %s
            """,
            (schema, table),
        )
    finally:
        c.close()

    contype_map = {"p": "PK", "f": "FK", "u": "UNIQUE", "c": "CHECK", "x": "EXCLUDE"}

    # Columns table
    col_rows = [
        [
            str(r["ordinal_position"]),
            r["column_name"],
            _format_type(r),
            "YES" if r["is_nullable"] == "YES" else "[dim]NO[/dim]",
            str(r["column_default"])[:40] if r["column_default"] else "-",
        ]
        for r in columns_data
    ]

    # Size detail
    if size_info:
        sections = [
            (
                "Table Info",
                [
                    ("Full Name", f"{schema}.{table}"),
                    ("Total Size", size_info["total_size"]),
                    ("Table Size", size_info["table_size"]),
                    ("Indexes Size", size_info["indexes_size"]),
                    ("Row Estimate", f"{size_info['row_estimate']:,}"),
                ],
            ),
        ]
        json_data = {
            "table": f"{schema}.{table}",
            "size": dict(size_info) if size_info else {},
            "columns": columns_data,
            "constraints": constraints_data,
        }
        out.detail(f"Table: {schema}.{table}", sections, data_for_json=json_data)

    out.table(
        "Columns",
        [
            ("#", "dim"),
            ("Column", "cyan"),
            ("Type", "green"),
            ("Nullable", ""),
            ("Default", "dim"),
        ],
        col_rows,
        data_for_json=columns_data,
    )

    # Constraints table
    if constraints_data:
        con_rows = [
            [
                r["constraint_name"],
                contype_map.get(r["constraint_type"], r["constraint_type"]),
                r["definition"][:80],
            ]
            for r in constraints_data
        ]
        out.table(
            "Constraints",
            [
                ("Name", "cyan"),
                ("Type", "yellow"),
                ("Definition", "dim"),
            ],
            con_rows,
            data_for_json=constraints_data,
        )
    else:
        out.info("No constraints defined")


@app.command()
def size(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
    top: Annotated[int, typer.Option("--top", "-n", help="Number of tables to show")] = 20,
) -> None:
    """Show table sizes with breakdown (table, toast, indexes)."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    c = actx.get_client(database=db)
    try:
        rows_data = c.fetchall(
            """
            SELECT
                n.nspname || '.' || c.relname AS table_name,
                pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
                pg_total_relation_size(c.oid) AS total_bytes,
                pg_size_pretty(pg_relation_size(c.oid)) AS table_size,
                pg_relation_size(c.oid) AS table_bytes,
                pg_size_pretty(pg_indexes_size(c.oid)) AS indexes_size,
                pg_indexes_size(c.oid) AS indexes_bytes,
                pg_size_pretty(
                    pg_total_relation_size(c.oid) - pg_relation_size(c.oid) - pg_indexes_size(c.oid)
                ) AS toast_size,
                pg_total_relation_size(c.oid) - pg_relation_size(c.oid) - pg_indexes_size(c.oid) AS toast_bytes
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r'
              AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
            ORDER BY pg_total_relation_size(c.oid) DESC
            LIMIT %s
            """,
            (top,),
        )
    finally:
        c.close()

    if not rows_data:
        out.info(f"No user tables found in '{db}'")
        return

    rows = [
        [
            r["table_name"],
            r["total_size"],
            r["table_size"],
            r["indexes_size"],
            r["toast_size"],
            _size_bar(r["table_bytes"], r["indexes_bytes"], r["toast_bytes"]),
        ]
        for r in rows_data
    ]

    out.table(
        f"Table Sizes — {db} (top {top})",
        [
            ("Table", "cyan"),
            ("Total", "green"),
            ("Table", ""),
            ("Indexes", "yellow"),
            ("TOAST", "dim"),
            ("Distribution", ""),
        ],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def partitions(
    ctx: typer.Context,
    table: Annotated[str, typer.Argument(help="Parent table name")],
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
    schema: Annotated[str, typer.Option("--schema", "-s", help="Table schema")] = "public",
) -> None:
    """Show partition children and their bounds."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    c = actx.get_client(database=db)
    try:
        rows_data = c.fetchall(
            """
            SELECT
                child_ns.nspname || '.' || child.relname AS partition_name,
                pg_get_expr(child.relpartbound, child.oid) AS partition_bound,
                pg_size_pretty(pg_total_relation_size(child.oid)) AS total_size,
                pg_total_relation_size(child.oid) AS total_bytes,
                COALESCE(s.n_live_tup, 0) AS row_estimate
            FROM pg_inherits i
            JOIN pg_class parent ON parent.oid = i.inhparent
            JOIN pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace
            JOIN pg_class child ON child.oid = i.inhrelid
            JOIN pg_namespace child_ns ON child_ns.oid = child.relnamespace
            LEFT JOIN pg_stat_user_tables s ON s.relid = child.oid
            WHERE parent_ns.nspname = %s AND parent.relname = %s
            ORDER BY child.relname
            """,
            (schema, table),
        )

        # Get partition strategy
        part_info = c.fetchone(
            """
            SELECT
                partstrat,
                pg_get_partkeydef(partrelid) AS partition_key
            FROM pg_partitioned_table pt
            JOIN pg_class c ON c.oid = pt.partrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = %s
            """,
            (schema, table),
        )
    finally:
        c.close()

    if not rows_data and not part_info:
        out.info(f"Table '{schema}.{table}' has no partitions or is not partitioned")
        return

    strat_map = {"r": "RANGE", "l": "LIST", "h": "HASH"}

    if part_info:
        sections = [
            (
                "Partition Info",
                [
                    ("Table", f"{schema}.{table}"),
                    ("Strategy", strat_map.get(part_info["partstrat"], part_info["partstrat"])),
                    ("Partition Key", part_info["partition_key"]),
                    ("Children", str(len(rows_data))),
                ],
            ),
        ]
        json_data = {
            "table": f"{schema}.{table}",
            "strategy": strat_map.get(part_info["partstrat"], part_info["partstrat"]),
            "partition_key": part_info["partition_key"],
            "partitions": rows_data,
        }
        out.detail(f"Partitions: {schema}.{table}", sections, data_for_json=json_data)

    if rows_data:
        rows = [
            [
                r["partition_name"],
                r["partition_bound"] or "-",
                r["total_size"],
                f"{r['row_estimate']:,}",
            ]
            for r in rows_data
        ]

        out.table(
            f"Partition Children ({len(rows_data)})",
            [
                ("Partition", "cyan"),
                ("Bound", "green"),
                ("Size", "yellow"),
                ("Row Estimate", ""),
            ],
            rows,
            data_for_json=rows_data,
        )


@app.command()
def constraints(
    ctx: typer.Context,
    table: Annotated[str, typer.Argument(help="Table name")],
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
    schema: Annotated[str, typer.Option("--schema", "-s", help="Table schema")] = "public",
) -> None:
    """Show all constraints on a table (PK, FK, UNIQUE, CHECK)."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    c = actx.get_client(database=db)
    try:
        rows_data = c.fetchall(
            """
            SELECT
                con.conname AS constraint_name,
                CASE con.contype
                    WHEN 'p' THEN 'PRIMARY KEY'
                    WHEN 'f' THEN 'FOREIGN KEY'
                    WHEN 'u' THEN 'UNIQUE'
                    WHEN 'c' THEN 'CHECK'
                    WHEN 'x' THEN 'EXCLUDE'
                    ELSE con.contype::text
                END AS constraint_type,
                pg_get_constraintdef(con.oid, true) AS definition,
                con.convalidated AS is_validated,
                con.condeferrable AS is_deferrable,
                con.condeferred AS is_deferred
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            WHERE nsp.nspname = %s AND rel.relname = %s
            ORDER BY
                CASE con.contype
                    WHEN 'p' THEN 1
                    WHEN 'u' THEN 2
                    WHEN 'f' THEN 3
                    WHEN 'c' THEN 4
                    ELSE 5
                END,
                con.conname
            """,
            (schema, table),
        )
    finally:
        c.close()

    if not rows_data:
        out.info(f"No constraints found on '{schema}.{table}'")
        return

    rows = [
        [
            r["constraint_name"],
            _constraint_style(r["constraint_type"]),
            r["definition"][:80],
            "[green]yes[/green]" if r["is_validated"] else "[red]no[/red]",
            "yes" if r["is_deferrable"] else "-",
        ]
        for r in rows_data
    ]

    out.table(
        f"Constraints — {schema}.{table} ({len(rows_data)})",
        [
            ("Name", "cyan"),
            ("Type", ""),
            ("Definition", "dim"),
            ("Validated", ""),
            ("Deferrable", "dim"),
        ],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def triggers(
    ctx: typer.Context,
    table: Annotated[str, typer.Argument(help="Table name")],
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
    schema: Annotated[str, typer.Option("--schema", "-s", help="Table schema")] = "public",
) -> None:
    """Show triggers on a table with event, function, and enabled status."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    c = actx.get_client(database=db)
    try:
        rows_data = c.fetchall(
            """
            SELECT
                t.tgname AS trigger_name,
                CASE
                    WHEN t.tgtype & 2 = 2 THEN 'BEFORE'
                    WHEN t.tgtype & 64 = 64 THEN 'INSTEAD OF'
                    ELSE 'AFTER'
                END AS timing,
                array_to_string(ARRAY[
                    CASE WHEN t.tgtype & 4 = 4 THEN 'INSERT' END,
                    CASE WHEN t.tgtype & 8 = 8 THEN 'DELETE' END,
                    CASE WHEN t.tgtype & 16 = 16 THEN 'UPDATE' END,
                    CASE WHEN t.tgtype & 32 = 32 THEN 'TRUNCATE' END
                ], ', ') AS events,
                p.proname AS function_name,
                CASE t.tgenabled
                    WHEN 'O' THEN 'ORIGIN'
                    WHEN 'D' THEN 'DISABLED'
                    WHEN 'R' THEN 'REPLICA'
                    WHEN 'A' THEN 'ALWAYS'
                    ELSE t.tgenabled::text
                END AS enabled_status,
                CASE WHEN t.tgtype & 1 = 1 THEN 'ROW' ELSE 'STATEMENT' END AS level
            FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_proc p ON p.oid = t.tgfoid
            WHERE n.nspname = %s
              AND c.relname = %s
              AND NOT t.tgisinternal
            ORDER BY t.tgname
            """,
            (schema, table),
        )
    finally:
        c.close()

    if not rows_data:
        out.info(f"No triggers found on '{schema}.{table}'")
        return

    rows = [
        [
            r["trigger_name"],
            r["timing"],
            r["events"],
            r["level"],
            r["function_name"],
            _trigger_enabled_style(r["enabled_status"]),
        ]
        for r in rows_data
    ]

    out.table(
        f"Triggers — {schema}.{table} ({len(rows_data)})",
        [
            ("Trigger", "cyan"),
            ("Timing", ""),
            ("Events", "green"),
            ("Level", "dim"),
            ("Function", "yellow"),
            ("Status", ""),
        ],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def dependencies(
    ctx: typer.Context,
    table: Annotated[str, typer.Argument(help="Table name")],
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
    schema: Annotated[str, typer.Option("--schema", "-s", help="Table schema")] = "public",
) -> None:
    """Show foreign key references to and from a table."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    c = actx.get_client(database=db)
    try:
        # FK references FROM this table (outgoing)
        outgoing = c.fetchall(
            """
            SELECT
                con.conname AS constraint_name,
                a.attname AS column_name,
                ref_ns.nspname || '.' || ref_cl.relname AS referenced_table,
                ref_a.attname AS referenced_column,
                CASE con.confdeltype
                    WHEN 'a' THEN 'NO ACTION'
                    WHEN 'r' THEN 'RESTRICT'
                    WHEN 'c' THEN 'CASCADE'
                    WHEN 'n' THEN 'SET NULL'
                    WHEN 'd' THEN 'SET DEFAULT'
                    ELSE con.confdeltype::text
                END AS on_delete,
                CASE con.confupdtype
                    WHEN 'a' THEN 'NO ACTION'
                    WHEN 'r' THEN 'RESTRICT'
                    WHEN 'c' THEN 'CASCADE'
                    WHEN 'n' THEN 'SET NULL'
                    WHEN 'd' THEN 'SET DEFAULT'
                    ELSE con.confupdtype::text
                END AS on_update
            FROM pg_constraint con
            JOIN pg_class cl ON cl.oid = con.conrelid
            JOIN pg_namespace ns ON ns.oid = cl.relnamespace
            JOIN pg_class ref_cl ON ref_cl.oid = con.confrelid
            JOIN pg_namespace ref_ns ON ref_ns.oid = ref_cl.relnamespace
            JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = ANY(con.conkey)
            JOIN pg_attribute ref_a ON ref_a.attrelid = con.confrelid AND ref_a.attnum = ANY(con.confkey)
            WHERE con.contype = 'f'
              AND ns.nspname = %s
              AND cl.relname = %s
            ORDER BY con.conname
            """,
            (schema, table),
        )

        # FK references TO this table (incoming)
        incoming = c.fetchall(
            """
            SELECT
                con.conname AS constraint_name,
                src_ns.nspname || '.' || src_cl.relname AS source_table,
                a.attname AS source_column,
                ref_a.attname AS referenced_column,
                CASE con.confdeltype
                    WHEN 'a' THEN 'NO ACTION'
                    WHEN 'r' THEN 'RESTRICT'
                    WHEN 'c' THEN 'CASCADE'
                    WHEN 'n' THEN 'SET NULL'
                    WHEN 'd' THEN 'SET DEFAULT'
                    ELSE con.confdeltype::text
                END AS on_delete
            FROM pg_constraint con
            JOIN pg_class src_cl ON src_cl.oid = con.conrelid
            JOIN pg_namespace src_ns ON src_ns.oid = src_cl.relnamespace
            JOIN pg_class ref_cl ON ref_cl.oid = con.confrelid
            JOIN pg_namespace ref_ns ON ref_ns.oid = ref_cl.relnamespace
            JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = ANY(con.conkey)
            JOIN pg_attribute ref_a ON ref_a.attrelid = con.confrelid AND ref_a.attnum = ANY(con.confkey)
            WHERE con.contype = 'f'
              AND ref_ns.nspname = %s
              AND ref_cl.relname = %s
            ORDER BY src_cl.relname, con.conname
            """,
            (schema, table),
        )
    finally:
        c.close()

    json_data = {
        "table": f"{schema}.{table}",
        "outgoing_fks": outgoing,
        "incoming_fks": incoming,
    }

    if not outgoing and not incoming:
        out.info(f"No foreign key dependencies for '{schema}.{table}'")
        if actx.json_mode:
            out.raw_json(json_data)
        return

    if outgoing:
        out_rows = [
            [
                r["constraint_name"],
                r["column_name"],
                r["referenced_table"],
                r["referenced_column"],
                r["on_delete"],
                r["on_update"],
            ]
            for r in outgoing
        ]

        out.table(
            f"Outgoing FKs — {schema}.{table} references...",
            [
                ("Constraint", "cyan"),
                ("Column", ""),
                ("Referenced Table", "green"),
                ("Referenced Column", ""),
                ("ON DELETE", "yellow"),
                ("ON UPDATE", "dim"),
            ],
            out_rows,
            data_for_json=outgoing,
        )

    if incoming:
        in_rows = [
            [
                r["constraint_name"],
                r["source_table"],
                r["source_column"],
                r["referenced_column"],
                r["on_delete"],
            ]
            for r in incoming
        ]

        out.table(
            f"Incoming FKs — ...references {schema}.{table}",
            [
                ("Constraint", "cyan"),
                ("Source Table", "green"),
                ("Source Column", ""),
                ("Referenced Column", ""),
                ("ON DELETE", "yellow"),
            ],
            in_rows,
            data_for_json=incoming,
        )


@app.command()
def toast(
    ctx: typer.Context,
    table: Annotated[str, typer.Argument(help="Table name")],
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
    schema: Annotated[str, typer.Option("--schema", "-s", help="Table schema")] = "public",
) -> None:
    """Show TOAST table statistics for a table."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    c = actx.get_client(database=db)
    try:
        toast_info = c.fetchone(
            """
            SELECT
                c.relname AS table_name,
                t.relname AS toast_table,
                pg_size_pretty(pg_relation_size(c.reltoastrelid)) AS toast_size,
                pg_relation_size(c.reltoastrelid) AS toast_bytes,
                pg_size_pretty(pg_total_relation_size(c.oid)) AS total_table_size,
                pg_size_pretty(pg_relation_size(c.oid)) AS heap_size,
                pg_size_pretty(pg_indexes_size(c.oid)) AS indexes_size,
                t.reltuples::bigint AS toast_tuples
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_class t ON t.oid = c.reltoastrelid
            WHERE n.nspname = %s AND c.relname = %s
            """,
            (schema, table),
        )

        # TOAST columns info
        toast_cols = c.fetchall(
            """
            SELECT
                a.attname AS column_name,
                format_type(a.atttypid, a.atttypmod) AS data_type,
                CASE a.attstorage
                    WHEN 'p' THEN 'PLAIN'
                    WHEN 'e' THEN 'EXTERNAL'
                    WHEN 'm' THEN 'MAIN'
                    WHEN 'x' THEN 'EXTENDED'
                    ELSE a.attstorage::text
                END AS storage_strategy
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s
              AND c.relname = %s
              AND a.attnum > 0
              AND NOT a.attisdropped
              AND a.attstorage != 'p'
            ORDER BY a.attnum
            """,
            (schema, table),
        )
    finally:
        c.close()

    if not toast_info:
        out.error(f"Table '{schema}.{table}' not found in '{db}'")
        return

    if not toast_info["toast_table"]:
        out.info(f"Table '{schema}.{table}' has no TOAST table")
        return

    sections = [
        (
            "TOAST Table",
            [
                ("Table", f"{schema}.{table}"),
                ("TOAST Table", toast_info["toast_table"]),
                ("TOAST Size", toast_info["toast_size"]),
                ("TOAST Tuples", f"{toast_info['toast_tuples']:,}"),
                ("Total Table Size", toast_info["total_table_size"]),
                ("Heap Size", toast_info["heap_size"]),
                ("Indexes Size", toast_info["indexes_size"]),
            ],
        ),
    ]

    json_data = {
        "table": f"{schema}.{table}",
        "toast": dict(toast_info) if toast_info else {},
        "toastable_columns": toast_cols,
    }

    out.detail(f"TOAST Info: {schema}.{table}", sections, data_for_json=json_data)

    if toast_cols:
        col_rows = [
            [
                r["column_name"],
                r["data_type"],
                _storage_style(r["storage_strategy"]),
            ]
            for r in toast_cols
        ]

        out.table(
            "TOASTable Columns",
            [
                ("Column", "cyan"),
                ("Type", ""),
                ("Storage", "yellow"),
            ],
            col_rows,
            data_for_json=toast_cols,
        )


@app.command()
def sequences(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
    near_max: Annotated[bool, typer.Option("--near-max", help="Only show sequences >80%% used")] = False,
) -> None:
    """Show sequences with current value and percentage used."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    c = actx.get_client(database=db)
    try:
        rows_data = c.fetchall(
            """
            SELECT
                schemaname || '.' || sequencename AS sequence_name,
                sequenceowner AS owner,
                data_type,
                start_value,
                min_value,
                max_value,
                increment_by,
                cycle AS is_cycle,
                last_value,
                CASE
                    WHEN max_value = 0 OR last_value IS NULL THEN 0
                    ELSE round(100.0 * COALESCE(last_value, start_value) / max_value, 2)
                END AS pct_used
            FROM pg_sequences
            ORDER BY
                CASE
                    WHEN max_value = 0 OR last_value IS NULL THEN 0
                    ELSE round(100.0 * COALESCE(last_value, start_value) / max_value, 2)
                END DESC
            """
        )
    finally:
        c.close()

    if near_max:
        rows_data = [r for r in rows_data if r["pct_used"] and float(r["pct_used"]) > 80]

    if not rows_data:
        msg = f"No sequences found in '{db}'"
        if near_max:
            msg += " with >80% usage"
        out.info(msg)
        return

    rows = [
        [
            r["sequence_name"],
            r["data_type"],
            str(r["last_value"]) if r["last_value"] is not None else "not yet used",
            str(r["max_value"]),
            _pct_style(r["pct_used"]),
            "yes" if r["is_cycle"] else "no",
            r["owner"],
        ]
        for r in rows_data
    ]

    title = f"Sequences — {db}"
    if near_max:
        title += " (>80% used only)"
    title += f" ({len(rows_data)})"

    out.table(
        title,
        [
            ("Sequence", "cyan"),
            ("Type", "dim"),
            ("Current Value", ""),
            ("Max Value", "dim"),
            ("% Used", ""),
            ("Cycle", "dim"),
            ("Owner", "dim"),
        ],
        rows,
        data_for_json=rows_data,
    )


# --- Helper functions ---


def _format_type(col: dict) -> str:
    """Format column type with precision info."""
    dtype = col["data_type"]
    if col["character_maximum_length"]:
        return f"{dtype}({col['character_maximum_length']})"
    if col["numeric_precision"] and col["numeric_scale"] is not None:
        return f"{dtype}({col['numeric_precision']},{col['numeric_scale']})"
    return dtype


def _size_bar(table_bytes: int, index_bytes: int, toast_bytes: int) -> str:
    """Create a simple text-based distribution indicator."""
    total = table_bytes + index_bytes + toast_bytes
    if total == 0:
        return "-"
    t_pct = round(100 * table_bytes / total)
    i_pct = round(100 * index_bytes / total)
    to_pct = 100 - t_pct - i_pct
    return f"T:{t_pct}% I:{i_pct}% TO:{to_pct}%"


def _constraint_style(ctype: str) -> str:
    """Style constraint type with color."""
    colors = {
        "PRIMARY KEY": "green",
        "FOREIGN KEY": "cyan",
        "UNIQUE": "yellow",
        "CHECK": "magenta",
        "EXCLUDE": "red",
    }
    color = colors.get(ctype, "")
    if color:
        return f"[{color}]{ctype}[/{color}]"
    return ctype


def _trigger_enabled_style(status: str) -> str:
    """Style trigger enabled status."""
    if status == "DISABLED":
        return "[red]DISABLED[/red]"
    if status == "ORIGIN":
        return "[green]ORIGIN[/green]"
    if status == "ALWAYS":
        return "[green]ALWAYS[/green]"
    return f"[yellow]{status}[/yellow]"


def _storage_style(strategy: str) -> str:
    """Style TOAST storage strategy."""
    colors = {
        "EXTENDED": "green",
        "EXTERNAL": "yellow",
        "MAIN": "cyan",
        "PLAIN": "dim",
    }
    color = colors.get(strategy, "")
    if color:
        return f"[{color}]{strategy}[/{color}]"
    return strategy


def _pct_style(pct: object) -> str:
    """Style percentage used with color coding."""
    if pct is None:
        return "-"
    p = float(pct)
    if p >= 90:
        return f"[red]{p}%[/red]"
    if p >= 80:
        return f"[yellow]{p}%[/yellow]"
    if p >= 50:
        return f"[cyan]{p}%[/cyan]"
    return f"[green]{p}%[/green]"
