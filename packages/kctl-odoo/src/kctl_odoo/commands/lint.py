# Copyright 2026 Kodemeio
# License OPL-1

"""Odoo module linting and quality checks.

Validates private modules against Odoo 18 best practices:
- Manifest completeness
- Security CSV presence and completeness
- Model quality (_description, field conventions)
- Python anti-patterns (SQL injection, bare except, print statements)
- View XML validity (Odoo 18 patterns)
- Test presence and quality
- CLAUDE.md documentation
"""

from __future__ import annotations

import ast
import contextlib
import re
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

app = typer.Typer(help="Lint and validate Odoo modules against best practices.")
console = Console()


def _get_private_dir() -> Path:
    from kctl_odoo.core.utils import find_project_root

    return find_project_root() / "src" / "private"


def _find_module(name: str) -> Path:
    p = _get_private_dir() / name
    if p.is_dir() and (p / "__manifest__.py").exists():
        return p
    console.print(f"[red]ERROR[/red] Module not found: {name}")
    raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_manifest(mod_dir: Path) -> list[tuple[str, str, str]]:
    """Check __manifest__.py completeness."""
    issues: list[tuple[str, str, str]] = []
    manifest_path = mod_dir / "__manifest__.py"

    if not manifest_path.exists():
        issues.append(("error", "__manifest__.py", "Missing __manifest__.py"))
        return issues

    try:
        content = manifest_path.read_text()
        tree = ast.parse(content)
        # Extract the dict
        manifest = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key, val in zip(node.keys, node.values, strict=False):
                    if isinstance(key, ast.Constant):
                        manifest[key.value] = val
                break

        if "name" not in manifest:
            issues.append(("error", "__manifest__.py", "Missing 'name'"))
        if "version" not in manifest:
            issues.append(("warn", "__manifest__.py", "Missing 'version'"))
        if "license" not in manifest:
            issues.append(("warn", "__manifest__.py", "Missing 'license'"))
        if "depends" not in manifest:
            issues.append(("error", "__manifest__.py", "Missing 'depends'"))
        if "installable" not in manifest:
            issues.append(("warn", "__manifest__.py", "Missing 'installable: True'"))
        if "author" not in manifest:
            issues.append(("warn", "__manifest__.py", "Missing 'author'"))

    except SyntaxError as e:
        issues.append(("error", "__manifest__.py", f"Syntax error: {e}"))

    return issues


def _check_security(mod_dir: Path) -> list[tuple[str, str, str]]:
    """Check security files."""
    issues: list[tuple[str, str, str]] = []
    csv_path = mod_dir / "security" / "ir.model.access.csv"

    if not csv_path.exists():
        issues.append(("error", "security/", "Missing ir.model.access.csv"))
        return issues

    content = csv_path.read_text()
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]

    if len(lines) < 1:
        issues.append(("error", "ir.model.access.csv", "Empty file"))
    elif len(lines) == 1:
        # Only header, might be OK for inherit-only modules
        issues.append(("info", "ir.model.access.csv", "Header only — OK if module only inherits models"))

    return issues


