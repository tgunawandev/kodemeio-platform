"""Deployment status and verification commands."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer

from kctl_odoo.core.bundles import (
    get_default_install_dir,
    load_profile,
    resolve_profile_modules,
)
from kctl_odoo.core.callbacks import AppContext

app = typer.Typer(help="Deployment status and verification.")


@app.command()
def status(
    ctx: typer.Context,
) -> None:
    """Show deployment status overview.

    Displays Odoo version, database name, installed module count,
    active user count, and key system parameters.

    Examples:
      kctl-odoo deploy status
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Gather data
    version_info = c.version_info()
    server_version = version_info.get("server_version", "unknown")
    server_serie = version_info.get("server_serie", "unknown")

    installed_count = c.search_count(
        "ir.module.module",
        domain=[("state", "=", "installed")],
    )

    active_user_count = c.search_count(
        "res.users",
        domain=[("active", "=", True)],
    )

    # Fetch key system parameters
    param_keys = ["web.base.url", "database.uuid", "database.create_date"]
    params: dict[str, str] = {}
    for key in param_keys:
        records = c.search_read(
            "ir.config_parameter",
            domain=[("key", "=", key)],
            fields=["value"],
        )
        if records:
            params[key] = str(records[0].get("value", ""))

    json_data = {
        "server_version": server_version,
        "server_serie": server_serie,
        "database": c.database,
        "installed_modules": installed_count,
        "active_users": active_user_count,
        "web_base_url": params.get("web.base.url", ""),
        "database_uuid": params.get("database.uuid", ""),
        "database_create_date": params.get("database.create_date", ""),
    }

    out.detail(
        "Deployment Status",
        [
            (
                "Server",
                [
                    ("Odoo Version", server_version),
                    ("Series", server_serie),
                    ("Base URL", params.get("web.base.url", "(not set)")),
                ],
            ),
            (
                "Database",
                [
                    ("Name", c.database),
                    ("UUID", params.get("database.uuid", "(not set)")),
                    ("Created", params.get("database.create_date", "(unknown)")),
                ],
            ),
            (
                "Counts",
                [
                    ("Installed Modules", str(installed_count)),
                    ("Active Users", str(active_user_count)),
                ],
            ),
        ],
        data_for_json=json_data,
    )


