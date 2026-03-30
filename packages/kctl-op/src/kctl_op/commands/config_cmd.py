"""Configuration management commands (standard kctl pattern)."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_op.core.callbacks import AppContext
from kctl_op.core.config import (
    CONFIG_FILE,
    SERVICE_KEY,
    ServiceConfig,
    get_all_services_in_profile,
    get_default_profile,
    get_profile_names,
    get_service_config,
    load_raw_config,
    remove_profile,
    save_raw_config,
    set_default_profile,
    set_service_config,
)

app = typer.Typer(help="Manage CLI configuration and profiles.")


def _mask_token(token: str) -> str:
    """Mask a token for display."""
    if not token or token.startswith("${"):
        return token or "(not set)"
    if len(token) <= 8:
        return "****"
    return token[:4] + "..." + token[-4:]


@app.command()
def init(
    ctx: typer.Context,
    vault: Annotated[str | None, typer.Option("--vault", help="1Password vault name.")] = None,
    token: Annotated[str | None, typer.Option("--token", help="Service account token.")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Profile name.")] = None,
    scan_root: Annotated[
        list[str] | None, typer.Option("--scan-root", help="Scan root directory (repeatable).")
    ] = None,
) -> None:
    """Initialize CLI configuration (interactive if no flags given)."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_name = name or typer.prompt("Profile name", default="kodemeio")
    vault_name = vault or typer.prompt("1Password vault name", default="Kodemeio")
    svc_token = token or typer.prompt(
        "Service account token (or ${ENV_VAR} reference)",
        default="${OP_SERVICE_ACCOUNT_TOKEN}",
    )

    roots: list[str] = []
    if scan_root:
        roots = scan_root
    else:
        out.info("Enter scan root directories (empty line to finish):")
        while True:
            root = typer.prompt("  Scan root", default="")
            if not root:
                break
            roots.append(root)

    if not roots:
        roots = ["."]

    # Test connection
    import os

    from kctl_op.core.client import OnePasswordClient

    expanded_token = svc_token
    if svc_token.startswith("${") and svc_token.endswith("}"):
        env_name = svc_token[2:-1]
        expanded_token = os.environ.get(env_name, "")

    if expanded_token:
        out.info("Testing 1Password connection...")
        try:
            client = OnePasswordClient(vault=vault_name, token=expanded_token)
            info = client.whoami()
            account = info.get("url", info.get("email", "unknown"))
            out.success(f"Authenticated ({account})")
        except Exception as e:
            out.error(f"Connection failed: {e}")
            if not typer.confirm("Save configuration anyway?", default=False):
                raise typer.Exit(code=1) from None
    else:
        out.warn("No token available for testing. Will save config anyway.")

    svc = ServiceConfig(
        vault=vault_name,
        service_account_token=svc_token,
        scan_roots=roots,
    )
    set_service_config(profile_name, svc)

    if len(get_profile_names()) <= 1:
        set_default_profile(profile_name)

    out.success(f"Configuration saved to {CONFIG_FILE}")
    out.kv("Profile", profile_name)
    out.kv("Service", SERVICE_KEY)
    out.kv("Vault", vault_name)
    out.kv("Token", _mask_token(svc_token))
    out.kv("Scan roots", str(len(roots)))


@app.command()
def add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to add.")],
    vault: Annotated[str | None, typer.Option("--vault", help="1Password vault name.")] = None,
    token: Annotated[str | None, typer.Option("--token", help="Service account token.")] = None,
    scan_root: Annotated[
        list[str] | None, typer.Option("--scan-root", help="Scan root directory (repeatable).")
    ] = None,
) -> None:
    """Add a new profile."""
    actx: AppContext = ctx.obj
    out = actx.output

    if name in get_profile_names():
        existing = get_service_config(name)
        if existing.vault:
            out.warn(f"Profile '{name}' already has {SERVICE_KEY} config. Use 'config set' to update.")
            raise typer.Exit(code=1)

    vault_name = vault or typer.prompt("1Password vault name")
    svc_token = token or typer.prompt("Service account token (or ${ENV_VAR} reference)")
    roots = list(scan_root) if scan_root else []
    if not roots:
        out.info("Enter scan root directories (empty line to finish):")
        while True:
            root = typer.prompt("  Scan root", default="")
            if not root:
                break
            roots.append(root)

    svc = ServiceConfig(
        vault=vault_name,
        service_account_token=svc_token,
        scan_roots=roots,
    )
    set_service_config(name, svc)
    out.success(f"Profile '{name}' added with {SERVICE_KEY} config.")


@app.command()
def use(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to set as default.")],
) -> None:
    """Set the default profile."""
    actx: AppContext = ctx.obj
    out = actx.output

    if name not in get_profile_names():
        out.error(f"Profile '{name}' not found.")
        raise typer.Exit(code=1)

    set_default_profile(name)
    out.success(f"Default profile set to '{name}'.")


@app.command(name="remove")
def remove_cmd(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to remove.")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation.")] = False,
) -> None:
    """Remove a profile's 1Password configuration."""
    actx: AppContext = ctx.obj
    out = actx.output

    if name not in get_profile_names():
        out.error(f"Profile '{name}' not found.")
        raise typer.Exit(code=1)

    if not force and not typer.confirm(f"Remove {SERVICE_KEY} config from profile '{name}'?"):
        raise typer.Exit()

    remove_profile(name)
    out.success(f"Removed {SERVICE_KEY} config from profile '{name}'.")


