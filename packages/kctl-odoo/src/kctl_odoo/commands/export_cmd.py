"""Export command — export model data to CSV or JSON."""

from __future__ import annotations

import csv
import io
import json
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext

app = typer.Typer(help="Export model data.")


@app.command()
def records(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Model name (e.g. res.partner)")],
    domain: Annotated[str | None, typer.Option("--domain", "-d", help="JSON-encoded domain filter")] = None,
    fields: Annotated[str | None, typer.Option("--fields", "-f", help="Comma-separated field names")] = None,
    fmt: Annotated[str, typer.Option("--format", help="Output format: json or csv")] = "json",
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max records")] = 0,
    output: Annotated[str | None, typer.Option("--output", "-o", help="Output file path")] = None,
    with_id: Annotated[
        bool, typer.Option("--with-id", help="Include external ID column (for idempotent re-import)")
    ] = False,
) -> None:
    """Export records from a model.

    Use --with-id to include the external ID column, making the export
    suitable for idempotent re-import via 'kctl-odoo import records'.

    Examples:
      kctl-odoo export records res.partner --fields name,email --limit 100
      kctl-odoo export records res.partner -d '[["is_company","=",true]]' -f name,phone --format csv -o partners.csv
      kctl-odoo export records res.partner --with-id --format csv -o partners_with_ids.csv
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    parsed_domain: list = []
    if domain:
        try:
            parsed_domain = json.loads(domain)
        except json.JSONDecodeError as e:
            out.error(f"Invalid domain JSON: {e}")
            raise typer.Exit(1) from e

    field_list: list[str] | None = None
    if fields:
        field_list = [f.strip() for f in fields.split(",")]

    export_records = c.search_read(
        model,
        domain=parsed_domain,
        fields=field_list,
        limit=limit,
        order="id",
    )

    if not export_records:
        out.warn("No records found")
        return

    # Add external ID column if requested
    if with_id:
        record_ids = [r["id"] for r in export_records]
        id_map = _get_external_ids(c, model, record_ids)
        for r in export_records:
            r["id"] = id_map.get(r["id"], f"__export__.{model.replace('.', '_')}_{r['id']}")

    if fmt == "csv":
        content = _to_csv(export_records, id_first=with_id)
    else:
        content = json.dumps(export_records, indent=2, default=str)

    if output:
        with open(output, "w") as f:
            f.write(content)
        out.success(f"Exported {len(export_records)} records to {output}")
    else:
        print(content)


def _get_external_ids(c, model: str, record_ids: list[int]) -> dict[int, str]:
    """Fetch external IDs (XML IDs) for records via ir.model.data."""
    if not record_ids:
        return {}
    imd_records = c.search_read(
        "ir.model.data",
        domain=[("model", "=", model), ("res_id", "in", record_ids)],
        fields=["res_id", "module", "name"],
    )
    result: dict[int, str] = {}
    for imd in imd_records:
        res_id = imd["res_id"]
        # Prefer non-__export__ IDs
        xml_id = f"{imd['module']}.{imd['name']}"
        if res_id not in result or result[res_id].startswith("__export__"):
            result[res_id] = xml_id
    return result


def _to_csv(records: list[dict], id_first: bool = False) -> str:
    """Convert records to CSV string."""
    if not records:
        return ""
    buf = io.StringIO()
    fieldnames = list(records[0].keys())
    # Move 'id' column to first position if present
    if id_first and "id" in fieldnames:
        fieldnames.remove("id")
        fieldnames.insert(0, "id")
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for r in records:
        flat = {}
        for k, v in r.items():
            if isinstance(v, (list, tuple)):
                # Many2one: [id, name] → just the external ID or name
                if len(v) == 2 and isinstance(v[0], int):
                    flat[k] = v[1]  # Display name
                else:
                    flat[k] = str(v)
            elif v is False:
                flat[k] = ""
            else:
                flat[k] = v
        writer.writerow(flat)
    return buf.getvalue()
