"""Webhook management commands for kctl-api.

View recent webhooks, replay, and verify signatures.
Note: These commands require webhook audit endpoints on api-main (not yet implemented).
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext

app = typer.Typer(name="webhooks", help="Webhook management — recent, replay, verify.", no_args_is_help=True)


# ---------------------------------------------------------------------------
# recent
# ---------------------------------------------------------------------------
@app.command()
def recent(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of recent webhooks.")] = 20,
    source: Annotated[str | None, typer.Option("--source", "-s", help="Filter by source (github, chatwoot).")] = None,
) -> None:
    """List recent webhook deliveries (requires webhook audit API — not yet available)."""
    actx: AppContext = ctx.obj
    actx.output.warn("Webhook audit endpoints are not yet implemented on api-main.")
    actx.output.info("Available webhook endpoints: POST /webhooks/mattermost, /telegram, /generic/{source}")


# ---------------------------------------------------------------------------
# replay
# ---------------------------------------------------------------------------
@app.command()
def replay(
    ctx: typer.Context,
    webhook_id: Annotated[str, typer.Argument(help="Webhook delivery ID to replay.")],
) -> None:
    """Replay a webhook delivery (requires webhook audit API — not yet available)."""
    actx: AppContext = ctx.obj
    actx.output.warn("Webhook replay is not yet implemented on api-main.")


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------
@app.command()
def verify(
    ctx: typer.Context,
    source: Annotated[str, typer.Argument(help="Webhook source to verify (github, chatwoot).")],
) -> None:
    """Verify webhook signature configuration (requires webhook audit API — not yet available)."""
    actx: AppContext = ctx.obj
    actx.output.warn("Webhook verification is not yet implemented on api-main.")
