"""SQL/script query execution commands.

Wraps DBGate's /database-connections/sql-* and eval-json-script endpoints.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer
from kctl_lib.exceptions import KctlError

from kctl_dbgate.core.callbacks import AppContext

app = typer.Typer(help="Run SQL / eval scripts against DBGate connections.")


def _parse_vars(variables: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for pair in variables or []:
        if "=" not in pair:
            raise typer.BadParameter(f"--var must be k=v, got: {pair}")
        k, v = pair.split("=", 1)
        out[k.strip()] = v
    return out


def _substitute(text: str, variables: dict[str, str]) -> str:
    for k, v in variables.items():
        text = text.replace(f"{{{{{k}}}}}", v)
    return text


def _resolve_sql(sql: str | None, file: Path | None, variables: dict[str, str]) -> str:
    if not sql and not file:
        raise typer.BadParameter("Provide --sql or --file")
    if sql and file:
        raise typer.BadParameter("Provide only one of --sql / --file")
    text = sql if sql is not None else file.read_text()  # type: ignore[union-attr]
    return _substitute(text, variables)


def _emit_rows(out: Any, rows: list[dict[str, Any]], columns: list[dict[str, Any]] | None) -> None:
    col_names: list[str]
    if columns:
        col_names = [c.get("columnName") or c.get("name") or "" for c in columns if isinstance(c, dict)]
    elif rows:
        col_names = list(rows[0].keys())
    else:
        col_names = []

    table_rows: list[list[str]] = [[str(row.get(c, "")) for c in col_names] for row in rows]
    cols_decl = [(c, "") for c in col_names] or [("(no columns)", "")]
    out.table(
        title=f"{len(rows)} row(s)",
        columns=cols_decl,
        rows=table_rows,
        data_for_json=rows,
    )


@app.command()
def run(
    ctx: typer.Context,
    connection: Annotated[str, typer.Option("--connection", help="Connection ID")],
    database: Annotated[str, typer.Option("--database", help="Database name")],
    sql: Annotated[str | None, typer.Option("--sql", help="SQL to run")] = None,
    file: Annotated[Path | None, typer.Option("--file", help="Path to SQL file")] = None,
    variables: Annotated[
        list[str] | None, typer.Option("--var", help="Variable substitution: k=v (repeatable)")
    ] = None,
) -> None:
    """Run SQL and print the result rows."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        query_text = _resolve_sql(sql, file, _parse_vars(variables))
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e
    except OSError as e:
        out.error(f"Cannot read SQL file: {e}")
        raise typer.Exit(1) from e

    payload = {"conid": connection, "database": database, "sql": query_text}
    try:
        result = actx.client.call("/database-connections/sql-select", payload)
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    rows = (result or {}).get("rows") or []
    columns = (result or {}).get("columns") or []
    _emit_rows(out, rows, columns)


@app.command()
def select(
    ctx: typer.Context,
    connection: Annotated[str, typer.Option("--connection", help="Connection ID")],
    database: Annotated[str, typer.Option("--database", help="Database name")],
    table: Annotated[str, typer.Option("--table", help="Table name")],
    limit: Annotated[int, typer.Option("--limit", help="Row limit")] = 100,
    where: Annotated[str | None, typer.Option("--where", help="WHERE clause body")] = None,
) -> None:
    """Convenience wrapper: SELECT * FROM <table> [WHERE ...] LIMIT N."""
    actx: AppContext = ctx.obj
    out = actx.output

    sql = f'SELECT * FROM "{table}"'
    if where:
        sql += f" WHERE {where}"
    sql += f" LIMIT {limit}"

    payload = {"conid": connection, "database": database, "sql": sql}
    try:
        result = actx.client.call("/database-connections/sql-select", payload)
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    rows = (result or {}).get("rows") or []
    columns = (result or {}).get("columns") or []
    _emit_rows(out, rows, columns)


@app.command()
def preview(
    ctx: typer.Context,
    connection: Annotated[str, typer.Option("--connection", help="Connection ID")],
    database: Annotated[str, typer.Option("--database", help="Database name")],
    sql: Annotated[str | None, typer.Option("--sql", help="SQL to preview")] = None,
    file: Annotated[Path | None, typer.Option("--file", help="Path to SQL file")] = None,
    variables: Annotated[list[str] | None, typer.Option("--var", help="Variable substitution: k=v")] = None,
) -> None:
    """Preview the planned SQL without executing it."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        query_text = _resolve_sql(sql, file, _parse_vars(variables))
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e
    except OSError as e:
        out.error(f"Cannot read SQL file: {e}")
        raise typer.Exit(1) from e

    payload = {"conid": connection, "database": database, "sql": query_text}
    try:
        result = actx.client.call("/database-connections/sql-preview", payload)
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    planned = (result or {}).get("sql") or query_text
    err = (result or {}).get("errorMessage")
    if err:
        out.error(f"Preview error: {err}")
        raise typer.Exit(1)

    out.header("Planned SQL")
    out.text(planned)


@app.command("eval")
def eval_(
    ctx: typer.Context,
    connection: Annotated[str, typer.Option("--connection", help="Connection ID")],
    database: Annotated[str, typer.Option("--database", help="Database name")],
    script: Annotated[Path, typer.Option("--script", help="Path to JS/JSON script file")],
) -> None:
    """Evaluate a JSON/JS script (for MongoDB/NoSQL engines)."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not script.exists():
        out.error(f"Script file not found: {script}")
        raise typer.Exit(1)

    try:
        content = script.read_text()
    except OSError as e:
        out.error(f"Cannot read script: {e}")
        raise typer.Exit(1) from e

    payload = {"conid": connection, "database": database, "script": content}
    try:
        result = actx.client.call("/database-connections/eval-json-script", payload)
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    rows = (result or {}).get("rows") or []
    columns = (result or {}).get("columns") or []
    _emit_rows(out, rows, columns)
