"""Cloudflare Workers management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_cf.core.callbacks import AppContext
from kctl_cf.core.utils import require_account, resolve_zone

app = typer.Typer(help="Manage Cloudflare Workers, routes, and KV.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all Workers scripts."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    scripts = c.client.get(f"/accounts/{acct}/workers/scripts")
    if not isinstance(scripts, list):
        scripts = []
    rows = []
    for s in scripts:
        rows.append(
            [
                s.get("id", ""),
                s.get("etag", "")[:12],
                s.get("modified_on", "")[:19],
                str(len(s.get("handlers", []))),
            ]
        )
    c.output.table(
        "Workers Scripts",
        [("Name", "cyan"), ("ETag", "dim"), ("Modified", ""), ("Handlers", "dim")],
        rows,
        data_for_json=scripts,
    )


@app.command()
def routes(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """List Workers routes for a zone."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    route_list = c.client.get(f"/zones/{zone_id}/workers/routes")
    if not isinstance(route_list, list):
        route_list = []
    rows = []
    for r in route_list:
        rows.append(
            [
                r.get("id", "")[:12],
                r.get("pattern", ""),
                r.get("script", "") or "(none)",
            ]
        )
    c.output.table(
        f"Workers Routes — {zone}",
        [("ID", "dim"), ("Pattern", "cyan"), ("Script", "green")],
        rows,
        data_for_json=route_list,
    )


@app.command()
def kv(ctx: typer.Context) -> None:
    """List Workers KV namespaces."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    namespaces = c.client.get(f"/accounts/{acct}/storage/kv/namespaces")
    if not isinstance(namespaces, list):
        namespaces = []
    rows = []
    for ns in namespaces:
        rows.append(
            [
                ns.get("title", ""),
                ns.get("id", "")[:12],
                str(ns.get("supports_url_encoding", "")),
            ]
        )
    c.output.table(
        "KV Namespaces",
        [("Title", "cyan"), ("ID", "dim"), ("URL Encoding", "")],
        rows,
        data_for_json=namespaces,
    )


@app.command()
def deploy(
    ctx: typer.Context,
    script_name: Annotated[str, typer.Argument(help="Worker script name")],
    file: Annotated[str, typer.Option("--file", "-f", help="Path to JavaScript/TypeScript worker file")],
) -> None:
    """Deploy a Worker script."""
    import pathlib

    c: AppContext = ctx.obj
    acct = require_account(c)
    script_path = pathlib.Path(file)
    if not script_path.exists():
        c.output.error(f"File not found: {file}")
        raise typer.Exit(1)
    content = script_path.read_text()
    # Upload worker script via raw request with JavaScript content type
    c.client.request(
        "PUT",
        f"/accounts/{acct}/workers/scripts/{script_name}",
        content=content,
        headers={"Content-Type": "application/javascript"},
    )
    c.output.success(f"Worker deployed: {script_name}")


@app.command("delete")
def delete_(
    ctx: typer.Context,
    script_name: Annotated[str, typer.Argument(help="Worker script name")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
) -> None:
    """Delete a Worker script. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    acct = require_account(c)
    c.client.delete(f"/accounts/{acct}/workers/scripts/{script_name}")
    c.output.success(f"Worker deleted: {script_name}")


@app.command()
def env(
    ctx: typer.Context,
    script_name: Annotated[str, typer.Argument(help="Worker script name")],
) -> None:
    """Show environment bindings for a Worker script."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    result = c.client.get(f"/accounts/{acct}/workers/scripts/{script_name}/settings")
    if not isinstance(result, dict):
        result = {}
    bindings = result.get("bindings", [])
    if not isinstance(bindings, list):
        bindings = []
    rows = []
    for b in bindings:
        rows.append(
            [
                b.get("name", ""),
                b.get("type", ""),
                b.get("text", "") or b.get("namespace_id", "") or b.get("bucket_name", "") or "",
            ]
        )
    c.output.table(
        f"Worker Bindings — {script_name}",
        [("Name", "cyan"), ("Type", "green"), ("Value", "")],
        rows,
        data_for_json=bindings,
    )


@app.command("set-env")
def set_env(
    ctx: typer.Context,
    script_name: Annotated[str, typer.Argument(help="Worker script name")],
    key: Annotated[str, typer.Option("--key", help="Environment variable name")],
    value: Annotated[str, typer.Option("--value", help="Environment variable value")],
) -> None:
    """Set an environment variable (plain text binding) for a Worker."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    # Fetch current settings, then patch bindings
    result = c.client.get(f"/accounts/{acct}/workers/scripts/{script_name}/settings")
    if not isinstance(result, dict):
        result = {}
    bindings = result.get("bindings", [])
    if not isinstance(bindings, list):
        bindings = []
    # Update or add the binding
    found = False
    for b in bindings:
        if b.get("name") == key and b.get("type") == "plain_text":
            b["text"] = value
            found = True
            break
    if not found:
        bindings.append({"name": key, "type": "plain_text", "text": value})
    c.client.patch(
        f"/accounts/{acct}/workers/scripts/{script_name}/settings",
        json={"bindings": bindings},
    )
    c.output.success(f"Environment variable set: {key} on {script_name}")


