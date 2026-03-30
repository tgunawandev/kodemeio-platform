"""WebSocket testing commands for kctl-api.

Connect, send, listen, and load test WebSocket endpoints.
"""

from __future__ import annotations

import asyncio
import time
from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext

app = typer.Typer(name="ws", help="WebSocket testing — connect, send, listen, load-test.", no_args_is_help=True)


def _build_ws_url(actx: AppContext, endpoint: str) -> str:
    """Convert HTTP base URL to WebSocket URL."""
    base = actx.client.base_url.rstrip("/")
    ws_base = base.replace("https://", "wss://").replace("http://", "ws://")
    if not endpoint.startswith("/"):
        endpoint = f"/{endpoint}"
    return f"{ws_base}{endpoint}"


# ---------------------------------------------------------------------------
# connect
# ---------------------------------------------------------------------------
@app.command()
def connect(
    ctx: typer.Context,
    endpoint: Annotated[str, typer.Argument(help="WebSocket endpoint path (e.g. /api/v1/ws/chat).")],
    token: Annotated[str | None, typer.Option("--token", help="Bearer token for auth.")] = None,
) -> None:
    """Open a WebSocket connection and show the handshake."""
    actx: AppContext = ctx.obj
    out = actx.output

    ws_url = _build_ws_url(actx, endpoint)
    out.info(f"Connecting to {ws_url} ...")

    async def _run() -> dict:
        try:
            import websockets  # type: ignore[import-untyped]
        except ImportError:
            raise RuntimeError("websockets not installed. Run: uv add websockets") from None

        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif actx.client.api_key:
            headers["Authorization"] = f"Bearer {actx.client.api_key}"

        start = time.monotonic()
        try:
            async with websockets.connect(ws_url, additional_headers=headers) as ws:
                elapsed_ms = round((time.monotonic() - start) * 1000)
                return {
                    "url": ws_url,
                    "connected": True,
                    "handshake_ms": elapsed_ms,
                    "subprotocol": ws.subprotocol,
                    "remote_address": str(ws.remote_address),
                }
        except Exception as e:
            elapsed_ms = round((time.monotonic() - start) * 1000)
            return {"url": ws_url, "connected": False, "error": str(e), "handshake_ms": elapsed_ms}

    try:
        result = asyncio.run(_run())
    except RuntimeError as e:
        out.error(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        out.error(f"Connection failed: {e}")
        raise typer.Exit(1) from None

    if result.get("connected"):
        out.success(f"Connected in {result['handshake_ms']}ms")
        sections = [
            (
                "Handshake",
                [
                    ("URL", result["url"]),
                    ("Latency", f"{result['handshake_ms']}ms"),
                    ("Subprotocol", str(result.get("subprotocol") or "none")),
                    ("Remote", str(result.get("remote_address", ""))),
                ],
            )
        ]
        out.detail(title="WebSocket Connection", sections=sections, data_for_json=result)
    else:
        out.error(f"Connection failed: {result.get('error')}")
        if actx.json_mode:
            out.raw_json(result)
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# send
# ---------------------------------------------------------------------------
@app.command()
def send(
    ctx: typer.Context,
    endpoint: Annotated[str, typer.Argument(help="WebSocket endpoint path.")],
    message: Annotated[str, typer.Argument(help="Message to send (string or JSON).")],
    token: Annotated[str | None, typer.Option("--token", help="Bearer token.")] = None,
    timeout: Annotated[int, typer.Option("--timeout", help="Wait N seconds for response.")] = 5,
) -> None:
    """Send a message over WebSocket and show the response."""
    actx: AppContext = ctx.obj
    out = actx.output

    ws_url = _build_ws_url(actx, endpoint)
    out.info(f"Sending to {ws_url} ...")

    async def _run() -> dict:
        try:
            import websockets  # type: ignore[import-untyped]
        except ImportError:
            raise RuntimeError("websockets not installed. Run: uv add websockets") from None

        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif actx.client.api_key:
            headers["Authorization"] = f"Bearer {actx.client.api_key}"

        async with websockets.connect(ws_url, additional_headers=headers) as ws:
            await ws.send(message)
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=timeout)
                return {"sent": message, "received": response, "success": True}
            except TimeoutError:
                return {"sent": message, "received": None, "success": False, "error": f"No response within {timeout}s"}

    try:
        result = asyncio.run(_run())
    except RuntimeError as e:
        out.error(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        out.error(f"WebSocket error: {e}")
        raise typer.Exit(1) from None

    if result.get("success"):
        out.success("Message sent and response received.")
        out.text(f"  Sent:     {result['sent']}")
        out.text(f"  Received: {result['received']}")
    else:
        out.warn(f"Sent message but: {result.get('error', 'no response')}")

    if actx.json_mode:
        out.raw_json(result)


# ---------------------------------------------------------------------------
# listen
# ---------------------------------------------------------------------------
@app.command()
def listen(
    ctx: typer.Context,
    endpoint: Annotated[str, typer.Argument(help="WebSocket endpoint path.")],
    duration: Annotated[int, typer.Option("--duration", help="Listen for N seconds.")] = 30,
    token: Annotated[str | None, typer.Option("--token", help="Bearer token.")] = None,
) -> None:
    """Listen for incoming WebSocket messages for a duration."""
    actx: AppContext = ctx.obj
    out = actx.output

    ws_url = _build_ws_url(actx, endpoint)
    out.info(f"Listening on {ws_url} for {duration}s (Ctrl+C to stop) ...")

    async def _run() -> list[str]:
        try:
            import websockets  # type: ignore[import-untyped]
        except ImportError:
            raise RuntimeError("websockets not installed. Run: uv add websockets") from None

        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif actx.client.api_key:
            headers["Authorization"] = f"Bearer {actx.client.api_key}"

        messages: list[str] = []
        deadline = time.monotonic() + duration

        async with websockets.connect(ws_url, additional_headers=headers) as ws:
            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 1.0))
                    messages.append(str(msg))
                    typer.echo(f"  [{len(messages)}] {msg}")
                except TimeoutError:
                    continue

        return messages

    try:
        messages = asyncio.run(_run())
    except RuntimeError as e:
        out.error(str(e))
        raise typer.Exit(1) from None
    except KeyboardInterrupt:
        out.info("Listening stopped.")
        return
    except Exception as e:
        out.error(f"WebSocket error: {e}")
        raise typer.Exit(1) from None

    out.success(f"Received {len(messages)} messages in {duration}s.")
    if actx.json_mode:
        out.raw_json({"messages": messages, "count": len(messages)})


