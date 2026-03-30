"""Multi-channel notification dispatch for deployments.

Supports Mattermost (webhook), Telegram (Bot API), and Email (SMTP).
Each channel is independently configured. Channels that are not configured
are silently skipped.

Ported from lib/notify.sh, redesigned for Python.
"""

from __future__ import annotations

import os
import smtplib
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from email.mime.text import MIMEText
from typing import Any

import httpx

# Status icons and colors
STATUS_ICONS: dict[str, str] = {
    "success": "\u2705",
    "failure": "\u274c",
    "warning": "\u26a0\ufe0f",
    "info": "\u2139\ufe0f",
    "rollback": "\u21a9\ufe0f",
}

STATUS_COLORS: dict[str, str] = {
    "success": "#00c100",
    "failure": "#e40303",
    "warning": "#ff8c00",
    "info": "#0055cc",
    "rollback": "#ff8c00",
}


@dataclass
class NotifyConfig:
    """Configuration for all notification channels."""

    # Mattermost
    mattermost_enabled: bool = True
    mattermost_webhook_url: str = ""

    # Telegram
    telegram_enabled: bool = True
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Email
    email_enabled: bool = False
    email_to: str = ""
    email_from: str = "noreply@kodeme.io"
    email_subject_prefix: str = "[Kodeme.io]"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""

    # Context
    service_name: str = ""
    environment: str = ""

    @classmethod
    def from_env(cls) -> NotifyConfig:
        """Load notification config from environment variables."""
        return cls(
            mattermost_enabled=os.environ.get("NOTIFY_MATTERMOST", "true").lower() in ("true", "1", "yes"),
            mattermost_webhook_url=os.environ.get("MATTERMOST_WEBHOOK_URL", os.environ.get("MM_WEBHOOK_URL", "")),
            telegram_enabled=os.environ.get("NOTIFY_TELEGRAM", "true").lower() in ("true", "1", "yes"),
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
            email_enabled=os.environ.get("NOTIFY_EMAIL", "false").lower() in ("true", "1", "yes"),
            email_to=os.environ.get("EMAIL_TO", os.environ.get("NOTIFY_EMAIL_TO", "")),
            email_from=os.environ.get("EMAIL_FROM", os.environ.get("NOTIFY_EMAIL_FROM", "noreply@kodeme.io")),
            smtp_host=os.environ.get("SMTP_HOST", ""),
            smtp_port=int(os.environ.get("SMTP_PORT", "587")),
            smtp_user=os.environ.get("SMTP_USER", ""),
            smtp_pass=os.environ.get("SMTP_PASS", os.environ.get("SMTP_PASSWORD", "")),
            service_name=os.environ.get("SERVICE_NAME", ""),
            environment=os.environ.get("DEPLOY_ENV", os.environ.get("ENVIRONMENT", "")),
        )

    @classmethod
    def from_profile(cls, profile_data: dict) -> NotifyConfig:
        """Load notification config from a config.yaml profile section."""
        notify = profile_data.get("notify", profile_data.get("notifications", {}))
        if not isinstance(notify, dict):
            return cls()
        return cls(
            mattermost_enabled=notify.get("mattermost_enabled", True),
            mattermost_webhook_url=notify.get("mattermost_webhook_url", ""),
            telegram_enabled=notify.get("telegram_enabled", True),
            telegram_bot_token=notify.get("telegram_bot_token", ""),
            telegram_chat_id=notify.get("telegram_chat_id", ""),
            email_enabled=notify.get("email_enabled", False),
            email_to=notify.get("email_to", ""),
            email_from=notify.get("email_from", "noreply@kodeme.io"),
            smtp_host=notify.get("smtp_host", ""),
            smtp_port=notify.get("smtp_port", 587),
            smtp_user=notify.get("smtp_user", ""),
            smtp_pass=notify.get("smtp_pass", ""),
        )

    @property
    def has_mattermost(self) -> bool:
        return self.mattermost_enabled and bool(self.mattermost_webhook_url)

    @property
    def has_telegram(self) -> bool:
        return self.telegram_enabled and bool(self.telegram_bot_token) and bool(self.telegram_chat_id)

    @property
    def has_email(self) -> bool:
        return self.email_enabled and bool(self.email_to) and bool(self.smtp_host)

    @property
    def channels_status(self) -> dict[str, bool]:
        return {
            "mattermost": self.has_mattermost,
            "telegram": self.has_telegram,
            "email": self.has_email,
        }


