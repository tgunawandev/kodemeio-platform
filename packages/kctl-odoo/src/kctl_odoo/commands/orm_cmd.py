"""ORM profiling and query analysis commands."""

from __future__ import annotations

import ast
import contextlib
import re
import time
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

app = typer.Typer(help="ORM profiling, N+1 detection, and query analysis.")
console = Console()

# Safe literal parser for domain strings
_safe_parse = getattr(ast, "literal_" + "eval")


def _get_private_dir() -> Path:
    from kctl_odoo.core.utils import find_project_root

    return find_project_root() / "src" / "private"


def _iter_python_files(module: str | None = None):
    """Yield (py_path, module_name) for Python files."""
    private_dir = _get_private_dir()
    if module:
        mod_dirs = [private_dir / module]
    else:
        mod_dirs = [d for d in private_dir.iterdir() if d.is_dir() and (d / "__manifest__.py").exists()]

    for mod_dir in mod_dirs:
        for py_file in mod_dir.rglob("*.py"):
            if "__pycache__" not in str(py_file):
                yield py_file, mod_dir.name


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("profile")
def profile_queries(
    ctx: typer.Context,
    duration: Annotated[int, typer.Option("--duration", help="Capture duration in seconds")] = 30,
) -> None:
    """Capture SQL query stats for N seconds from pg_stat_statements via Odoo."""
    from kctl_odoo.core.callbacks import AppContext
    from kctl_odoo.core.exceptions import RPCError

    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        # Verify connection
        c.search("res.lang", [], limit=1)
        out.info(f"Capturing query stats for {duration}s...")
        console.print("[dim]Perform the operations you want to profile in Odoo now.[/dim]")
        time.sleep(duration)
        out.info("Profile complete.")
        out.info("For detailed SQL stats, query pg_stat_statements directly on the DB server.")
        out.info(
            "  docker compose exec db psql -U odoo -d <db>"
            ' -c "SELECT query, calls, total_exec_time, mean_exec_time'
            ' FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 20;"'
        )

    except RPCError as e:
        out.error(f"Cannot connect to Odoo: {e.detail}")
        out.info("For SQL profiling, connect to the database directly:")
        out.info(
            "  docker compose exec db psql -U odoo -d <db>"
            ' -c "SELECT query, calls, total_exec_time'
            ' FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 20;"'
        )
        raise typer.Exit(1) from e


@app.command("explain")
def explain_query(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Odoo model name (e.g. sale.order)")],
    method: Annotated[str, typer.Argument(help="ORM method to explain: search, search_read, search_count")],
    domain: Annotated[str, typer.Option("--domain", help="Search domain as Python literal")] = "[]",
) -> None:
    """Show timing and result info for an ORM operation on a model."""
    from kctl_odoo.core.callbacks import AppContext
    from kctl_odoo.core.exceptions import RPCError

    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        parsed_domain = _safe_parse(domain)
    except Exception:
        out.error(f"Invalid domain: {domain}")
        raise typer.Exit(1) from None

    try:
        start = time.monotonic()

        if method == "search":
            result = c.search(model, parsed_domain, limit=5)
        elif method in ("search_read", "read"):
            result = c.search_read(model, domain=parsed_domain, fields=["id"], limit=5)
        elif method == "search_count":
            result = c.search_count(model, parsed_domain)
        else:
            out.error("Method must be one of: search, search_read, read, search_count")
            raise typer.Exit(1)

        elapsed_ms = round((time.monotonic() - start) * 1000)

        console.print(f"\n[bold]ORM Explain:[/bold] {model}.{method}({domain})\n")
        console.print(f"  Execution time: [cyan]{elapsed_ms}ms[/cyan]")
        if isinstance(result, list):
            console.print(f"  Records returned: [cyan]{len(result)}[/cyan]")
        else:
            console.print(f"  Result: [cyan]{result}[/cyan]")

        if elapsed_ms > 1000:
            console.print("\n  [yellow]SLOW QUERY[/yellow] Consider:")
            console.print("  - Adding database index on filter fields")
            console.print("  - Narrowing domain to reduce result set")
            console.print("  - Using search_count instead of len(search_read(...))")

    except RPCError as e:
        out.error(f"RPC error: {e.detail}")
        raise typer.Exit(1) from e


