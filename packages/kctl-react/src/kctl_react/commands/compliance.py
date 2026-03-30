"""Compliance audit, fix, prompt, api-check, and api-health commands."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import typer

from kctl_react.core.callbacks import AppContext
from kctl_react.core.compliance.engine import ComplianceEngine
from kctl_react.core.compliance.fixes import apply_fixes
from kctl_react.core.compliance.models import AppReport, CategoryResult

logger = logging.getLogger(__name__)

app = typer.Typer(help="Audit app compliance, auto-fix violations, and generate fix prompts.")


def _parse_categories(categories: str | None) -> list[str] | None:
    """Parse comma-separated category string into list, or None."""
    if not categories:
        return None
    return [c.strip() for c in categories.split(",") if c.strip()]


def _grade_color(grade: str) -> str:
    """Return Rich color tag for a grade."""
    if grade in ("A+", "A"):
        return "green"
    if grade == "B":
        return "yellow"
    return "red"


def _audit_single(actx: AppContext, report: AppReport) -> None:
    """Print detailed single-app audit report."""
    out = actx.output

    if actx.json_mode:
        out.raw_json(report.to_dict())
        return

    color = _grade_color(report.grade)
    pct = int(report.total_score / report.max_score * 100) if report.max_score > 0 else 100

    out.text("")
    out.text(f"  Compliance Report: {report.app} ([{color}]{report.grade}[/{color}])")
    out.text(f"  Score: {pct}% ({report.total_score}/{report.max_score})")
    out.text("")

    # Category summary
    for cat in report.categories:
        if cat.violations:
            vcount = len(cat.violations)
            out.text(
                f"  [yellow]![/yellow] {cat.label:<20s} {cat.score}/{cat.max_points}  ({vcount} violation{'s' if vcount != 1 else ''})"
            )
        else:
            out.text(f"  [green]\u2713[/green] {cat.label:<20s} {cat.score}/{cat.max_points}")

    # Violations detail
    if report.total_violations > 0:
        out.text("")
        out.text(f"  Violations ({report.total_violations}):")

        # Group by category
        for cat in report.categories:
            if not cat.violations:
                continue
            out.text("")
            out.text(f"  {cat.label} ({len(cat.violations)}):")
            for v in cat.violations:
                loc = f":{v.line}" if v.line else ""
                out.text(f"    [yellow]![/yellow]  {v.file}{loc}       {v.message}")

        out.text("")
        out.text(f"  Auto-fixable: {report.auto_fixable_count}    Needs review: {report.needs_review_count}")
        out.text("")
        out.text(f"  Run: kctl-react compliance fix {report.app} --dry-run")
        out.text(f"  Run: kctl-react compliance prompt {report.app} -o fix-{report.app}.md")
    else:
        out.text("")
        out.success("No violations found!")


def _audit_all(actx: AppContext, reports: list[AppReport]) -> None:
    """Print scorecard table for all apps."""
    out = actx.output

    if actx.json_mode:
        out.raw_json([r.to_dict() for r in reports])
        return

    # Build table
    # Collect all category names from the first report (all should be the same)
    cat_names: list[str] = []
    if reports:
        cat_names = [c.name for c in reports[0].categories]

    columns: list[tuple[str, str]] = [
        ("App", "cyan"),
        ("Score", "green"),
        ("Grade", "yellow"),
    ]
    for cn in cat_names:
        columns.append((cn[:6], "dim"))

    rows: list[list[str]] = []
    json_data: list[dict] = []
    for r in reports:
        color = _grade_color(r.grade)
        pct = int(r.total_score / r.max_score * 100) if r.max_score > 0 else 100
        row: list[str] = [
            r.app,
            f"{pct}%",
            f"[{color}]{r.grade}[/{color}]",
        ]
        for cat in r.categories:
            row.append(f"{cat.score}/{cat.max_points}")
        rows.append(row)
        json_data.append(r.to_dict())

    out.table("Compliance Scorecard", columns, rows, data_for_json=json_data)


@app.command()
def audit(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name to audit")] = None,
    all_apps: Annotated[bool, typer.Option("--all", help="Audit all apps")] = False,
    min_score: Annotated[
        int | None, typer.Option("--min-score", help="Minimum passing score (percentage 0-100)")
    ] = None,
    categories: Annotated[
        str | None, typer.Option("--categories", "-c", help="Comma-separated category filter")
    ] = None,
) -> None:
    """Run compliance audit on one or all apps.

    Examples:
      kctl-react compliance audit sfa
      kctl-react compliance audit --all
      kctl-react compliance audit sfa --min-score 80
      kctl-react compliance audit sfa --categories structure,imports
      kctl-react --json compliance audit --all
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    if not app_name and not all_apps:
        out.error("Specify an app name or use --all")
        raise typer.Exit(1) from None

    cat_list = _parse_categories(categories)
    engine = ComplianceEngine()

    if all_apps:
        reports: list[AppReport] = []
        for name in actx.app_names:
            app_path = root / "apps" / name
            report = engine.audit(app_path, name, categories=cat_list)
            reports.append(report)

        _audit_all(actx, reports)

        if min_score is not None:
            any_below = False
            for r in reports:
                pct = int(r.total_score / r.max_score * 100) if r.max_score > 0 else 100
                if pct < min_score:
                    out.error(f"{r.app} scored {pct}% (below {min_score}%)")
                    any_below = True
            if any_below:
                raise typer.Exit(1) from None
    else:
        assert app_name is not None
        actx.validate_app(app_name)
        app_path = root / "apps" / app_name
        report = engine.audit(app_path, app_name, categories=cat_list)
        _audit_single(actx, report)

        if min_score is not None:
            pct = int(report.total_score / report.max_score * 100) if report.max_score > 0 else 100
            if pct < min_score:
                out.error(f"{report.app} scored {pct}% (below {min_score}%)")
                raise typer.Exit(1) from None


