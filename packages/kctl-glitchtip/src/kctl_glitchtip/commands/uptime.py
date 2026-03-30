"""Uptime monitoring commands (GlitchTip monitors)."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from kctl_glitchtip.core.callbacks import AppContext

app = typer.Typer(help="Manage uptime monitors.")


def _get_org_slug(c: AppContext) -> str:
    """Get the first organization slug."""
    orgs = c.client.get_list("organizations/")
    if orgs:
        return orgs[0].get("slug", "")
    c.output.error("No organizations found")
    raise typer.Exit(1)


@app.command("list")
def list_(
    ctx: typer.Context,
    org: Annotated[Optional[str], typer.Option("--org", help="Organization slug")] = None,
) -> None:
    """List uptime monitors."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    org_slug = org or _get_org_slug(actx)
    monitors = c.get_list(f"organizations/{org_slug}/monitors/")

    if not monitors:
        out.info("No uptime monitors found.")
        return

    rows: list[list[str]] = []
    for m in monitors:
        is_up = m.get("isUp", m.get("is_up"))
        status_str = "[green]up[/green]" if is_up else "[red]down[/red]" if is_up is False else "[dim]unknown[/dim]"
        rows.append(
            [
                str(m.get("id", "")),
                m.get("name", ""),
                m.get("monitorType", m.get("monitor_type", "")) or m.get("url", "-"),
                m.get("url", "-"),
                str(m.get("interval", "-")),
                status_str,
            ]
        )

    out.table(
        f"Uptime Monitors ({len(monitors)})",
        [("ID", "dim"), ("Name", "cyan"), ("Type", ""), ("URL", ""), ("Interval", "dim"), ("Status", "")],
        rows,
        data_for_json=monitors,
    )


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="Monitor name")],
    url: Annotated[str, typer.Option("--url", help="URL to monitor")],
    org: Annotated[Optional[str], typer.Option("--org", help="Organization slug")] = None,
    interval: Annotated[int, typer.Option("--interval", help="Check interval in seconds")] = 60,
    monitor_type: Annotated[str, typer.Option("--type", help="Monitor type (e.g. Ping, GET)")] = "Ping",
    expected_status: Annotated[int, typer.Option("--expected-status", help="Expected HTTP status code")] = 200,
) -> None:
    """Create an uptime monitor."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    org_slug = org or _get_org_slug(actx)

    # Try project-based endpoint first, then org-based
    payload: dict = {
        "name": name,
        "url": url,
        "interval": interval,
        "monitor_type": monitor_type,
        "expected_status": expected_status,
    }

    result = c.post(f"organizations/{org_slug}/monitors/", data=payload)
    out.success(f"Monitor '{name}' created")
    out.kv("ID", str(result.get("id", "")))
    out.kv("URL", url)
    if out.json_mode:
        out.raw_json(result)


@app.command()
def delete(
    ctx: typer.Context,
    monitor_id: Annotated[int, typer.Argument(help="Monitor ID")],
    org: Annotated[Optional[str], typer.Option("--org", help="Organization slug")] = None,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete an uptime monitor."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    org_slug = org or _get_org_slug(actx)

    if not force:
        if not typer.confirm(f"Delete monitor {monitor_id}?"):
            raise typer.Exit(0)

    c.delete(f"organizations/{org_slug}/monitors/{monitor_id}/")
    out.success(f"Monitor {monitor_id} deleted")


@app.command()
def checks(
    ctx: typer.Context,
    monitor_id: Annotated[int, typer.Argument(help="Monitor ID")],
    org: Annotated[Optional[str], typer.Option("--org", help="Organization slug")] = None,
) -> None:
    """Show recent checks for an uptime monitor."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    org_slug = org or _get_org_slug(actx)

    result = c.get_list(f"organizations/{org_slug}/monitors/{monitor_id}/checks/")

    if not result:
        out.info(f"No checks found for monitor {monitor_id}")
        return

    rows: list[list[str]] = []
    for check in result:
        is_up = check.get("isUp", check.get("is_up"))
        status = "[green]up[/green]" if is_up else "[red]down[/red]" if is_up is False else "[dim]unknown[/dim]"
        created = str(check.get("startCheck", check.get("created", "")))[:19].replace("T", " ")
        response_time = check.get("responseTime", check.get("response_time"))
        rows.append(
            [
                created,
                status,
                f"{response_time}ms" if response_time is not None else "-",
                str(check.get("reason", "-")),
            ]
        )

    out.table(
        f"Monitor Checks -- {monitor_id} ({len(result)})",
        [("Timestamp", "dim"), ("Status", ""), ("Response Time", ""), ("Reason", "dim")],
        rows,
        data_for_json=result,
    )