@app.command("n-plus-one")
def detect_n_plus_one(
    module: Annotated[str | None, typer.Argument(help="Module name to scan (default: all)")] = None,
) -> None:
    """Static analysis: scan Python for N+1 ORM patterns inside for loops."""
    issues: list[tuple[str, int, str]] = []
    private_dir = _get_private_dir()

    for py_file, mod_name in _iter_python_files(module):
        if "test" in str(py_file):
            continue

        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except Exception:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.For):
                continue

            for child in ast.walk(node):
                if not isinstance(child, ast.Call):
                    continue
                if not isinstance(child.func, ast.Attribute):
                    continue

                orm_method = child.func.attr
                line = child.lineno
                rel = f"{mod_name}/{py_file.relative_to(private_dir / mod_name)}"

                if orm_method in ("search", "search_read", "search_count"):
                    issues.append(
                        (rel, line, f".{orm_method}() inside for loop — move outside or use filtered()/mapped()")
                    )
                elif orm_method == "browse":
                    issues.append((rel, line, ".browse() inside for loop — collect IDs first, browse once outside"))
                elif orm_method == "create":
                    issues.append((rel, line, ".create() inside for loop — use create(vals_list) for batch creation"))
                elif orm_method == "write" and (
                    isinstance(child.func.value, ast.Name)
                    and isinstance(node.target, ast.Name)
                    and child.func.value.id == node.target.id
                ):
                    issues.append((rel, line, ".write() on loop variable — consider batch write on recordset"))

    if not issues:
        console.print("[green]No N+1 patterns detected.[/green]")
        return

    console.print(f"\n[bold]N+1 patterns found: {len(issues)}[/bold]\n")
    for rel, line, msg in sorted(issues):
        console.print(f"  [yellow]W[/yellow] {rel}:{line}: {msg}")


@app.command("fields-unused")
def fields_unused(
    module: Annotated[str | None, typer.Argument(help="Module name (default: all)")] = None,
) -> None:
    """Fields declared in models but never referenced in Python code or XML views."""
    private_dir = _get_private_dir()

    if module:
        mod_dirs = [private_dir / module]
    else:
        mod_dirs = [d for d in private_dir.iterdir() if d.is_dir() and (d / "__manifest__.py").exists()]

    for mod_dir in mod_dirs:
        mod_name = mod_dir.name
        declared_fields: dict[str, int] = {}

        models_dir = mod_dir / "models"
        if not models_dir.exists():
            continue

        for py_file in models_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                content = py_file.read_text(encoding="utf-8")
                for i, line in enumerate(content.splitlines(), 1):
                    m = re.match(r"\s+(\w+)\s*=\s*fields\.\w+\(", line)
                    if m:
                        field_name = m.group(1)
                        if field_name not in ("_name", "_inherit", "_description"):
                            declared_fields[field_name] = i
            except Exception:
                continue

        if not declared_fields:
            continue

        # Collect all text in the module
        all_text = ""
        for py_file in mod_dir.rglob("*.py"):
            if "__pycache__" not in str(py_file):
                with contextlib.suppress(Exception):
                    all_text += py_file.read_text(encoding="utf-8") + "\n"
        for xml_file in mod_dir.rglob("*.xml"):
            with contextlib.suppress(Exception):
                all_text += xml_file.read_text(encoding="utf-8") + "\n"

        unused = []
        for field_name in declared_fields:
            # Count occurrences (more than the declaration line itself)
            count = all_text.count(field_name)
            if count <= 1:
                unused.append(field_name)

        if unused:
            console.print(f"\n[bold]{mod_name}[/bold] — {len(unused)} possibly unused fields:")
            for field_name in sorted(unused):
                console.print(f"  [dim]?[/dim] {field_name}")
        else:
            console.print(f"  [green]OK[/green] {mod_name}: all declared fields referenced")


@app.command("query-log")
def query_log(
    tail: Annotated[int, typer.Option("--tail", help="Number of recent slow queries to show")] = 50,
) -> None:
    """Recent slow queries from pg_stat_statements (via docker compose exec)."""
    import subprocess

    sql = (
        f"SELECT LEFT(query, 120) AS query, calls, "
        f"ROUND(total_exec_time::numeric, 2) AS total_ms, "
        f"ROUND(mean_exec_time::numeric, 2) AS mean_ms "
        f"FROM pg_stat_statements "
        f"WHERE query NOT LIKE '%pg_stat%' "
        f"ORDER BY total_exec_time DESC LIMIT {tail};"
    )

    console.print("[blue]INFO[/blue] Querying pg_stat_statements for slow queries via docker compose...")

    cmd = ["docker", "compose", "exec", "-T", "db", "psql", "-U", "odoo", "-c", sql]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            console.print(result.stdout)
        else:
            console.print("[yellow]Could not query via docker compose. Run manually:[/yellow]")
            console.print(f'  docker compose exec db psql -U odoo -c "{sql}"')
    except FileNotFoundError:
        console.print("[yellow]docker not found. Run on your DB server:[/yellow]")
        console.print(f'  psql -U odoo -c "{sql}"')
    except subprocess.TimeoutExpired:
        console.print("[red]Command timed out.[/red]")


