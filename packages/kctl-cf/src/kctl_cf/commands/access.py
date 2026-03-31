"""Zero Trust Access management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_cloudflare.core.callbacks import AppContext
from kctl_cloudflare.core.utils import require_account

app = typer.Typer(help="Manage Cloudflare Zero Trust Access.")


def _parse_access_rules(c: AppContext, rules: list[str] | None) -> list[dict]:
    """Parse access rules from CLI format (email:user@x.com, email_domain:x.com, everyone:)."""
    if not rules:
        return []
    parsed = []
    for rule in rules:
        if ":" not in rule:
            c.output.error(
                f"Invalid rule format: {rule!r} (expected type:value, e.g. 'email:user@x.com' or 'everyone:')"
            )
            raise typer.Exit(1)
        rule_type, rule_value = rule.split(":", 1)
        if rule_type == "email":
            parsed.append({"email": {"email": rule_value}})
        elif rule_type == "email_domain":
            parsed.append({"email_domain": {"domain": rule_value}})
        elif rule_type == "everyone":
            parsed.append({"everyone": {}})
        else:
            parsed.append({rule_type: {"value": rule_value}})
    return parsed


@app.command()
def apps(ctx: typer.Context) -> None:
    """List Access applications."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    result = c.client.get(f"/accounts/{acct}/access/apps")
    if not isinstance(result, list):
        result = []
    rows = []
    for a in result:
        rows.append(
            [
                a.get("id", "")[:12],
                a.get("name", ""),
                a.get("domain", ""),
                a.get("type", ""),
                a.get("session_duration", ""),
                a.get("created_at", "")[:19],
            ]
        )
    c.output.table(
        "Access Applications",
        [("ID", "dim"), ("Name", "cyan"), ("Domain", "green"), ("Type", ""), ("Session", "dim"), ("Created", "dim")],
        rows,
        data_for_json=result,
    )


@app.command("get-app")
def get_app(
    ctx: typer.Context,
    app_id: Annotated[str, typer.Argument(help="Application ID")],
) -> None:
    """Get details for an Access application."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    result = c.client.get(f"/accounts/{acct}/access/apps/{app_id}")
    if not isinstance(result, dict):
        result = {}
    policies_count = len(result.get("policies", [])) if isinstance(result.get("policies"), list) else 0
    sections = [
        (
            "Application",
            [
                ("ID", result.get("id", "")),
                ("Name", result.get("name", "")),
                ("Domain", result.get("domain", "")),
                ("Type", result.get("type", "")),
                ("AUD", result.get("aud", "")[:40]),
                ("Session Duration", result.get("session_duration", "")),
                ("Auto-Redirect to IdP", str(result.get("auto_redirect_to_identity", False))),
            ],
        ),
        (
            "Settings",
            [
                ("Policies", str(policies_count)),
                ("App Launcher Visible", str(result.get("app_launcher_visible", True))),
                ("Skip Interstitial", str(result.get("skip_interstitial", False))),
                ("Created", result.get("created_at", "")[:19]),
                ("Updated", result.get("updated_at", "")[:19]),
            ],
        ),
    ]
    c.output.detail(f"Access App — {result.get('name', app_id)}", sections, data_for_json=result)


@app.command()
def policies(
    ctx: typer.Context,
    app_id: Annotated[str, typer.Argument(help="Application ID")],
) -> None:
    """List policies for an Access application."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    result = c.client.get(f"/accounts/{acct}/access/apps/{app_id}/policies")
    if not isinstance(result, list):
        result = []
    rows = []
    for p in result:
        include = p.get("include", [])
        include_str = ", ".join(str(i.get("email", {}).get("email", "") or i) for i in include[:3]) if include else ""
        rows.append(
            [
                p.get("id", "")[:12],
                p.get("name", ""),
                p.get("decision", ""),
                str(p.get("precedence", "")),
                include_str[:40],
            ]
        )
    c.output.table(
        f"Access Policies — {app_id[:12]}",
        [("ID", "dim"), ("Name", "cyan"), ("Decision", "green"), ("Precedence", "dim"), ("Include", "")],
        rows,
        data_for_json=result,
    )


