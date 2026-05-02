"""Emergency hotfix deployment commands.

Provides hotfix, hotfix-status, and hotfix-rollback commands for
deploying module patches directly to running containers via SSH.

These commands operate at the infrastructure level (SSH + Docker),
not via JSON-RPC, so they work independently of kctl_common.
"""

from __future__ import annotations

import getpass
import json
import subprocess
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
# Helpers
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
    target_host: str,
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
    full_cmd = f"{tar_cmd} | ssh -o StrictHostKeyChecking=accept-new {target_host} '{remote_cmd}'"
    return subprocess.run(full_cmd, shell=True, text=True, check=True)


def _resolve_target(target: str) -> tuple[str, str, str]:
    """Resolve a deploy target to SSH host and container names.

    Returns (ssh_host, init_container, web_container).
    """
    ssh_host = target.split("-")[0]
    return (
        ssh_host,
        f"{target}-odoo-init-1",
        f"{target}-odoo-web-1",
    )


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
    safe_keywords = ("staging", "dev", "test", "local")
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


def _query_hotfix_params(
    ssh_host: str,
    container: str,
) -> list[dict]:
    """Query all kodemeio.hotfix.* ir.config_parameter records via XML-RPC."""
    python_script = (
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
    result = _ssh_run(
        ssh_host,
        f'docker exec {container} python3 -c "{python_script}"',
        check=True,
    )
    try:
        return json.loads(result.stdout.strip())
    except (json.JSONDecodeError, ValueError):
        return []


def _set_hotfix_param(
    ssh_host: str,
    container: str,
    key: str,
    value: str,
) -> None:
    """Set an ir.config_parameter via XML-RPC inside the container."""
    escaped_value = value.replace("'", "\\'")
    python_script = (
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
    _ssh_run(
        ssh_host,
        f'docker exec {container} python3 -c "{python_script}"',
        check=True,
    )


def _delete_hotfix_params(ssh_host: str, container: str) -> int:
    """Delete all kodemeio.hotfix.* ir.config_parameter records. Returns count."""
    python_script = (
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
    result = _ssh_run(ssh_host, f'docker exec {container} python3 -c "{python_script}"')
    try:
        return int(result.stdout.strip())
    except (ValueError, AttributeError):
        return 0


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def hotfix(
    module: Annotated[str, typer.Option("--module", "-m", help="Module name to hotfix")],
    target: Annotated[str, typer.Option("--target", "-t", help="Deploy target (e.g. mac-odoo-erp)")],
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
      kctl-odoo deploy hotfix --module stock_management --target mac-odoo-erp-staging
      kctl-odoo deploy hotfix -m account_management -t mac-odoo-erp --i-know-what-im-doing
    """
    _production_gate(target, i_know_what_im_doing)

    # Locate module
    module_path, bucket = _find_module_path(module, project_dir)
    console.print(f"[green]Found module:[/green] {module_path} (bucket: {bucket})")

    # Resolve target
    ssh_host, init_container, web_container = _resolve_target(target)
    cron_container = f"{target}-odoo-cron-1"

    # Check active hotfixes
    existing = _query_hotfix_params(ssh_host, web_container)
    if not force:
        if len(existing) >= MAX_ACTIVE_HOTFIXES:
            console.print(
                f"[red]Too many active hotfixes ({len(existing)}/{MAX_ACTIVE_HOTFIXES}).[/red]\n"
                "Use --force to override or run hotfix-rollback first.",
            )
            raise typer.Exit(1)

        # Check for duplicate
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

    # Copy module into containers
    console.print(f"[cyan]Copying {module} to {web_container}...[/cyan]")
    addons_path = "/opt/odoo/auto/addons"
    _docker_cp(ssh_host, module_path, web_container, addons_path)
    console.print(f"[cyan]Copying {module} to {cron_container}...[/cyan]")
    _docker_cp(ssh_host, module_path, cron_container, addons_path)

    # Run module upgrade
    console.print(f"[cyan]Running odoo -u {module} inside {init_container}...[/cyan]")
    upgrade_cmd = (
        f"docker compose run --rm --no-deps -e ODOO_RUN_UPDATE=false"
        f" --entrypoint odoo {init_container.replace(f'{target}-', '').rsplit('-1', 1)[0]}"
        f" -u {module} --stop-after-init"
    )
    # Use the web container to run upgrade (it has the patched code)
    upgrade_cmd_direct = f"docker exec {web_container} odoo -u {module} -d ${{PGDATABASE:-odoo}} --stop-after-init"
    _ssh_run(ssh_host, upgrade_cmd_direct)
    console.print(f"[green]Module {module} upgraded successfully.[/green]")

    # Restart containers
    console.print("[cyan]Restarting web + cron containers...[/cyan]")
    _ssh_run(ssh_host, f"docker restart {web_container} {cron_container}")
    console.print("[green]Containers restarted.[/green]")

    # Log hotfix record
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
            "target": target,
        },
    )
    _set_hotfix_param(ssh_host, web_container, param_key, param_value)
    console.print(f"[green]Hotfix recorded:[/green] {param_key}")

    # Warning
    console.print()
    console.print(
        "[bold yellow]WARNING: Container image is now dirty.[/bold yellow]\n"
        "This hotfix MUST be merged into the codebase and redeployed\n"
        "from a clean image within 24 hours. Use 'deploy hotfix-status'\n"
        "to track active hotfixes.",
    )


def hotfix_status(
    target: Annotated[str, typer.Option("--target", "-t", help="Deploy target (e.g. mac-odoo-erp)")],
) -> None:
    """Show active hotfixes on a deployment target.

    Queries ir.config_parameter records with the kodemeio.hotfix.* prefix
    and displays them in a table with age tracking.

    Examples:
      kctl-odoo deploy hotfix-status --target mac-odoo-erp
    """
    ssh_host, _init_container, web_container = _resolve_target(target)
    records = _query_hotfix_params(ssh_host, web_container)

    if not records:
        console.print(f"[green]No active hotfixes on {target}.[/green]")
        return

    table = Table(title=f"Active Hotfixes on {target}")
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

        module_name = val.get("module", "?")
        git_sha = val.get("git_sha", "?")
        operator = val.get("operator", "?")
        ts_str = val.get("timestamp", "")

        try:
            applied = datetime.fromisoformat(ts_str)
            age = now - applied
            age_hours = age.total_seconds() / 3600
            if age_hours > 24:
                age_display = f"[bold red]{age_hours:.1f}h (OVERDUE)[/bold red]"
            else:
                age_display = f"{age_hours:.1f}h"
            applied_display = applied.strftime("%Y-%m-%d %H:%M UTC")
        except (ValueError, TypeError):
            applied_display = ts_str or "?"
            age_display = "?"

        table.add_row(module_name, git_sha, operator, applied_display, age_display)

    console.print(table)
    console.print(
        f"\n[dim]Max active hotfixes: {MAX_ACTIVE_HOTFIXES} | Current: {len(records)}[/dim]",
    )


def hotfix_rollback(
    target: Annotated[str, typer.Option("--target", "-t", help="Deploy target (e.g. mac-odoo-erp)")],
    i_know_what_im_doing: Annotated[
        bool,
        typer.Option("--i-know-what-im-doing", help="Confirm production rollback"),
    ] = False,
) -> None:
    """Roll back all hotfixes by recreating containers from the clean image.

    Clears all kodemeio.hotfix.* ir.config_parameter records and
    force-recreates odoo-web and odoo-cron containers from the
    original Docker image.

    Examples:
      kctl-odoo deploy hotfix-rollback --target mac-odoo-erp-staging
      kctl-odoo deploy hotfix-rollback --target mac-odoo-erp --i-know-what-im-doing
    """
    _production_gate(target, i_know_what_im_doing)

    ssh_host, _init_container, web_container = _resolve_target(target)

    # Show current hotfixes before rollback
    records = _query_hotfix_params(ssh_host, web_container)
    if not records:
        console.print(f"[green]No active hotfixes on {target}. Nothing to roll back.[/green]")
        return

    console.print(f"[yellow]Rolling back {len(records)} hotfix(es) on {target}...[/yellow]")

    # Clear hotfix records
    deleted = _delete_hotfix_params(ssh_host, web_container)
    console.print(f"[green]Cleared {deleted} hotfix record(s).[/green]")

    # Force-recreate containers from clean image
    console.print("[cyan]Recreating containers from clean image...[/cyan]")
    _ssh_run(
        ssh_host,
        f"docker compose -f /opt/dokploy/compose/{target}/docker-compose.yml up -d --force-recreate odoo-web odoo-cron",
    )
    console.print(f"[green]Rollback complete. Containers recreated on {target}.[/green]")
