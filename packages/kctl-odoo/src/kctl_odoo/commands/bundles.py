"""Bundle management commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import yaml

from kctl_odoo.core.bundles import (
    Bundle,
    discover_bundles,
    discover_profiles,
    get_default_install_dir,
    load_bundle,
    load_profile,
    resolve_modules,
    resolve_profile_modules,
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


def _find_profile(install_dir: Path, name: str) -> Path:
    """Find a profile file by name (with or without 'profile-' prefix), or exit."""
    for prefix in ("profile-", ""):
        for ext in (".yaml", ".yml"):
            path = install_dir / f"{prefix}{name}{ext}"
            if path.exists():
                return path
    typer.echo(f"Profile not found: {name} (looked in {install_dir})", err=True)
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


# ============================================================================
# Profile commands
# ============================================================================


@app.command("list-profiles")
def list_profiles(
    ctx: typer.Context,
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
) -> None:
    """List all deployment profiles with bundle and module counts."""
    actx: AppContext = ctx.obj
    out = actx.output
    install_dir = _resolve_install_dir(dir_path)

    profiles = discover_profiles(install_dir)
    if not profiles:
        out.info("No profiles found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for p in profiles:
        modules = resolve_profile_modules(p, install_dir)
        extends = p.extends or "-"
        rows.append(
            [
                p.name,
                str(len(p.bundles)),
                str(len(modules)),
                extends,
                (p.description or "-")[:60],
            ]
        )
        json_data.append(
            {
                "name": p.name,
                "bundles": len(p.bundles),
                "total_modules": len(modules),
                "extends": p.extends or None,
                "description": p.description,
            }
        )

    out.table(
        f"Profiles ({len(profiles)})",
        [
            ("Name", "cyan"),
            ("Bundles", ""),
            ("Modules", "green"),
            ("Extends", "dim"),
            ("Description", "dim"),
        ],
        rows,
        json_data,
    )


@app.command("show-profile")
def show_profile(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name (e.g., distribution, retail)")],
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
) -> None:
    """Show profile details: bundles, resolved modules, and foundation overlap."""
    actx: AppContext = ctx.obj
    out = actx.output
    install_dir = _resolve_install_dir(dir_path)

    path = _find_profile(install_dir, name)
    profile = load_profile(path)
    modules = resolve_profile_modules(profile, install_dir)

    # Resolve foundation modules to show what's added on top
    foundation_path = install_dir / "profile-foundation.yaml"
    foundation_modules: set[str] = set()
    if foundation_path.exists():
        fp = load_profile(foundation_path)
        foundation_modules = set(resolve_profile_modules(fp, install_dir))

    profile_only = sorted(set(modules) - foundation_modules)

    info_pairs = [
        ("Name", profile.name),
        ("Description", (profile.description or "-")[:120]),
        ("Bundles", str(len(profile.bundles))),
        ("Total Modules", str(len(modules))),
        ("Foundation Modules", str(len(foundation_modules & set(modules)))),
        ("Profile-specific Modules", str(len(profile_only))),
    ]
    if profile.extends:
        info_pairs.insert(2, ("Extends", profile.extends))

    sections = [
        ("Profile", info_pairs),
        ("Bundles", [(b, "") for b in profile.bundles]),
    ]
    if profile_only:
        sections.append(("Modules beyond foundation", [(m, "") for m in profile_only]))

    json_obj = {
        "name": profile.name,
        "description": profile.description,
        "extends": profile.extends or None,
        "bundles": profile.bundles,
        "total_modules": len(modules),
        "foundation_modules": len(foundation_modules & set(modules)),
        "profile_specific_modules": profile_only,
        "all_modules": modules,
    }

    out.detail(f"Profile: {profile.name}", sections, json_obj)


@app.command("compare-profiles")
def compare_profiles(
    ctx: typer.Context,
    profiles: Annotated[list[str], typer.Argument(help="Two or more profile names to compare")],
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
    show_modules: Annotated[bool, typer.Option("--modules", "-m", help="Show individual module lists")] = False,
) -> None:
    """Compare features between deployment profiles.

    Shows shared foundation, unique bundles/modules per profile, and a
    side-by-side bundle matrix.

    Examples:
        kctl-odoo bundles compare-profiles distribution retail manufacturing
        kctl-odoo bundles compare-profiles distribution trading --modules
    """
    actx: AppContext = ctx.obj
    out = actx.output
    install_dir = _resolve_install_dir(dir_path)

    if len(profiles) < 2:
        out.error("Provide at least two profile names to compare.")
        raise typer.Exit(1)

    # Load all profiles
    loaded: dict[str, dict] = {}
    for pname in profiles:
        path = _find_profile(install_dir, pname)
        profile = load_profile(path)
        modules = resolve_profile_modules(profile, install_dir)
        loaded[profile.name] = {
            "profile": profile,
            "bundles": set(profile.bundles),
            "modules": set(modules),
            "modules_ordered": modules,
        }

    profile_names = list(loaded.keys())

    # Compute shared vs unique modules
    all_module_sets = [d["modules"] for d in loaded.values()]
    shared_modules = sorted(set.intersection(*all_module_sets))
    union_modules = sorted(set.union(*all_module_sets))

    # Compute shared vs unique bundles
    all_bundle_sets = [d["bundles"] for d in loaded.values()]
    shared_bundles = sorted(set.intersection(*all_bundle_sets))
    all_bundles = sorted(set.union(*all_bundle_sets))

    # --- Summary table ---
    summary_rows = []
    summary_json = []
    for pname in profile_names:
        d = loaded[pname]
        unique_mods = sorted(d["modules"] - set(shared_modules))
        unique_bundles = sorted(d["bundles"] - set(shared_bundles))
        summary_rows.append(
            [
                pname,
                str(len(d["bundles"])),
                str(len(d["modules"])),
                str(len(shared_modules)),
                str(len(unique_mods)),
            ]
        )
        summary_json.append(
            {
                "profile": pname,
                "bundles": len(d["bundles"]),
                "total_modules": len(d["modules"]),
                "shared_modules": len(shared_modules),
                "unique_modules": len(unique_mods),
                "unique_module_list": unique_mods,
                "unique_bundles": unique_bundles,
            }
        )

    out.table(
        f"Profile Comparison ({len(profile_names)} profiles)",
        [
            ("Profile", "cyan"),
            ("Bundles", ""),
            ("Total Modules", "green"),
            ("Shared", "dim"),
            ("Unique", "yellow"),
        ],
        summary_rows,
        summary_json if actx.json_mode else None,
    )

    # --- Bundle matrix ---
    matrix_rows = []
    matrix_json = []
    for bundle_name in all_bundles:
        row = [bundle_name]
        entry: dict = {"bundle": bundle_name}
        for pname in profile_names:
            has_it = bundle_name in loaded[pname]["bundles"]
            row.append("[green]yes[/green]" if has_it else "[dim]-[/dim]")
            entry[pname] = has_it
        matrix_rows.append(row)
        matrix_json.append(entry)

    cols: list[tuple[str, str]] = [("Bundle", "")]
    for pname in profile_names:
        cols.append((pname, "cyan"))

    out.table(
        "Bundle Matrix",
        cols,
        matrix_rows,
        matrix_json if actx.json_mode else None,
    )

    # --- Unique modules per profile ---
    if show_modules:
        sections = []
        for pname in profile_names:
            d = loaded[pname]
            unique = sorted(d["modules"] - set(shared_modules))
            if unique:
                sections.append(
                    (
                        f"Only in {pname} ({len(unique)})",
                        [(m, "") for m in unique],
                    )
                )
        if sections:
            out.detail("Unique Modules", sections, None)

    # --- JSON output ---
    if actx.json_mode:
        out.raw_json(
            {
                "profiles": summary_json,
                "shared_bundles": shared_bundles,
                "shared_modules": shared_modules,
                "shared_module_count": len(shared_modules),
                "union_module_count": len(union_modules),
                "bundle_matrix": matrix_json,
            }
        )


# ============================================================================
# Bundle authoring helpers
# ============================================================================


def _create_bundle_yaml(
    install_dir: Path,
    name: str,
    description: str = "",
    requires: list[str] | None = None,
) -> Path:
    """Create a new grouped-format bundle YAML file.

    Raises FileExistsError if the file already exists.
    """
    path = install_dir / f"{name}.yaml"
    if path.exists():
        raise FileExistsError(f"Bundle file already exists: {path}")

    data: dict = {
        "name": name,
        "description": description,
        "groups": {
            "core": {
                "description": "",
                "modules": [],
            }
        },
        "default": ["core"],
    }
    if requires:
        data["requires"] = requires

    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")
    return path


def _add_module_to_bundle(path: Path, module: str, group: str) -> None:
    """Add a module to a group in a bundle YAML file.

    Raises ValueError if module already exists in any group.
    Creates the group if it does not exist.
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    if not isinstance(data, dict) or "groups" not in data:
        raise ValueError(f"Bundle file is not grouped format: {path}")

    groups = data["groups"]

    # Check for duplicates in ALL groups
    for gname, gdata in groups.items():
        existing_modules = gdata.get("modules", []) if isinstance(gdata, dict) else []
        if module in existing_modules:
            raise ValueError(f"Module '{module}' already exists in group '{gname}'")

    # Create group if it doesn't exist
    if group not in groups:
        groups[group] = {"description": "", "modules": [module]}
    else:
        gdata = groups[group]
        if not isinstance(gdata, dict):
            groups[group] = {"description": "", "modules": [module]}
        else:
            mods = gdata.get("modules", [])
            mods.append(module)
            gdata["modules"] = mods

    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")


