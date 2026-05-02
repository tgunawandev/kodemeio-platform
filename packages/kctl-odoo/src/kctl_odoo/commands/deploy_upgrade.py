"""Deploy upgrade — set ODOO_RUN_UPDATE env vars, redeploy via Dokploy, clean up.

Wraps the 5-step flow (set env → redeploy → wait → verify → clean env) into
a single command. Requires kctl-dokploy's Dokploy API credentials in the
shared config under the same profile.
"""

from __future__ import annotations

import http.client
import json
import ssl
import time
import urllib.parse
from typing import Annotated

import typer
from rich.console import Console

console = Console()


def _dokploy_config(profile: str) -> tuple[str, str]:
    """Read Dokploy URL and API key from shared config."""
    import yaml

    config_path = __import__("pathlib").Path.home() / ".config" / "kodemeio" / "config.yaml"
    if not config_path.exists():
        console.print(f"[red]Config not found: {config_path}[/red]")
        raise typer.Exit(1)

    cfg = yaml.safe_load(config_path.read_text())
    prof = cfg.get("profiles", {}).get(profile, {})
    dokploy = prof.get("dokploy", {})
    url = dokploy.get("url", "")
    api_key = dokploy.get("api_key", "")

    if not url or not api_key:
        console.print(
            f"[red]No dokploy config in profile '{profile}'. Run: kctl-dokploy -p {profile} config init[/red]"
        )
        raise typer.Exit(1)

    return url.rstrip("/"), api_key


