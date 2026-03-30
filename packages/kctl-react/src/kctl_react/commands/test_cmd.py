"""Test commands with deep Vitest integration."""

from __future__ import annotations

import contextlib
import json
import signal
import subprocess
from pathlib import Path
from typing import Annotated

import typer

from kctl_react.core.callbacks import AppContext
from kctl_react.core.runner import run, run_turbo

app = typer.Typer(help="Run tests across the monorepo.")

_SUBCOMMANDS = {"count", "summary", "coverage", "naming", "threshold", "snapshots"}


def _parse_vitest_json(json_path: Path) -> dict | None:
    """Parse vitest JSON reporter output."""
    if not json_path.exists():
        return None
    try:
        return json.loads(json_path.read_text())
    except Exception:
        return None


def _run_vitest_json(app_dir: Path, timeout: int = 300) -> dict | None:
    """Run vitest with JSON reporter and return parsed results."""
    json_output = app_dir / ".vitest-results.json"
    json_output.unlink(missing_ok=True)

    with contextlib.suppress(Exception):
        run(
            ["pnpm", "vitest", "run", "--reporter=json", f"--outputFile={json_output}"],
            cwd=app_dir,
            capture=True,
            timeout=timeout,
        )

    return _parse_vitest_json(json_output)


@app.callback(invoke_without_command=True)
def test(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Option("--app", "-a", help="App name (omit for all apps)")] = None,
    coverage_flag: Annotated[bool, typer.Option("--coverage", "-c", help="Run with coverage.")] = False,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Run in watch mode.")] = False,
) -> None:
    """Run vitest for app(s).

    Examples:
      kctl-react test --app sfa             # Test SFA
      kctl-react test --coverage            # All apps with coverage
      kctl-react test --app sfa --watch     # Watch mode for SFA
    """
    if ctx.invoked_subcommand is not None:
        return

    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    if app_name:
        actx.validate_app(app_name)

    if watch and not app_name:
        out.warn("--watch requires an app name (e.g. kctl-react test sfa --watch)")
        raise typer.Exit(1) from None

    task = "test:ci" if coverage_flag else "test"
    target = app_name or "all apps"
    out.info(f"Running tests for {target}{'  (coverage)' if coverage_flag else ''}...")

    if watch and app_name:
        app_dir = root / "apps" / app_name
        try:
            proc = subprocess.Popen(["pnpm", "vitest", "--watch"], cwd=app_dir)
            proc.wait()
        except KeyboardInterrupt:
            proc.send_signal(signal.SIGINT)
            proc.wait()
        return

    try:
        run_turbo(task, root, filter_app=app_name, capture=False, timeout=600)
        out.success(f"Tests passed: {target}")
    except Exception as e:
        out.error(f"Tests failed: {e}")
        raise typer.Exit(1) from None