@app.command()
def fix(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name to fix")] = None,
    all_apps: Annotated[bool, typer.Option("--all", help="Fix all apps")] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show what would be fixed without modifying files")
    ] = False,
    categories: Annotated[
        str | None, typer.Option("--categories", "-c", help="Comma-separated category filter")
    ] = None,
) -> None:
    """Apply auto-fixes for compliance violations.

    Examples:
      kctl-react compliance fix sfa
      kctl-react compliance fix sfa --dry-run
      kctl-react compliance fix --all
      kctl-react compliance fix sfa --categories structure,i18n
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    if not app_name and not all_apps:
        out.error("Specify an app name or use --all")
        raise typer.Exit(1) from None

    cat_list = _parse_categories(categories)
    engine = ComplianceEngine()

    names = actx.app_names if all_apps else [app_name]  # type: ignore[list-item]
    for name in names:
        if not all_apps:
            actx.validate_app(name)
        app_path = root / "apps" / name

        prefix = "(dry-run) " if dry_run else ""
        count = apply_fixes(app_path, name, dry_run=dry_run, categories=cat_list)
        out.info(f"{prefix}{name}: {count} fix{'es' if count != 1 else ''} applied")

        # Re-audit to show remaining issues
        report = engine.audit(app_path, name, categories=cat_list)
        remaining = report.needs_review_count
        if remaining > 0:
            out.text(f"  Remaining issues needing review: {remaining}")
        else:
            out.success(f"  {name}: all clear!")


@app.command()
def prompt(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name to generate prompt for")] = None,
    all_apps: Annotated[bool, typer.Option("--all", help="Generate prompts for all apps")] = False,
    output_file: Annotated[
        str | None, typer.Option("-o", "--output", help="Output file path (directory if --all)")
    ] = None,
    categories: Annotated[
        str | None, typer.Option("--categories", "-c", help="Comma-separated category filter")
    ] = None,
) -> None:
    """Generate markdown fix prompts for AI or human review.

    Examples:
      kctl-react compliance prompt sfa
      kctl-react compliance prompt sfa -o fix-sfa.md
      kctl-react compliance prompt --all -o fix-prompts/
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    if not app_name and not all_apps:
        out.error("Specify an app name or use --all")
        raise typer.Exit(1) from None

    cat_list = _parse_categories(categories)
    engine = ComplianceEngine()

    if all_apps:
        for name in actx.app_names:
            app_path = root / "apps" / name
            report = engine.audit(app_path, name, categories=cat_list)
            md = engine.generate_prompt(report)

            if output_file:
                out_dir = Path(output_file)
                out_dir.mkdir(parents=True, exist_ok=True)
                dest = out_dir / f"fix-{name}.md"
                dest.write_text(md)
                out.info(f"Saved: {dest}")
            else:
                out.text(md)
    else:
        assert app_name is not None
        actx.validate_app(app_name)
        app_path = root / "apps" / app_name
        report = engine.audit(app_path, app_name, categories=cat_list)
        md = engine.generate_prompt(report)

        if output_file:
            dest = Path(output_file)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(md)
            out.info(f"Saved: {dest}")
        else:
            out.text(md)


