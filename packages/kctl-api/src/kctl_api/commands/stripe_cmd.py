"""Stripe integration commands for kctl-api.

Checkout sessions, customer portal, and webhook status.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.exceptions import APIError, AuthenticationError
from kctl_api.core.exceptions import ConnectionError as KctlConnectionError

app = typer.Typer(name="stripe", help="Stripe integration — checkout, portal, webhooks.", no_args_is_help=True)

_BASE = "/api/v1/stripe"


# ---------------------------------------------------------------------------
# checkout
# ---------------------------------------------------------------------------
@app.command()
def checkout(
    ctx: typer.Context,
    price_id: Annotated[str, typer.Argument(help="Stripe Price ID.")],
    success_url: Annotated[str, typer.Option("--success-url", help="Redirect URL on success.")] = "",
    cancel_url: Annotated[str, typer.Option("--cancel-url", help="Redirect URL on cancel.")] = "",
) -> None:
    """Create a Stripe checkout session via POST /api/v1/stripe/checkout."""
    actx: AppContext = ctx.obj
    out = actx.output

    payload: dict = {"price_id": price_id}
    if success_url:
        payload["success_url"] = success_url
    if cancel_url:
        payload["cancel_url"] = cancel_url

    try:
        result = actx.client.post(f"{_BASE}/checkout", json=payload)
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    checkout_url = result.get("url", "") if isinstance(result, dict) else ""
    if checkout_url:
        out.success(f"Checkout session created: {checkout_url}")
    else:
        out.success("Checkout session created.")
    if actx.json_mode:
        out.raw_json(result)


# ---------------------------------------------------------------------------
# portal
# ---------------------------------------------------------------------------
@app.command()
def portal(ctx: typer.Context) -> None:
    """Create a Stripe customer portal session via POST /api/v1/stripe/portal."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        result = actx.client.post(f"{_BASE}/portal")
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    portal_url = result.get("url", "") if isinstance(result, dict) else ""
    if portal_url:
        out.success(f"Portal session created: {portal_url}")
    else:
        out.success("Portal session created.")
    if actx.json_mode:
        out.raw_json(result)


# ---------------------------------------------------------------------------
# webhook-status
# ---------------------------------------------------------------------------
@app.command(name="webhook-status")
def webhook_status(ctx: typer.Context) -> None:
    """Check Stripe webhook endpoint status via GET /api/v1/stripe/webhook-status."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        data = actx.client.get(f"{_BASE}/webhook-status")
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    if not data:
        out.info("No webhook status available.")
        return

    out.detail(
        title="Stripe Webhook Status",
        sections=[
            ("Status", [(k, str(v)) for k, v in data.items()]),
        ],
        data_for_json=data,
    )
