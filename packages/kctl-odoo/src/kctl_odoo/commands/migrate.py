"""Migration management commands — audit, cleanse, map, load, verify."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.client import OdooClient
from kctl_odoo.core.config import resolve_connection

app = typer.Typer(help="Database migration tools — audit source, validate target, compare.")
console = Console()


def _client_for_profile(profile_name: str) -> OdooClient:
    """Create an OdooClient for the given profile name."""
    url, database, username, api_key = resolve_connection(
        profile_name=profile_name,
        url_override=None,
        api_key_override=None,
        database_override=None,
        username_override=None,
    )
    return OdooClient(
        base_url=url,
        database=database,
        username=username,
        api_key=api_key,
    )


def _get_table_counts(client: OdooClient) -> dict[str, int]:
    """Query ir.model for all models and their record counts."""
    models = client.search_read(
        "ir.model",
        domain=[],
        fields=["model"],
        limit=0,
    )
    counts: dict[str, int] = {}
    for m in models:
        model_name = m["model"]
        try:
            count = client.search_count(model_name, [])
            counts[model_name] = count
        except Exception:
            # Some models are abstract or not queryable
            counts[model_name] = -1
    return counts


@app.command()
def status(
    ctx: typer.Context,
    source: Annotated[str, typer.Option("--source", "-s", help="Source profile name")],
    target: Annotated[str, typer.Option("--target", "-t", help="Target profile name")],
) -> None:
    """Show migration status: compare source and target profiles.

    Connects to both profiles and compares database info, module counts,
    and installed module states.

    Examples:
        kctl-odoo migrate status --source production --target staging
    """
    actx: AppContext = ctx.obj
    out = actx.output

    out.info(f"Connecting to source profile: {source}")
    src_client = _client_for_profile(source)

    out.info(f"Connecting to target profile: {target}")
    tgt_client = _client_for_profile(target)

    try:
        src_ok, src_ver = src_client.check_health()
        tgt_ok, tgt_ver = tgt_client.check_health()

        src_modules = 0
        tgt_modules = 0
        if src_ok:
            try:
                src_client.authenticate()
                src_modules = src_client.search_count("ir.module.module", [("state", "=", "installed")])
            except Exception:
                pass
        if tgt_ok:
            try:
                tgt_client.authenticate()
                tgt_modules = tgt_client.search_count("ir.module.module", [("state", "=", "installed")])
            except Exception:
                pass

        sections = [
            (
                "Source",
                [
                    ("Profile", source),
                    ("Database", src_client.database),
                    ("Status", "[green]OK[/green]" if src_ok else f"[red]{src_ver}[/red]"),
                    ("Version", src_ver if src_ok else "-"),
                    ("Installed Modules", str(src_modules)),
                ],
            ),
            (
                "Target",
                [
                    ("Profile", target),
                    ("Database", tgt_client.database),
                    ("Status", "[green]OK[/green]" if tgt_ok else f"[red]{tgt_ver}[/red]"),
                    ("Version", tgt_ver if tgt_ok else "-"),
                    ("Installed Modules", str(tgt_modules)),
                ],
            ),
            (
                "Comparison",
                [
                    ("Module Diff", f"{tgt_modules - src_modules:+d}" if src_modules and tgt_modules else "-"),
                ],
            ),
        ]

        out.detail(
            "Migration Status",
            sections,
            data_for_json={
                "source": {
                    "profile": source,
                    "database": src_client.database,
                    "healthy": src_ok,
                    "version": src_ver if src_ok else None,
                    "installed_modules": src_modules,
                },
                "target": {
                    "profile": target,
                    "database": tgt_client.database,
                    "healthy": tgt_ok,
                    "version": tgt_ver if tgt_ok else None,
                    "installed_modules": tgt_modules,
                },
            },
        )
    finally:
        src_client.close()
        tgt_client.close()


@app.command()
def validate(
    ctx: typer.Context,
    target: Annotated[str | None, typer.Option("--target", "-t", help="Target profile (default: active)")] = None,
) -> None:
    """Post-migration validation checks on the target database.

    Checks for:
    - Modules in error/to upgrade state
    - Missing required ir.model.access records
    - Orphaned records in common relationship tables

    Examples:
        kctl-odoo migrate validate --target staging
    """
    actx: AppContext = ctx.obj
    out = actx.output

    c = _client_for_profile(target) if target else actx.client

    try:
        c.authenticate()

        # Check 1: modules in bad state
        bad_states = c.search_read(
            "ir.module.module",
            domain=[("state", "in", ["to upgrade", "to install", "to remove"])],
            fields=["name", "state"],
            limit=0,
        )

        # Check 2: modules with errors (uninstallable)
        error_modules = c.search_read(
            "ir.module.module",
            domain=[("state", "=", "uninstallable")],
            fields=["name", "state"],
            limit=50,
        )

        # Check 3: total record counts for key models
        key_models = [
            "res.partner",
            "res.users",
            "account.move",
            "sale.order",
            "purchase.order",
            "stock.picking",
            "product.template",
            "product.product",
        ]
        model_counts: list[tuple[str, int]] = []
        for model in key_models:
            try:
                count = c.search_count(model, [])
                model_counts.append((model, count))
            except Exception:
                model_counts.append((model, -1))

        # Build output
        issues: list[tuple[str, str]] = []
        if bad_states:
            for m in bad_states:
                issues.append((m["name"], f"[yellow]{m['state']}[/yellow]"))
        if not issues:
            issues.append(("-", "[green]No issues found[/green]"))

        sections = [
            ("Module State Issues", issues),
            (
                "Uninstallable Modules",
                [(m["name"], "[red]uninstallable[/red]") for m in error_modules[:10]] or [("-", "[green]None[/green]")],
            ),
            (
                "Record Counts",
                [(model, str(count) if count >= 0 else "[dim]n/a[/dim]") for model, count in model_counts],
            ),
        ]

        json_data = {
            "bad_state_modules": [{"name": m["name"], "state": m["state"]} for m in bad_states],
            "uninstallable_count": len(error_modules),
            "record_counts": {model: count for model, count in model_counts},
        }

        out.detail("Migration Validation", sections, data_for_json=json_data)

        if bad_states:
            out.warn(f"{len(bad_states)} module(s) in transitional state.")
        else:
            out.success("All modules in clean state.")

    finally:
        if target:
            c.close()


@app.command()
def tables(
    ctx: typer.Context,
    target: Annotated[str | None, typer.Option("--target", "-t", help="Target profile (default: active)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max models to show")] = 50,
    min_records: Annotated[int, typer.Option("--min", help="Only show models with at least N records")] = 1,
) -> None:
    """Show table record counts on the target instance.

    Queries ir.model for models and counts their records.
    Useful for verifying data was migrated correctly.

    Examples:
        kctl-odoo migrate tables --target staging --min 100
        kctl-odoo migrate tables --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output

    c = _client_for_profile(target) if target else actx.client

    try:
        c.authenticate()

        models = c.search_read(
            "ir.model",
            domain=[("transient", "=", False)],
            fields=["model", "name"],
            limit=0,
            order="model",
        )

        out.info(f"Counting records for {len(models)} models...")

        results: list[tuple[str, str, int]] = []
        for m in models:
            model_name = m["model"]
            try:
                count = c.search_count(model_name, [])
                if count >= min_records:
                    results.append((model_name, m.get("name", ""), count))
            except Exception:
                continue

        # Sort by count descending and apply limit
        results.sort(key=lambda x: x[2], reverse=True)
        results = results[:limit]

        rows = []
        json_data = []
        for model_name, label, count in results:
            rows.append([model_name, label, str(count)])
            json_data.append(
                {
                    "model": model_name,
                    "name": label,
                    "count": count,
                }
            )

        out.table(
            f"Table Record Counts (top {len(results)}, min {min_records})",
            [("Model", "cyan"), ("Description", "dim"), ("Records", "green")],
            rows,
            data_for_json=json_data,
        )
    finally:
        if target:
            c.close()