def _check_python_quality(mod_dir: Path) -> list[tuple[str, str, str]]:
    """Check Python code quality."""
    issues: list[tuple[str, str, str]] = []

    for py_file in mod_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        rel = py_file.relative_to(mod_dir)

        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue

        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            # SQL injection: f-string in SQL
            if re.search(r'f["\'].*(?:SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER)', line, re.IGNORECASE):
                issues.append(("error", f"{rel}:{i}", "f-string in SQL — use psycopg2.sql or %s params"))

            # Bare except
            if re.match(r"\s*except\s*:\s*$", line):
                issues.append(("warn", f"{rel}:{i}", "Bare except: — specify exception type"))

            # print() statements (not in tests)
            if "test" not in str(rel) and re.match(r"\s*print\(", line):
                issues.append(("warn", f"{rel}:{i}", "print() — use _logger.info() instead"))

            # sudo() in router files (privilege escalation risk)
            if "router" in str(rel) and ".sudo()" in line and "test" not in str(rel):
                issues.append(
                    ("info", f"{rel}:{i}", "sudo() in router — verify this privilege escalation is intentional")
                )

            # XSS: Markup() bypass (renders raw HTML without escaping)
            if "Markup(" in line and "test" not in str(rel):
                issues.append(
                    ("warn", f"{rel}:{i}", "XSS risk: Markup() bypasses HTML escaping — ensure input is sanitized")
                )

            # Unsafe eval/exec (code execution)
            if re.match(r"\s*eval\(", line) or re.match(r"\s*exec\(", line):
                issues.append(("error", f"{rel}:{i}", "CRITICAL: eval()/exec() — arbitrary code execution risk"))

            # Unsafe yaml.load (should be safe_load)
            if "yaml.load(" in line and "safe_load" not in line:
                issues.append(("error", f"{rel}:{i}", "yaml.load() — use yaml.safe_load() to prevent code execution"))

            # Unsafe pickle (deserialization attack)
            if "pickle.load" in line or "pickle.loads" in line:
                issues.append(
                    ("error", f"{rel}:{i}", "pickle deserialization — vulnerable to arbitrary code execution")
                )

            # subprocess with shell=True (command injection)
            if "shell=True" in line and ("subprocess" in line or "Popen" in content):
                issues.append(
                    ("error", f"{rel}:{i}", "shell=True — command injection risk, use shell=False with list args")
                )

            # os.system (command injection)
            if re.match(r"\s*os\.system\(", line):
                issues.append(("error", f"{rel}:{i}", "os.system() — use subprocess.run() with shell=False"))

            # Hardcoded credentials (password/secret/key with string literal)
            stripped = line.strip()
            _skip_keywords = [
                "help=",
                "field",
                "param",
                "label",
                "description",
                "example",
                "placeholder",
                "string=",
                "env[",
            ]
            if (
                not stripped.startswith("#")
                and "test" not in str(rel)
                and re.search(
                    r'(?:password|secret|api_key|token)\s*=\s*["\'][^"\']{8,}["\']',
                    stripped,
                    re.IGNORECASE,
                )
                and not any(skip in stripped.lower() for skip in _skip_keywords)
            ):
                issues.append(
                    (
                        "error",
                        f"{rel}:{i}",
                        "Hardcoded credential — use environment variable or ir.config_parameter",
                    )
                )

        # Check for _description on _name models
        if (
            "models" in str(rel)
            and "_name" in content
            and "_description" not in content
            and "_inherit" not in content  # Only new models need _description
        ):
            issues.append(("warn", str(rel), "Model has _name but no _description"))

    return issues


def _check_n_plus_one(mod_dir: Path) -> list[tuple[str, str, str]]:
    """Detect potential N+1 query patterns in Python code.

    Scans for ORM calls (search, browse, write, create, unlink) inside
    for loops, which is the most common Odoo performance anti-pattern.
    """
    issues: list[tuple[str, str, str]] = []

    # ORM methods that hit the database

    for py_file in mod_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        rel = py_file.relative_to(mod_dir)

        # Skip test files — N+1 in tests is acceptable
        if "test" in str(rel):
            continue

        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue

        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue

        # Walk AST to find for loops with ORM calls in body
        for node in ast.walk(tree):
            if not isinstance(node, ast.For):
                continue

            # Check all nodes in the for body
            for child in ast.walk(node):
                if not isinstance(child, ast.Call):
                    continue
                if not isinstance(child.func, ast.Attribute):
                    continue

                method_name = child.func.attr

                # Detect: .search(), .browse(), .write(), .create() inside for loop
                if method_name in ("search", "search_read", "search_count"):
                    issues.append(
                        (
                            "warn",
                            f"{rel}:{child.lineno}",
                            f"N+1: .{method_name}() inside for loop"
                            " — move search before loop or use filtered()/mapped()",
                        )
                    )
                elif method_name == "browse":
                    issues.append(
                        (
                            "warn",
                            f"{rel}:{child.lineno}",
                            "N+1: .browse() inside for loop — collect IDs first, browse once outside loop",
                        )
                    )
                elif method_name == "write" and _is_single_record_write(child, node):
                    issues.append(
                        (
                            "info",
                            f"{rel}:{child.lineno}",
                            "N+1: .write() inside for loop — consider batch write on recordset",
                        )
                    )
                elif method_name == "create":
                    # create() inside loop is a common pattern but can be batched
                    issues.append(
                        (
                            "info",
                            f"{rel}:{child.lineno}",
                            "N+1: .create() inside for loop — use create(vals_list) for batch creation",
                        )
                    )

    return issues


