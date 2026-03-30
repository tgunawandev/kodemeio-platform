"""Bulk operations across multiple services."""

from __future__ import annotations

import contextlib
from typing import Annotated

import typer
from rich.status import Status

from kctl_dokploy.core.callbacks import AppContext
from kctl_dokploy.core.resolve import resolve_project

app = typer.Typer(help="Bulk operations across multiple services.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_project_compose_services(c: AppContext, project_name_or_id: str) -> list[dict]:
    """Resolve a project and return its compose services with project metadata."""
    project_id = resolve_project(c.client, project_name_or_id)
    projects = c.client.get("/project.all")
    if not isinstance(projects, list):
        return []
    for p in projects:
        if p.get("projectId") == project_id:
            services = p.get("compose", [])
            for s in services:
                s["_projectName"] = p.get("name", "")
            return services
    return []


def _filter_services(
    services: list[dict],
    exclude: str | None,
    include: str | None = None,
) -> tuple[list[dict], list[dict]]:
    """Split services into (active, skipped) based on include/exclude filters."""
    exclude_names = {n.strip().lower() for n in exclude.split(",")} if exclude else set()
    include_names = {n.strip().lower() for n in include.split(",")} if include else set()

    active: list[dict] = []
    skipped: list[dict] = []
    for s in services:
        name = s.get("name", "").lower()
        if (exclude_names and name in exclude_names) or (include_names and name not in include_names):
            skipped.append(s)
        else:
            active.append(s)
    return active, skipped


def _fetch_env(c: AppContext, compose_id: str) -> str:
    """Fetch the current env string for a compose service."""
    data = c.client.get("/compose.one", params={"composeId": compose_id})
    if isinstance(data, dict):
        return data.get("env", "")
    return ""


def _update_env_key(env_str: str, key: str, value: str) -> str:
    """Update or add a key=value pair in an env string."""
    new_lines: list[str] = []
    found = False
    for line in env_str.splitlines():
        stripped = line.strip()
        if stripped and "=" in stripped:
            existing_key = stripped.split("=", 1)[0].strip()
            if existing_key == key:
                new_lines.append(f"{key}={value}")
                found = True
                continue
        new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}")
    return "\n".join(new_lines)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("deploy-all")
def deploy_all(
    ctx: typer.Context,
    project: Annotated[str, typer.Option("--project", "-p", help="Project name or ID")],
    exclude: Annotated[
        str | None, typer.Option("--exclude", "-e", help="Comma-separated service names to skip")
    ] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation prompt")] = False,
) -> None:
    """Deploy all compose services in a project."""
    c: AppContext = ctx.obj
    services = _get_project_compose_services(c, project)
    if not services:
        c.output.error(f"No compose services found in project '{project}'")
        raise typer.Exit(1)

    active, skipped = _filter_services(services, exclude)
    if not active:
        c.output.warn("All services excluded; nothing to deploy")
        return

    if not force:
        names = ", ".join(s.get("name", "?") for s in active)
        typer.confirm(f"Deploy {len(active)} service(s): {names}?", abort=True)

    results: list[list[str]] = []

    for s in skipped:
        results.append([s.get("name", "?"), "[yellow]skipped[/yellow]", "-"])

    with Status("[bold blue]Deploying services...", console=c.output._console) as spinner:
        for s in active:
            name = s.get("name", "?")
            cid = s.get("composeId", "")
            spinner.update(f"[bold blue]Deploying {name}...")
            try:
                c.client.post("/compose.deploy", json={"composeId": cid})
                results.append([name, "[green]success[/green]", cid[:12]])
            except Exception as exc:
                results.append([name, "[red]failed[/red]", str(exc)[:50]])

    success = sum(1 for r in results if "success" in r[1])
    failed = sum(1 for r in results if "failed" in r[1])

    c.output.table(
        f"Bulk Deploy Results ({success} ok, {failed} failed, {len(skipped)} skipped)",
        [("Service", "cyan"), ("Status", ""), ("Detail", "dim")],
        results,
        data_for_json={
            "project": project,
            "results": [
                {
                    "service": r[0],
                    "status": "success" if "success" in r[1] else ("skipped" if "skipped" in r[1] else "failed"),
                    "detail": r[2],
                }
                for r in results
            ],
        },
    )


@app.command("stop-all")
def stop_all(
    ctx: typer.Context,
    project: Annotated[str, typer.Option("--project", "-p", help="Project name or ID")],
    exclude: Annotated[
        str | None, typer.Option("--exclude", "-e", help="Comma-separated service names to skip")
    ] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Required for destructive operation")] = False,
) -> None:
    """Stop all compose services in a project."""
    c: AppContext = ctx.obj

    if not force:
        c.output.error("--force is required for stop-all (destructive operation)")
        raise typer.Exit(1)

    services = _get_project_compose_services(c, project)
    if not services:
        c.output.error(f"No compose services found in project '{project}'")
        raise typer.Exit(1)

    active, skipped = _filter_services(services, exclude)
    if not active:
        c.output.warn("All services excluded; nothing to stop")
        return

    results: list[list[str]] = []

    for s in skipped:
        results.append([s.get("name", "?"), "[yellow]skipped[/yellow]", "-"])

    with Status("[bold red]Stopping services...", console=c.output._console) as spinner:
        for s in active:
            name = s.get("name", "?")
            cid = s.get("composeId", "")
            spinner.update(f"[bold red]Stopping {name}...")
            try:
                c.client.post("/compose.stop", json={"composeId": cid})
                results.append([name, "[green]stopped[/green]", cid[:12]])
            except Exception as exc:
                results.append([name, "[red]failed[/red]", str(exc)[:50]])

    stopped = sum(1 for r in results if "stopped" in r[1])
    failed = sum(1 for r in results if "failed" in r[1])

    c.output.table(
        f"Bulk Stop Results ({stopped} stopped, {failed} failed, {len(skipped)} skipped)",
        [("Service", "cyan"), ("Status", ""), ("Detail", "dim")],
        results,
        data_for_json={
            "project": project,
            "results": [
                {
                    "service": r[0],
                    "status": "stopped" if "stopped" in r[1] else ("skipped" if "skipped" in r[1] else "failed"),
                    "detail": r[2],
                }
                for r in results
            ],
        },
    )


