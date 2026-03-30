"""Email commands: send recovery/welcome emails via Authentik's SMTP."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_ak.core.callbacks import AppContext
from kctl_ak.core.resolve import resolve_user

app = typer.Typer(help="Email operations (uses Authentik's built-in SMTP).")

# Stage names used by kctl-ak
_RECOVERY_STAGE_NAME = "recovery-email"
_WELCOME_STAGE_NAME = "welcome-email"


def _find_stage_by_name(client, name: str) -> str | None:  # type: ignore[type-arg]
    """Find an email stage by name, return PK or None."""
    try:
        data = client.get("stages/email/", params={"name": name})
        results = data.get("results", [])
        if results:
            return results[0]["pk"]
    except Exception:
        pass
    return None


def _ensure_recovery_stage(client, output) -> str:  # type: ignore[type-arg]
    """Find or create the password reset email stage."""
    pk = _find_stage_by_name(client, _RECOVERY_STAGE_NAME)
    if pk:
        return pk
    output.info("Creating recovery email stage...")
    result = client.post(
        "stages/email/",
        data={
            "name": _RECOVERY_STAGE_NAME,
            "use_global_settings": True,
            "template": "email/password_reset.html",
            "subject": "Kodemeio - Password Reset",
            "token_expiry": "minutes=60",
            "activate_user_on_success": True,
        },
    )
    output.success("Recovery email stage created")
    return result["pk"]


def _ensure_welcome_stage(client, output) -> str:  # type: ignore[type-arg]
    """Find or create the welcome/account confirmation email stage."""
    pk = _find_stage_by_name(client, _WELCOME_STAGE_NAME)
    if pk:
        return pk
    output.info("Creating welcome email stage...")
    result = client.post(
        "stages/email/",
        data={
            "name": _WELCOME_STAGE_NAME,
            "use_global_settings": True,
            "template": "email/account_confirmation.html",
            "subject": "Welcome to Kodemeio - Set Up Your Account",
            "token_expiry": "hours=72",
            "activate_user_on_success": True,
        },
    )
    output.success("Welcome email stage created")
    return result["pk"]


# Public aliases for use by other modules (users.py --send-mail)
def ensure_recovery_stage(client, output) -> str:  # type: ignore[type-arg]
    return _ensure_recovery_stage(client, output)


def ensure_welcome_stage(client, output) -> str:  # type: ignore[type-arg]
    return _ensure_welcome_stage(client, output)


@app.command()
def test(
    ctx: typer.Context,
    to: Annotated[
        str | None, typer.Option(help="Send test email to this address (must be an existing user's email)")
    ] = None,
) -> None:
    """Test email configuration by checking Authentik's SMTP and email stages."""
    c: AppContext = ctx.obj
    out = c.output

    out.header("Authentik Email Configuration")

    # Check email stages
    recovery_pk = _find_stage_by_name(c.client, _RECOVERY_STAGE_NAME)
    welcome_pk = _find_stage_by_name(c.client, _WELCOME_STAGE_NAME)
    out.kv("Recovery Stage", f"OK ({recovery_pk[:8]}...)" if recovery_pk else "(will auto-create)")
    out.kv("Welcome Stage", f"OK ({welcome_pk[:8]}...)" if welcome_pk else "(will auto-create)")

    # Check recovery flow
    try:
        brands = c.client.get("core/brands/")
        brand = brands.get("results", [{}])[0]
        recovery_flow = brand.get("flow_recovery")
        out.kv("Recovery Flow", f"OK ({recovery_flow[:8]}...)" if recovery_flow else "[red]NOT SET[/red]")
        if not recovery_flow:
            out.warn("No recovery flow set on brand. Run: kctl-ak setup recovery-flow")
    except Exception:
        out.kv("Recovery Flow", "(could not check)")

    out.success("Email is configured server-side (Authentik .env.prod EMAIL_* vars)")

    if to:
        out.info(f"Sending test welcome email to {to}...")
        users = c.client.get("core/users/", params={"email": to})
        results = users.get("results", [])
        if not results:
            out.error(f"No user found with email {to}. Create one first.")
            raise typer.Exit(1)

        user_pk = results[0]["pk"]
        stage = _ensure_welcome_stage(c.client, out)
        try:
            c.client.post(
                f"core/users/{user_pk}/recovery_email/",
                data={
                    "email": to,
                    "email_stage": stage,
                },
            )
            out.success(f"Welcome email sent to {to}")
        except Exception as e:
            out.error(f"Failed: {e}")
            raise typer.Exit(1) from e
    else:
        out.info("Use --to <email> to send a test email (must match an existing user)")


