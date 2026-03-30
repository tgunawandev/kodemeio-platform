"""Authentication commands for kctl-api.

Login, logout, token refresh, and user identity inspection.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.config import (
    ServiceConfig,
    get_service_config,
    resolve_active_profile_name,
    set_service_config,
)
from kctl_api.core.exceptions import APIError, AuthenticationError
from kctl_api.core.exceptions import ConnectionError as KctlConnectionError
from kctl_api.core.utils import mask_secret, role_color, tier_color

app = typer.Typer(name="auth", help="Authentication and identity management.", no_args_is_help=True)


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------
@app.command()
def login(
    ctx: typer.Context,
    email: Annotated[str | None, typer.Option("--email", "-e", help="Account email.")] = None,
    password: Annotated[str | None, typer.Option("--password", "-p", help="Account password.", hide_input=True)] = None,
) -> None:
    """Authenticate with email and password, cache JWT tokens in profile."""
    actx: AppContext = ctx.obj
    out = actx.output

    # Interactive prompts if not provided via flags
    if not email:
        email = typer.prompt("Email")
    if not password:
        password = typer.prompt("Password", hide_input=True)

    out.info("Authenticating ...")

    try:
        tokens = actx.client.login(email, password)
    except AuthenticationError as e:
        out.error(f"Login failed: {e}")
        raise typer.Exit(1) from None
    except KctlConnectionError as e:
        out.error(f"Connection failed: {e}")
        raise typer.Exit(1) from None
    except APIError as e:
        out.error(f"API error: {e.detail}")
        raise typer.Exit(1) from None

    # Persist the access token into the profile config
    profile_name = resolve_active_profile_name(actx.profile)
    svc = get_service_config(profile_name)
    updated = ServiceConfig(
        url=svc.url,
        ai_url=svc.ai_url,
        api_key=tokens.get("access_token", svc.api_key),
        database_url=svc.database_url,
        redis_url=svc.redis_url,
    )
    set_service_config(profile_name, updated)

    out.success(f"Logged in as {email} (profile: {profile_name}).")

    if actx.json_mode:
        out.raw_json(
            {
                "email": email,
                "profile": profile_name,
                "access_token": mask_secret(tokens.get("access_token", "")),
                "has_refresh_token": bool(tokens.get("refresh_token")),
            }
        )


# ---------------------------------------------------------------------------
# logout
# ---------------------------------------------------------------------------
@app.command()
def logout(ctx: typer.Context) -> None:
    """Clear cached tokens from the active profile."""
    actx: AppContext = ctx.obj
    out = actx.output

    # Try server-side logout (best-effort)
    import contextlib

    with contextlib.suppress(Exception):
        actx.client.post("/api/v1/auth/logout")

    # Clear api_key (JWT token) from profile
    profile_name = resolve_active_profile_name(actx.profile)
    svc = get_service_config(profile_name)
    updated = ServiceConfig(
        url=svc.url,
        ai_url=svc.ai_url,
        api_key="",
        database_url=svc.database_url,
        redis_url=svc.redis_url,
    )
    set_service_config(profile_name, updated)

    out.success(f"Logged out (profile: {profile_name}). Tokens cleared.")

    if actx.json_mode:
        out.raw_json({"profile": profile_name, "logged_out": True})


# ---------------------------------------------------------------------------
# refresh
# ---------------------------------------------------------------------------
@app.command()
def refresh(ctx: typer.Context) -> None:
    """Refresh the JWT access token using the refresh token."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        tokens = actx.client.refresh()
    except AuthenticationError as e:
        out.error(f"Refresh failed: {e}")
        raise typer.Exit(1) from None
    except KctlConnectionError as e:
        out.error(f"Connection failed: {e}")
        raise typer.Exit(1) from None
    except APIError as e:
        out.error(f"API error: {e.detail}")
        raise typer.Exit(1) from None

    # Update stored token
    new_token = tokens.get("access_token", "")
    if new_token:
        profile_name = resolve_active_profile_name(actx.profile)
        svc = get_service_config(profile_name)
        updated = ServiceConfig(
            url=svc.url,
            ai_url=svc.ai_url,
            api_key=new_token,
            database_url=svc.database_url,
            redis_url=svc.redis_url,
        )
        set_service_config(profile_name, updated)
        out.success("Token refreshed and saved.")
    else:
        out.warn("Server returned no access token.")

    if actx.json_mode:
        out.raw_json(
            {
                "refreshed": bool(new_token),
                "access_token": mask_secret(new_token) if new_token else None,
            }
        )