@app.command("restart-all")
def restart_all(
    ctx: typer.Context,
    project: Annotated[str, typer.Option("--project", "-p", help="Project name or ID")],
    exclude: Annotated[
        str | None, typer.Option("--exclude", "-e", help="Comma-separated service names to skip")
    ] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation prompt")] = False,
) -> None:
    """Restart all compose services (stop + deploy) in a project."""
    c: AppContext = ctx.obj
    services = _get_project_compose_services(c, project)
    if not services:
        c.output.error(f"No compose services found in project '{project}'")
        raise typer.Exit(1)

    active, skipped = _filter_services(services, exclude)
    if not active:
        c.output.warn("All services excluded; nothing to restart")
        return

    if not force:
        names = ", ".join(s.get("name", "?") for s in active)
        typer.confirm(f"Restart {len(active)} service(s): {names}?", abort=True)

    results: list[list[str]] = []

    for s in skipped:
        results.append([s.get("name", "?"), "[yellow]skipped[/yellow]", "-"])

    with Status("[bold blue]Restarting services...", console=c.output._console) as spinner:
        for s in active:
            name = s.get("name", "?")
            cid = s.get("composeId", "")
            spinner.update(f"[bold blue]Stopping {name}...")
            with contextlib.suppress(Exception):
                c.client.post("/compose.stop", json={"composeId": cid})
            spinner.update(f"[bold blue]Deploying {name}...")
            try:
                c.client.post("/compose.deploy", json={"composeId": cid})
                results.append([name, "[green]restarted[/green]", cid[:12]])
            except Exception as exc:
                results.append([name, "[red]failed[/red]", str(exc)[:50]])

    restarted = sum(1 for r in results if "restarted" in r[1])
    failed = sum(1 for r in results if "failed" in r[1])

    c.output.table(
        f"Bulk Restart Results ({restarted} ok, {failed} failed, {len(skipped)} skipped)",
        [("Service", "cyan"), ("Status", ""), ("Detail", "dim")],
        results,
        data_for_json={
            "project": project,
            "results": [
                {
                    "service": r[0],
                    "status": "restarted" if "restarted" in r[1] else ("skipped" if "skipped" in r[1] else "failed"),
                    "detail": r[2],
                }
                for r in results
            ],
        },
    )


@app.command("env-set")
def env_set(
    ctx: typer.Context,
    project: Annotated[str, typer.Option("--project", "-p", help="Project name or ID")],
    key: Annotated[str, typer.Option("--key", "-k", help="Environment variable name")],
    value: Annotated[str, typer.Option("--value", "-v", help="Environment variable value")],
    services: Annotated[
        str | None, typer.Option("--services", "-s", help="Comma-separated service names (default: all)")
    ] = None,
) -> None:
    """Set an environment variable across multiple compose services."""
    c: AppContext = ctx.obj
    all_services = _get_project_compose_services(c, project)
    if not all_services:
        c.output.error(f"No compose services found in project '{project}'")
        raise typer.Exit(1)

    active, _ = _filter_services(all_services, exclude=None, include=services)
    if not active:
        c.output.warn("No matching services found")
        return

    results: list[list[str]] = []

    with Status("[bold blue]Updating env vars...", console=c.output._console) as spinner:
        for s in active:
            name = s.get("name", "?")
            cid = s.get("composeId", "")
            spinner.update(f"[bold blue]Setting {key} on {name}...")
            try:
                current_env = _fetch_env(c, cid)
                updated_env = _update_env_key(current_env, key, value)
                c.client.post("/compose.update", json={"composeId": cid, "env": updated_env})
                results.append([name, "[green]updated[/green]", cid[:12]])
            except Exception as exc:
                results.append([name, "[red]failed[/red]", str(exc)[:50]])

    updated = sum(1 for r in results if "updated" in r[1])
    failed = sum(1 for r in results if "failed" in r[1])

    c.output.table(
        f"Bulk Env Set: {key} ({updated} updated, {failed} failed)",
        [("Service", "cyan"), ("Status", ""), ("Detail", "dim")],
        results,
        data_for_json={
            "project": project,
            "key": key,
            "value": value,
            "results": [
                {"service": r[0], "status": "updated" if "updated" in r[1] else "failed", "detail": r[2]}
                for r in results
            ],
        },
    )
