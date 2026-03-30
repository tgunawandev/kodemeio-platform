"""Health check commands."""

from __future__ import annotations

import time
from typing import Annotated

import typer

from kctl_cloudflare.core.callbacks import AppContext
from kctl_cloudflare.core.config import resolve_active_profile_name
from kctl_cloudflare.core.exceptions import KctlError

app = typer.Typer(help="Health checks.")


@app.command("check")
def check(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously monitor")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Watch interval in seconds")] = 10,
) -> None:
    """Check Cloudflare API connectivity."""
    c: AppContext = ctx.obj
    out = c.output
    active = resolve_active_profile_name(c.profile)

    def _check_once() -> None:
        try:
            result = c.client.check_health()
            status = result.get("status", "unknown") if isinstance(result, dict) else "ok"

            # Get additional info
            try:
                zones = c.client.get("/zones")
                zone_count = len(zones) if isinstance(zones, list) else 0
            except Exception:
                zone_count = 0

            sections = [
                (
                    "Health",
                    [
                        ("Status", f"[green]{status}[/green]"),
                        ("Profile", active),
                        ("Zones", str(zone_count)),
                    ],
                )
            ]
            out.detail(
                "Cloudflare Health",
                sections,
                data_for_json={
                    "healthy": True,
                    "status": status,
                    "profile": active,
                    "zones": zone_count,
                },
            )
        except KctlError as e:
            out.detail(
                "Cloudflare Health",
                [
                    (
                        "Health",
                        [
                            ("Status", "[red]Unreachable[/red]"),
                            ("Error", str(e)),
                        ],
                    )
                ],
                data_for_json={"healthy": False, "error": str(e)},
            )
            if not watch:
                raise typer.Exit(1) from e

    _check_once()

    if watch:
        try:
            while True:
                time.sleep(interval)
                out.header(f"Check at {time.strftime('%H:%M:%S')}")
                _check_once()
        except KeyboardInterrupt:
            out.info("Stopped watching")