# ---------------------------------------------------------------------------
# whoami
# ---------------------------------------------------------------------------
@app.command()
def whoami(ctx: typer.Context) -> None:
    """Display current authenticated user info."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        user = actx.client.get("/api/v1/auth/me")
    except AuthenticationError as e:
        out.error(f"Not authenticated: {e}")
        raise typer.Exit(1) from None
    except KctlConnectionError as e:
        out.error(f"Connection failed: {e}")
        raise typer.Exit(1) from None
    except APIError as e:
        out.error(f"API error: {e.detail}")
        raise typer.Exit(1) from None

    if not user:
        out.error("No user data returned.")
        raise typer.Exit(1)

    role = user.get("role", "unknown")
    tier = user.get("tier", "unknown")

    out.detail(
        title="Current User",
        sections=[
            (
                "Identity",
                [
                    ("ID", str(user.get("id", ""))),
                    ("Email", user.get("email", "")),
                    ("Name", user.get("name", user.get("full_name", ""))),
                ],
            ),
            (
                "Access",
                [
                    ("Role", role_color(role)),
                    ("Tier", tier_color(tier)),
                    ("Active", str(user.get("is_active", ""))),
                ],
            ),
        ],
        data_for_json=user,
    )


# ---------------------------------------------------------------------------
# token-info
# ---------------------------------------------------------------------------
def _decode_jwt_payload(token: str) -> dict:
    """Decode JWT payload without verification (base64 only, no PyJWT)."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format: expected 3 dot-separated parts.")

    # Decode the payload (second part)
    payload_b64 = parts[1]
    # Add padding if needed
    padding = 4 - len(payload_b64) % 4
    if padding != 4:
        payload_b64 += "=" * padding

    payload_bytes = base64.urlsafe_b64decode(payload_b64)
    return json.loads(payload_bytes)


def _format_timestamp(ts: int | float | None) -> str:
    """Format a Unix timestamp to human-readable UTC string."""
    if ts is None:
        return "(not set)"
    try:
        dt = datetime.fromtimestamp(float(ts), tz=UTC)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (OSError, ValueError):
        return str(ts)


@app.command(name="token-info")
def token_info(
    ctx: typer.Context,
    token: Annotated[
        str | None, typer.Option("--token", "-t", help="JWT token to inspect (default: from profile).")
    ] = None,
) -> None:
    """Decode and display JWT token claims (without cryptographic verification)."""
    actx: AppContext = ctx.obj
    out = actx.output

    # Resolve token: explicit flag > profile config
    if not token:
        profile_name = resolve_active_profile_name(actx.profile)
        svc = get_service_config(profile_name)
        token = svc.api_key

    if not token:
        out.error("No token available. Login first: kctl-api auth login")
        raise typer.Exit(1)

    try:
        claims = _decode_jwt_payload(token)
    except (ValueError, json.JSONDecodeError) as e:
        out.error(f"Failed to decode token: {e}")
        raise typer.Exit(1) from None

    # Determine expiry status
    exp = claims.get("exp")
    now_ts = datetime.now(tz=UTC).timestamp()
    expired = exp is not None and float(exp) < now_ts
    exp_display = _format_timestamp(exp)
    if expired:
        exp_display = f"[red]{exp_display} (EXPIRED)[/red]"

    iat_display = _format_timestamp(claims.get("iat"))

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Token Claims",
            [
                ("Subject (sub)", str(claims.get("sub", "(none)"))),
                ("Email", str(claims.get("email", "(none)"))),
                ("Role", str(claims.get("role", "(none)"))),
                ("Tier", str(claims.get("tier", "(none)"))),
                ("Issued At (iat)", iat_display),
                ("Expires (exp)", exp_display),
                ("Issuer (iss)", str(claims.get("iss", "(none)"))),
                ("Token Type", str(claims.get("type", claims.get("token_type", "(none)")))),
            ],
        ),
    ]

    # Show all extra claims not already displayed
    known_keys = {"sub", "email", "role", "tier", "iat", "exp", "iss", "type", "token_type"}
    extra = {k: v for k, v in claims.items() if k not in known_keys}
    if extra:
        sections.append(
            ("Additional Claims", [(k, str(v)) for k, v in sorted(extra.items())]),
        )

    json_data = {**claims, "_expired": expired, "_exp_formatted": _format_timestamp(exp)}

    out.detail(title="JWT Token Info", sections=sections, data_for_json=json_data)