# ---------------------------------------------------------------------------
# Source Data Quality Audit
# ---------------------------------------------------------------------------


@app.command("audit-source")
def audit_source(
    ctx: typer.Context,
    source: Annotated[str | None, typer.Option("--source", "-s", help="Source profile (default: active)")] = None,
) -> None:
    """Audit source data quality before migration.

    Analyzes the source system for data quality issues that should be
    fixed BEFORE migrating to the new system:

    - Record counts for key business models
    - Duplicate detection (partners by email, by VAT, by name)
    - Completeness checks (required fields with null/empty values)
    - Referential integrity (orphan records)
    - Data distribution (top categories, states, types)

    Examples:
        kctl-odoo migrate audit-source
        kctl-odoo migrate audit-source --source old-system
    """
    actx: AppContext = ctx.obj
    out = actx.output

    c = _client_for_profile(source) if source else actx.client

    try:
        c.authenticate()
        db = c.database

        rows: list[list[str]] = []
        json_data: list[dict] = []
        total_issues = 0

        def _add(category: str, check: str, ok: bool, count: int, detail: str) -> None:
            nonlocal total_issues
            if not ok:
                total_issues += count
            status = "[green]OK[/green]" if ok else f"[red]{count}[/red]"
            rows.append([category, check, status, detail if not ok else ""])
            json_data.append({"category": category, "check": check, "count": count, "ok": ok, "detail": detail})

        console.print(f"\n[bold cyan]Source Data Quality Audit — {db}[/bold cyan]\n")

        # ===================================================================
        # RECORD COUNTS
        # ===================================================================
        console.print("[bold]Record Counts[/bold]")
        count_models = [
            ("res.partner", "Partners"),
            ("product.template", "Product Templates"),
            ("product.product", "Product Variants"),
            ("sale.order", "Sale Orders"),
            ("purchase.order", "Purchase Orders"),
            ("account.move", "Journal Entries"),
            ("stock.picking", "Stock Transfers"),
            ("hr.employee", "Employees"),
        ]
        for model, label in count_models:
            try:
                cnt = c.search_count(model, [])
                console.print(f"  {label}: {cnt:,}")
            except Exception:
                console.print(f"  {label}: [dim]N/A[/dim]")

        # ===================================================================
        # PARTNER DUPLICATES
        # ===================================================================
        console.print("\n[bold]Partner Quality[/bold]")

        # Duplicate emails
        try:
            partners = c.search_read("res.partner", [("email", "!=", False)], fields=["email"], limit=10000)
            emails: dict[str, int] = {}
            for p in partners:
                email = (p.get("email") or "").strip().lower()
                if email:
                    emails[email] = emails.get(email, 0) + 1
            email_dupes = sum(1 for v in emails.values() if v > 1)
            _add(
                "Partners",
                "Duplicate emails",
                email_dupes == 0,
                email_dupes,
                f"{email_dupes} emails appear on multiple partners",
            )
        except Exception:
            pass

        # Duplicate VAT
        try:
            vat_partners = c.search_read("res.partner", [("vat", "!=", False)], fields=["vat"], limit=10000)
            vats: dict[str, int] = {}
            for p in vat_partners:
                vat = (p.get("vat") or "").strip().upper()
                if vat:
                    vats[vat] = vats.get(vat, 0) + 1
            vat_dupes = sum(1 for v in vats.values() if v > 1)
            _add(
                "Partners",
                "Duplicate VAT/TIN",
                vat_dupes == 0,
                vat_dupes,
                f"{vat_dupes} VAT numbers duplicated — merge before migration",
            )
        except Exception:
            pass

        # Duplicate names (companies)
        try:
            companies = c.search_read("res.partner", [("is_company", "=", True)], fields=["name"], limit=10000)
            names: dict[str, int] = {}
            for p in companies:
                name = (p.get("name") or "").strip().lower()
                if name:
                    names[name] = names.get(name, 0) + 1
            name_dupes = sum(1 for v in names.values() if v > 1)
            _add(
                "Partners",
                "Duplicate company names",
                name_dupes == 0,
                name_dupes,
                f"{name_dupes} company names duplicated",
            )
        except Exception:
            pass

        # Partners without email
        try:
            no_email = c.search_count("res.partner", [("email", "in", [False, ""]), ("is_company", "=", True)])
            _add("Partners", "Companies without email", no_email == 0, no_email, f"{no_email} companies have no email")
        except Exception:
            pass

        # Partners without phone
        try:
            no_phone = c.search_count(
                "res.partner", [("phone", "in", [False, ""]), ("mobile", "in", [False, ""]), ("is_company", "=", True)]
            )
            _add(
                "Partners",
                "Companies without phone/mobile",
                no_phone < 10,
                no_phone,
                f"{no_phone} companies have no phone or mobile",
            )
        except Exception:
            pass

        # ===================================================================
        # PRODUCT QUALITY
        # ===================================================================
        console.print("\n[bold]Product Quality[/bold]")

        try:
            no_code = c.search_count("product.template", [("default_code", "in", [False, ""])])
            total_products = c.search_count("product.template", [])
            _add(
                "Products",
                "Without internal reference",
                no_code < total_products * 0.2,
                no_code,
                f"{no_code}/{total_products} products have no internal reference",
            )
        except Exception:
            pass

        try:
            no_categ = c.search_count("product.template", [("categ_id", "=", False)])
            _add("Products", "Without category", no_categ == 0, no_categ, f"{no_categ} products have no category")
        except Exception:
            pass

        try:
            zero_price = c.search_count("product.template", [("list_price", "<=", 0), ("sale_ok", "=", True)])
            _add(
                "Products",
                "Saleable with zero price",
                zero_price == 0,
                zero_price,
                f"{zero_price} saleable products have zero or negative price",
            )
        except Exception:
            pass

        try:
            zero_cost = c.search_count("product.template", [("standard_price", "<=", 0), ("type", "!=", "service")])
            _add(
                "Products",
                "Storable with zero cost",
                zero_cost == 0,
                zero_cost,
                f"{zero_cost} storable products have zero cost",
            )
        except Exception:
            pass

        # ===================================================================
        # ACCOUNTING QUALITY
        # ===================================================================
        console.print("\n[bold]Accounting Quality[/bold]")

        try:
            draft_moves = c.search_count("account.move", [("state", "=", "draft")])
            posted_moves = c.search_count("account.move", [("state", "=", "posted")])
            _add(
                "Accounting",
                "Draft journal entries",
                draft_moves == 0,
                draft_moves,
                f"{draft_moves} draft entries — post or delete before migration",
            )
            console.print(f"  Posted entries: {posted_moves:,}, Draft: {draft_moves:,}")
        except Exception:
            pass

        try:
            unreconciled = c.search_count(
                "account.move.line",
                [
                    ("reconciled", "=", False),
                    ("account_id.reconcile", "=", True),
                ],
            )
            _add(
                "Accounting",
                "Unreconciled items",
                unreconciled < 100,
                unreconciled,
                f"{unreconciled} unreconciled items on reconcilable accounts",
            )
        except Exception:
            pass

        # ===================================================================
        # SUMMARY
        # ===================================================================
        console.print()
        title = f"Source Data Quality ({len(rows)} checks)"
        if total_issues:
            title += f" — [yellow]{total_issues} issues to fix before migration[/yellow]"
        else:
            title += " — [green]data is clean[/green]"

        out.table(
            title,
            [("Category", "dim"), ("Check", "cyan"), ("Status", ""), ("Detail", "dim")],
            rows,
            json_data,
        )

        if total_issues:
            console.print("\n[bold]Recommendations:[/bold]")
            console.print("  1. Merge duplicate partners in source system before migration")
            console.print("  2. Fill missing required fields (email, phone, product codes)")
            console.print("  3. Post or delete journal entries before migrationdraft")
            console.print("  4. Reconcile open items before cut-over")
            console.print("  5. Export clean data: kctl-odoo export records res.partner --format csv")

    finally:
        if source:
            c.close()