# ---------------------------------------------------------------------------
# load-test
# ---------------------------------------------------------------------------
@app.command(name="load-test")
def load_test(
    ctx: typer.Context,
    endpoint: Annotated[str, typer.Argument(help="WebSocket endpoint path.")],
    connections: Annotated[int, typer.Option("--connections", help="Number of concurrent connections.")] = 10,
    duration: Annotated[int, typer.Option("--duration", help="Test duration in seconds.")] = 10,
    token: Annotated[str | None, typer.Option("--token", help="Bearer token.")] = None,
) -> None:
    """Concurrent WebSocket connection load test."""
    actx: AppContext = ctx.obj
    out = actx.output

    ws_url = _build_ws_url(actx, endpoint)
    out.info(f"Load testing {ws_url} — {connections} connections for {duration}s ...")

    async def _single_connection(conn_id: int, results: list[dict]) -> None:
        try:
            import websockets  # type: ignore[import-untyped]
        except ImportError:
            return

        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif actx.client.api_key:
            headers["Authorization"] = f"Bearer {actx.client.api_key}"

        start = time.monotonic()
        messages_received = 0
        error: str | None = None

        try:
            async with websockets.connect(ws_url, additional_headers=headers) as ws:
                connected_ms = round((time.monotonic() - start) * 1000)
                deadline = start + duration
                while time.monotonic() < deadline:
                    remaining = deadline - time.monotonic()
                    try:
                        await asyncio.wait_for(ws.recv(), timeout=min(remaining, 0.5))
                        messages_received += 1
                    except TimeoutError:
                        continue
        except Exception as e:
            error = str(e)
            connected_ms = round((time.monotonic() - start) * 1000)

        results.append(
            {
                "connection": conn_id,
                "connected": error is None,
                "connect_ms": connected_ms,
                "messages_received": messages_received,
                "error": error,
            }
        )

    async def _run() -> list[dict]:
        try:
            import websockets  # type: ignore[import-untyped]

            _ = websockets
        except ImportError:
            raise RuntimeError("websockets not installed. Run: uv add websockets") from None

        results: list[dict] = []
        tasks = [_single_connection(i + 1, results) for i in range(connections)]
        await asyncio.gather(*tasks, return_exceptions=True)
        return results

    try:
        results = asyncio.run(_run())
    except RuntimeError as e:
        out.error(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        out.error(f"Load test failed: {e}")
        raise typer.Exit(1) from None

    successful = sum(1 for r in results if r.get("connected"))
    failed = len(results) - successful
    avg_connect_ms = round(sum(r.get("connect_ms", 0) for r in results) / max(len(results), 1))
    total_messages = sum(r.get("messages_received", 0) for r in results)

    out.text("")
    out.text(f"  Connections:       {connections}")
    out.text(f"  Successful:        [green]{successful}[/green]")
    out.text(f"  Failed:            [red]{failed}[/red]")
    out.text(f"  Avg connect:       {avg_connect_ms}ms")
    out.text(f"  Total messages:    {total_messages}")

    if actx.json_mode:
        out.raw_json(
            {
                "connections": connections,
                "successful": successful,
                "failed": failed,
                "avg_connect_ms": avg_connect_ms,
                "total_messages": total_messages,
                "results": results,
            }
        )
