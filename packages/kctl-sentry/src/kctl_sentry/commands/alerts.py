"""Alert rule management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_sentry.core.callbacks import AppContext
from kctl_sentry.core.exceptions import KctlError

app = typer.Typer(help="Manage alert rules.")


@app.command("list")
def list_(
    ctx: typer.Context,
    project: Annotated[str | None, typer.Option("--project", "-p", help="Filter by project slug")] = None,
) -> None:
    """List alert rules."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        rules = c.client.project_get(project, "/rules/") if project else c.client.org_get("/alert-rules/")
        if not isinstance(rules, list):
            rules = []

        rows: list[list[str]] = []
        for rule in rules:
            rule_id = str(rule.get("id", ""))
            name = (rule.get("name", "") or "")[:50]
            # Project-scoped rules have 'projects', org-scoped have 'project'
            proj_info = ""
            if isinstance(rule.get("projects"), list):
                proj_info = ", ".join(rule["projects"])
            elif isinstance(rule.get("project"), dict):
                proj_info = rule["project"].get("slug", "")

            status_val = rule.get("status", "active")
            owner = ""
            if isinstance(rule.get("owner"), dict):
                owner = rule["owner"].get("name", "")
            elif isinstance(rule.get("owner"), str):
                owner = rule["owner"]

            rows.append([rule_id, name, proj_info, status_val, owner])

        out.table(
            "Alert Rules",
            [
                ("ID", "cyan"),
                ("Name", ""),
                ("Project", ""),
                ("Status", "green"),
                ("Owner", "dim"),
            ],
            rows,
            data_for_json=rules,
        )
    except KctlError as e:
        out.error(f"Failed to list alerts: {e}")
        raise typer.Exit(1) from e


@app.command("show")
def show(
    ctx: typer.Context,
    rule_id: Annotated[str, typer.Argument(help="Alert rule ID")],
    project: Annotated[str, typer.Option("--project", "-p", help="Project slug")],
) -> None:
    """Show alert rule details and trigger history."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        rule = c.client.project_get(project, f"/rules/{rule_id}/")
        if not isinstance(rule, dict):
            rule = {}

        # Parse conditions
        conditions = rule.get("conditions", [])
        condition_strs: list[tuple[str, str]] = []
        for cond in conditions if isinstance(conditions, list) else []:
            if isinstance(cond, dict):
                condition_strs.append(("Condition", cond.get("name", str(cond.get("id", "")))))

        # Parse actions
        actions = rule.get("actions", [])
        action_strs: list[tuple[str, str]] = []
        for act in actions if isinstance(actions, list) else []:
            if isinstance(act, dict):
                action_strs.append(("Action", act.get("name", str(act.get("id", "")))))

        sections = [
            (
                "Alert Rule",
                [
                    ("ID", str(rule.get("id", ""))),
                    ("Name", rule.get("name", "")),
                    ("Status", rule.get("status", "")),
                    ("Frequency", f"{rule.get('frequency', '')} seconds"),
                    ("Date created", (rule.get("dateCreated", "") or "")[:19]),
                ],
            ),
        ]

        if condition_strs:
            sections.append(("Conditions", condition_strs))
        if action_strs:
            sections.append(("Actions", action_strs))

        out.detail(
            f"Alert Rule: {rule.get('name', rule_id)}",
            sections,
            data_for_json=rule,
        )
    except KctlError as e:
        out.error(f"Failed to show alert: {e}")
        raise typer.Exit(1) from e


@app.command("create")
def create(
    ctx: typer.Context,
    project: Annotated[str, typer.Option("--project", "-p", help="Project slug")],
    name: Annotated[str, typer.Option("--name", "-n", help="Alert rule name")],
    metric: Annotated[str, typer.Option("--metric", help="Metric: events, users")] = "events",
    threshold: Annotated[int, typer.Option("--threshold", help="Threshold value")] = 100,
    time_window: Annotated[int, typer.Option("--time-window", help="Time window in minutes")] = 60,
) -> None:
    """Create a new metric alert rule."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        # Map metric to Sentry's aggregate format
        aggregate_map = {
            "events": "count()",
            "users": "count_unique(user)",
        }
        aggregate = aggregate_map.get(metric, "count()")

        payload = {
            "name": name,
            "aggregate": aggregate,
            "timeWindow": time_window,
            "dataset": "events",
            "query": "",
            "thresholdType": 0,  # Above threshold
            "resolveThreshold": None,
            "triggers": [
                {
                    "label": "critical",
                    "alertThreshold": threshold,
                    "actions": [],
                }
            ],
            "projects": [project],
            "owner": None,
        }

        result = c.client.org_post("/alert-rules/", json=payload)
        if not isinstance(result, dict):
            result = {}

        if out.json_mode:
            out.raw_json(result)
        else:
            out.success(f"Alert rule created: {result.get('name', name)}")
            out.kv("ID", str(result.get("id", "")))
            out.kv("Metric", aggregate)
            out.kv("Threshold", str(threshold))
    except KctlError as e:
        out.error(f"Failed to create alert: {e}")
        raise typer.Exit(1) from e
