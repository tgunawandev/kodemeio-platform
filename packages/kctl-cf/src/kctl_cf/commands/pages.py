"""Cloudflare Pages project and deployment management commands."""

from __future__ import annotations

import json as json_mod
from typing import Annotated

import typer

from kctl_cf.core.callbacks import AppContext
from kctl_cf.core.utils import require_account

app = typer.Typer(help="Manage Cloudflare Pages projects and deployments.")


@app.command()
def projects(ctx: typer.Context) -> None:
    """List all Pages projects."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    items = c.client.get(f"/accounts/{acct}/pages/projects")
    if not isinstance(items, list):
        items = []
    rows = []
    for p in items:
        rows.append(
            [
                p.get("name", ""),
                p.get("subdomain", ""),
                p.get("production_branch", ""),
                (p.get("created_on") or "")[:19],
            ]
        )
    c.output.table(
        "Pages Projects",
        [("Name", "cyan"), ("Subdomain", ""), ("Production Branch", "green"), ("Created", "dim")],
        rows,
        data_for_json=items,
    )


@app.command("get-project")
def get_project(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Project name")],
) -> None:
    """Get Pages project details."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    data = c.client.get(f"/accounts/{acct}/pages/projects/{name}")
    if not isinstance(data, dict):
        data = {}
    source = data.get("source", {}) or {}
    source_type = source.get("type", "")
    source_config = source.get("config", {}) or {}
    build_config = data.get("build_config", {}) or {}
    latest = data.get("latest_deployment", {}) or {}
    sections = [
        (
            "Project",
            [
                ("Name", data.get("name", "")),
                ("Subdomain", data.get("subdomain", "")),
                ("Production Branch", data.get("production_branch", "")),
                ("Source Type", source_type),
                ("Source Production Branch", source_config.get("production_branch", "")),
                ("Build Command", build_config.get("build_command", "")),
                ("Destination Dir", build_config.get("destination_dir", "")),
                ("Deployment Configs", json_mod.dumps(data.get("deployment_configs", {}), default=str)),
                ("Created", (data.get("created_on") or "")[:19]),
                ("Latest Deployment ID", latest.get("id", "")[:12] if latest.get("id") else ""),
            ],
        )
    ]
    c.output.detail(f"Pages Project: {name}", sections, data_for_json=data)


@app.command("create-project")
def create_project(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="Project name")],
    production_branch: Annotated[str, typer.Option("--production-branch", help="Production branch name")],
) -> None:
    """Create a new Pages project."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    payload = {"name": name, "production_branch": production_branch}
    result = c.client.post(f"/accounts/{acct}/pages/projects", json=payload)
    proj_name = result.get("name", name) if isinstance(result, dict) else name
    if c.output.json_mode:
        c.output.raw_json(result if isinstance(result, dict) else {"name": proj_name})
    else:
        c.output.success(f"Pages project created: {proj_name}")


@app.command("delete-project")
def delete_project(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Project name to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
) -> None:
    """Delete a Pages project. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    acct = require_account(c)
    c.client.delete(f"/accounts/{acct}/pages/projects/{name}")
    c.output.success(f"Pages project deleted: {name}")


@app.command()
def deployments(
    ctx: typer.Context,
    project_name: Annotated[str, typer.Argument(help="Project name")],
) -> None:
    """List deployments for a Pages project."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    items = c.client.get(f"/accounts/{acct}/pages/projects/{project_name}/deployments")
    if not isinstance(items, list):
        items = []
    rows = []
    for d in items:
        latest_stage = d.get("latest_stage", {}) or {}
        rows.append(
            [
                (d.get("id") or "")[:12],
                d.get("environment", ""),
                (d.get("url") or "")[:50],
                (d.get("created_on") or "")[:19],
                latest_stage.get("name", ""),
            ]
        )
    c.output.table(
        f"Deployments — {project_name}",
        [("ID", "dim"), ("Environment", "cyan"), ("URL", ""), ("Created", "dim"), ("Status", "green")],
        rows,
        data_for_json=items,
    )


@app.command("get-deployment")
def get_deployment(
    ctx: typer.Context,
    project_name: Annotated[str, typer.Argument(help="Project name")],
    deployment_id: Annotated[str, typer.Argument(help="Deployment ID")],
) -> None:
    """Get deployment details."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    data = c.client.get(f"/accounts/{acct}/pages/projects/{project_name}/deployments/{deployment_id}")
    if not isinstance(data, dict):
        data = {}
    latest_stage = data.get("latest_stage", {}) or {}
    sections = [
        (
            "Deployment",
            [
                ("ID", data.get("id", "")),
                ("Environment", data.get("environment", "")),
                ("URL", data.get("url", "")),
                ("Created", (data.get("created_on") or "")[:19]),
                ("Modified", (data.get("modified_on") or "")[:19]),
                ("Stage", latest_stage.get("name", "")),
                ("Stage Status", latest_stage.get("status", "")),
                ("Short ID", data.get("short_id", "")),
            ],
        )
    ]
    c.output.detail(f"Deployment: {deployment_id[:12]}", sections, data_for_json=data)


