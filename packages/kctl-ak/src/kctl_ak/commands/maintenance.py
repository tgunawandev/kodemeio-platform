"""Maintenance and system administration commands.

System status, version info, task management, outpost monitoring,
and cache/cleanup operations.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_ak.core.callbacks import AppContext

app = typer.Typer(help="System maintenance and administration.")


@app.command()
def status(ctx: typer.Context) -> None:
    """Show system status."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    try:
        data = c.get("admin/system/")
    except Exception as e:
        out.error(f"Failed to fetch system status: {e}")
        raise typer.Exit(code=1)

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    # Server info
    server_kvs: list[tuple[str, str]] = []
    runtime = data.get("runtime", {})
    server_kvs.append(("Python", runtime.get("python_version", "unknown")))
    server_kvs.append(("Platform", runtime.get("platform", "unknown")))
    server_kvs.append(("Uname", runtime.get("uname", "unknown")))
    sections.append(("Server Runtime", server_kvs))

    # Embedded outpost
    outpost_kvs: list[tuple[str, str]] = []
    embedded_host = data.get("embedded_outpost_host", "")
    outpost_kvs.append(("Embedded Outpost Host", embedded_host or "[dim]not set[/dim]"))
    sections.append(("Outpost", outpost_kvs))

    out.detail("System Status", sections, data_for_json=data)


@app.command()
def version(ctx: typer.Context) -> None:
    """Show Authentik version info."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    try:
        data = c.get("admin/version/")
    except Exception as e:
        out.error(f"Failed to fetch version: {e}")
        raise typer.Exit(code=1)

    current = data.get("version_current", "unknown")
    latest = data.get("version_latest", "unknown")
    outdated = data.get("outdated", False)

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Version Info",
            [
                ("Installed", current),
                ("Latest", latest),
                ("Outdated", "[yellow]Yes -- update available[/yellow]" if outdated else "[green]No[/green]"),
            ],
        ),
    ]

    out.detail("Authentik Version", sections, data_for_json=data)


@app.command()
def tasks(ctx: typer.Context) -> None:
    """List system tasks."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    try:
        data = c.get_all("admin/system_tasks/")
    except Exception as e:
        out.error(f"Failed to fetch tasks: {e}")
        raise typer.Exit(code=1)

    rows: list[list[str]] = []
    for t in data:
        task_id = t.get("uuid", t.get("pk", ""))
        name = t.get("task_name", t.get("name", ""))
        task_status = t.get("status", "unknown")
        description = t.get("task_description", t.get("description", ""))
        duration = str(t.get("task_duration", t.get("duration", "")))
        finish = t.get("task_finish_timestamp", t.get("finish_timestamp", ""))

        if task_status == "successful":
            status_display = "[green]OK[/green]"
        elif task_status == "warning":
            status_display = "[yellow]WARN[/yellow]"
        else:
            status_display = f"[red]{task_status}[/red]"

        rows.append([str(task_id), name, status_display, description, duration, str(finish)])

    out.table(
        "System Tasks",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("Status", ""),
            ("Description", ""),
            ("Duration", "dim"),
            ("Finished", "dim"),
        ],
        rows,
        data_for_json=data,
    )


@app.command()
def run(
    ctx: typer.Context,
    task_name: Annotated[str, typer.Argument(help="Task UUID or name to run.")],
) -> None:
    """Trigger a system task to run."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    try:
        c.post(f"admin/system_tasks/{task_name}/run/")
        out.success(f"Task '{task_name}' triggered.")
    except Exception as e:
        out.error(f"Failed to run task: {e}")
        raise typer.Exit(code=1)


@app.command("cache-clear")
def cache_clear(ctx: typer.Context) -> None:
    """Clear system caches."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    # Trigger cache clear via admin tasks (clear_cache is a known system task)
    try:
        c.post("admin/system_tasks/clean_expired_models/run/")
        out.success("Cache clear task triggered.")
    except Exception as e:
        out.error(f"Failed to clear cache: {e}")
        raise typer.Exit(code=1)


