"""System settings and administration commands."""

from __future__ import annotations

import json

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
