"""Test runner commands."""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from kctl_odoo.core.local import LocalClient

app = typer.Typer(help="Run and manage Odoo tests.")
console = Console()


def _get_client() -> LocalClient:
    try:
        return LocalClient()
    except Exception:
        console.print(
            "[red]ERROR[/red] Not inside a Docker Compose project directory.\n"
            "  Run this command from the kodemeio-odoo root (where docker-compose.yml lives),\n"
            "  or any subdirectory within it."
        )
        raise typer.Exit(1) from None


# ---------------------------------------------------------------------------
# Test output parser
# ---------------------------------------------------------------------------


def _parse_test_output(output: str) -> dict:
    """Parse Odoo test output for results summary.

    Handles both the standard unittest runner output and Odoo's own test
    logging format (``odoo.modules.module: ... tested``).
    """
    results: dict = {
        "tests": 0,
        "errors": 0,
        "failures": 0,
        "passed": 0,
        "skipped": 0,
        "test_names": [],
        "failed_tests": [],
        "error_tests": [],
        "time_seconds": 0.0,
    }

    # Match "Ran X tests in Y.YYYs"
    ran_match = re.search(r"Ran (\d+) tests? in ([\d.]+)s", output)
    if ran_match:
        results["tests"] = int(ran_match.group(1))
        results["time_seconds"] = float(ran_match.group(2))

    # Match "FAILED (failures=N, errors=N)" — groups are optional
    failed_match = re.search(r"FAILED \((?:failures=(\d+))?(?:,\s*)?(?:errors=(\d+))?\)", output)
    if failed_match:
        results["failures"] = int(failed_match.group(1) or 0)
        results["errors"] = int(failed_match.group(2) or 0)

    # Match "OK (skipped=N)"
    skip_match = re.search(r"OK \(skipped=(\d+)\)", output)
    if skip_match:
        results["skipped"] = int(skip_match.group(1))

    # Match individual test result lines: "ERROR: test_name" / "FAIL: test_name" / "ok"
    for match in re.finditer(r"(ERROR|FAIL|ok):\s+(\S+)", output):
        status, name = match.groups()
        results["test_names"].append(name)
        if status == "FAIL":
            results["failed_tests"].append(name)
        elif status == "ERROR":
            results["error_tests"].append(name)

    # Also capture Odoo-style test lines: "odoo.tests ... test_something ... ok/FAIL/ERROR"
    for match in re.finditer(r"odoo\.tests[^:]*:\s+\S+\s+\((\S+)\)\s+\.\.\.\s+(ok|FAIL|ERROR)", output):
        name, status = match.groups()
        if name not in results["test_names"]:
            results["test_names"].append(name)
            if status == "FAIL":
                results["failed_tests"].append(name)
            elif status == "ERROR":
                results["error_tests"].append(name)

    results["passed"] = max(0, results["tests"] - results["failures"] - results["errors"] - results["skipped"])
    return results


