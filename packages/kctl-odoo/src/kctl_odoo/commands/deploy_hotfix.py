"""Emergency hotfix deployment commands.

Provides hotfix, hotfix-status, and hotfix-rollback commands for
deploying module patches directly to running containers via SSH.

Uses Dokploy API to resolve compose → server IP + container names,
then SSH + docker for the actual file copy and module upgrade.
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
# Dokploy API helpers (same http.client pattern as deploy_upgrade)
# ---------------------------------------------------------------------------


def _dokploy_config(profile: str) -> tuple[str, str]:
    """Read Dokploy URL and API key from shared config."""
    import yaml

    config_path = Path.home() / ".config" / "kodemeio" / "config.yaml"
    if not config_path.exists():
        console.print(f"[red]Config not found: {config_path}[/red]")
        raise typer.Exit(1)

    cfg = yaml.safe_load(config_path.read_text())
    prof = cfg.get("profiles", {}).get(profile, {})
    dokploy = prof.get("dokploy", {})
    url = dokploy.get("url", "")
    api_key = dokploy.get("api_key", "")

    if not url or not api_key:
        console.print(f"[red]No dokploy config in profile '{profile}'.[/red]")
        raise typer.Exit(1)

    return url.rstrip("/"), api_key


def _dokploy_get(base_url: str, api_key: str, path: str, query: str = "") -> dict:
    """GET request to Dokploy API using http.client (preserves header case)."""
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
            console.print(f"[red]Dokploy API error: HTTP {resp.status} — {body[:200]}[/red]")
            raise typer.Exit(1)
        return json.loads(body)
    finally:
        conn.close()


def _resolve_compose(base_url: str, api_key: str, compose_id: str) -> tuple[str, str, str]:
    """Resolve a compose ID to (ssh_host, appName, server_ip).

    Returns (server_user@server_ip, appName, compose_name).
    """
    data = _dokploy_get(base_url, api_key, "compose.one", f"composeId={compose_id}")
    app_name = data.get("appName", "")
    compose_name = data.get("name", compose_id)
    server = data.get("server", {})
    ip = server.get("ipAddress", "")
    user = server.get("username", "root")

    if not ip:
        console.print("[red]Could not resolve server IP from Dokploy[/red]")
        raise typer.Exit(1)

    ssh_host = f"{user}@{ip}"
    return ssh_host, app_name, compose_name


# ---------------------------------------------------------------------------
# SSH / Docker helpers
# ---------------------------------------------------------------------------


def _ssh_run(
    target_host: str,
    cmd: str,
    *,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a command on a remote host via SSH."""
    return subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=accept-new", target_host, cmd],
        capture_output=capture,
        text=True,
        check=check,
    )


def _docker_cp(
    ssh_host: str,
    local_path: Path,
    container: str,
    remote_path: str,
) -> subprocess.CompletedProcess[str]:
    """Copy a local directory into a remote Docker container via tar + SSH."""
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
    """Locate a private module and return (path, bucket)."""
    base = project_dir or Path.cwd()
    for bucket in PRIVATE_BUCKETS:
        candidate = base / "src" / "private" / bucket / module
        if candidate.is_dir() and (candidate / "__manifest__.py").exists():
            return candidate, bucket
    msg = f"Module '{module}' not found in any private bucket ({', '.join(PRIVATE_BUCKETS)})"
    console.print(f"[red]{msg}[/red]")
    raise typer.Exit(1)


def _production_gate(target: str, confirmed: bool) -> None:
    """Block production targets unless explicitly confirmed."""
    safe_keywords = ("staging", "stg", "dev", "test", "local")
    if any(kw in target for kw in safe_keywords):
        return
    if not confirmed:
        console.print(
            f"[red]Target '{target}' looks like production.[/red]\nPass --i-know-what-im-doing to confirm.",
        )
        raise typer.Exit(1)


def _get_git_sha(module_path: Path) -> str:
    """Get current git SHA for the module directory."""
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


def _query_hotfix_params(ssh_host: str, container: str) -> list[dict]:
    """Query all kodemeio.hotfix.* ir.config_parameter records."""
    script = (
        "import os, xmlrpc.client as x, json; "
        "db = os.environ.get('PGDATABASE', 'odoo'); "
        "pwd = os.environ.get('ODOO_ADMIN_PASSWD', 'admin'); "
        "url = 'http://localhost:8069'; "
        "common = x.ServerProxy(f'{url}/xmlrpc/2/common'); "
        "uid = common.authenticate(db, 'admin', pwd, {}); "
        "models = x.ServerProxy(f'{url}/xmlrpc/2/object'); "
        "ids = models.execute_kw(db, uid, pwd, 'ir.config_parameter', 'search', "
        "[[['key', 'like', 'kodemeio.hotfix.']]]); "
        "recs = models.execute_kw(db, uid, pwd, 'ir.config_parameter', 'read', "
        "[ids], {'fields': ['key', 'value']}); "
        "print(json.dumps(recs))"
    )
    result = _ssh_run(ssh_host, f'docker exec {container} python3 -c "{script}"', check=False)
    if result.returncode != 0:
        return []
    try:
        return json.loads(result.stdout.strip())
    except (json.JSONDecodeError, ValueError):
        return []


