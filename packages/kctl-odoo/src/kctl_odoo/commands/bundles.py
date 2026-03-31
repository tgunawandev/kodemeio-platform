"""Bundle management commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from kctl_odoo.core.bundles import (
    discover_bundles,
    get_default_install_dir,
    load_bundle,
    resolve_modules,
)
from kctl_odoo.core.callbacks import AppContext

app = typer.Typer(help="Manage module bundles (YAML-based installation groups).")


def _resolve_install_dir(dir_path: str | None) -> Path:
    """Resolve the install directory from flag or default."""
    p = Path(dir_path) if dir_path else get_default_install_dir()
    if not p.is_dir():
        typer.echo(
            f"Install directory not found: {p}\nRun from the kodemeio-odoo repo, or set KCTL_ODOO_REPO=/path/to/repo",
            err=True,
        )
        raise typer.Exit(1)
    return p


def _find_bundle(install_dir: Path, name: str) -> Path:
    """Find a bundle file by name, or exit with error."""
    for ext in (".yaml", ".yml"):
        path = install_dir / f"{name}{ext}"
        if path.exists():
            return path
    typer.echo(f"Bundle not found: {name} (looked in {install_dir})", err=True)
    raise typer.Exit(1)


@app.command("list")
def list_(
    ctx: typer.Context,
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
) -> None:
    """List all available bundles."""
    actx: AppContext = ctx.obj
    out = actx.output
    install_dir = _resolve_install_dir(dir_path)

    bundles = discover_bundles(install_dir)
    if not bundles:
        out.info("No bundles found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for b in bundles:
        groups = len(b.groups) if not b.is_flat else 0
        defaults = len(b.default) if not b.is_flat else 0
        total = b.total_modules
        fmt = "flat" if b.is_flat else "groups"

        rows.append(
            [
                b.name,
                fmt,
                str(groups),
                str(defaults),
                str(total),
            ]
        )
        json_data.append(
            {
                "name": b.name,
                "format": fmt,
                "groups": groups,
                "default_groups": defaults,
                "total_modules": total,
            }
        )

    out.table(
        f"Bundles ({len(bundles)})",
        [
            ("Name", "cyan"),
            ("Format", "dim"),
            ("Groups", ""),
            ("Default", ""),
            ("Modules", "green"),
        ],
        rows,
        json_data,
    )


@app.command("show")
def show(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Bundle name (e.g., oca-server)")],
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
) -> None:
    """Show bundle details: groups, dependencies, and modules."""
    actx: AppContext = ctx.obj
    out = actx.output
    install_dir = _resolve_install_dir(dir_path)
    path = _find_bundle(install_dir, name)
    bundle = load_bundle(path)

    if bundle.is_flat:
        sections = [
            (
                "Bundle",
                [
                    ("Name", bundle.name),
                    ("Format", "flat list"),
                    ("Modules", str(len(bundle.flat_modules))),
                ],
            ),
            ("Modules", [(m, "") for m in bundle.flat_modules]),
        ]
        json_obj = {
            "name": bundle.name,
            "format": "flat",
            "modules": bundle.flat_modules,
        }
    else:
        info_pairs = [
            ("Name", bundle.name),
            ("Description", bundle.description or "-"),
            ("Groups", str(len(bundle.groups))),
            ("Default", ", ".join(bundle.default)),
            ("Total Modules", str(bundle.total_modules)),
        ]
        if bundle.requires:
            info_pairs.append(("Requires", ", ".join(bundle.requires)))

        group_pairs = []
        for gname, group in bundle.groups.items():
            is_default = gname in bundle.default
            marker = " *" if is_default else ""
            deps = f" (depends: {', '.join(group.depends)})" if group.depends else ""
            group_pairs.append(
                (
                    f"{gname}{marker}",
                    f"{len(group.modules)} modules{deps}",
                )
            )

        sections = [
            ("Bundle", info_pairs),
            ("Groups (* = default)", group_pairs),
        ]

        json_obj = {
            "name": bundle.name,
            "description": bundle.description,
            "requires": bundle.requires,
            "default_groups": bundle.default,
            "groups": {
                gname: {
                    "description": g.description,
                    "depends": g.depends,
                    "modules": g.modules,
                }
                for gname, g in bundle.groups.items()
            },
        }

    out.detail(f"Bundle: {bundle.name}", sections, json_obj)


@app.command("modules")
def modules_cmd(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Bundle name")],
    groups: Annotated[str | None, typer.Option("--groups", "-g", help="Comma-separated groups or 'all'")] = None,
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
) -> None:
    """Resolve bundle to a comma-separated module list (CI/CD compatible)."""
    actx: AppContext = ctx.obj
    install_dir = _resolve_install_dir(dir_path)
    path = _find_bundle(install_dir, name)
    bundle = load_bundle(path)

    group_list = groups.split(",") if groups else None
    mods = resolve_modules(bundle, group_list)

    if actx.json_mode:
        actx.output.raw_json(mods)
    else:
        typer.echo(",".join(mods))


@app.command("groups")
def groups_cmd(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Bundle name")],
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
) -> None:
    """List groups in a bundle with module counts."""
    actx: AppContext = ctx.obj
    out = actx.output
    install_dir = _resolve_install_dir(dir_path)
    path = _find_bundle(install_dir, name)
    bundle = load_bundle(path)

    if bundle.is_flat:
        out.info(f"Bundle '{name}' is a flat list with no groups.")
        return

    rows = []
    json_data = []
    for gname, group in bundle.groups.items():
        is_default = gname in bundle.default
        rows.append(
            [
                gname,
                "[green]yes[/green]" if is_default else "",
                str(len(group.modules)),
                ", ".join(group.depends) if group.depends else "-",
                group.description[:50] if group.description else "-",
            ]
        )
        json_data.append(
            {
                "name": gname,
                "default": is_default,
                "module_count": len(group.modules),
                "depends": group.depends,
                "description": group.description,
            }
        )

    out.table(
        f"Groups in {bundle.name} ({len(bundle.groups)})",
        [
            ("Group", "cyan"),
            ("Default", ""),
            ("Modules", "green"),
            ("Depends", "dim"),
            ("Description", "dim"),
        ],
        rows,
        json_data,
    )


@app.command("status")
def status(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Bundle name")],
    groups: Annotated[str | None, typer.Option("--groups", "-g", help="Comma-separated groups or 'all'")] = None,
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
) -> None:
    """Compare bundle modules against the remote Odoo instance."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    install_dir = _resolve_install_dir(dir_path)
    path = _find_bundle(install_dir, name)
    bundle = load_bundle(path)

    group_list = groups.split(",") if groups else None
    expected_modules = resolve_modules(bundle, group_list)

    if not expected_modules:
        out.info("No modules resolved from bundle.")
        return

    # Query installed modules from remote
    installed = c.search_read(
        "ir.module.module",
        domain=[("name", "in", expected_modules), ("state", "=", "installed")],
        fields=["name"],
    )
    installed_names = {m["name"] for m in installed}

    rows = []
    json_data = []
    missing_count = 0
    for mod in expected_modules:
        is_installed = mod in installed_names
        status_str = "[green]installed[/green]" if is_installed else "[red]missing[/red]"
        if not is_installed:
            missing_count += 1
        rows.append([mod, status_str])
        json_data.append({"module": mod, "installed": is_installed})

    title = f"Bundle Status: {bundle.name} ({len(expected_modules)} modules)"
    if missing_count:
        title += f" - [red]{missing_count} missing[/red]"
    else:
        title += " - [green]all installed[/green]"

    out.table(
        title,
        [("Module", ""), ("Status", "")],
        rows,
        json_data,
    )


