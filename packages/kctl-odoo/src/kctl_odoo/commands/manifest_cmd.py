"""Module manifest validation and dependency analysis commands."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Validate and analyze Odoo module manifests.")
console = Console()

# Required keys per Kodemeio conventions
_REQUIRED_KEYS = ["name", "version", "depends", "installable"]
_RECOMMENDED_KEYS = ["author", "license", "summary", "category", "description"]
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+\.\d+\.\d+$")  # e.g. 18.0.1.0.0

# Safe manifest loader — uses ast module's safe literal parser
_safe_parse = getattr(ast, "literal_" + "eval")


def _get_private_dir() -> Path:
    from kctl_odoo.core.utils import find_project_root

    return find_project_root() / "src" / "private"


def _load_manifest(mod_dir: Path) -> dict | None:
    """Safely load __manifest__.py using ast safe literal parser."""
    manifest_path = mod_dir / "__manifest__.py"
    if not manifest_path.exists():
        return None
    try:
        content = manifest_path.read_text(encoding="utf-8")
        return _safe_parse(content)
    except Exception:
        return None


def _iter_modules(module: str | None = None):
    """Yield module directories (with __manifest__.py)."""
    private_dir = _get_private_dir()
    if module:
        mod_dir = private_dir / module
        if mod_dir.is_dir() and (mod_dir / "__manifest__.py").exists():
            yield mod_dir
        return
    for d in sorted(private_dir.iterdir()):
        if d.is_dir() and (d / "__manifest__.py").exists():
            yield d


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("validate")
def validate_manifests(
    module: Annotated[str | None, typer.Argument(help="Module name to validate (default: all)")] = None,
) -> None:
    """Check __manifest__.py: required keys, version format, installable=True."""
    errors = 0
    checked = 0

    for mod_dir in _iter_modules(module):
        manifest_path = mod_dir / "__manifest__.py"
        mod_name = mod_dir.name
        checked += 1

        try:
            content = manifest_path.read_text(encoding="utf-8")
            data = _safe_parse(content)
        except SyntaxError as e:
            console.print(f"  [red]E[/red] {mod_name}/__manifest__.py: Syntax error: {e}")
            errors += 1
            continue
        except Exception as e:
            console.print(f"  [red]E[/red] {mod_name}/__manifest__.py: Parse error: {e}")
            errors += 1
            continue

        mod_ok = True

        # Required keys
        for key in _REQUIRED_KEYS:
            if key not in data:
                console.print(f"  [red]E[/red] {mod_name}: Missing required key '{key}'")
                errors += 1
                mod_ok = False

        # installable must be True
        if data.get("installable") is False:
            console.print(f"  [yellow]W[/yellow] {mod_name}: installable=False — module won't appear in Apps")

        # Version format: 18.0.x.y.z
        version = data.get("version", "")
        if version and not _VERSION_RE.match(version):
            console.print(f"  [yellow]W[/yellow] {mod_name}: version '{version}' should match 18.0.x.y.z")

        # Recommended keys
        for key in _RECOMMENDED_KEYS:
            if key not in data:
                console.print(f"  [dim]I[/dim] {mod_name}: Missing recommended key '{key}'")

        if mod_ok:
            console.print(f"  [green]OK[/green] {mod_name}")

    console.print(f"\n[bold]Checked {checked} modules, {errors} errors.[/bold]")
    if errors:
        raise typer.Exit(1)


@app.command("lint")
def lint_manifests(
    module: Annotated[str | None, typer.Argument(help="Module name (default: all)")] = None,
) -> None:
    """Kodemeio conventions: depends ordering, description present, author set."""
    issues_total = 0

    for mod_dir in _iter_modules(module):
        mod_name = mod_dir.name
        data = _load_manifest(mod_dir)
        if data is None:
            console.print(f"  [red]E[/red] {mod_name}: Cannot parse __manifest__.py")
            issues_total += 1
            continue

        issues: list[str] = []

        # description present (not just summary)
        if not data.get("description", "").strip():
            issues.append("Missing 'description' (multi-line docs)")

        # author set
        if not data.get("author", "").strip():
            issues.append("Missing 'author'")

        # website set
        if not data.get("website", ""):
            issues.append("Missing 'website'")

        # license set
        if not data.get("license", ""):
            issues.append("Missing 'license'")

        # depends ordering: base should come first if present
        depends = data.get("depends", [])
        if isinstance(depends, list) and "base" in depends and depends.index("base") != 0:
            issues.append("'base' should be first in depends list")

        # data files: security/ir.model.access.csv should be listed
        data_files = data.get("data", [])
        if isinstance(data_files, list):
            has_security = any("ir.model.access.csv" in f for f in data_files)
            if not has_security:
                security_csv = mod_dir / "security" / "ir.model.access.csv"
                if security_csv.exists():
                    issues.append("security/ir.model.access.csv exists but not listed in 'data'")

        if issues:
            for issue in issues:
                console.print(f"  [yellow]W[/yellow] {mod_name}: {issue}")
            issues_total += len(issues)
        else:
            console.print(f"  [green]OK[/green] {mod_name}")

    console.print(f"\n[bold]{issues_total} convention issues found.[/bold]")


@app.command("deps")
def show_deps(
    module: Annotated[str, typer.Argument(help="Module name to show dependency tree for")],
) -> None:
    """Show dependency tree for a module (static, from __manifest__.py)."""
    private_dir = _get_private_dir()
    visited: set[str] = set()

    def _print_tree(name: str, indent: int = 0) -> None:
        prefix = "  " * indent
        if name in visited:
            console.print(f"{prefix}[dim]{name} (already shown)[/dim]")
            return
        visited.add(name)

        mod_dir = private_dir / name
        data = _load_manifest(mod_dir) if mod_dir.is_dir() else None
        source = "[cyan](private)[/cyan]" if data else "[dim](external)[/dim]"
        console.print(f"{prefix}[bold]{name}[/bold] {source}")

        if data:
            for dep in sorted(data.get("depends", [])):
                _print_tree(dep, indent + 1)

    console.print(f"\n[bold]Dependency tree:[/bold] {module}\n")
    _print_tree(module)


@app.command("circular")
def detect_circular() -> None:
    """Detect circular dependencies across all private modules."""
    _get_private_dir()
    graph: dict[str, list[str]] = {}

    for mod_dir in _iter_modules():
        data = _load_manifest(mod_dir)
        if data:
            graph[mod_dir.name] = list(data.get("depends", []))

    cycles_found = []

    def _dfs(node: str, path: list[str], visited: set[str]) -> None:
        if node in visited:
            if node in path:
                cycle_start = path.index(node)
                cycles_found.append(path[cycle_start:] + [node])
            return
        visited.add(node)
        path.append(node)
        for dep in graph.get(node, []):
            _dfs(dep, path[:], visited)

    for mod_name in graph:
        _dfs(mod_name, [], set())

    # Deduplicate cycles
    seen_cycles: set[frozenset] = set()
    unique_cycles = []
    for cycle in cycles_found:
        key = frozenset(cycle)
        if key not in seen_cycles:
            seen_cycles.add(key)
            unique_cycles.append(cycle)

    if not unique_cycles:
        console.print("[green]No circular dependencies detected.[/green]")
        return

    console.print(f"\n[red][bold]Circular dependencies found: {len(unique_cycles)}[/bold][/red]\n")
    for cycle in unique_cycles:
        console.print("  " + " -> ".join(f"[cyan]{m}[/cyan]" for m in cycle))

    raise typer.Exit(1)


@app.command("versions")
def check_versions() -> None:
    """Version consistency check across all private modules."""
    versions: dict[str, str] = {}

    for mod_dir in _iter_modules():
        data = _load_manifest(mod_dir)
        if data:
            versions[mod_dir.name] = data.get("version", "")

    if not versions:
        console.print("[yellow]No modules found.[/yellow]")
        return

    table = Table(title="Module Version Summary", show_header=True)
    table.add_column("Module", style="cyan")
    table.add_column("Version")
    table.add_column("Status")

    for mod_name, version in sorted(versions.items()):
        if not version:
            status = "[yellow]missing[/yellow]"
        elif not _VERSION_RE.match(version):
            status = "[red]invalid format[/red]"
        elif not version.startswith("18."):
            status = "[yellow]wrong Odoo version[/yellow]"
        else:
            status = "[green]OK[/green]"
        table.add_row(mod_name, version or "-", status)

    console.print(table)


@app.command("report")
def manifest_report() -> None:
    """Full manifest health report across all private modules."""
    console.print("\n[bold]Manifest Health Report[/bold]\n")

    results = []
    for mod_dir in _iter_modules():
        mod_name = mod_dir.name
        manifest_path = mod_dir / "__manifest__.py"

        try:
            content = manifest_path.read_text(encoding="utf-8")
            data = _safe_parse(content)
            parse_ok = True
        except Exception:
            data = {}
            parse_ok = False

        errors = 0
        warnings = 0

        if not parse_ok:
            errors += 1
        else:
            for key in _REQUIRED_KEYS:
                if key not in data:
                    errors += 1
            version = data.get("version", "")
            if version and not _VERSION_RE.match(version):
                warnings += 1
            if not data.get("description", "").strip():
                warnings += 1
            if not data.get("author", ""):
                warnings += 1

        results.append((mod_name, data.get("version", "-"), errors, warnings))

    table = Table(title=f"Manifest Report ({len(results)} modules)", show_header=True)
    table.add_column("Module", style="cyan")
    table.add_column("Version")
    table.add_column("Errors", justify="right")
    table.add_column("Warnings", justify="right")
    table.add_column("Status")

    total_errors = 0
    total_warnings = 0
    for mod_name, version, errors, warnings in results:
        total_errors += errors
        total_warnings += warnings
        if errors:
            status = "[red]FAIL[/red]"
        elif warnings:
            status = "[yellow]WARN[/yellow]"
        else:
            status = "[green]OK[/green]"
        e_str = f"[red]{errors}[/red]" if errors else "0"
        w_str = f"[yellow]{warnings}[/yellow]" if warnings else "0"
        table.add_row(mod_name, version or "-", e_str, w_str, status)

    console.print(table)
    console.print(f"\n[bold]Total:[/bold] {total_errors} errors, {total_warnings} warnings")

    if total_errors:
        raise typer.Exit(1)
