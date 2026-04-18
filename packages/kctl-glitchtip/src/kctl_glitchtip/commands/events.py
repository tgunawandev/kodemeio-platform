"""Event management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_glitchtip.core.callbacks import AppContext

app = typer.Typer(help="Manage GlitchTip events.")


@app.command("list")
def list_(
    ctx: typer.Context,
    org_slug: Annotated[str, typer.Argument(help="Organization slug")],
    project_slug: Annotated[str, typer.Argument(help="Project slug")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 25,
) -> None:
    """List recent events for a project."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    events = c.get_list(f"projects/{org_slug}/{project_slug}/events/", params={"limit": limit})

    rows: list[list[str]] = []
    for e in events:
        event_id = str(e.get("eventID") or e.get("id", ""))[:12]
        title = (e.get("title") or e.get("message") or "")[:60]
        timestamp = str(e.get("dateCreated") or e.get("timestamp") or "")[:19]
        tags = e.get("tags", [])
        level = ""
        for tag in tags:
            if isinstance(tag, dict) and tag.get("key") == "level":
                level = tag.get("value", "")
                break
        rows.append([event_id, title, level, timestamp])

    out.table(
        f"Events — {org_slug}/{project_slug}",
        [("Event ID", "cyan"), ("Title", ""), ("Level", ""), ("Timestamp", "dim")],
        rows,
        data_for_json=events,
    )


@app.command()
def cleanup(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", "-d", help="Delete events older than N days")] = 90,
) -> None:
    """Clean old events via Django management command (requires Docker access)."""
    import subprocess

    actx: AppContext = ctx.obj
    out = actx.output

    out.info(f"Cleaning events older than {days} days...")
    try:
        result = subprocess.run(
            ["docker", "exec", "kodemeio-glitchtip", "./manage.py", "cleanup_old_events", "--days", str(days)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            out.success(f"Event cleanup complete (>{days} days)")
            if result.stdout.strip():
                out.text(result.stdout.strip())
        else:
            out.error(f"Cleanup failed: {result.stderr.strip()}")
            raise typer.Exit(1)
    except FileNotFoundError as e:
        out.error("Docker not found. This command requires Docker access to the GlitchTip container.")
        raise typer.Exit(1) from e
    except subprocess.TimeoutExpired as e:
        out.error("Cleanup timed out after 5 minutes")
        raise typer.Exit(1) from e
