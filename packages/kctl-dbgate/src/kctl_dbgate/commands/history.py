"""Query history commands.

Wraps /query-history/read and /query-history/write.
"""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib.exceptions import KctlError

from kctl_dbgate.core.callbacks import AppContext

app = typer.Typer(help="Browse and append to DBGate query history.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List query history entries."""
    actx: AppContext = ctx.obj
    out = actx.output
    try:
        items = actx.client.call("/query-history/read")
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    if not isinstance(items, list):
        items = []

    rows: list[list[str]] = []
    for entry in items:
        if not isinstance(entry, dict):
            continue
        sql = str(entry.get("sql", ""))[:80]
        rows.append(
            [
                str(entry.get("date", "") or entry.get("timestamp", ""))[:19],
                str(entry.get("conid", "")),
                str(entry.get("database", "")),
                sql,
            ]
        )
    out.table(
        title=f"{len(rows)} history entries",
        columns=[("Date", "dim"), ("Connection", "cyan"), ("Database", "blue"), ("SQL", "")],
        rows=rows,
        data_for_json=items,
    )


@app.command()
def add(
    ctx: typer.Context,
    connection: Annotated[str, typer.Option("--connection", help="Connection ID")],
    sql: Annotated[str, typer.Option("--sql", help="SQL to record")],
    database: Annotated[str | None, typer.Option("--database", help="Database name")] = None,
) -> None:
    """Append an entry to the query history.

    DBGate's /query-history/write expects the entry wrapped as {data: {...}}
    and appends JSON.stringify(data)+"\\n" to its history JSONL file. If the
    entry is NOT nested the server stringifies `undefined`, which corrupts
    the file and later breaks /query-history/read with "'undefined' is not
    valid JSON".
    """
    actx: AppContext = ctx.obj
    out = actx.output

    entry: dict[str, str] = {"conid": connection, "sql": sql}
    if database:
        entry["database"] = database

    try:
        actx.client.call("/query-history/write", {"data": entry})
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e
    out.success("History entry added")
