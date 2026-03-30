"""Local Docker Compose development commands."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from kctl_odoo.core.local import LocalClient

app = typer.Typer(help="Local Docker Compose development environment.")

console = Console()


def _get_client() -> LocalClient:
    return LocalClient()


@app.command("up")
def up(
    tunnel: Annotated[bool, typer.Option("--tunnel", help="Enable Cloudflare tunnel")] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Enable debugpy on port 5678")] = False,
    cron: Annotated[bool, typer.Option("--cron", help="Enable cron scheduler service")] = False,
) -> None:
    """Start the development environment (docker compose up)."""
    client = _get_client()
    flags = []
    if tunnel:
        flags.append("tunnel")
    if debug:
        flags.append("debug")
    if cron:
        flags.append("cron")
    if flags:
        console.print(f"Starting with profiles: {', '.join(flags)}")
    result = client.up(tunnel=tunnel, debug=debug, cron=cron)
    if result.returncode == 0:
        console.print("[green]Development environment started.[/green]")
        # Auto-sync web.base.url after startup
        _sync_base_url_on_up()
    else:
        raise typer.Exit(result.returncode)


def _sync_base_url_on_up() -> None:
    """Best-effort sync of web.base.url after local up."""
    from pathlib import Path

    try:
        # Read port from .env
        env_file = Path.cwd() / ".env"
        port = "8069"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("ODOO_HTTP_PORT="):
                    port = line.split("=", 1)[1].strip()
                    break

        expected_url = f"http://localhost:{port}"

        import subprocess
        import time

        time.sleep(3)
        subprocess.run(
            ["kctl-odoo", "server", "set-param", "web.base.url", expected_url],
            capture_output=True,
            timeout=15,
        )
        console.print(f"[dim]Synced web.base.url = {expected_url}[/dim]")
    except Exception:
        # Best-effort — don't fail the up command
        pass


@app.command("down")
def down() -> None:
    """Stop all containers."""
    client = _get_client()
    result = client.down()
    if result.returncode == 0:
        console.print("[green]All containers stopped.[/green]")
    else:
        raise typer.Exit(result.returncode)


@app.command("restart")
def restart(
    service: Annotated[str | None, typer.Argument(help="Service to restart (default: all)")] = None,
) -> None:
    """Restart container(s)."""
    client = _get_client()
    result = client.restart(service)
    if result.returncode == 0:
        target = service or "all services"
        console.print(f"[green]Restarted {target}.[/green]")
    else:
        raise typer.Exit(result.returncode)


@app.command("status")
def status() -> None:
    """Show container status."""
    client = _get_client()
    result = client.status()
    if result.stdout:
        console.print(result.stdout)
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


@app.command("build")
def build(
    no_cache: Annotated[bool, typer.Option("--no-cache", help="Build without cache")] = False,
) -> None:
    """Build Docker image."""
    client = _get_client()
    result = client.build(no_cache=no_cache)
    if result.returncode == 0:
        console.print("[green]Build completed.[/green]")
    else:
        raise typer.Exit(result.returncode)


@app.command("exec")
def exec_cmd(
    command: Annotated[list[str], typer.Argument(help="Command to execute in container")],
) -> None:
    """Execute a command inside the Odoo container."""
    if not command:
        typer.echo("No command specified.", err=True)
        raise typer.Exit(1)
    client = _get_client()
    result = client.exec(*command, interactive=True)
    raise typer.Exit(result.returncode)


@app.command("shell")
def shell(
    database: Annotated[str | None, typer.Argument(help="Database name")] = None,
    db: Annotated[str | None, typer.Option("--database", "-d", help="Database name")] = None,
) -> None:
    """Open interactive Odoo shell.

    Examples:
        kctl-odoo local shell odoo_full
        kctl-odoo local shell -d odoo_full
    """
    client = _get_client()
    client.shell(database=db or database or "")


@app.command("test")
def test(
    module: Annotated[str, typer.Argument(help="Module to test")],
    tags: Annotated[str | None, typer.Option("--tags", help="Test tag filter")] = None,
    database: Annotated[str | None, typer.Option("--database", "-d", help="Test database")] = None,
    clean: Annotated[bool, typer.Option("--clean", help="Drop test database after run")] = False,
) -> None:
    """Run Odoo tests for a module."""
    client = _get_client()
    result = client.test(module, tags=tags or "", database=database or "", clean=clean)
    raise typer.Exit(result.returncode)


@app.command("aggregate")
def aggregate() -> None:
    """Fetch OCA repositories via git-aggregator."""
    client = _get_client()
    result = client.aggregate()
    if result.returncode == 0:
        console.print("[green]OCA repositories aggregated and linked.[/green]")
    else:
        raise typer.Exit(result.returncode)


@app.command("db-create")
def db_create(
    name: Annotated[str, typer.Argument(help="Database name")],
    modules: Annotated[str, typer.Option("--modules", "-m", help="Modules to install")] = "base",
) -> None:
    """Create a new database via Docker.

    Examples:
        kctl-odoo local db-create odoo_full
        kctl-odoo local db-create odoo_test -m sale,stock
    """
    client = _get_client()
    result = client.exec("db", "create", name, modules)
    if result.returncode == 0:
        console.print(f"[green]Database '{name}' created.[/green]")
    else:
        raise typer.Exit(result.returncode)


@app.command("db-drop")
def db_drop(
    name: Annotated[str, typer.Argument(help="Database name")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation")] = False,
) -> None:
    """Drop a database via Docker (irreversible).

    Examples:
        kctl-odoo local db-drop odoo_full
        kctl-odoo local db-drop odoo_full -y
    """
    if not force and not typer.confirm(f"DROP database '{name}'? This is irreversible."):
        raise typer.Exit(0)
    client = _get_client()
    result = client.exec("db", "drop", name, "-y")
    if result.returncode == 0:
        console.print(f"[green]Database '{name}' dropped.[/green]")
    else:
        raise typer.Exit(result.returncode)


@app.command("db-list")
def db_list() -> None:
    """List databases via Docker."""
    client = _get_client()
    result = client.exec("db", "list", capture=True)
    if result.stdout:
        console.print(result.stdout)
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


@app.command("install")
def install(
    modules: Annotated[str | None, typer.Argument(help="Comma-separated module names")] = None,
    bundle: Annotated[str | None, typer.Option("--file", "-f", help="Bundle YAML file")] = None,
    groups: Annotated[str | None, typer.Option("--groups", "-g", help="Bundle groups to install")] = None,
    database: Annotated[str | None, typer.Option("--database", "-d", help="Target database")] = None,
    no_demo: Annotated[bool, typer.Option("--no-demo", help="Install without demo data")] = False,
) -> None:
    """Install modules via Docker (no JSON-RPC timeout).

    Examples:
        kctl-odoo local install sale,stock
        kctl-odoo local install -f install/oca-server.yaml
        kctl-odoo local install -f install/oca-server.yaml -g core -d odoo_full
        kctl-odoo local install sale,stock --no-demo
    """
    client = _get_client()
    if bundle:
        args = ["mod", "install", "-f", bundle]
        if groups:
            args.extend(["-g", groups])
        if database:
            args.extend(["--database", database])
        if no_demo:
            args.append("--no-demo")
        result = client.exec(*args)
    elif modules:
        args = ["mod", "install", modules]
        if database:
            args.extend(["--database", database])
        if no_demo:
            args.append("--no-demo")
        result = client.exec(*args)
    else:
        console.print("[red]Specify modules or --file bundle.yaml[/red]", highlight=False)
        raise typer.Exit(1)
    if result.returncode == 0:
        console.print("[green]Modules installed.[/green]")
    else:
        raise typer.Exit(result.returncode)


@app.command("update")
def update(
    modules: Annotated[str, typer.Argument(help="Comma-separated module names")],
    database: Annotated[str | None, typer.Option("--database", "-d", help="Target database")] = None,
    safe: Annotated[
        bool, typer.Option("--safe", help="Stop Odoo before update, restart after (avoids concurrent errors)")
    ] = False,
) -> None:
    """Update modules via Docker.

    Examples:
        kctl-odoo local update sale_management
        kctl-odoo local update sale_management,stock_management -d odoo_full
        kctl-odoo local update report_management -d odoo_full --safe
    """
    client = _get_client()
    if safe:
        console.print("[yellow]Safe mode: stopping Odoo before update...[/yellow]")
        result = client.safe_update(modules.split(","), database=database or "")
        if result.returncode == 0:
            console.print("[green]Modules updated (safe mode).[/green]")
        else:
            raise typer.Exit(result.returncode)
    else:
        args = ["mod", "update", modules]
        if database:
            args.extend(["--database", database])
        result = client.exec(*args)
        if result.returncode == 0:
            console.print("[green]Modules updated.[/green]")
        else:
            raise typer.Exit(result.returncode)


@app.command("install-bundles")
def install_bundles(
    database: Annotated[str | None, typer.Option("--database", "-d", help="Target database")] = None,
    tier: Annotated[str | None, typer.Option("--tier", help="Tiers: core, oca, private, all")] = None,
    all_groups: Annotated[bool, typer.Option("--all", help="Install ALL groups (not just default)")] = False,
    single: Annotated[bool, typer.Option("--single", help="Install all in one Odoo call")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without installing")] = False,
) -> None:
    """Install all bundles by tier (core -> oca -> private).

    Examples:
        kctl-odoo local install-bundles -d odoo_full --all
        kctl-odoo local install-bundles --tier core,oca --dry-run
        kctl-odoo local install-bundles -d odoo_full --single
    """
    client = _get_client()
    args = ["mod", "install-bundles"]
    if database:
        args.extend(["--database", database])
    if tier:
        args.extend(["--tier", tier])
    if all_groups:
        args.append("--all")
    if single:
        args.append("--single")
    if dry_run:
        args.append("--dry-run")
    result = client.exec(*args)
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


@app.command("install-profiles")
def install_profiles(
    profiles: Annotated[list[str] | None, typer.Argument(help="Profile names (default: all)")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without installing")] = False,
    no_demo: Annotated[bool, typer.Option("--no-demo", help="Install without demo data")] = False,
) -> None:
    """Install deployment profiles (creates databases + installs bundles).

    Examples:
        kctl-odoo local install-profiles full
        kctl-odoo local install-profiles full --no-demo
        kctl-odoo local install-profiles hrms trading
        kctl-odoo local install-profiles --dry-run
    """
    client = _get_client()
    args = ["install-profiles"]
    if profiles:
        args.extend(profiles)
    if dry_run:
        args.append("--dry-run")
    if no_demo:
        args.append("--no-demo")
    result = client.exec(*args)
    if result.returncode == 0:
        console.print("[green]Profile installation complete.[/green]")
    else:
        raise typer.Exit(result.returncode)


@app.command("clear-assets")
def clear_assets(
    database: Annotated[str | None, typer.Option("--database", "-d", help="Target database")] = None,
) -> None:
    """Clear compiled asset bundles (CSS/JS cache).

    Useful after changing JavaScript or CSS files. Deletes ir_attachment
    records with 'assets' in the name, forcing Odoo to recompile.

    Examples:
        kctl-odoo local clear-assets
        kctl-odoo local clear-assets -d odoo_full
    """
    client = _get_client()
    result = client.clear_assets(database=database or "")
    if result.returncode == 0:
        # Parse DELETE count from psql output
        output = (result.stdout or "").strip()
        console.print(f"[green]Assets cleared.[/green] {output}")
    else:
        console.print(f"[red]Failed to clear assets.[/red] {result.stderr or ''}")
        raise typer.Exit(result.returncode)


@app.command("lint-js")
def lint_js(
    module: Annotated[str | None, typer.Argument(help="Module name (default: all)")] = None,
    fix: Annotated[bool, typer.Option("--fix", help="Auto-fix issues")] = False,
) -> None:
    """Lint JavaScript files in private Odoo modules."""
    import subprocess

    client = _get_client()
    cmd = [str(client.project_dir / "bin" / "lint-js")]
    if module:
        cmd.append(module)
    if fix:
        cmd.append("--fix")
    result = subprocess.run(cmd, cwd=str(client.project_dir))
    raise typer.Exit(result.returncode)


@app.command("db-reset")
def db_reset(
    database: Annotated[str, typer.Argument(help="Database name")],
    with_demo: Annotated[bool, typer.Option("--with-demo", help="Load demo data")] = False,
    modules: Annotated[str | None, typer.Option("--modules", "-m", help="Modules to install after reset")] = None,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation")] = False,
) -> None:
    """Drop and recreate a database (irreversible).

    Drops the database and creates a fresh one. Optionally installs modules
    and/or loads demo data.

    Examples:
        kctl-odoo local db-reset odoo_dev -y
        kctl-odoo local db-reset odoo_test --with-demo --modules sale,stock
    """
    if not force and not typer.confirm(f"DROP and RECREATE database '{database}'? This is irreversible."):
        raise typer.Exit(0)

    client = _get_client()

    # Drop
    console.print(f"Dropping database '{database}'...")
    result = client.exec("db", "drop", database, "-y")
    if result.returncode != 0:
        console.print("[yellow]Drop returned non-zero (database may not exist). Continuing...[/yellow]")

    # Create
    install_modules = modules or "base"
    console.print(f"Creating database '{database}' with modules: {install_modules}...")
    args = ["db", "create", database, install_modules]
    result = client.exec(*args)
    if result.returncode != 0:
        console.print(f"[red]Failed to create database '{database}'.[/red]")
        raise typer.Exit(result.returncode)

    # Install additional modules with demo if requested
    if with_demo and modules:
        console.print("Installing modules with demo data...")
        install_args = ["mod", "install", modules]
        result = client.exec(*install_args)
        if result.returncode != 0:
            console.print("[yellow]Module installation with demo data had issues.[/yellow]")

    console.print(f"[green]Database '{database}' reset successfully.[/green]")


@app.command("reload")
def reload() -> None:
    """Restart Odoo and clear assets cache for development.

    Restarts the Odoo container and clears compiled asset attachments
    from the database to force regeneration.

    Examples:
        kctl-odoo local reload
    """
    client = _get_client()

    # Clear assets cache
    console.print("Clearing assets cache...")
    clear_result = client.clear_assets(database="")
    if clear_result.returncode == 0:
        console.print("[green]Assets cache cleared.[/green]")
    else:
        console.print("[yellow]Assets clear returned non-zero (DB may not exist yet).[/yellow]")

    # Restart Odoo
    console.print("Restarting Odoo...")
    result = client.restart("odoo")
    if result.returncode == 0:
        console.print("[green]Odoo restarted. Assets will regenerate on next page load.[/green]")
    else:
        console.print("[red]Failed to restart Odoo.[/red]")
        raise typer.Exit(result.returncode)
