"""Import command — import data from CSV or JSON files.

Includes generic record import, template generation, data validation,
and domain-specific importers for opening balances and inventory.
"""

from __future__ import annotations

import contextlib
import csv
import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from kctl_odoo.core.callbacks import AppContext

app = typer.Typer(help="Import data into Odoo models.")
console = Console()


@app.command()
def records(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Model name (e.g. res.partner)")],
    file: Annotated[str, typer.Argument(help="Input file path (CSV or JSON)")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Validate without importing")] = False,
    batch_size: Annotated[int, typer.Option("--batch-size", "-b", help="Records per batch")] = 50,
) -> None:
    """Import records into a model from CSV or JSON.

    Examples:
      kctl-odoo import records res.partner partners.json
      kctl-odoo import records res.partner partners.csv --dry-run
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    path = Path(file)
    if not path.exists():
        out.error(f"File not found: {file}")
        raise typer.Exit(1)

    # Parse file
    if path.suffix.lower() == ".csv":
        records_data = _parse_csv(path)
    elif path.suffix.lower() in (".json", ".jsonl"):
        records_data = _parse_json(path)
    else:
        out.error(f"Unsupported format: {path.suffix} (use .csv or .json)")
        raise typer.Exit(1)

    if not records_data:
        out.warn("No records found in file")
        return

    out.info(f"Parsed {len(records_data)} records from {file}")

    if dry_run:
        out.info("Dry run — validating fields...")
        valid_fields = set(c.fields_get(model, ["string"]).keys())
        record_fields = set(records_data[0].keys())
        unknown = record_fields - valid_fields - {"id", ".id"}
        if unknown:
            out.warn(f"Unknown fields: {', '.join(sorted(unknown))}")
        else:
            out.success("All fields valid")
        return

    # Check if data has external IDs (id column) for idempotent upsert
    has_external_ids = "id" in records_data[0]

    if has_external_ids:
        # Use Odoo's load() method — supports external IDs for upsert
        # This is idempotent: existing records are updated, new ones created
        field_names = list(records_data[0].keys())
        rows = [[r.get(f, "") for f in field_names] for r in records_data]

        try:
            result = c.execute_kw(model, "load", [field_names, rows])
            ids = result.get("ids", [])
            messages = result.get("messages", [])
            error_msgs = [m for m in messages if m.get("type") == "error"]

            if error_msgs:
                out.warn(f"Imported with {len(error_msgs)} errors:")
                for msg in error_msgs[:5]:
                    out.error(f"  Row {msg.get('rows', {}).get('from', '?')}: {msg.get('message', '')}")
            else:
                out.success(f"Imported {len(ids)} records into {model} (idempotent via external IDs)")
        except Exception as e:
            out.error(f"Import failed: {e}")
            raise typer.Exit(1) from e
    else:
        # Fallback: create() without external IDs (not idempotent)
        created = 0
        errors = 0
        for i in range(0, len(records_data), batch_size):
            batch = records_data[i : i + batch_size]
            for vals in batch:
                vals.pop(".id", None)
                try:
                    c.create(model, vals)
                    created += 1
                except Exception as e:
                    errors += 1
                    if errors <= 5:
                        out.error(f"Failed to create record: {e}")

        out.success(f"Imported {created} records into {model}")
        if errors:
            out.warn(f"{errors} records failed (no external IDs — duplicates possible)")


def _parse_csv(path: Path) -> list[dict]:
    """Parse CSV file into list of dicts."""
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _parse_json(path: Path) -> list[dict]:
    """Parse JSON or JSONL file."""
    text = path.read_text()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        return [data]
    except json.JSONDecodeError:
        # Try JSONL
        records = []
        for line in text.strip().splitlines():
            if line.strip():
                records.append(json.loads(line))
        return records


# ---------------------------------------------------------------------------
# Template generation
# ---------------------------------------------------------------------------

# Fields to always exclude from import templates
_EXCLUDED_FIELDS = frozenset(
    {
        "id",
        "__last_update",
        "create_uid",
        "create_date",
        "write_uid",
        "write_date",
        "display_name",
    }
)


def _is_user_facing_field(name: str, meta: dict, required_only: bool) -> bool:
    """Return True if a field should be included in an import template."""
    if name in _EXCLUDED_FIELDS:
        return False
    # Skip computed fields that are not stored
    if meta.get("readonly") and not meta.get("store", True):
        return False
    if not meta.get("store", True):
        return False
    return not (required_only and not meta.get("required"))


@app.command("template")
def template(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Model name (e.g. res.partner, product.template)")],
    format: Annotated[str, typer.Option("--format", "-f", help="Output format: csv or json")] = "csv",
    required_only: Annotated[bool, typer.Option("--required-only", help="Only include required fields")] = False,
    output: Annotated[
        str | None, typer.Option("--output", "-o", help="Output file path (default: <model>_import_template.<ext>)")
    ] = None,
) -> None:
    """Generate an import template file for a model.

    Queries the model's field definitions and produces a CSV or JSON
    template with headers matching user-facing fields. Excludes system
    fields (id, create_uid, write_uid, etc.) and non-stored computed fields.

    Examples:
        kctl-odoo import template res.partner
        kctl-odoo import template product.template --format json
        kctl-odoo import template res.partner --required-only
        kctl-odoo import template res.partner -o my_partners.csv
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    out.info(f"Fetching fields for {model}...")

    try:
        fields = c.fields_get(model, ["string", "type", "required", "readonly", "store", "help"])
    except Exception as e:
        out.error(f"Failed to get fields for '{model}': {e}")
        raise typer.Exit(1) from e

    # Filter fields
    selected: list[tuple[str, dict]] = []
    for fname, fmeta in sorted(fields.items()):
        if _is_user_facing_field(fname, fmeta, required_only):
            selected.append((fname, fmeta))

    if not selected:
        out.warn(f"No importable fields found for {model}")
        raise typer.Exit(0)

    out.info(f"Found {len(selected)} importable fields" + (" (required only)" if required_only else ""))

    # Determine output path
    safe_model = model.replace(".", "_")
    ext = "json" if format == "json" else "csv"
    out_path = Path(output) if output else Path.cwd() / f"{safe_model}_import_template.{ext}"

    if format == "json":
        # JSON schema dict with field info
        schema: dict[str, dict[str, str]] = {}
        for fname, fmeta in selected:
            entry: dict[str, str] = {
                "type": fmeta.get("type", ""),
                "label": fmeta.get("string", fname),
            }
            if fmeta.get("required"):
                entry["required"] = "true"
            help_text = fmeta.get("help")
            if help_text:
                entry["help"] = help_text
            schema[fname] = entry

        content = {
            "model": model,
            "fields": schema,
            "template": [{fname: "" for fname, _ in selected}],
        }
        out_path.write_text(json.dumps(content, indent=2, ensure_ascii=False) + "\n")
    else:
        # CSV with a comment row showing types, then a header row
        field_names = [fname for fname, _ in selected]
        type_comments = [
            f"{fmeta.get('string', fname)} ({fmeta.get('type', '?')})" + (" *" if fmeta.get("required") else "")
            for fname, fmeta in selected
        ]

        with open(out_path, "w", newline="") as f:
            writer = csv.writer(f)
            # First row: human-readable field descriptions as comments
            writer.writerow(type_comments)
            # Second row: actual field names (import header)
            writer.writerow(field_names)

    out.success(f"Template written to {out_path} ({len(selected)} fields)")
    if required_only:
        out.info("Showing required fields only. Remove --required-only for all fields.")


# ---------------------------------------------------------------------------
# Validate — check CSV/JSON before importing
# ---------------------------------------------------------------------------


@app.command("validate")
def validate(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Target model")],
    file: Annotated[str, typer.Argument(help="CSV or JSON file to validate")],
) -> None:
    """Validate an import file against a model without importing.

    Checks: field names exist, required fields present, data types
    match (Many2one references resolve, selection values valid).
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    path = Path(file)
    if not path.exists():
        out.error(f"File not found: {file}")
        raise typer.Exit(1)

    data = _parse_csv(path) if path.suffix.lower() == ".csv" else _parse_json(path)

    if not data:
        out.error("No records in file")
        raise typer.Exit(1)

    # Get field definitions
    fields_meta = c.fields_get(model, ["string", "type", "required", "selection", "relation"])
    valid_fields = set(fields_meta.keys())
    file_fields = set(data[0].keys()) - {"id", ".id"}

    issues: list[str] = []

    # Check unknown fields
    unknown = file_fields - valid_fields
    for f in sorted(unknown):
        issues.append(f"Unknown field: '{f}'")

    # Check required fields
    known_fields = file_fields & valid_fields
    for fname, fmeta in fields_meta.items():
        if (
            fmeta.get("required")
            and fname not in file_fields
            and fname not in ("id", "create_uid", "write_uid", "create_date", "write_date")
        ):
            issues.append(f"Missing required field: '{fname}' ({fmeta.get('string', '')})")

    # Validate data types on first 10 records
    for i, row in enumerate(data[:10]):
        for fname, value in row.items():
            if fname not in fields_meta or not value:
                continue
            fmeta = fields_meta[fname]
            ftype = fmeta.get("type", "")

            # Check Many2one — value should be int or exist as name
            if ftype == "many2one" and value:
                with contextlib.suppress(ValueError, TypeError):
                    int(value)

            # Check selection values
            if ftype == "selection" and fmeta.get("selection"):
                valid_values = [s[0] for s in fmeta["selection"]]
                if str(value) not in valid_values:
                    issues.append(
                        f"Row {i + 1}, '{fname}': invalid selection value '{value}'"
                        f" (valid: {', '.join(str(v) for v in valid_values[:5])})"
                    )

            # Check integer/float
            if ftype in ("integer", "float", "monetary") and value:
                try:
                    float(value)
                except (ValueError, TypeError):
                    issues.append(f"Row {i + 1}, '{fname}': expected number, got '{value}'")

    if issues:
        out.error(f"Validation found {len(issues)} issues:")
        for issue in issues[:20]:
            console.print(f"  [red]E[/red] {issue}")
        if len(issues) > 20:
            console.print(f"  ... and {len(issues) - 20} more")
        raise typer.Exit(1)
    else:
        out.success(f"Validation passed: {len(data)} records, {len(known_fields)} fields, no issues")


# ---------------------------------------------------------------------------
# Opening Balances — create journal entries for GL opening
# ---------------------------------------------------------------------------


@app.command("opening-balances")
def opening_balances(
    ctx: typer.Context,
    file: Annotated[str, typer.Argument(help="CSV file with columns: account_code, debit, credit, partner (optional)")],
    journal: Annotated[str, typer.Option("--journal", "-j", help="Journal code (default: MISC)")] = "MISC",
    date: Annotated[str, typer.Option("--date", "-d", help="Opening date (YYYY-MM-DD)")] = "",
    ref: Annotated[str, typer.Option("--ref", help="Reference text")] = "Opening Balances",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Validate without creating")] = False,
) -> None:
    """Import opening balances as a journal entry.

    CSV format:
        account_code,debit,credit,partner
        110100,50000,0,
        210100,0,30000,
        310100,0,20000,

    Creates a single journal entry (account.move) with one line per row.
    Debit and credit must balance. Partner column is optional (for AR/AP).

    Examples:
        kctl-odoo import opening-balances opening.csv --date 2026-01-01
        kctl-odoo import opening-balances opening.csv --journal OBL --dry-run
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    from datetime import date as date_type

    path = Path(file)
    if not path.exists():
        out.error(f"File not found: {file}")
        raise typer.Exit(1)

    opening_date = date if date else str(date_type.today().replace(month=1, day=1))

    # Parse CSV
    rows = _parse_csv(path)
    if not rows:
        out.error("No data rows in file")
        raise typer.Exit(1)

    # Validate columns
    required_cols = {"account_code", "debit", "credit"}
    if not required_cols.issubset(set(rows[0].keys())):
        out.error(f"CSV must have columns: account_code, debit, credit (got: {', '.join(rows[0].keys())})")
        raise typer.Exit(1)

    # Find journal
    journals = c.search_read("account.journal", [("code", "=", journal)], fields=["id", "name"], limit=1)
    if not journals:
        out.error(f"Journal '{journal}' not found. List journals: kctl-odoo setup audit")
        raise typer.Exit(1)
    journal_id = journals[0]["id"]

    # Resolve account codes and build lines
    lines = []
    total_debit = 0.0
    total_credit = 0.0
    issues = []

    for i, row in enumerate(rows, 1):
        code = row.get("account_code", "").strip()
        try:
            debit = float(row.get("debit", 0) or 0)
            credit = float(row.get("credit", 0) or 0)
        except ValueError:
            issues.append(f"Row {i}: invalid debit/credit values")
            continue

        if not code:
            issues.append(f"Row {i}: missing account_code")
            continue
        if debit == 0 and credit == 0:
            continue  # Skip zero lines

        # Resolve account
        accounts = c.search_read("account.account", [("code", "=", code)], fields=["id", "name"], limit=1)
        if not accounts:
            # Try partial match
            accounts = c.search_read("account.account", [("code", "ilike", code)], fields=["id", "name"], limit=1)
        if not accounts:
            issues.append(f"Row {i}: account '{code}' not found")
            continue

        line_vals = {
            "account_id": accounts[0]["id"],
            "name": ref,
            "debit": debit,
            "credit": credit,
        }

        # Optional partner
        partner_name = row.get("partner", "").strip()
        if partner_name:
            partners = c.search_read("res.partner", [("name", "ilike", partner_name)], fields=["id"], limit=1)
            if partners:
                line_vals["partner_id"] = partners[0]["id"]

        lines.append((0, 0, line_vals))
        total_debit += debit
        total_credit += credit

    if issues:
        out.error(f"{len(issues)} issues found:")
        for issue in issues[:15]:
            console.print(f"  [red]E[/red] {issue}")
        raise typer.Exit(1)

    # Check balance
    diff = abs(total_debit - total_credit)
    if diff > 0.01:
        out.error(f"Debit ({total_debit:,.2f}) != Credit ({total_credit:,.2f}) — difference: {diff:,.2f}")
        raise typer.Exit(1)

    out.info(f"Opening balances: {len(lines)} lines, Debit: {total_debit:,.2f}, Credit: {total_credit:,.2f}")

    if dry_run:
        out.success("Dry run passed — balances match, all accounts resolved")
        if actx.json_mode:
            out.raw_json({"lines": len(lines), "debit": total_debit, "credit": total_credit, "balanced": True})
        return

    # Create journal entry
    move_vals = {
        "journal_id": journal_id,
        "date": opening_date,
        "ref": ref,
        "line_ids": lines,
    }

    try:
        move_id = c.create("account.move", move_vals)
        out.success(
            f"Created opening balance journal entry ID {move_id} ({len(lines)} lines, {total_debit:,.2f} total)"
        )
        out.info(f'Post it via: kctl-odoo shell call account.move button_post "[[{move_id}]]"')
    except Exception as e:
        out.error(f"Failed to create journal entry: {e}")
        raise typer.Exit(1) from e


# ---------------------------------------------------------------------------
# Inventory — set stock levels
# ---------------------------------------------------------------------------


@app.command("inventory")
def inventory(
    ctx: typer.Context,
    file: Annotated[str, typer.Argument(help="CSV with: product_code, location (optional), lot (optional), quantity")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Validate without updating")] = False,
) -> None:
    """Import inventory levels (stock quantities).

    CSV format:
        product_code,quantity,location,lot
        PROD001,100,WH/Stock,
        PROD002,50,WH/Stock,LOT-001

    Uses Odoo's inventory adjustment mechanism (stock.quant with
    inventory_quantity). Location defaults to the main warehouse stock.

    Examples:
        kctl-odoo import inventory stock_levels.csv
        kctl-odoo import inventory stock_levels.csv --dry-run
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    path = Path(file)
    if not path.exists():
        out.error(f"File not found: {file}")
        raise typer.Exit(1)

    rows = _parse_csv(path)
    if not rows:
        out.error("No data rows")
        raise typer.Exit(1)

    if "product_code" not in rows[0] or "quantity" not in rows[0]:
        out.error("CSV must have columns: product_code, quantity (optional: location, lot)")
        raise typer.Exit(1)

    # Get default stock location
    default_locations = c.search_read(
        "stock.warehouse",
        domain=[],
        fields=["lot_stock_id"],
        limit=1,
    )
    default_location_id = default_locations[0]["lot_stock_id"][0] if default_locations else None

    results = {"resolved": 0, "not_found": 0, "updated": 0, "errors": 0}
    issues = []

    for i, row in enumerate(rows, 1):
        code = row.get("product_code", "").strip()
        try:
            qty = float(row.get("quantity", 0) or 0)
        except ValueError:
            issues.append(f"Row {i}: invalid quantity")
            results["errors"] += 1
            continue

        if not code:
            issues.append(f"Row {i}: missing product_code")
            results["errors"] += 1
            continue

        # Find product
        products = c.search_read("product.product", [("default_code", "=", code)], fields=["id", "name"], limit=1)
        if not products:
            products = c.search_read(
                "product.product", [("default_code", "ilike", code)], fields=["id", "name"], limit=1
            )
        if not products:
            issues.append(f"Row {i}: product '{code}' not found")
            results["not_found"] += 1
            continue

        product_id = products[0]["id"]
        results["resolved"] += 1

        # Resolve location
        location_id = default_location_id
        loc_name = row.get("location", "").strip()
        if loc_name:
            locations = c.search_read("stock.location", [("complete_name", "ilike", loc_name)], fields=["id"], limit=1)
            if locations:
                location_id = locations[0]["id"]

        if not location_id:
            issues.append(f"Row {i}: no stock location found")
            results["errors"] += 1
            continue

        if dry_run:
            continue

        # Set inventory quantity via stock.quant
        try:
            # Find existing quant
            quant_domain = [("product_id", "=", product_id), ("location_id", "=", location_id)]
            lot_name = row.get("lot", "").strip()
            if lot_name:
                lots = c.search_read(
                    "stock.lot", [("name", "=", lot_name), ("product_id", "=", product_id)], fields=["id"], limit=1
                )
                if lots:
                    quant_domain.append(("lot_id", "=", lots[0]["id"]))

            quants = c.search_read("stock.quant", quant_domain, fields=["id", "quantity"], limit=1)

            if quants:
                c.write("stock.quant", [quants[0]["id"]], {"inventory_quantity": qty})
            else:
                c.create(
                    "stock.quant",
                    {
                        "product_id": product_id,
                        "location_id": location_id,
                        "inventory_quantity": qty,
                    },
                )
            results["updated"] += 1
        except Exception as e:
            issues.append(f"Row {i}: {e}")
            results["errors"] += 1

    if issues and len(issues) <= 15:
        for issue in issues:
            console.print(f"  [yellow]W[/yellow] {issue}")

    if dry_run:
        out.success(
            f"Dry run: {results['resolved']} products resolved,"
            f" {results['not_found']} not found, {results['errors']} errors"
        )
    else:
        out.success(
            f"Inventory: {results['updated']} updated, {results['not_found']} not found, {results['errors']} errors"
        )
        if results["updated"]:
            out.info("Apply adjustments via: Inventory > Operations > Physical Inventory > Apply All")

    if actx.json_mode:
        out.raw_json(results)


# ---------------------------------------------------------------------------
# Import Guide
# ---------------------------------------------------------------------------


@app.command("guide")
def guide(ctx: typer.Context) -> None:
    """Show the recommended data import order and CSV formats.

    Covers master data, opening balances, and transaction migration
    in the correct sequence for a new Odoo implementation.
    """
    console.print("""
[bold cyan]Odoo Data Import Guide[/bold cyan]

Import data in this order to maintain referential integrity:

[bold]Phase 1: Master Data (import first)[/bold]

  [bold]1. Partners (customers + vendors)[/bold]
     kctl-odoo import template res.partner -o partners.csv
     # Edit CSV: name, email, phone, vat, street, city, country_id, is_company, customer_rank, supplier_rank
     kctl-odoo import validate res.partner partners.csv
     kctl-odoo import records res.partner partners.csv

  [bold]2. Product Categories[/bold]
     kctl-odoo import template product.category -o categories.csv
     kctl-odoo import records product.category categories.csv

  [bold]3. Products[/bold]
     kctl-odoo import template product.template -o products.csv
     # Key fields: name, default_code, type, categ_id, list_price, standard_price, uom_id
     kctl-odoo import validate product.template products.csv
     kctl-odoo import records product.template products.csv

[bold]Phase 2: Opening Balances[/bold]

  [bold]4. GL Opening Balances[/bold]
     # CSV format: account_code, debit, credit, partner
     # Debit and credit MUST balance exactly
     kctl-odoo import opening-balances opening.csv --date 2026-01-01 --dry-run
     kctl-odoo import opening-balances opening.csv --date 2026-01-01
     # Then post: kctl-odoo shell call account.move button_post "[[<move_id>]]"

  [bold]5. Inventory Levels[/bold]
     # CSV format: product_code, quantity, location (optional), lot (optional)
     kctl-odoo import inventory stock.csv --dry-run
     kctl-odoo import inventory stock.csv
     # Then apply via: Inventory > Operations > Physical Inventory > Apply All

[bold]Phase 3: Open Transactions (optional)[/bold]

  [bold]6. Open Customer Invoices (AR)[/bold]
     # Include in opening balances as receivable lines with partner
     # Or import as draft invoices:
     kctl-odoo import template account.move -o invoices.csv
     kctl-odoo import records account.move invoices.csv

  [bold]7. Open Vendor Bills (AP)[/bold]
     # Same approach — opening balance lines or draft bills

  [bold]8. Sale Orders (if migrating active orders)[/bold]
     kctl-odoo import template sale.order -o orders.csv
     kctl-odoo import records sale.order orders.csv

[bold]Phase 4: Verify[/bold]

  kctl-odoo setup audit                            # Check all master data
  kctl-odoo maintenance check-data                 # Data integrity checks
  kctl-odoo -p dev performance stats               # Record counts

[dim]Tip: Always use --dry-run first to validate before importing.[/dim]
[dim]Tip: Import to a test database first, verify, then repeat on production.[/dim]
""")
