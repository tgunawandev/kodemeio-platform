"""Production monitoring."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_common.monitor_base import health_check_url, ssl_check

from kctl_react.core.callbacks import AppContext

app = typer.Typer(help="Production monitoring.")


@app.command()
def health(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    url: Annotated[str | None, typer.Option("--url")] = None,
) -> None:
    """HTTP health check against deployed app."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    target = url or f"https://{app_name}.kodeme.io"
    result = health_check_url(target)
    if out.json_mode:
        out.raw_json(result)
        return
    if result["healthy"]:
        out.success(f"{target} — {result['status_code']} ({result['latency_ms']}ms)")
    else:
        out.error(f"{target} — {result.get('error', result.get('status_code', 'unknown'))}")


@app.command("ssl")
def ssl_cmd(ctx: typer.Context, domain: Annotated[str, typer.Argument(help="Domain to check")]) -> None:
    """Check SSL certificate."""
    actx: AppContext = ctx.obj
    out = actx.output
    result = ssl_check(domain)
    if out.json_mode:
        out.raw_json(result)
        return
    if result.get("valid"):
        out.success(
            f"{domain} — SSL valid, expires in {result.get('days_remaining', '?')} days ({result.get('issuer', '')})"
        )
    else:
        out.error(f"{domain} — SSL check failed: {result.get('error', 'unknown')}")