@app.command("create-deployment")
def create_deployment(
    ctx: typer.Context,
    project_name: Annotated[str, typer.Argument(help="Project name")],
    branch: Annotated[str | None, typer.Option("--branch", help="Branch to deploy")] = None,
) -> None:
    """Create a new deployment for a Pages project."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    payload: dict | None = {"branch": branch} if branch else None
    result = c.client.post(f"/accounts/{acct}/pages/projects/{project_name}/deployments", json=payload)
    dep_id = result.get("id", "")[:12] if isinstance(result, dict) else ""
    if c.output.json_mode:
        c.output.raw_json(result if isinstance(result, dict) else {"id": dep_id})
    else:
        c.output.success(f"Deployment created: {dep_id}")


@app.command("retry-deployment")
def retry_deployment(
    ctx: typer.Context,
    project_name: Annotated[str, typer.Argument(help="Project name")],
    deployment_id: Annotated[str, typer.Argument(help="Deployment ID to retry")],
) -> None:
    """Retry a failed deployment."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    result = c.client.post(f"/accounts/{acct}/pages/projects/{project_name}/deployments/{deployment_id}/retry")
    if c.output.json_mode:
        c.output.raw_json(result if isinstance(result, dict) else {})
    else:
        c.output.success(f"Deployment retry initiated: {deployment_id[:12]}")


@app.command("rollback-deployment")
def rollback_deployment(
    ctx: typer.Context,
    project_name: Annotated[str, typer.Argument(help="Project name")],
    deployment_id: Annotated[str, typer.Argument(help="Deployment ID to rollback to")],
) -> None:
    """Rollback to a specific deployment."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    result = c.client.post(f"/accounts/{acct}/pages/projects/{project_name}/deployments/{deployment_id}/rollback")
    if c.output.json_mode:
        c.output.raw_json(result if isinstance(result, dict) else {})
    else:
        c.output.success(f"Deployment rollback initiated: {deployment_id[:12]}")


@app.command("delete-deployment")
def delete_deployment(
    ctx: typer.Context,
    project_name: Annotated[str, typer.Argument(help="Project name")],
    deployment_id: Annotated[str, typer.Argument(help="Deployment ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
) -> None:
    """Delete a deployment. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    acct = require_account(c)
    c.client.delete(f"/accounts/{acct}/pages/projects/{project_name}/deployments/{deployment_id}")
    c.output.success(f"Deployment deleted: {deployment_id[:12]}")


@app.command()
def domains(
    ctx: typer.Context,
    project_name: Annotated[str, typer.Argument(help="Project name")],
) -> None:
    """List custom domains for a Pages project."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    items = c.client.get(f"/accounts/{acct}/pages/projects/{project_name}/domains")
    if not isinstance(items, list):
        items = []
    rows = []
    for d in items:
        rows.append(
            [
                (d.get("id") or "")[:12],
                d.get("name", ""),
                d.get("status", ""),
                (d.get("created_on") or "")[:19],
            ]
        )
    c.output.table(
        f"Domains — {project_name}",
        [("ID", "dim"), ("Name", "cyan"), ("Status", "green"), ("Created", "dim")],
        rows,
        data_for_json=items,
    )


@app.command("add-domain")
def add_domain(
    ctx: typer.Context,
    project_name: Annotated[str, typer.Argument(help="Project name")],
    name: Annotated[str, typer.Option("--name", help="Domain name to add")],
) -> None:
    """Add a custom domain to a Pages project."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    result = c.client.post(f"/accounts/{acct}/pages/projects/{project_name}/domains", json={"name": name})
    domain_name = result.get("name", name) if isinstance(result, dict) else name
    if c.output.json_mode:
        c.output.raw_json(result if isinstance(result, dict) else {"name": domain_name})
    else:
        c.output.success(f"Domain added: {domain_name}")


@app.command("remove-domain")
def remove_domain(
    ctx: typer.Context,
    project_name: Annotated[str, typer.Argument(help="Project name")],
    domain_name: Annotated[str, typer.Argument(help="Domain name to remove")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
) -> None:
    """Remove a custom domain from a Pages project. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    acct = require_account(c)
    c.client.delete(f"/accounts/{acct}/pages/projects/{project_name}/domains/{domain_name}")
    c.output.success(f"Domain removed: {domain_name}")
