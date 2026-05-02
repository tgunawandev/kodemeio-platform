"""Emergency hotfix deployment commands.

Uses Dokploy API to resolve compose → server IP + container names,
SSH + docker for file copy and module upgrade, and Odoo JSON-RPC
(via --odoo-profile) for hotfix tracking in ir.config_parameter.
"""

from __future__ import annotations

import getpass
import http.client
import json
import subprocess
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

MAX_ACTIVE_HOTFIXES = 3
HOTFIX_PARAM_PREFIX = "kodemeio.hotfix."
PRIVATE_BUCKETS = (
    "core",
    "applications",
    "extensions",
    "integrations",
    "reports",
    "themes",
)

console = Console()


# ---------------------------------------------------------------------------
# Dokploy API helpers
# ---------------------------------------------------------------------------


def _dokploy_config(profile: str) -> tuple[str, str]:
    import yaml

    config_path = Path.home() / ".config" / "kodemeio" / "config.yaml"
    if not config_path.exists():
        console.print(f"[red]Config not found: {config_path}[/red]")
        raise typer.Exit(1)
    cfg = yaml.safe_load(config_path.read_text())
    dokploy = cfg.get("profiles", {}).get(profile, {}).get("dokploy", {})
    url = dokploy.get("url", "")
    api_key = dokploy.get("api_key", "")
    if not url or not api_key:
        console.print(f"[red]No dokploy config in profile '{profile}'.[/red]")
        raise typer.Exit(1)
    return url.rstrip("/"), api_key


def _dokploy_get(base_url: str, api_key: str, path: str, query: str = "") -> dict:
    parsed = urllib.parse.urlparse(base_url)
    full_path = f"/api/{path}"
    if query:
        full_path += f"?{query}"
    if parsed.scheme == "https":
        conn = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=15)
    else:
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=15)
    try:
        conn.request("GET", full_path, headers={"x-api-key": api_key})
        resp = conn.getresponse()
        body = resp.read().decode()
        if resp.status != 200:
            console.print(f"[red]Dokploy API error: HTTP {resp.status}[/red]")
            raise typer.Exit(1)
        return json.loads(body)
    finally:
        conn.close()


def _resolve_compose(base_url: str, api_key: str, compose_id: str) -> tuple[str, str, str]:
    data = _dokploy_get(base_url, api_key, "compose.one", f"composeId={compose_id}")
    app_name = data.get("appName", "")
    compose_name = data.get("name", compose_id)
    server = data.get("server", {})
    ip = server.get("ipAddress", "")
    user = server.get("username", "root")
    if not ip:
        console.print("[red]Could not resolve server IP from Dokploy[/red]")
        raise typer.Exit(1)
    return f"{user}@{ip}", app_name, compose_name


# ---------------------------------------------------------------------------
# Odoo JSON-RPC client for tracking (lightweight, no kctl_common dependency)
# ---------------------------------------------------------------------------


def _odoo_client(profile: str):
    """Create an OdooClient from a kctl-odoo profile."""
    try:
        from kctl_odoo.core.client import OdooClient
        from kctl_odoo.core.config import resolve_connection

        url, database, username, api_key = resolve_connection(profile)
        return OdooClient(
            base_url=url,
            database=database,
            username=username,
            api_key=api_key,
        )
    except Exception as e:
        console.print(f"[yellow]Cannot connect to Odoo for tracking: {e}[/yellow]")
        return None


def _query_hotfix_records(client) -> list[dict]:
    """Query hotfix records via JSON-RPC."""
    try:
        return client.search_read(
            "ir.config_parameter",
            domain=[("key", "like", HOTFIX_PARAM_PREFIX)],
            fields=["key", "value"],
            limit=0,
        )
    except Exception:
        return []


def _set_hotfix_record(client, key: str, value: str) -> None:
    """Create or update a hotfix tracking record via JSON-RPC."""
    try:
        existing = client.search_read(
            "ir.config_parameter",
            domain=[("key", "=", key)],
            fields=["id"],
            limit=1,
        )
        if existing:
            client.write("ir.config_parameter", [existing[0]["id"]], {"value": value})
        else:
            client.create("ir.config_parameter", {"key": key, "value": value})
    except Exception as e:
        console.print(f"[yellow]Failed to record hotfix: {e}[/yellow]")