# ---------------------------------------------------------------------------
# Helpers for api-check / api-health
# ---------------------------------------------------------------------------


def _read_env_var(app_path: Path, var_name: str) -> str | None:
    """Read a single variable from the app's .env file."""
    env_file = app_path / ".env"
    if not env_file.is_file():
        return None
    for line in env_file.read_text().splitlines():
        if line.startswith(f"{var_name}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _run_api_check_for_app(
    app_path: Path,
    app_name: str,
    *,
    offline: bool,
    cat_list: list[str] | None,
) -> AppReport | None:
    """Run api-check checkers for a single app, returning AppReport or None if no schema."""
    from kctl_react.core.compliance.api_check.checks import ALL_API_CHECKERS, CHECKER_MAP
    from kctl_react.core.compliance.api_check.hooks import parse_hooks
    from kctl_react.core.compliance.api_check.matcher import match_hooks_to_schema
    from kctl_react.core.compliance.api_check.schema import load_schema, parse_schema

    schema_raw = load_schema(app_path, app_name, offline=offline)
    if schema_raw is None:
        return None

    schema = parse_schema(schema_raw)
    hooks = parse_hooks(app_path)
    match = match_hooks_to_schema(hooks, schema)

    # Select checkers (filtered by --categories if given)
    if cat_list:
        checkers = [CHECKER_MAP[c] for c in cat_list if c in CHECKER_MAP]
    else:
        checkers = list(ALL_API_CHECKERS)

    categories: list[CategoryResult] = []
    for checker in checkers:
        result = checker.check(schema, hooks, match)
        categories.append(result)

    return AppReport(app=app_name, categories=categories)


def _run_api_health_for_app(
    app_path: Path,
    app_name: str,
    *,
    url: str | None,
    timeout: float,
    token: str | None,
    cat_list: list[str] | None,
) -> AppReport | None:
    """Run api-health checkers for a single app, returning AppReport or None if no schema."""
    from kctl_react.core.compliance.api_check.schema import (
        APP_BACKEND_MAP,
        load_schema,
        parse_schema,
    )
    from kctl_react.core.compliance.api_health import run_health_checks
    from kctl_react.core.compliance.api_health.checks import AuthChecker
    from kctl_react.core.compliance.api_health.checks import ReachableChecker, ResponseChecker, TimingChecker
    from kctl_react.core.compliance.api_health.client import HealthClient
    from kctl_react.core.compliance.api_health.sampler import sample_endpoints

    schema_raw = load_schema(app_path, app_name, offline=False)
    if schema_raw is None:
        return None

    schema = parse_schema(schema_raw)

    # Resolve base URL
    base_url = url
    if not base_url:
        base_url = _read_env_var(app_path, "VITE_API_BASE_URL")
    if not base_url:
        base_url = _read_env_var(app_path, "NEXT_PUBLIC_API_BASE_URL")
    if not base_url:
        backend = APP_BACKEND_MAP.get(app_name, app_name)
        base_url = f"http://localhost:8069/{backend}/api"

    client = HealthClient(base_url=base_url, token=token, timeout=timeout)

    # Authenticate if no token provided
    auth_failed = False
    if not client.token:
        if not client.authenticate(app_path, app_name):
            auth_failed = True

    endpoints = sample_endpoints(schema)
    results = run_health_checks(client, endpoints)

    # Run checkers (filtered by --categories if given)
    categories: list[CategoryResult] = []

    checker_instances = {
        "auth": lambda: AuthChecker().check(client, schema),
        "reachable": lambda: ReachableChecker().check(results),
        "response": lambda: ResponseChecker().check(results),
        "timing": lambda: TimingChecker().check(results, threshold=timeout),
    }

    if cat_list:
        selected = [c for c in cat_list if c in checker_instances]
    else:
        selected = list(checker_instances.keys())

    for name in selected:
        categories.append(checker_instances[name]())

    return AppReport(app=app_name, categories=categories)


# ---------------------------------------------------------------------------
# api-check command
# ---------------------------------------------------------------------------