@app.command()
def groups(ctx: typer.Context) -> None:
    """List Access groups."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    result = c.client.get(f"/accounts/{acct}/access/groups")
    if not isinstance(result, list):
        result = []
    rows = []
    for g in result:
        include = g.get("include", [])
        include_count = len(include) if isinstance(include, list) else 0
        rows.append(
            [
                g.get("id", "")[:12],
                g.get("name", ""),
                str(include_count),
                g.get("created_at", "")[:19],
                g.get("updated_at", "")[:19],
            ]
        )
    c.output.table(
        "Access Groups",
        [("ID", "dim"), ("Name", "cyan"), ("Include Rules", "green"), ("Created", "dim"), ("Updated", "dim")],
        rows,
        data_for_json=result,
    )


@app.command("create-group")
def create_group(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="Group name")],
    include: Annotated[
        list[str] | None,
        typer.Option("--include", help="Include rules (email:user@example.com or email_domain:example.com)"),
    ] = None,
    require: Annotated[
        list[str] | None, typer.Option("--require", help="Require rules (same format as include)")
    ] = None,
) -> None:
    """Create an Access group."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    payload: dict = {
        "name": name,
        "include": _parse_access_rules(c, include),
    }
    if require:
        payload["require"] = _parse_access_rules(c, require)

    result = c.client.post(f"/accounts/{acct}/access/groups", json=payload)
    group_id = result.get("id", "") if isinstance(result, dict) else ""
    c.output.success(f"Access group created: {group_id}")


