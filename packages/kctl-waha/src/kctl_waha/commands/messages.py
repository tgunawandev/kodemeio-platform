"""Message sending commands.

Send text and image messages via WhatsApp sessions.
"""

from __future__ import annotations

import os
from typing import Annotated

import typer

from kctl_waha.core.callbacks import AppContext
from kctl_waha.core.exceptions import KctlError

app = typer.Typer(help="Send WhatsApp messages.")

DEFAULT_SESSION = os.environ.get("WAHA_DEFAULT_SESSION", "default")


def _format_phone(phone: str) -> str:
    """Format phone number as chatId.

    Strips '+' prefix and appends '@c.us' if not present.
    """
    phone = phone.strip()
    if phone.startswith("+"):
        phone = phone[1:]
    if "@" not in phone:
        phone = f"{phone}@c.us"
    return phone


@app.command()
def send(
    ctx: typer.Context,
    phone: Annotated[str, typer.Argument(help="Phone number (e.g. 6281234567890 or +62812345)")],
    text: Annotated[str, typer.Argument(help="Message text to send.")],
    session: Annotated[str, typer.Option("--session", "-s", help="Session name.")] = DEFAULT_SESSION,
) -> None:
    """Send a text message.

    Phone number is auto-formatted: strips '+' prefix and appends '@c.us' if needed.

    Examples:
      kctl-waha messages send 6281234567890 "Hello!"
      kctl-waha messages send +628123456 "Hi there" --session my-session
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    chat_id = _format_phone(phone)

    try:
        result = c.post(
            "sendText",
            data={
                "chatId": chat_id,
                "text": text,
                "session": session,
            },
        )
    except KctlError as e:
        out.error(f"Failed to send message: {e}")
        raise typer.Exit(1) from e

    if out.json_mode:
        out.raw_json(result)
    else:
        out.success(f"Message sent to {chat_id} via session '{session}'")
        if isinstance(result, dict):
            msg_id = result.get("id", {})
            if isinstance(msg_id, dict):
                out.kv("Message ID", msg_id.get("id", "unknown"))
            elif msg_id:
                out.kv("Message ID", str(msg_id))


@app.command("send-image")
def send_image(
    ctx: typer.Context,
    phone: Annotated[str, typer.Argument(help="Phone number (e.g. 6281234567890)")],
    url: Annotated[str, typer.Argument(help="Image URL to send.")],
    caption: Annotated[str | None, typer.Option("--caption", "-c", help="Image caption.")] = None,
    session: Annotated[str, typer.Option("--session", "-s", help="Session name.")] = DEFAULT_SESSION,
) -> None:
    """Send an image message.

    Examples:
      kctl-waha messages send-image 6281234567890 https://example.com/image.png
      kctl-waha messages send-image 6281234567890 https://example.com/photo.jpg --caption "Check this out"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    chat_id = _format_phone(phone)

    body: dict = {
        "chatId": chat_id,
        "file": {"url": url},
        "session": session,
    }
    if caption:
        body["caption"] = caption

    try:
        result = c.post("sendImage", data=body)
    except KctlError as e:
        out.error(f"Failed to send image: {e}")
        raise typer.Exit(1) from e

    if out.json_mode:
        out.raw_json(result)
    else:
        out.success(f"Image sent to {chat_id} via session '{session}'")
        if isinstance(result, dict):
            msg_id = result.get("id", {})
            if isinstance(msg_id, dict):
                out.kv("Message ID", msg_id.get("id", "unknown"))
            elif msg_id:
                out.kv("Message ID", str(msg_id))