@app.command()
def profiles(ctx: typer.Context) -> None:
    """List all profiles."""
    actx: AppContext = ctx.obj
    out = actx.output
    default = get_default_profile()
    names = get_profile_names()

    rows = []
    json_data = []
    for name in names:
        svc = get_service_config(name)
        is_default = name == default
        marker = " [green](default)[/green]" if is_default else ""
        has_op = "[green]yes[/green]" if svc.vault else "[dim]no[/dim]"
        rows.append([f"{name}{marker}", has_op, svc.vault or "-", str(len(svc.scan_roots))])
        json_data.append(
            {
                "name": name,
                "default": is_default,
                "has_op": bool(svc.vault),
                "vault": svc.vault,
                "scan_roots": len(svc.scan_roots),
            }
        )

    out.table(
        title="Profiles",
        columns=[("Name", "green"), ("1Password", ""), ("Vault", "cyan"), ("Scan Roots", "")],
        rows=rows,
        data_for_json=json_data,
    )


@app.command()
def current(ctx: typer.Context) -> None:
    """Show current active profile."""
    actx: AppContext = ctx.obj
    out = actx.output
    default = get_default_profile()
    svc = get_service_config(default)

    if out.json_mode:
        out.raw_json({"profile": default, **svc.model_dump()})
        return

    out.kv("Profile", default)
    out.kv("Vault", svc.vault or "(not set)")
    out.kv("Token", _mask_token(svc.service_account_token))
    out.kv("Scan roots", str(len(svc.scan_roots)))
    for root in svc.scan_roots:
        out.kv("  ", root)


@app.command()
def show(ctx: typer.Context) -> None:
    """Show full configuration (tokens masked)."""
    actx: AppContext = ctx.obj
    out = actx.output
    default = get_default_profile()
    names = get_profile_names()

    if out.json_mode:
        data = load_raw_config()
        for _pname, pdata in data.get("profiles", {}).items():
            for _svc, svc_data in pdata.items():
                if isinstance(svc_data, dict) and "service_account_token" in svc_data:
                    svc_data["service_account_token"] = _mask_token(svc_data["service_account_token"])
        out.raw_json(data)
        return

    sections: list[tuple[str, list[tuple[str, str]]]] = []
    sections.append(
        (
            "General",
            [
                ("Config file", str(CONFIG_FILE)),
                ("Default profile", default),
                ("Total profiles", str(len(names))),
            ],
        )
    )

    for pname in names:
        marker = " [green](default)[/green]" if pname == default else ""
        services = get_all_services_in_profile(pname)
        kvs: list[tuple[str, str]] = []
        for svc_name, svc_data in services.items():
            if not isinstance(svc_data, dict):
                continue
            indicator = "[green]\u25cf[/green]" if svc_name == SERVICE_KEY else "[dim]\u25cb[/dim]"
            svc_vault = svc_data.get("vault", "")
            svc_token = _mask_token(svc_data.get("service_account_token", ""))
            roots_count = len(svc_data.get("scan_roots", []))
            kvs.append(
                (
                    f"{indicator} {svc_name}",
                    f"vault: {svc_vault}  token: {svc_token}  roots: {roots_count}",
                )
            )
        sections.append((f"Profile: {pname}{marker}", kvs))

    out.detail("Configuration", sections)


@app.command()
def test(ctx: typer.Context) -> None:
    """Test current profile's 1Password connection."""
    actx: AppContext = ctx.obj
    out = actx.output

    cfg = actx.service_config
    if not cfg.vault:
        out.error("No vault configured. Run: kctl-op config init")
        raise typer.Exit(code=1)

    out.info(f"Testing connection (vault: {cfg.vault})...")
    try:
        client = actx.client
        info = client.whoami()
        out.success(f"Authenticated as {info.get('email', info.get('url', 'unknown'))}")

        vault_data = client.vault_info()
        items = vault_data.get("items", 0)
        out.success(f"Vault '{cfg.vault}' accessible ({items} items)")
    except Exception as e:
        out.error(f"Connection failed: {e}")
        raise typer.Exit(code=1) from None


@app.command(name="set")
def set_cmd(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Config key (vault, service_account_token, scan_roots).")],
    value: Annotated[str, typer.Argument(help="Config value.")],
) -> None:
    """Set a configuration value in the current profile."""
    actx: AppContext = ctx.obj
    out = actx.output
    profile = actx.profile or get_default_profile()
    svc = get_service_config(profile)

    if key == "vault":
        svc.vault = value
    elif key == "service_account_token":
        svc.service_account_token = value
    elif key == "scan_roots":
        svc.scan_roots = [r.strip() for r in value.split(",")]
    else:
        out.error(f"Unknown key: {key}. Valid: vault, service_account_token, scan_roots")
        raise typer.Exit(code=1)

    set_service_config(profile, svc)
    out.success(f"Set {key} = {value} in profile '{profile}'.")


@app.command()
def migrate(ctx: typer.Context) -> None:
    """Migrate legacy configuration to service-scoped format."""
    actx: AppContext = ctx.obj
    out = actx.output

    data = load_raw_config()
    profiles = data.get("profiles", {})
    migrated = 0

    for _pname, pdata in profiles.items():
        if not isinstance(pdata, dict):
            continue
        # Check for flat (legacy) format: vault at top level instead of under SERVICE_KEY
        if "vault" in pdata and SERVICE_KEY not in pdata:
            pdata[SERVICE_KEY] = {
                "vault": pdata.pop("vault", ""),
                "service_account_token": pdata.pop("service_account_token", ""),
                "scan_roots": pdata.pop("scan_roots", []),
            }
            migrated += 1

    if migrated:
        save_raw_config(data)
        out.success(f"Migrated {migrated} profile(s) to service-scoped format.")
    else:
        out.info("No migration needed. All profiles already use service-scoped format.")
