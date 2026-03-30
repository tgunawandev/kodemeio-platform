"""Email sending via SMTP for notifications and onboarding.

Supports welcome emails, recovery/password-reset emails, and test emails.
SMTP config is read from the config profile or environment variables.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from kctl_ak.core.config import get_service_config, resolve_active_profile_name


@dataclass
class SmtpConfig:
    host: str = ""
    port: int = 587
    username: str = ""
    password: str = ""
    use_tls: bool = True
    use_ssl: bool = False
    from_address: str = ""
    from_name: str = "Kodemeio"

    @property
    def is_configured(self) -> bool:
        return bool(self.host and self.username and self.password and self.from_address)


def resolve_smtp_config() -> SmtpConfig:
    """Resolve SMTP config from config file then environment variables.

    Priority:
    1. Config file profile's authentik.smtp section
    2. Environment variables (EMAIL_HOST, etc.)
    """
    smtp_cfg = SmtpConfig()

    # Try config file first (service-scoped)
    pname = resolve_active_profile_name()
    svc = get_service_config(pname)
    if svc.smtp:
        s = svc.smtp
        smtp_cfg = SmtpConfig(
            host=s.host,
            port=s.port,
            username=s.username,
            password=s.password,
            use_tls=s.use_tls,
            use_ssl=s.use_ssl,
            from_address=s.from_address,
            from_name=s.from_name,
        )

    # Environment variable overrides
    if env := os.environ.get("EMAIL_HOST"):
        smtp_cfg.host = env
    if env := os.environ.get("EMAIL_PORT"):
        smtp_cfg.port = int(env)
    if env := os.environ.get("EMAIL_USERNAME"):
        smtp_cfg.username = env
    if env := os.environ.get("EMAIL_PASSWORD"):
        smtp_cfg.password = env
    if env := os.environ.get("EMAIL_USE_TLS"):
        smtp_cfg.use_tls = env.lower() in ("true", "1", "yes")
    if env := os.environ.get("EMAIL_USE_SSL"):
        smtp_cfg.use_ssl = env.lower() in ("true", "1", "yes")
    if env := os.environ.get("EMAIL_FROM"):
        smtp_cfg.from_address = env
    if env := os.environ.get("EMAIL_FROM_NAME"):
        smtp_cfg.from_name = env

    return smtp_cfg


def send_email(
    to: str,
    subject: str,
    html_body: str,
    smtp: SmtpConfig | None = None,
) -> None:
    """Send an HTML email via SMTP."""
    if smtp is None:
        smtp = resolve_smtp_config()

    if not smtp.is_configured:
        raise RuntimeError(
            "SMTP not configured. Set EMAIL_HOST, EMAIL_USERNAME, EMAIL_PASSWORD, EMAIL_FROM "
            "environment variables or add smtp section to config profile."
        )

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{smtp.from_name} <{smtp.from_address}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    context = ssl.create_default_context()

    if smtp.use_ssl:
        with smtplib.SMTP_SSL(smtp.host, smtp.port, context=context) as server:
            server.login(smtp.username, smtp.password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(smtp.host, smtp.port) as server:
            if smtp.use_tls:
                server.starttls(context=context)
            server.login(smtp.username, smtp.password)
            server.send_message(msg)


def build_welcome_email(
    name: str,
    email: str,
    recovery_link: str = "",
    password: str = "",
    auth_url: str = "https://auth.kodeme.io",
    tenant: str = "Kodemeio",
) -> tuple[str, str]:
    """Build welcome email subject and HTML body."""
    subject = f"Welcome to {tenant} - Set Up Your Account"

    credential_section = ""
    if recovery_link:
        credential_section = f"""
    <div style="text-align: center; margin: 30px 0;">
      <a href="{recovery_link}" style="background: #2563eb; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: 600; display: inline-block;">Set Up Your Password</a>
    </div>
    <p style="font-size: 14px; color: #666;">If the button doesn't work, copy and paste this link:</p>
    <p style="font-size: 13px; color: #888; word-break: break-all;">{recovery_link}</p>
    <p style="font-size: 14px; color: #cc0000;">This link expires in 60 minutes and can only be used once.</p>"""
    elif password:
        credential_section = f"""
    <div style="background: #f0f4f8; border-radius: 8px; padding: 20px; margin: 20px 0;">
      <h3 style="margin-top: 0; font-size: 16px;">Your Credentials</h3>
      <table style="font-size: 14px; line-height: 2;">
        <tr><td style="font-weight: 600; padding-right: 15px;">Email:</td><td>{email}</td></tr>
        <tr><td style="font-weight: 600; padding-right: 15px;">Password:</td><td><code style="background: #e2e8f0; padding: 2px 8px; border-radius: 3px;">{password}</code></td></tr>
      </table>
      <p style="font-size: 13px; color: #cc0000; margin-bottom: 0;">Please change your password after first login.</p>
    </div>"""

    body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
  <div style="background: #f8f9fa; border-radius: 8px; padding: 30px; margin-bottom: 20px;">
    <h1 style="color: #1a1a1a; margin-top: 0; font-size: 24px;">Welcome to {tenant}</h1>
    <p style="font-size: 16px; line-height: 1.5;">Hi <strong>{name}</strong>,</p>
    <p style="font-size: 16px; line-height: 1.5;">Your account has been created. Please use the information below to get started.</p>
    {credential_section}
  </div>
  <div style="background: #f0f4f8; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
    <h3 style="margin-top: 0; font-size: 16px;">Your Services</h3>
    <table style="width: 100%; font-size: 14px; line-height: 1.8;">
      <tr><td style="font-weight: 600;">Login Portal:</td><td><a href="{auth_url}" style="color: #2563eb;">{auth_url}</a></td></tr>
    </table>
  </div>
  <div style="font-size: 13px; color: #999; border-top: 1px solid #eee; padding-top: 15px;">
    <p>This is an automated message from {tenant}. If you did not expect this email, please ignore it.</p>
  </div>
</body>
</html>"""

    return subject, body


def build_recovery_email(
    name: str,
    recovery_link: str,
    auth_url: str = "https://auth.kodeme.io",
    tenant: str = "Kodemeio",
) -> tuple[str, str]:
    """Build password recovery email subject and HTML body."""
    subject = f"{tenant} - Password Reset"

    body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
  <div style="background: #f8f9fa; border-radius: 8px; padding: 30px; margin-bottom: 20px;">
    <h1 style="color: #1a1a1a; margin-top: 0; font-size: 24px;">Password Reset</h1>
    <p style="font-size: 16px; line-height: 1.5;">Hi <strong>{name}</strong>,</p>
    <p style="font-size: 16px; line-height: 1.5;">A password reset has been requested for your account. Click the button below to set a new password.</p>
    <div style="text-align: center; margin: 30px 0;">
      <a href="{recovery_link}" style="background: #2563eb; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: 600; display: inline-block;">Reset Password</a>
    </div>
    <p style="font-size: 14px; color: #666;">If the button doesn't work, copy and paste this link:</p>
    <p style="font-size: 13px; color: #888; word-break: break-all;">{recovery_link}</p>
    <p style="font-size: 14px; color: #cc0000;">This link expires in 60 minutes and can only be used once.</p>
  </div>
  <div style="font-size: 13px; color: #999; border-top: 1px solid #eee; padding-top: 15px;">
    <p>If you did not request this reset, you can safely ignore this email. Your password will not change.</p>
    <p>Login portal: <a href="{auth_url}" style="color: #2563eb;">{auth_url}</a></p>
  </div>
</body>
</html>"""

    return subject, body
