"""Realm (server) settings commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_zulip.core.callbacks import AppContext

app = typer.Typer(help="Realm (server) settings.")


@app.command("settings")
def settings_(ctx: typer.Context) -> None:
    """Show server settings (public endpoint)."""
    c: AppContext = ctx.obj
    data = c.client.get("server_settings")

    auth_methods = data.get("authentication_methods", {})
    enabled_auth = [k for k, v in auth_methods.items() if v]

    c.output.detail(
        "Server Settings",
        [
            ("Server", [
                ("Zulip Version", data.get("zulip_version", "")),
                ("Feature Level", str(data.get("zulip_feature_level", ""))),
                ("Merge Base", data.get("zulip_merge_base", "")),
                ("Push Notifications", str(data.get("push_notifications_enabled", False))),
            ]),
            ("Realm", [
                ("Name", data.get("realm_name", "")),
                ("Description", data.get("realm_description", "")),
                ("Icon URL", data.get("realm_icon", "")),
                ("URI", data.get("realm_uri", "")),
                ("Web Public", str(data.get("realm_web_public_access_enabled", False))),
            ]),
            ("Authentication", [
                ("Enabled Methods", ", ".join(enabled_auth) if enabled_auth else "(none)"),
                ("Require Email Format", str(data.get("require_email_format_usernames", True))),
            ]),
        ],
        data_for_json=data,
    )


@app.command()
def get(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Setting key to retrieve")],
) -> None:
    """Get a specific server setting."""
    c: AppContext = ctx.obj
    data = c.client.get("server_settings")

    value = data.get(key)
    if value is None:
        c.output.error(f"Setting '{key}' not found")
        c.output.info(f"Available keys: {', '.join(sorted(data.keys())[:20])}...")
        raise typer.Exit(1)

    if c.output.json_mode:
        c.output.raw_json({key: value})
    else:
        c.output.kv(key, str(value))


@app.command()
def update(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Setting key")],
    value: Annotated[str, typer.Argument(help="New value")],
) -> None:
    """Update a realm setting (admin required).

    Common settings: name, description, emails_restricted_to_domains,
    invite_required, message_retention_days, etc.
    """
    c: AppContext = ctx.obj

    # Try to coerce booleans/ints
    coerced: str | bool | int = value
    if value.lower() in ("true", "false"):
        coerced = value.lower() == "true"
    else:
        try:
            coerced = int(value)
        except ValueError:
            pass

    c.client.patch("realm", data={key: coerced})
    c.output.success(f"Realm setting '{key}' updated to: {value}")