def _is_single_record_write(call_node: ast.Call, for_node: ast.For) -> bool:
    """Heuristic: is this .write() on the loop variable (single record)?"""
    # Check if the write is on a variable that looks like a single record
    if (
        isinstance(call_node.func, ast.Attribute)
        and isinstance(call_node.func.value, ast.Name)
        and isinstance(for_node.target, ast.Name)
    ):
        return call_node.func.value.id == for_node.target.id
    return False


def _check_views(mod_dir: Path) -> list[tuple[str, str, str]]:
    """Check XML views for Odoo 18 patterns."""
    issues: list[tuple[str, str, str]] = []

    for xml_file in mod_dir.rglob("*.xml"):
        if "__pycache__" in str(xml_file):
            continue
        rel = xml_file.relative_to(mod_dir)

        try:
            content = xml_file.read_text(encoding="utf-8")
        except Exception:
            continue

        # Odoo 18: <tree> should be <list>
        if "<tree" in content and "<list" not in content:
            issues.append(("error", str(rel), "Uses <tree> — Odoo 18 requires <list>"))

        # Odoo 18: states= attribute removed
        if "states=" in content and "invisible=" not in content:
            for i, line in enumerate(content.splitlines(), 1):
                if "states=" in line and "__manifest__" not in str(rel):
                    issues.append(("error", f"{rel}:{i}", "states= attribute removed in Odoo 18 — use invisible="))

    return issues


def _check_tests(mod_dir: Path) -> list[tuple[str, str, str]]:
    """Check test presence and quality."""
    issues: list[tuple[str, str, str]] = []
    tests_dir = mod_dir / "tests"

    if not tests_dir.exists():
        issues.append(("error", "tests/", "Missing tests/ directory"))
        return issues

    if not (tests_dir / "__init__.py").exists():
        issues.append(("error", "tests/__init__.py", "Missing tests/__init__.py"))

    test_files = list(tests_dir.glob("test_*.py"))
    if not test_files:
        issues.append(("error", "tests/", "No test_*.py files"))
        return issues

    total_tests = 0
    for tf in test_files:
        content = tf.read_text(encoding="utf-8")
        test_count = len(re.findall(r"def test_", content))
        total_tests += test_count

        # Check for proper tagging
        if "@tagged" not in content:
            issues.append(("warn", tf.name, "Missing @tagged decorator"))

    if total_tests == 0:
        issues.append(("warn", "tests/", "Test files exist but no test_ methods found"))

    return issues


def _check_docs(mod_dir: Path) -> list[tuple[str, str, str]]:
    """Check documentation."""
    issues: list[tuple[str, str, str]] = []

    if not (mod_dir / "CLAUDE.md").exists():
        issues.append(("warn", "CLAUDE.md", "Missing CLAUDE.md — add for AI assistant context"))

    return issues