def _set_hotfix_param(ssh_host: str, container: str, key: str, value: str) -> None:
    """Set an ir.config_parameter via XML-RPC inside the container."""
    escaped_value = value.replace("'", "\\'").replace('"', '\\"')
    script = (
        "import os, xmlrpc.client as x; "
        "db = os.environ.get('PGDATABASE', 'odoo'); "
        "pwd = os.environ.get('ODOO_ADMIN_PASSWD', 'admin'); "
        "url = 'http://localhost:8069'; "
        "common = x.ServerProxy(f'{url}/xmlrpc/2/common'); "
        "uid = common.authenticate(db, 'admin', pwd, {}); "
        "models = x.ServerProxy(f'{url}/xmlrpc/2/object'); "
        f"models.execute_kw(db, uid, pwd, 'ir.config_parameter', 'set_param', "
        f"['{key}', '{escaped_value}'])"
    )
    _ssh_run(ssh_host, f'docker exec {container} python3 -c "{script}"', check=False)


def _delete_hotfix_params(ssh_host: str, container: str) -> int:
    """Delete all kodemeio.hotfix.* params. Returns count deleted."""
    script = (
        "import os, xmlrpc.client as x; "
        "db = os.environ.get('PGDATABASE', 'odoo'); "
        "pwd = os.environ.get('ODOO_ADMIN_PASSWD', 'admin'); "
        "url = 'http://localhost:8069'; "
        "common = x.ServerProxy(f'{url}/xmlrpc/2/common'); "
        "uid = common.authenticate(db, 'admin', pwd, {}); "
        "models = x.ServerProxy(f'{url}/xmlrpc/2/object'); "
        "ids = models.execute_kw(db, uid, pwd, 'ir.config_parameter', 'search', "
        "[[['key', 'like', 'kodemeio.hotfix.']]]); "
        "print(len(ids)); "
        "models.execute_kw(db, uid, pwd, 'ir.config_parameter', 'unlink', [ids]) "
        "if ids else None"
    )
    result = _ssh_run(ssh_host, f'docker exec {container} python3 -c "{script}"', check=False)
    try:
        return int(result.stdout.strip())
    except (ValueError, AttributeError):
        return 0


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def hotfix(
    compose_id: Annotated[str, typer.Argument(help="Dokploy compose ID")],
    module: Annotated[str, typer.Option("--module", "-m", help="Module name to hotfix")],
    dokploy_profile: Annotated[
        str, typer.Option("--dokploy-profile", "-dp", help="Dokploy config profile (required)")
    ] = ...,
    force: Annotated[bool, typer.Option("--force", help="Skip hotfix count / duplicate checks")] = False,
    i_know_what_im_doing: Annotated[
        bool,
        typer.Option("--i-know-what-im-doing", help="Confirm production deployment"),
    ] = False,
    project_dir: Annotated[
        Path | None,
        typer.Option("--project-dir", "-C", help="Project root directory"),
    ] = None,
) -> None:
    """Deploy an emergency hotfix to a running container.

    Copies a private module into the target container, runs odoo -u,
    and restarts the web + cron services. Records the hotfix as an
    ir.config_parameter for tracking.

    Examples:
      kctl-odoo deploy hotfix h1I7b35s8w9UVOhbqLNgT -m stock_management -dp idtpp
      kctl-odoo deploy hotfix h1I7b35s8w9UVOhbqLNgT -m account_management -dp idtpp --i-know-what-im-doing
    """
    # Resolve via Dokploy API
    dok_url, dok_key = _dokploy_config(dokploy_profile)
    ssh_host, app_name, compose_name = _resolve_compose(dok_url, dok_key, compose_id)

    _production_gate(compose_name, i_know_what_im_doing)

    web_container = f"{app_name}-odoo-web-1"
    cron_container = f"{app_name}-odoo-cron-1"

    console.print(f"[bold]Hotfix: {module} → {compose_name}[/bold]")
    console.print(f"  Server: {ssh_host}")
    console.print(f"  Web container: {web_container}")

    # Locate module
    module_path, bucket = _find_module_path(module, project_dir)
    console.print(f"  Module: src/private/{bucket}/{module}")

    # Check active hotfixes
    existing = _query_hotfix_params(ssh_host, web_container)
    if not force:
        if len(existing) >= MAX_ACTIVE_HOTFIXES:
            console.print(
                f"[red]Too many active hotfixes ({len(existing)}/{MAX_ACTIVE_HOTFIXES}).[/red]\n"
                "Use --force to override or run hotfix-rollback first.",
            )
            raise typer.Exit(1)

        for rec in existing:
            try:
                val = json.loads(rec.get("value", "{}"))
            except (json.JSONDecodeError, ValueError):
                continue
            if val.get("module") == module:
                console.print(
                    f"[red]Module '{module}' already has an active hotfix.[/red]\nUse --force to override.",
                )
                raise typer.Exit(1)

    # Copy module into web container
    remote_path = f"/opt/odoo/src/private/{bucket}/"
    console.print(f"\n[cyan]Step 1/4:[/cyan] Copying {module} to container...")
    _docker_cp(ssh_host, module_path, web_container, remote_path)

    # Also copy into cron container if it exists
    cron_check = _ssh_run(ssh_host, f"docker ps -q -f name={cron_container}", check=False)
    if cron_check.stdout.strip():
        _docker_cp(ssh_host, module_path, cron_container, remote_path)

    # Run module upgrade inside web container
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

    # Restart containers
    console.print("[cyan]Step 3/4:[/cyan] Restarting containers...")
    _ssh_run(ssh_host, f"docker restart {web_container}", check=False)
    if cron_check.stdout.strip():
        _ssh_run(ssh_host, f"docker restart {cron_container}", check=False)
    console.print("  Containers restarted")

    # Log hotfix record
    console.print("[cyan]Step 4/4:[/cyan] Recording hotfix...")
    now = datetime.now(UTC)
    git_sha = _get_git_sha(module_path)
    operator = getpass.getuser()
    timestamp = now.strftime("%Y%m%d%H%M%S")
    param_key = f"{HOTFIX_PARAM_PREFIX}{module}.{timestamp}"
    param_value = json.dumps(
        {
            "module": module,
            "bucket": bucket,
            "git_sha": git_sha,
            "operator": operator,
            "timestamp": now.isoformat(),
            "target": compose_name,
        }
    )
    _set_hotfix_param(ssh_host, web_container, param_key, param_value)
    console.print(f"  Recorded: {param_key}")

    console.print()
    console.print("[bold green]Hotfix applied![/bold green]")
    console.print("[bold yellow]WARNING: Container is DIRTY. Push + rebuild within 24h.[/bold yellow]")


