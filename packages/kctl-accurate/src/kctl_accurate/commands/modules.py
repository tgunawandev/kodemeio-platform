"""Module command factory — builds Typer sub-apps from MODULE_REGISTRY entries.

Each :class:`~kctl_accurate.core.columns.ModuleSpec` produces a Typer group with
three subcommands: ``list``, ``get``, and ``count``.  All 23 module groups are
registered in ``cli.py`` by iterating over ``MODULE_REGISTRY``.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Annotated, Any

import typer

from kctl_accurate.core.callbacks import AppContext
from kctl_accurate.core.columns import ModuleSpec


def build_module_app(spec: ModuleSpec) -> typer.Typer:
    """Return a Typer sub-app with ``list``, ``get``, and ``count`` commands.

    The returned app is bound to *spec* at definition time via closure, so
    every registry entry gets its own independent command tree.
    """
    app = typer.Typer(
        name=spec.cli_name,
        help=f"Accurate {spec.cli_name} operations.",
        no_args_is_help=True,
    )

    # ── list ───────────────────────────────────────────────────────────────

    @app.command("list")
    def list_cmd(
        ctx: typer.Context,
        since: Annotated[
            str | None,
            typer.Option("--since", help="ISO date (YYYY-MM-DD) — only records modified on/after this date."),
        ] = None,
        days: Annotated[
            int | None,
            typer.Option("--days", "-d", help="Shorthand: only records modified in the last N days."),
        ] = None,
        limit: Annotated[
            int | None,
            typer.Option("--limit", "-n", help="Cap the number of rows returned (no limit by default)."),
        ] = None,
    ) -> None:
        f"""List {spec.cli_name}. Use --since or --days for incremental filtering."""
        actx: AppContext = ctx.obj
        raw_client = actx.client.raw

        # Resolve modified_since
        modified_since: date | None = None
        if days is not None:
            modified_since = date.today() - timedelta(days=days)
        elif since is not None:
            try:
                modified_since = date.fromisoformat(since)
            except ValueError:
                typer.echo(f"ERROR: --since must be YYYY-MM-DD, got: {since!r}", err=True)
                raise typer.Exit(1)

        accessor = getattr(raw_client, spec.sdk_accessor)
        rows: list[dict[str, Any]] = accessor.list_raw(modified_since=modified_since)

        if limit is not None:
            rows = rows[:limit]

        if actx.json_mode:
            print(json.dumps(rows, indent=2, ensure_ascii=False, default=str))
            return

        # Pretty table — curated columns only
        columns = [(col, "") for col in spec.columns]
        table_rows = [[str(row.get(col, "")) for col in spec.columns] for row in rows]
        actx.output.table(
            title=f"{spec.cli_name} ({len(rows)} rows)",
            columns=columns,
            rows=table_rows,
            data_for_json=rows,
        )

    # ── get ────────────────────────────────────────────────────────────────

    @app.command("get")
    def get_cmd(
        ctx: typer.Context,
        record_id: Annotated[int, typer.Argument(help="Accurate record ID.")],
        full: Annotated[bool, typer.Option("--full", help="Show all fields (not just curated columns).")] = False,
    ) -> None:
        f"""Fetch a single {spec.cli_name} record by ID."""
        actx: AppContext = ctx.obj
        raw_client = actx.client.raw

        accessor = getattr(raw_client, spec.sdk_accessor)
        record: dict[str, Any] = accessor.get_raw(record_id)

        if actx.json_mode:
            print(json.dumps(record, indent=2, ensure_ascii=False, default=str))
            return

        if full:
            # Show every field as a flat kv list
            kvs = [(k, str(v)) for k, v in record.items()]
        else:
            kvs = [(col, str(record.get(col, ""))) for col in spec.columns]

        actx.output.detail(
            title=f"{spec.cli_name} #{record_id}",
            sections=[("Fields", kvs)],
            data_for_json=record,
        )

    # ── count ──────────────────────────────────────────────────────────────

    @app.command("count")
    def count_cmd(
        ctx: typer.Context,
        since: Annotated[
            str | None,
            typer.Option("--since", help="ISO date (YYYY-MM-DD) — only records modified on/after this date."),
        ] = None,
        days: Annotated[
            int | None,
            typer.Option("--days", "-d", help="Shorthand: only records modified in the last N days."),
        ] = None,
    ) -> None:
        f"""Count {spec.cli_name} records without fetching all pages."""
        actx: AppContext = ctx.obj
        raw_client = actx.client.raw

        # Resolve modified_since params
        extra_params: dict[str, Any] = {}
        if days is not None:
            modified_since = date.today() - timedelta(days=days)
            extra_params["filter.lastUpdated.op"] = "GREATER_EQUAL"
            extra_params["filter.lastUpdated.val[0]"] = modified_since.strftime("%d/%m/%Y")
        elif since is not None:
            try:
                modified_since_date = date.fromisoformat(since)
                extra_params["filter.lastUpdated.op"] = "GREATER_EQUAL"
                extra_params["filter.lastUpdated.val[0]"] = modified_since_date.strftime("%d/%m/%Y")
            except ValueError:
                typer.echo(f"ERROR: --since must be YYYY-MM-DD, got: {since!r}", err=True)
                raise typer.Exit(1)

        # Hit list.do with pageSize=1 to read sp.rowCount cheaply
        accessor = getattr(raw_client, spec.sdk_accessor)
        path = f"{accessor._module_path}/list.do"
        params: dict[str, Any] = {"sp.pageSize": 1, "sp.page": 1}
        params.update(extra_params)

        response = raw_client.get(path, params=params)
        sp = response.get("sp") or {}
        row_count: int = sp.get("rowCount", 0)

        if actx.json_mode:
            print(json.dumps({"module": spec.cli_name, "count": row_count}, indent=2))
            return

        actx.output.success(f"{spec.cli_name}: {row_count:,} records")

    return app