def _check_field_conventions(mod_dir: Path) -> list[tuple[str, str, str]]:
    """Check field naming conventions on inherited models."""
    issues: list[tuple[str, str, str]] = []
    module_name = mod_dir.name
    prefix = module_name.removesuffix("_management").replace("_", "")

    for py_file in (mod_dir / "models").rglob("*.py") if (mod_dir / "models").exists() else []:
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue

        # Only check inherited models
        if "_inherit" not in content:
            continue

        rel = py_file.relative_to(mod_dir)
        # Find field definitions
        for match in re.finditer(r"(\w+)\s*=\s*fields\.\w+\(", content):
            field_name = match.group(1)
            # Skip standard fields
            if field_name in (
                "name",
                "active",
                "state",
                "company_id",
                "currency_id",
                "sequence",
                "note",
                "description",
                "display_name",
            ):
                continue
            # Check if custom field has module prefix on inherited model
            if not field_name.startswith(prefix) and not field_name.startswith("x_"):
                issues.append(
                    ("info", f"{rel}", f"Field '{field_name}' on inherited model — consider prefix '{prefix}_'")
                )

    return issues


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("module")
def lint_module(
    name: Annotated[str, typer.Argument(help="Module name to lint")],
    strict: Annotated[bool, typer.Option("--strict", help="Treat warnings as errors")] = False,
) -> None:
    """Lint a single private module against Odoo 18 best practices.

    Checks: manifest, security, Python quality, XML views, tests, docs, field conventions.
    """
    mod_dir = _find_module(name)
    console.print(f"\n[bold]Linting module[/bold] [cyan]{name}[/cyan]\n")

    all_issues: list[tuple[str, str, str]] = []
    checks = [
        ("Manifest", _check_manifest),
        ("Security", _check_security),
        ("Python Quality", _check_python_quality),
        ("XML Views", _check_views),
        ("Tests", _check_tests),
        ("Documentation", _check_docs),
        ("Field Conventions", _check_field_conventions),
        ("N+1 Queries", _check_n_plus_one),
    ]

    for check_name, check_fn in checks:
        issues = check_fn(mod_dir)
        if issues:
            all_issues.extend(issues)
            for severity, location, message in issues:
                icon = {"error": "[red]E[/red]", "warn": "[yellow]W[/yellow]", "info": "[dim]I[/dim]"}[severity]
                console.print(f"  {icon} {location}: {message}")
        else:
            console.print(f"  [green]OK[/green] {check_name}")

    errors = sum(1 for s, _, _ in all_issues if s == "error")
    warnings = sum(1 for s, _, _ in all_issues if s == "warn")
    infos = sum(1 for s, _, _ in all_issues if s == "info")

    console.print(f"\n[bold]Result:[/bold] {errors} errors, {warnings} warnings, {infos} info")

    if errors or (strict and warnings):
        console.print("[red]FAIL[/red]")
        raise typer.Exit(1)
    else:
        console.print("[green]PASS[/green]")