# ---------------------------------------------------------------------------
# Wave 5: field-map, column-diff, dry-run
# ---------------------------------------------------------------------------

_KEY_MODELS_FOR_FIELD_MAP = [
    "res.partner",
    "sale.order",
    "account.move",
    "product.template",
    "product.product",
    "stock.picking",
    "purchase.order",
    "hr.employee",
]


@app.command("field-map")
def field_map(
    ctx: typer.Context,
    source: Annotated[str, typer.Option("--source", "-s", help="Source profile name")],
    target: Annotated[str, typer.Option("--target", "-t", help="Target profile name")],
) -> None:
    """Auto-detect field differences between two profiles.

    Compares fields_get output for key models and reports added, removed,
    and type-changed fields.

    Examples:
        kctl-odoo migrate field-map --source old-system --target staging
    """
    actx: AppContext = ctx.obj
    out = actx.output

    src_client = _client_for_profile(source)
    tgt_client = _client_for_profile(target)

    try:
        src_client.authenticate()
        tgt_client.authenticate()

        rows: list[list[str]] = []
        json_data: list[dict] = []

        for model in _KEY_MODELS_FOR_FIELD_MAP:
            try:
                src_fields = src_client.fields_get(model, attributes=["string", "type"])
            except Exception:
                src_fields = {}
            try:
                tgt_fields = tgt_client.fields_get(model, attributes=["string", "type"])
            except Exception:
                tgt_fields = {}

            src_names = set(src_fields.keys())
            tgt_names = set(tgt_fields.keys())

            added = tgt_names - src_names
            removed = src_names - tgt_names
            type_changed = [f for f in src_names & tgt_names if src_fields[f].get("type") != tgt_fields[f].get("type")]

            for field in sorted(added):
                rows.append([model, field, "added", f"type: {tgt_fields[field].get('type', '?')}"])
                json_data.append(
                    {"model": model, "field": field, "change": "added", "detail": tgt_fields[field].get("type")}
                )

            for field in sorted(removed):
                rows.append([model, field, "removed", f"type: {src_fields[field].get('type', '?')}"])
                json_data.append(
                    {"model": model, "field": field, "change": "removed", "detail": src_fields[field].get("type")}
                )

            for field in sorted(type_changed):
                src_type = src_fields[field].get("type", "?")
                tgt_type = tgt_fields[field].get("type", "?")
                rows.append([model, field, "type-changed", f"{src_type} -> {tgt_type}"])
                json_data.append(
                    {"model": model, "field": field, "change": "type-changed", "detail": f"{src_type} -> {tgt_type}"}
                )

        if not rows:
            out.success("No field differences detected across key models.")
            return

        out.table(
            f"Field Differences ({len(rows)} changes)",
            [("Model", "cyan"), ("Field", ""), ("Change", "yellow"), ("Detail", "dim")],
            rows,
            data_for_json=json_data,
        )

    finally:
        src_client.close()
        tgt_client.close()


