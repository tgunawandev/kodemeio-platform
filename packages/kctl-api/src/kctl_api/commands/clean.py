"""Artifact cleanup commands for kctl-api.

Clean build artifacts, caches, and __pycache__ directories.
"""

from __future__ import annotations

import pathlib
import shutil
from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.utils import find_project_root

app = typer.Typer(name="clean", help="Cleanup — all, cache, build, pycache.", no_args_is_help=True)


def _rm_dirs(patterns: list[str], root: pathlib.Path, dry_run: bool = False) -> list[pathlib.Path]:
    """Remove directories matching glob patterns under root. Returns removed paths."""
    removed: list[pathlib.Path] = []
    skip_dirs = {".venv", ".git", "node_modules"}

    for pattern in patterns:
        for target in root.rglob(pattern):
            # Don't clean inside .venv or .git
            if any(part in skip_dirs for part in target.parts):
                continue
            if target.is_dir():
                removed.append(target)
                if not dry_run:
                    shutil.rmtree(target, ignore_errors=True)
            elif target.is_file():
                removed.append(target)
                if not dry_run:
                    target.unlink(missing_ok=True)

    return removed


def _rm_files(patterns: list[str], root: pathlib.Path, dry_run: bool = False) -> list[pathlib.Path]:
    """Remove files matching glob patterns under root."""
    removed: list[pathlib.Path] = []
    skip_dirs = {".venv", ".git", "node_modules"}

    for pattern in patterns:
        for target in root.rglob(pattern):
            if any(part in skip_dirs for part in target.parts):
                continue
            if target.is_file():
                removed.append(target)
                if not dry_run:
                    target.unlink(missing_ok=True)

    return removed


def _display_removed(out: object, removed: list[pathlib.Path], root: pathlib.Path, dry_run: bool) -> None:
    """Print removed paths."""
    prefix = "[dim](dry-run)[/dim] " if dry_run else ""
    for path in removed[:30]:
        try:
            rel = path.relative_to(root)
        except ValueError:
            rel = path
        out.text(f"  {prefix}[red]rm[/red] {rel}")  # type: ignore[attr-defined]
    if len(removed) > 30:
        out.text(f"  ... and {len(removed) - 30} more")  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# all
# ---------------------------------------------------------------------------
@app.command(name="all")
def clean_all(
    ctx: typer.Context,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be removed without deleting.")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation.")] = False,
) -> None:
    """Remove all build artifacts, caches, and __pycache__ directories."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not force and not dry_run:
        confirm = typer.confirm("Remove all build artifacts and caches?", default=False)
        if not confirm:
            out.info("Cancelled.")
            raise typer.Exit(0)

    root = find_project_root()
    total_removed: list[pathlib.Path] = []

    cache_dirs = [".ruff_cache", ".mypy_cache", ".pytest_cache", ".hypothesis", ".tox"]
    build_dirs = ["dist", "build", "*.egg-info"]
    pycache_dirs = ["__pycache__"]
    coverage_files = [".coverage", "coverage.xml", "htmlcov"]

    total_removed += _rm_dirs(cache_dirs, root, dry_run)
    total_removed += _rm_dirs(build_dirs, root, dry_run)
    total_removed += _rm_dirs(pycache_dirs, root, dry_run)
    total_removed += _rm_dirs(coverage_files, root, dry_run)
    total_removed += _rm_files(["*.pyc", "*.pyo"], root, dry_run)

    if total_removed:
        _display_removed(out, total_removed, root, dry_run)
        action = "Would remove" if dry_run else "Removed"
        out.success(f"{action} {len(total_removed)} items.")
    else:
        out.info("Nothing to clean.")


# ---------------------------------------------------------------------------
# cache
# ---------------------------------------------------------------------------
@app.command()
def cache(
    ctx: typer.Context,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be removed.")] = False,
) -> None:
    """Remove .ruff_cache, .mypy_cache, .pytest_cache directories."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    patterns = [".ruff_cache", ".mypy_cache", ".pytest_cache", ".hypothesis"]
    removed = _rm_dirs(patterns, root, dry_run)

    if removed:
        _display_removed(out, removed, root, dry_run)
        action = "Would remove" if dry_run else "Removed"
        out.success(f"{action} {len(removed)} cache directories.")
    else:
        out.info("No cache directories found.")


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
@app.command()
def build(
    ctx: typer.Context,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be removed.")] = False,
) -> None:
    """Remove dist/ and *.egg-info build artifacts."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    patterns = ["dist", "build", "*.egg-info", "*.dist-info"]
    removed = _rm_dirs(patterns, root, dry_run)

    if removed:
        _display_removed(out, removed, root, dry_run)
        action = "Would remove" if dry_run else "Removed"
        out.success(f"{action} {len(removed)} build artifact directories.")
    else:
        out.info("No build artifacts found.")


# ---------------------------------------------------------------------------
# pycache
# ---------------------------------------------------------------------------
@app.command()
def pycache(
    ctx: typer.Context,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be removed.")] = False,
) -> None:
    """Remove all __pycache__ directories and .pyc/.pyo files."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    removed = _rm_dirs(["__pycache__"], root, dry_run)
    removed += _rm_files(["*.pyc", "*.pyo"], root, dry_run)

    if removed:
        _display_removed(out, removed, root, dry_run)
        action = "Would remove" if dry_run else "Removed"
        out.success(f"{action} {len(removed)} __pycache__ items.")
    else:
        out.info("No __pycache__ directories found.")