@app.command("send-recovery")
def send_recovery(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="User ID, username, or email")],
) -> None:
    """Send a password reset email to a user.

    Uses Authentik's password_reset.html template. The email says
    "Reset your password" with a link to set a new one.
    """
    c: AppContext = ctx.obj
    pk = resolve_user(c.client, identifier)
    user = c.client.get(f"core/users/{pk}/")
    email = user.get("email", "")
    name = user.get("name", "") or user.get("username", "")

    if not email:
        c.output.error(f"User {pk} has no email address")
        raise typer.Exit(1)

    stage = _ensure_recovery_stage(c.client, c.output)

    c.output.info(f"Sending password reset email to {email}...")
    try:
        c.client.post(
            f"core/users/{pk}/recovery_email/",
            data={
                "email": email,
                "email_stage": stage,
            },
        )
        c.output.success(f"Password reset email sent to {email}")
        c.output.info(f"User: {name} (ID: {pk})")
        c.output.info("Link expires in 60 minutes")
    except Exception as e:
        c.output.error(f"Failed: {e}")
        raise typer.Exit(1) from e


@app.command("send-welcome")
def send_welcome(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="User ID, username, or email")],
) -> None:
    """Send a welcome/onboarding email to a new user.

    Uses Authentik's account_confirmation.html template. The email says
    "Welcome - set up your account" with a link to create their password.
    Link is valid for 72 hours (longer than recovery).
    """
    c: AppContext = ctx.obj
    pk = resolve_user(c.client, identifier)
    user = c.client.get(f"core/users/{pk}/")
    email = user.get("email", "")
    name = user.get("name", "") or user.get("username", "")

    if not email:
        c.output.error(f"User {pk} has no email address")
        raise typer.Exit(1)

    stage = _ensure_welcome_stage(c.client, c.output)

    c.output.info(f"Sending welcome email to {email}...")
    try:
        c.client.post(
            f"core/users/{pk}/recovery_email/",
            data={
                "email": email,
                "email_stage": stage,
            },
        )
        c.output.success(f"Welcome email sent to {email}")
        c.output.info(f"User: {name} (ID: {pk})")
        c.output.info("Link expires in 72 hours")
    except Exception as e:
        c.output.error(f"Failed: {e}")
        raise typer.Exit(1) from e


@app.command("send-password")
def send_password(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="User ID, username, or email")],
    new_password: Annotated[
        str | None, typer.Option("--password", help="Password to set (auto-generated if omitted)")
    ] = None,
) -> None:
    """Set a new password and also send a recovery email.

    Sets the password immediately (for sharing manually if needed),
    then also sends a recovery email so the user can change it.
    """
    import secrets as sec

    c: AppContext = ctx.obj
    pk = resolve_user(c.client, identifier)
    user = c.client.get(f"core/users/{pk}/")
    email = user.get("email", "")
    name = user.get("name", "") or user.get("username", "")

    if not email:
        c.output.error(f"User {pk} has no email address")
        raise typer.Exit(1)

    pw = new_password or sec.token_urlsafe(16)
    c.client.post(f"core/users/{pk}/set_password/", data={"password": pw})
    c.output.success(f"Password set for {name}: {pw}")

    stage = _ensure_recovery_stage(c.client, c.output)

    c.output.info(f"Sending recovery email to {email}...")
    try:
        c.client.post(
            f"core/users/{pk}/recovery_email/",
            data={
                "email": email,
                "email_stage": stage,
            },
        )
        c.output.success(f"Recovery email also sent to {email}")
    except Exception as e:
        c.output.warn(f"Email failed: {e} (password was still set)")


@app.command("recovery-link")
def recovery_link(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="User ID, username, or email")],
) -> None:
    """Generate a recovery link (without sending email).

    Returns the link that can be shared manually.
    """
    c: AppContext = ctx.obj
    pk = resolve_user(c.client, identifier)

    try:
        result = c.client.post(f"core/users/{pk}/recovery/", data={})
        link = result.get("link", "")
        if c.output.json_mode:
            c.output.raw_json({"user_id": pk, "link": link})
        else:
            c.output.success(f"Recovery link for user {pk}:")
            c.output.text(f"  {link}")
            c.output.info("Valid for 60 minutes, one-time use")
    except Exception as e:
        c.output.error(f"Failed: {e}")
        raise typer.Exit(1) from e
