"""Server actions and automated rules."""

from __future__ import annotations

import contextlib
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Server actions and automated rules.")


def _m2o_name(val):
    if isinstance(val, list):
        return str(val[1])
    return str(val or "-")


@app.command("actions")
def actions(
    ctx: typer.Context,
    model: Annotated[str | None, typer.Option("--model", "-m", help="Filter by model name (e.g. sale.order)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum records to list")] = 50,
) -> None:
    """List ir.actions.server records.

    Shows server actions with name, model, state, binding type and usage.

    Examples:
        kctl-odoo automation actions
        kctl-odoo automation actions --model sale.order
        kctl-odoo automation actions --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = []
    if model:
        domain.append(("model_id.model", "=", model))

    try:
        server_actions = c.search_read(
            "ir.actions.server",
            domain=domain,
            fields=["name", "model_id", "state", "binding_type", "usage", "type"],
            limit=limit,
            order="name",
        )
    except RPCError as e:
        out.error(f"Failed to read server actions: {e}")
        raise typer.Exit(1) from e

    if not server_actions:
        out.info(f"No server actions found{' for model ' + model if model else ''}.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    for sa in server_actions:
        rows.append(
            [
                str(sa.get("id", "")),
                sa.get("name", "")[:50],
                _m2o_name(sa.get("model_id")),
                sa.get("state", "") or "",
                sa.get("binding_type", "") or "",
                sa.get("usage", "") or "",
            ]
        )

    out.table(
        f"Server Actions ({len(server_actions)} found)",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("Model", ""),
            ("State", ""),
            ("Binding", "dim"),
            ("Usage", "dim"),
        ],
        rows,
        data_for_json=server_actions,
    )

    if actx.json_mode:
        out.raw_json(server_actions)


@app.command("rules")
def rules(
    ctx: typer.Context,
    model: Annotated[str | None, typer.Option("--model", "-m", help="Filter by model name (e.g. sale.order)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum records to list")] = 50,
) -> None:
    """List base.automation records (automated rules).

    Shows automation rules with name, model, trigger, active status and last run date.

    Examples:
        kctl-odoo automation rules
        kctl-odoo automation rules --model sale.order
        kctl-odoo automation rules --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = []
    if model:
        domain.append(("model_id.model", "=", model))

    try:
        automation_rules = c.search_read(
            "base.automation",
            domain=domain,
            fields=["name", "model_id", "trigger", "active", "last_run"],
            limit=limit,
            order="name",
        )
    except RPCError as e:
        out.error(f"Failed to read automation rules: {e}")
        raise typer.Exit(1) from e

    if not automation_rules:
        out.info(f"No automation rules found{' for model ' + model if model else ''}.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    for rule in automation_rules:
        active = rule.get("active", False)
        active_display = "[green]Yes[/green]" if active else "[red]No[/red]"
        last_run = rule.get("last_run") or "-"
        if last_run != "-":
            last_run = str(last_run)[:16]
        rows.append(
            [
                str(rule.get("id", "")),
                rule.get("name", "")[:50],
                _m2o_name(rule.get("model_id")),
                rule.get("trigger", "") or "",
                active_display,
                str(last_run),
            ]
        )

    out.table(
        f"Automation Rules ({len(automation_rules)} found)",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("Model", ""),
            ("Trigger", ""),
            ("Active", ""),
            ("Last Run", "dim"),
        ],
        rows,
        data_for_json=automation_rules,
    )

    if actx.json_mode:
        out.raw_json(automation_rules)


@app.command("enable")
def enable(
    ctx: typer.Context,
    rule_id: Annotated[int, typer.Argument(help="ID of the automation rule to enable")],
) -> None:
    """Enable an automation rule (set active=True).

    Examples:
        kctl-odoo automation enable 42
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        rules_found = c.search_read(
            "base.automation",
            domain=[("id", "=", rule_id)],
            fields=["id", "name", "active"],
            limit=1,
        )
    except RPCError as e:
        out.error(f"Failed to read automation rule {rule_id}: {e}")
        raise typer.Exit(1) from e

    if not rules_found:
        out.error(f"Automation rule #{rule_id} not found.")
        raise typer.Exit(1)

    rule = rules_found[0]
    if rule.get("active"):
        out.info(f"Rule '{rule['name']}' (#{rule_id}) is already active.")
        return

    try:
        c.execute_kw("base.automation", "write", [[rule_id], {"active": True}])
        out.success(f"Enabled automation rule: '{rule['name']}' (#{rule_id})")
    except RPCError as e:
        out.error(f"Failed to enable rule #{rule_id}: {e}")
        raise typer.Exit(1) from e

    if actx.json_mode:
        out.raw_json({"id": rule_id, "name": rule["name"], "active": True})


@app.command("disable")
def disable(
    ctx: typer.Context,
    rule_id: Annotated[int, typer.Argument(help="ID of the automation rule to disable")],
) -> None:
    """Disable an automation rule (set active=False).

    Examples:
        kctl-odoo automation disable 42
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        rules_found = c.search_read(
            "base.automation",
            domain=[("id", "=", rule_id)],
            fields=["id", "name", "active"],
            limit=1,
        )
    except RPCError as e:
        out.error(f"Failed to read automation rule {rule_id}: {e}")
        raise typer.Exit(1) from e

    if not rules_found:
        out.error(f"Automation rule #{rule_id} not found.")
        raise typer.Exit(1)

    rule = rules_found[0]
    if not rule.get("active"):
        out.info(f"Rule '{rule['name']}' (#{rule_id}) is already inactive.")
        return

    try:
        c.execute_kw("base.automation", "write", [[rule_id], {"active": False}])
        out.success(f"Disabled automation rule: '{rule['name']}' (#{rule_id})")
    except RPCError as e:
        out.error(f"Failed to disable rule #{rule_id}: {e}")
        raise typer.Exit(1) from e

    if actx.json_mode:
        out.raw_json({"id": rule_id, "name": rule["name"], "active": False})