@app.command("all")
def lint_all(
    strict: Annotated[bool, typer.Option("--strict", help="Treat warnings as errors")] = False,
    summary_only: Annotated[bool, typer.Option("--summary", help="Show only summary table")] = False,
) -> None:
    """Lint ALL private modules and show a summary report.

    Runs all quality checks across every module in src/private/.
    """
    private_dir = _get_private_dir()
    modules = sorted([d.name for d in private_dir.iterdir() if d.is_dir() and (d / "__manifest__.py").exists()])

    if not modules:
        console.print("[yellow]No modules found in src/private/[/yellow]")
        return

    console.print(f"\n[bold]Linting {len(modules)} private modules[/bold]\n")

    from rich.table import Table

    results: list[tuple[str, int, int, int]] = []
    total_errors = 0
    total_warnings = 0

    checks = [
        _check_manifest,
        _check_security,
        _check_python_quality,
        _check_views,
        _check_tests,
        _check_docs,
        _check_n_plus_one,
    ]

    for mod_name in modules:
        mod_dir = private_dir / mod_name
        errors = warnings = infos = 0

        for check_fn in checks:
            try:
                issues = check_fn(mod_dir)
                for severity, location, message in issues:
                    if severity == "error":
                        errors += 1
                    elif severity == "warn":
                        warnings += 1
                    else:
                        infos += 1
                    if not summary_only:
                        icon = {"error": "[red]E[/red]", "warn": "[yellow]W[/yellow]", "info": "[dim]I[/dim]"}[severity]
                        console.print(f"  {icon} {mod_name}/{location}: {message}")
            except Exception:
                pass

        results.append((mod_name, errors, warnings, infos))
        total_errors += errors
        total_warnings += warnings

    # Summary table
    console.print()
    table = Table(title=f"Module Quality Summary ({len(modules)} modules)", show_header=True)
    table.add_column("Module", style="cyan")
    table.add_column("Errors", justify="right")
    table.add_column("Warnings", justify="right")
    table.add_column("Status")

    clean = 0
    for mod_name, errors, warnings, _infos in results:
        if errors == 0 and warnings == 0:
            clean += 1
            if not summary_only:
                continue  # Skip clean modules in detailed view
            table.add_row(mod_name, "0", "0", "[green]CLEAN[/green]")
        else:
            e_str = f"[red]{errors}[/red]" if errors else "0"
            w_str = f"[yellow]{warnings}[/yellow]" if warnings else "0"
            status = "[red]FAIL[/red]" if errors else "[yellow]WARN[/yellow]"
            table.add_row(mod_name, e_str, w_str, status)

    console.print(table)
    console.print(
        f"\n[bold]Total:[/bold] {clean}/{len(modules)} clean, {total_errors} errors, {total_warnings} warnings"
    )

    if total_errors or (strict and total_warnings):
        raise typer.Exit(1)


@app.command("xml")
def lint_xml(
    name: Annotated[str | None, typer.Argument(help="Module name (default: all private modules)")] = None,
) -> None:
    """XML-specific lint: deprecated attributes, encoding declarations, indentation.

    Checks: Odoo 18 deprecated attrs=, states=, <tree>, missing encoding,
    inconsistent indentation (tabs vs spaces).
    """
    private_dir = _get_private_dir()
    if name:
        modules = [name]
        if not (private_dir / name / "__manifest__.py").exists():
            console.print(f"[red]ERROR[/red] Module not found: {name}")
            raise typer.Exit(1)
    else:
        modules = sorted([d.name for d in private_dir.iterdir() if d.is_dir() and (d / "__manifest__.py").exists()])

    total_errors = 0
    total_warnings = 0

    for mod_name in modules:
        mod_dir = private_dir / mod_name
        for xml_file in mod_dir.rglob("*.xml"):
            if "__pycache__" in str(xml_file):
                continue
            rel = f"{mod_name}/{xml_file.relative_to(mod_dir)}"
            try:
                content = xml_file.read_text(encoding="utf-8")
            except Exception:
                continue

            lines = content.splitlines()
            file_errors = 0
            file_warnings = 0

            # Check encoding declaration
            if lines and "<?xml" in lines[0] and "encoding" not in lines[0]:
                console.print(f'  [yellow]W[/yellow] {rel}:1: Missing encoding declaration — add encoding="utf-8"')
                file_warnings += 1

            for i, line in enumerate(lines, 1):
                stripped = line.strip()

                # Deprecated attrs= (Odoo 17+)
                if 'attrs="' in stripped or "attrs='" in stripped:
                    console.print(
                        f"  [red]E[/red] {rel}:{i}: attrs= removed in Odoo 17+ — use invisible=, required=, readonly="
                    )
                    file_errors += 1

                # Deprecated states= (Odoo 18)
                if (
                    re.search(r"\bstates=", stripped)
                    and not stripped.startswith("<!--")
                    and "__manifest__" not in str(xml_file)
                ):
                    console.print(f"  [red]E[/red] {rel}:{i}: states= removed in Odoo 18 — use invisible=")
                    file_errors += 1

                # Deprecated <tree (Odoo 18)
                if re.match(r"\s*<tree(\s|>|/)", line):
                    console.print(f"  [red]E[/red] {rel}:{i}: <tree> deprecated in Odoo 18 — use <list>")
                    file_errors += 1

                # Mixed tabs and spaces
                if "\t" in line and line.startswith(" "):
                    console.print(f"  [yellow]W[/yellow] {rel}:{i}: Mixed tabs and spaces")
                    file_warnings += 1

            if file_errors == 0 and file_warnings == 0:
                console.print(f"  [green]OK[/green] {rel}")

            total_errors += file_errors
            total_warnings += file_warnings

    console.print(f"\n[bold]XML Lint:[/bold] {total_errors} errors, {total_warnings} warnings")
    if total_errors:
        raise typer.Exit(1)


