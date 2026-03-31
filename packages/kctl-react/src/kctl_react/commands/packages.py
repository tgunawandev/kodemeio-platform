"""Shared package management commands."""

from __future__ import annotations

import contextlib
import json
from typing import Annotated

import typer

from kctl_react.core.callbacks import AppContext
from kctl_react.core.discovery import get_app_dir

app = typer.Typer(help="Shared package inspection and management.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all shared packages with versions and descriptions."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    rows: list[list[str]] = []
    json_data: list[dict] = []

    packages_dir = root / "packages"
    for pkg_name in sorted(actx.packages):
        pkg_dir = packages_dir / pkg_name
        pkg_file = pkg_dir / "package.json"

        if not pkg_file.exists():
            rows.append([f"@kodemeio/{pkg_name}", "[dim]--[/dim]", "[red]missing[/red]", ""])
            continue

        pkg = json.loads(pkg_file.read_text())
        version = pkg.get("version", "0.0.0")
        description = pkg.get("description", "")

        # Count exports
        src_dir = pkg_dir / "src"
        ts_files = len(list(src_dir.rglob("*.ts"))) + len(list(src_dir.rglob("*.tsx"))) if src_dir.is_dir() else 0

        rows.append([f"@kodemeio/{pkg_name}", version, str(ts_files), description[:50]])
        json_data.append(
            {
                "package": f"@kodemeio/{pkg_name}",
                "version": version,
                "files": ts_files,
                "description": description,
            }
        )

    out.table(
        "Shared Packages",
        [("Package", "cyan"), ("Version", "green"), ("Files", ""), ("Description", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def consumers(
    ctx: typer.Context,
    package_name: Annotated[str, typer.Argument(help="Package name (e.g. core, ui, offline)")],
) -> None:
    """Show which apps use a specific shared package."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    full_name = f"@kodemeio/{package_name}"

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for app_name in actx.app_names:
        pkg_file = get_app_dir(root, app_name) / "package.json"
        if not pkg_file.exists():
            continue

        pkg = json.loads(pkg_file.read_text())
        all_deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

        if full_name in all_deps:
            version = all_deps[full_name]
            rows.append([app_name, "[green]Yes[/green]", version])
            json_data.append({"app": app_name, "uses": True, "version": version})
        else:
            rows.append([app_name, "[dim]No[/dim]", ""])
            json_data.append({"app": app_name, "uses": False})

    out.table(
        f"Consumers of {full_name}",
        [("App", "cyan"), ("Uses", ""), ("Version", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def size(ctx: typer.Context) -> None:
    """Show source size of each shared package."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    rows: list[list[str]] = []
    packages_dir = root / "packages"

    for pkg_name in sorted(actx.packages):
        src_dir = packages_dir / pkg_name / "src"
        if not src_dir.is_dir():
            rows.append([f"@kodemeio/{pkg_name}", "[dim]--[/dim]", "[dim]--[/dim]"])
            continue

        files = list(src_dir.rglob("*.ts")) + list(src_dir.rglob("*.tsx"))
        total_lines = 0
        for f in files:
            with contextlib.suppress(Exception):
                total_lines += len(f.read_text().splitlines())

        rows.append([f"@kodemeio/{pkg_name}", str(len(files)), f"{total_lines:,} lines"])

    out.table(
        "Package Source Sizes",
        [("Package", "cyan"), ("Files", "green"), ("Lines", "")],
        rows,
    )
