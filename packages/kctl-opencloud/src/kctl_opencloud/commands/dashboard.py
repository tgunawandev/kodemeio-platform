"""Dashboard commands for kctl-opencloud."""

from __future__ import annotations

import time
from typing import Annotated, Any

import typer
from kctl_lib.exceptions import AuthenticationError, ConfigError

from kctl_opencloud.core.callbacks import AppContext

app = typer.Typer(help="System overview and statistics.")


def _fetch_dashboard(c: AppContext) -> dict[str, Any]:
    """Fetch dashboard data."""
    client = c.client
    data: dict[str, Any] = {}

    # Version
    data["version"] = client.get_version() or "unknown"

    # Resource counts
    for resource, endpoint in [("users", "users"), ("groups", "groups"), ("spaces", "drives")]:
        try:
            result = client.get(endpoint)
            data[resource] = len(result.get("value", []))
        except (AuthenticationError, ConfigError):
            raise
        except Exception:
            data[resource] = 0

    return data


def _display_dashboard(c: AppContext, data: dict[str, Any]) -> None:
    """Display dashboard."""
    out = c.output

    if c.json_mode:
        out.raw_json(data)
        return

    out.header("OpenCloud Dashboard")
    out.kv("URL", c.client.root_url)
    out.kv("Version", data["version"])
    out.text("")
    out.kv("Users", str(data.get("users", 0)))
    out.kv("Groups", str(data.get("groups", 0)))
    out.kv("Spaces", str(data.get("spaces", 0)))


@app.callback(invoke_without_command=True)
def show(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuous monitoring")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Watch interval")] = 10,
    compact: Annotated[bool, typer.Option("--compact", "-c", help="Compact output")] = False,
) -> None:
    """Show system overview."""
    c: AppContext = ctx.obj

    if watch:
        try:
            while True:
                data = _fetch_dashboard(c)
                if compact:
                    c.output.text(f"Users: {data['users']} | Groups: {data['groups']} | Spaces: {data['spaces']}")
                else:
                    _display_dashboard(c, data)
                time.sleep(interval)
        except KeyboardInterrupt:
            pass
    else:
        data = _fetch_dashboard(c)
        if compact:
            c.output.text(f"Users: {data['users']} | Groups: {data['groups']} | Spaces: {data['spaces']}")
        else:
            _display_dashboard(c, data)