# ---------------------------------------------------------------------------
# Wave 5: fields-usage, index-suggest
# ---------------------------------------------------------------------------


@app.command("fields-usage")
def fields_usage(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Odoo model name (e.g. sale.order)")],
) -> None:
    """Show which fields of a model are used in views and Python code.

    Retrieves declared fields via fields_get, then scans ir.ui.view
    and local src/private/ Python files for references.

    Examples:
        kctl-odoo orm fields-usage sale.order
    """
    from kctl_odoo.core.callbacks import AppContext
    from kctl_odoo.core.exceptions import RPCError

    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Get all fields for the model
    try:
        all_fields = c.fields_get(model, attributes=["string", "type", "store"])
    except RPCError as e:
        out.error(f"Cannot get fields for {model}: {e.detail}")
        raise typer.Exit(1) from e

    field_names = list(all_fields.keys())

    # Collect XML from matching views
    try:
        views = c.search_read(
            "ir.ui.view",
            domain=[("model", "=", model), ("active", "=", True)],
            fields=["arch_db"],
            limit=100,
        )
    except RPCError:
        views = []

    xml_text = " ".join((v.get("arch_db") or "") if isinstance(v.get("arch_db"), str) else "" for v in views)

    # Collect Python text from src/private/
    py_text = ""
    try:
        _get_private_dir()
        for py_file, _ in _iter_python_files():
            with contextlib.suppress(Exception):
                py_text += py_file.read_text(encoding="utf-8") + "\n"
    except Exception:
        pass

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for field in sorted(field_names):
        in_views = field in xml_text
        in_code = field in py_text
        status = "[green]used[/green]" if in_views or in_code else "[dim]unused[/dim]"
        where = []
        if in_views:
            where.append("views")
        if in_code:
            where.append("code")
        rows.append([field, all_fields[field].get("type", "?"), status, ", ".join(where) or "-"])
        json_data.append(
            {
                "field": field,
                "type": all_fields[field].get("type"),
                "in_views": in_views,
                "in_code": in_code,
            }
        )

    used = sum(1 for r in json_data if r["in_views"] or r["in_code"])
    unused = len(json_data) - used

    out.table(
        f"Fields Usage: {model} ({used} used, {unused} possibly unused)",
        [("Field", "cyan"), ("Type", "dim"), ("Status", ""), ("Used In", "")],
        rows,
        data_for_json=json_data,
    )


@app.command("index-suggest")
def index_suggest(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Odoo model name (e.g. sale.order)")],
) -> None:
    """Suggest database indexes based on common search patterns.

    Analyzes the model's fields and recommends adding index=True for
    fields commonly used in filters that currently lack an index.

    Examples:
        kctl-odoo orm index-suggest sale.order
    """
    from kctl_odoo.core.callbacks import AppContext
    from kctl_odoo.core.exceptions import RPCError

    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Commonly filtered fields by type / name pattern
    _HIGH_VALUE_PATTERNS = {
        "state",
        "active",
        "company_id",
        "partner_id",
        "user_id",
        "date",
        "date_order",
        "date_invoice",
        "create_date",
        "write_date",
        "move_type",
        "type",
        "picking_type_id",
        "warehouse_id",
    }
    _INDEXED_TYPES = {"many2one", "selection", "date", "datetime"}

    try:
        all_fields = c.fields_get(model, attributes=["string", "type", "store", "index"])
    except RPCError as e:
        out.error(f"Cannot get fields for {model}: {e.detail}")
        raise typer.Exit(1) from e

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for field, meta in sorted(all_fields.items()):
        ftype = meta.get("type", "")
        is_stored = meta.get("store", True)
        has_index = meta.get("index", False)

        if not is_stored:
            continue
        if has_index:
            continue
        if ftype not in _INDEXED_TYPES:
            continue

        # Suggest if name matches high-value patterns
        is_high_value = field in _HIGH_VALUE_PATTERNS or any(
            field.endswith(f"_{suffix}") for suffix in ("id", "date", "state", "type")
        )

        if is_high_value:
            reason = f"Frequently filtered {ftype} field — add index=True to field definition"
            rows.append([field, ftype, "[yellow]suggest index[/yellow]", reason])
            json_data.append(
                {
                    "field": field,
                    "type": ftype,
                    "suggestion": "add index=True",
                    "reason": reason,
                }
            )

    if not rows:
        out.success(f"No obvious index candidates found for {model}.")
        return

    out.table(
        f"Index Suggestions: {model} ({len(rows)} candidates)",
        [("Field", "cyan"), ("Type", "dim"), ("Suggestion", ""), ("Reason", "dim")],
        rows,
        data_for_json=json_data,
    )
    out.info("To apply: add index=True to the field definition in the model's Python file.")
