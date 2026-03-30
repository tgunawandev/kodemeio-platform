"""App registry commands for kctl-api.

Enumerate and inspect known apps in the kodemeio-fastapi monorepo.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.utils import KNOWN_APPS

app = typer.Typer(name="apps", help="App registry — list and inspect monorepo apps.", no_args_is_help=True)


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------
@app.command(name="list")
def list_apps(ctx: typer.Context) -> None:
    """List all known apps in the kodemeio-fastapi monorepo."""
    actx: AppContext = ctx.obj
    out = actx.output

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for name, meta in KNOWN_APPS.items():
        port = meta.get("port", "")
        app_type = meta.get("type", "")
        module = meta.get("module", "")
        rows.append([name, app_type, port or "-", module])
        json_data.append({"name": name, "type": app_type, "port": port, "module": module})

    out.table(
        title=f"Known Apps ({len(KNOWN_APPS)})",
        columns=[
            ("Name", "bold"),
            ("Type", ""),
            ("Port", ""),
            ("Module", "dim"),
        ],
        rows=rows,
        data_for_json=json_data,
    )


# ---------------------------------------------------------------------------
# info
# ---------------------------------------------------------------------------
@app.command()
def info(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="App name.")],
) -> None:
    """Show details for a specific app from the registry."""
    actx: AppContext = ctx.obj
    out = actx.output

    meta = KNOWN_APPS.get(name)
    if not meta:
        out.error(f"Unknown app: {name}. Run 'kctl-api apps list' to see available apps.")
        raise typer.Exit(1)

    data = {"name": name, **meta}

    out.detail(
        title=f"App: {name}",
        sections=[
            (
                "Details",
                [
                    ("Name", name),
                    ("Type", meta.get("type", "")),
                    ("Port", meta.get("port", "") or "(none)"),
                    ("Module", meta.get("module", "")),
                ],
            ),
        ],
        data_for_json=data,
    )


# ---------------------------------------------------------------------------
# env
# ---------------------------------------------------------------------------
@app.command()
def env(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="App name.")],
) -> None:
    """Show environment variables for an app (reads .env.example)."""
    actx: AppContext = ctx.obj
    out = actx.output

    from kctl_api.core.utils import find_project_root

    meta = KNOWN_APPS.get(name)
    if not meta:
        out.error(f"Unknown app: {name}")
        raise typer.Exit(1)

    root = find_project_root()
    env_example = root / "apps" / name / ".env.example"
    if not env_example.exists():
        env_example = root / ".env.example"

    if not env_example.exists():
        out.info(f"No .env.example found for {name}.")
        return

    content = env_example.read_text()
    if actx.json_mode:
        lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]
        out.raw_json([{"var": line.split("=", 1)[0], "example": line} for line in lines])
    else:
        out.header(f"Environment: {name}")
        out.text(content)


# ---------------------------------------------------------------------------
# deps
# ---------------------------------------------------------------------------
@app.command()
def deps(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="App name.")],
) -> None:
    """Show dependencies for an app (reads pyproject.toml)."""
    actx: AppContext = ctx.obj
    out = actx.output

    from kctl_api.core.utils import find_project_root

    meta = KNOWN_APPS.get(name)
    if not meta:
        out.error(f"Unknown app: {name}")
        raise typer.Exit(1)

    root = find_project_root()
    pyproject = root / "apps" / name / "pyproject.toml"
    if not pyproject.exists():
        out.info(f"No pyproject.toml found for {name}.")
        return

    content = pyproject.read_text()

    # Simple TOML parsing for dependencies section
    in_deps = False
    deps_list: list[str] = []
    for line in content.splitlines():
        if line.strip().startswith("[project]"):
            continue
        if "dependencies" in line and "=" in line:
            in_deps = True
            continue
        if in_deps:
            if line.strip().startswith("]"):
                break
            dep = line.strip().strip('",').strip("'")
            if dep:
                deps_list.append(dep)

    if actx.json_mode:
        out.raw_json({"app": name, "dependencies": deps_list})
    else:
        out.header(f"Dependencies: {name}")
        for dep in deps_list:
            out.text(f"  {dep}")
        out.info(f"{len(deps_list)} dependencies.")
