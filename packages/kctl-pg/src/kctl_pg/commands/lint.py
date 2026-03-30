"""Lint commands: schema, indexes, permissions, all — quality checks for CI/CD."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_pg.core.callbacks import AppContext

app = typer.Typer(help="Schema and configuration quality checks.")


# ---------------------------------------------------------------------------
# Severity helpers
# ---------------------------------------------------------------------------

_SEVERITIES = {"error": 3, "warning": 2, "info": 1}


def _finding(severity: str, category: str, table: str, message: str) -> dict:
    return {
        "severity": severity,
        "category": category,
        "object": table,
        "message": message,
    }


def _severity_style(sev: str) -> str:
    if sev == "error":
        return f"[red]{sev.upper()}[/red]"
    if sev == "warning":
        return f"[yellow]{sev.upper()}[/yellow]"
    return f"[blue]{sev.upper()}[/blue]"


# ---------------------------------------------------------------------------
# lint schema
# ---------------------------------------------------------------------------


@app.command()
def schema(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
) -> None:
    """Check naming conventions, missing PKs, column types, and NOT NULL gaps."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    c = actx.get_client(database=db)
    try:
        findings = _check_schema(c)
    finally:
        c.close()

    _render_findings(out, f"Schema Lint — {db}", findings)


def _check_schema(c) -> list[dict]:  # noqa: C901
    findings: list[dict] = []

    # 1. Non-snake_case table names
    rows = c.fetchall("""
        SELECT schemaname, tablename
        FROM pg_tables
        WHERE schemaname NOT IN ('pg_catalog', 'information_schema', 'pg_toast', 'audit')
    """)
    for r in rows:
        tbl = r["tablename"]
        if tbl != tbl.lower() or " " in tbl or "-" in tbl:
            findings.append(
                _finding(
                    "warning",
                    "naming",
                    f"{r['schemaname']}.{tbl}",
                    f"Table name is not snake_case: '{tbl}'",
                )
            )

    # 2. Tables without primary keys
    rows = c.fetchall("""
        SELECT n.nspname AS schema, c.relname AS table_name
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'r'
          AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast', 'audit')
          AND NOT EXISTS (
              SELECT 1 FROM pg_index i
              WHERE i.indrelid = c.oid AND i.indisprimary
          )
    """)
    for r in rows:
        findings.append(
            _finding(
                "error",
                "primary_key",
                f"{r['schema']}.{r['table_name']}",
                "Table has no primary key",
            )
        )

    # 3. Tables with no indexes at all
    rows = c.fetchall("""
        SELECT n.nspname AS schema, c.relname AS table_name,
               pg_stat_get_live_tuples(c.oid) AS row_estimate
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'r'
          AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast', 'audit')
          AND pg_stat_get_live_tuples(c.oid) > 100
          AND NOT EXISTS (
              SELECT 1 FROM pg_index i WHERE i.indrelid = c.oid
          )
    """)
    for r in rows:
        findings.append(
            _finding(
                "warning",
                "missing_index",
                f"{r['schema']}.{r['table_name']}",
                f"Table has {r['row_estimate']} rows but no indexes",
            )
        )

    # 4. FK columns not following _id suffix convention
    rows = c.fetchall("""
        SELECT
            n.nspname AS schema,
            cl.relname AS table_name,
            a.attname AS column_name,
            ct.relname AS referenced_table
        FROM pg_constraint con
        JOIN pg_class cl ON cl.oid = con.conrelid
        JOIN pg_namespace n ON n.oid = cl.relnamespace
        JOIN pg_class ct ON ct.oid = con.confrelid
        CROSS JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS k(attnum, ord)
        JOIN pg_attribute a ON a.attrelid = cl.oid AND a.attnum = k.attnum
        WHERE con.contype = 'f'
          AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast', 'audit')
    """)
    for r in rows:
        col = r["column_name"]
        if not col.endswith("_id"):
            findings.append(
                _finding(
                    "info",
                    "naming",
                    f"{r['schema']}.{r['table_name']}.{col}",
                    f"FK column '{col}' → {r['referenced_table']} does not end with '_id'",
                )
            )

    # 5. varchar with explicit length > 255 (prefer text)
    rows = c.fetchall("""
        SELECT
            n.nspname AS schema,
            c.relname AS table_name,
            a.attname AS column_name,
            a.atttypmod - 4 AS max_length
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE a.atttypid = 'pg_catalog.varchar'::regtype
          AND a.atttypmod > 259  -- varchar(255) = 259
          AND a.attnum > 0
          AND NOT a.attisdropped
          AND c.relkind = 'r'
          AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast', 'audit')
    """)
    for r in rows:
        findings.append(
            _finding(
                "info",
                "column_type",
                f"{r['schema']}.{r['table_name']}.{r['column_name']}",
                f"varchar({r['max_length']}) — consider using text instead",
            )
        )

    # 6. Nullable columns that look like they should be NOT NULL (common patterns)
    rows = c.fetchall("""
        SELECT
            n.nspname AS schema,
            c.relname AS table_name,
            a.attname AS column_name
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE NOT a.attnotnull
          AND a.attnum > 0
          AND NOT a.attisdropped
          AND c.relkind = 'r'
          AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast', 'audit')
          AND a.attname IN ('created_at', 'updated_at', 'name', 'type', 'status', 'email')
    """)
    for r in rows:
        findings.append(
            _finding(
                "warning",
                "not_null",
                f"{r['schema']}.{r['table_name']}.{r['column_name']}",
                f"Column '{r['column_name']}' is nullable but typically should be NOT NULL",
            )
        )

    return findings