@app.command("run")
def run(
    ctx: typer.Context,
    action_id: Annotated[int, typer.Argument(help="ID of the ir.actions.server to execute")],
    record_ids: Annotated[
        str | None, typer.Option("--record-ids", help="Comma-separated record IDs to run against")
    ] = None,
) -> None:
    """Execute an ir.actions.server action.

    Runs the server action. If --record-ids is provided, the action is called
    in the context of those specific records.

    Examples:
        kctl-odoo automation run 42
        kctl-odoo automation run 42 --record-ids 1,2,3
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Verify the action exists
    try:
        actions_found = c.search_read(
            "ir.actions.server",
            domain=[("id", "=", action_id)],
            fields=["id", "name", "model_id", "state"],
            limit=1,
        )
    except RPCError as e:
        out.error(f"Failed to read server action {action_id}: {e}")
        raise typer.Exit(1) from e

    if not actions_found:
        out.error(f"Server action #{action_id} not found.")
        raise typer.Exit(1)

    action = actions_found[0]
    out.info(f"Running action: '{action['name']}' (#{action_id})")

    # Parse record IDs
    ids_to_run: list[int] = []
    if record_ids:
        try:
            ids_to_run = [int(x.strip()) for x in record_ids.split(",") if x.strip()]
        except ValueError:
            out.error(f"Invalid record IDs: '{record_ids}'. Must be comma-separated integers.")
            raise typer.Exit(1) from None

    try:
        if ids_to_run:
            c.execute_kw("ir.actions.server", "run", [[action_id]], {"context": {"active_ids": ids_to_run}})
        else:
            c.execute_kw("ir.actions.server", "run", [[action_id]])
        out.success(f"Action '{action['name']}' executed successfully.")
    except RPCError as e:
        out.error(f"Failed to run action #{action_id}: {e}")
        raise typer.Exit(1) from e
    except Exception as e:
        out.error(f"Unexpected error running action #{action_id}: {e}")
        raise typer.Exit(1) from e

    if actx.json_mode:
        out.raw_json(
            {
                "id": action_id,
                "name": action["name"],
                "record_ids": ids_to_run or "all",
                "executed": True,
            }
        )


@app.command("history")
def history(
    ctx: typer.Context,
    rule_id: Annotated[int, typer.Argument(help="ID of the base.automation rule")],
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum log entries to show")] = 20,
) -> None:
    """Show execution history for an automation rule.

    Searches ir.logging and mail.message for related entries.

    Examples:
        kctl-odoo automation history 42
        kctl-odoo automation history 42 --limit 10
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Verify rule exists
    try:
        rules_found = c.search_read(
            "base.automation",
            domain=[("id", "=", rule_id)],
            fields=["id", "name", "model_id", "last_run"],
            limit=1,
        )
    except RPCError as e:
        out.error(f"Failed to read automation rule {rule_id}: {e}")
        raise typer.Exit(1) from e

    if not rules_found:
        out.error(f"Automation rule #{rule_id} not found.")
        raise typer.Exit(1)

    rule = rules_found[0]
    model_name = _m2o_name(rule.get("model_id"))
    out.info(f"Rule: '{rule['name']}' | Model: {model_name} | Last run: {rule.get('last_run') or 'never'}")

    # Try ir.logging first
    log_entries: list = []
    with contextlib.suppress(RPCError, Exception):
        log_entries = c.search_read(
            "ir.logging",
            domain=[("func", "ilike", str(rule_id))],
            fields=["create_date", "level", "message", "func", "name"],
            limit=limit,
            order="id desc",
        )

    if log_entries:
        rows = []
        for entry in log_entries:
            rows.append(
                [
                    str(entry.get("create_date", ""))[:16],
                    entry.get("level", "") or "",
                    entry.get("name", "") or "",
                    (entry.get("message", "") or "")[:80],
                ]
            )

        out.table(
            f"Execution Logs (ir.logging) for Rule #{rule_id}",
            [("Date", "dim"), ("Level", ""), ("Logger", ""), ("Message", "cyan")],
            rows,
            data_for_json=log_entries,
        )

        if actx.json_mode:
            out.raw_json(log_entries)
        return

    # Fallback: mail.message chatter for the rule record
    try:
        messages = c.search_read(
            "mail.message",
            domain=[
                ("res_id", "=", rule_id),
                ("model", "=", "base.automation"),
            ],
            fields=["date", "message_type", "subtype_id", "body", "author_id"],
            limit=limit,
            order="id desc",
        )
    except (RPCError, Exception):
        messages = []

    if messages:
        rows = []
        for msg in messages:
            author = _m2o_name(msg.get("author_id"))
            body = (msg.get("body") or "").replace("<p>", "").replace("</p>", "").strip()[:80]
            rows.append(
                [
                    str(msg.get("date", ""))[:16],
                    msg.get("message_type", "") or "",
                    author,
                    body,
                ]
            )

        out.table(
            f"Chatter Messages for Rule #{rule_id}",
            [("Date", "dim"), ("Type", ""), ("Author", ""), ("Message", "cyan")],
            rows,
            data_for_json=messages,
        )

        if actx.json_mode:
            out.raw_json(messages)
        return

    out.info(f"No execution history found for automation rule #{rule_id}.")
    if actx.json_mode:
        out.raw_json([])
