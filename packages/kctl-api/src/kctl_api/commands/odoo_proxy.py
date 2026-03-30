"""Odoo proxy commands for kctl-api.

Admin-only JSON-RPC proxy calls to Odoo backend.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.exceptions import APIError, AuthenticationError
from kctl_api.core.exceptions import ConnectionError as KctlConnectionError

app = typer.Typer(name="odoo", help="Odoo proxy — search-read, call, create, write (admin-only).", no_args_is_help=True)

_BASE = "/api/v1/odoo"


# ---------------------------------------------------------------------------
# search-read
# ---------------------------------------------------------------------------
@app.command(name="search-read")
def search_read(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Odoo model name (e.g. res.partner).")],
    domain: Annotated[str, typer.Option("--domain", "-d", help="JSON domain filter.")] = "[]",
    fields: Annotated[str, typer.Option("--fields", "-f", help="Comma-separated field names.")] = "",
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max records to return.")] = 20,
) -> None:
    """Search and read Odoo records via POST /api/v1/odoo/search-read (admin-only)."""
    actx: AppContext = ctx.obj
    out = actx.output

    import json

    try:
        domain_parsed = json.loads(domain)
    except json.JSONDecodeError as e:
        out.error(f"Invalid domain JSON: {e}")
        raise typer.Exit(1) from None

    payload: dict = {
        "model": model,
        "domain": domain_parsed,
        "limit": limit,
    }
    if fields:
        payload["fields"] = [f.strip() for f in fields.split(",")]

    try:
        result = actx.client.post(f"{_BASE}/search-read", json=payload)
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    records = result if isinstance(result, list) else result.get("records", []) if isinstance(result, dict) else []
    out.info(f"Found {len(records)} record(s).")

    if actx.json_mode:
        out.raw_json(records)
    elif records:
        # Auto-detect columns from first record
        cols = list(records[0].keys()) if records else []
        rows = [[str(r.get(c, "")) for c in cols] for r in records]
        out.table(
            title=f"{model} ({len(records)} records)",
            columns=[(c, "") for c in cols],
            rows=rows,
            data_for_json=records,
        )


# ---------------------------------------------------------------------------
# call
# ---------------------------------------------------------------------------
@app.command()
def call(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Odoo model name.")],
    method: Annotated[str, typer.Argument(help="Method to call.")],
    args_json: Annotated[str, typer.Option("--args", "-a", help="JSON args array.")] = "[]",
    kwargs_json: Annotated[str, typer.Option("--kwargs", "-k", help="JSON kwargs object.")] = "{}",
) -> None:
    """Call an Odoo model method via POST /api/v1/odoo/call (admin-only)."""
    actx: AppContext = ctx.obj
    out = actx.output

    import json

    try:
        args = json.loads(args_json)
        kwargs = json.loads(kwargs_json)
    except json.JSONDecodeError as e:
        out.error(f"Invalid JSON: {e}")
        raise typer.Exit(1) from None

    payload: dict = {"model": model, "method": method, "args": args, "kwargs": kwargs}

    try:
        result = actx.client.post(f"{_BASE}/call", json=payload)
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"Called {model}.{method}")
    if actx.json_mode:
        out.raw_json(result)
    elif result:
        out.text(str(result))


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------
@app.command()
def create(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Odoo model name.")],
    values_json: Annotated[str, typer.Argument(help="JSON object with field values.")],
) -> None:
    """Create an Odoo record via POST /api/v1/odoo/create (admin-only)."""
    actx: AppContext = ctx.obj
    out = actx.output

    import json

    try:
        values = json.loads(values_json)
    except json.JSONDecodeError as e:
        out.error(f"Invalid JSON: {e}")
        raise typer.Exit(1) from None

    payload: dict = {"model": model, "values": values}

    try:
        result = actx.client.post(f"{_BASE}/create", json=payload)
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"Created {model} record.")
    if actx.json_mode:
        out.raw_json(result)
    elif result:
        out.text(str(result))


# ---------------------------------------------------------------------------
# write
# ---------------------------------------------------------------------------
@app.command()
def write(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Odoo model name.")],
    record_id: Annotated[int, typer.Argument(help="Record ID to update.")],
    values_json: Annotated[str, typer.Argument(help="JSON object with field values.")],
) -> None:
    """Update an Odoo record via POST /api/v1/odoo/write (admin-only)."""
    actx: AppContext = ctx.obj
    out = actx.output

    import json

    try:
        values = json.loads(values_json)
    except json.JSONDecodeError as e:
        out.error(f"Invalid JSON: {e}")
        raise typer.Exit(1) from None

    payload: dict = {"model": model, "ids": [record_id], "values": values}

    try:
        result = actx.client.post(f"{_BASE}/write", json=payload)
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"Updated {model} record {record_id}.")
    if actx.json_mode:
        out.raw_json(result)
