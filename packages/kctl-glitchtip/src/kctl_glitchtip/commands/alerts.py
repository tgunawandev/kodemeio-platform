"""Alert and notification commands."""

from __future__ import annotations

import subprocess
from typing import Annotated, Optional

import httpx
import typer

from kctl_glitchtip.core.callbacks import AppContext

app = typer.Typer(help="Manage alerts and notifications.")


@app.command("list")
def list_(
    ctx: typer.Context,
    org_slug: Annotated[str, typer.Option("--org", help="Organization slug")],
    project_slug: Annotated[str, typer.Option("--project", help="Project slug")],
) -> None:
    """List project alerts."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    alerts = c.get_list(f"projects/{org_slug}/{project_slug}/alerts/")

    rows: list[list[str]] = []
    for a in alerts:
        alert_id = str(a.get("id", ""))
        name = a.get("name", "")
        alert_type = a.get("alertType", a.get("type", ""))
        quantity = str(a.get("quantity", ""))
        timespan = str(a.get("timespanMinutes", a.get("timespan_minutes", "")))
        rows.append([alert_id, name, alert_type, quantity, f"{timespan}m" if timespan else "-"])

    out.table(
        f"Alerts — {org_slug}/{project_slug}",
        [("ID", "cyan"), ("Name", ""), ("Type", ""), ("Threshold", ""), ("Window", "dim")],
        rows,
        data_for_json=alerts,
    )


@app.command("test-alert")
def test_alert(
    ctx: typer.Context,
    org_slug: Annotated[str, typer.Option("--org", help="Organization slug")],
    project_slug: Annotated[str, typer.Option("--project", help="Project slug")],
    alert_id: Annotated[int, typer.Argument(help="Alert ID to test")],
) -> None:
    """Test a project alert."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    result = c.post(f"projects/{org_slug}/{project_slug}/alerts/{alert_id}/test/")
    out.success(f"Test alert {alert_id} sent")
    if out.json_mode:
        out.raw_json(result)


@app.command("test-webhook")
def test_webhook(
    ctx: typer.Context,
    url: Annotated[str, typer.Argument(help="Webhook URL to test")],
) -> None:
    """Send test alert to a webhook URL."""
    actx: AppContext = ctx.obj
    out = actx.output

    payload = {
        "text": "GlitchTip test alert from kctl-glitchtip",
        "alias": "kctl-glitchtip-test",
    }

    try:
        resp = httpx.post(url, json=payload, timeout=10)
        if resp.status_code < 300:
            out.success(f"Webhook responded: {resp.status_code}")
        else:
            out.error(f"Webhook failed: {resp.status_code} — {resp.text[:200]}")
    except Exception as e:
        out.error(f"Webhook error: {e}")


@app.command("test-email")
def test_email(
    ctx: typer.Context,
    to: Annotated[Optional[str], typer.Option("--to", help="Recipient email (default: admin)")] = None,
) -> None:
    """Send test email via Django (requires Docker access)."""
    actx: AppContext = ctx.obj
    out = actx.output

    cmd = ["docker", "exec", "kodemeio-glitchtip", "./manage.py", "sendtestemail"]
    if to:
        cmd.append(to)
    else:
        cmd.append("--admin")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            out.success("Test email sent")
        else:
            out.error(f"Failed: {result.stderr.strip()}")
    except FileNotFoundError:
        out.error("Docker not found")
    except subprocess.TimeoutExpired:
        out.error("Email send timed out")
