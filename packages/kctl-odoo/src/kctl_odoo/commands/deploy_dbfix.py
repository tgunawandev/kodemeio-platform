"""Emergency DB fix — execute SQL on a Dokploy-hosted database when Odoo is down.

Resolves postgres connection details from Dokploy compose env vars,
then runs SQL via an ephemeral postgres:16 container on the target server.
Works even when odoo-init has crashed and the web server isn't running.
"""

from __future__ import annotations

import http.client
import json
import subprocess
import urllib.parse
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

console = Console()


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


def _extract_pg_from_env(env_str: str) -> dict[str, str]:
    """Extract PG* connection vars from a Dokploy compose env string."""
    pg = {}
    for line in env_str.split("\n"):
        line = line.strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key in ("PGHOST", "PGPORT", "PGUSER", "PGPASSWORD", "PGDATABASE"):
            pg[key] = value
    missing = {"PGHOST", "PGUSER", "PGPASSWORD", "PGDATABASE"} - pg.keys()
    if missing:
        console.print(f"[red]Missing postgres env vars: {', '.join(sorted(missing))}[/red]")
        raise typer.Exit(1)
    pg.setdefault("PGPORT", "5432")
    return pg


def db_fix(
    compose_id: Annotated[str, typer.Argument(help="Dokploy compose ID")],
    sql: Annotated[str | None, typer.Option("--sql", "-s", help="SQL to execute")] = None,
    sql_file: Annotated[Path | None, typer.Option("--file", "-f", help="SQL file to execute")] = None,
    dokploy_profile: Annotated[
        str, typer.Option("--dokploy-profile", "-dp", help="Dokploy config profile (required)")
    ] = ...,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would run without executing")] = False,
    i_know_what_im_doing: Annotated[
        bool, typer.Option("--i-know-what-im-doing", help="Required for production targets")
    ] = False,
) -> None:
    """Execute SQL directly on a Dokploy-hosted database.

    Auto-detects postgres connection from the compose's env vars.
    Runs SQL via an ephemeral postgres:16 container on the target
    server (works even when Odoo is crashed).

    Examples:
      kctl-odoo deploy db-fix h1I7b35s8w9UVOhbqLNgT -dp idtpp \\
        --sql "DELETE FROM ir_ui_view WHERE arch_db::text LIKE '%enforce_fefo%'"

      kctl-odoo deploy db-fix h1I7b35s8w9UVOhbqLNgT -dp idtpp \\
        --sql "SELECT name, state FROM ir_module_module WHERE state = 'to upgrade'"

      kctl-odoo deploy db-fix h1I7b35s8w9UVOhbqLNgT -dp idtpp -f fix.sql
    """
    if not sql and not sql_file:
        console.print("[red]Provide --sql or --file[/red]")
        raise typer.Exit(1)

    if sql_file:
        if not sql_file.exists():
            console.print(f"[red]File not found: {sql_file}[/red]")
            raise typer.Exit(1)
        sql = sql_file.read_text()

    dok_url, dok_key = _dokploy_config(dokploy_profile)
    data = _dokploy_get(dok_url, dok_key, "compose.one", f"composeId={compose_id}")

    compose_name = data.get("name", compose_id)
    server = data.get("server", {})
    ip = server.get("ipAddress", "")
    user = server.get("username", "root")
    ssh_host = f"{user}@{ip}"

    # Production gate
    safe_keywords = ("staging", "stg", "dev", "test", "local")
    if not any(kw in compose_name for kw in safe_keywords) and not i_know_what_im_doing:
        console.print(
            f"[red]Target '{compose_name}' looks like production.[/red]\nPass --i-know-what-im-doing to confirm."
        )
        raise typer.Exit(1)

    pg = _extract_pg_from_env(data.get("env", ""))

    console.print(f"[bold]DB Fix: {compose_name}[/bold]")
    console.print(f"  Server: {ssh_host}")
    console.print(f"  Database: {pg['PGUSER']}@{pg['PGHOST']}:{pg['PGPORT']}/{pg['PGDATABASE']}")
    console.print(f"  SQL: {sql[:100]}{'...' if len(sql) > 100 else ''}")
    console.print()

    if dry_run:
        console.print("[yellow]--dry-run: would execute the above SQL[/yellow]")
        return

    # Execute via ephemeral postgres:16 container on the target server
    import base64

    b64_sql = base64.b64encode(sql.encode()).decode()
    cmd = (
        f"docker run --rm --network dokploy-network "
        f"-e PGPASSWORD={pg['PGPASSWORD']} "
        f"postgres:16 "
        f"sh -c 'echo {b64_sql} | base64 -d | psql -h {pg['PGHOST']} -p {pg['PGPORT']} -U {pg['PGUSER']} -d {pg['PGDATABASE']}'"
    )

    result = subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=accept-new", ssh_host, cmd],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.stdout.strip():
        console.print(result.stdout.strip())
    if result.stderr.strip():
        for line in result.stderr.strip().split("\n"):
            if "WARNING" in line or "NOTICE" in line:
                continue
            console.print(f"[dim]{line}[/dim]")

    if result.returncode == 0:
        console.print("\n[bold green]SQL executed successfully.[/bold green]")
    else:
        console.print(f"\n[bold red]SQL failed (exit {result.returncode})[/bold red]")
        raise typer.Exit(1)