@app.command()
def verify(
    ctx: typer.Context,
    profile_name: Annotated[str, typer.Argument(help="Deployment profile name (e.g. profile-found)")],
    install_dir: Annotated[
        Path | None,
        typer.Option("--dir", "-d", help="Install directory containing bundle YAMLs"),
    ] = None,
) -> None:
    """Verify that a remote instance matches a deployment profile.

    Resolves expected modules from the profile's bundle definitions and
    compares against modules actually installed on the server.

    Examples:
      kctl-odoo deploy verify profile-found
      kctl-odoo deploy verify profile-full --dir /path/to/install
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    base_dir = install_dir or get_default_install_dir()

    # Find and load the profile
    profile_path = None
    for ext in (".yaml", ".yml"):
        candidate = base_dir / f"{profile_name}{ext}"
        if candidate.exists():
            profile_path = candidate
            break

    if profile_path is None:
        out.error(f"Profile not found: {profile_name} (searched in {base_dir})")
        raise typer.Exit(1)

    profile = load_profile(profile_path)
    expected_modules = set(resolve_profile_modules(profile, base_dir))

    if not expected_modules:
        out.warn(f"Profile '{profile_name}' resolves to zero modules. Check bundle definitions.")
        raise typer.Exit(1)

    # Fetch installed modules from remote
    installed_records = c.search_read(
        "ir.module.module",
        domain=[("state", "=", "installed")],
        fields=["name"],
        limit=0,
    )
    installed_names = {r["name"] for r in installed_records}

    missing = sorted(expected_modules - installed_names)
    extra = sorted(installed_names - expected_modules)
    matched = sorted(expected_modules & installed_names)

    json_data = {
        "profile": profile_name,
        "expected_count": len(expected_modules),
        "installed_count": len(installed_names),
        "matched": len(matched),
        "missing": missing,
        "extra_count": len(extra),
    }

    if actx.json_mode:
        out.raw_json(json_data)
        return

    match_pct = (len(matched) / len(expected_modules) * 100) if expected_modules else 0

    out.detail(
        f"Verify: {profile_name}",
        [
            (
                "Summary",
                [
                    ("Expected Modules", str(len(expected_modules))),
                    ("Installed Modules", str(len(installed_names))),
                    ("Matched", f"{len(matched)} ({match_pct:.0f}%)"),
                    ("Missing", str(len(missing))),
                    ("Extra (not in profile)", str(len(extra))),
                ],
            ),
        ],
    )

    if missing:
        rows = [[m] for m in missing]
        out.table(
            f"Missing Modules ({len(missing)})",
            [("Module", "red")],
            rows,
        )
    else:
        out.success("All profile modules are installed.")


@app.command()
def changelog(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", "-n", help="Look back N days")] = 7,
) -> None:
    """Show recently installed or upgraded modules.

    Queries ir.module.module for records with write_date in the last N days
    that are currently in 'installed' state.

    Examples:
      kctl-odoo deploy changelog
      kctl-odoo deploy changelog --days 30
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    cutoff = datetime.now(UTC) - timedelta(days=days)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    records = c.search_read(
        "ir.module.module",
        domain=[
            ("state", "=", "installed"),
            ("write_date", ">=", cutoff_str),
        ],
        fields=["name", "shortdesc", "installed_version", "write_date", "state"],
        limit=0,
        order="write_date desc",
    )

    if not records:
        out.info(f"No modules installed or upgraded in the last {days} days.")
        return

    rows = []
    json_data = []
    for r in records:
        write_date = str(r.get("write_date", ""))
        rows.append(
            [
                r["name"],
                r.get("shortdesc") or "",
                r.get("installed_version") or "-",
                write_date,
            ]
        )
        json_data.append(
            {
                "name": r["name"],
                "summary": r.get("shortdesc"),
                "version": r.get("installed_version"),
                "write_date": write_date,
            }
        )

    out.table(
        f"Recently Updated Modules (last {days} days, {len(records)} found)",
        [("Module", ""), ("Summary", ""), ("Version", "dim"), ("Last Modified", "cyan")],
        rows,
        data_for_json=json_data,
    )


@app.command("env")
def env_(
    ctx: typer.Context,
    redact: Annotated[bool, typer.Option("--redact/--no-redact", help="Redact sensitive values")] = True,
) -> None:
    """Show key system parameters (environment configuration).

    Displays web.base.url, database.*, report.*, mail.* parameters.
    Sensitive values are redacted by default.

    Examples:
      kctl-odoo deploy env
      kctl-odoo deploy env --no-redact
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Fetch parameters matching common deployment-relevant prefixes
    prefixes = ["web.base", "database.", "report.", "mail.", "auth_", "server_"]
    all_params: list[dict] = []

    for prefix in prefixes:
        records = c.search_read(
            "ir.config_parameter",
            domain=[("key", "ilike", prefix)],
            fields=["key", "value"],
            limit=0,
            order="key",
        )
        all_params.extend(records)

    # Deduplicate by key (prefixes may overlap)
    seen: dict[str, str] = {}
    for p in all_params:
        key = p["key"]
        if key not in seen:
            seen[key] = str(p.get("value", ""))

    # Sensitive key patterns
    sensitive_patterns = {"password", "secret", "token", "api_key", "private", "smtp_pass"}

    rows = []
    json_data = []
    for key in sorted(seen):
        value = seen[key]
        display_value = value

        if redact:
            key_lower = key.lower()
            if any(s in key_lower for s in sensitive_patterns):
                display_value = "***REDACTED***"

        rows.append([key, display_value])
        json_data.append({"key": key, "value": display_value})

    if not rows:
        out.info("No matching system parameters found.")
        return

    out.table(
        f"System Environment ({len(rows)} parameters)",
        [("Key", ""), ("Value", "")],
        rows,
        data_for_json=json_data,
    )


from kctl_odoo.commands.deploy_hotfix import hotfix, hotfix_rollback, hotfix_status  # noqa: E402
from kctl_odoo.commands.deploy_upgrade import upgrade  # noqa: E402

app.command("hotfix")(hotfix)
app.command("hotfix-status")(hotfix_status)
app.command("hotfix-rollback")(hotfix_rollback)
app.command("upgrade")(upgrade)
