"""Lint and type-check commands."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated

import typer

from kctl_react.core.analyzers import read_tsconfig_strict
from kctl_react.core.callbacks import AppContext
from kctl_react.core.exceptions import CommandError
from kctl_react.core.runner import run, run_turbo

app = typer.Typer(help="Lint, type-check, and format code.")

_SUBCOMMANDS = {"format", "strict-check", "tsconfig-audit", "conventions"}


# ---------------------------------------------------------------------------
# Core logic functions (shared by callback dispatch and @app.command stubs)
# ---------------------------------------------------------------------------


def _run_strict_check(actx: AppContext) -> None:
    """Check that every app has strict: true in its tsconfig.json."""
    out = actx.output
    root = actx.project_root

    rows: list[list[str]] = []
    json_data: list[dict[str, str]] = []
    any_not_strict = False

    for app_name in actx.app_names:
        app_dir = root / "apps" / app_name
        is_strict = read_tsconfig_strict(app_dir)
        status = "strict" if is_strict else "[red]NOT strict[/red]"
        rows.append([app_name, status])
        json_data.append({"app": app_name, "strict": str(is_strict).lower()})
        if not is_strict:
            any_not_strict = True

    out.table(
        "TypeScript Strict Mode",
        [("App", "cyan"), ("Status", "green")],
        rows,
        data_for_json=json_data,
    )

    if any_not_strict:
        out.error("Some apps are missing strict: true in tsconfig.json")
        raise typer.Exit(1) from None

    out.success("All apps have strict: true")


def _run_tsconfig_audit(actx: AppContext) -> None:
    """Audit tsconfig.json settings for strict and jsx across all apps."""
    out = actx.output
    root = actx.project_root

    rows: list[list[str]] = []
    json_data: list[dict[str, str]] = []
    any_issues = False

    for app_name in actx.app_names:
        app_dir = root / "apps" / app_name
        tsconfig_path = app_dir / "tsconfig.json"

        if not tsconfig_path.exists():
            rows.append([app_name, "[red]MISSING[/red]", "tsconfig.json not found"])
            json_data.append({"app": app_name, "status": "MISSING", "issues": "tsconfig.json not found"})
            any_issues = True
            continue

        try:
            text = tsconfig_path.read_text()
            # Strip single-line // comments (tsconfig allows them)
            text = re.sub(r"//.*", "", text)
            data = json.loads(text)
        except (json.JSONDecodeError, OSError) as exc:
            rows.append([app_name, "[red]INVALID[/red]", f"Parse error: {exc}"])
            json_data.append({"app": app_name, "status": "INVALID", "issues": f"Parse error: {exc}"})
            any_issues = True
            continue

        compiler_opts = data.get("compilerOptions", {})
        issues: list[str] = []

        if not compiler_opts.get("strict", False):
            issues.append("strict: true missing")
        if compiler_opts.get("jsx") != "react-jsx":
            issues.append(f'jsx: expected "react-jsx", got {compiler_opts.get("jsx")!r}')

        if issues:
            issues_str = "; ".join(issues)
            rows.append([app_name, "[yellow]ISSUES[/yellow]", issues_str])
            json_data.append({"app": app_name, "status": "ISSUES", "issues": issues_str})
            any_issues = True
        else:
            rows.append([app_name, "[green]OK[/green]", ""])
            json_data.append({"app": app_name, "status": "OK", "issues": ""})

    out.table(
        "tsconfig.json Audit",
        [("App", "cyan"), ("Status", "green"), ("Issues", "yellow")],
        rows,
        data_for_json=json_data,
    )

    if any_issues:
        out.error("Some apps have tsconfig.json issues")
        raise typer.Exit(1) from None

    out.success("All apps have consistent tsconfig.json settings")


def _run_conventions(actx: AppContext, app_name: str) -> None:
    """Check a single app for convention violations."""
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)

    src_dir = root / "apps" / app_name / "src"

    rows: list[list[str]] = []
    json_data: list[dict[str, str]] = []

    _SKIP_DIRS = {"generated", "node_modules"}

    def _iter_ts_files(base: Path) -> list[Path]:
        files: list[Path] = []
        for p in base.rglob("*.ts"):
            if not any(part in _SKIP_DIRS for part in p.parts):
                files.append(p)
        for p in base.rglob("*.tsx"):
            if not any(part in _SKIP_DIRS for part in p.parts):
                files.append(p)
        return files

    if src_dir.is_dir():
        for file_path in _iter_ts_files(src_dir):
            try:
                lines = file_path.read_text().splitlines()
            except OSError:
                continue
            rel = str(file_path.relative_to(root / "apps" / app_name))
            for line_num, line in enumerate(lines, start=1):
                if '"use client"' in line or "'use client'" in line:
                    rows.append([rel, str(line_num), "use client directive", line.strip()])
                    json_data.append(
                        {"file": rel, "line": str(line_num), "issue": "use client directive", "code": line.strip()}
                    )
                if re.search(r'from\s+["\'](\.\./){2,}', line):
                    rows.append([rel, str(line_num), "deep relative import", line.strip()])
                    json_data.append(
                        {"file": rel, "line": str(line_num), "issue": "deep relative import", "code": line.strip()}
                    )

    if rows:
        out.table(
            f"Convention Issues: {app_name}",
            [("File", "cyan"), ("Line", "yellow"), ("Issue", "red"), ("Code", "dim")],
            rows,
            data_for_json=json_data,
        )
        out.error(f"{len(rows)} convention issue(s) found in {app_name}")
        raise typer.Exit(1) from None

    out.success(f"No convention issues found in {app_name}")


# ---------------------------------------------------------------------------
# Typer commands
# ---------------------------------------------------------------------------


@app.callback(invoke_without_command=True)
def lint(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Option("--app", "-a", help="App name to lint (omit for all apps)")] = None,
    fix: Annotated[bool, typer.Option("--fix", "-f", help="Auto-fix issues.")] = False,
) -> None:
    """Run ESLint + TypeScript type-check.

    Examples:
      kctl-react lint              # Lint all apps
      kctl-react lint --app sfa   # Lint SFA only
      kctl-react lint --app sfa --fix
      kctl-react lint strict-check
      kctl-react lint tsconfig-audit
      kctl-react lint conventions sfa
    """
    if ctx.invoked_subcommand is not None:
        return

    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    if app_name:
        actx.validate_app(app_name)

    target = app_name or "all apps"
    failed = False

    # ESLint
    out.info(f"Running ESLint on {target}...")
    try:
        run_turbo("lint", root, filter_app=app_name, capture=False, timeout=300)
        out.success("ESLint passed")
    except CommandError:
        out.error("ESLint failed")
        failed = True
    except Exception as e:
        out.error(f"ESLint error: {e}")
        failed = True

    # TypeScript type-check
    out.info(f"Running type-check on {target}...")
    try:
        run_turbo("type-check", root, filter_app=app_name, capture=False, timeout=300)
        out.success("Type-check passed")
    except CommandError:
        out.error("Type-check failed")
        failed = True
    except Exception as e:
        out.error(f"Type-check error: {e}")
        failed = True

    if failed:
        raise typer.Exit(1) from None

    out.success(f"All quality checks passed: {target}")


@app.command()
def format(
    ctx: typer.Context,
    check: Annotated[bool, typer.Option("--check", help="Check only, don't fix.")] = False,
) -> None:
    """Run Prettier on the codebase."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    if check:
        out.info("Checking formatting...")
        cmd = ["pnpm", "format-check"]
    else:
        out.info("Formatting code...")
        cmd = ["pnpm", "format"]

    try:
        run(cmd, cwd=root, capture=False, timeout=120)
        out.success("Formatting OK")
    except CommandError:
        out.error("Formatting issues found")
        raise typer.Exit(1) from None


@app.command("strict-check")
def strict_check(ctx: typer.Context) -> None:
    """Verify all apps have TypeScript strict mode enabled.

    Examples:
      kctl-react lint strict-check
      kctl-react --json lint strict-check
    """
    actx: AppContext = ctx.obj
    _run_strict_check(actx)


@app.command("tsconfig-audit")
def tsconfig_audit(ctx: typer.Context) -> None:
    """Audit tsconfig.json settings for consistency across all apps.

    Checks that each app has strict: true and jsx: react-jsx.

    Examples:
      kctl-react lint tsconfig-audit
    """
    actx: AppContext = ctx.obj
    _run_tsconfig_audit(actx)


@app.command()
def conventions(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name to check")],
) -> None:
    """Check project conventions for an app.

    Scans .ts/.tsx files for anti-patterns:
      - 'use client' directive (Next.js pattern, wrong for Vite)
      - Deep relative imports (../../) — should use @/ alias

    Examples:
      kctl-react lint conventions sfa
    """
    actx: AppContext = ctx.obj
    _run_conventions(actx, app_name)