@app.command()
def tail(
    ctx: typer.Context,
    script_name: Annotated[str, typer.Argument(help="Worker script name")],
) -> None:
    """Start a tail session for a Worker (shows recent events)."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    result = c.client.post(f"/accounts/{acct}/workers/scripts/{script_name}/tails", json={})
    if not isinstance(result, dict):
        result = {}
    tail_id = result.get("id", "")
    url = result.get("url", "")
    data = {"script": script_name, "tail_id": tail_id, "url": url}
    sections = [
        (
            "Tail Session",
            [
                ("Script", script_name),
                ("Tail ID", tail_id),
                ("WebSocket URL", url),
            ],
        )
    ]
    c.output.detail(f"Tail — {script_name}", sections, data_for_json=data)
    if url and not c.output.json_mode:
        c.output.info(f"Connect with: websocat '{url}'")


@app.command()
def subdomain(ctx: typer.Context) -> None:
    """Show Workers subdomain for the account."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    result = c.client.get(f"/accounts/{acct}/workers/subdomain")
    if not isinstance(result, dict):
        result = {}
    name = result.get("subdomain", "")
    data = {"subdomain": name}
    sections = [
        (
            "Workers Subdomain",
            [
                ("Subdomain", f"{name}.workers.dev" if name else "(not set)"),
            ],
        )
    ]
    c.output.detail("Workers Subdomain", sections, data_for_json=data)


@app.command("set-subdomain")
def set_subdomain(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="Subdomain name (without .workers.dev)")],
) -> None:
    """Set Workers subdomain for the account."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    c.client.put(f"/accounts/{acct}/workers/subdomain", json={"subdomain": name})
    c.output.success(f"Workers subdomain set: {name}.workers.dev")


@app.command("create-kv")
def create_kv(
    ctx: typer.Context,
    title: Annotated[str, typer.Option("--title", help="KV namespace title")],
) -> None:
    """Create a Workers KV namespace."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    result = c.client.post(f"/accounts/{acct}/storage/kv/namespaces", json={"title": title})
    ns_id = result.get("id", "") if isinstance(result, dict) else ""
    c.output.success(f"KV namespace created: {ns_id}")


@app.command("delete-kv")
def delete_kv(
    ctx: typer.Context,
    namespace_id: Annotated[str, typer.Argument(help="KV namespace ID")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
) -> None:
    """Delete a Workers KV namespace. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    acct = require_account(c)
    c.client.delete(f"/accounts/{acct}/storage/kv/namespaces/{namespace_id}")
    c.output.success(f"KV namespace deleted: {namespace_id}")


@app.command("create-route")
def create_route(
    ctx: typer.Context,
    pattern: Annotated[str, typer.Option("--pattern", help="Route pattern (e.g., *.example.com/*)")],
    script: Annotated[str, typer.Option("--script", help="Worker script name to bind")],
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Create a Workers route for a zone."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    payload = {"pattern": pattern, "script": script}
    result = c.client.post(f"/zones/{zone_id}/workers/routes", json=payload)
    route_id = result.get("id", "") if isinstance(result, dict) else ""
    c.output.success(f"Worker route created: {route_id}")


@app.command("delete-route")
def delete_route(
    ctx: typer.Context,
    route_id: Annotated[str, typer.Argument(help="Route ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Delete a Workers route. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    c.client.delete(f"/zones/{zone_id}/workers/routes/{route_id}")
    c.output.success(f"Worker route deleted: {route_id}")


@app.command("cron-triggers")
def cron_triggers(
    ctx: typer.Context,
    script_name: Annotated[str, typer.Argument(help="Worker script name")],
) -> None:
    """List cron triggers for a Worker script."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    result = c.client.get(f"/accounts/{acct}/workers/scripts/{script_name}/schedules")
    schedules = result.get("schedules", []) if isinstance(result, dict) else result if isinstance(result, list) else []
    rows = []
    for s in schedules:
        rows.append(
            [
                s.get("cron", ""),
                s.get("created_on", "")[:19],
                s.get("modified_on", "")[:19],
            ]
        )
    c.output.table(
        f"Cron Triggers — {script_name}",
        [("Cron Expression", "cyan"), ("Created", "dim"), ("Modified", "dim")],
        rows,
        data_for_json=schedules,
    )


@app.command("set-cron-triggers")
def set_cron_triggers(
    ctx: typer.Context,
    script_name: Annotated[str, typer.Argument(help="Worker script name")],
    crons: Annotated[list[str], typer.Option("--cron", help="Cron expressions (repeat for multiple)")],
) -> None:
    """Set cron triggers for a Worker script (replaces all existing)."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    payload = [{"cron": cron} for cron in crons]
    c.client.put(f"/accounts/{acct}/workers/scripts/{script_name}/schedules", json=payload)
    c.output.success(f"Cron triggers set for {script_name}: {', '.join(crons)}")


@app.command("delete-cron-triggers")
def delete_cron_triggers(
    ctx: typer.Context,
    script_name: Annotated[str, typer.Argument(help="Worker script name")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
) -> None:
    """Delete all cron triggers for a Worker script. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    acct = require_account(c)
    c.client.put(f"/accounts/{acct}/workers/scripts/{script_name}/schedules", json=[])
    c.output.success(f"All cron triggers deleted for {script_name}")
