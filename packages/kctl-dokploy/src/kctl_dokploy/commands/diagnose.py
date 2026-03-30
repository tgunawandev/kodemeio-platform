"""Comprehensive diagnostic health scoring for Dokploy deployments.

Runs 8 diagnostic sections, scores each 0-100, and computes a weighted
overall health score for the platform.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from kctl_dokploy.core.callbacks import AppContext
from kctl_dokploy.core.client import DokployClient
from kctl_dokploy.core.output import Output
from kctl_dokploy.core.utils import fmt_duration

app = typer.Typer(help="Diagnostic health scoring for Dokploy platform.")

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
SEVERITY_COLORS = {
    "critical": "bold red",
    "high": "red",
    "medium": "yellow",
    "low": "cyan",
    "info": "dim",
}


@dataclass
class Finding:
    """A single diagnostic finding within a section."""

    section: str
    severity: str  # critical, high, medium, low, info
    title: str
    message: str
    fix_command: str | None = None


@dataclass
class SectionResult:
    """Result of a single diagnostic section."""

    name: str
    score: int  # 0-100
    findings: list[Finding] = field(default_factory=list)
    weight: int = 10  # relative importance
    duration_seconds: float = 0.0


@dataclass
class DiagnosticReport:
    """Full diagnostic report across all sections."""

    sections: list[SectionResult]
    overall_score: int
    timestamp: str
    duration_seconds: float


# ---------------------------------------------------------------------------
# Section registry
# ---------------------------------------------------------------------------

SECTION_WEIGHTS: dict[str, int] = {
    "api_health": 20,
    "service_health": 15,
    "deployment_success": 15,
    "ssl_certificates": 15,
    "docker_health": 10,
    "backup_coverage": 10,
    "server_health": 5,
    "notification_channels": 5,
}

SECTION_DESCRIPTIONS: dict[str, str] = {
    "api_health": "API connectivity and response time",
    "service_health": "Compose and application status distribution",
    "deployment_success": "Recent deployment success rate",
    "ssl_certificates": "SSL certificate expiry checks",
    "docker_health": "Docker container status",
    "backup_coverage": "Backup schedule coverage for databases",
    "server_health": "Server connectivity",
    "notification_channels": "Notification channel configuration",
}


# ---------------------------------------------------------------------------
# Section checkers
# ---------------------------------------------------------------------------


def _check_api_health(client: DokployClient) -> SectionResult:
    """Test API connectivity and measure response time."""
    name = "api_health"
    findings: list[Finding] = []

    try:
        t0 = time.monotonic()
        status_code = client.check_health()
        latency = time.monotonic() - t0

        if status_code not in (200, 301, 302):
            findings.append(
                Finding(
                    section=name,
                    severity="critical",
                    title="API unreachable",
                    message=f"Health check returned HTTP {status_code}",
                    fix_command="kctl-dokploy health check",
                )
            )
            return SectionResult(name=name, score=0, findings=findings, weight=SECTION_WEIGHTS[name])

        # Also test an authenticated endpoint
        t1 = time.monotonic()
        client.get("/project.all")
        auth_latency = time.monotonic() - t1

        score = 100
        if auth_latency > 5.0:
            score = 50
            findings.append(
                Finding(
                    section=name,
                    severity="medium",
                    title="Slow API response",
                    message=f"Authenticated request took {auth_latency:.1f}s (>5s threshold)",
                )
            )
        elif auth_latency > 2.0:
            score = 80
            findings.append(
                Finding(
                    section=name,
                    severity="low",
                    title="Moderate API latency",
                    message=f"Authenticated request took {auth_latency:.1f}s (>2s threshold)",
                )
            )

        if score == 100:
            findings.append(
                Finding(
                    section=name,
                    severity="info",
                    title="API healthy",
                    message=f"Response time: {latency:.2f}s (health) / {auth_latency:.2f}s (auth)",
                )
            )

    except Exception as exc:
        findings.append(
            Finding(
                section=name,
                severity="critical",
                title="API connection failed",
                message=str(exc),
                fix_command="kctl-dokploy config test",
            )
        )
        return SectionResult(name=name, score=0, findings=findings, weight=SECTION_WEIGHTS[name])

    return SectionResult(name=name, score=score, findings=findings, weight=SECTION_WEIGHTS[name])


def _check_service_health(client: DokployClient) -> SectionResult:
    """Check status distribution of all compose and application services."""
    name = "service_health"
    findings: list[Finding] = []

    try:
        projects = client.get("/project.all")
        if not isinstance(projects, list):
            projects = []

        total = 0
        running = 0
        error_services: list[str] = []

        for p in projects:
            project_name = p.get("name", "unknown")
            for env in p.get("environments", [p]):
                for svc in env.get("compose", []):
                    total += 1
                    status = svc.get("composeStatus", svc.get("status", "unknown")).lower()
                    if status in ("done", "running", "active"):
                        running += 1
                    elif status in ("error", "failed"):
                        svc_name = svc.get("name", svc.get("composeId", "?")[:12])
                        error_services.append(f"{project_name}/{svc_name}")
                for svc in env.get("applications", []):
                    total += 1
                    status = svc.get("applicationStatus", svc.get("status", "unknown")).lower()
                    if status in ("done", "running", "active"):
                        running += 1
                    elif status in ("error", "failed"):
                        svc_name = svc.get("name", svc.get("applicationId", "?")[:12])
                        error_services.append(f"{project_name}/{svc_name}")

        if total == 0:
            findings.append(
                Finding(
                    section=name,
                    severity="info",
                    title="No services found",
                    message="No compose or application services detected",
                )
            )
            return SectionResult(name=name, score=100, findings=findings, weight=SECTION_WEIGHTS[name])

        ratio = running / total
        score = int(ratio * 100)

        if error_services:
            severity = "critical" if len(error_services) > 2 else "high"
            findings.append(
                Finding(
                    section=name,
                    severity=severity,
                    title=f"{len(error_services)} service(s) in error state",
                    message=", ".join(error_services[:10]),
                    fix_command="kctl-dokploy apps list",
                )
            )

        not_running = total - running - len(error_services)
        if not_running > 0:
            findings.append(
                Finding(
                    section=name,
                    severity="medium",
                    title=f"{not_running} service(s) not running",
                    message=f"{running}/{total} services are in a healthy state",
                )
            )

        if score == 100:
            findings.append(
                Finding(
                    section=name,
                    severity="info",
                    title="All services healthy",
                    message=f"{running}/{total} services running",
                )
            )

    except Exception as exc:
        findings.append(
            Finding(
                section=name,
                severity="high",
                title="Failed to check services",
                message=str(exc),
            )
        )
        return SectionResult(name=name, score=0, findings=findings, weight=SECTION_WEIGHTS[name])

    return SectionResult(name=name, score=score, findings=findings, weight=SECTION_WEIGHTS[name])


def _check_deployment_success(client: DokployClient) -> SectionResult:
    """Analyze recent deployment history for success rate."""
    name = "deployment_success"
    findings: list[Finding] = []

    try:
        deployments = client.get("/deployment.all")
        if not isinstance(deployments, list):
            deployments = []

        # Consider last 50 deployments
        deployments = sorted(
            deployments,
            key=lambda d: d.get("createdAt", ""),
            reverse=True,
        )[:50]

        if not deployments:
            findings.append(
                Finding(
                    section=name,
                    severity="info",
                    title="No deployments found",
                    message="No deployment history available to analyze",
                )
            )
            return SectionResult(name=name, score=100, findings=findings, weight=SECTION_WEIGHTS[name])

        total = len(deployments)
        succeeded = sum(1 for d in deployments if d.get("status", "").lower() in ("done", "success", "running"))
        failed = sum(1 for d in deployments if d.get("status", "").lower() in ("error", "failed"))

        ratio = succeeded / total if total > 0 else 1.0
        score = int(ratio * 100)

        if failed > 0:
            severity = "critical" if ratio < 0.5 else "high" if ratio < 0.8 else "medium"
            findings.append(
                Finding(
                    section=name,
                    severity=severity,
                    title=f"{failed}/{total} recent deployments failed",
                    message=f"Success rate: {ratio:.0%} across last {total} deployments",
                    fix_command="kctl-dokploy deployments list --limit 20",
                )
            )
        else:
            findings.append(
                Finding(
                    section=name,
                    severity="info",
                    title="All recent deployments succeeded",
                    message=f"{succeeded}/{total} deployments successful",
                )
            )

    except Exception as exc:
        findings.append(
            Finding(
                section=name,
                severity="high",
                title="Failed to check deployments",
                message=str(exc),
            )
        )
        return SectionResult(name=name, score=0, findings=findings, weight=SECTION_WEIGHTS[name])

    return SectionResult(name=name, score=score, findings=findings, weight=SECTION_WEIGHTS[name])


def _check_ssl_certificates(client: DokployClient) -> SectionResult:
    """Check certificate expiry -- warn <30d, fail <7d."""
    name = "ssl_certificates"
    findings: list[Finding] = []

    try:
        certs = client.get("/certificates.all")
        if not isinstance(certs, list):
            certs = []

        if not certs:
            findings.append(
                Finding(
                    section=name,
                    severity="medium",
                    title="No SSL certificates found",
                    message="No certificates are configured in Dokploy",
                    fix_command="kctl-dokploy certificates create --name example --domain example.com",
                )
            )
            return SectionResult(name=name, score=60, findings=findings, weight=SECTION_WEIGHTS[name])

        now = datetime.now(tz=UTC)
        score = 100
        expiring_soon: list[str] = []
        expired: list[str] = []

        for cert in certs:
            cert_name = cert.get("name", cert.get("certificateId", "?")[:12])
            expires_raw = cert.get("expiresAt", cert.get("expiration"))
            if not expires_raw:
                continue

            try:
                exp_str = str(expires_raw).replace("Z", "+00:00")
                expires_at = datetime.fromisoformat(exp_str)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)
                days_left = (expires_at - now).days
            except (ValueError, TypeError):
                continue

            if days_left < 0:
                expired.append(cert_name)
                score = min(score, 0)
            elif days_left < 7:
                expiring_soon.append(f"{cert_name} ({days_left}d)")
                score = min(score, 20)
            elif days_left < 30:
                expiring_soon.append(f"{cert_name} ({days_left}d)")
                score = min(score, 70)

        if expired:
            findings.append(
                Finding(
                    section=name,
                    severity="critical",
                    title=f"{len(expired)} certificate(s) expired",
                    message=", ".join(expired),
                    fix_command="kctl-dokploy certificates renew <certificate-id>",
                )
            )

        if expiring_soon:
            findings.append(
                Finding(
                    section=name,
                    severity="high" if score <= 20 else "medium",
                    title=f"{len(expiring_soon)} certificate(s) expiring soon",
                    message=", ".join(expiring_soon),
                    fix_command="kctl-dokploy certificates renew <certificate-id>",
                )
            )

        if not expired and not expiring_soon:
            findings.append(
                Finding(
                    section=name,
                    severity="info",
                    title="All certificates valid",
                    message=f"{len(certs)} certificate(s) checked",
                )
            )

    except Exception as exc:
        findings.append(
            Finding(
                section=name,
                severity="high",
                title="Failed to check certificates",
                message=str(exc),
            )
        )
        return SectionResult(name=name, score=0, findings=findings, weight=SECTION_WEIGHTS[name])

    return SectionResult(name=name, score=score, findings=findings, weight=SECTION_WEIGHTS[name])


def _check_docker_health(client: DokployClient) -> SectionResult:
    """Check Docker container status distribution."""
    name = "docker_health"
    findings: list[Finding] = []

    try:
        containers = client.get("/docker.getContainers")
        if not isinstance(containers, list):
            containers = []

        if not containers:
            findings.append(
                Finding(
                    section=name,
                    severity="info",
                    title="No containers reported",
                    message="Docker API returned no containers",
                )
            )
            return SectionResult(name=name, score=100, findings=findings, weight=SECTION_WEIGHTS[name])

        total = len(containers)
        running = 0
        exited: list[str] = []

        for ct in containers:
            state = ct.get("state", ct.get("State", "unknown")).lower()
            ct_name = ct.get("name", ct.get("Names", "?"))
            if isinstance(ct_name, list):
                ct_name = ct_name[0].lstrip("/") if ct_name else "?"
            ct_name = str(ct_name).lstrip("/")

            if state == "running":
                running += 1
            elif state in ("exited", "dead"):
                exited.append(ct_name)

        ratio = running / total if total > 0 else 1.0
        score = int(ratio * 100)

        if exited:
            severity = "high" if len(exited) > 3 else "medium"
            findings.append(
                Finding(
                    section=name,
                    severity=severity,
                    title=f"{len(exited)} container(s) exited/dead",
                    message=", ".join(exited[:8]),
                    fix_command="kctl-dokploy docker containers",
                )
            )

        if score == 100:
            findings.append(
                Finding(
                    section=name,
                    severity="info",
                    title="All containers running",
                    message=f"{running}/{total} containers in running state",
                )
            )

    except Exception as exc:
        findings.append(
            Finding(
                section=name,
                severity="medium",
                title="Failed to query Docker",
                message=str(exc),
            )
        )
        return SectionResult(name=name, score=50, findings=findings, weight=SECTION_WEIGHTS[name])

    return SectionResult(name=name, score=score, findings=findings, weight=SECTION_WEIGHTS[name])


def _check_backup_coverage(client: DokployClient) -> SectionResult:
    """Verify backup schedules exist for databases."""
    name = "backup_coverage"
    findings: list[Finding] = []
    db_types = ("postgres", "redis", "mysql", "mariadb", "mongo")

    try:
        projects = client.get("/project.all")
        if not isinstance(projects, list):
            projects = []

        # Collect all databases
        databases: list[dict[str, str]] = []
        for p in projects:
            project_name = p.get("name", "unknown")
            for env in p.get("environments", [p]):
                for db_type in db_types:
                    for db in env.get(db_type, []):
                        db_id_field = f"{db_type}Id"
                        databases.append(
                            {
                                "id": db.get(db_id_field, ""),
                                "name": db.get("name", ""),
                                "type": db_type,
                                "project": project_name,
                            }
                        )

        if not databases:
            findings.append(
                Finding(
                    section=name,
                    severity="info",
                    title="No databases found",
                    message="No managed database services detected",
                )
            )
            return SectionResult(name=name, score=100, findings=findings, weight=SECTION_WEIGHTS[name])

        # Check backup schedules
        # backup.all is not available globally in this Dokploy version
        backups: list = []

        backed_up_ids: set[str] = set()
        for b in backups:
            if b.get("enabled", False):
                # Backups may reference various ID fields
                for key in ("databaseId", "postgresId", "mysqlId", "mariadbId", "mongoId", "redisId"):
                    bid = b.get(key)
                    if bid:
                        backed_up_ids.add(bid)

        uncovered: list[str] = []
        for db in databases:
            if db["id"] and db["id"] not in backed_up_ids:
                uncovered.append(f"{db['project']}/{db['name']} ({db['type']})")

        total_db = len(databases)
        covered = total_db - len(uncovered)
        ratio = covered / total_db if total_db > 0 else 1.0
        score = int(ratio * 100)

        if uncovered:
            severity = "high" if ratio < 0.5 else "medium"
            findings.append(
                Finding(
                    section=name,
                    severity=severity,
                    title=f"{len(uncovered)}/{total_db} database(s) without backups",
                    message=", ".join(uncovered[:8]),
                    fix_command="kctl-dokploy backups list",
                )
            )
        else:
            findings.append(
                Finding(
                    section=name,
                    severity="info",
                    title="All databases have backups",
                    message=f"{total_db} database(s) covered by backup schedules",
                )
            )

    except Exception as exc:
        findings.append(
            Finding(
                section=name,
                severity="medium",
                title="Failed to check backups",
                message=str(exc),
            )
        )
        return SectionResult(name=name, score=0, findings=findings, weight=SECTION_WEIGHTS[name])

    return SectionResult(name=name, score=score, findings=findings, weight=SECTION_WEIGHTS[name])


def _check_server_health(client: DokployClient) -> SectionResult:
    """Check server connectivity status."""
    name = "server_health"
    findings: list[Finding] = []

    try:
        servers = client.get("/server.all")
        if not isinstance(servers, list):
            servers = []

        if not servers:
            findings.append(
                Finding(
                    section=name,
                    severity="info",
                    title="No remote servers",
                    message="Only the local Dokploy server is configured",
                )
            )
            return SectionResult(name=name, score=100, findings=findings, weight=SECTION_WEIGHTS[name])

        total = len(servers)
        healthy = 0
        unhealthy_servers: list[str] = []

        for s in servers:
            server_name = s.get("name", s.get("serverId", "?")[:12])
            status = s.get("serverStatus", "unknown").lower()
            if status in ("active", "running", "healthy", "connected"):
                healthy += 1
            else:
                unhealthy_servers.append(f"{server_name} ({status})")

        ratio = healthy / total if total > 0 else 1.0
        score = int(ratio * 100)

        if unhealthy_servers:
            findings.append(
                Finding(
                    section=name,
                    severity="high",
                    title=f"{len(unhealthy_servers)} server(s) unhealthy",
                    message=", ".join(unhealthy_servers),
                    fix_command="kctl-dokploy servers list",
                )
            )
        else:
            findings.append(
                Finding(
                    section=name,
                    severity="info",
                    title="All servers healthy",
                    message=f"{healthy}/{total} server(s) connected",
                )
            )

    except Exception as exc:
        findings.append(
            Finding(
                section=name,
                severity="medium",
                title="Failed to check servers",
                message=str(exc),
            )
        )
        return SectionResult(name=name, score=0, findings=findings, weight=SECTION_WEIGHTS[name])

    return SectionResult(name=name, score=score, findings=findings, weight=SECTION_WEIGHTS[name])


def _check_notification_channels(client: DokployClient) -> SectionResult:
    """Verify notification channel configurations exist."""
    name = "notification_channels"
    findings: list[Finding] = []

    try:
        notifications = client.get("/notification.all")
        if not isinstance(notifications, list):
            notifications = []

        if not notifications:
            findings.append(
                Finding(
                    section=name,
                    severity="medium",
                    title="No notification channels configured",
                    message="Deployment alerts will not be sent anywhere",
                    fix_command="kctl-dokploy notifications list",
                )
            )
            return SectionResult(name=name, score=30, findings=findings, weight=SECTION_WEIGHTS[name])

        enabled = [n for n in notifications if n.get("enabled", True)]
        disabled = len(notifications) - len(enabled)

        if not enabled:
            findings.append(
                Finding(
                    section=name,
                    severity="high",
                    title="All notification channels disabled",
                    message=f"{len(notifications)} channel(s) exist but none are enabled",
                )
            )
            return SectionResult(name=name, score=20, findings=findings, weight=SECTION_WEIGHTS[name])

        score = 100
        if disabled > 0:
            score = 80
            findings.append(
                Finding(
                    section=name,
                    severity="low",
                    title=f"{disabled} notification channel(s) disabled",
                    message=f"{len(enabled)} enabled, {disabled} disabled",
                )
            )
        else:
            findings.append(
                Finding(
                    section=name,
                    severity="info",
                    title="Notification channels configured",
                    message=f"{len(enabled)} channel(s) active",
                )
            )

    except Exception as exc:
        findings.append(
            Finding(
                section=name,
                severity="medium",
                title="Failed to check notifications",
                message=str(exc),
            )
        )
        return SectionResult(name=name, score=0, findings=findings, weight=SECTION_WEIGHTS[name])

    return SectionResult(name=name, score=score, findings=findings, weight=SECTION_WEIGHTS[name])


# ---------------------------------------------------------------------------
# Section dispatcher
# ---------------------------------------------------------------------------

SECTION_CHECKERS: dict[str, type[...] | object] = {
    "api_health": _check_api_health,
    "service_health": _check_service_health,
    "deployment_success": _check_deployment_success,
    "ssl_certificates": _check_ssl_certificates,
    "docker_health": _check_docker_health,
    "backup_coverage": _check_backup_coverage,
    "server_health": _check_server_health,
    "notification_channels": _check_notification_channels,
}


def _run_section(name: str, client: DokployClient) -> SectionResult:
    """Run a single diagnostic section by name, timing its execution."""
    checker = SECTION_CHECKERS[name]
    t0 = time.monotonic()
    result = checker(client)  # type: ignore[operator]
    result.duration_seconds = time.monotonic() - t0
    return result


def _compute_overall_score(sections: list[SectionResult]) -> int:
    """Weighted average of section scores."""
    total_weight = sum(s.weight for s in sections)
    if total_weight == 0:
        return 0
    return sum(s.score * s.weight for s in sections) // total_weight


def _score_color(score: int) -> str:
    """Return a Rich color string for the given score."""
    if score > 80:
        return "green"
    if score >= 50:
        return "yellow"
    return "red"


def _score_label(score: int) -> str:
    """Return a human-readable label for the score."""
    if score > 90:
        return "Excellent"
    if score > 80:
        return "Good"
    if score >= 50:
        return "Fair"
    if score >= 30:
        return "Poor"
    return "Critical"


def _report_to_dict(report: DiagnosticReport) -> dict:
    """Convert a DiagnosticReport to a JSON-serializable dict."""
    return {
        "overall_score": report.overall_score,
        "timestamp": report.timestamp,
        "duration_seconds": round(report.duration_seconds, 2),
        "sections": [
            {
                "name": s.name,
                "description": SECTION_DESCRIPTIONS.get(s.name, ""),
                "score": s.score,
                "weight": s.weight,
                "duration_seconds": round(s.duration_seconds, 3),
                "findings": [
                    {
                        "severity": f.severity,
                        "title": f.title,
                        "message": f.message,
                        **({"fix_command": f.fix_command} if f.fix_command else {}),
                    }
                    for f in s.findings
                ],
            }
            for s in report.sections
        ],
    }


def _render_report(report: DiagnosticReport, out: Output) -> None:
    """Render the diagnostic report in pretty mode using Rich."""
    console = out.console
    color = _score_color(report.overall_score)
    label = _score_label(report.overall_score)

    # Overall score panel
    score_text = (
        f"[bold {color}]{report.overall_score}/100[/bold {color}]  "
        f"[{color}]{label}[/{color}]\n\n"
        f"[dim]Completed in {fmt_duration(report.duration_seconds)} "
        f"at {report.timestamp}[/dim]"
    )
    console.print(Panel(score_text, title="[bold]Platform Health Score[/bold]", border_style=color))

    # Per-section breakdown table
    section_table = Table(title="Section Scores", show_header=True, header_style="bold cyan")
    section_table.add_column("Section", style="")
    section_table.add_column("Score", justify="right", style="")
    section_table.add_column("Weight", justify="right", style="dim")
    section_table.add_column("Time", justify="right", style="dim")
    section_table.add_column("Status", style="")

    for s in report.sections:
        sc = _score_color(s.score)
        desc = SECTION_DESCRIPTIONS.get(s.name, s.name)
        status_parts: list[str] = []
        for f in s.findings:
            if f.severity in ("critical", "high"):
                status_parts.append(f"[red]{f.title}[/red]")
            elif f.severity == "medium":
                status_parts.append(f"[yellow]{f.title}[/yellow]")
        status_str = "; ".join(status_parts) if status_parts else "[green]OK[/green]"
        section_table.add_row(
            desc,
            f"[{sc}]{s.score}[/{sc}]",
            str(s.weight),
            f"{s.duration_seconds:.1f}s",
            status_str,
        )

    console.print(section_table)

    # Findings table (only non-info findings)
    actionable = [f for s in report.sections for f in s.findings if f.severity != "info"]
    actionable.sort(key=lambda f: SEVERITY_ORDER.get(f.severity, 99))

    if actionable:
        findings_table = Table(title="Findings", show_header=True, header_style="bold cyan")
        findings_table.add_column("Severity", style="")
        findings_table.add_column("Section", style="dim")
        findings_table.add_column("Title", style="")
        findings_table.add_column("Message", style="")
        findings_table.add_column("Fix", style="dim")

        for f in actionable:
            sev_color = SEVERITY_COLORS.get(f.severity, "")
            findings_table.add_row(
                f"[{sev_color}]{f.severity.upper()}[/{sev_color}]",
                f.section,
                f.title,
                f.message,
                f.fix_command or "",
            )

        console.print(findings_table)
    else:
        console.print("[green]No actionable findings -- platform looks healthy.[/green]")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("run")
def run(ctx: typer.Context) -> None:
    """Run all diagnostic sections and display the health report."""
    c: AppContext = ctx.obj
    out = c.output

    if not c.json_mode:
        out.info("Running diagnostics across 8 sections...")

    t0 = time.monotonic()
    sections: list[SectionResult] = []
    for name in SECTION_WEIGHTS:
        result = _run_section(name, c.client)
        sections.append(result)

    overall = _compute_overall_score(sections)
    report = DiagnosticReport(
        sections=sections,
        overall_score=overall,
        timestamp=datetime.now(tz=UTC).isoformat(timespec="seconds"),
        duration_seconds=time.monotonic() - t0,
    )

    if c.json_mode:
        out.raw_json(_report_to_dict(report))
        return

    _render_report(report, out)


@app.command("section")
def section(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Section name to run (e.g., api_health, ssl_certificates)")],
) -> None:
    """Run a single diagnostic section."""
    c: AppContext = ctx.obj
    out = c.output

    if name not in SECTION_CHECKERS:
        available = ", ".join(sorted(SECTION_CHECKERS.keys()))
        out.error(f"Unknown section '{name}'. Available: {available}")
        raise typer.Exit(1)

    if not c.json_mode:
        desc = SECTION_DESCRIPTIONS.get(name, name)
        out.info(f"Running diagnostic section: {desc}")

    t0 = time.monotonic()
    result = _run_section(name, c.client)
    total_time = time.monotonic() - t0

    report = DiagnosticReport(
        sections=[result],
        overall_score=result.score,
        timestamp=datetime.now(tz=UTC).isoformat(timespec="seconds"),
        duration_seconds=total_time,
    )

    if c.json_mode:
        out.raw_json(_report_to_dict(report))
        return

    _render_report(report, out)
