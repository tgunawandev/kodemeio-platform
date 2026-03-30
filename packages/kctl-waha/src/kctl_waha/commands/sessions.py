"""WhatsApp session management commands.

Create, start, stop, restart, and inspect sessions.
"""

from __future__ import annotations

import os
from typing import Annotated

import typer

from kctl_waha.core.callbacks import AppContext
from kctl_waha.core.exceptions import KctlError

app = typer.Typer(help="Manage WhatsApp sessions.")

DEFAULT_SESSION = os.environ.get("WAHA_DEFAULT_SESSION", "default")


@app.command("list")
def list_(
    ctx: typer.Context,
    all_sessions: Annotated[bool, typer.Option("--all", "-a", help="Include stopped sessions.")] = False,
) -> None:
    """List WhatsApp sessions."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    params: dict = {}
    if all_sessions:
        params["all"] = "true"

    try:
        raw = c.get("sessions/", params=params)
    except KctlError as e:
        out.error(f"Failed to list sessions: {e}")
        raise typer.Exit(1) from e

    sessions = raw if isinstance(raw, list) else []

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for s in sessions:
        name = s.get("name", "unknown")
        status = s.get("status", "UNKNOWN")
        engine = s.get("config", {}).get("engine", s.get("engine", "NOWEB"))

        if status == "WORKING":
            status_display = "[green]WORKING[/green]"
        elif status == "SCAN_QR_CODE":
            status_display = "[yellow]SCAN_QR[/yellow]"
        elif status == "STOPPED":
            status_display = "[red]STOPPED[/red]"
        elif status == "STARTING":
            status_display = "[yellow]STARTING[/yellow]"
        elif status == "FAILED":
            status_display = "[red]FAILED[/red]"
        else:
            status_display = f"[dim]{status}[/dim]"

        rows.append([name, status_display, engine])
        json_data.append(
            {
                "name": name,
                "status": status,
                "engine": engine,
            }
        )

    out.table(
        f"Sessions ({len(sessions)})",
        [("Name", "cyan"), ("Status", ""), ("Engine", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def get(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Session name.")] = DEFAULT_SESSION,
) -> None:
    """Show session details."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        raw = c.get("sessions/", params={"all": "true"})
    except KctlError as e:
        out.error(f"Failed to get sessions: {e}")
        raise typer.Exit(1) from e

    sessions = raw if isinstance(raw, list) else []
    session = next((s for s in sessions if s.get("name") == name), None)

    if not session:
        out.error(f"Session '{name}' not found")
        raise typer.Exit(1)

    status = session.get("status", "UNKNOWN")
    config = session.get("config", {})
    engine = config.get("engine", session.get("engine", "NOWEB"))
    webhooks = config.get("webhooks", [])

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    # Basic info
    basic_kvs: list[tuple[str, str]] = [
        ("Name", name),
        ("Status", status),
        ("Engine", engine),
    ]
    sections.append(("Session", basic_kvs))

    # Me info (if working)
    if status == "WORKING":
        try:
            me = c.get(f"sessions/{name}/me")
            if isinstance(me, dict):
                me_kvs: list[tuple[str, str]] = [
                    ("Phone", me.get("id", "").replace("@c.us", "")),
                    ("Push Name", me.get("pushName", "")),
                    ("Platform", me.get("platform", "")),
                ]
                sections.append(("Account", me_kvs))
        except Exception:
            pass

    # Webhooks
    if webhooks:
        wh_kvs: list[tuple[str, str]] = []
        for i, wh in enumerate(webhooks):
            url = wh.get("url", "")
            events = ", ".join(wh.get("events", []))
            wh_kvs.append((f"Webhook {i + 1}", f"{url}  events: {events}"))
        sections.append(("Webhooks", wh_kvs))

    # Config extras
    config_kvs: list[tuple[str, str]] = []
    proxy = config.get("proxy")
    if proxy:
        config_kvs.append(("Proxy", str(proxy)))
    debug = config.get("debug", False)
    config_kvs.append(("Debug", str(debug)))
    if config_kvs:
        sections.append(("Configuration", config_kvs))

    out.detail(f"Session: {name}", sections, data_for_json=session)


