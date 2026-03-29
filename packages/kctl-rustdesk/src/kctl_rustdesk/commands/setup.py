"""Setup and configuration commands."""

from __future__ import annotations

import typer

from kctl_rustdesk.core.callbacks import AppContext

app = typer.Typer(help="Server setup and configuration.")


@app.command()
def status(ctx: typer.Context) -> None:
    """Show setup status checklist."""
    c: AppContext = ctx.obj
    out = c.output
    ex = c.executor

    checks: list[tuple[str, bool]] = []
    checks.append(("hbbs container running", ex.container_running("hbbs")))
    checks.append(("hbbr container running", ex.container_running("hbbr")))
    checks.append(("Public key exists", ex.file_exists("hbbs", ex.KEY_PUB_PATH)))
    checks.append(("Private key exists", ex.file_exists("hbbs", ex.KEY_PRIV_PATH)))

    try:
        ex.query_db_scalar("SELECT count(*) FROM peer;")
        checks.append(("Database accessible", True))
    except Exception:
        checks.append(("Database accessible", False))

    out.header("Setup Status")
    all_ok = True
    for name, ok in checks:
        icon = "[green]OK[/green]" if ok else "[red]MISSING[/red]"
        out.text(f"  {icon} {name}")
        if not ok:
            all_ok = False

    out.text("")
    if all_ok:
        out.success("All checks passed. Server is ready.")
    else:
        out.warn("Some checks failed. Review and fix issues above.")


@app.command("get-key")
def get_key(ctx: typer.Context) -> None:
    """Display the server's public key."""
    c: AppContext = ctx.obj
    try:
        key = c.executor.get_public_key()
        if c.json_mode:
            c.output.raw_json({"public_key": key})
        else:
            c.output.text(key)
    except Exception as e:
        c.output.error(f"Cannot read public key: {e}")
        raise typer.Exit(1)


@app.command("client-config")
def client_config(ctx: typer.Context) -> None:
    """Generate RustDesk client configuration string."""
    c: AppContext = ctx.obj
    out = c.output
    ex = c.executor

    try:
        key = ex.get_public_key()
    except Exception as e:
        out.error(f"Cannot read public key: {e}")
        raise typer.Exit(1)

    domain = ex.config.domain
    config_str = f"rs-pub-key={key},rendezvous-server={domain}:21116,relay-server={domain}:21117"

    if c.json_mode:
        out.raw_json(
            {
                "config_string": config_str,
                "id_server": f"{domain}:21116",
                "relay_server": f"{domain}:21117",
                "public_key": key,
            }
        )
        return

    out.header("Client Configuration")
    out.kv("ID Server", f"{domain}:21116")
    out.kv("Relay Server", f"{domain}:21117")
    out.kv("Public Key", key)
    out.text("")
    out.text("[bold]Config string (paste into client):[/bold]")
    out.text(f"  {config_str}")


@app.command()
def firewall(ctx: typer.Context) -> None:
    """Show required firewall rules."""
    c: AppContext = ctx.obj
    rows = [
        ["21115", "TCP", "NAT type test"],
        ["21116", "TCP", "ID/Rendezvous server"],
        ["21116", "UDP", "ID/Rendezvous server (heartbeat)"],
        ["21117", "TCP", "Relay server"],
        ["21118", "TCP", "WebSocket (hbbs)"],
        ["21119", "TCP", "WebSocket (hbbr)"],
    ]

    c.output.table(
        "Required Firewall Rules",
        [("Port", "cyan"), ("Protocol", ""), ("Service", "")],
        rows,
    )
