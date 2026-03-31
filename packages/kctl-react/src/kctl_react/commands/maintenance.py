"""Maintenance commands: health-report, cleanup, dr-status, count-test-files, deps-sync."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Annotated

import typer

from kctl_react.core.callbacks import AppContext
from kctl_react.core.discovery import get_app_dir

app = typer.Typer(help="Maintenance utilities for the React monorepo.")

# Artifact directories to clean up
_CLEANUP_TARGETS = [
    "dist",
    ".turbo",
    "coverage",
    Path("node_modules") / ".cache",
    Path("node_modules") / ".vite",
]


def _count_test_files(app_dir: Path) -> int:
    """Count .test.ts and .test.tsx files under <app_dir>/src."""
    src = app_dir / "src"
    if not src.is_dir():
        return 0
    return len(list(src.rglob("*.test.ts")) + list(src.rglob("*.test.tsx")))


def _collect_dep_versions(
    root: Path,
    app_names: list[str],
    package_names: list[str],
) -> dict[str, dict[str, str]]:
    """Collect dependency versions from apps and packages.

    Returns: {dep_name: {source_name: version, ...}, ...}
    """
    versions: dict[str, dict[str, str]] = {}

    sources: list[tuple[str, Path]] = []
    for name in app_names:
        sources.append((name, get_app_dir(root, name) / "package.json"))
    for name in package_names:
        sources.append((name, root / "packages" / name / "package.json"))

    for source_name, pkg_file in sources:
        if not pkg_file.exists():
            continue
        try:
            pkg = json.loads(pkg_file.read_text())
        except Exception:
            continue
        all_deps: dict[str, str] = {}
        all_deps.update(pkg.get("dependencies", {}))
        all_deps.update(pkg.get("devDependencies", {}))
        for dep, ver in all_deps.items():
            if dep not in versions:
                versions[dep] = {}
            versions[dep][source_name] = ver

    return versions


@app.command("health-report")
def health_report(ctx: typer.Context) -> None:
    """Show per-app health: test file count, codegen status, and dist presence."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for name in actx.app_names:
        app_dir = get_app_dir(root, name)
        tests = _count_test_files(app_dir)
        codegen = (app_dir / "src" / "generated").is_dir()
        built = (app_dir / "dist").is_dir()
        has_env = (app_dir / ".env").exists()

        codegen_str = "[green]yes[/green]" if codegen else "[red]no[/red]"
        built_str = "[green]yes[/green]" if built else "[dim]no[/dim]"
        env_str = "[green]yes[/green]" if has_env else "[dim]no[/dim]"

        rows.append([name, str(tests), codegen_str, built_str, env_str])
        json_data.append(
            {
                "app": name,
                "tests": tests,
                "codegen": codegen,
                "built": built,
                "env": has_env,
            }
        )

    out.table(
        "Monorepo Health Report",
        [
            ("App", "cyan"),
            ("Tests", "green"),
            ("Codegen", ""),
            ("Built", ""),
            (".env", ""),
        ],
        rows,
        data_for_json=json_data,
    )