@app.command("delete-group")
def delete_group(
    ctx: typer.Context,
    group_id: Annotated[str, typer.Argument(help="Access group ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
) -> None:
    """Delete an Access group. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    acct = require_account(c)
    c.client.delete(f"/accounts/{acct}/access/groups/{group_id}")
    c.output.success(f"Access group deleted: {group_id}")


@app.command("create-app")
def create_app(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="Application name")],
    domain: Annotated[str, typer.Option("--domain", help="Application domain")],
    app_type: Annotated[
        str, typer.Option("--type", help="Application type (self_hosted, ssh, vnc, bookmark)")
    ] = "self_hosted",
    session_duration: Annotated[str, typer.Option("--session-duration", help="Session duration (e.g. 24h)")] = "24h",
) -> None:
    """Create an Access application."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    payload = {
        "name": name,
        "domain": domain,
        "type": app_type,
        "session_duration": session_duration,
    }
    result = c.client.post(f"/accounts/{acct}/access/apps", json=payload)
    app_id = result.get("id", "") if isinstance(result, dict) else ""
    c.output.success(f"Access application created: {app_id}")


@app.command("update-app")
def update_app(
    ctx: typer.Context,
    app_id: Annotated[str, typer.Argument(help="Application ID")],
    name: Annotated[str | None, typer.Option("--name", help="New name")] = None,
    domain: Annotated[str | None, typer.Option("--domain", help="New domain")] = None,
    session_duration: Annotated[str | None, typer.Option("--session-duration", help="Session duration")] = None,
) -> None:
    """Update an Access application (merges with existing settings)."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    if not any([name, domain, session_duration]):
        c.output.warn("No fields to update")
        return
    existing = c.client.get(f"/accounts/{acct}/access/apps/{app_id}")
    if not isinstance(existing, dict):
        existing = {}
    payload: dict = {
        "name": name or existing.get("name", ""),
        "domain": domain or existing.get("domain", ""),
        "type": existing.get("type", "self_hosted"),
        "session_duration": session_duration or existing.get("session_duration", "24h"),
    }
    c.client.put(f"/accounts/{acct}/access/apps/{app_id}", json=payload)
    c.output.success(f"Access application updated: {app_id}")


@app.command("delete-app")
def delete_app(
    ctx: typer.Context,
    app_id: Annotated[str, typer.Argument(help="Application ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
) -> None:
    """Delete an Access application. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    acct = require_account(c)
    c.client.delete(f"/accounts/{acct}/access/apps/{app_id}")
    c.output.success(f"Access application deleted: {app_id}")


@app.command("create-policy")
def create_policy(
    ctx: typer.Context,
    app_id: Annotated[str, typer.Argument(help="Application ID")],
    name: Annotated[str, typer.Option("--name", help="Policy name")],
    decision: Annotated[str, typer.Option("--decision", help="Decision (allow, deny, non_identity, bypass)")] = "allow",
    include: Annotated[
        list[str] | None,
        typer.Option("--include", help="Include rules (email:user@x.com or email_domain:x.com)"),
    ] = None,
) -> None:
    """Create a policy for an Access application."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    include_rules = _parse_access_rules(c, include)
    payload = {"name": name, "decision": decision, "include": include_rules}
    result = c.client.post(f"/accounts/{acct}/access/apps/{app_id}/policies", json=payload)
    policy_id = result.get("id", "") if isinstance(result, dict) else ""
    c.output.success(f"Access policy created: {policy_id}")


@app.command("update-policy")
def update_policy(
    ctx: typer.Context,
    app_id: Annotated[str, typer.Argument(help="Application ID")],
    policy_id: Annotated[str, typer.Argument(help="Policy ID")],
    name: Annotated[str | None, typer.Option("--name", help="New policy name")] = None,
    decision: Annotated[str | None, typer.Option("--decision", help="New decision")] = None,
) -> None:
    """Update a policy for an Access application (merges with existing)."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    if not any([name, decision]):
        c.output.warn("No fields to update")
        return
    existing = c.client.get(f"/accounts/{acct}/access/apps/{app_id}/policies/{policy_id}")
    if not isinstance(existing, dict):
        existing = {}
    payload: dict = {
        "name": name or existing.get("name", ""),
        "decision": decision or existing.get("decision", "allow"),
        "include": existing.get("include", []),
    }
    c.client.put(f"/accounts/{acct}/access/apps/{app_id}/policies/{policy_id}", json=payload)
    c.output.success(f"Access policy updated: {policy_id}")


@app.command("delete-policy")
def delete_policy(
    ctx: typer.Context,
    app_id: Annotated[str, typer.Argument(help="Application ID")],
    policy_id: Annotated[str, typer.Argument(help="Policy ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
) -> None:
    """Delete a policy for an Access application. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    acct = require_account(c)
    c.client.delete(f"/accounts/{acct}/access/apps/{app_id}/policies/{policy_id}")
    c.output.success(f"Access policy deleted: {policy_id}")


@app.command()
def idps(ctx: typer.Context) -> None:
    """List Access identity providers."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    result = c.client.get(f"/accounts/{acct}/access/identity_providers")
    if not isinstance(result, list):
        result = []
    rows = []
    for idp in result:
        rows.append(
            [
                idp.get("id", "")[:12],
                idp.get("name", ""),
                idp.get("type", ""),
                idp.get("created_at", "")[:19],
            ]
        )
    c.output.table(
        "Identity Providers",
        [("ID", "dim"), ("Name", "cyan"), ("Type", "green"), ("Created", "dim")],
        rows,
        data_for_json=result,
    )


@app.command("service-tokens")
def service_tokens(ctx: typer.Context) -> None:
    """List Access service tokens."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    result = c.client.get(f"/accounts/{acct}/access/service_tokens")
    if not isinstance(result, list):
        result = []
    rows = []
    for t in result:
        rows.append(
            [
                t.get("id", "")[:12],
                t.get("name", ""),
                t.get("client_id", "")[:20],
                t.get("expires_at", "")[:19] if t.get("expires_at") else "never",
                t.get("created_at", "")[:19],
            ]
        )
    c.output.table(
        "Service Tokens",
        [("ID", "dim"), ("Name", "cyan"), ("Client ID", ""), ("Expires", "green"), ("Created", "dim")],
        rows,
        data_for_json=result,
    )


@app.command("create-service-token")
def create_service_token(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="Service token name")],
    duration: Annotated[str, typer.Option("--duration", help="Token duration (e.g. 8760h for 1 year)")] = "8760h",
) -> None:
    """Create an Access service token."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    payload = {"name": name, "duration": duration}
    result = c.client.post(f"/accounts/{acct}/access/service_tokens", json=payload)
    if not isinstance(result, dict):
        result = {}
    if c.output.json_mode:
        c.output.raw_json(result)
    else:
        c.output.success(f"Service token created: {result.get('id', '')}")
        c.output.kv("Client ID", result.get("client_id", ""))
        c.output.warn("Client Secret (save this — shown only once):")
        c.output.text(result.get("client_secret", ""))


@app.command("rotate-service-token")
def rotate_service_token(
    ctx: typer.Context,
    token_id: Annotated[str, typer.Argument(help="Service token ID")],
) -> None:
    """Rotate an Access service token (generates new secret)."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    result = c.client.post(f"/accounts/{acct}/access/service_tokens/{token_id}/rotate")
    if not isinstance(result, dict):
        result = {}
    if c.output.json_mode:
        c.output.raw_json(result)
    else:
        c.output.success(f"Service token rotated: {token_id}")
        c.output.warn("New Client Secret (save this — shown only once):")
        c.output.text(result.get("client_secret", ""))


@app.command("delete-service-token")
def delete_service_token(
    ctx: typer.Context,
    token_id: Annotated[str, typer.Argument(help="Service token ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
) -> None:
    """Delete an Access service token. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    acct = require_account(c)
    c.client.delete(f"/accounts/{acct}/access/service_tokens/{token_id}")
    c.output.success(f"Service token deleted: {token_id}")