@app.command()
def start(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Session name.")] = DEFAULT_SESSION,
    engine: Annotated[str | None, typer.Option("--engine", "-e", help="Engine: NOWEB or WEBJS.")] = None,
) -> None:
    """Start a WhatsApp session.

    Creates the session if it does not exist, otherwise starts existing session.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Check if session exists
    try:
        raw = c.get("sessions/", params={"all": "true"})
        sessions = raw if isinstance(raw, list) else []
        existing = next((s for s in sessions if s.get("name") == name), None)
    except Exception:
        existing = None

    try:
        if existing:
            # Session exists, start it
            result = c.post(f"sessions/{name}/start")
        else:
            # Create new session
            body: dict = {"name": name}
            if engine:
                body["config"] = {"engine": engine.upper()}
            result = c.post("sessions/", data=body)
    except KctlError as e:
        out.error(f"Failed to start session '{name}': {e}")
        raise typer.Exit(1) from e

    out.success(f"Session '{name}' started")
    if isinstance(result, dict):
        status = result.get("status", "")
        if status:
            out.kv("Status", status)


@app.command()
def stop(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Session name.")] = DEFAULT_SESSION,
) -> None:
    """Stop a WhatsApp session."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        c.post(f"sessions/{name}/stop")
    except KctlError as e:
        out.error(f"Failed to stop session '{name}': {e}")
        raise typer.Exit(1) from e

    out.success(f"Session '{name}' stopped")


@app.command()
def restart(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Session name.")] = DEFAULT_SESSION,
) -> None:
    """Restart a WhatsApp session (stop + start)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        c.post(f"sessions/{name}/stop")
    except Exception:
        pass  # Session may already be stopped

    try:
        c.post(f"sessions/{name}/start")
    except KctlError as e:
        out.error(f"Failed to restart session '{name}': {e}")
        raise typer.Exit(1) from e

    out.success(f"Session '{name}' restarted")


@app.command()
def logout(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Session name.")] = DEFAULT_SESSION,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation.")] = False,
) -> None:
    """Logout from a WhatsApp session."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not force:
        if not typer.confirm(f"Logout session '{name}'? This will disconnect from WhatsApp."):
            raise typer.Exit(0)

    try:
        c.post(f"sessions/{name}/logout")
    except KctlError as e:
        out.error(f"Failed to logout session '{name}': {e}")
        raise typer.Exit(1) from e

    out.success(f"Session '{name}' logged out")


@app.command()
def delete(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Session name.")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation.")] = False,
) -> None:
    """Delete a WhatsApp session."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not force:
        if not typer.confirm(f"Delete session '{name}'? This cannot be undone."):
            raise typer.Exit(0)

    try:
        c.delete(f"sessions/{name}")
    except KctlError as e:
        out.error(f"Failed to delete session '{name}': {e}")
        raise typer.Exit(1) from e

    out.success(f"Session '{name}' deleted")


@app.command()
def qr(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Session name.")] = DEFAULT_SESSION,
) -> None:
    """Get QR code for session authentication."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        result = c.get(f"sessions/{name}/auth/qr")
    except KctlError as e:
        out.error(f"Failed to get QR code for session '{name}': {e}")
        raise typer.Exit(1) from e

    if isinstance(result, dict):
        qr_value = result.get("value", "")
        if qr_value:
            if out.json_mode:
                out.raw_json(result)
            else:
                out.text(f"\n[bold]QR Code for session: {name}[/bold]\n")
                out.text(qr_value)
                out.text("\n[dim]Scan this QR code with WhatsApp on your phone.[/dim]")
        else:
            out.warn("No QR code available. Session may already be authenticated.")
            if out.json_mode:
                out.raw_json(result)
    else:
        out.error("Unexpected response format")
        raise typer.Exit(1)


@app.command()
def me(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Session name.")] = DEFAULT_SESSION,
) -> None:
    """Show current session account info."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        result = c.get(f"sessions/{name}/me")
    except KctlError as e:
        out.error(f"Failed to get account info for session '{name}': {e}")
        raise typer.Exit(1) from e

    if not isinstance(result, dict):
        out.error("Unexpected response format")
        raise typer.Exit(1)

    phone = result.get("id", "").replace("@c.us", "")
    push_name = result.get("pushName", "")
    platform = result.get("platform", "")

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Account Info",
            [
                ("Session", name),
                ("Phone", phone or "[dim]unknown[/dim]"),
                ("Name", push_name or "[dim]unknown[/dim]"),
                ("Platform", platform or "[dim]unknown[/dim]"),
            ],
        ),
    ]

    out.detail(f"Session: {name}", sections, data_for_json=result)