@app.command("cleanup")
def cleanup(
    ctx: typer.Context,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be removed without deleting")] = False,
) -> None:
    """Remove build artifacts (dist/, .turbo/, coverage/, node_modules/.cache)."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    found: list[dict] = []

    # Check apps
    for name in actx.app_names:
        app_dir = get_app_dir(root, name)
        for target in _CLEANUP_TARGETS:
            path = app_dir / target
            if path.exists():
                found.append({"path": str(path.relative_to(root)), "app": name, "target": str(target)})

    # Check root
    for target in _CLEANUP_TARGETS:
        path = root / target
        if path.exists():
            found.append({"path": str(path.relative_to(root)), "app": "root", "target": str(target)})

    if not found:
        out.success("Nothing to clean — workspace is already tidy")
        if out.json_mode:
            out.raw_json([])
        return

    if out.json_mode:
        out.raw_json(found)
        return

    label = "[dim](dry-run)[/dim]" if dry_run else ""
    out.info(f"Cleaning build artifacts {label}...")

    for item in found:
        path = root / item["path"]
        if dry_run:
            out.info(f"  Would remove: {item['path']}")
        else:
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                out.info(f"  Removed: {item['path']}")
            except Exception as e:
                out.warn(f"  Could not remove {item['path']}: {e}")

    if dry_run:
        out.info(f"Dry-run complete — {len(found)} item(s) would be removed")
    else:
        out.success(f"Cleaned {len(found)} artifact(s)")


@app.command("dr-status")
def dr_status(ctx: typer.Context) -> None:
    """Check deployment readiness: Dockerfile, docker-compose, and .env files."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for name in actx.app_names:
        app_dir = get_app_dir(root, name)

        dockerfile = (app_dir / "Dockerfile").exists()
        compose = (app_dir / "docker-compose.yml").exists() or (app_dir / "docker-compose.yaml").exists()
        env_file = (app_dir / ".env").exists()
        env_example = (app_dir / ".env.example").exists()

        # Ready when at least Dockerfile is present
        is_ready = dockerfile
        status = "[green]ready[/green]" if is_ready else "[yellow]not ready[/yellow]"

        def _icon(v: bool) -> str:
            return "[green]yes[/green]" if v else "[dim]no[/dim]"

        rows.append([name, _icon(dockerfile), _icon(compose), _icon(env_file), _icon(env_example), status])
        json_data.append(
            {
                "app": name,
                "build": dockerfile,
                "docker": compose,
                "env": env_file,
                "env_example": env_example,
                "ready": is_ready,
            }
        )

    out.table(
        "Deployment Readiness Status",
        [
            ("App", "cyan"),
            ("Dockerfile", ""),
            ("Compose", ""),
            (".env", ""),
            (".env.example", ""),
            ("Status", ""),
        ],
        rows,
        data_for_json=json_data,
    )


@app.command("count-test-files")
def count_test_files_cmd(ctx: typer.Context) -> None:
    """Count test files (.test.ts / .test.tsx) per app."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    rows: list[list[str]] = []
    json_data: list[dict] = []
    total = 0

    for name in actx.app_names:
        app_dir = get_app_dir(root, name)
        count = _count_test_files(app_dir)
        total += count
        rows.append([name, str(count)])
        json_data.append({"app": name, "test_files": count})

    rows.append(["[bold]TOTAL[/bold]", f"[bold]{total}[/bold]"])

    out.table(
        "Test File Count",
        [("App", "cyan"), ("Test Files", "green")],
        rows,
        data_for_json=json_data,
    )


@app.command("deps-sync")
def deps_sync(
    ctx: typer.Context,
    exclude: Annotated[str | None, typer.Option("--exclude", help="Comma-separated dep names to ignore")] = None,
) -> None:
    """Check dependency version consistency across all apps and packages."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    excluded = {e.strip() for e in exclude.split(",")} if exclude else set()

    # Collect all package names from packages/
    package_names: list[str] = []
    packages_dir = root / "packages"
    if packages_dir.is_dir():
        for p in sorted(packages_dir.iterdir()):
            if (p / "package.json").exists():
                package_names.append(p.name)

    all_versions = _collect_dep_versions(root, actx.app_names, package_names)

    # Find inconsistencies: same dep, multiple different versions
    inconsistent: list[dict] = []
    for dep, sources in sorted(all_versions.items()):
        if dep in excluded:
            continue
        unique_versions = set(sources.values())
        if len(unique_versions) > 1:
            inconsistent.append({"package": dep, "versions": sources})

    if not inconsistent:
        out.success("All shared dependencies are in sync")
        if out.json_mode:
            out.raw_json([])
        return

    if out.json_mode:
        out.raw_json(inconsistent)
        return

    out.warn(f"Found {len(inconsistent)} inconsistent dependency(s):")
    rows: list[list[str]] = []
    for item in inconsistent:
        for source, ver in item["versions"].items():
            rows.append([item["package"], source, ver])

    out.table(
        "Inconsistent Dependencies",
        [("Package", "cyan"), ("App/Package", "dim"), ("Version", "yellow")],
        rows,
        data_for_json=inconsistent,
    )
    out.warn("Run `pnpm update <package>` to align versions")