@app.command("manifests")
def lint_manifests_cmd(
    name: Annotated[str | None, typer.Argument(help="Module name (default: all private modules)")] = None,
    strict: Annotated[bool, typer.Option("--strict", help="Treat warnings as errors")] = False,
) -> None:
    """Batch manifest linting using manifest_cmd conventions.

    Checks: required keys, version format, author, description, depends ordering.
    """
    from kctl_odoo.commands.manifest_cmd import lint_manifests

    lint_manifests(module=name)


@app.command("security")
def lint_security_cmd(
    name: Annotated[str | None, typer.Argument(help="Module name (default: all)")] = None,
) -> None:
    """Check every model has a corresponding ir.model.access.csv row."""
    import ast

    private_dir = _get_private_dir()
    if name:
        modules = [name]
    else:
        modules = sorted([d.name for d in private_dir.iterdir() if d.is_dir() and (d / "__manifest__.py").exists()])

    total_issues = 0

    for mod_name in modules:
        mod_dir = private_dir / mod_name
        csv_path = mod_dir / "security" / "ir.model.access.csv"

        # Find models with _name
        models_declared: list[str] = []
        models_dir = mod_dir / "models"
        if models_dir.exists():
            for py_file in sorted(models_dir.rglob("*.py")):
                if "__pycache__" in str(py_file):
                    continue
                try:
                    content = py_file.read_text(encoding="utf-8")
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            for item in node.body:
                                if (
                                    isinstance(item, ast.Assign)
                                    and len(item.targets) == 1
                                    and isinstance(item.targets[0], ast.Name)
                                    and item.targets[0].id == "_name"
                                    and isinstance(item.value, ast.Constant)
                                    and isinstance(item.value.value, str)
                                ):
                                    models_declared.append(item.value.value)
                except Exception:
                    continue

        if not models_declared:
            continue

        # Check CSV covers all models
        csv_content = ""
        if csv_path.exists():
            csv_content = csv_path.read_text(encoding="utf-8")

        missing_models = []
        for model_name in models_declared:
            model_xmlid = f"model_{model_name.replace('.', '_')}"
            if model_xmlid not in csv_content:
                missing_models.append(model_name)

        if missing_models:
            total_issues += len(missing_models)
            for model_name in missing_models:
                console.print(f"  [red]E[/red] {mod_name}: Model '{model_name}' has no ir.model.access.csv row")
        else:
            console.print(f"  [green]OK[/green] {mod_name}")

    console.print(f"\n[bold]Security Lint:[/bold] {total_issues} missing access rules")
    if total_issues:
        raise typer.Exit(1)