def _dokploy_request(
    base_url: str, api_key: str, path: str, *, method: str = "GET", data: dict | None = None, query: str = ""
) -> tuple[int, dict]:
    """HTTP request using http.client (preserves lowercase x-api-key header)."""
    parsed = urllib.parse.urlparse(base_url)
    full_path = f"/api/{path}"
    if query:
        full_path += f"?{query}"

    if parsed.scheme == "https":
        conn = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=30)
    else:
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=30)

    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    body = json.dumps(data) if data else None

    try:
        conn.request(method, full_path, body=body, headers=headers)
        resp = conn.getresponse()
        resp_body = resp.read().decode()
        return resp.status, json.loads(resp_body) if resp_body else {}
    except Exception as e:
        console.print(f"[red]Dokploy API error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        conn.close()


def _get_env(url: str, api_key: str, compose_id: str) -> str:
    """Fetch current env content for a compose."""
    status, data = _dokploy_request(url, api_key, "compose.one", query=f"composeId={compose_id}")
    if status != 200:
        console.print(f"[red]Failed to get compose env: HTTP {status}[/red]")
        raise typer.Exit(1)
    return data.get("env", "")


def _set_env(url: str, api_key: str, compose_id: str, env_content: str) -> None:
    """Update env content for a compose."""
    status, data = _dokploy_request(
        url, api_key, "compose.update", method="POST", data={"composeId": compose_id, "env": env_content}
    )
    if status != 200:
        console.print(f"[red]Failed to update env: HTTP {status} — {data}[/red]")
        raise typer.Exit(1)


def _redeploy(url: str, api_key: str, compose_id: str) -> None:
    """Trigger compose redeploy."""
    status, data = _dokploy_request(url, api_key, "compose.redeploy", method="POST", data={"composeId": compose_id})
    if status != 200:
        console.print(f"[red]Failed to trigger redeploy: HTTP {status} — {data}[/red]")
        raise typer.Exit(1)


def upgrade(
    compose_id: Annotated[str, typer.Argument(help="Dokploy compose ID")],
    modules: Annotated[
        str, typer.Option("--modules", "-m", help="Modules to upgrade (comma-separated, or 'all')")
    ] = "all",
    dokploy_profile: Annotated[
        str, typer.Option("--dokploy-profile", "-dp", help="Dokploy config profile name (required)")
    ] = ...,
    wait: Annotated[int, typer.Option("--wait", "-w", help="Seconds to wait for redeploy before health check")] = 120,
    health_url: Annotated[
        str | None,
        typer.Option(
            "--health-url", help="URL to check after redeploy (e.g. https://mac-odoo-erp-stg.idtpp.com/web/health)"
        ),
    ] = None,
    skip_cleanup: Annotated[
        bool, typer.Option("--skip-cleanup", help="Don't remove ODOO_RUN_UPDATE env vars after deploy")
    ] = False,
) -> None:
    """Upgrade modules on a Dokploy-hosted Odoo instance via init container.

    Sets ODOO_RUN_UPDATE env vars on the compose, triggers a redeploy
    (init container runs odoo -u <modules> --stop-after-init), waits
    for health, then cleans up the env vars.

    Examples:
      kctl-odoo deploy upgrade h1I7b35s8w9UVOhbqLNgT -m stock_management
      kctl-odoo deploy upgrade h1I7b35s8w9UVOhbqLNgT -m stock_management,partner_management
      kctl-odoo deploy upgrade h1I7b35s8w9UVOhbqLNgT -m all
      kctl-odoo deploy upgrade h1I7b35s8w9UVOhbqLNgT -m all --health-url https://mac-odoo-erp-stg.idtpp.com/web/health
    """
    url, api_key = _dokploy_config(dokploy_profile)

    console.print(f"[bold]Deploy Upgrade[/bold]")
    console.print(f"  Compose: {compose_id}")
    console.print(f"  Modules: {modules}")
    console.print(f"  Dokploy: {url}")
    console.print()

    # Step 1: Set ODOO_RUN_UPDATE env vars
    console.print("[cyan]Step 1/5:[/cyan] Setting ODOO_RUN_UPDATE env vars...")
    current_env = _get_env(url, api_key, compose_id)
    clean_env = "\n".join(
        line
        for line in current_env.split("\n")
        if not line.startswith("ODOO_RUN_UPDATE=") and not line.startswith("ODOO_RUN_UPDATE_MODULES=")
    )
    new_env = f"{clean_env}\nODOO_RUN_UPDATE=true\nODOO_RUN_UPDATE_MODULES={modules}"
    _set_env(url, api_key, compose_id, new_env)
    console.print(f"  Set ODOO_RUN_UPDATE_MODULES={modules}")

    # Step 2: Trigger redeploy
    console.print("[cyan]Step 2/5:[/cyan] Triggering redeploy...")
    _redeploy(url, api_key, compose_id)
    console.print("  Redeploy triggered")

    # Step 3: Wait for init container to finish
    console.print(f"[cyan]Step 3/5:[/cyan] Waiting {wait}s for init + module upgrade...")
    time.sleep(wait)

    # Step 4: Health check
    if health_url:
        console.print(f"[cyan]Step 4/5:[/cyan] Checking health at {health_url}...")
        healthy = False
        for attempt in range(1, 11):
            try:
                req = urllib.request.Request(health_url)
                resp = urllib.request.urlopen(req, timeout=10)
                if resp.status == 200:
                    console.print(f"  [green]Healthy (attempt {attempt})[/green]")
                    healthy = True
                    break
            except Exception:
                pass
            console.print(f"  Attempt {attempt}/10 — not ready, waiting 30s...")
            time.sleep(30)

        if not healthy:
            console.print("[red]Health check failed after 5 min[/red]")
            console.print("[yellow]Env vars NOT cleaned up — investigate and run with --skip-cleanup to retry[/yellow]")
            raise typer.Exit(1)
    else:
        console.print("[cyan]Step 4/5:[/cyan] No --health-url provided, skipping health check")

    # Step 5: Clean up env vars
    if skip_cleanup:
        console.print("[cyan]Step 5/5:[/cyan] --skip-cleanup set, leaving env vars in place")
    else:
        console.print("[cyan]Step 5/5:[/cyan] Cleaning up ODOO_RUN_UPDATE env vars...")
        final_env = "\n".join(
            line
            for line in new_env.split("\n")
            if not line.startswith("ODOO_RUN_UPDATE=") and not line.startswith("ODOO_RUN_UPDATE_MODULES=")
        )
        _set_env(url, api_key, compose_id, final_env)
        console.print("  Env vars removed")

    console.print()
    console.print("[bold green]Deploy upgrade complete![/bold green]")
