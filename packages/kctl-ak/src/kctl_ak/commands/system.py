"""System settings and administration commands."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from kctl_ak.core.callbacks import AppContext

app = typer.Typer(name="system", help="System settings, version, and license info.")


@app.command()
def settings(ctx: typer.Context) -> None:
    """Show Authentik system settings."""
    c: AppContext = ctx.obj
    data = c.client.get("admin/settings/")

    if not isinstance(data, dict):
        c.output.error("Unexpected response format")
        raise typer.Exit(1)

    kvs: list[tuple[str, str]] = []
    for key, value in sorted(data.items()):
        if isinstance(value, dict):
            kvs.append((key, json.dumps(value, default=str)))
        elif isinstance(value, list):
            kvs.append((key, ", ".join(str(v) for v in value)))
        else:
            kvs.append((key, str(value)))

    c.output.detail("System Settings", [("Settings", kvs)], data_for_json=data)


@app.command("update-setting")
def update_setting(
    ctx: typer.Context,
    key: str = typer.Option(..., "--key", help="Setting key"),
    value: str = typer.Option(..., "--value", help="Setting value (JSON-encoded for complex values)"),
) -> None:
    """Update a system setting."""
    c: AppContext = ctx.obj

    # Try to parse as JSON first (for booleans, numbers, objects)
    try:
        parsed_value = json.loads(value)
    except (json.JSONDecodeError, ValueError):
        parsed_value = value

    # Get current settings, update the key
    current = c.client.get("admin/settings/")
    if not isinstance(current, dict):
        current = {}

    current[key] = parsed_value

    result = c.client.put("admin/settings/", data=current)
    c.output.success(f"Setting '{key}' updated")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command()
def license(ctx: typer.Context) -> None:
    """Show enterprise license information."""
    c: AppContext = ctx.obj

    try:
        data = c.client.get("enterprise/license/")
    except Exception:
        c.output.info("No enterprise license or endpoint not available.")
        return

    results = data.get("results", []) if isinstance(data, dict) else data if isinstance(data, list) else []

    if not results:
        c.output.info("No enterprise licenses installed (Community Edition).")
        return

    for lic in results:
        expiry = str(lic.get("expiry", ""))[:19].replace("T", " ")
        sections = [
            (
                "License",
                [
                    ("ID", str(lic.get("license_uuid", lic.get("pk", "")))),
                    ("Name", str(lic.get("name", ""))),
                    ("Key", str(lic.get("key", ""))[:20] + "..."),
                    ("Users", str(lic.get("internal_users", ""))),
                    ("External Users", str(lic.get("external_users", ""))),
                    ("Expiry", expiry),
                ],
            ),
        ]
        c.output.detail("Enterprise License", sections, data_for_json=lic)


@app.command()
def impersonation(
    ctx: typer.Context,
    state: Annotated[str | None, typer.Argument(help="on or off (omit to show current)")] = None,
) -> None:
    """Toggle or show impersonation setting."""
    c: AppContext = ctx.obj
    current = c.client.get("admin/settings/")
    if not isinstance(current, dict):
        current = {}

    if state is None:
        val = current.get("impersonation", True)
        label = "[green]enabled[/green]" if val else "[red]disabled[/red]"
        c.output.detail(
            "Impersonation",
            [("Setting", [("Impersonation", label)])],
            data_for_json={"impersonation": val},
        )
        return

    new_val = state.lower() in ("on", "true", "1", "yes", "enable", "enabled")
    current["impersonation"] = new_val
    c.client.put("admin/settings/", data=current)
    c.output.success(f"Impersonation {'enabled' if new_val else 'disabled'}")


@app.command("user-changes")
def user_changes(
    ctx: typer.Context,
    name: Annotated[str | None, typer.Option(help="Allow name changes: on/off")] = None,
    email: Annotated[str | None, typer.Option(help="Allow email changes: on/off")] = None,
    username: Annotated[str | None, typer.Option(help="Allow username changes: on/off")] = None,
) -> None:
    """Toggle user self-service field change settings."""
    c: AppContext = ctx.obj
    current = c.client.get("admin/settings/")
    if not isinstance(current, dict):
        current = {}

    def parse_bool(v: str) -> bool:
        return v.lower() in ("on", "true", "1", "yes")

    fields_map = {
        "allow_user_name_change": name,
        "allow_user_email_change": email,
        "allow_user_username_change": username,
    }

    changed = False
    for key, val in fields_map.items():
        if val is not None:
            current[key] = parse_bool(val)
            changed = True

    if changed:
        c.client.put("admin/settings/", data=current)
        c.output.success("User self-service settings updated")
    else:
        # Show current values
        kvs = [
            ("Name changes", str(current.get("allow_user_name_change", True))),
            ("Email changes", str(current.get("allow_user_email_change", True))),
            ("Username changes", str(current.get("allow_user_username_change", True))),
        ]
        c.output.detail("User Self-Service", [("Settings", kvs)], data_for_json=current)


@app.command("token-defaults")
def token_defaults(
    ctx: typer.Context,
    duration: Annotated[str | None, typer.Option(help="Default token duration (e.g. 'days=30')")] = None,
    length: Annotated[int | None, typer.Option(help="Default token key length")] = None,
) -> None:
    """Set or show default token parameters."""
    c: AppContext = ctx.obj
    current = c.client.get("admin/settings/")
    if not isinstance(current, dict):
        current = {}

    changed = False
    if duration is not None:
        current["default_token_duration"] = duration
        changed = True
    if length is not None:
        current["default_token_length"] = length
        changed = True

    if changed:
        c.client.put("admin/settings/", data=current)
        c.output.success("Token defaults updated")
    else:
        kvs = [
            ("Duration", str(current.get("default_token_duration", "(server default)"))),
            ("Length", str(current.get("default_token_length", "(server default)"))),
        ]
        c.output.detail("Token Defaults", [("Settings", kvs)], data_for_json=current)


@app.command("event-retention")
def event_retention(
    ctx: typer.Context,
    duration: Annotated[
        str | None, typer.Argument(help="Retention duration (e.g. 'days=365'). Omit to show current.")
    ] = None,
) -> None:
    """Set or show event retention duration."""
    c: AppContext = ctx.obj
    current = c.client.get("admin/settings/")
    if not isinstance(current, dict):
        current = {}

    if duration is None:
        val = current.get("event_retention", "(server default)")
        c.output.detail(
            "Event Retention",
            [("Setting", [("Retention", str(val))])],
            data_for_json={"event_retention": val},
        )
        return

    current["event_retention"] = duration
    c.client.put("admin/settings/", data=current)
    c.output.success(f"Event retention set to: {duration}")


@app.command()
def version(ctx: typer.Context) -> None:
    """Show Authentik server version."""
    c: AppContext = ctx.obj

    try:
        data = c.client.get("admin/version/")
    except Exception:
        c.output.error("Could not retrieve version information")
        raise typer.Exit(1)

    if not isinstance(data, dict):
        c.output.error("Unexpected response format")
        raise typer.Exit(1)

    version_current = data.get("version_current", "unknown")
    version_latest = data.get("version_latest", "unknown")
    outdated = data.get("outdated", False)

    sections = [
        (
            "Authentik Version",
            [
                ("Current", str(version_current)),
                ("Latest", str(version_latest)),
                ("Outdated", "[yellow]Yes[/yellow]" if outdated else "[green]No[/green]"),
                ("Build Hash", str(data.get("build_hash", "-"))),
            ],
        ),
    ]

    c.output.detail("Server Version", sections, data_for_json=data)