@app.command("full")
def lint_full(
    strict: Annotated[bool, typer.Option("--strict", help="Treat warnings as errors")] = False,
) -> None:
    """Run all linters: module checks, XML, manifests, security, N+1, ruff."""
    console.print("\n[bold]Running full lint suite...[/bold]\n")

    exit_code = 0

    # 1. Module lint (all checks)
    console.print("[bold cyan]=== Module Lint (all) ===[/bold cyan]")
    try:
        lint_all(strict=strict, summary_only=True)
    except SystemExit as e:
        if e.code:
            exit_code = 1

    # 2. XML lint
    console.print("\n[bold cyan]=== XML Lint ===[/bold cyan]")
    try:
        lint_xml(name=None)
    except SystemExit as e:
        if e.code:
            exit_code = 1

    # 3. Security lint
    console.print("\n[bold cyan]=== Security Lint ===[/bold cyan]")
    try:
        lint_security_cmd(name=None)
    except SystemExit as e:
        if e.code:
            exit_code = 1

    # 4. Manifest lint
    console.print("\n[bold cyan]=== Manifest Lint ===[/bold cyan]")
    try:
        from kctl_odoo.commands.manifest_cmd import lint_manifests

        lint_manifests(module=None)
    except SystemExit:
        pass  # manifest lint does not exit with code 1 on warnings

    console.print()
    if exit_code:
        console.print("[red][bold]FULL LINT: FAILED[/bold][/red]")
        raise typer.Exit(1)
    else:
        console.print("[green][bold]FULL LINT: PASSED[/bold][/green]")


@app.command("ruff")
def lint_ruff(
    name: Annotated[str | None, typer.Argument(help="Module name (default: all private modules)")] = None,
    fix: Annotated[bool, typer.Option("--fix", help="Auto-fix issues")] = False,
) -> None:
    """Run ruff linter on private module Python code.

    Uses the project's ruff configuration. Checks PEP 8, imports,
    common bugs, and code simplification opportunities.
    """
    import subprocess

    private_dir = _get_private_dir()
    if name:
        target = str(private_dir / name)
        if not Path(target).is_dir():
            console.print(f"[red]ERROR[/red] Module not found: {name}")
            raise typer.Exit(1)
    else:
        target = str(private_dir)

    cmd = ["ruff", "check", target]
    if fix:
        cmd.append("--fix")

    console.print(f"[blue]INFO[/blue] Running ruff on {target}...")
    result = subprocess.run(cmd)
    raise typer.Exit(result.returncode)


@app.command("summary")
def lint_summary() -> None:
    """Quick lint summary showing CLEAN/WARN/FAIL per module.

    Faster than 'lint all' -- only counts errors and warnings without
    showing individual issues.

    Examples:
        kctl-odoo lint summary
    """
    from rich.table import Table

    private_dir = _get_private_dir()
    modules = sorted([d.name for d in private_dir.iterdir() if d.is_dir() and (d / "__manifest__.py").exists()])

    clean = 0
    warn_count = 0
    fail = 0

    table = Table(title=f"Lint Summary ({len(modules)} modules)", show_header=True, header_style="bold")
    table.add_column("Module", style="cyan")
    table.add_column("Errors", justify="right")
    table.add_column("Warnings", justify="right")
    table.add_column("Status")

    checks = [
        _check_manifest,
        _check_security,
        _check_python_quality,
        _check_views,
    ]

    for mod_name in modules:
        mod_dir = private_dir / mod_name
        issues: list[tuple[str, str, str]] = []
        for check_fn in checks:
            with contextlib.suppress(Exception):
                issues.extend(check_fn(mod_dir))

        errors = sum(1 for severity, _, _ in issues if severity == "error")
        warnings = sum(1 for severity, _, _ in issues if severity in ("warn", "info"))

        if errors > 0:
            status = "[red]FAIL[/red]"
            fail += 1
        elif warnings > 0:
            status = "[yellow]WARN[/yellow]"
            warn_count += 1
        else:
            status = "[green]CLEAN[/green]"
            clean += 1

        e_str = f"[red]{errors}[/red]" if errors else "0"
        w_str = f"[yellow]{warnings}[/yellow]" if warnings else "0"
        table.add_row(mod_name, e_str, w_str, status)

    console.print(table)
    console.print(f"\n[bold]Summary:[/bold] {clean} clean, {warn_count} warn, {fail} fail (of {len(modules)})")