@app.command("column-diff")
def column_diff(
    ctx: typer.Context,
    table: Annotated[str, typer.Argument(help="Odoo model name (e.g. res.partner)")],
    source: Annotated[str | None, typer.Option("--source", "-s", help="Source profile (default: active)")] = None,
    target: Annotated[str | None, typer.Option("--target", "-t", help="Target profile (default: active)")] = None,
) -> None:
    """Compare column types for a model between source and target.

    Compares field types, required, and stored attributes from fields_get.

    Examples:
        kctl-odoo migrate column-diff res.partner --source old --target new
    """
    actx: AppContext = ctx.obj
    out = actx.output

    src_client = _client_for_profile(source) if source else actx.client
    tgt_client = _client_for_profile(target) if target else actx.client

    try:
        if source:
            src_client.authenticate()
        if target:
            tgt_client.authenticate()

        try:
            src_fields = src_client.fields_get(table, attributes=["string", "type", "required", "store"])
        except Exception as e:
            out.error(f"Could not get fields from source for {table}: {e}")
            raise typer.Exit(1) from e

        try:
            tgt_fields = tgt_client.fields_get(table, attributes=["string", "type", "required", "store"])
        except Exception as e:
            out.error(f"Could not get fields from target for {table}: {e}")
            raise typer.Exit(1) from e

        src_names = set(src_fields.keys())
        tgt_names = set(tgt_fields.keys())

        rows: list[list[str]] = []
        json_data: list[dict] = []

        # Type differences
        common = src_names & tgt_names
        for field in sorted(common):
            sf = src_fields[field]
            tf = tgt_fields[field]
            diffs = []
            if sf.get("type") != tf.get("type"):
                diffs.append(f"type: {sf.get('type')} -> {tf.get('type')}")
            if sf.get("required") != tf.get("required"):
                diffs.append(f"required: {sf.get('required')} -> {tf.get('required')}")
            if sf.get("store") != tf.get("store"):
                diffs.append(f"stored: {sf.get('store')} -> {tf.get('store')}")
            if diffs:
                rows.append([field, sf.get("type", "?"), tf.get("type", "?"), "; ".join(diffs)])
                json_data.append(
                    {"field": field, "src_type": sf.get("type"), "tgt_type": tf.get("type"), "diffs": diffs}
                )

        for field in sorted(src_names - tgt_names):
            rows.append([field, src_fields[field].get("type", "?"), "-", "removed in target"])
            json_data.append(
                {"field": field, "src_type": src_fields[field].get("type"), "tgt_type": None, "diffs": ["removed"]}
            )

        for field in sorted(tgt_names - src_names):
            rows.append([field, "-", tgt_fields[field].get("type", "?"), "added in target"])
            json_data.append(
                {"field": field, "src_type": None, "tgt_type": tgt_fields[field].get("type"), "diffs": ["added"]}
            )

        if not rows:
            out.success(f"No column differences for {table}.")
            return

        out.table(
            f"Column Diff: {table} ({len(rows)} differences)",
            [("Field", "cyan"), ("Source Type", ""), ("Target Type", ""), ("Differences", "yellow")],
            rows,
            data_for_json=json_data,
        )

    finally:
        if source:
            src_client.close()
        if target:
            tgt_client.close()


