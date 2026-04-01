"""Deployment profile management commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from kctl_odoo.core.bundles import (
    _find_bundle_file,
    _parse_bundle_entry,
    discover_profiles,
    get_default_install_dir,
    load_profile,
    resolve_profile_modules,
)
from kctl_odoo.core.callbacks import AppContext

app = typer.Typer(help="Manage deployment profiles (bundle sets for different company types).")


def _deprecation_warning(old: str, new: str) -> None:
    typer.echo(
        f"Warning: 'kctl-odoo config profiles {old}' is deprecated. Use 'kctl-odoo bundles {new}' instead.",
        err=True,
    )


def _resolve_install_dir(dir_path: str | None) -> Path:
    p = Path(dir_path) if dir_path else get_default_install_dir()
    if not p.is_dir():
        typer.echo(
            f"Install directory not found: {p}\nRun from the kodemeio-odoo repo, or set KCTL_ODOO_REPO=/path/to/repo",
            err=True,
        )
        raise typer.Exit(1)
    return p


def _find_profile(install_dir: Path, name: str) -> Path:
    """Find a profile file by name."""
    # Try with and without profile- prefix
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
    """List all available deployment profiles."""
    _deprecation_warning("list", "list-profiles")
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
        total = len(resolve_profile_modules(p, install_dir))
        rows.append(
            [
                p.name.removeprefix("profile-"),
                str(len(p.bundles)),
                str(total),
                (p.description[:60] + "...") if len(p.description) > 63 else p.description or "-",
            ]
        )
        json_data.append(
            {
                "name": p.name,
                "bundles": len(p.bundles),
                "total_modules": total,
                "description": p.description,
            }
        )

    out.table(
        f"Deployment Profiles ({len(profiles)})",
        [
            ("Profile", "cyan"),
            ("Bundles", ""),
            ("Modules", "green"),
            ("Description", "dim"),
        ],
        rows,
        json_data,
    )


@app.command("show")
def show(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name (e.g., manufacturing)")],
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
) -> None:
    """Show profile details: bundles, resolved modules."""
    _deprecation_warning("show", "show-profile")
    actx: AppContext = ctx.obj
    out = actx.output
    install_dir = _resolve_install_dir(dir_path)
    path = _find_profile(install_dir, name)
    profile = load_profile(path)

    modules = resolve_profile_modules(profile, install_dir)

    sections = [
        (
            "Profile",
            [
                ("Name", profile.name),
                ("Description", profile.description or "-"),
                ("Bundles", str(len(profile.bundles))),
                ("Total Modules", str(len(modules))),
            ],
        ),
        ("Bundles", [(b, "") for b in profile.bundles]),
    ]

    json_obj = {
        "name": profile.name,
        "description": profile.description,
        "bundles": profile.bundles,
        "total_modules": len(modules),
        "modules": modules,
    }

    out.detail(f"Profile: {profile.name}", sections, json_obj)


@app.command("status")
def status(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name")],
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
) -> None:
    """Compare all profile modules against the remote Odoo instance."""
    _deprecation_warning("status", "profile-status")
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    install_dir = _resolve_install_dir(dir_path)
    path = _find_profile(install_dir, name)
    profile = load_profile(path)

    expected = resolve_profile_modules(profile, install_dir)
    if not expected:
        out.info("No modules resolved from profile.")
        return

    # Query installed modules
    installed = c.search_read(
        "ir.module.module",
        domain=[("name", "in", expected), ("state", "=", "installed")],
        fields=["name"],
    )
    installed_names = {m["name"] for m in installed}

    missing = [m for m in expected if m not in installed_names]
    installed_list = [m for m in expected if m in installed_names]

    sections = [
        (
            "Summary",
            [
                ("Profile", profile.name),
                ("Expected", str(len(expected))),
                ("Installed", f"[green]{len(installed_list)}[/green]"),
                ("Missing", f"[red]{len(missing)}[/red]" if missing else "[green]0[/green]"),
                (
                    "Compliance",
                    "[green]100%[/green]"
                    if not missing
                    else f"[yellow]{len(installed_list) * 100 // len(expected)}%[/yellow]",
                ),
            ],
        ),
    ]
    if missing:
        sections.append(("Missing Modules", [(m, "[red]not installed[/red]") for m in missing]))

    json_obj = {
        "profile": profile.name,
        "expected": len(expected),
        "installed": len(installed_list),
        "missing_count": len(missing),
        "missing_modules": missing,
        "compliance_pct": round(len(installed_list) * 100 / len(expected), 1) if expected else 100,
    }

    out.detail(f"Profile Status: {profile.name}", sections, json_obj)


@app.command("install")
def install(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name")],
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be installed")] = False,
) -> None:
    """Install all missing profile modules on the remote Odoo instance."""
    _deprecation_warning("install", "profile-install")
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    install_dir = _resolve_install_dir(dir_path)
    path = _find_profile(install_dir, name)
    profile = load_profile(path)

    expected = resolve_profile_modules(profile, install_dir)
    if not expected:
        out.info("No modules resolved from profile.")
        return

    # Find missing
    installed = c.search_read(
        "ir.module.module",
        domain=[("name", "in", expected), ("state", "=", "installed")],
        fields=["name"],
    )
    installed_names = {m["name"] for m in installed}
    missing = [m for m in expected if m not in installed_names]

    if not missing:
        out.success(f"All {len(expected)} modules from profile '{profile.name}' are already installed.")
        if actx.json_mode:
            out.raw_json({"installed": len(expected), "missing": 0})
        return

    if dry_run:
        out.info(f"Would install {len(missing)} modules for profile '{profile.name}':")
        for m in missing:
            out.text(f"  - {m}")
        if actx.json_mode:
            out.raw_json({"dry_run": True, "modules": missing})
        return

    # Find installable modules
    to_install = c.search_read(
        "ir.module.module",
        domain=[("name", "in", missing)],
        fields=["id", "name", "state"],
    )

    found_names = {m["name"] for m in to_install}
    not_found = [m for m in missing if m not in found_names]
    if not_found:
        out.warn(
            f"{len(not_found)} modules not found in Odoo:"
            f" {', '.join(not_found[:10])}{'...' if len(not_found) > 10 else ''}"
        )
        out.info("Run 'kctl-odoo maintenance update-list' to refresh the module list.")

    install_ids = [m["id"] for m in to_install if m["state"] != "installed"]
    if not install_ids:
        out.success("All available modules are already installed.")
        return

    out.info(f"Installing {len(install_ids)} modules for profile '{profile.name}'...")
    c.execute_kw("ir.module.module", "button_immediate_install", [install_ids])
    out.success(f"Installed {len(install_ids)} modules for profile '{profile.name}'.")

    if actx.json_mode:
        out.raw_json(
            {
                "installed": len(install_ids),
                "modules": list(found_names),
                "not_found": not_found,
            }
        )


@app.command("validate")
def validate(
    ctx: typer.Context,
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
) -> None:
    """Validate all profiles: check that referenced bundles exist and resolve correctly."""
    _deprecation_warning("validate", "profile-validate")
    actx: AppContext = ctx.obj
    out = actx.output
    install_dir = _resolve_install_dir(dir_path)

    profiles = discover_profiles(install_dir)
    if not profiles:
        out.info("No profiles found.")
        return

    rows = []
    json_data = []
    errors = 0

    for p in profiles:
        profile_name = p.name.removeprefix("profile-")
        issues: list[str] = []

        # Check extends reference
        if p.extends:
            from kctl_odoo.core.bundles import _find_profile_file

            parent = _find_profile_file(install_dir, p.extends)
            if not parent:
                issues.append(f"extends '{p.extends}' not found")

        # Check each bundle reference exists
        for entry in p.bundles:
            bundle_name, _groups = _parse_bundle_entry(entry)
            if _find_bundle_file(install_dir, bundle_name) is None:
                issues.append(f"bundle '{bundle_name}' not found")

        # Try to resolve
        try:
            modules = resolve_profile_modules(p, install_dir)
            mod_count = len(modules)
        except Exception as e:
            issues.append(f"resolution failed: {e}")
            mod_count = 0

        if mod_count == 0 and not p.extends:
            issues.append("resolves to 0 modules")

        if issues:
            errors += len(issues)
            status_str = f"[red]{len(issues)} issues[/red]"
        else:
            status_str = "[green]OK[/green]"

        rows.append(
            [
                profile_name,
                str(len(p.bundles)),
                str(mod_count),
                p.extends or "-",
                status_str,
                "; ".join(issues) if issues else "-",
            ]
        )
        json_data.append(
            {
                "name": profile_name,
                "bundles": len(p.bundles),
                "modules": mod_count,
                "extends": p.extends or None,
                "valid": len(issues) == 0,
                "issues": issues,
            }
        )

    title = f"Profile Validation ({len(profiles)} profiles)"
    if errors:
        title += f" - [red]{errors} issues[/red]"
    else:
        title += " - [green]all valid[/green]"

    out.table(
        title,
        [
            ("Profile", "cyan"),
            ("Bundles", ""),
            ("Modules", ""),
            ("Extends", "dim"),
            ("Status", ""),
            ("Issues", "dim"),
        ],
        rows,
        json_data,
    )

    if errors:
        raise typer.Exit(1)
