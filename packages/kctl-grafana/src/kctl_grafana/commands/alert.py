"""Alert management commands."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_grafana.core.callbacks import AppContext

app = typer.Typer(help="Alert rule management.")


@app.command("list")
def list_alerts(ctx: typer.Context) -> None:
    """List alert rules with current state."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    rules = client.get("/v1/provisioning/alert-rules")

    rows: list[list[str]] = []
    for rule in rules:
        uid = rule.get("uid", "")
        title = rule.get("title", "")
        folder = rule.get("folderUID", "")
        rule_group = rule.get("ruleGroup", "")
        for_duration = rule.get("for", "")

        # Determine state from labels/annotations if available
        state = rule.get("labels", {}).get("severity", "")
        rows.append([uid, title, folder, rule_group, for_duration, state])

    out.table(
        f"Alert Rules ({len(rules)})",
        [("UID", "cyan"), ("Title", ""), ("Folder", "dim"), ("Group", "dim"), ("For", ""), ("Severity", "")],
        rows,
        data_for_json=rules,
    )


@app.command("show")
def show_alert(
    ctx: typer.Context,
    uid: Annotated[str, typer.Argument(help="Alert rule UID")],
) -> None:
    """Show alert rule details."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    rule = client.get(f"/v1/provisioning/alert-rules/{uid}")

    labels = rule.get("labels", {})
    annotations = rule.get("annotations", {})

    sections = [
        (
            "Alert Rule",
            [
                ("UID", rule.get("uid", "")),
                ("Title", rule.get("title", "")),
                ("Folder UID", rule.get("folderUID", "")),
                ("Group", rule.get("ruleGroup", "")),
                ("For", rule.get("for", "")),
                ("Condition", rule.get("condition", "")),
                ("No Data State", rule.get("noDataState", "")),
                ("Exec Error State", rule.get("execErrState", "")),
                ("Updated", rule.get("updated", "")),
                ("Provisioned", str(rule.get("provenance", "") != "")),
            ],
        ),
    ]

    if labels:
        sections.append(("Labels", [(k, v) for k, v in labels.items()]))

    if annotations:
        sections.append(("Annotations", [(k, v) for k, v in annotations.items()]))

    out.detail(
        f"Alert Rule: {rule.get('title', uid)}",
        sections,
        data_for_json=rule,
    )


@app.command("silence")
def silence_alert(
    ctx: typer.Context,
    uid: Annotated[str, typer.Argument(help="Alert rule UID")],
    duration: Annotated[str, typer.Option("--duration", "-d", help="Silence duration (e.g., 1h, 30m, 2d)")] = "1h",
    comment: Annotated[str, typer.Option("--comment", "-c", help="Silence comment")] = "Silenced via kctl-grafana",
) -> None:
    """Silence an alert rule for a given duration."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    # Parse duration
    now = datetime.now(UTC)
    if duration.endswith("h"):
        delta = timedelta(hours=int(duration[:-1]))
    elif duration.endswith("m"):
        delta = timedelta(minutes=int(duration[:-1]))
    elif duration.endswith("d"):
        delta = timedelta(days=int(duration[:-1]))
    else:
        out.error(f"Invalid duration format: {duration}. Use 1h, 30m, or 2d.")
        raise typer.Exit(1)

    ends_at = now + delta

    # Get the alert rule to extract labels for matching
    rule = client.get(f"/v1/provisioning/alert-rules/{uid}")
    rule_title = rule.get("title", uid)

    # Create silence
    silence_payload = {
        "matchers": [
            {
                "name": "alertname",
                "value": rule_title,
                "isRegex": False,
                "isEqual": True,
            }
        ],
        "startsAt": now.isoformat(),
        "endsAt": ends_at.isoformat(),
        "createdBy": "kctl-grafana",
        "comment": comment,
    }

    result = client.post("/alertmanager/grafana/api/v2/silences", json_body=silence_payload)
    silence_id = result.get("silenceID", "unknown")
    out.success(f"Alert '{rule_title}' silenced for {duration} (silence ID: {silence_id})")


@app.command("contacts")
def list_contacts(ctx: typer.Context) -> None:
    """List notification contact points."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    contacts = client.get("/v1/provisioning/contact-points")

    rows: list[list[str]] = []
    for cp in contacts:
        name = cp.get("name", "")
        cp_type = cp.get("type", "")
        uid = cp.get("uid", "")
        provisioned = "[green]yes[/green]" if cp.get("provenance", "") else "[dim]no[/dim]"
        rows.append([uid, name, cp_type, provisioned])

    out.table(
        f"Contact Points ({len(contacts)})",
        [("UID", "cyan"), ("Name", ""), ("Type", ""), ("Provisioned", "")],
        rows,
        data_for_json=contacts,
    )
