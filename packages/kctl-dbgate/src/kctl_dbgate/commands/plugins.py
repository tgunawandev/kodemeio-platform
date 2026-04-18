"""Plugin management commands.

Wraps /plugins/install, /plugins/uninstall, /plugins/upgrade.

NOTE: DBGate does not expose a dedicated "list plugins" endpoint.
`list` derives the set of in-use plugins by scanning connection engines
(engine strings look like "postgres@dbgate-plugin-postgres").
"""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib.exceptions import KctlError

from kctl_dbgate.core.callbacks import AppContext

app = typer.Typer(help="Manage DBGate plugins.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List plugins in use (derived from connection engines)."""
    actx: AppContext = ctx.obj
    out = actx.output
    try:
        connections = actx.client.list_connections()
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    seen: dict[str, int] = {}
    for conn in connections:
        engine = str(conn.get("engine", ""))
        if "@" in engine:
            plugin = engine.split("@", 1)[1]
            seen[plugin] = seen.get(plugin, 0) + 1

    rows = [[name, str(count)] for name, count in sorted(seen.items())]
    out.table(
        title=f"{len(rows)} plugin(s) in use",
        columns=[("Plugin", "cyan"), ("Connection count", "")],
        rows=rows,
        data_for_json=[{"plugin": n, "count": c} for n, c in seen.items()],
    )
    if not rows:
        out.info("No plugins currently in use by any connection.")


@app.command()
def install(
    ctx: typer.Context,
    package: Annotated[str, typer.Argument(help="Plugin package name (e.g. dbgate-plugin-redis)")],
) -> None:
    """Install a plugin package."""
    actx: AppContext = ctx.obj
    out = actx.output
    try:
        actx.client.call("/plugins/install", {"packageName": package})
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e
    out.success(f"Plugin '{package}' installed")


@app.command()
def uninstall(
    ctx: typer.Context,
    package: Annotated[str, typer.Argument(help="Plugin package name")],
) -> None:
    """Uninstall a plugin package."""
    actx: AppContext = ctx.obj
    out = actx.output
    try:
        actx.client.call("/plugins/uninstall", {"packageName": package})
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e
    out.success(f"Plugin '{package}' uninstalled")


@app.command()
def upgrade(
    ctx: typer.Context,
    package: Annotated[str, typer.Argument(help="Plugin package name")],
) -> None:
    """Upgrade a plugin to its latest version."""
    actx: AppContext = ctx.obj
    out = actx.output
    try:
        actx.client.call("/plugins/upgrade", {"packageName": package})
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e
    out.success(f"Plugin '{package}' upgraded")