@app.command("api-check")
def api_check_cmd(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name to check")] = None,
    all_apps: Annotated[bool, typer.Option("--all", help="Check all apps")] = False,
    offline: Annotated[bool, typer.Option("--offline", help="Skip schema fetching, use cached only")] = False,
    categories: Annotated[
        str | None, typer.Option("--categories", "-c", help="Comma-separated category filter")
    ] = None,
    min_score: Annotated[
        int | None, typer.Option("--min-score", help="Minimum passing score (percentage 0-100)")
    ] = None,
) -> None:
    """Check frontend API hooks against OpenAPI schema.

    Examples:
      kctl-react compliance api-check sfa
      kctl-react compliance api-check --all
      kctl-react compliance api-check sfa --offline
      kctl-react compliance api-check sfa --categories endpoints,types
      kctl-react compliance api-check --all --min-score 80
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    if not app_name and not all_apps:
        out.error("Specify an app name or use --all")
        raise typer.Exit(1) from None

    cat_list = _parse_categories(categories)

    if all_apps:
        reports: list[AppReport] = []
        for name in actx.app_names:
            app_path = root / "apps" / name
            report = _run_api_check_for_app(app_path, name, offline=offline, cat_list=cat_list)
            if report is None:
                out.warn(f"No OpenAPI schema available for {name}")
                continue
            reports.append(report)

        _audit_all(actx, reports)

        if min_score is not None:
            any_below = False
            for r in reports:
                pct = int(r.total_score / r.max_score * 100) if r.max_score > 0 else 100
                if pct < min_score:
                    out.error(f"{r.app} scored {pct}% (below {min_score}%)")
                    any_below = True
            if any_below:
                raise typer.Exit(1) from None
    else:
        assert app_name is not None
        actx.validate_app(app_name)
        app_path = root / "apps" / app_name
        report = _run_api_check_for_app(app_path, app_name, offline=offline, cat_list=cat_list)
        if report is None:
            out.warn(f"No OpenAPI schema available for {app_name}")
            raise typer.Exit(0) from None

        _audit_single(actx, report)

        if min_score is not None:
            pct = int(report.total_score / report.max_score * 100) if report.max_score > 0 else 100
            if pct < min_score:
                out.error(f"{report.app} scored {pct}% (below {min_score}%)")
                raise typer.Exit(1) from None


# ---------------------------------------------------------------------------
# api-health command
# ---------------------------------------------------------------------------


@app.command("api-health")
def api_health_cmd(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name to health-check")] = None,
    all_apps: Annotated[bool, typer.Option("--all", help="Health-check all apps")] = False,
    url: Annotated[str | None, typer.Option("--url", help="Override base URL for backend")] = None,
    timeout: Annotated[float, typer.Option("--timeout", help="Per-request timeout in seconds")] = 3.0,
    token: Annotated[str | None, typer.Option("--token", help="Pre-authenticated JWT token")] = None,
    categories: Annotated[
        str | None, typer.Option("--categories", "-c", help="Comma-separated category filter")
    ] = None,
    min_score: Annotated[
        int | None, typer.Option("--min-score", help="Minimum passing score (percentage 0-100)")
    ] = None,
) -> None:
    """Run live health checks against backend API endpoints.

    Examples:
      kctl-react compliance api-health sfa
      kctl-react compliance api-health sfa --url https://api.kodeme.io
      kctl-react compliance api-health --all --url http://localhost:8069
      kctl-react compliance api-health sfa --timeout 5
      kctl-react compliance api-health sfa --token eyJ...
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    if not app_name and not all_apps:
        out.error("Specify an app name or use --all")
        raise typer.Exit(1) from None

    cat_list = _parse_categories(categories)

    if all_apps:
        reports: list[AppReport] = []
        for name in actx.app_names:
            app_path = root / "apps" / name
            report = _run_api_health_for_app(
                app_path,
                name,
                url=url,
                timeout=timeout,
                token=token,
                cat_list=cat_list,
            )
            if report is None:
                out.warn(f"No OpenAPI schema available for {name}")
                continue
            reports.append(report)

        _audit_all(actx, reports)

        if min_score is not None:
            any_below = False
            for r in reports:
                pct = int(r.total_score / r.max_score * 100) if r.max_score > 0 else 100
                if pct < min_score:
                    out.error(f"{r.app} scored {pct}% (below {min_score}%)")
                    any_below = True
            if any_below:
                raise typer.Exit(1) from None
    else:
        assert app_name is not None
        actx.validate_app(app_name)
        app_path = root / "apps" / app_name
        report = _run_api_health_for_app(
            app_path,
            app_name,
            url=url,
            timeout=timeout,
            token=token,
            cat_list=cat_list,
        )
        if report is None:
            out.warn(f"No OpenAPI schema available for {app_name}")
            raise typer.Exit(0) from None

        _audit_single(actx, report)

        if min_score is not None:
            pct = int(report.total_score / report.max_score * 100) if report.max_score > 0 else 100
            if pct < min_score:
                out.error(f"{report.app} scored {pct}% (below {min_score}%)")
                raise typer.Exit(1) from None