def hotfix_status(
    compose_id: Annotated[str, typer.Argument(help="Dokploy compose ID")],
    dokploy_profile: Annotated[
        str, typer.Option("--dokploy-profile", "-dp", help="Dokploy config profile (required)")
    ] = ...,
) -> None:
    """Show active hotfixes on a deployment target.

    Examples:
      kctl-odoo deploy hotfix-status h1I7b35s8w9UVOhbqLNgT -dp idtpp
    """
    dok_url, dok_key = _dokploy_config(dokploy_profile)
    ssh_host, app_name, compose_name = _resolve_compose(dok_url, dok_key, compose_id)
    web_container = f"{app_name}-odoo-web-1"

    records = _query_hotfix_params(ssh_host, web_container)

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
    i_know_what_im_doing: Annotated[
        bool,
        typer.Option("--i-know-what-im-doing", help="Confirm production rollback"),
    ] = False,
) -> None:
    """Roll back all hotfixes by recreating containers from the clean image.

    Examples:
      kctl-odoo deploy hotfix-rollback h1I7b35s8w9UVOhbqLNgT -dp idtpp
    """
    dok_url, dok_key = _dokploy_config(dokploy_profile)
    ssh_host, app_name, compose_name = _resolve_compose(dok_url, dok_key, compose_id)

    _production_gate(compose_name, i_know_what_im_doing)

    web_container = f"{app_name}-odoo-web-1"

    records = _query_hotfix_params(ssh_host, web_container)
    if not records:
        console.print(f"[green]No active hotfixes on {compose_name}.[/green]")
        return

    console.print(f"[yellow]Rolling back {len(records)} hotfix(es) on {compose_name}...[/yellow]")

    deleted = _delete_hotfix_params(ssh_host, web_container)
    console.print(f"  Cleared {deleted} hotfix record(s)")

    console.print("  Recreating containers from clean image...")
    _ssh_run(
        ssh_host,
        f"cd /opt/dokploy && docker compose -p {app_name} up -d --force-recreate odoo-web odoo-cron",
        check=False,
    )
    console.print(f"[bold green]Rollback complete on {compose_name}.[/bold green]")
