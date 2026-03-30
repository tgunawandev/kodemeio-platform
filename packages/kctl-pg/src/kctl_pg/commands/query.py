"""Ad-hoc SQL query execution."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_pg.core.callbacks import AppContext

app = typer.Typer(help="Execute SQL queries.")


@app.callback(invoke_without_command=True)
def query(
    ctx: typer.Context,
    sql: Annotated[str, typer.Argument(help="SQL query to execute")],
    database: Annotated[str, typer.Option("--db", "-d", help="Target database")] = "postgres",
) -> None:
    """Execute an ad-hoc SQL query and display results.

    Examples:
      kctl-pg query "SELECT version()"
      kctl-pg query "SELECT * FROM pg_stat_activity" --db odoo
      kctl-pg query "SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database"
    """
    actx: AppContext = ctx.obj
    out = actx.output

    c = actx.get_client(database=database)
    try:
        rows = c.fetchall(sql)
    finally:
        c.close()

    if not rows:
        out.info("Query returned no rows")
        if out.json_mode:
            out.raw_json([])
        return

    # Build columns from first row's keys
    columns: list[tuple[str, str]] = [(k, "") for k in rows[0].keys()]
    table_rows = [[str(v) for v in row.values()] for row in rows]

    out.table(
        f"Query Result ({len(rows)} rows)",
        columns,
        table_rows,
        data_for_json=rows,
    )
