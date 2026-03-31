"""Webhook notification helper for Mattermost/Slack-compatible webhooks."""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)


def _resolve_webhook_url(webhook_url: str | None = None) -> str | None:
    """Resolve webhook URL from argument or environment variables."""
    if webhook_url:
        return webhook_url
    return os.environ.get("KCTL_CLOUDFLARE_WEBHOOK_URL") or os.environ.get("MATTERMOST_WEBHOOK_URL")


def _resolve_channel(channel: str | None = None) -> str | None:
    """Resolve channel from argument or environment variables."""
    if channel:
        return channel
    return os.environ.get("KCTL_CLOUDFLARE_WEBHOOK_CHANNEL") or os.environ.get("MATTERMOST_CHANNEL")


def send_webhook(
    message: str,
    channel: str | None = None,
    webhook_url: str | None = None,
) -> bool:
    """Send a message to a Mattermost/Slack-compatible webhook.

    Args:
        message: The message text to send.
        channel: Target channel override. Falls back to
            ``KCTL_CLOUDFLARE_WEBHOOK_CHANNEL`` or ``MATTERMOST_CHANNEL``.
        webhook_url: Webhook endpoint URL. Falls back to
            ``KCTL_CLOUDFLARE_WEBHOOK_URL`` or ``MATTERMOST_WEBHOOK_URL``.

    Returns:
        ``True`` on success (2xx response), ``False`` on failure or if no
        webhook URL is configured.
    """
    url = _resolve_webhook_url(webhook_url)
    if not url:
        return False

    resolved_channel = _resolve_channel(channel)

    payload: dict[str, str] = {"text": message}
    if resolved_channel:
        payload["channel"] = resolved_channel

    try:
        response = httpx.post(url, json=payload, timeout=10.0)
        if response.is_success:
            return True
        logger.warning("Webhook returned %d: %s", response.status_code, response.text)
    except httpx.HTTPError as exc:
        logger.warning("Webhook request failed: %s", exc)

    return False


def notify_health(
    passed: int,
    total: int,
    issues: list[str],
    webhook_url: str | None = None,
) -> bool:
    """Send a health check summary notification.

    Args:
        passed: Number of checks that passed.
        total: Total number of checks.
        issues: List of issue descriptions for failed checks.
        webhook_url: Optional webhook URL override.

    Returns:
        ``True`` on successful delivery, ``False`` otherwise.
    """
    if passed == total:
        message = f":white_check_mark: **kctl-cf** health: {passed}/{total} checks passed"
    else:
        issue_lines = "\n".join(f"- {issue}" for issue in issues)
        message = f":warning: **kctl-cf** health: {passed}/{total} checks passed\n{issue_lines}"

    return send_webhook(message, webhook_url=webhook_url)


def notify_terraform(
    action: str,
    success: bool,
    user: str | None = None,
) -> bool:
    """Send a Terraform action notification.

    Args:
        action: The Terraform action performed (e.g. ``"apply"`` or ``"destroy"``).
        success: Whether the action completed successfully.
        user: The user who triggered the action.

    Returns:
        ``True`` on successful delivery, ``False`` otherwise.
    """
    if success:
        user_part = f" by `{user}`" if user else ""
        message = f":white_check_mark: **kctl-cf** terraform {action} completed{user_part}"
    else:
        message = f":x: **kctl-cf** terraform {action} FAILED"

    return send_webhook(message)
