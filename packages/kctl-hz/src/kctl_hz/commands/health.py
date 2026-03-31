"""Health check command."""

from __future__ import annotations

import typer
from kctl_lib.exceptions import KctlError

from kctl_hz.core.callbacks import AppContext
from kctl_hz.core.config import resolve_active_profile_name

app = typer.Typer(help="Health checks.")


@app.command("check")
def check(ctx: typer.Context) -> None:
    """Check Hetzner Cloud + DNS API connectivity."""
    c: AppContext = ctx.obj
    out = c.output
    active = resolve_active_profile_name(c.profile)
    out.info(f"Checking profile '{active}'...")

    # Cloud API
    try:
        c.client.get("/servers", params={"per_page": "1"})
        out.success("Cloud API: connected")
    except KctlError as e:
        out.error(f"Cloud API: {e}")

    # DNS API
    try:
        c.dns_client.get("/zones")
        out.success("DNS API: connected")
    except KctlError as e:
        out.warn(f"DNS API: {e} (optional — may not be configured)")
