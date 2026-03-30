"""Alert management commands."""

from __future__ import annotations

from typing import Annotated

import httpx
import typer

from kctl_gatus.core.callbacks import AppContext

app = typer.Typer(help="Manage and test alert channels.")


@app.command()
def test(
    ctx: typer.Context,
    channel: Annotated[
        str | None,
        typer.Argument(help="Alert channel to test: telegram, mattermost, smtp, or all"),
    ] = "all",
    telegram_token: Annotated[str | None, typer.Option("--telegram-token", envvar="TELEGRAM_BOT_TOKEN")] = None,
    telegram_chat_id: Annotated[str | None, typer.Option("--telegram-chat-id", envvar="TELEGRAM_CHAT_ID")] = None,
    mattermost_webhook: Annotated[
        str | None, typer.Option("--mattermost-webhook", envvar="MATTERMOST_WEBHOOK_URL")
    ] = None,
    smtp_host: Annotated[str | None, typer.Option("--smtp-host", envvar="SMTP_HOST")] = None,
    smtp_port: Annotated[int, typer.Option("--smtp-port", envvar="SMTP_PORT")] = 587,
) -> None:
    """Test alert channels by sending a test message."""
    actx: AppContext = ctx.obj
    out = actx.output

    results: list[dict] = []

    if channel in ("all", "telegram"):
        ok, msg = _test_telegram(telegram_token, telegram_chat_id)
        results.append({"channel": "telegram", "success": ok, "message": msg})
        if ok:
            out.success(f"Telegram: {msg}")
        else:
            out.error(f"Telegram: {msg}")

    if channel in ("all", "mattermost"):
        ok, msg = _test_mattermost(mattermost_webhook)
        results.append({"channel": "mattermost", "success": ok, "message": msg})
        if ok:
            out.success(f"Mattermost: {msg}")
        else:
            out.error(f"Mattermost: {msg}")

    if channel in ("all", "smtp"):
        ok, msg = _test_smtp(smtp_host, smtp_port)
        results.append({"channel": "smtp", "success": ok, "message": msg})
        if ok:
            out.success(f"SMTP: {msg}")
        else:
            out.error(f"SMTP: {msg}")

    if channel not in ("all", "telegram", "mattermost", "smtp"):
        out.error(f"Unknown channel: {channel}")
        out.info("Available channels: telegram, mattermost, smtp, all")
        raise typer.Exit(1)

    if out.json_mode:
        out.raw_json(results)
        return

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r["success"])
    out.text("")
    if passed == total:
        out.success(f"All {total} alert channel(s) passed")
    else:
        out.warn(f"{passed}/{total} alert channel(s) passed")


@app.command()
def history(ctx: typer.Context) -> None:
    """Show recent alert triggers (from endpoint results)."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    statuses = client.get_endpoint_statuses()

    # Collect failed checks as "alert triggers"
    alert_events: list[dict] = []

    for ep in statuses:
        name = ep.get("name", "unknown")
        group = ep.get("group", "")
        results = ep.get("results", [])

        for r in results:
            if not r.get("success", True):
                alert_events.append(
                    {
                        "endpoint": f"{group}/{name}" if group else name,
                        "timestamp": r.get("timestamp", "-"),
                        "http_status": r.get("httpStatus", "-"),
                        "duration_ms": r.get("duration", 0),
                        "hostname": r.get("hostname", "-"),
                    }
                )

    if not alert_events:
        out.success("No failed checks found — all endpoints are healthy")
        return

    # Sort by timestamp descending
    alert_events.sort(key=lambda x: x["timestamp"], reverse=True)

    # Limit to most recent 50
    recent = alert_events[:50]

    rows: list[list[str]] = []
    for evt in recent:
        ts = str(evt["timestamp"])[:19]
        rows.append(
            [
                ts,
                evt["endpoint"],
                str(evt["http_status"]),
                f"{evt['duration_ms']}ms",
            ]
        )

    out.table(
        f"Failed Checks ({len(recent)} most recent)",
        [("Timestamp", "dim"), ("Endpoint", "cyan"), ("HTTP", ""), ("Duration", "")],
        rows,
        data_for_json=recent,
    )


def _test_telegram(token: str | None, chat_id: str | None) -> tuple[bool, str]:
    """Send a test message via Telegram Bot API."""
    if not token or not chat_id:
        return False, "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required"

    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={
                "chat_id": chat_id,
                "text": "Gatus test alert from kctl-gatus CLI",
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
        data = resp.json()
        if data.get("ok"):
            return True, "Test message sent"
        return False, data.get("description", f"HTTP {resp.status_code}")
    except Exception as e:
        return False, str(e)


def _test_mattermost(webhook_url: str | None) -> tuple[bool, str]:
    """Send a test message via Mattermost webhook."""
    if not webhook_url:
        return False, "MATTERMOST_WEBHOOK_URL required"

    try:
        resp = httpx.post(
            webhook_url,
            json={"text": "Gatus test alert from kctl-gatus CLI"},
            timeout=10,
        )
        if resp.status_code == 200:
            return True, "Test message sent"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)


def _test_smtp(host: str | None, port: int) -> tuple[bool, str]:
    """Test SMTP connectivity (connect only, no message sent)."""
    if not host:
        return False, "SMTP_HOST required"

    import socket

    try:
        sock = socket.create_connection((host, port), timeout=5)
        sock.close()
        return True, f"SMTP server reachable at {host}:{port}"
    except Exception as e:
        return False, f"Cannot reach {host}:{port}: {e}"
