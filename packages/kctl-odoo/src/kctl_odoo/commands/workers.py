"""Worker process management commands."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Monitor Odoo worker and server status.")


@app.command()
def status(ctx: typer.Context) -> None:
    """Check if Odoo is responding and show server version info."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    ok, version_or_error = c.check_health()

    if not ok:
        out.error(f"Odoo is not responding: {version_or_error}")
        if actx.json_mode:
            out.raw_json({"status": "down", "error": version_or_error})
        raise typer.Exit(1)

    info = c.version_info()
    server_version = info.get("server_version", "unknown")
    server_serie = info.get("server_serie", "unknown")
    protocol_version = info.get("protocol_version", "unknown")

    sections = [
        (
            "Server Status",
            [
                ("Status", "[green]OK[/green]"),
                ("Server Version", server_version),
                ("Server Serie", server_serie),
                ("Protocol Version", str(protocol_version)),
            ],
        ),
    ]

    json_result = {
        "status": "ok",
        "server_version": server_version,
        "server_serie": server_serie,
        "protocol_version": protocol_version,
    }

    # Try to get database info
    try:
        uid = c.uid
        json_result["uid"] = uid
        json_result["database"] = c.database
        sections[0][1].append(("Database", c.database))
        sections[0][1].append(("Authenticated UID", str(uid)))
    except Exception:
        pass

    out.detail("Odoo Worker Status", sections, data_for_json=json_result)


@app.command()
def info(ctx: typer.Context) -> None:
    """Show server configuration parameters (workers, limits, etc.)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Read from ir.config_parameter for any stored config
    params = c.search_read(
        "ir.config_parameter",
        domain=[
            (
                "key",
                "in",
                [
                    "web.base.url",
                    "database.expiration_date",
                    "database.uuid",
                    "database.create_date",
                ],
            )
        ],
        fields=["key", "value"],
    )

    sections = []
    json_result: dict = {}

    # System parameters
    if params:
        sys_kvs = []
        for p in params:
            key = p.get("key", "")
            value = p.get("value", "")
            sys_kvs.append((key, value))
            json_result[key] = value
        sections.append(("System Parameters", sys_kvs))

    # ── Server Limits (from ir.config_parameter) ──
    limit_keys = [
        ("workers", "Workers"),
        ("limit_time_real", "Limit Time Real (s)"),
        ("limit_memory_hard", "Limit Memory Hard (bytes)"),
        ("max_cron_threads", "Max Cron Threads"),
        ("proxy_mode", "Proxy Mode"),
    ]
    limit_kvs: list[tuple[str, str]] = []
    limit_json: dict[str, str | None] = {}
    for key, label in limit_keys:
        try:
            result = c.search_read("ir.config_parameter", [("key", "=", key)], fields=["value"])
            val = result[0]["value"] if result else None
        except RPCError:
            val = None
        display = val if val else "[dim]not set[/dim]"
        limit_kvs.append((label, display))
        limit_json[key] = val
    if limit_kvs:
        sections.append(("Server Limits", limit_kvs))
        json_result["server_limits"] = limit_json

    # Server version info
    try:
        info_data = c.version_info()
        version_kvs = [
            ("server_version", info_data.get("server_version", "unknown")),
            ("server_serie", info_data.get("server_serie", "unknown")),
        ]
        sections.append(("Version Info", version_kvs))
        json_result["server_version"] = info_data.get("server_version")
        json_result["server_serie"] = info_data.get("server_serie")
    except RPCError:
        pass

    # Module counts as a proxy for system load/complexity
    for _state_label, state_val in [
        ("installed", "installed"),
        ("uninstalled", "uninstalled"),
        ("to upgrade", "to upgrade"),
    ]:
        count = c.search_count("ir.module.module", [("state", "=", state_val)])
        json_result[f"modules_{state_val.replace(' ', '_')}"] = count

    sections.append(
        (
            "Module Counts",
            [
                ("Installed", str(json_result.get("modules_installed", 0))),
                ("Uninstalled", str(json_result.get("modules_uninstalled", 0))),
                ("To Upgrade", str(json_result.get("modules_to_upgrade", 0))),
            ],
        )
    )

    # Active users count
    active_users = c.search_count("res.users", [("active", "=", True), ("share", "=", False)])
    json_result["active_internal_users"] = active_users
    sections.append(("Users", [("Active internal users", str(active_users))]))

    out.detail("Server Configuration", sections, data_for_json=json_result)


# Moved to cron group: kctl-odoo cron status
# (Previously: kctl-odoo workers cron-status)


@app.command()
def longpoll(ctx: typer.Context) -> None:
    """Check longpolling/websocket status via bus.bus model."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    sections = []
    json_result: dict = {}

    # Check server health first
    ok, version = c.check_health()
    sections.append(
        (
            "Server",
            [
                ("HTTP Status", "[green]OK[/green]" if ok else "[red]DOWN[/red]"),
                ("Version", version),
            ],
        )
    )
    json_result["http_ok"] = ok
    json_result["version"] = version

    # Check bus.bus for recent activity
    try:
        cutoff_5m = (datetime.now(tz=UTC) - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        cutoff_1h = (datetime.now(tz=UTC) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")

        bus_5m = c.search_count("bus.bus", [("create_date", ">", cutoff_5m)])
        bus_1h = c.search_count("bus.bus", [("create_date", ">", cutoff_1h)])

        sections.append(
            (
                "Bus Activity",
                [
                    ("Messages (last 5 min)", str(bus_5m)),
                    ("Messages (last 1 hour)", str(bus_1h)),
                ],
            )
        )
        json_result["bus_messages_5m"] = bus_5m
        json_result["bus_messages_1h"] = bus_1h
    except RPCError:
        sections.append(("Bus Activity", [("Status", "[dim]bus.bus not accessible[/dim]")]))
        json_result["bus_messages_5m"] = None

    # Check mail.channel for discuss/chat activity
    try:
        channel_count = c.search_count("discuss.channel", [])
        sections.append(("Discuss Channels", [("Total channels", str(channel_count))]))
        json_result["discuss_channels"] = channel_count
    except RPCError:
        pass

    out.detail("Longpolling / Websocket Status", sections, data_for_json=json_result)