@app.command()
def outposts(ctx: typer.Context) -> None:
    """List outpost instances."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    try:
        data = c.get_all("outposts/instances/")
    except Exception as e:
        out.error(f"Failed to fetch outposts: {e}")
        raise typer.Exit(code=1)

    rows: list[list[str]] = []
    for o in data:
        pk = str(o.get("pk", ""))
        name = o.get("name", "")
        otype = o.get("type", "")
        providers_list = o.get("providers", [])
        provider_count = str(len(providers_list))
        service_connection = o.get("service_connection_obj", {})
        conn_name = ""
        if isinstance(service_connection, dict) and service_connection:
            conn_name = service_connection.get("name", "")
        rows.append([pk[:8], name, otype, provider_count, conn_name or "[dim]embedded[/dim]"])

    out.table(
        "Outposts",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("Type", "yellow"),
            ("Providers", ""),
            ("Connection", "dim"),
        ],
        rows,
        data_for_json=data,
    )


@app.command()
def workers(ctx: typer.Context) -> None:
    """Show worker status via system info."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    try:
        data = c.get("admin/system/")
    except Exception as e:
        out.error(f"Failed to fetch system info: {e}")
        raise typer.Exit(code=1)

    runtime = data.get("runtime", {})
    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Worker Info",
            [
                ("Python", runtime.get("python_version", "unknown")),
                ("Platform", runtime.get("platform", "unknown")),
            ],
        ),
    ]

    # Try to get worker-specific info from system tasks
    try:
        task_data = c.get_all("admin/system_tasks/")
        worker_tasks = [t for t in task_data if "worker" in t.get("task_name", "").lower()]
        if worker_tasks:
            task_kvs: list[tuple[str, str]] = []
            for wt in worker_tasks:
                name = wt.get("task_name", wt.get("name", ""))
                status = wt.get("status", "unknown")
                status_icon = "[green]OK[/green]" if status == "successful" else f"[yellow]{status}[/yellow]"
                task_kvs.append((name, status_icon))
            sections.append(("Worker Tasks", task_kvs))
    except Exception:
        pass

    out.detail("Workers", sections, data_for_json=data)


@app.command()
def config(ctx: typer.Context) -> None:
    """Show brands/tenant configuration."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    try:
        brands = c.get_all("core/brands/")
    except Exception as e:
        out.error(f"Failed to fetch brands: {e}")
        raise typer.Exit(code=1)

    if out.json_mode:
        out.raw_json(brands)
        return

    for brand in brands:
        sections: list[tuple[str, list[tuple[str, str]]]] = []
        sections.append(
            (
                "Brand",
                [
                    ("Domain", brand.get("domain", "")),
                    ("Default", str(brand.get("default", False))),
                    ("Branding Title", brand.get("branding_title", "")),
                    ("Branding Logo", brand.get("branding_logo", "")),
                    ("Branding Favicon", brand.get("branding_favicon", "")),
                ],
            )
        )

        flow_kvs: list[tuple[str, str]] = []
        for key in [
            "flow_authentication",
            "flow_invalidation",
            "flow_recovery",
            "flow_unenrollment",
            "flow_user_settings",
            "flow_device_code",
        ]:
            val = brand.get(key, "")
            flow_kvs.append((key.replace("flow_", "").replace("_", " ").title(), str(val) or "[dim]none[/dim]"))
        sections.append(("Flows", flow_kvs))

        out.detail(f"Brand: {brand.get('domain', 'unknown')}", sections)


@app.command()
def clean(ctx: typer.Context) -> None:
    """Clean expired sessions and models."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    try:
        c.post("admin/system_tasks/clean_expired_models/run/")
        out.success("Expired model cleanup triggered.")
    except Exception as e:
        out.error(f"Failed to trigger cleanup: {e}")
        raise typer.Exit(code=1)