def _print_summary(parsed: dict, module: str) -> None:
    """Print a rich summary table of test results."""
    table = Table(title=f"Test Results: {module}", show_header=True, header_style="bold")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    table.add_row("Total tests", str(parsed["tests"]))
    table.add_row(
        "Passed",
        f"[green]{parsed['passed']}[/green]" if parsed["passed"] else "0",
    )
    table.add_row(
        "Failures",
        f"[red]{parsed['failures']}[/red]" if parsed["failures"] else "0",
    )
    table.add_row(
        "Errors",
        f"[red]{parsed['errors']}[/red]" if parsed["errors"] else "0",
    )
    if parsed["skipped"]:
        table.add_row("Skipped", f"[yellow]{parsed['skipped']}[/yellow]")
    table.add_row("Time", f"{parsed['time_seconds']:.2f}s")

    console.print()
    console.print(table)

    # List failed/error tests if any
    if parsed["failed_tests"]:
        console.print("\n[red bold]Failed tests:[/red bold]")
        for name in parsed["failed_tests"]:
            console.print(f"  [red]FAIL[/red] {name}")

    if parsed["error_tests"]:
        console.print("\n[red bold]Error tests:[/red bold]")
        for name in parsed["error_tests"]:
            console.print(f"  [red]ERROR[/red] {name}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("run")
def run(
    module: Annotated[str, typer.Argument(help="Module to test (e.g. base_management)")],
    tags: Annotated[str | None, typer.Option("--tags", "-t", help="Test tag filter")] = None,
    database: Annotated[str | None, typer.Option("--database", "-d", help="Test database name")] = None,
    clean: Annotated[bool, typer.Option("--clean", help="Drop test database after run")] = False,
    summary: Annotated[bool, typer.Option("--summary/--no-summary", help="Show result summary table")] = True,
) -> None:
    """Run Odoo tests for a module.

    Executes tests inside the Docker container via docker compose exec.
    Output is streamed in real time, and a summary table is shown at the end.

    Examples:
        kctl-odoo test run base_management
        kctl-odoo test run sfa_management --tags fast --database test_sfa
        kctl-odoo test run payment_management --clean
        kctl-odoo test run base_management --no-summary
    """
    client = _get_client()

    console.print(f"[blue]INFO[/blue] Running tests for [bold]{module}[/bold]...")
    if tags:
        console.print(f"  Tags: {tags}")
    if database:
        console.print(f"  Database: {database}")
    if clean:
        console.print("  Clean: database will be dropped after run")

    # Build the docker compose exec command and run with real-time output + capture
    compose_cmd = client.compose_cmd() + ["exec", "-T", client.service, "test", module]
    if tags:
        compose_cmd.extend(["--tags", tags])
    if database:
        compose_cmd.extend(["-d", database])
    if clean:
        compose_cmd.append("--clean")

    collected_lines: list[str] = []
    returncode = 0

    try:
        proc = subprocess.Popen(
            compose_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(client.project_dir),
        )
        assert proc.stdout is not None  # noqa: S101

        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            collected_lines.append(line)

        proc.wait()
        returncode = proc.returncode
    except FileNotFoundError:
        console.print("[red]ERROR[/red] docker compose not found. Is Docker installed?")
        raise typer.Exit(1) from None

    # Show summary
    if summary and collected_lines:
        output = "".join(collected_lines)
        parsed = _parse_test_output(output)
        if parsed["tests"] > 0:
            _print_summary(parsed, module)

    # Final status line
    if returncode == 0:
        console.print(f"\n[green]OK[/green] Tests passed for {module}")
    else:
        console.print(f"\n[red]FAIL[/red] Tests failed for {module} (exit code {returncode})")

    raise typer.Exit(returncode)


def _find_test_classes(filepath: Path) -> list[str]:
    """Parse a Python file and return names of TestCase classes."""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []

    classes: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            classes.append(node.name)
    return classes


@app.command("list")
def list_(
    module: Annotated[str, typer.Argument(help="Module name to introspect")],
    directory: Annotated[str | None, typer.Option("--dir", help="Base directory for modules")] = None,
) -> None:
    """List test files and classes for a module.

    Introspects src/private/<module>/tests/ to find test files and
    parses them for TestCase class definitions.

    Examples:
        kctl-odoo test list base_management
        kctl-odoo test list sfa_management --dir /opt/odoo/addons
    """
    from kctl_odoo.core.utils import find_project_root

    base_dir = Path(directory) if directory else find_project_root() / "src" / "private"
    tests_dir = base_dir / module / "tests"

    if not tests_dir.exists():
        console.print(f"[yellow]WARN[/yellow] Tests directory not found: {tests_dir}")
        raise typer.Exit(1)

    test_files = sorted(tests_dir.glob("test_*.py"))
    if not test_files:
        console.print(f"[yellow]WARN[/yellow] No test files found in {tests_dir}")
        raise typer.Exit(0)

    from rich.tree import Tree

    tree = Tree(f"[bold]{module}[/bold] tests ({len(test_files)} files)")

    total_classes = 0
    for tf in test_files:
        classes = _find_test_classes(tf)
        total_classes += len(classes)
        label = f"[cyan]{tf.name}[/cyan]"
        if classes:
            label += f" [dim]({len(classes)} classes)[/dim]"
        branch = tree.add(label)
        for cls_name in classes:
            branch.add(f"[green]{cls_name}[/green]")

    console.print(tree)
    console.print(f"\n  {len(test_files)} files, {total_classes} test classes")


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


@app.command("profile")
def profile(
    name: Annotated[str, typer.Argument(help="Deployment profile name (e.g. manufacturing)")],
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory")] = None,
    stop_on_fail: Annotated[bool, typer.Option("--stop-on-fail", help="Abort on first test failure")] = False,
    tags: Annotated[str | None, typer.Option("--tags", "-t", help="Test tag filter")] = None,
    database: Annotated[str | None, typer.Option("--database", "-d", help="Test database name")] = None,
) -> None:
    """Run tests for all testable modules in a deployment profile.

    Resolves the profile to its module list, filters to modules that have
    a tests/ directory in src/private/, and runs each module's tests
    sequentially. Shows per-module pass/fail and an overall summary.

    Examples:
        kctl-odoo test profile manufacturing
        kctl-odoo test profile distribution --stop-on-fail
        kctl-odoo test profile foundation --tags fast
    """
    from kctl_odoo.core.bundles import (
        discover_profiles,
        get_default_install_dir,
        load_profile,
        resolve_profile_modules,
    )

    client = _get_client()
    install_dir = Path(dir_path) if dir_path else get_default_install_dir()

    if not install_dir.is_dir():
        console.print(f"[red]ERROR[/red] Install directory not found: {install_dir}")
        raise typer.Exit(1)

    # Find the profile file
    profile_path: Path | None = None
    for prefix in ("profile-", ""):
        for ext in (".yaml", ".yml"):
            p = install_dir / f"{prefix}{name}{ext}"
            if p.exists():
                profile_path = p
                break
        if profile_path:
            break

    if not profile_path:
        console.print(f"[red]ERROR[/red] Profile '{name}' not found in {install_dir}")
        available = discover_profiles(install_dir)
        if available:
            console.print(f"  Available: {', '.join(p.name for p in available)}")
        raise typer.Exit(1)

    prof = load_profile(profile_path)
    all_modules = resolve_profile_modules(prof, install_dir)

    if not all_modules:
        console.print(f"[yellow]WARN[/yellow] Profile '{name}' resolved to 0 modules")
        raise typer.Exit(0)

    # Filter to modules with tests/ directory in src/private/
    private_dir = client.project_dir / "src" / "private"
    testable: list[str] = []
    for mod in all_modules:
        tests_dir = private_dir / mod / "tests"
        if tests_dir.is_dir() and any(tests_dir.glob("test_*.py")):
            testable.append(mod)

    console.print(
        f"\n[bold]Profile '{name}'[/bold]: {len(all_modules)} modules total, "
        f"{len(testable)} testable (have tests/ in src/private/)\n"
    )

    if not testable:
        console.print("[yellow]WARN[/yellow] No testable modules found in this profile")
        raise typer.Exit(0)

    # Run tests for each module
    results: list[tuple[str, bool, str]] = []

    for i, mod in enumerate(testable, 1):
        console.print(f"[blue]({i}/{len(testable)})[/blue] Testing [bold]{mod}[/bold]...")

        compose_cmd = client.compose_cmd() + ["exec", "-T", client.service, "test", mod]
        if tags:
            compose_cmd.extend(["--tags", tags])
        if database:
            compose_cmd.extend(["-d", database])

        try:
            proc = subprocess.run(
                compose_cmd,
                capture_output=True,
                text=True,
                cwd=str(client.project_dir),
            )
            parsed = _parse_test_output(proc.stdout + proc.stderr)

            if proc.returncode == 0:
                detail = f"{parsed['tests']} tests, {parsed['time_seconds']:.1f}s"
                results.append((mod, True, detail))
                console.print(f"  [green]PASS[/green] {detail}")
            else:
                detail = f"{parsed['failures']} failures, {parsed['errors']} errors"
                results.append((mod, False, detail))
                console.print(f"  [red]FAIL[/red] {detail}")

                if stop_on_fail:
                    console.print("\n[red]Stopping on first failure (--stop-on-fail)[/red]")
                    break
        except FileNotFoundError:
            results.append((mod, False, "docker compose not found"))
            console.print("  [red]FAIL[/red] docker compose not found")
            break

    # Summary
    total = len(results)
    passed_count = sum(1 for _, ok, _ in results if ok)
    failed_count = total - passed_count

    console.print()
    table = Table(title=f"Profile '{name}' Test Summary", show_header=True, header_style="bold")
    table.add_column("Module", style="cyan")
    table.add_column("Status")
    table.add_column("Detail", style="dim")

    for mod, ok, detail in results:
        status = "[green]PASS[/green]" if ok else "[red]FAIL[/red]"
        table.add_row(mod, status, detail)

    console.print(table)
    console.print(
        f"\n[bold]Result: {passed_count}/{total} modules passed[/bold]"
        + (f" [red]({failed_count} failed)[/red]" if failed_count else " [green](all passed)[/green]")
    )

    if failed_count:
        raise typer.Exit(1)


@app.command("coverage")
def test_coverage(
    module: Annotated[str, typer.Argument(help="Module name")],
    database: Annotated[str | None, typer.Option("--database", "-d", help="Database")] = None,
) -> None:
    """Run tests with coverage measurement for a module.

    Runs Odoo tests and counts test functions as a proxy for coverage.
    True line-level coverage requires pytest-cov inside the container.

    Examples:
        kctl-odoo test coverage base_management
        kctl-odoo test coverage sfa_management -d odoo_sfa
    """
    from pathlib import Path

    private_dir = Path.cwd() / "src" / "private"
    mod_dir = private_dir / module
    tests_dir = mod_dir / "tests"

    if not tests_dir.exists():
        console.print(f"[red]No tests directory for {module}[/red]")
        raise typer.Exit(1)

    # Count models
    models_dir = mod_dir / "models"
    model_count = 0
    if models_dir.exists():
        for py_file in models_dir.rglob("*.py"):
            if "__pycache__" not in str(py_file):
                content = py_file.read_text(errors="ignore")
                model_count += len(re.findall(r"_name\s*=", content))

    # Count routers
    controllers_dir = mod_dir / "controllers"
    router_count = len(list(controllers_dir.glob("*_router.py"))) if controllers_dir.exists() else 0

    # Count tests
    test_files = list(tests_dir.glob("test_*.py"))
    test_count = 0
    for tf in test_files:
        test_count += len(re.findall(r"def test_", tf.read_text(errors="ignore")))

    console.print(f"\n[bold]{module}[/bold] coverage summary:")
    console.print(f"  Models: {model_count}")
    console.print(f"  Routers: {router_count}")
    console.print(f"  Test files: {len(test_files)}")
    console.print(f"  Test functions: {test_count}")

    ratio = test_count / max(model_count + router_count, 1)
    if ratio >= 1.0:
        console.print(f"  Coverage ratio: [green]{ratio:.1f}x[/green] (good)")
    elif ratio >= 0.5:
        console.print(f"  Coverage ratio: [yellow]{ratio:.1f}x[/yellow] (acceptable)")
    else:
        console.print(f"  Coverage ratio: [red]{ratio:.1f}x[/red] (needs more tests)")
