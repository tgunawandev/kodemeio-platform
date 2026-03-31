"""Environment variable management commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from kctl_react.core.callbacks import AppContext
from kctl_react.core.discovery import get_app_dir

app = typer.Typer(help="Environment variable management.")


def _find_env_files(app_dir: Path) -> list[Path]:
    """Find all .env* files in an app directory."""
    return sorted(f for f in app_dir.iterdir() if f.name.startswith(".env") and f.is_file())


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file into key-value pairs."""
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip().strip('"').strip("'")
    return result


@app.command()
def show(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
) -> None:
    """Show environment variables for an app."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_dir = get_app_dir(root, app_name)

    env_files = _find_env_files(app_dir)
    if not env_files:
        out.warn(f"No .env files found in apps/{app_name}/")
        return

    for env_file in env_files:
        env_vars = _parse_env_file(env_file)
        sections: list[tuple[str, list[tuple[str, str]]]] = [
            (env_file.name, [(k, v) for k, v in sorted(env_vars.items())]),
        ]
        out.detail(f"{app_name} — {env_file.name}", sections, data_for_json=env_vars)


@app.command()
def diff(
    ctx: typer.Context,
    app1: Annotated[str, typer.Argument(help="First app name")],
    app2: Annotated[str, typer.Argument(help="Second app name")],
) -> None:
    """Compare .env files between two apps."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app1)
    actx.validate_app(app2)

    env1 = _parse_env_file(get_app_dir(root, app1) / ".env")
    env2 = _parse_env_file(get_app_dir(root, app2) / ".env")

    if not env1:
        env1 = _parse_env_file(get_app_dir(root, app1) / ".env.local")
    if not env2:
        env2 = _parse_env_file(get_app_dir(root, app2) / ".env.local")

    all_keys = sorted(set(env1.keys()) | set(env2.keys()))

    rows: list[list[str]] = []
    for key in all_keys:
        v1 = env1.get(key, "[dim]--[/dim]")
        v2 = env2.get(key, "[dim]--[/dim]")
        match = "[green]=[/green]" if v1 == v2 else "[yellow]![/yellow]"
        rows.append([key, v1, v2, match])

    out.table(
        f"Env Diff: {app1} vs {app2}",
        [("Key", "cyan"), (app1, ""), (app2, ""), ("Match", "")],
        rows,
    )


@app.command()
def validate(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (omit for all)")] = None,
) -> None:
    """Validate .env files exist and have required keys."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    apps_to_check = [app_name] if app_name else actx.app_names
    if app_name:
        actx.validate_app(app_name)

    # Common expected keys for Kodemeio React apps
    expected_keys = {"VITE_ODOO_URL", "VITE_ODOO_DB", "VITE_AUTH_MODE"}

    rows: list[list[str]] = []
    issues = 0

    for name in apps_to_check:
        app_dir = get_app_dir(root, name)
        env_files = _find_env_files(app_dir)

        if not env_files:
            rows.append([name, "[red]missing[/red]", "[dim]--[/dim]", "[red]no .env file[/red]"])
            issues += 1
            continue

        env = _parse_env_file(env_files[0])
        missing = expected_keys - set(env.keys())
        file_name = env_files[0].name

        if missing:
            rows.append(
                [
                    name,
                    f"[green]{file_name}[/green]",
                    str(len(env)),
                    f"[yellow]missing: {', '.join(sorted(missing))}[/yellow]",
                ]
            )
            issues += 1
        else:
            rows.append([name, f"[green]{file_name}[/green]", str(len(env)), "[green]OK[/green]"])

    out.table(
        "Env Validation",
        [("App", "cyan"), ("File", ""), ("Keys", ""), ("Status", "")],
        rows,
    )

    if issues:
        out.warn(f"{issues} app(s) have env issues")
    else:
        out.success("All apps have valid env files")