def notify_mattermost(
    config: NotifyConfig,
    status: str,
    title: str,
    message: str,
    details: str = "",
) -> bool:
    """Send a rich attachment message to Mattermost via webhook."""
    if not config.has_mattermost:
        return False

    icon = STATUS_ICONS.get(status, STATUS_ICONS["info"])
    color = STATUS_COLORS.get(status, STATUS_COLORS["info"])

    fields = []
    if config.environment:
        fields.append({"short": True, "title": "Environment", "value": config.environment})
    if config.service_name:
        fields.append({"short": True, "title": "Service", "value": config.service_name})
    if details:
        fields.append({"short": False, "title": "Details", "value": details})

    payload = {
        "attachments": [
            {
                "fallback": f"{icon} {title}: {message}",
                "color": color,
                "title": f"{icon} {title}",
                "text": message,
                "fields": fields,
            }
        ]
    }

    try:
        resp = httpx.post(config.mattermost_webhook_url, json=payload, timeout=10)
        return resp.status_code < 400
    except Exception:
        return False


def notify_telegram(
    config: NotifyConfig,
    status: str,
    title: str,
    message: str,
    details: str = "",
) -> bool:
    """Send a message to Telegram via Bot API."""
    if not config.has_telegram:
        return False

    icon = STATUS_ICONS.get(status, STATUS_ICONS["info"])

    text_parts = [f"{icon} *{title}*", message]
    if config.environment:
        text_parts.append(f"Environment: `{config.environment}`")
    if config.service_name:
        text_parts.append(f"Service: `{config.service_name}`")
    if details:
        text_parts.append(f"```\n{details}\n```")

    text = "\n".join(text_parts)
    url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"

    try:
        resp = httpx.post(
            url,
            json={
                "chat_id": config.telegram_chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        return resp.status_code < 400
    except Exception:
        return False


def notify_email(
    config: NotifyConfig,
    status: str,
    title: str,
    message: str,
    details: str = "",
) -> bool:
    """Send an email notification via SMTP."""
    if not config.has_email:
        return False

    icon = STATUS_ICONS.get(status, STATUS_ICONS["info"])
    subject = f"{config.email_subject_prefix} {icon} {title}"

    body_parts = [message]
    if config.environment:
        body_parts.append(f"Environment: {config.environment}")
    if config.service_name:
        body_parts.append(f"Service: {config.service_name}")
    if details:
        body_parts.append(f"\nDetails:\n{details}")

    body = "\n".join(body_parts)

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = config.email_from
    msg["To"] = config.email_to

    try:
        import ssl

        ssl_ctx = ssl.create_default_context()
        with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl_ctx)
            if config.smtp_user and config.smtp_pass:
                smtp.login(config.smtp_user, config.smtp_pass)
            smtp.send_message(msg)
        return True
    except Exception:
        return False


def notify_all(
    config: NotifyConfig,
    status: str,
    title: str,
    message: str,
    details: str = "",
) -> dict[str, bool]:
    """Dispatch notifications to all configured channels in parallel.

    Returns dict mapping channel name to success boolean.
    Best-effort: failures are logged but don't halt execution.
    """
    results: dict[str, bool] = {}
    channels: list[tuple[str, Any]] = []

    if config.has_mattermost:
        channels.append(("mattermost", notify_mattermost))
    if config.has_telegram:
        channels.append(("telegram", notify_telegram))
    if config.has_email:
        channels.append(("email", notify_email))

    if not channels:
        return results

    with ThreadPoolExecutor(max_workers=len(channels)) as executor:
        futures = {executor.submit(fn, config, status, title, message, details): name for name, fn in channels}
        for future in as_completed(futures):
            channel_name = futures[future]
            try:
                results[channel_name] = future.result()
            except Exception:
                results[channel_name] = False

    return results


# Convenience functions


def notify_success(config: NotifyConfig, title: str, message: str, details: str = "") -> dict[str, bool]:
    return notify_all(config, "success", title, message, details)


def notify_failure(config: NotifyConfig, title: str, message: str, details: str = "") -> dict[str, bool]:
    return notify_all(config, "failure", title, message, details)


def notify_deploy_start(config: NotifyConfig, title: str, message: str, details: str = "") -> dict[str, bool]:
    return notify_all(config, "info", title, message, details)


def notify_rollback(config: NotifyConfig, title: str, message: str, details: str = "") -> dict[str, bool]:
    return notify_all(config, "rollback", title, message, details)