def _delete_hotfix_records(client) -> int:
    """Delete all hotfix tracking records via JSON-RPC."""
    try:
        records = client.search_read(
            "ir.config_parameter",
            domain=[("key", "like", HOTFIX_PARAM_PREFIX)],
            fields=["id"],
            limit=0,
        )
        ids = [r["id"] for r in records]
        if ids:
            client.unlink("ir.config_parameter", ids)
        return len(ids)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# SSH / Docker helpers
# ---------------------------------------------------------------------------


def _ssh_run(
    target_host: str, cmd: str, *, check: bool = True, capture: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=accept-new", target_host, cmd],
        capture_output=capture,
        text=True,
        check=check,
    )


def _docker_cp(ssh_host: str, local_path: Path, container: str, remote_path: str) -> subprocess.CompletedProcess[str]:
    module_name = local_path.name
    tar_cmd = f"tar -C {local_path.parent} -cf - {module_name}"
    remote_cmd = (
        f"cat > /tmp/{module_name}.tar"
        f" && tar -C /tmp -xf /tmp/{module_name}.tar"
        f" && docker cp /tmp/{module_name} {container}:{remote_path}"
        f" && rm -rf /tmp/{module_name} /tmp/{module_name}.tar"
    )
    full_cmd = f"{tar_cmd} | ssh -o StrictHostKeyChecking=accept-new {ssh_host} '{remote_cmd}'"
    return subprocess.run(full_cmd, shell=True, text=True, check=True)


def _find_module_path(module: str, project_dir: Path | None) -> tuple[Path, str]:
    base = project_dir or Path.cwd()
    for bucket in PRIVATE_BUCKETS:
        candidate = base / "src" / "private" / bucket / module
        if candidate.is_dir() and (candidate / "__manifest__.py").exists():
            return candidate, bucket
    console.print(f"[red]Module '{module}' not found in src/private/[/red]")
    raise typer.Exit(1)


def _production_gate(target: str, confirmed: bool) -> None:
    safe_keywords = ("staging", "stg", "dev", "test", "local")
    if any(kw in target for kw in safe_keywords):
        return
    if not confirmed:
        console.print(f"[red]Target '{target}' looks like production.[/red]\nPass --i-know-what-im-doing to confirm.")
        raise typer.Exit(1)


