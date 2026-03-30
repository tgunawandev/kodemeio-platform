"""Notification management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_ak.core.callbacks import AppContext

app = typer.Typer(name="notifications", help="Manage notifications, rules, and transports.")

_NOTIFICATIONS_ENDPOINT = "events/notifications/"
_RULES_ENDPOINT = "events/rules/"
_TRANSPORTS_ENDPOINT = "events/transports/"


@app.command("list")
def list_(
    ctx: typer.Context,
    page: Annotated[int, typer.Option(help="Page number.")] = 1,
) -> None:
    """List notifications."""
    c: AppContext = ctx.obj
    data = c.client.get(_NOTIFICATIONS_ENDPOINT, params={"page": page, "page_size": 20, "ordering": "-created"})
    results = data.get("results", [])
    pagination = data.get("pagination", {})

    if not results:
        c.output.info("No notifications found.")
        return

    rows = []
    for n in results:
        created = str(n.get("created", ""))[:19].replace("T", " ")
        severity = n.get("severity", "-")
        body = str(n.get("body", ""))[:60]
        seen = "yes" if n.get("seen") else "no"
        rows.append(
            [
                n.get("pk", "")[:8],
                severity,
                body,
                seen,
                created,
            ]
        )

    c.output.table(
        f"Notifications (page {page}, {pagination.get('count', len(results))} total)",
        [("ID", "dim"), ("Severity", "yellow"), ("Body", ""), ("Seen", "green"), ("Created", "dim")],
        rows,
        data_for_json=results,
    )


@app.command()
def rules(ctx: typer.Context) -> None:
    """List notification rules."""
    c: AppContext = ctx.obj
    data = c.client.get(_RULES_ENDPOINT)
    results = data.get("results", []) if isinstance(data, dict) else data if isinstance(data, list) else []

    if not results:
        c.output.info("No notification rules found.")
        return

    rows = []
    for r in results:
        transports = r.get("transports", [])
        transport_names = ", ".join(str(t) for t in transports[:3])
        if len(transports) > 3:
            transport_names += "..."
        group = r.get("group_obj", r.get("group", {}))
        group_name = group.get("name", str(group)) if isinstance(group, dict) else str(group)
        rows.append(
            [
                r.get("pk", "")[:8],
                r.get("name", ""),
                r.get("severity", "-"),
                group_name,
                transport_names or "-",
            ]
        )

    c.output.table(
        f"Notification Rules ({len(results)})",
        [("ID", "dim"), ("Name", "cyan"), ("Severity", "yellow"), ("Group", ""), ("Transports", "dim")],
        rows,
        data_for_json=results,
    )


@app.command("create-rule")
def create_rule(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="Rule name")],
    group: Annotated[str, typer.Option("--group", help="Group UUID")],
    severity: Annotated[str, typer.Option("--severity", help="Severity: notice, warning, alert")] = "notice",
    transports: Annotated[list[str] | None, typer.Option("--transport", help="Transport UUID(s)")] = None,
) -> None:
    """Create a notification rule."""
    c: AppContext = ctx.obj
    payload: dict = {
        "name": name,
        "group": group,
        "severity": severity,
    }
    if transports:
        payload["transports"] = transports

    result = c.client.post(_RULES_ENDPOINT, data=payload)
    c.output.success(f"Notification rule '{name}' created")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("update-rule")
def update_rule(
    ctx: typer.Context,
    rule_id: Annotated[str, typer.Argument(help="Rule UUID")],
    name: Annotated[str | None, typer.Option("--name")] = None,
    group: Annotated[str | None, typer.Option("--group")] = None,
    severity: Annotated[str | None, typer.Option("--severity")] = None,
    transports: Annotated[list[str] | None, typer.Option("--transport")] = None,
) -> None:
    """Update a notification rule."""
    c: AppContext = ctx.obj

    # Get current rule first
    current = c.client.get(f"{_RULES_ENDPOINT}{rule_id}/")

    payload: dict = {}
    payload["name"] = name if name is not None else current.get("name", "")
    payload["group"] = group if group is not None else current.get("group", "")
    if severity is not None:
        payload["severity"] = severity
    else:
        payload["severity"] = current.get("severity", "notice")
    if transports is not None:
        payload["transports"] = transports
    elif "transports" in current:
        payload["transports"] = current["transports"]

    result = c.client.put(f"{_RULES_ENDPOINT}{rule_id}/", data=payload)
    c.output.success(f"Notification rule '{rule_id}' updated")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("delete-rule")
def delete_rule(
    ctx: typer.Context,
    rule_id: Annotated[str, typer.Argument(help="Rule UUID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a notification rule."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete notification rule '{rule_id}'?", abort=True)
    c.client.delete(f"{_RULES_ENDPOINT}{rule_id}/")
    c.output.success(f"Notification rule '{rule_id}' deleted")


@app.command()
def transports(ctx: typer.Context) -> None:
    """List notification transports."""
    c: AppContext = ctx.obj
    data = c.client.get(_TRANSPORTS_ENDPOINT)
    results = data.get("results", []) if isinstance(data, dict) else data if isinstance(data, list) else []

    if not results:
        c.output.info("No notification transports found.")
        return

    rows = []
    for t in results:
        rows.append(
            [
                t.get("pk", "")[:8],
                t.get("name", ""),
                t.get("mode", ""),
                t.get("webhook_url", "-")[:50] if t.get("webhook_url") else "-",
                str(t.get("send_once", "")),
            ]
        )

    c.output.table(
        f"Notification Transports ({len(results)})",
        [("ID", "dim"), ("Name", "cyan"), ("Mode", ""), ("Webhook URL", "dim"), ("Send Once", "")],
        rows,
        data_for_json=results,
    )


@app.command("create-transport")
def create_transport(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="Transport name")],
    mode: Annotated[str, typer.Option("--mode", help="Mode: webhook, email, webhook_slack")] = "webhook",
    webhook_url: Annotated[str | None, typer.Option("--webhook-url", help="Webhook URL")] = None,
    send_once: Annotated[bool, typer.Option("--send-once/--send-always", help="Send notification only once")] = True,
) -> None:
    """Create a notification transport."""
    c: AppContext = ctx.obj
    payload: dict = {
        "name": name,
        "mode": mode,
        "send_once": send_once,
    }
    if webhook_url:
        payload["webhook_url"] = webhook_url

    result = c.client.post(_TRANSPORTS_ENDPOINT, data=payload)
    c.output.success(f"Notification transport '{name}' created")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("delete-transport")
def delete_transport(
    ctx: typer.Context,
    transport_id: Annotated[str, typer.Argument(help="Transport UUID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a notification transport."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete notification transport '{transport_id}'?", abort=True)
    c.client.delete(f"{_TRANSPORTS_ENDPOINT}{transport_id}/")
    c.output.success(f"Notification transport '{transport_id}' deleted")


@app.command("mark-read")
def mark_read(
    ctx: typer.Context,
    notification_id: Annotated[str | None, typer.Argument(help="Notification UUID (omit to mark all read)")] = None,
) -> None:
    """Mark notification(s) as seen."""
    c: AppContext = ctx.obj

    if notification_id:
        c.client.post(f"{_NOTIFICATIONS_ENDPOINT}{notification_id}/mark_all_seen/")
        c.output.success(f"Notification '{notification_id}' marked as seen")
    else:
        # Mark all as seen
        c.client.post(f"{_NOTIFICATIONS_ENDPOINT}mark_all_seen/")
        c.output.success("All notifications marked as seen")
