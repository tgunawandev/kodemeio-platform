"""Top-level clean command group."""

from __future__ import annotations

import shutil
from typing import Annotated

import typer

from kctl_react.core.callbacks import AppContext
from kctl_react.core.discovery import get_app_dir

app = typer.Typer(help="Clean build artifacts and caches.")


def run_clean(actx: AppContext, app_name: str | None = None, all_: bool = False) -> None:
    """Clean dist, .turbo, and coverage directories."""
    out = actx.output
    root = actx.project_root

    if app_name:
        actx.validate_app(app_name)

    apps = [app_name] if app_name else actx.app_names
    removed = 0

    for name in apps:
        app_dir = get_app_dir(root, name)
        for dirname in ("dist", ".next", ".turbo", "coverage"):
            target = app_dir / dirname
            if target.is_dir():
                shutil.rmtree(target)
                removed += 1

    for dirname in (".turbo",):
        target = root / dirname
        if target.is_dir():
            shutil.rmtree(target)
            removed += 1

    packages_dir = root / "packages"
    if packages_dir.is_dir():
        for pkg_dir in packages_dir.iterdir():
            for dirname in ("dist", ".turbo"):
                target = pkg_dir / dirname
                if target.is_dir():
                    shutil.rmtree(target)
                    removed += 1

    if all_:
        nm = root / "node_modules"
        if nm.is_dir():
            out.info("Removing node_modules (this may take a moment)...")
            shutil.rmtree(nm)
            removed += 1

    out.success(f"Cleaned {removed} directories")
    if all_:
        out.info("Run `pnpm install` to reinstall dependencies")


@app.command("run")
def run(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (omit for all)")] = None,
    all_: Annotated[bool, typer.Option("--all", "-a", help="Also remove node_modules.")] = False,
) -> None:
    """Clean dist, .turbo, and coverage directories.

    Examples:
      kctl-react clean run             # Clean all apps
      kctl-react clean run sfa         # Clean SFA only
      kctl-react clean run --all       # Clean + remove node_modules
    """
    actx: AppContext = ctx.obj
    run_clean(actx, app_name=app_name, all_=all_)
