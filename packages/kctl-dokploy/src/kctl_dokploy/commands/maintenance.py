"""Maintenance and data integrity commands."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext
from kctl_dokploy.core.helpers import collect_all_services

app = typer.Typer(help="Maintenance, integrity checks, and cleanup.")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class IntegrityFinding:
    """Single data integrity finding."""

    category: str
    name: str
    resource_id: str
    issue: str
    severity: str  # "critical", "warning", "info"
    fix_command: str | None = None


def _severity_color(severity: str) -> str:
    """Return Rich color tag for a severity level."""
    colors: dict[str, str] = {
        "critical": "red",
        "warning": "yellow",
        "info": "blue",
    }
    return colors.get(severity.lower(), "dim")


def _severity_icon(severity: str) -> str:
    """Return Rich-colored icon for severity."""
    s = severity.lower()
    if s == "critical":
        return "[red]\u2717[/red]"
    if s == "warning":
        return "[yellow]\u26a0[/yellow]"
    return "[blue]\u2139[/blue]"


def _parse_duration(duration_str: str) -> float:
    """Parse a duration string like '1h', '30m', '2h30m' into seconds."""
    total = 0.0
    pattern = re.compile(r"(\d+(?:\.\d+)?)\s*(h|m|s)", re.IGNORECASE)
    matches = pattern.findall(duration_str)
    if not matches:
        # Try as plain number (assume seconds)
        try:
            return float(duration_str)
        except ValueError:
            return 3600.0  # default 1 hour
    for value, unit in matches:
        multipliers = {"h": 3600, "m": 60, "s": 1}
        total += float(value) * multipliers.get(unit.lower(), 1)
    return total


# ---------------------------------------------------------------------------
# Integrity check helpers
# ---------------------------------------------------------------------------


def _collect_all_projects(c: AppContext) -> list[dict]:
    """Fetch all projects, returning empty list on failure."""
    try:
        projects = c.client.get("/project.all")
        return projects if isinstance(projects, list) else []
    except Exception:
        return []


def _check_orphaned_compose(
    projects: list[dict],
    composes: list[dict],
) -> list[IntegrityFinding]:
    """Find compose services not linked to a valid project."""
    findings: list[IntegrityFinding] = []
    # Check for projects with missing projectId
    missing_project_ids = {p.get("name", "unknown") for p in projects if not p.get("projectId", "")}
    for comp in composes:
        project_name = comp.get("_project", "unknown")
        if project_name in missing_project_ids:
            findings.append(
                IntegrityFinding(
                    category="Orphaned compose",
                    name=comp.get("name", "unknown"),
                    resource_id=comp.get("composeId", ""),
                    issue=f"Compose service in project '{project_name}' with missing projectId",
                    severity="warning",
                )
            )
    return findings


def _check_services_without_domains(
    composes: list[dict],
    applications: list[dict],
) -> list[IntegrityFinding]:
    """Find compose services and applications with zero domains."""
    findings: list[IntegrityFinding] = []
    for comp in composes:
        project_name = comp.get("_project", "unknown")
        cid = comp.get("composeId", "")
        comp_name = comp.get("name", "unknown")
        # domains are enriched by collect_all_services
        domains = comp.get("domains", [])
        if not domains:
            findings.append(
                IntegrityFinding(
                    category="No domains",
                    name=f"{project_name}/{comp_name}",
                    resource_id=cid,
                    issue="Compose service has no domains configured",
                    severity="info",
                    fix_command=f"kctl-dokploy domains create {cid} --host <hostname>",
                )
            )
    for app_item in applications:
        project_name = app_item.get("_project", "unknown")
        aid = app_item.get("applicationId", "")
        app_name = app_item.get("name", "unknown")
        domains = app_item.get("domains", [])
        if not domains:
            findings.append(
                IntegrityFinding(
                    category="No domains",
                    name=f"{project_name}/{app_name}",
                    resource_id=aid,
                    issue="Application has no domains configured",
                    severity="info",
                    fix_command=f"kctl-dokploy domains create {aid} --host <hostname>",
                )
            )
    return findings


def _check_stale_deployments(
    c: AppContext,
    threshold_seconds: float,
) -> list[IntegrityFinding]:
    """Find deployments stuck in 'running' state beyond threshold."""
    findings: list[IntegrityFinding] = []
    try:
        deployments = c.client.get("/deployment.all")
        if not isinstance(deployments, list):
            deployments = []
    except Exception:
        return findings

    now = datetime.now(tz=UTC)
    for d in deployments:
        status = d.get("status", "").lower()
        if status != "running":
            continue
        created_at = d.get("createdAt", "")
        if not created_at:
            continue
        try:
            cleaned = re.sub(r"Z$", "+00:00", created_at)
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            elapsed = (now - dt).total_seconds()
            if elapsed > threshold_seconds:
                did = d.get("deploymentId", "unknown")
                minutes = int(elapsed // 60)
                findings.append(
                    IntegrityFinding(
                        category="Stale deployment",
                        name=did[:16],
                        resource_id=did,
                        issue=f"Running for {minutes}m (threshold: {int(threshold_seconds // 60)}m)",
                        severity="warning",
                        fix_command=f"kctl-dokploy deployments cancel {did}",
                    )
                )
        except (ValueError, TypeError):
            continue

    return findings


def _check_databases_without_backups(
    c: AppContext,
    composes: list[dict],
    raw_projects: list[dict],
) -> list[IntegrityFinding]:
    """Find database services without backup schedules."""
    findings: list[IntegrityFinding] = []
    db_types = ("postgres", "redis", "mysql", "mariadb", "mongo")

    # Check compose services whose name contains a DB type
    for comp in composes:
        project_name = comp.get("_project", "unknown")
        comp_name = comp.get("name", "").lower()
        cid = comp.get("composeId", "")
        # backups are enriched by collect_all_services
        has_backup = bool(comp.get("backups"))
        if any(db in comp_name for db in db_types) and not has_backup:
            findings.append(
                IntegrityFinding(
                    category="No backup",
                    name=f"{project_name}/{comp.get('name', 'unknown')}",
                    resource_id=cid,
                    issue="Database service has no backup schedule",
                    severity="warning",
                    fix_command=f"kctl-dokploy backups trigger {cid}",
                )
            )

    # Check native DB resources across environments
    for p in raw_projects:
        project_name = p.get("name", "unknown")
        envs = p.get("environments", [])
        sources = envs if envs else [p]
        for env in sources:
            for db_key in db_types:
                for db_item in env.get(db_key, []):
                    db_id = db_item.get(f"{db_key}Id", db_item.get("databaseId", ""))
                    db_name = db_item.get("name", db_key)
                    findings.append(
                        IntegrityFinding(
                            category="No backup",
                            name=f"{project_name}/{db_name}",
                            resource_id=db_id,
                            issue=f"Native {db_key} database - verify backup is configured",
                            severity="info",
                        )
                    )

    return findings


def _check_unreachable_services(
    composes: list[dict],
    applications: list[dict],
) -> list[IntegrityFinding]:
    """Find services in error state."""
    findings: list[IntegrityFinding] = []
    for comp in composes:
        project_name = comp.get("_project", "unknown")
        status = comp.get("composeStatus", comp.get("status", "")).lower()
        if status == "error":
            cid = comp.get("composeId", "")
            findings.append(
                IntegrityFinding(
                    category="Unreachable",
                    name=f"{project_name}/{comp.get('name', 'unknown')}",
                    resource_id=cid,
                    issue="Compose service is in error state",
                    severity="critical",
                    fix_command=f"kctl-dokploy deployments redeploy {cid}",
                )
            )
    for app_item in applications:
        project_name = app_item.get("_project", "unknown")
        status = app_item.get("applicationStatus", app_item.get("status", "")).lower()
        if status == "error":
            aid = app_item.get("applicationId", "")
            findings.append(
                IntegrityFinding(
                    category="Unreachable",
                    name=f"{project_name}/{app_item.get('name', 'unknown')}",
                    resource_id=aid,
                    issue="Application is in error state",
                    severity="critical",
                    fix_command=f"kctl-dokploy deployments redeploy {aid}",
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("integrity")
def integrity(ctx: typer.Context) -> None:
    """Run data integrity checks across all resources."""
    c: AppContext = ctx.obj
    out = c.output
    out.info("Running data integrity checks...")

    raw_projects = _collect_all_projects(c)
    if not raw_projects:
        out.warn("No projects found or API unreachable.")

    data = collect_all_services(c.client)

    findings: list[IntegrityFinding] = []
    findings.extend(_check_orphaned_compose(data["projects"], data["composes"]))
    findings.extend(_check_services_without_domains(data["composes"], data["applications"]))
    findings.extend(_check_stale_deployments(c, threshold_seconds=3600.0))
    findings.extend(_check_databases_without_backups(c, data["composes"], raw_projects))
    findings.extend(_check_unreachable_services(data["composes"], data["applications"]))

    if c.json_mode:
        out.raw_json([asdict(f) for f in findings])
        return

    if not findings:
        out.success("No integrity issues found.")
        return

    rows: list[list[str]] = []
    for f in findings:
        icon = _severity_icon(f.severity)
        color = _severity_color(f.severity)
        rows.append(
            [
                f"{icon} [{color}]{f.severity.upper()}[/{color}]",
                f.category,
                f.name,
                f.issue,
                f.fix_command or "",
            ]
        )

    out.table(
        "Integrity Findings",
        [
            ("Severity", ""),
            ("Category", "cyan"),
            ("Resource", ""),
            ("Issue", ""),
            ("Fix", "dim"),
        ],
        rows,
        data_for_json=[asdict(f) for f in findings],
    )

    critical = sum(1 for f in findings if f.severity == "critical")
    warnings = sum(1 for f in findings if f.severity == "warning")
    info_count = sum(1 for f in findings if f.severity == "info")
    out.text(
        f"\nFound: [red]{critical} critical[/red], "
        f"[yellow]{warnings} warning(s)[/yellow], "
        f"[blue]{info_count} info[/blue]"
    )

    if critical > 0:
        raise typer.Exit(1)


@app.command("orphans")
def orphans(ctx: typer.Context) -> None:
    """List orphaned resources (disconnected services, domains)."""
    c: AppContext = ctx.obj
    out = c.output
    out.info("Scanning for orphaned resources...")

    data = collect_all_services(c.client)
    findings: list[IntegrityFinding] = []
    findings.extend(_check_orphaned_compose(data["projects"], data["composes"]))

    if c.json_mode:
        out.raw_json([asdict(f) for f in findings])
        return

    if not findings:
        out.success("No orphaned resources found.")
        return

    rows: list[list[str]] = []
    for f in findings:
        rows.append([f.category, f.name, f.resource_id[:16], f.issue])

    out.table(
        "Orphaned Resources",
        [("Type", "cyan"), ("Name", ""), ("ID", "dim"), ("Reason", "")],
        rows,
        data_for_json=[asdict(f) for f in findings],
    )


@app.command("stale")
def stale(
    ctx: typer.Context,
    threshold: Annotated[
        str,
        typer.Option("--threshold", "-t", help="Duration threshold (e.g. '1h', '30m')"),
    ] = "1h",
) -> None:
    """List stale/stuck deployments beyond a time threshold."""
    c: AppContext = ctx.obj
    out = c.output
    threshold_seconds = _parse_duration(threshold)
    out.info(f"Looking for deployments running longer than {threshold}...")

    findings = _check_stale_deployments(c, threshold_seconds)

    if c.json_mode:
        out.raw_json([asdict(f) for f in findings])
        return

    if not findings:
        out.success("No stale deployments found.")
        return

    rows: list[list[str]] = []
    for f in findings:
        rows.append([f.name, f.resource_id[:16], f.issue, f.fix_command or ""])

    out.table(
        "Stale Deployments",
        [("Deployment", "cyan"), ("ID", "dim"), ("Details", ""), ("Cancel Command", "yellow")],
        rows,
        data_for_json=[asdict(f) for f in findings],
    )


@app.command("cleanup")
def cleanup(
    ctx: typer.Context,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run/--no-dry-run", help="Show what would be cleaned up without executing"),
    ] = True,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Execute cleanup (overrides dry-run)"),
    ] = False,
) -> None:
    """Safe cleanup of orphaned and stale resources."""
    c: AppContext = ctx.obj
    out = c.output

    effective_dry_run = dry_run and not force

    if effective_dry_run:
        out.info("Running cleanup in DRY RUN mode (use --force to execute)...")
    else:
        out.warn("Running cleanup in LIVE mode...")

    data = collect_all_services(c.client)
    findings: list[IntegrityFinding] = []
    findings.extend(_check_orphaned_compose(data["projects"], data["composes"]))
    findings.extend(_check_stale_deployments(c, threshold_seconds=3600.0))
    findings.extend(_check_unreachable_services(data["composes"], data["applications"]))

    # Filter to actionable findings (those with fix commands)
    actionable = [f for f in findings if f.fix_command]

    if c.json_mode:
        out.raw_json(
            {
                "dry_run": effective_dry_run,
                "findings": [asdict(f) for f in actionable],
            }
        )
        return

    if not actionable:
        out.success("Nothing to clean up.")
        return

    rows: list[list[str]] = []
    for f in actionable:
        action = "WOULD" if effective_dry_run else "WILL"
        rows.append(
            [
                _severity_icon(f.severity),
                f.category,
                f.name,
                f.issue,
                f"{action}: {f.fix_command}",
            ]
        )

    out.table(
        f"Cleanup {'Plan' if effective_dry_run else 'Actions'}",
        [("", ""), ("Category", "cyan"), ("Resource", ""), ("Issue", ""), ("Action", "yellow")],
        rows,
        data_for_json={"dry_run": effective_dry_run, "actions": [asdict(f) for f in actionable]},
    )

    if not effective_dry_run:
        # Execute cancellation of stale deployments
        cancelled = 0
        for f in actionable:
            if f.category == "Stale deployment" and f.fix_command:
                try:
                    c.client.post("/deployment.killProcess", json={"deploymentId": f.resource_id})
                    out.success(f"Cancelled stale deployment: {f.name}")
                    cancelled += 1
                except Exception as exc:
                    out.warn(f"Failed to cancel {f.name}: {exc}")

        if cancelled:
            out.success(f"Cleaned up {cancelled} stale deployment(s)")
        out.info(
            "Note: orphaned and unreachable services require manual intervention. Use the suggested fix commands above."
        )
    else:
        out.text(f"\n{len(actionable)} item(s) would be affected. Use --force to execute.")