@app.command("install")
def install(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Bundle name")],
    groups: Annotated[str | None, typer.Option("--groups", "-g", help="Comma-separated groups or 'all'")] = None,
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be installed without installing")] = False,
) -> None:
    """Install missing bundle modules on the remote Odoo instance."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    install_dir = _resolve_install_dir(dir_path)
    path = _find_bundle(install_dir, name)
    bundle = load_bundle(path)

    group_list = groups.split(",") if groups else None
    expected_modules = resolve_modules(bundle, group_list)

    if not expected_modules:
        out.info("No modules resolved from bundle.")
        return

    # Find missing modules
    installed = c.search_read(
        "ir.module.module",
        domain=[("name", "in", expected_modules), ("state", "=", "installed")],
        fields=["name"],
    )
    installed_names = {m["name"] for m in installed}
    missing = [m for m in expected_modules if m not in installed_names]

    if not missing:
        out.success(f"All {len(expected_modules)} modules from '{bundle.name}' are already installed.")
        if actx.json_mode:
            out.raw_json({"installed": len(expected_modules), "missing": 0, "modules_installed": []})
        return

    if dry_run:
        out.info(f"Would install {len(missing)} modules: {', '.join(missing)}")
        if actx.json_mode:
            out.raw_json({"dry_run": True, "modules": missing})
        return

    # Find module IDs for missing modules
    to_install = c.search_read(
        "ir.module.module",
        domain=[("name", "in", missing)],
        fields=["id", "name", "state"],
    )

    if not to_install:
        out.error(f"Modules not found in Odoo module list: {', '.join(missing)}")
        out.info("Run 'kctl-odoo maintenance update-list' to refresh the module list.")
        raise typer.Exit(1)

    found_names = {m["name"] for m in to_install}
    not_found = [m for m in missing if m not in found_names]
    if not_found:
        out.warn(f"Modules not found in Odoo: {', '.join(not_found)}")

    install_modules = [m for m in to_install if m["state"] != "installed"]
    install_ids = [m["id"] for m in install_modules]
    install_names = sorted(m["name"] for m in install_modules)
    if not install_ids:
        out.success("All available modules are already installed.")
        return

    out.info(f"Installing {len(install_ids)} modules from '{bundle.name}' (may take several minutes)...")
    # Module install can take 5-10+ min — increase timeout
    import httpx as _httpx

    saved = c._client.timeout
    c._client = _httpx.Client(headers=dict(c._client.headers), timeout=600.0, follow_redirects=True)
    try:
        c.execute_kw("ir.module.module", "button_immediate_install", [install_ids])
    finally:
        c._client = _httpx.Client(headers=dict(c._client.headers), timeout=saved, follow_redirects=True)
    out.success(f"Installed {len(install_ids)} modules: {', '.join(install_names)}")

    if actx.json_mode:
        out.raw_json(
            {
                "installed": len(install_ids),
                "modules": install_names,
                "not_found": not_found,
            }
        )


@app.command("diff")
def diff(
    ctx: typer.Context,
    bundle_a: Annotated[str, typer.Argument(help="First bundle name")],
    bundle_b: Annotated[str, typer.Argument(help="Second bundle name")],
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
) -> None:
    """Diff two bundles showing modules unique to each and shared."""
    actx: AppContext = ctx.obj
    out = actx.output
    install_dir = _resolve_install_dir(dir_path)

    path_a = _find_bundle(install_dir, bundle_a)
    path_b = _find_bundle(install_dir, bundle_b)
    ba = load_bundle(path_a)
    bb = load_bundle(path_b)

    mods_a = set(resolve_modules(ba, ["all"]))
    mods_b = set(resolve_modules(bb, ["all"]))

    only_a = sorted(mods_a - mods_b)
    only_b = sorted(mods_b - mods_a)
    shared = sorted(mods_a & mods_b)

    sections = [
        (
            "Summary",
            [
                (ba.name, f"{len(mods_a)} modules"),
                (bb.name, f"{len(mods_b)} modules"),
                ("Shared", str(len(shared))),
                (f"Only in {ba.name}", str(len(only_a))),
                (f"Only in {bb.name}", str(len(only_b))),
            ],
        ),
    ]

    if only_a:
        sections.append((f"Only in {ba.name}", [(m, "") for m in only_a]))
    if only_b:
        sections.append((f"Only in {bb.name}", [(m, "") for m in only_b]))

    json_obj = {
        "bundle_a": ba.name,
        "bundle_b": bb.name,
        "only_a": only_a,
        "only_b": only_b,
        "shared": shared,
    }

    out.detail(f"Diff: {ba.name} vs {bb.name}", sections, json_obj)
