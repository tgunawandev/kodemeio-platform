"""kctl-accurate config — profile and credential management."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_accurate.core.callbacks import AppContext
from kctl_accurate.core.client import AccurateClientWrapper
from kctl_accurate.core.config import (
    CONFIG_FILE,
    SERVICE_KEY,
    ServiceConfig,
    get_default_profile,
    get_profile_names,
    get_service_config,
    mask_secret,
    remove_profile as _remove_profile,
    resolve_active_profile_name,
    resolve_connection,
    set_default_profile,
    set_service_config,
)

app = typer.Typer(help="Manage CLI configuration and profiles.")


def _show_profile(actx: AppContext, profile: str) -> None:
    out = actx.output
    cfg = get_service_config(profile)
    out.header(f"Profile: {profile}")
    out.kv("Service", SERVICE_KEY)
    out.kv("API Token", mask_secret(cfg.api_token))
    out.kv("Signature Secret", mask_secret(cfg.signature_secret))
    out.kv("DB ID", str(cfg.db_id) if cfg.db_id else "[dim]not set[/dim]")
    out.kv("Host", cfg.host or "[dim]auto-discover[/dim]")
    out.kv("DB Alias", cfg.db_alias or "[dim]—[/dim]")


@app.command("show")
def show(
    ctx: typer.Context,
    profile: Annotated[str | None, typer.Argument(help="Profile name (default: active)")] = None,
) -> None:
    """Show one profile's accurate config (secrets masked)."""
    actx: AppContext = ctx.obj
    pname = profile or resolve_active_profile_name(actx.profile)
    _show_profile(actx, pname)


@app.command("list")
def list_cmd(ctx: typer.Context) -> None:
    """List profiles that have an accurate section."""
    actx: AppContext = ctx.obj
    out = actx.output
    default = get_default_profile()
    names = get_profile_names()
    rows = []
    for name in names:
        cfg = get_service_config(name)
        if not cfg.api_token and not cfg.db_id:
            continue
        marker = "*" if name == default else ""
        rows.append([marker, name, str(cfg.db_id) or "—", cfg.db_alias or "—"])
    out.table(
        title="Accurate Profiles",
        columns=[("", ""), ("Name", ""), ("DB ID", ""), ("Alias", "")],
        rows=rows,
    )


@app.command("use")
def use(
    ctx: typer.Context,
    profile: Annotated[str, typer.Argument(help="Profile name to set as default")],
) -> None:
    """Set the default profile."""
    actx: AppContext = ctx.obj
    out = actx.output
    set_default_profile(profile)
    out.success(f"Default profile is now: {profile}")


@app.command("add")
def add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name")],
    api_token: Annotated[str, typer.Option("--api-token", help="Accurate API token")],
    signature_secret: Annotated[str, typer.Option("--signature-secret", help="HMAC-SHA256 secret")],
    db_id: Annotated[int, typer.Option("--db-id", help="Tenant company db_id")],
    host: Annotated[str, typer.Option("--host", help="Accurate host (optional)")] = "",
) -> None:
    """Add a profile non-interactively."""
    actx: AppContext = ctx.obj
    out = actx.output
    svc = ServiceConfig(
        api_token=api_token,
        signature_secret=signature_secret,
        db_id=db_id,
        host=host,
    )
    set_service_config(name, svc)
    if len(get_profile_names()) <= 1:
        set_default_profile(name)
    out.success(f"Profile '{name}' added")


@app.command("remove")
def remove(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name")],
) -> None:
    """Remove a profile entirely (drops every service section, not just accurate)."""
    actx: AppContext = ctx.obj
    out = actx.output
    _remove_profile(name)
    out.success(f"Profile '{name}' removed")


@app.command("set")
def set_field(
    ctx: typer.Context,
    key: Annotated[
        str,
        typer.Argument(help="Field name (api_token, signature_secret, db_id, host, db_alias)"),
    ],
    value: Annotated[str, typer.Argument(help="New value")],
    profile: Annotated[
        str | None,
        typer.Option("--profile", "-p", help="Profile name (overrides global -p)"),
    ] = None,
) -> None:
    """Patch a single field on a profile."""
    actx: AppContext = ctx.obj
    out = actx.output
    pname = resolve_active_profile_name(profile or actx.profile)
    cfg = get_service_config(pname)
    valid_fields = ServiceConfig.model_fields
    if key not in valid_fields:
        out.error(f"Unknown field: {key}. Valid: {', '.join(valid_fields.keys())}")
        raise typer.Exit(2)
    # Coerce to int if the current field value is an int
    if isinstance(getattr(cfg, key), int):
        setattr(cfg, key, int(value))
    else:
        setattr(cfg, key, value)
    set_service_config(pname, cfg)
    out.success(f"{pname}.{key} updated")


@app.command("test")
def test_cmd(
    ctx: typer.Context,
    profile: Annotated[str | None, typer.Argument(help="Profile (default: active)")] = None,
) -> None:
    """Test creds: call token_info() and report verdict."""
    actx: AppContext = ctx.obj
    out = actx.output
    pname = profile or resolve_active_profile_name(actx.profile)
    cfg = resolve_connection(profile_name=pname)
    client = AccurateClientWrapper(cfg)
    info = client.token_info()
    db = (info.get("d") or {}).get("database") or {}
    out.success(f"Connected: db_id={db.get('id')} alias={db.get('alias')!r}")


@app.command("init")
def init(ctx: typer.Context) -> None:
    """Interactive setup: prompt for token + secret + db_id; verify; save."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_name = typer.prompt("Profile name", default="default")
    api_token = typer.prompt("API token", hide_input=True)
    signature_secret = typer.prompt("Signature secret", hide_input=True)
    db_id = typer.prompt("DB ID (tenant company id)", type=int)

    out.info("Verifying credentials with Accurate...")
    cfg = ServiceConfig(api_token=api_token, signature_secret=signature_secret, db_id=db_id)
    try:
        client = AccurateClientWrapper(cfg)
        info = client.token_info()
        d = (info.get("d") or {}).get("database") or {}
        cfg.host = d.get("host", "")
        cfg.db_alias = d.get("alias", "")
        out.success(f"Verified: {cfg.db_alias} @ {cfg.host}")
    except Exception as exc:
        out.error(f"Verification failed: {exc}")
        if not typer.confirm("Save profile anyway?", default=False):
            raise typer.Exit(2) from exc

    set_service_config(profile_name, cfg)
    if len(get_profile_names()) <= 1:
        set_default_profile(profile_name)
    out.success(f"Profile '{profile_name}' saved to {CONFIG_FILE}")
