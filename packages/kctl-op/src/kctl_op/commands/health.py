"""Health check and dashboard commands."""

from __future__ import annotations

import shutil

import typer

from kctl_op.core.callbacks import AppContext

app = typer.Typer(help="Health checks and diagnostics.")


@app.callback(invoke_without_command=True)
def health(ctx: typer.Context) -> None:
    """Check: op CLI installed, authenticated, vault accessible."""
    if ctx.invoked_subcommand is not None:
        return

    actx: AppContext = ctx.obj
    out = actx.output
    cfg = actx.service_config
    all_ok = True
    checks: list[dict] = []

    # Check 1: op CLI installed
    op_path = shutil.which("op")
    if op_path:
        out.success(f"1Password CLI found: {op_path}")
        checks.append({"check": "op_cli", "status": "ok", "detail": op_path})
    else:
        out.error("1Password CLI (op) not found in PATH")
        checks.append({"check": "op_cli", "status": "fail", "detail": "not found"})
        all_ok = False

    # Check 2: op CLI version
    if op_path:
        client = actx.client
        version = client.get_version()
        out.success(f"op CLI version: {version}")
        checks.append({"check": "op_version", "status": "ok", "detail": version})

    # Check 3: Authentication
    if op_path:
        try:
            info = client.whoami()
            email = info.get("email", info.get("url", "unknown"))
            out.success(f"Authenticated: {email}")
            checks.append({"check": "auth", "status": "ok", "detail": email})
        except Exception as e:
            out.error(f"Not authenticated: {e}")
            checks.append({"check": "auth", "status": "fail", "detail": str(e)})
            all_ok = False

    # Check 4: Vault access
    if op_path and cfg.vault:
        try:
            vault_data = client.vault_info()
            item_count = vault_data.get("items", 0)
            out.success(f"Vault '{cfg.vault}' accessible ({item_count} items)")
            checks.append(
                {
                    "check": "vault",
                    "status": "ok",
                    "detail": f"{cfg.vault} ({item_count} items)",
                }
            )
        except Exception as e:
            out.error(f"Vault '{cfg.vault}' not accessible: {e}")
            checks.append({"check": "vault", "status": "fail", "detail": str(e)})
            all_ok = False
    elif not cfg.vault:
        out.warn("No vault configured. Run: kctl-op config init")
        checks.append({"check": "vault", "status": "skip", "detail": "not configured"})

    # Check 5: Scan roots
    from pathlib import Path

    for root in cfg.scan_roots:
        p = Path(root).expanduser()
        if p.exists():
            out.success(f"Scan root exists: {root}")
            checks.append({"check": f"scan_root:{root}", "status": "ok"})
        else:
            out.warn(f"Scan root missing: {root}")
            checks.append({"check": f"scan_root:{root}", "status": "warn", "detail": "missing"})

    if out.json_mode:
        out.raw_json({"healthy": all_ok, "checks": checks})

    if not all_ok:
        raise typer.Exit(code=1)


@app.command()
def dashboard(ctx: typer.Context) -> None:
    """Overview: projects, files, sync status, last sync times."""
    actx: AppContext = ctx.obj
    out = actx.output
    cfg = actx.service_config
    client = actx.client

    out.header("1Password Dashboard")

    # Connection info
    try:
        info = client.whoami()
        email = info.get("email", info.get("url", "unknown"))
        out.kv("Account", email)
    except Exception:
        out.kv("Account", "[red]not connected[/red]")

    out.kv("Vault", cfg.vault or "(not set)")
    out.kv("Profile", actx.profile or "(default)")

    # Discover files
    files = client.discover_files(
        cfg.scan_roots,
        cfg.exclude_patterns,
        cfg.env_mappings,
        cfg.custom_env_pattern,
    )
    out.kv("Total .env files", str(len(files)))

    # Group by project
    projects: dict[str, list] = {}
    for f in files:
        projects.setdefault(f.project, []).append(f)
    out.kv("Projects", str(len(projects)))

    # Sync status summary
    synced = 0
    out_of_sync = 0
    remote_only = 0

    out.header("Sync Status")
    for project_name in sorted(projects.keys()):
        project_files = projects[project_name]
        statuses = []
        for env_file in project_files:
            try:
                status = client.file_status(env_file)
                if status.get("in_sync"):
                    synced += 1
                    statuses.append(f"  [green]\u2713[/green] {env_file.environment}")
                elif status.get("remote_exists") and not status.get("local_exists"):
                    remote_only += 1
                    statuses.append(f"  [yellow]\u2193[/yellow] {env_file.environment} (remote only)")
                else:
                    out_of_sync += 1
                    statuses.append(f"  [red]\u2717[/red] {env_file.environment}")
            except Exception:
                out_of_sync += 1
                statuses.append(f"  [dim]?[/dim] {env_file.environment}")

        out.text(f"[bold]{project_name}[/bold]")
        for s in statuses:
            out.text(s)

    out.header("Summary")
    out.kv("In sync", f"[green]{synced}[/green]")
    out.kv("Out of sync", f"[red]{out_of_sync}[/red]" if out_of_sync else "0")
    out.kv("Remote only", f"[yellow]{remote_only}[/yellow]" if remote_only else "0")

    if out.json_mode:
        out.raw_json(
            {
                "vault": cfg.vault,
                "total_files": len(files),
                "total_projects": len(projects),
                "synced": synced,
                "out_of_sync": out_of_sync,
                "remote_only": remote_only,
            }
        )
