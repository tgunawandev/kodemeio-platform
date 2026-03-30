"""Databases command group -- database management and querying."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Annotated, Any

import typer

from kctl_notion.core.callbacks import AppContext

app = typer.Typer(help="Database management.")


def _extract_db_title(db: dict[str, Any]) -> str:
    """Extract database title."""
    title_parts = db.get("title", [])
    if isinstance(title_parts, list) and title_parts:
        return "".join(t.get("plain_text", "") for t in title_parts)
    return "(untitled)"


def _extract_row_values(row: dict[str, Any], prop_names: list[str]) -> list[str]:
    """Extract property values from a database row for tabular display."""
    values: list[str] = []
    props = row.get("properties", {})
    for name in prop_names:
        prop = props.get(name, {})
        values.append(_format_property_value(prop))
    return values


def _format_property_value(prop: dict[str, Any]) -> str:
    """Format a single Notion property value to a string."""
    prop_type = prop.get("type", "")

    if prop_type == "title":
        parts = prop.get("title", [])
        return "".join(t.get("plain_text", "") for t in parts) if parts else ""

    if prop_type == "rich_text":
        parts = prop.get("rich_text", [])
        return "".join(t.get("plain_text", "") for t in parts) if parts else ""

    if prop_type == "number":
        val = prop.get("number")
        return str(val) if val is not None else ""

    if prop_type == "select":
        sel = prop.get("select")
        return sel.get("name", "") if sel else ""

    if prop_type == "multi_select":
        items = prop.get("multi_select", [])
        return ", ".join(s.get("name", "") for s in items)

    if prop_type == "date":
        date_obj = prop.get("date")
        if date_obj:
            start = date_obj.get("start", "")
            end = date_obj.get("end")
            return f"{start} - {end}" if end else start
        return ""

    if prop_type == "checkbox":
        return str(prop.get("checkbox", False))

    if prop_type == "url":
        return prop.get("url", "") or ""

    if prop_type == "email":
        return prop.get("email", "") or ""

    if prop_type == "phone_number":
        return prop.get("phone_number", "") or ""

    if prop_type == "status":
        status = prop.get("status")
        return status.get("name", "") if status else ""

    if prop_type == "people":
        people = prop.get("people", [])
        return ", ".join(p.get("name", p.get("id", "")) for p in people)

    if prop_type == "relation":
        relations = prop.get("relation", [])
        return ", ".join(r.get("id", "")[:8] for r in relations)

    if prop_type == "formula":
        formula = prop.get("formula", {})
        f_type = formula.get("type", "")
        return str(formula.get(f_type, ""))

    return f"({prop_type})"


@app.command("list")
def list_(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 20,
) -> None:
    """List all databases accessible to the integration."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        result = client.search(filter_type="database", page_size=limit)
        databases = result.get("results", [])

        if out.json_mode:
            out.raw_json({"databases": databases, "count": len(databases)})
            return

        if not databases:
            out.warn("No databases found")
            return

        rows: list[list[str]] = []
        for db in databases:
            db_id = db.get("id", "")[:8]
            title = _extract_db_title(db)
            prop_count = len(db.get("properties", {}))
            last_edited = db.get("last_edited_time", "")[:10]
            rows.append([db_id, title[:50], str(prop_count), last_edited])

        out.table(
            f"Databases ({len(databases)})",
            [("ID", "cyan"), ("Title", "white"), ("Props", "green"), ("Edited", "yellow")],
            rows,
        )
    finally:
        actx.close()


