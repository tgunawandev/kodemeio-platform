"""Module management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.utils import module_state_color

app = typer.Typer(help="Manage Odoo modules.")


@app.command("list")
def list_(
    ctx: typer.Context,
    state: Annotated[
        str | None, typer.Option("--state", "-s", help="Filter by state (installed, uninstalled, to upgrade)")
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 200,
) -> None:
    """List modules."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = []
    if state:
        domain.append(("state", "=", state))

    modules = c.search_read(
        "ir.module.module",
        domain=domain,
        fields=["id", "name", "shortdesc", "state", "installed_version", "author"],
        limit=limit,
        order="name",
    )

    rows = []
    json_data = []
    for m in modules:
        state_display = module_state_color(m.get("state", ""))
        rows.append(
            [
                str(m["id"]),
                m["name"],
                m.get("shortdesc") or "",
                state_display,
                m.get("installed_version") or "-",
                m.get("author") or "",
            ]
        )
        json_data.append(
            {
                "id": m["id"],
                "name": m["name"],
                "summary": m.get("shortdesc"),
                "state": m.get("state"),
                "version": m.get("installed_version"),
                "author": m.get("author"),
            }
        )

    out.table(
        f"Modules ({len(modules)})",
        [("ID", "cyan"), ("Technical Name", ""), ("Summary", ""), ("State", ""), ("Version", "dim"), ("Author", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def install(
    ctx: typer.Context,
    names: Annotated[str, typer.Argument(help="Comma-separated module names")],
) -> None:
    """Install modules."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    module_names = [n.strip() for n in names.split(",")]
    for name in module_names:
        ids = c.search("ir.module.module", [("name", "=", name)])
        if not ids:
            out.error(f"Module not found: {name}")
            continue
        c.execute_kw("ir.module.module", "button_immediate_install", [ids])
        out.success(f"Installed: {name}")


@app.command()
def upgrade(
    ctx: typer.Context,
    names: Annotated[str, typer.Argument(help="Comma-separated module names")],
) -> None:
    """Upgrade modules."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    module_names = [n.strip() for n in names.split(",")]
    for name in module_names:
        ids = c.search("ir.module.module", [("name", "=", name), ("state", "=", "installed")])
        if not ids:
            out.error(f"Module not found or not installed: {name}")
            continue
        c.execute_kw("ir.module.module", "button_immediate_upgrade", [ids])
        out.success(f"Upgraded: {name}")


@app.command()
def uninstall(
    ctx: typer.Context,
    names: Annotated[str, typer.Argument(help="Comma-separated module names")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Uninstall modules."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    module_names = [n.strip() for n in names.split(",")]
    if not force and not typer.confirm(f"Uninstall {', '.join(module_names)}? This may remove data."):
        raise typer.Exit(0)

    for name in module_names:
        ids = c.search("ir.module.module", [("name", "=", name), ("state", "=", "installed")])
        if not ids:
            out.error(f"Module not found or not installed: {name}")
            continue
        c.execute_kw("ir.module.module", "button_immediate_uninstall", [ids])
        out.success(f"Uninstalled: {name}")


@app.command()
def check(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Module technical name")],
) -> None:
    """Check if a module is installed (exit 0 if yes, exit 1 if not).

    Useful for scripting: kctl-odoo modules check sfa_management && echo "ready"

    Examples:
        kctl-odoo modules check sfa_management
        kctl-odoo modules check sale --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    modules = c.search_read(
        "ir.module.module",
        [("name", "=", name)],
        ["name", "state", "installed_version", "shortdesc"],
        limit=1,
    )

    if not modules:
        if actx.json_mode:
            out.raw_json({"name": name, "found": False, "installed": False})
        else:
            out.error(f"Module not found: {name}")
        raise typer.Exit(1)

    m = modules[0]
    installed = m.get("state") == "installed"

    if actx.json_mode:
        out.raw_json(
            {
                "name": m["name"],
                "found": True,
                "installed": installed,
                "state": m.get("state"),
                "version": m.get("installed_version") or None,
                "summary": m.get("shortdesc") or None,
            }
        )
    else:
        state = m.get("state", "")
        state_display = module_state_color(state)
        out.detail(
            f"Module: {name}",
            [
                (
                    "Info",
                    [
                        ("Name", m["name"]),
                        ("Summary", m.get("shortdesc") or "-"),
                        ("State", state_display),
                        ("Version", m.get("installed_version") or "-"),
                    ],
                )
            ],
        )

    if not installed:
        raise typer.Exit(1)


@app.command()
def search(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Search term")],
    limit: Annotated[int, typer.Option("--limit", "-l")] = 20,
) -> None:
    """Search for modules by name or description."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain = ["|", ("name", "ilike", query), ("shortdesc", "ilike", query)]
    modules = c.search_read(
        "ir.module.module",
        domain=domain,
        fields=["id", "name", "shortdesc", "state", "installed_version"],
        limit=limit,
        order="name",
    )

    rows = []
    for m in modules:
        rows.append(
            [
                str(m["id"]),
                m["name"],
                m.get("shortdesc") or "",
                module_state_color(m.get("state", "")),
                m.get("installed_version") or "-",
            ]
        )

    out.table(
        f"Search: '{query}' ({len(modules)} results)",
        [("ID", "cyan"), ("Name", ""), ("Summary", ""), ("State", ""), ("Version", "dim")],
        rows,
        data_for_json=modules,
    )


@app.command("scan")
def scan(ctx: typer.Context) -> None:
    """Scan for new or updated modules (update module list)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    out.info("Scanning for new modules...")
    c.execute_kw("ir.module.module", "update_list", [])
    out.success("Module list updated")
