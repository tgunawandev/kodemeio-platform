"""Dev mode management for FastAPI apps."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError
from kctl_odoo.core.utils import KNOWN_APPS

app = typer.Typer(help="Enable/disable dev mode for FastAPI apps.")


def _param_key(app_name: str) -> str:
    """Return the ir.config_parameter key for dev mode."""
    return f"{app_name}.dev_mode"


def _get_dev_mode(client, app_name: str) -> bool | None:
    """Get dev mode status. Returns None if param doesn't exist."""
    params = client.search_read(
        "ir.config_parameter",
        [("key", "=", _param_key(app_name))],
        ["value"],
    )
    if not params:
        return None
    return str(params[0].get("value", "")).lower() in ("true", "1")


def _set_dev_mode(client, app_name: str, enabled: bool) -> None:
    """Set dev mode via ir.config_parameter."""
    client.execute_kw(
        "ir.config_parameter",
        "set_param",
        [_param_key(app_name), str(enabled)],
    )


@app.command()
def enable(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name (sfa, tpm, dms, etc.)")],
) -> None:
    """Enable dev mode for an app.

    Sets {app}.dev_mode system parameter to True, enabling dev-users
    endpoint for passwordless login during development.

    Examples:
        kctl-odoo dev-mode enable tpm
        kctl-odoo dev-mode enable sfa
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        _set_dev_mode(c, app_name, True)
    except RPCError as exc:
        out.error(f"Failed to enable dev mode: {exc}")
        raise typer.Exit(1) from exc

    out.success(f"Dev mode enabled for {app_name}")
    out.info(f"Parameter {_param_key(app_name)} = True")


@app.command()
def disable(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name (sfa, tpm, dms, etc.)")],
) -> None:
    """Disable dev mode for an app.

    Examples:
        kctl-odoo dev-mode disable tpm
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        _set_dev_mode(c, app_name, False)
    except RPCError as exc:
        out.error(f"Failed to disable dev mode: {exc}")
        raise typer.Exit(1) from exc

    out.success(f"Dev mode disabled for {app_name}")


@app.command()
def status(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (default: show all)")] = None,
) -> None:
    """Show dev mode status for one or all apps.

    Examples:
        kctl-odoo dev-mode status
        kctl-odoo dev-mode status tpm
        kctl-odoo dev-mode status --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    apps_to_check = [app_name] if app_name else list(KNOWN_APPS.keys())

    rows = []
    json_data = []
    for name in apps_to_check:
        val = _get_dev_mode(c, name)
        if val is None:
            status_str = "[dim]not set[/dim]"
            status_val = None
        elif val:
            status_str = "[green]enabled[/green]"
            status_val = True
        else:
            status_str = "[red]disabled[/red]"
            status_val = False
        rows.append([name, _param_key(name), status_str])
        json_data.append({"app": name, "key": _param_key(name), "dev_mode": status_val})

    if app_name and len(json_data) == 1:
        if actx.json_mode:
            out.raw_json(json_data[0])
        else:
            out.detail(
                f"Dev Mode — {app_name}",
                [(app_name, [("Parameter", _param_key(app_name)), ("Status", rows[0][2])])],
                data_for_json=json_data[0],
            )
    else:
        out.table(
            f"Dev Mode Status ({len(rows)})",
            [("App", "cyan"), ("Parameter", "dim"), ("Status", "")],
            rows,
            data_for_json=json_data,
        )
