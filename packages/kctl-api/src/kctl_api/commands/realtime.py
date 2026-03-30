"""Real-time / SSE commands for kctl-api.

Presence, heartbeat, and event subscription management.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.exceptions import APIError, AuthenticationError
from kctl_api.core.exceptions import ConnectionError as KctlConnectionError

app = typer.Typer(name="realtime", help="Real-time features — presence, heartbeat, subscribe.", no_args_is_help=True)

_BASE = "/api/v1/realtime"


# ---------------------------------------------------------------------------
# presence
# ---------------------------------------------------------------------------
@app.command()
def presence(
    ctx: typer.Context,
    scope: Annotated[str, typer.Argument(help="Presence scope (e.g. 'global', a channel name).")] = "global",
) -> None:
    """Get online users for a scope via GET /api/v1/realtime/presence/{scope}."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        data = actx.client.get(f"{_BASE}/presence/{scope}")
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    if not data:
        out.info("No presence data available.")
        return

    out.detail(
        title=f"Presence: {scope}",
        sections=[
            ("Status", [(k, str(v)) for k, v in data.items()]),
        ],
        data_for_json=data,
    )


# ---------------------------------------------------------------------------
# heartbeat
# ---------------------------------------------------------------------------
@app.command()
def heartbeat(
    ctx: typer.Context,
    scope: Annotated[str, typer.Argument(help="Presence scope.")] = "global",
) -> None:
    """Send a heartbeat ping via POST /api/v1/realtime/presence/{scope}/heartbeat."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        result = actx.client.post(f"{_BASE}/presence/{scope}/heartbeat")
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"Heartbeat sent for scope: {scope}")
    if actx.json_mode:
        out.raw_json(result)


# ---------------------------------------------------------------------------
# subscribe
# ---------------------------------------------------------------------------
@app.command()
def subscribe(
    ctx: typer.Context,
    channel: Annotated[str, typer.Argument(help="Channel name to subscribe to.")],
) -> None:
    """Subscribe to a real-time SSE channel via GET /api/v1/realtime/sse/{channel}.

    Note: This opens a streaming connection. Press Ctrl+C to stop.
    """
    actx: AppContext = ctx.obj
    out = actx.output

    out.info(f"Subscribing to channel: {channel} (Ctrl+C to stop)")
    try:
        with actx.client.stream_sse(f"{_BASE}/sse/{channel}") as response:
            for line in response.iter_lines():
                if line.strip():
                    out.text(line)
    except KeyboardInterrupt:
        out.info("Subscription stopped.")
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None