@app.command()
def settings(
    ctx: typer.Context,
    set_key: Annotated[str | None, typer.Option("--set", help="Setting key to change (e.g. impersonation)")] = None,
    value: Annotated[
        str | None, typer.Option("--value", help="New value (true/false for booleans, string otherwise)")
    ] = None,
) -> None:
    """View or modify Authentik system settings.

    Without --set: shows all settings.
    With --set and --value: updates a setting.

    Examples:
      kctl-ak maintenance settings
      kctl-ak maintenance settings --set impersonation --value false
      kctl-ak maintenance settings --set impersonation --value true
      kctl-ak maintenance settings --set impersonation_require_reason --value true
      kctl-ak maintenance settings --set default_user_change_name --value false
    """
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    if set_key and value is not None:
        # Update a setting
        # Parse value: booleans, integers, or strings
        parsed_value: bool | int | str
        if value.lower() in ("true", "false"):
            parsed_value = value.lower() == "true"
        elif value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
            parsed_value = int(value)
        else:
            parsed_value = value

        try:
            c.patch("admin/settings/", data={set_key: parsed_value})
            out.success(f"Setting updated: {set_key} = {parsed_value}")
        except Exception as e:
            out.error(f"Failed to update setting: {e}")
            raise typer.Exit(code=1)
        return

    # Show all settings
    try:
        data = c.get("admin/settings/")
    except Exception as e:
        out.error(f"Failed to fetch settings: {e}")
        raise typer.Exit(code=1)

    if out.json_mode:
        out.raw_json(data)
        return

    security_kvs: list[tuple[str, str]] = []
    user_kvs: list[tuple[str, str]] = []
    general_kvs: list[tuple[str, str]] = []

    for key, val in sorted(data.items()):
        display = str(val)
        if isinstance(val, bool):
            display = "[green]enabled[/green]" if val else "[red]disabled[/red]"

        if "impersonation" in key:
            security_kvs.append((key, display))
        elif "user" in key or "gdpr" in key:
            user_kvs.append((key, display))
        elif key in ("flags", "footer_links", "attributes"):
            continue
        else:
            general_kvs.append((key, display))

    sections: list[tuple[str, list[tuple[str, str]]]] = []
    if security_kvs:
        sections.append(("Security", security_kvs))
    if user_kvs:
        sections.append(("User Settings", user_kvs))
    if general_kvs:
        sections.append(("General", general_kvs))

    out.detail("Authentik System Settings", sections, data_for_json=data)


@app.command()
def impersonation(
    ctx: typer.Context,
    enable: Annotated[bool | None, typer.Option("--enable/--disable", help="Enable or disable impersonation")] = None,
    require_reason: Annotated[
        bool | None, typer.Option("--require-reason/--no-require-reason", help="Require reason for impersonation")
    ] = None,
) -> None:
    """View or toggle user impersonation settings.

    Without flags: shows current impersonation status.
    With flags: updates the setting.

    Examples:
      kctl-ak maintenance impersonation
      kctl-ak maintenance impersonation --disable
      kctl-ak maintenance impersonation --enable --require-reason
      kctl-ak maintenance impersonation --enable --no-require-reason
    """
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    if enable is not None or require_reason is not None:
        update: dict = {}
        if enable is not None:
            update["impersonation"] = enable
        if require_reason is not None:
            update["impersonation_require_reason"] = require_reason

        try:
            c.patch("admin/settings/", data=update)
        except Exception as e:
            out.error(f"Failed to update: {e}")
            raise typer.Exit(code=1)

        for key, val in update.items():
            action = "[green]enabled[/green]" if val else "[red]disabled[/red]"
            out.success(f"{key}: {action}")

    # Show current status
    try:
        data = c.get("admin/settings/")
    except Exception as e:
        out.error(f"Failed to fetch settings: {e}")
        raise typer.Exit(code=1)

    imp = data.get("impersonation", False)
    reason = data.get("impersonation_require_reason", False)

    out.detail(
        "Impersonation Settings",
        [
            (
                "Status",
                [
                    ("Impersonation", "[green]enabled[/green]" if imp else "[red]disabled[/red]"),
                    ("Require Reason", "[green]yes[/green]" if reason else "[yellow]no[/yellow]"),
                ],
            )
        ],
        data_for_json={"impersonation": imp, "impersonation_require_reason": reason},
    )
