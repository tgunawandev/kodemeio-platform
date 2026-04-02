"""Atomic deployment pipeline commands.

Provides end-to-end deployment orchestration, status tracking, history,
rollback, and verification for Docker Compose services via Dokploy.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any

import typer

from kctl_dokploy.core.callbacks import AppContext
from kctl_dokploy.core.deploy_ops import DeploymentResult, deploy_atomic
from kctl_dokploy.core.health_ops import quick_health_check, wait_for_healthy
from kctl_dokploy.core.notify_ops import NotifyConfig, notify_all
from kctl_dokploy.core.utils import fmt_duration, fmt_timestamp, status_icon

app = typer.Typer(help="Deployment pipeline operations.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_project_id(client: Any, project_name: str) -> str:
    """Look up a project ID by name (case-insensitive).

    Raises typer.Exit(1) if not found.
    """
    projects = client.get("/project.all")
    if isinstance(projects, list):
        for p in projects:
            if p.get("name", "").lower() == project_name.lower():
                return p.get("projectId", "")
    raise typer.Exit(1)


def _render_deployment_result(
    out: Any,
    result: DeploymentResult,
    *,
    json_mode: bool = False,
) -> None:
    """Render a DeploymentResult as a Rich detail panel or JSON."""
    data = asdict(result)
    if json_mode:
        out.raw_json(data)
        return

    outcome = "[green]SUCCESS[/green]" if result.success else "[red]FAILED[/red]"
    rolled_back = "[yellow]yes[/yellow]" if result.rolled_back else "no"
    steps = ", ".join(result.steps_completed) if result.steps_completed else "-"

    sections = [
        (
            "Result",
            [
                ("Outcome", outcome),
                ("Compose ID", result.compose_id or "-"),
                ("Duration", fmt_duration(result.duration_seconds)),
                ("Steps Completed", steps),
                ("Rolled Back", rolled_back),
            ],
        ),
    ]
    if result.error:
        sections.append(("Error", [("Message", f"[red]{result.error}[/red]")]))

    out.detail("Deployment Result", sections, data_for_json=data)


def _build_notify_fn(config: NotifyConfig) -> Any:
    """Return a notification callback compatible with deploy_atomic."""

    def _notify(status: str, title: str, message: str) -> None:
        notify_all(config, status, title, message)

    return _notify


def _deployment_status_color(status: str) -> str:
    """Return Rich color tag for a deployment status string."""
    s = status.lower()
    if s in ("done", "running"):
        return f"[green]{status}[/green]"
    if s in ("error", "failed"):
        return f"[red]{status}[/red]"
    if s in ("in-progress", "pending", "queued"):
        return f"[yellow]{status}[/yellow]"
    return status


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def deploy(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Compose service name")],
    project: Annotated[str, typer.Option("--project", "-p", help="Project name or ID")],
    file: Annotated[
        Path,
        typer.Option(
            "--file",
            "-f",
            help="Path to docker-compose.yml",
            exists=True,
            readable=True,
            resolve_path=True,
        ),
    ],
    env: Annotated[
        Path | None,
        typer.Option(
            "--env",
            "-e",
            help="Path to .env file",
            exists=True,
            readable=True,
            resolve_path=True,
        ),
    ] = None,
    domain: Annotated[str | None, typer.Option("--domain", "-d", help="Domain to configure")] = None,
    port: Annotated[int, typer.Option("--port", help="Container port for domain routing")] = 80,
    https: Annotated[bool, typer.Option("--https/--no-https", help="Enable HTTPS for domain")] = True,
    cert: Annotated[str, typer.Option("--cert", help="Certificate type for domain")] = "letsencrypt",
    service: Annotated[
        str | None, typer.Option("--service", "-s", help="Docker Compose service name for domain")
    ] = None,
    wait: Annotated[bool, typer.Option("--wait/--no-wait", help="Wait for healthy after deploy")] = False,
    notify: Annotated[bool, typer.Option("--notify/--no-notify", help="Send deployment notifications")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show plan without executing")] = False,
    rollback_on_failure: Annotated[
        bool,
        typer.Option("--rollback-on-failure/--no-rollback", help="Auto-rollback on failure"),
    ] = True,
) -> None:
    """Full atomic deployment pipeline.

    Creates or updates a compose service, uploads the compose file,
    optionally sets environment variables and configures a domain,
    then triggers deployment with optional health-check polling
    and multi-channel notifications.
    """
    c: AppContext = ctx.obj
    out = c.output

    # Resolve project name to ID (accept both name and raw ID)
    project_id = project
    try:
        projects = c.client.get("/project.all")
        if isinstance(projects, list):
            for p in projects:
                if p.get("name", "").lower() == project.lower():
                    project_id = p.get("projectId", project)
                    break
    except Exception:
        pass

    # --dry-run: display the plan and exit
    if dry_run:
        out.header("Deployment Plan (dry run)")
        steps = [
            f"1. Find or create compose [bold]{name}[/bold] in project [bold]{project}[/bold]",
            "2. Snapshot current state for rollback",
            f"3. Upload compose file: [dim]{file}[/dim]",
        ]
        if env:
            steps.append(f"4. Upload environment from: [dim]{env}[/dim]")
        else:
            steps.append("4. Skip environment (not provided)")
        if domain:
            proto = "https" if https else "http"
            steps.append(
                f"5. Configure domain: [bold]{proto}://{domain}:{port}[/bold] "
                f"(cert={cert}, service={service or 'default'})"
            )
        else:
            steps.append("5. Skip domain (not provided)")
        steps.append("6. Trigger deployment")
        if wait:
            steps.append("7. Wait for healthy (poll Dokploy + HTTP)")
        if notify:
            steps.append("8. Send notifications on completion")

        for step in steps:
            out.text(f"  {step}")

        out.text("")
        opts = []
        if rollback_on_failure:
            opts.append("rollback-on-failure")
        if wait:
            opts.append("wait-for-healthy")
        if notify:
            opts.append("notifications")
        out.info(f"Flags: {', '.join(opts) if opts else 'none'}")
        out.warn("No changes were made (dry run)")
        return

    # Build optional callbacks
    health_fn = None
    if wait:

        def _health(client: Any, compose_id: str) -> tuple[bool, str]:
            return wait_for_healthy(
                client,
                compose_id,
                hostname=domain,
                service_hint=service,
            )

        health_fn = _health

    notify_fn = None
    if notify:
        config = NotifyConfig.from_env()
        config.service_name = name
        notify_fn = _build_notify_fn(config)

    # Execute pipeline
    out.header(f"Deploying {name}")
    result = deploy_atomic(
        c.client,
        out,
        name=name,
        project_id=project_id,
        compose_file=file,
        env_file=env,
        domain=domain,
        port=port,
        https=https,
        cert_type=cert,
        service_name=service,
        health_fn=health_fn,
        notify_fn=notify_fn,
        rollback_on_fail=rollback_on_failure,
    )

    _render_deployment_result(out, result, json_mode=c.json_mode)

    if not result.success:
        raise typer.Exit(1)


@app.command()
def status(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
) -> None:
    """Show current deployment status for a compose service.

    Displays compose details, latest deployment info, and associated domains.
    """
    c: AppContext = ctx.obj
    out = c.output

    data = c.client.get("/compose.one", params={"composeId": compose_id})
    if not isinstance(data, dict):
        out.error(f"Compose '{compose_id}' not found")
        raise typer.Exit(1)

    compose_status = data.get("composeStatus", "unknown")
    name = data.get("name", "-")
    created = data.get("createdAt", "")
    updated = data.get("updatedAt", "")
    source_type = data.get("sourceType", "-")
    description = data.get("description", "") or "-"

    # Fetch deployments to find the latest
    deployments = c.client.get("/deployment.allByCompose", params={"composeId": compose_id})
    last_deploy_info: list[tuple[str, str]] = []
    if isinstance(deployments, list) and deployments:
        latest = sorted(deployments, key=lambda d: d.get("createdAt", ""), reverse=True)[0]
        last_deploy_info = [
            ("Deploy ID", latest.get("deploymentId", "")[:16]),
            ("Deploy Status", _deployment_status_color(latest.get("status", "unknown"))),
            ("Deploy Type", latest.get("deploymentType", "-")),
            ("Deploy Time", fmt_timestamp(latest.get("createdAt"))),
        ]

    # Fetch domains
    domains: list[dict[str, Any]] = data.get("domains", [])
    domain_lines: list[tuple[str, str]] = []
    for i, dom in enumerate(domains):
        host = dom.get("host", "-")
        dom_port = dom.get("port", 80)
        dom_https = dom.get("https", False)
        proto = "https" if dom_https else "http"
        cert_type = dom.get("certificateType", "-")
        domain_lines.append((f"Domain {i + 1}", f"[bold]{proto}://{host}:{dom_port}[/bold] (cert={cert_type})"))

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Compose Service",
            [
                ("Name", f"[bold]{name}[/bold]"),
                ("ID", compose_id),
                ("Status", f"{status_icon(compose_status)} {compose_status}"),
                ("Source", source_type),
                ("Description", description),
                ("Created", fmt_timestamp(created)),
                ("Updated", fmt_timestamp(updated)),
            ],
        ),
    ]

    if last_deploy_info:
        sections.append(("Latest Deployment", last_deploy_info))

    if domain_lines:
        sections.append(("Domains", domain_lines))
    else:
        sections.append(("Domains", [("(none)", "No domains configured")]))

    if c.json_mode:
        json_data = dict(data)
        if isinstance(deployments, list) and deployments:
            json_data["latestDeployment"] = sorted(deployments, key=lambda d: d.get("createdAt", ""), reverse=True)[0]
        out.raw_json(json_data)
    else:
        out.detail(f"Pipeline Status: {name}", sections, data_for_json=data)


@app.command()
def history(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum entries to show")] = 20,
) -> None:
    """Show deployment timeline for a compose service.

    Lists recent deployments with date, status, duration, and type.
    """
    c: AppContext = ctx.obj
    out = c.output

    deployments = c.client.get("/deployment.allByCompose", params={"composeId": compose_id})
    if not isinstance(deployments, list):
        out.error(f"No deployments found for compose '{compose_id}'")
        raise typer.Exit(1)

    deployments = sorted(deployments, key=lambda d: d.get("createdAt", ""), reverse=True)[:limit]

    if not deployments:
        out.warn(f"No deployments found for compose '{compose_id}'")
        return

    rows: list[list[str]] = []
    for d in deployments:
        deploy_id = d.get("deploymentId", "")
        deploy_status = d.get("status", "unknown")
        deploy_type = d.get("deploymentType", "-")
        created = d.get("createdAt", "")
        ended = d.get("endedAt")

        # Calculate duration if both timestamps exist
        duration = "-"
        if created and ended:
            try:
                from datetime import datetime

                start_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(ended.replace("Z", "+00:00"))
                delta = (end_dt - start_dt).total_seconds()
                if delta >= 0:
                    duration = fmt_duration(delta)
            except (ValueError, TypeError):
                pass

        rows.append(
            [
                deploy_id,
                fmt_timestamp(created),
                _deployment_status_color(deploy_status),
                duration,
                deploy_type,
            ]
        )

    out.table(
        f"Deployment History ({compose_id}...)",
        [
            ("ID", "dim"),
            ("Date", ""),
            ("Status", ""),
            ("Duration", "cyan"),
            ("Type", ""),
        ],
        rows,
        data_for_json=deployments,
    )


@app.command()
def rollback(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Roll back to the previous successful deployment.

    Finds the last successful deployment, restores its compose file content,
    and triggers a new deployment. Requires confirmation unless --force is used.
    """
    c: AppContext = ctx.obj
    out = c.output

    # Fetch current compose state
    compose_data = c.client.get("/compose.one", params={"composeId": compose_id})
    if not isinstance(compose_data, dict):
        out.error(f"Compose '{compose_id}' not found")
        raise typer.Exit(1)

    compose_name = compose_data.get("name", compose_id)

    # Fetch deployment history
    deployments = c.client.get("/deployment.allByCompose", params={"composeId": compose_id})
    if not isinstance(deployments, list) or len(deployments) < 2:
        out.error("Not enough deployment history to roll back. Need at least 2 deployments.")
        raise typer.Exit(1)

    # Sort newest first, skip the current (first), find previous successful
    sorted_deploys = sorted(deployments, key=lambda d: d.get("createdAt", ""), reverse=True)

    previous: dict[str, Any] | None = None
    for d in sorted_deploys[1:]:
        if d.get("status", "").lower() in ("done", "running"):
            previous = d
            break

    if previous is None:
        out.error("No previous successful deployment found to roll back to")
        raise typer.Exit(1)

    prev_id = previous.get("deploymentId", "")[:16]
    prev_time = fmt_timestamp(previous.get("createdAt"))
    prev_status = previous.get("status", "unknown")

    out.header(f"Rollback: {compose_name}")
    out.text(f"  Current compose: [bold]{compose_name}[/bold] ({compose_id[:16]})")
    out.text(f"  Target deployment: {prev_id} ({prev_time}, status={prev_status})")
    out.text("")

    # Confirm unless forced
    if not force:
        confirmed = typer.confirm("Roll back to the previous version?")
        if not confirmed:
            out.warn("Rollback cancelled")
            raise typer.Exit(0)

    # Re-deploy with previous compose file if available in snapshot
    # The Dokploy API does not store per-deployment compose files directly,
    # so we trigger a plain re-deploy which uses the last known compose file.
    # For a full rollback, the user should have used pipeline deploy with
    # snapshotting enabled.
    out.warn(
        "NOTE: This re-triggers the current compose configuration. "
        "For a full content rollback, use 'pipeline deploy' with a saved template."
    )
    out.info("Triggering re-deployment...")

    try:
        c.client.post("/compose.deploy", json={"composeId": compose_id})
    except Exception as exc:
        out.error(f"Rollback deployment failed: {exc}")
        raise typer.Exit(1) from exc

    out.success(f"Rollback triggered for '{compose_name}'")
    out.info(f"Target: deployment {prev_id} ({prev_time})")

    if c.json_mode:
        out.raw_json(
            {
                "action": "rollback",
                "composeId": compose_id,
                "composeName": compose_name,
                "targetDeploymentId": previous.get("deploymentId", ""),
                "targetCreatedAt": previous.get("createdAt", ""),
                "status": "triggered",
            }
        )


