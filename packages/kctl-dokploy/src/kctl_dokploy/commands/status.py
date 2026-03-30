"""Status dashboard command."""

from __future__ import annotations

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Platform status and dashboard.")


@app.command()
def health(ctx: typer.Context) -> None:
    """Check Dokploy API health."""
    c: AppContext = ctx.obj
    out = c.output
    code = c.client.check_health()
    if c.json_mode:
        out.raw_json({"status": "healthy" if code == 200 else "unhealthy", "http_code": code})
        return
    if code == 200:
        out.success("Dokploy API is healthy")
    else:
        out.error(f"Dokploy API returned HTTP {code}")
        raise typer.Exit(1)
