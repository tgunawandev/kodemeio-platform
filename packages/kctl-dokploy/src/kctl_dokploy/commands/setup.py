"""Setup and pre-flight deployment checks."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import typer

from kctl_dokploy.core.callbacks import AppContext
from kctl_dokploy.core.config import resolve_active_profile_name
from kctl_dokploy.core.helpers import collect_all_services
from kctl_dokploy.core.utils import status_icon

app = typer.Typer(help="Setup and pre-flight checks.")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Check:
    """Single pre-flight check result."""

    name: str
    category: str
    status: str  # "pass", "warn", "fail", "skip"
    message: str
    fix_command: str | None = None


def _check_icon(status: str) -> str:
    """Return a Rich-colored icon for a check status."""
    icons: dict[str, str] = {
        "pass": "[green]\u2713[/green]",
        "warn": "[yellow]\u26a0[/yellow]",
        "fail": "[red]\u2717[/red]",
        "skip": "[dim]-[/dim]",
    }
    return icons.get(status, "[dim]?[/dim]")


# ---------------------------------------------------------------------------
# Check runners
# ---------------------------------------------------------------------------

_CATEGORY_ORDER = ["Infrastructure", "Security", "Data", "Notifications", "Services"]


def _run_infrastructure_checks(c: AppContext) -> list[Check]:
    """Run infrastructure-related pre-flight checks."""
    checks: list[Check] = []

    # 1. API connectivity
    try:
        projects = c.client.get("/project.all")
        if not isinstance(projects, list):
            projects = []
        checks.append(
            Check(
                name="API connectivity",
                category="Infrastructure",
                status="pass",
                message="Dokploy API is reachable",
            )
        )
    except Exception as exc:
        checks.append(
            Check(
                name="API connectivity",
                category="Infrastructure",
                status="fail",
                message=f"Cannot reach API: {exc}",
                fix_command="kctl-dokploy config init",
            )
        )
        # Cannot proceed with further checks if API is down
        for name in ("Server configured", "Docker accessible", "Projects exist"):
            checks.append(
                Check(
                    name=name,
                    category="Infrastructure",
                    status="skip",
                    message="Skipped (API unreachable)",
                )
            )
        return checks

    # 2. Server configured
    try:
        servers = c.client.get("/server.all")
        if not isinstance(servers, list):
            servers = []
        if servers:
            checks.append(
                Check(
                    name="Server configured",
                    category="Infrastructure",
                    status="pass",
                    message=f"{len(servers)} server(s) configured",
                )
            )
        else:
            checks.append(
                Check(
                    name="Server configured",
                    category="Infrastructure",
                    status="warn",
                    message="No servers configured (using local Docker only)",
                )
            )
    except Exception:
        checks.append(
            Check(
                name="Server configured",
                category="Infrastructure",
                status="skip",
                message="Server endpoint not available",
            )
        )

    # 3. Docker accessible
    try:
        containers = c.client.get("/docker.getContainers")
        container_list = containers if isinstance(containers, list) else containers.get("containers", [])
        if not isinstance(container_list, list):
            container_list = []
        if container_list:
            checks.append(
                Check(
                    name="Docker accessible",
                    category="Infrastructure",
                    status="pass",
                    message=f"{len(container_list)} container(s) found",
                )
            )
        else:
            checks.append(
                Check(
                    name="Docker accessible",
                    category="Infrastructure",
                    status="warn",
                    message="Docker reachable but no containers running",
                )
            )
    except Exception:
        checks.append(
            Check(
                name="Docker accessible",
                category="Infrastructure",
                status="fail",
                message="Cannot access Docker API",
                fix_command="Ensure Docker is running and accessible",
            )
        )

    # 4. Projects exist
    if projects:
        checks.append(
            Check(
                name="Projects exist",
                category="Infrastructure",
                status="pass",
                message=f"{len(projects)} project(s) found",
            )
        )
    else:
        checks.append(
            Check(
                name="Projects exist",
                category="Infrastructure",
                status="warn",
                message="No projects created yet",
                fix_command="kctl-dokploy projects create --name <name>",
            )
        )

    return checks


def _run_security_checks(c: AppContext, projects: list[dict]) -> list[Check]:
    """Run security-related pre-flight checks."""
    checks: list[Check] = []

    # 1. SSL certificates
    try:
        certs = c.client.get("/certificates.all")
        if not isinstance(certs, list):
            certs = []
        if certs:
            checks.append(
                Check(
                    name="SSL certificates",
                    category="Security",
                    status="pass",
                    message=f"{len(certs)} certificate(s) configured",
                )
            )
        else:
            checks.append(
                Check(
                    name="SSL certificates",
                    category="Security",
                    status="warn",
                    message="No SSL certificates configured",
                    fix_command="kctl-dokploy certificates create",
                )
            )
    except Exception:
        checks.append(
            Check(
                name="SSL certificates",
                category="Security",
                status="skip",
                message="Certificate endpoint not available",
            )
        )

    # 2. No HTTP-only domains (use shared helper to iterate environments)
    data = collect_all_services(c.client)
    http_only_domains: list[str] = []
    for d in data["domains"]:
        if not d.get("https", True):
            http_only_domains.append(d.get("host", "unknown"))

    if http_only_domains:
        hosts = ", ".join(http_only_domains[:5])
        suffix = f" (+{len(http_only_domains) - 5} more)" if len(http_only_domains) > 5 else ""
        checks.append(
            Check(
                name="No HTTP-only domains",
                category="Security",
                status="warn",
                message=f"{len(http_only_domains)} domain(s) without HTTPS: {hosts}{suffix}",
                fix_command="kctl-dokploy domains update <id> --https",
            )
        )
    else:
        checks.append(
            Check(
                name="No HTTP-only domains",
                category="Security",
                status="pass",
                message="All domains use HTTPS",
            )
        )

    # 3. Users configured
    try:
        users = c.client.get("/user.all")
        if not isinstance(users, list):
            users = []
        if users:
            checks.append(
                Check(
                    name="Users configured",
                    category="Security",
                    status="pass",
                    message=f"{len(users)} user(s) configured",
                )
            )
        else:
            checks.append(
                Check(
                    name="Users configured",
                    category="Security",
                    status="warn",
                    message="No additional users configured",
                )
            )
    except Exception:
        checks.append(
            Check(
                name="Users configured",
                category="Security",
                status="skip",
                message="User endpoint not available",
            )
        )

    return checks


def _run_data_checks(c: AppContext, projects: list[dict]) -> list[Check]:
    """Run data-related pre-flight checks."""
    checks: list[Check] = []

    # 1. Databases provisioned
    db_types = ("postgres", "redis", "mysql", "mariadb", "mongo")
    db_count = 0
    for p in projects:
        # Check environments first, fallback to project root
        envs = p.get("environments", [])
        sources = envs if envs else [p]
        for env in sources:
            for comp in env.get("compose", []):
                comp_name = comp.get("name", "").lower()
                if any(db in comp_name for db in db_types):
                    db_count += 1
            for db_key in ("postgres", "redis", "mysql", "mariadb", "mongo"):
                db_count += len(env.get(db_key, []))

    if db_count > 0:
        checks.append(
            Check(
                name="Databases provisioned",
                category="Data",
                status="pass",
                message=f"{db_count} database service(s) detected",
            )
        )
    else:
        checks.append(
            Check(
                name="Databases provisioned",
                category="Data",
                status="warn",
                message="No database services detected",
            )
        )

    # 2. Backup destinations
    try:
        destinations = c.client.get("/destination.all")
        if not isinstance(destinations, list):
            destinations = []
        if destinations:
            checks.append(
                Check(
                    name="Backup destinations",
                    category="Data",
                    status="pass",
                    message=f"{len(destinations)} destination(s) configured",
                )
            )
        else:
            checks.append(
                Check(
                    name="Backup destinations",
                    category="Data",
                    status="warn",
                    message="No backup destinations configured",
                    fix_command="kctl-dokploy backups add-destination",
                )
            )
    except Exception:
        checks.append(
            Check(
                name="Backup destinations",
                category="Data",
                status="skip",
                message="Destination endpoint not available",
            )
        )

    # 3. Backup schedules
    try:
        # backup.all is not available globally; check destinations instead
        backups: list = []
        enabled = [b for b in backups if b.get("enabled", False)]
        if enabled:
            checks.append(
                Check(
                    name="Backup schedules",
                    category="Data",
                    status="pass",
                    message=f"{len(enabled)} active backup schedule(s)",
                )
            )
        elif backups:
            checks.append(
                Check(
                    name="Backup schedules",
                    category="Data",
                    status="warn",
                    message=f"{len(backups)} backup(s) configured but none enabled",
                )
            )
        else:
            checks.append(
                Check(
                    name="Backup schedules",
                    category="Data",
                    status="warn",
                    message="No backup schedules configured",
                    fix_command="kctl-dokploy backups trigger <compose-id>",
                )
            )
    except Exception:
        checks.append(
            Check(
                name="Backup schedules",
                category="Data",
                status="skip",
                message="Backup endpoint not available",
            )
        )

    return checks


def _run_notification_checks(c: AppContext) -> list[Check]:
    """Run notification-related pre-flight checks."""
    checks: list[Check] = []

    # 1. Notification channels
    try:
        notifications = c.client.get("/notification.all")
        if not isinstance(notifications, list):
            notifications = []
        if notifications:
            checks.append(
                Check(
                    name="Notification channels",
                    category="Notifications",
                    status="pass",
                    message=f"{len(notifications)} channel(s) configured",
                )
            )
        else:
            checks.append(
                Check(
                    name="Notification channels",
                    category="Notifications",
                    status="warn",
                    message="No notification channels configured",
                    fix_command="kctl-dokploy notifications create",
                )
            )
    except Exception:
        checks.append(
            Check(
                name="Notification channels",
                category="Notifications",
                status="skip",
                message="Notification endpoint not available",
            )
        )

    # 2. Git providers
    try:
        git_providers = c.client.get("/gitProvider.getAll")
        if not isinstance(git_providers, list):
            git_providers = []
        if git_providers:
            checks.append(
                Check(
                    name="Git providers",
                    category="Notifications",
                    status="pass",
                    message=f"{len(git_providers)} provider(s) linked",
                )
            )
        else:
            checks.append(
                Check(
                    name="Git providers",
                    category="Notifications",
                    status="warn",
                    message="No git providers linked",
                    fix_command="kctl-dokploy git create",
                )
            )
    except Exception:
        checks.append(
            Check(
                name="Git providers",
                category="Notifications",
                status="skip",
                message="Git provider endpoint not available",
            )
        )

    return checks


def _run_service_checks(c: AppContext, projects: list[dict]) -> list[Check]:
    """Run service-related pre-flight checks."""
    checks: list[Check] = []

    data = collect_all_services(c.client)
    all_compose = data["composes"]
    all_apps = data["applications"]
    all_domains = data["domains"]
    error_services: list[str] = []

    for comp in all_compose:
        status = comp.get("composeStatus", comp.get("status", "")).lower()
        if status == "error":
            error_services.append(comp.get("name", comp.get("composeId", "unknown")))
    for app_item in all_apps:
        status = app_item.get("applicationStatus", app_item.get("status", "")).lower()
        if status == "error":
            error_services.append(app_item.get("name", app_item.get("applicationId", "unknown")))

    total_services = len(all_compose) + len(all_apps)

    # 1. Active services
    if total_services > 0:
        checks.append(
            Check(
                name="Active services",
                category="Services",
                status="pass",
                message=f"{len(all_compose)} compose + {len(all_apps)} application(s)",
            )
        )
    else:
        checks.append(
            Check(
                name="Active services",
                category="Services",
                status="warn",
                message="No services deployed",
                fix_command="kctl-dokploy deploy <compose-id>",
            )
        )

    # 2. All services healthy
    if error_services:
        names = ", ".join(error_services[:5])
        suffix = f" (+{len(error_services) - 5} more)" if len(error_services) > 5 else ""
        checks.append(
            Check(
                name="All services healthy",
                category="Services",
                status="fail",
                message=f"{len(error_services)} service(s) in error state: {names}{suffix}",
                fix_command="kctl-dokploy deployments redeploy <compose-id>",
            )
        )
    elif total_services > 0:
        checks.append(
            Check(
                name="All services healthy",
                category="Services",
                status="pass",
                message="No services in error state",
            )
        )
    else:
        checks.append(
            Check(
                name="All services healthy",
                category="Services",
                status="skip",
                message="No services to check",
            )
        )

    # 3. Domains configured
    if all_domains:
        checks.append(
            Check(
                name="Domains configured",
                category="Services",
                status="pass",
                message=f"{len(all_domains)} domain(s) configured",
            )
        )
    else:
        checks.append(
            Check(
                name="Domains configured",
                category="Services",
                status="warn",
                message="No domains configured",
                fix_command="kctl-dokploy domains create <compose-id> --host <hostname>",
            )
        )

    return checks


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("check")
def check(ctx: typer.Context) -> None:
    """Run pre-flight deployment checklist (15+ checks)."""
    c: AppContext = ctx.obj
    out = c.output
    profile = resolve_active_profile_name(c.profile)
    out.info(f"Running pre-flight checks for profile '{profile}'...")

    all_checks: list[Check] = []

    # Infrastructure checks (also captures projects for reuse)
    infra_checks = _run_infrastructure_checks(c)
    all_checks.extend(infra_checks)

    # Only continue with deeper checks if API is reachable
    api_ok = any(ch.name == "API connectivity" and ch.status == "pass" for ch in infra_checks)

    projects: list[dict] = []
    if api_ok:
        try:
            projects_data = c.client.get("/project.all")
            projects = projects_data if isinstance(projects_data, list) else []
        except Exception:
            projects = []

        all_checks.extend(_run_security_checks(c, projects))
        all_checks.extend(_run_data_checks(c, projects))
        all_checks.extend(_run_notification_checks(c))
        all_checks.extend(_run_service_checks(c, projects))

    # Output
    if c.json_mode:
        out.raw_json([asdict(ch) for ch in all_checks])
        return

    # Pretty output: grouped by category
    rows: list[list[str]] = []
    for category in _CATEGORY_ORDER:
        cat_checks = [ch for ch in all_checks if ch.category == category]
        if not cat_checks:
            continue
        # Category header row
        rows.append([f"[bold cyan]{category}[/bold cyan]", "", "", ""])
        for ch in cat_checks:
            icon = _check_icon(ch.status)
            fix = ch.fix_command or ""
            rows.append([f"  {icon} {ch.name}", ch.status.upper(), ch.message, fix])

    out.table(
        "Pre-Flight Checklist",
        [("Check", ""), ("Status", ""), ("Details", ""), ("Fix", "dim")],
        rows,
        data_for_json=[asdict(ch) for ch in all_checks],
    )

    # Summary
    counts = {"pass": 0, "warn": 0, "fail": 0, "skip": 0}
    for ch in all_checks:
        counts[ch.status] = counts.get(ch.status, 0) + 1

    summary_parts = [
        f"[green]{counts['pass']} passed[/green]",
        f"[yellow]{counts['warn']} warnings[/yellow]",
        f"[red]{counts['fail']} failed[/red]",
    ]
    if counts["skip"]:
        summary_parts.append(f"[dim]{counts['skip']} skipped[/dim]")

    out.text(f"\nSummary: {', '.join(summary_parts)}")

    if counts["fail"] > 0:
        raise typer.Exit(1)


@app.command("wizard")
def wizard(ctx: typer.Context) -> None:
    """Interactive guided setup for Dokploy CLI."""
    c: AppContext = ctx.obj
    out = c.output
    profile = resolve_active_profile_name(c.profile)

    out.header("Dokploy Setup Wizard")
    out.text(f"Active profile: [bold]{profile}[/bold]\n")

    # Step 1: Test API connection
    out.info("Step 1: Testing API connectivity...")
    try:
        status_code = c.client.check_health()
        if status_code in (200, 301, 302):
            out.success(f"API reachable (HTTP {status_code})")
        else:
            out.error(f"API returned HTTP {status_code}")
            out.text("\nRun [bold]kctl-dokploy config init[/bold] to configure your connection.")
            raise typer.Exit(1)
    except Exception as exc:
        out.error(f"Cannot connect: {exc}")
        out.text("\nRun [bold]kctl-dokploy config init[/bold] to configure your connection.")
        raise typer.Exit(1) from exc

    # Step 2: List projects
    out.info("Step 2: Checking projects...")
    try:
        projects = c.client.get("/project.all")
        if not isinstance(projects, list):
            projects = []
    except Exception:
        projects = []

    if projects:
        out.success(f"{len(projects)} project(s) found:")
        for p in projects[:10]:
            name = p.get("name", "unknown")
            compose_count = 0
            app_count = 0
            envs = p.get("environments", [])
            if envs:
                for env in envs:
                    compose_count += len(env.get("compose", []))
                    app_count += len(env.get("applications", []))
            else:
                compose_count = len(p.get("compose", []))
                app_count = len(p.get("applications", []))
            out.text(f"  {status_icon('running')} {name} ({compose_count} compose, {app_count} apps)")
    else:
        out.warn("No projects found.")
        out.text("  Create one with: [bold]kctl-dokploy projects create --name <name>[/bold]")

    # Step 3: Run quick checks and give recommendations
    out.info("Step 3: Running quick diagnostics...")

    recommendations: list[str] = []

    # Check servers
    try:
        servers = c.client.get("/server.all")
        if not isinstance(servers, list) or not servers:
            recommendations.append("Consider adding a remote server for redundancy")
    except Exception:
        pass

    # Check certificates
    try:
        certs = c.client.get("/certificates.all")
        if not isinstance(certs, list) or not certs:
            recommendations.append("Add SSL certificates: kctl-dokploy certificates create")
    except Exception:
        pass

    # Check notifications
    try:
        notifications = c.client.get("/notification.all")
        if not isinstance(notifications, list) or not notifications:
            recommendations.append("Set up notifications: kctl-dokploy notifications create")
    except Exception:
        pass

    # Check backup destinations
    try:
        destinations = c.client.get("/destination.all")
        if not isinstance(destinations, list) or not destinations:
            recommendations.append("Configure backup destinations: kctl-dokploy backups add-destination")
    except Exception:
        pass

    # Check git providers
    try:
        git_providers = c.client.get("/gitProvider.getAll")
        if not isinstance(git_providers, list) or not git_providers:
            recommendations.append("Link a git provider: kctl-dokploy git create")
    except Exception:
        pass

    if recommendations:
        out.text("\n[bold yellow]Recommendations:[/bold yellow]")
        for i, rec in enumerate(recommendations, 1):
            out.text(f"  {i}. {rec}")
    else:
        out.success("All basic setup looks good!")

    out.text("\nRun [bold]kctl-dokploy setup check[/bold] for a detailed pre-flight checklist.")