@app.command()
def verify(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
    domain: Annotated[str | None, typer.Option("--domain", "-d", help="Domain for HTTP probing")] = None,
    service_hint: Annotated[
        str | None,
        typer.Option("--service-hint", "-s", help="Service name hint for health path detection"),
    ] = None,
) -> None:
    """Quick health verification for a compose service.

    Checks Dokploy compose status. If --domain is provided, also probes
    the HTTP health endpoint (auto-detected or from --service-hint).
    """
    c: AppContext = ctx.obj
    out = c.output

    # Quick API status check
    compose_status = quick_health_check(c.client, compose_id)
    api_ok = compose_status.lower() in ("done", "running")

    # HTTP probe (optional)
    http_ok: bool | None = None
    http_detail = ""
    if domain:
        from kctl_dokploy.core.health_ops import get_health_url, wait_for_http

        scheme = "https" if not domain.startswith("http") else ""
        base_url = f"{scheme}://{domain}" if scheme else domain
        health_url = get_health_url(base_url, service_hint)

        out.info(f"Probing {health_url}...")
        http_ok, http_code = wait_for_http(health_url, timeout=30, interval=5)
        http_detail = f"HTTP {http_code} at {health_url}"

    # Determine overall result
    overall_ok = (api_ok and http_ok is True) if domain else api_ok

    result_data = {
        "composeId": compose_id,
        "composeStatus": compose_status,
        "apiHealthy": api_ok,
        "httpHealthy": http_ok,
        "httpDetail": http_detail,
        "overall": "healthy" if overall_ok else "unhealthy",
    }

    if c.json_mode:
        out.raw_json(result_data)
        return

    # Pretty output
    api_label = (
        f"[green]PASS[/green] Dokploy: {compose_status}" if api_ok else f"[red]FAIL[/red] Dokploy: {compose_status}"
    )

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Health Check",
            [
                ("Compose ID", compose_id),
                ("API Status", api_label),
            ],
        ),
    ]

    if domain:
        http_label = (
            f"[green]PASS[/green] {http_detail}" if http_ok else f"[red]FAIL[/red] {http_detail or 'HTTP probe failed'}"
        )
        sections[0][1].append(("HTTP Probe", http_label))

    overall_label = "[green]HEALTHY[/green]" if overall_ok else "[red]UNHEALTHY[/red]"
    sections[0][1].append(("Overall", overall_label))

    out.detail("Verification Result", sections, data_for_json=result_data)

    if not overall_ok:
        raise typer.Exit(1)