# ---------------------------------------------------------------------------
# lint indexes
# ---------------------------------------------------------------------------


@app.command()
def indexes(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
    min_scans: Annotated[int, typer.Option("--min-scans", help="Unused threshold")] = 50,
) -> None:
    """Detect unused, duplicate, bloated, and missing FK indexes."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    c = actx.get_client(database=db)
    try:
        findings = _check_indexes(c, min_scans)
    finally:
        c.close()

    _render_findings(out, f"Index Lint — {db}", findings)


def _check_indexes(c, min_scans: int) -> list[dict]:
    findings: list[dict] = []

    # 1. Unused indexes (< min_scans)
    rows = c.fetchall(
        """
        SELECT
            s.schemaname AS schema,
            s.relname AS table_name,
            s.indexrelname AS index_name,
            s.idx_scan AS scans,
            pg_size_pretty(pg_relation_size(s.indexrelid)) AS index_size,
            pg_relation_size(s.indexrelid) AS index_bytes
        FROM pg_stat_user_indexes s
        JOIN pg_index i ON i.indexrelid = s.indexrelid
        WHERE s.idx_scan < %s
          AND NOT i.indisprimary
          AND NOT i.indisunique
          AND pg_relation_size(s.indexrelid) > 8192
        ORDER BY pg_relation_size(s.indexrelid) DESC
    """,
        (min_scans,),
    )
    for r in rows:
        findings.append(
            _finding(
                "warning",
                "unused_index",
                f"{r['schema']}.{r['table_name']}.{r['index_name']}",
                f"Index '{r['index_name']}' has only {r['scans']} scans, size {r['index_size']}",
            )
        )

    # 2. Duplicate indexes (same columns on same table)
    rows = c.fetchall("""
        WITH index_cols AS (
            SELECT
                n.nspname AS schema_name,
                ct.relname AS table_name,
                ci.relname AS index_name,
                pg_relation_size(ci.oid) AS index_size,
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
            b.index_name AS index_b,
            a.column_list,
            pg_size_pretty(a.index_size) AS size_a,
            pg_size_pretty(b.index_size) AS size_b
        FROM index_cols a
        JOIN index_cols b ON a.table_name = b.table_name
            AND a.schema_name = b.schema_name
            AND a.index_name < b.index_name
            AND a.column_list = b.column_list
        ORDER BY a.table_name
    """)
    for r in rows:
        findings.append(
            _finding(
                "error",
                "duplicate_index",
                r["table_name"],
                f"Duplicate indexes: '{r['index_a']}' and '{r['index_b']}' on ({r['column_list']})",
            )
        )

    # 3. Missing indexes on FK columns
    rows = c.fetchall("""
        SELECT
            n.nspname AS schema,
            cl.relname AS table_name,
            a.attname AS column_name,
            ct.relname AS referenced_table
        FROM pg_constraint con
        JOIN pg_class cl ON cl.oid = con.conrelid
        JOIN pg_namespace n ON n.oid = cl.relnamespace
        JOIN pg_class ct ON ct.oid = con.confrelid
        CROSS JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS k(attnum, ord)
        JOIN pg_attribute a ON a.attrelid = cl.oid AND a.attnum = k.attnum
        WHERE con.contype = 'f'
          AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
          AND NOT EXISTS (
              SELECT 1 FROM pg_index i
              WHERE i.indrelid = cl.oid
                AND a.attnum = ANY(i.indkey)
          )
    """)
    for r in rows:
        findings.append(
            _finding(
                "warning",
                "missing_fk_index",
                f"{r['schema']}.{r['table_name']}.{r['column_name']}",
                f"FK column '{r['column_name']}' → {r['referenced_table']} has no index",
            )
        )

    # 4. Bloated indexes (> 50%)
    rows = c.fetchall("""
        SELECT
            s.schemaname AS schema,
            s.relname AS table_name,
            s.indexrelname AS index_name,
            pg_relation_size(s.indexrelid) AS actual_size,
            pg_stat_get_live_tuples(s.relid) AS table_rows,
            pg_size_pretty(pg_relation_size(s.indexrelid)) AS index_size
        FROM pg_stat_user_indexes s
        WHERE pg_relation_size(s.indexrelid) > 65536
          AND pg_stat_get_live_tuples(s.relid) > 0
    """)
    for r in rows:
        est_pct = max(0, round(100.0 * (1.0 - (r["table_rows"] * 8.0 / max(r["actual_size"], 1))), 1))
        if est_pct > 50:
            findings.append(
                _finding(
                    "warning",
                    "bloated_index",
                    f"{r['schema']}.{r['table_name']}.{r['index_name']}",
                    f"Index bloat ~{est_pct}%, size {r['index_size']} — consider REINDEX CONCURRENTLY",
                )
            )

    return findings


# ---------------------------------------------------------------------------
# lint permissions
# ---------------------------------------------------------------------------


@app.command()
def permissions(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
) -> None:
    """Find excessive privileges, public schema grants, superuser misuse, missing RLS."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    c = actx.get_client(database=db)
    try:
        findings = _check_permissions(c)
    finally:
        c.close()

    _render_findings(out, f"Permission Lint — {db}", findings)


def _check_permissions(c) -> list[dict]:
    findings: list[dict] = []

    # 1. Roles with excessive privileges (SUPERUSER + LOGIN)
    rows = c.fetchall("""
        SELECT rolname, rolcanlogin, rolcreatedb, rolcreaterole, rolbypassrls
        FROM pg_roles
        WHERE rolsuper = true AND rolcanlogin = true
          AND rolname NOT IN ('postgres')
        ORDER BY rolname
    """)
    for r in rows:
        findings.append(
            _finding(
                "error",
                "superuser",
                r["rolname"],
                f"Role '{r['rolname']}' is SUPERUSER with LOGIN — reduce to minimum required privileges",
            )
        )

    # 2. Roles that can bypass RLS
    rows = c.fetchall("""
        SELECT rolname
        FROM pg_roles
        WHERE rolbypassrls = true AND NOT rolsuper AND rolcanlogin = true
        ORDER BY rolname
    """)
    for r in rows:
        findings.append(
            _finding(
                "warning",
                "bypassrls",
                r["rolname"],
                f"Role '{r['rolname']}' has BYPASSRLS without being SUPERUSER",
            )
        )

    # 3. Public schema grants (CREATE on public schema)
    row = c.fetchone("""
        SELECT
            has_schema_privilege('public', 'public', 'CREATE') AS public_can_create,
            has_schema_privilege('public', 'public', 'USAGE') AS public_can_usage
    """)
    if row and row["public_can_create"]:
        findings.append(
            _finding(
                "warning",
                "public_schema",
                "public",
                "PUBLIC role has CREATE privilege on 'public' schema — revoke for production",
            )
        )

    # 4. Sensitive tables without RLS
    rows = c.fetchall("""
        SELECT
            n.nspname AS schema,
            c.relname AS table_name,
            c.relrowsecurity AS rls_enabled
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'r'
          AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast', 'audit')
          AND c.relrowsecurity = false
          AND (
              c.relname LIKE '%%user%%'
              OR c.relname LIKE '%%account%%'
              OR c.relname LIKE '%%token%%'
              OR c.relname LIKE '%%session%%'
              OR c.relname LIKE '%%credential%%'
              OR c.relname LIKE '%%password%%'
              OR c.relname LIKE '%%secret%%'
          )
    """)
    for r in rows:
        findings.append(
            _finding(
                "info",
                "missing_rls",
                f"{r['schema']}.{r['table_name']}",
                "Sensitive table has no RLS — consider enabling row-level security",
            )
        )

    # 5. Roles with CREATEDB that shouldn't
    rows = c.fetchall("""
        SELECT rolname
        FROM pg_roles
        WHERE rolcreatedb = true AND NOT rolsuper
          AND rolname NOT IN ('postgres')
        ORDER BY rolname
    """)
    for r in rows:
        findings.append(
            _finding(
                "info",
                "createdb",
                r["rolname"],
                f"Role '{r['rolname']}' has CREATEDB — verify this is intentional",
            )
        )

    return findings


# ---------------------------------------------------------------------------
# lint all
# ---------------------------------------------------------------------------


@app.command("all")
def all_checks(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Target database")] = None,
    strict: Annotated[bool, typer.Option("--strict", help="Exit code 1 if any errors or warnings")] = False,
    min_scans: Annotated[int, typer.Option("--min-scans", help="Unused index threshold")] = 50,
) -> None:
    """Run all lint checks. Exit code 0/1 for CI with --strict."""
    actx: AppContext = ctx.obj
    out = actx.output
    db = database or "postgres"

    c = actx.get_client(database=db)
    try:
        findings: list[dict] = []
        findings.extend(_check_schema(c))
        findings.extend(_check_indexes(c, min_scans))
        findings.extend(_check_permissions(c))
    finally:
        c.close()

    if actx.json_mode:
        summary = {
            "database": db,
            "total": len(findings),
            "errors": sum(1 for f in findings if f["severity"] == "error"),
            "warnings": sum(1 for f in findings if f["severity"] == "warning"),
            "info": sum(1 for f in findings if f["severity"] == "info"),
            "findings": findings,
        }
        out.raw_json(summary)
    else:
        _render_findings(out, f"Full Lint — {db}", findings)

    # Exit code for CI
    if strict:
        has_issues = any(f["severity"] in ("error", "warning") for f in findings)
        if has_issues:
            raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Shared rendering
# ---------------------------------------------------------------------------


def _render_findings(out, title: str, findings: list[dict]) -> None:
    if not findings:
        out.success(f"{title}: no issues found")
        return

    # Sort by severity (errors first)
    findings.sort(key=lambda f: -_SEVERITIES.get(f["severity"], 0))

    rows = [
        [
            _severity_style(f["severity"]),
            f["category"],
            f["object"],
            f["message"],
        ]
        for f in findings
    ]

    out.table(
        f"{title} ({len(findings)} findings)",
        [
            ("Severity", ""),
            ("Category", "yellow"),
            ("Object", "cyan"),
            ("Message", ""),
        ],
        rows,
        data_for_json=findings,
    )

    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    info = sum(1 for f in findings if f["severity"] == "info")
    out.text(f"  [red]{errors} errors[/red] | [yellow]{warnings} warnings[/yellow] | [blue]{info} info[/blue]")