@app.command()
def show(
    ctx: typer.Context,
    database_id: Annotated[str, typer.Argument(help="Database ID")],
) -> None:
    """Show database schema (properties and their types)."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        db = client.get_database(database_id)

        if out.json_mode:
            out.raw_json(db)
            return

        title = _extract_db_title(db)
        created = db.get("created_time", "")[:10]
        edited = db.get("last_edited_time", "")[:10]
        url = db.get("url", "")

        sections: list[tuple[str, list[tuple[str, str]]]] = [
            (
                "Database Info",
                [
                    ("ID", db.get("id", "")),
                    ("Title", title),
                    ("Created", created),
                    ("Last edited", edited),
                    ("URL", url),
                ],
            ),
        ]

        # Show schema (properties)
        props = db.get("properties", {})
        if props:
            schema_fields: list[tuple[str, str]] = []
            for name, prop_def in props.items():
                prop_type = prop_def.get("type", "unknown")
                schema_fields.append((name, prop_type))
            sections.append(("Schema", schema_fields))

        out.detail(f"Database: {title}", sections)
    finally:
        actx.close()


@app.command()
def query(
    ctx: typer.Context,
    database_id: Annotated[str, typer.Argument(help="Database ID")],
    filter: Annotated[str | None, typer.Option("--filter", help="Filter JSON object")] = None,
    sort: Annotated[str | None, typer.Option("--sort", help="Sort by property name")] = None,
    descending: Annotated[bool, typer.Option("--desc", help="Sort descending")] = False,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 50,
) -> None:
    """Query database rows with optional filter and sort."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        filter_obj = json.loads(filter) if filter else None
        sorts: list[dict[str, Any]] | None = None
        if sort:
            sorts = [{"property": sort, "direction": "descending" if descending else "ascending"}]

        result = client.query_database(database_id, filter_obj=filter_obj, sorts=sorts, page_size=limit)
        rows_data = result.get("results", [])

        if out.json_mode:
            out.raw_json(
                {
                    "results": rows_data,
                    "count": len(rows_data),
                    "has_more": result.get("has_more", False),
                }
            )
            return

        if not rows_data:
            out.warn("No rows found")
            return

        # Discover property names from first row
        first_props = rows_data[0].get("properties", {})
        prop_names = list(first_props.keys())[:6]  # Limit columns for readability

        rows: list[list[str]] = []
        for row in rows_data:
            row_id = row.get("id", "")[:8]
            row_values = _extract_row_values(row, prop_names)
            rows.append([row_id, *[v[:30] for v in row_values]])

        columns: list[tuple[str, str]] = [("ID", "cyan")]
        for name in prop_names:
            columns.append((name[:20], "white"))

        out.table(f"Query results ({len(rows_data)} rows)", columns, rows)
    finally:
        actx.close()


@app.command()
def export(
    ctx: typer.Context,
    database_id: Annotated[str, typer.Argument(help="Database ID")],
    format: Annotated[str, typer.Option("--format", "-f", help="Export format: csv or json")] = "csv",
    output: Annotated[str | None, typer.Option("--output", "-o", help="Output file path")] = None,
) -> None:
    """Export database to CSV or JSON file."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        # Fetch all rows
        all_rows = client.query_database_all(database_id)

        if not all_rows:
            out.warn("Database is empty, nothing to export")
            return

        # Get property names from schema
        db = client.get_database(database_id)
        db_title = _extract_db_title(db)
        prop_names = list(db.get("properties", {}).keys())

        if format == "json":
            export_data = []
            for row in all_rows:
                row_dict: dict[str, str] = {"id": row.get("id", "")}
                for name in prop_names:
                    prop = row.get("properties", {}).get(name, {})
                    row_dict[name] = _format_property_value(prop)
                export_data.append(row_dict)

            content = json.dumps(export_data, indent=2, ensure_ascii=False)
            default_ext = ".json"
        else:
            # CSV
            string_io = io.StringIO()
            writer = csv.writer(string_io)
            writer.writerow(["id", *prop_names])
            for row in all_rows:
                values = _extract_row_values(row, prop_names)
                writer.writerow([row.get("id", ""), *values])
            content = string_io.getvalue()
            default_ext = ".csv"

        if output:
            filepath = Path(output)
        else:
            safe_title = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in db_title)
            filepath = Path(f"{safe_title}{default_ext}")

        filepath.write_text(content, encoding="utf-8")
        out.success(f"Exported {len(all_rows)} rows to {filepath}")
    finally:
        actx.close()
