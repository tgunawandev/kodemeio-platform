"""Git-aware affected app detection."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_react.core.callbacks import AppContext
from kctl_react.core.git import get_affected_apps, get_changed_files, get_uncommitted_files
from kctl_react.core.runner import run_turbo

app = typer.Typer(help="Git-aware change detection and targeted operations.")


@app.callback(invoke_without_command=True)
def affected(
    ctx: typer.Context,
    base: Annotated[str, typer.Option("--base", "-b", help="Base git ref to compare against.")] = "HEAD~1",
) -> None:
    """Show which apps are affected by recent changes.

    Detects changes in apps/, packages/, and root config files.
    Package changes propagate to all apps that depend on them.

    Examples:
      kctl-react affected                # Changes since last commit
      kctl-react affected --base main    # Changes since main branch
    """
    if ctx.invoked_subcommand is not None:
        return

    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    apps = get_affected_apps(root, base)
    changed = get_changed_files(root, base) + get_uncommitted_files(root)

    if not apps:
        out.info("No apps affected by current changes")
        if out.json_mode:
            out.raw_json({"affected": [], "changed_files": len(changed)})
        return

    # Categorize changes
    app_changes: dict[str, list[str]] = {a: [] for a in apps}
    pkg_changes: list[str] = []

    for f in changed:
        parts = f.split("/")
        if len(parts) >= 3 and parts[0] == "apps" and parts[1] in ("spa", "web", "api") and parts[2] in apps:
            app_changes[parts[2]].append(f)
        elif len(parts) >= 2 and parts[0] == "apps" and parts[1] in apps:
            app_changes[parts[1]].append(f)
        elif parts[0] == "packages":
            pkg_changes.append(f)

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for app_name in apps:
        direct = len(app_changes.get(app_name, []))
        reason = f"{direct} file(s)" if direct else "[dim]via package dep[/dim]"
        rows.append([app_name, reason])
        json_data.append({"app": app_name, "direct_changes": direct})

    out.table(
        f"Affected Apps (vs {base})",
        [("App", "cyan"), ("Reason", "")],
        rows,
        data_for_json=json_data,
    )

    if pkg_changes:
        out.info(f"{len(pkg_changes)} package file(s) changed")
    out.success(f"{len(apps)} app(s) affected, {len(changed)} file(s) changed")


@app.command()
def test(
    ctx: typer.Context,
    base: Annotated[str, typer.Option("--base", "-b", help="Base git ref.")] = "HEAD~1",
    coverage: Annotated[bool, typer.Option("--coverage", "-c", help="Run with coverage.")] = False,
) -> None:
    """Run tests only for affected apps."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    apps = get_affected_apps(root, base)
    if not apps:
        out.success("No apps affected — skipping tests")
        return

    out.info(f"Running tests for {len(apps)} affected app(s): {', '.join(apps)}")
    task = "test:ci" if coverage else "test"
    failed = 0

    for app_name in apps:
        try:
            run_turbo(task, root, filter_app=app_name, capture=False, timeout=300)
        except Exception:
            failed += 1

    if failed:
        out.error(f"{failed}/{len(apps)} app(s) failed")
        raise typer.Exit(1) from None
    out.success(f"All {len(apps)} affected app(s) passed")


@app.command()
def build(
    ctx: typer.Context,
    base: Annotated[str, typer.Option("--base", "-b", help="Base git ref.")] = "HEAD~1",
) -> None:
    """Build only affected apps."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    apps = get_affected_apps(root, base)
    if not apps:
        out.success("No apps affected — skipping build")
        return

    out.info(f"Building {len(apps)} affected app(s): {', '.join(apps)}")
    failed = 0

    for app_name in apps:
        try:
            run_turbo("build", root, filter_app=app_name, capture=False, timeout=600)
        except Exception:
            failed += 1

    if failed:
        out.error(f"{failed}/{len(apps)} app(s) failed to build")
        raise typer.Exit(1) from None
    out.success(f"All {len(apps)} affected app(s) built")


@app.command()
def lint(
    ctx: typer.Context,
    base: Annotated[str, typer.Option("--base", "-b", help="Base git ref.")] = "HEAD~1",
) -> None:
    """Lint only affected apps."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    apps = get_affected_apps(root, base)
    if not apps:
        out.success("No apps affected — skipping lint")
        return

    out.info(f"Linting {len(apps)} affected app(s): {', '.join(apps)}")
    failed = 0

    for app_name in apps:
        try:
            run_turbo("lint", root, filter_app=app_name, capture=False, timeout=300)
            run_turbo("type-check", root, filter_app=app_name, capture=False, timeout=300)
        except Exception:
            failed += 1

    if failed:
        out.error(f"{failed}/{len(apps)} app(s) have lint errors")
        raise typer.Exit(1) from None
    out.success(f"All {len(apps)} affected app(s) passed lint")