def _get_git_sha(module_path: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%h", "--", str(module_path)],
            capture_output=True,
            text=True,
            check=True,
            cwd=module_path.parent,
        )
        return result.stdout.strip() or "unknown"
    except subprocess.CalledProcessError:
        return "unknown"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def hotfix(
    compose_id: Annotated[str, typer.Argument(help="Dokploy compose ID")],
    module: Annotated[str, typer.Option("--module", "-m", help="Module name to hotfix")],
    dokploy_profile: Annotated[
        str, typer.Option("--dokploy-profile", "-dp", help="Dokploy config profile (required)")
    ] = ...,
    odoo_profile: Annotated[
        str | None, typer.Option("--odoo-profile", "-op", help="Odoo config profile for tracking (optional)")
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Skip hotfix count / duplicate checks")] = False,
    i_know_what_im_doing: Annotated[
        bool, typer.Option("--i-know-what-im-doing", help="Confirm production deployment")
    ] = False,
    project_dir: Annotated[Path | None, typer.Option("--project-dir", "-C", help="Project root directory")] = None,
) -> None:
    """Deploy an emergency hotfix to a running container.

    Copies a private module into the target container, runs odoo -u,
    and restarts services. Optionally tracks the hotfix via --odoo-profile.

    Examples:
      kctl-odoo deploy hotfix h1I7b35s8w9UVOhbqLNgT -m stock_management -dp idtpp
      kctl-odoo deploy hotfix h1I7b35s8w9UVOhbqLNgT -m stock_management -dp idtpp -op idtpp-mac-odoo-hrms-stg
    """
    dok_url, dok_key = _dokploy_config(dokploy_profile)
    ssh_host, app_name, compose_name = _resolve_compose(dok_url, dok_key, compose_id)
    _production_gate(compose_name, i_know_what_im_doing)

    web_container = f"{app_name}-odoo-web-1"
    cron_container = f"{app_name}-odoo-cron-1"

    console.print(f"[bold]Hotfix: {module} → {compose_name}[/bold]")
    console.print(f"  Server: {ssh_host}")
    console.print(f"  Container: {web_container}")

    module_path, bucket = _find_module_path(module, project_dir)
    console.print(f"  Module: src/private/{bucket}/{module}")

    # Check existing hotfixes via Odoo API (if profile provided)
    client = _odoo_client(odoo_profile) if odoo_profile else None
    if client and not force:
        existing = _query_hotfix_records(client)
        if len(existing) >= MAX_ACTIVE_HOTFIXES:
            console.print(f"[red]Max {MAX_ACTIVE_HOTFIXES} hotfixes reached. Use --force.[/red]")
            raise typer.Exit(1)
        for rec in existing:
            try:
                val = json.loads(rec.get("value", "{}"))
                if val.get("module") == module:
                    console.print(f"[red]Module '{module}' already hotfixed. Use --force.[/red]")
                    raise typer.Exit(1)
            except (json.JSONDecodeError, ValueError):
                continue

    # Step 1: Copy module
    remote_path = f"/opt/odoo/src/private/{bucket}/"
    console.print(f"\n[cyan]Step 1/4:[/cyan] Copying {module} to container...")
    _docker_cp(ssh_host, module_path, web_container, remote_path)
    cron_check = _ssh_run(ssh_host, f"docker ps -q -f name={cron_container}", check=False)
    if cron_check.stdout.strip():
        _docker_cp(ssh_host, module_path, cron_container, remote_path)

    # Step 2: Module upgrade
    console.print(f"[cyan]Step 2/4:[/cyan] Running odoo -u {module}...")
    upgrade_result = _ssh_run(
        ssh_host,
        f'docker exec {web_container} sh -c "odoo -u {module} -d \\$PGDATABASE --stop-after-init --no-http -c /etc/odoo/odoo.conf"',
        check=False,
    )
    if upgrade_result.returncode != 0:
        console.print(f"[red]Module upgrade failed:[/red]\n{upgrade_result.stderr[-500:]}")
        raise typer.Exit(1)
    console.print(f"  Module {module} upgraded")

    # Step 3: Restart
    console.print("[cyan]Step 3/4:[/cyan] Restarting containers...")
    _ssh_run(ssh_host, f"docker restart {web_container}", check=False)
    if cron_check.stdout.strip():
        _ssh_run(ssh_host, f"docker restart {cron_container}", check=False)
    console.print("  Containers restarted")

    # Step 4: Track hotfix
    console.print("[cyan]Step 4/4:[/cyan] Recording hotfix...")
    now = datetime.now(UTC)
    record = json.dumps(
        {
            "module": module,
            "bucket": bucket,
            "git_sha": _get_git_sha(module_path),
            "operator": getpass.getuser(),
            "timestamp": now.isoformat(),
            "target": compose_name,
        }
    )
    param_key = f"{HOTFIX_PARAM_PREFIX}{module}.{now.strftime('%Y%m%d%H%M%S')}"

    if client:
        _set_hotfix_record(client, param_key, record)
        console.print(f"  Tracked: {param_key}")
    else:
        console.print("  [yellow]No --odoo-profile — hotfix not tracked[/yellow]")

    console.print()
    console.print("[bold green]Hotfix applied![/bold green]")
    console.print("[bold yellow]WARNING: Container is DIRTY. Push + rebuild within 24h.[/bold yellow]")


def hotfix_status(
    compose_id: Annotated[str, typer.Argument(help="Dokploy compose ID")],
    dokploy_profile: Annotated[
        str, typer.Option("--dokploy-profile", "-dp", help="Dokploy config profile (required)")
    ] = ...,
    odoo_profile: Annotated[str, typer.Option("--odoo-profile", "-op", help="Odoo config profile (required)")] = ...,
) -> None:
    """Show active hotfixes on a target.

    Examples:
      kctl-odoo deploy hotfix-status h1I7b35s8w9UVOhbqLNgT -dp idtpp -op idtpp-mac-odoo-hrms-stg
    """
    dok_url, dok_key = _dokploy_config(dokploy_profile)
    _ssh_host, _app_name, compose_name = _resolve_compose(dok_url, dok_key, compose_id)

    client = _odoo_client(odoo_profile)
    if not client:
        console.print("[red]Cannot connect to Odoo — check --odoo-profile[/red]")
        raise typer.Exit(1)

    records = _query_hotfix_records(client)
    if not records:
        console.print(f"[green]No active hotfixes on {compose_name}.[/green]")
        return

    table = Table(title=f"Active Hotfixes on {compose_name}")
    table.add_column("Module", style="cyan")
    table.add_column("Git SHA", style="dim")
    table.add_column("Operator")
    table.add_column("Applied", style="cyan")
    table.add_column("Age")

    now = datetime.now(UTC)
    for rec in records:
        try:
            val = json.loads(rec.get("value", "{}"))
        except (json.JSONDecodeError, ValueError):
            continue
        ts_str = val.get("timestamp", "")
        try:
            applied = datetime.fromisoformat(ts_str)
            age_hours = (now - applied).total_seconds() / 3600
            age_display = f"[bold red]{age_hours:.1f}h OVERDUE[/bold red]" if age_hours > 24 else f"{age_hours:.1f}h"
            applied_display = applied.strftime("%Y-%m-%d %H:%M UTC")
        except (ValueError, TypeError):
            applied_display = ts_str or "?"
            age_display = "?"
        table.add_row(
            val.get("module", "?"), val.get("git_sha", "?"), val.get("operator", "?"), applied_display, age_display
        )

    console.print(table)
    console.print(f"\n[dim]Max: {MAX_ACTIVE_HOTFIXES} | Active: {len(records)}[/dim]")


def hotfix_rollback(
    compose_id: Annotated[str, typer.Argument(help="Dokploy compose ID")],
    dokploy_profile: Annotated[
        str, typer.Option("--dokploy-profile", "-dp", help="Dokploy config profile (required)")
    ] = ...,
    odoo_profile: Annotated[
        str | None, typer.Option("--odoo-profile", "-op", help="Odoo config profile (optional)")
    ] = None,
    i_know_what_im_doing: Annotated[
        bool, typer.Option("--i-know-what-im-doing", help="Confirm production rollback")
    ] = False,
) -> None:
    """Roll back all hotfixes by recreating containers from the clean image.

    Examples:
      kctl-odoo deploy hotfix-rollback h1I7b35s8w9UVOhbqLNgT -dp idtpp -op idtpp-mac-odoo-hrms-stg
    """
    dok_url, dok_key = _dokploy_config(dokploy_profile)
    ssh_host, app_name, compose_name = _resolve_compose(dok_url, dok_key, compose_id)
    _production_gate(compose_name, i_know_what_im_doing)

    # Clear tracking records if Odoo is accessible
    if odoo_profile:
        client = _odoo_client(odoo_profile)
        if client:
            deleted = _delete_hotfix_records(client)
            console.print(f"  Cleared {deleted} hotfix record(s)")

    # Force-recreate containers via Dokploy API redeploy
    console.print(f"[cyan]Recreating containers for {compose_name}...[/cyan]")
    parsed = urllib.parse.urlparse(dok_url)
    if parsed.scheme == "https":
        conn = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=30)
    else:
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=30)
    try:
        conn.request(
            "POST",
            "/api/compose.redeploy",
            json.dumps({"composeId": compose_id}),
            headers={"x-api-key": dok_key, "Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        if resp.status == 200:
            console.print(f"[bold green]Rollback triggered on {compose_name}.[/bold green]")
        else:
            console.print(f"[red]Redeploy failed: HTTP {resp.status}[/red]")
    finally:
        conn.close()