def _remove_module_from_bundle(path: Path, module: str) -> None:
    """Remove a module from a bundle YAML file (searches all groups).

    Raises ValueError if module is not found in any group.
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    if not isinstance(data, dict) or "groups" not in data:
        raise ValueError(f"Bundle file is not grouped format: {path}")

    groups = data["groups"]
    found = False

    for _gname, gdata in groups.items():
        if isinstance(gdata, dict):
            mods = gdata.get("modules", [])
            if module in mods:
                mods.remove(module)
                gdata["modules"] = mods
                found = True
                break

    if not found:
        raise ValueError(f"Module '{module}' not found in bundle '{path.stem}'")

    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")


def _create_profile_yaml(
    install_dir: Path,
    name: str,
    description: str = "",
    bundles: list[str] | None = None,
    extends: str = "",
) -> Path:
    """Create a new profile YAML file (adds 'profile-' prefix if not present).

    Raises FileExistsError if the file already exists.
    """
    if not name.startswith("profile-"):
        filename = f"profile-{name}.yaml"
    else:
        filename = f"{name}.yaml"

    path = install_dir / filename

    if path.exists():
        raise FileExistsError(f"Profile file already exists: {path}")

    profile_name = filename[: -len(".yaml")]  # strip .yaml

    default_bundles: list[str] = (
        bundles
        if bundles is not None
        else [
            "core-mandatory",
            "core-localization",
            "oca-mandatory",
            "private-mandatory",
        ]
    )

    data: dict = {
        "name": profile_name,
        "description": description,
        "bundles": default_bundles,
    }
    if extends:
        data["extends"] = extends

    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")
    return path


# ============================================================================
# Bundle authoring commands
# ============================================================================


@app.command("create")
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Bundle name (e.g., private-retail)")],
    description: Annotated[str, typer.Option("--description", "-d", help="Bundle description")] = "",
    requires: Annotated[str | None, typer.Option("--requires", help="Comma-separated required bundles")] = None,
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
) -> None:
    """Create a new grouped-format bundle YAML file."""
    actx: AppContext = ctx.obj
    install_dir = _resolve_install_dir(dir_path)
    requires_list = [r.strip() for r in requires.split(",")] if requires else None

    try:
        path = _create_bundle_yaml(install_dir, name, description, requires_list)
        actx.output.success(f"Created bundle: {path}")
    except FileExistsError as exc:
        actx.output.error(str(exc))
        raise typer.Exit(1)


@app.command("add-module")
def add_module(
    ctx: typer.Context,
    bundle: Annotated[str, typer.Argument(help="Bundle name (e.g., private-retail)")],
    module: Annotated[str, typer.Argument(help="Module name to add")],
    group: Annotated[str, typer.Option("--group", "-g", help="Group to add the module to")] = "core",
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
) -> None:
    """Add a module to a group in an existing bundle."""
    actx: AppContext = ctx.obj
    install_dir = _resolve_install_dir(dir_path)
    path = _find_bundle(install_dir, bundle)

    try:
        _add_module_to_bundle(path, module, group)
        actx.output.success(f"Added '{module}' to group '{group}' in {path.name}")
    except ValueError as exc:
        actx.output.error(str(exc))
        raise typer.Exit(1)


@app.command("remove-module")
def remove_module(
    ctx: typer.Context,
    bundle: Annotated[str, typer.Argument(help="Bundle name (e.g., private-retail)")],
    module: Annotated[str, typer.Argument(help="Module name to remove")],
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
) -> None:
    """Remove a module from a bundle (searches all groups)."""
    actx: AppContext = ctx.obj
    install_dir = _resolve_install_dir(dir_path)
    path = _find_bundle(install_dir, bundle)

    try:
        _remove_module_from_bundle(path, module)
        actx.output.success(f"Removed '{module}' from {path.name}")
    except ValueError as exc:
        actx.output.error(str(exc))
        raise typer.Exit(1)


@app.command("create-profile")
def create_profile(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name (e.g., retail, distribution)")],
    description: Annotated[str, typer.Option("--description", "-d", help="Profile description")] = "",
    bundles_list: Annotated[str | None, typer.Option("--bundles", "-b", help="Comma-separated bundle names")] = None,
    extends: Annotated[str, typer.Option("--extends", help="Profile to extend")] = "",
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
) -> None:
    """Create a new deployment profile YAML file."""
    actx: AppContext = ctx.obj
    install_dir = _resolve_install_dir(dir_path)
    bundles = [b.strip() for b in bundles_list.split(",")] if bundles_list else None

    try:
        path = _create_profile_yaml(install_dir, name, description, bundles, extends)
        actx.output.success(f"Created profile: {path}")
    except FileExistsError as exc:
        actx.output.error(str(exc))
        raise typer.Exit(1)


# ============================================================================
# Validation / graph / search helpers
# ============================================================================


def _find_module_in_bundles(install_dir: Path, module: str) -> list[tuple[str, str]]:
    """Return all (bundle_name, group_name) pairs that contain *module*.

    For flat bundles the group is reported as ``"(flat)"``.
    """
    matches: list[tuple[str, str]] = []
    for bundle in discover_bundles(install_dir):
        if bundle.is_flat:
            if module in bundle.flat_modules:
                matches.append((bundle.name, "(flat)"))
        else:
            for gname, group in bundle.groups.items():
                if module in group.modules:
                    matches.append((bundle.name, gname))
    return matches


def _build_bundle_graph(install_dir: Path) -> dict[str, list[str]]:
    """Return ``{bundle_name: requires_list}`` for every bundle in *install_dir*."""
    graph: dict[str, list[str]] = {}
    for bundle in discover_bundles(install_dir):
        graph[bundle.name] = list(bundle.requires)
    return graph


def _has_circular_dep(
    bundle: Bundle,
    group: str,
    visited: set[str],
    chain: list[str],
) -> bool:
    """Recursively detect circular group-level dependencies within a single bundle.

    Returns ``True`` (and appends the offending group to *chain*) when a cycle
    is found, ``False`` otherwise.
    """
    if group in visited:
        chain.append(group)
        return True
    if group not in bundle.groups:
        return False

    visited.add(group)
    chain.append(group)
    for dep in bundle.groups[group].depends:
        if _has_circular_dep(bundle, dep, visited, chain):
            return True
    chain.pop()
    visited.discard(group)
    return False


# ============================================================================
# validate command
# ============================================================================


@app.command("validate")
def validate_bundles(
    ctx: typer.Context,
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
) -> None:
    """Validate ALL bundle YAMLs: circular deps, duplicate modules, resolution errors."""
    actx: AppContext = ctx.obj
    out = actx.output
    install_dir = _resolve_install_dir(dir_path)

    bundles = discover_bundles(install_dir)
    if not bundles:
        out.info("No bundles found.")
        return

    rows = []
    json_data = []
    has_errors = False

    for bundle in bundles:
        issues: list[str] = []

        if bundle.is_flat:
            module_count = len(bundle.flat_modules)
            # Flat bundles have no groups — nothing to validate structurally.
        else:
            module_count = bundle.total_modules

            # 1. Circular group dependency check
            for gname in bundle.groups:
                chain: list[str] = []
                if _has_circular_dep(bundle, gname, set(), chain):
                    issues.append(f"circular dep in group '{gname}': {' -> '.join(chain)}")

            # 2. Duplicate modules across groups
            seen: dict[str, str] = {}
            for gname, group in bundle.groups.items():
                for mod in group.modules:
                    if mod in seen:
                        issues.append(f"duplicate module '{mod}' in groups '{seen[mod]}' and '{gname}'")
                    else:
                        seen[mod] = gname

            # 3. Resolution errors — try resolving all groups
            try:
                resolve_modules(bundle, ["all"])
            except Exception as exc:
                issues.append(f"resolution error: {exc}")

        status_str = "[red]FAIL[/red]" if issues else "[green]OK[/green]"
        if issues:
            has_errors = True

        rows.append(
            [
                bundle.name,
                str(module_count),
                status_str,
                "; ".join(issues) if issues else "-",
            ]
        )
        json_data.append(
            {
                "bundle": bundle.name,
                "modules": module_count,
                "ok": not bool(issues),
                "issues": issues,
            }
        )

    title = f"Bundle Validation ({len(bundles)} bundles)"
    if has_errors:
        title += " - [red]ERRORS FOUND[/red]"
    else:
        title += " - [green]all valid[/green]"

    out.table(
        title,
        [
            ("Bundle", "cyan"),
            ("Modules", "green"),
            ("Status", ""),
            ("Issues", "red"),
        ],
        rows,
        json_data,
    )

    if has_errors:
        raise typer.Exit(1)


# ============================================================================
# graph command
# ============================================================================


@app.command("graph")
def graph(
    ctx: typer.Context,
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
    fmt: Annotated[str, typer.Option("--format", "-f", help="Output format: text, dot, json")] = "text",
) -> None:
    """Show bundle dependency graph derived from 'requires' chains."""
    actx: AppContext = ctx.obj
    out = actx.output
    install_dir = _resolve_install_dir(dir_path)

    dep_graph = _build_bundle_graph(install_dir)

    if fmt == "json" or actx.json_mode:
        out.raw_json(dep_graph)
        return

    if fmt == "dot":
        lines = ["digraph bundles {"]
        for bundle_name, requires in sorted(dep_graph.items()):
            for req in requires:
                lines.append(f'    "{bundle_name}" -> "{req}";')
        lines.append("}")
        typer.echo("\n".join(lines))
        return

    # Default: text table
    rows = []
    json_rows = []
    for bundle_name, requires in sorted(dep_graph.items()):
        requires_str = ", ".join(requires) if requires else "-"
        rows.append([bundle_name, requires_str])
        json_rows.append({"bundle": bundle_name, "requires": requires})

    out.table(
        f"Bundle Dependency Graph ({len(dep_graph)} bundles)",
        [
            ("Bundle", "cyan"),
            ("Requires", "dim"),
        ],
        rows,
        json_rows,
    )


# ============================================================================
# find-module command
# ============================================================================


@app.command("find-module")
def find_module(
    ctx: typer.Context,
    module: Annotated[str, typer.Argument(help="Module name to find (e.g., sale_management)")],
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
) -> None:
    """Find which bundle(s) and group(s) contain a specific module."""
    actx: AppContext = ctx.obj
    out = actx.output
    install_dir = _resolve_install_dir(dir_path)

    matches = _find_module_in_bundles(install_dir, module)

    if not matches:
        out.info(f"Module '{module}' not found in any bundle.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = [[bundle_name, group_name] for bundle_name, group_name in matches]
    json_data = [{"bundle": b, "group": g} for b, g in matches]

    out.table(
        f"Module '{module}' found in {len(matches)} location(s)",
        [
            ("Bundle", "cyan"),
            ("Group", "dim"),
        ],
        rows,
        json_data,
    )