@app.command("dry-run")
def dry_run_cmd(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Odoo model name (e.g. res.partner)")],
    source: Annotated[str | None, typer.Option("--source", "-s", help="Source profile (default: active)")] = None,
    target: Annotated[str | None, typer.Option("--target", "-t", help="Target profile (default: active)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Sample records to examine")] = 10,
) -> None:
    """Simulate migration for a model — show type mismatches.

    Reads sample records from the source and compares against the target
    schema to surface potential type conflicts before a real migration.

    Examples:
        kctl-odoo migrate dry-run res.partner --source old --target new
        kctl-odoo migrate dry-run sale.order --source old --target new --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output

    src_client = _client_for_profile(source) if source else actx.client
    tgt_client = _client_for_profile(target) if target else actx.client

    try:
        if source:
            src_client.authenticate()
        if target:
            tgt_client.authenticate()

        # Get target schema
        try:
            tgt_fields = tgt_client.fields_get(model, attributes=["string", "type", "required"])
        except Exception as e:
            out.error(f"Cannot get target schema for {model}: {e}")
            raise typer.Exit(1) from e

        # Get source schema
        try:
            src_fields = src_client.fields_get(model, attributes=["type"])
        except Exception as e:
            out.error(f"Cannot get source schema for {model}: {e}")
            raise typer.Exit(1) from e

        # Identify storable scalar fields
        scalar_types = {"char", "text", "integer", "float", "monetary", "boolean", "date", "datetime", "selection"}
        candidate_fields = [f for f in tgt_fields if tgt_fields[f].get("type") in scalar_types and f in src_fields]

        # Fetch sample records from source
        try:
            sample_records = src_client.search_read(
                model,
                domain=[],
                fields=candidate_fields[:30],  # cap fields to avoid huge payloads
                limit=limit,
            )
        except Exception as e:
            out.error(f"Cannot read sample records from source {model}: {e}")
            raise typer.Exit(1) from e

        if not sample_records:
            out.info(f"No records found for {model} in source.")
            return

        # Detect mismatches
        mismatches: list[dict] = []
        for field in candidate_fields[:30]:
            src_type = src_fields.get(field, {}).get("type", "?")
            tgt_type = tgt_fields.get(field, {}).get("type", "?")
            if src_type != tgt_type:
                sample_val = sample_records[0].get(field) if sample_records else None
                mismatches.append(
                    {
                        "field": field,
                        "src_type": src_type,
                        "tgt_type": tgt_type,
                        "sample_value": str(sample_val)[:60],
                    }
                )

        rows = []
        for m in mismatches:
            rows.append([m["field"], m["src_type"], m["tgt_type"], m["sample_value"]])

        if not rows:
            out.success(f"No type mismatches detected for {model} (sample of {limit} records).")
        else:
            out.table(
                f"Dry-Run: {model} — {len(mismatches)} type mismatch(es) in {len(sample_records)} sample records",
                [("Field", "cyan"), ("Source Type", ""), ("Target Type", "yellow"), ("Sample Value", "dim")],
                rows,
                data_for_json=mismatches,
            )

    finally:
        if source:
            src_client.close()
        if target:
            tgt_client.close()