@app.command()
def count(ctx: typer.Context) -> None:
    """Count test files per app."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    rows: list[list[str]] = []
    json_data: list[dict] = []
    total = 0

    for name in actx.app_names:
        app_dir = root / "apps" / name / "src"
        if not app_dir.is_dir():
            rows.append([name, "0", "[dim]no src[/dim]"])
            continue

        test_files = list(app_dir.rglob("*.test.ts")) + list(app_dir.rglob("*.test.tsx"))
        file_count = len(test_files)
        total += file_count

        rows.append([name, str(file_count), "[green]OK[/green]" if file_count > 0 else "[yellow]no tests[/yellow]"])
        json_data.append({"app": name, "test_files": file_count})

    rows.append(["[bold]Total[/bold]", f"[bold]{total}[/bold]", ""])

    out.table(
        "Test Files",
        [("App", "cyan"), ("Files", "green"), ("Status", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def summary(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (omit for all)")] = None,
) -> None:
    """Run tests with JSON reporter and show parsed summary.

    Shows pass/fail/skip counts per app by parsing vitest JSON output.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    if app_name:
        actx.validate_app(app_name)

    apps = [app_name] if app_name else actx.app_names

    rows: list[list[str]] = []
    json_data: list[dict] = []
    total_passed = 0
    total_failed = 0
    total_skipped = 0

    for name in apps:
        app_dir = root / "apps" / name
        if not (app_dir / "src").is_dir():
            continue

        out.info(f"Testing {name}...")
        results = _run_vitest_json(app_dir)

        if results is None:
            rows.append([name, "[dim]--[/dim]", "[dim]--[/dim]", "[dim]--[/dim]", "[yellow]no output[/yellow]"])
            json_data.append({"app": name, "passed": 0, "failed": 0, "skipped": 0, "error": True})
            continue

        passed = results.get("numPassedTests", 0)
        failed = results.get("numFailedTests", 0)
        skipped = results.get("numPendingTests", 0)
        total_passed += passed
        total_failed += failed
        total_skipped += skipped

        status = "[green]PASS[/green]" if failed == 0 else "[red]FAIL[/red]"
        rows.append(
            [
                name,
                f"[green]{passed}[/green]",
                f"[red]{failed}[/red]" if failed else "[dim]0[/dim]",
                f"[yellow]{skipped}[/yellow]" if skipped else "[dim]0[/dim]",
                status,
            ]
        )
        json_data.append({"app": name, "passed": passed, "failed": failed, "skipped": skipped})

        # Show failure details
        if failed > 0:
            for suite in results.get("testResults", []):
                for test_case in suite.get("assertionResults", []):
                    if test_case.get("status") == "failed":
                        test_name = " > ".join(test_case.get("ancestorTitles", []) + [test_case.get("title", "")])
                        out.error(f"  {name}: {test_name}")

    rows.append(
        [
            "[bold]Total[/bold]",
            f"[bold green]{total_passed}[/bold green]",
            f"[bold red]{total_failed}[/bold red]" if total_failed else "[bold dim]0[/bold dim]",
            f"[bold yellow]{total_skipped}[/bold yellow]" if total_skipped else "[bold dim]0[/bold dim]",
            "",
        ]
    )

    out.table(
        "Test Summary",
        [("App", "cyan"), ("Passed", "green"), ("Failed", "red"), ("Skipped", "yellow"), ("Status", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def coverage(ctx: typer.Context) -> None:
    """Show aggregated test coverage across all apps.

    Reads coverage-summary.json from each app's coverage/ directory.
    Run `kctl-react test --coverage` first to generate coverage data.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for name in actx.app_names:
        cov_file = root / "apps" / name / "coverage" / "coverage-summary.json"
        if not cov_file.exists():
            rows.append(
                [name, "[dim]--[/dim]", "[dim]--[/dim]", "[dim]--[/dim]", "[dim]--[/dim]", "[dim]no data[/dim]"]
            )
            json_data.append({"app": name, "lines": None, "branches": None, "functions": None, "statements": None})
            continue

        try:
            data = json.loads(cov_file.read_text())
            total = data.get("total", {})
            lines = total.get("lines", {}).get("pct", 0)
            branches = total.get("branches", {}).get("pct", 0)
            functions = total.get("functions", {}).get("pct", 0)
            statements = total.get("statements", {}).get("pct", 0)

            def _color_pct(pct: float) -> str:
                if pct >= 80:
                    return f"[green]{pct:.1f}%[/green]"
                elif pct >= 60:
                    return f"[yellow]{pct:.1f}%[/yellow]"
                return f"[red]{pct:.1f}%[/red]"

            rows.append(
                [name, _color_pct(lines), _color_pct(branches), _color_pct(functions), _color_pct(statements), ""]
            )
            json_data.append(
                {"app": name, "lines": lines, "branches": branches, "functions": functions, "statements": statements}
            )
        except Exception:
            rows.append([name, "[red]error[/red]", "", "", "", ""])
            json_data.append({"app": name, "error": True})

    out.table(
        "Test Coverage",
        [("App", "cyan"), ("Lines", ""), ("Branches", ""), ("Functions", ""), ("Stmts", ""), ("", "")],
        rows,
        data_for_json=json_data,
    )
    out.info("Run `kctl-react test --coverage` first to generate coverage data")


@app.command()
def naming(ctx: typer.Context) -> None:
    """Check test file naming conventions across all apps.

    Flags .spec.* files as wrong convention — all tests should use .test.* suffix.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    rows: list[list[str]] = []
    json_data: list[dict] = []
    issues: list[str] = []

    for name in actx.app_names:
        src_dir = root / "apps" / name / "src"
        if not src_dir.is_dir():
            rows.append([name, "[dim]--[/dim]", "[dim]--[/dim]", "[dim]no src[/dim]"])
            json_data.append({"app": name, "test_count": 0, "spec_count": 0})
            continue

        test_files = list(src_dir.rglob("*.test.ts")) + list(src_dir.rglob("*.test.tsx"))
        spec_files = list(src_dir.rglob("*.spec.ts")) + list(src_dir.rglob("*.spec.tsx"))

        test_count = len(test_files)
        spec_count = len(spec_files)

        for sf in spec_files:
            issues.append(f"  {name}: {sf.relative_to(root)} (rename to .test{sf.suffix})")

        status = "[green]OK[/green]" if spec_count == 0 else f"[red]{spec_count} wrong[/red]"
        rows.append([name, str(test_count), str(spec_count), status])
        json_data.append({"app": name, "test_count": test_count, "spec_count": spec_count})

    out.table(
        "Test File Naming Conventions",
        [("App", "cyan"), (".test.*", "green"), (".spec.*", "red"), ("Status", "")],
        rows,
        data_for_json=json_data,
    )

    if issues:
        out.warn("Wrong convention (.spec should be .test):")
        for issue in issues:
            out.info(issue)
    else:
        out.success("All test files follow .test.* naming convention")


@app.command()
def threshold(
    ctx: typer.Context,
    min_pct: Annotated[int, typer.Option("--min", help="Minimum line coverage percentage.")] = 70,
) -> None:
    """Enforce minimum coverage threshold across all apps.

    Reads coverage-summary.json from each app's coverage/ directory.
    Exits 1 if any app is below the threshold.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    rows: list[list[str]] = []
    json_data: list[dict] = []
    any_fail = False

    for name in actx.app_names:
        cov_file = root / "apps" / name / "coverage" / "coverage-summary.json"
        if not cov_file.exists():
            rows.append([name, "[dim]no data[/dim]", f"{min_pct}%", "[dim]SKIP[/dim]"])
            json_data.append({"app": name, "lines_pct": None, "min_pct": min_pct, "status": "skip"})
            continue

        try:
            data = json.loads(cov_file.read_text())
            lines_pct = data.get("total", {}).get("lines", {}).get("pct", 0)
            passed = lines_pct >= min_pct
            if not passed:
                any_fail = True

            status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
            color = "green" if passed else "red"
            rows.append([name, f"[{color}]{lines_pct:.1f}%[/{color}]", f"{min_pct}%", status])
            json_data.append(
                {"app": name, "lines_pct": lines_pct, "min_pct": min_pct, "status": "pass" if passed else "fail"}
            )
        except Exception:
            rows.append([name, "[red]error[/red]", f"{min_pct}%", "[red]ERROR[/red]"])
            json_data.append({"app": name, "lines_pct": None, "min_pct": min_pct, "status": "error"})
            any_fail = True

    out.table(
        f"Coverage Threshold (min {min_pct}%)",
        [("App", "cyan"), ("Lines %", ""), ("Min %", ""), ("Status", "")],
        rows,
        data_for_json=json_data,
    )

    if any_fail:
        out.error("One or more apps are below the coverage threshold")
        raise typer.Exit(1) from None


@app.command()
def snapshots(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name to inspect snapshots for")],
) -> None:
    """List vitest snapshot files for an app.

    Shows all .snap files in the app's src/ directory with their sizes.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)

    src_dir = root / "apps" / app_name / "src"
    if not src_dir.is_dir():
        out.warn(f"No src/ directory found for {app_name}")
        return

    snap_files = sorted(src_dir.rglob("*.snap"))

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for snap in snap_files:
        size = snap.stat().st_size
        size_str = f"{size / 1024:.1f} KB" if size >= 1024 else f"{size} B"
        rel_path = str(snap.relative_to(root))
        rows.append([rel_path, size_str])
        json_data.append({"file": rel_path, "size_bytes": size})

    if not snap_files:
        out.info(f"No snapshot files found in {app_name}/src/")
    else:
        out.table(
            f"Snapshot Files: {app_name}",
            [("File", "cyan"), ("Size", "")],
            rows,
            data_for_json=json_data,
        )

    out.info(f"To update snapshots: pnpm --filter @kodemeio/{app_name} vitest run --update-snapshots")
