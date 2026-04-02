"""Security audit and compliance check commands."""

from __future__ import annotations

from datetime import UTC, datetime

import typer

from kctl_dokploy.core.callbacks import AppContext
from kctl_dokploy.core.helpers import collect_all_services
from kctl_dokploy.core.utils import fmt_timestamp

app = typer.Typer(help="Security audit and compliance checks.")


def _parse_expiry(expiry_str: str | None) -> datetime | None:
    """Parse an ISO expiry string into a timezone-aware datetime, or None."""
    if not expiry_str:
        return None
    try:
        cleaned = expiry_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, TypeError):
        return None


def _days_until(dt: datetime) -> int:
    """Return the number of days from now until the given datetime."""
    now = datetime.now(tz=UTC)
    delta = dt - now
    return delta.days


def _severity_color(severity: str) -> str:
    """Return a Rich color tag for a severity level."""
    mapping = {
        "critical": "[red]",
        "high": "[red]",
        "warning": "[yellow]",
        "info": "[blue]",
        "pass": "[green]",
    }
    return mapping.get(severity.lower(), "")


def _severity_label(severity: str) -> str:
    """Return a Rich-colored severity label."""
    color = _severity_color(severity)
    close = color.replace("[", "[/") if color else ""
    return f"{color}{severity.upper()}{close}"


@app.command()
def security(ctx: typer.Context) -> None:
    """Run a comprehensive security review across the platform."""
    c: AppContext = ctx.obj
    findings: list[dict] = []

    # --- SSL certificate expiry checks ---
    try:
        certs = c.client.get("/certificates.all")
        if not isinstance(certs, list):
            certs = []
    except Exception:
        certs = []
        findings.append(
            {
                "category": "SSL",
                "severity": "warning",
                "issue": "Unable to fetch certificates",
                "resource": "-",
                "fix_command": "kctl certificate list",
            }
        )

    for cert in certs:
        cert_name = cert.get("name", "unknown")
        expiry_str = cert.get("expiresAt", cert.get("expiration"))
        expiry_dt = _parse_expiry(expiry_str)
        if expiry_dt is None:
            findings.append(
                {
                    "category": "SSL",
                    "severity": "warning",
                    "issue": f"Certificate '{cert_name}' has no expiry date",
                    "resource": cert_name,
                    "fix_command": f"kctl certificate get {cert.get('certificateId', '')}",
                }
            )
            continue
        days = _days_until(expiry_dt)
        if days < 7:
            findings.append(
                {
                    "category": "SSL",
                    "severity": "critical",
                    "issue": f"Certificate '{cert_name}' expires in {days}d",
                    "resource": cert_name,
                    "fix_command": f"kctl certificate renew {cert.get('certificateId', '')}",
                }
            )
        elif days < 30:
            findings.append(
                {
                    "category": "SSL",
                    "severity": "warning",
                    "issue": f"Certificate '{cert_name}' expires in {days}d",
                    "resource": cert_name,
                    "fix_command": f"kctl certificate renew {cert.get('certificateId', '')}",
                }
            )

    # --- Collect all services via shared helper ---
    data = collect_all_services(c.client)

    # --- Autodeploy enabled ---
    for comp in data["composes"]:
        if comp.get("autoDeploy"):
            findings.append(
                {
                    "category": "Deploy",
                    "severity": "high",
                    "issue": f"Autodeploy enabled on '{comp.get('name', '?')}'",
                    "resource": comp.get("name", ""),
                    "fix_command": f"kctl-dokploy compose update --id {comp.get('composeId', '')} --no-auto-deploy",
                }
            )

    # --- HTTP-only domains ---
    for d in data["domains"]:
        if not d.get("https"):
            findings.append(
                {
                    "category": "HTTPS",
                    "severity": "high",
                    "issue": f"Domain '{d.get('host', '')}' does not have HTTPS enabled",
                    "resource": d.get("_service", ""),
                    "fix_command": f"kctl-dokploy domains update {d.get('domainId', '')} --https",
                }
            )

    # --- Compose without backup ---
    for comp in data["composes"]:
        if not comp.get("backups"):
            findings.append(
                {
                    "category": "Backup",
                    "severity": "warning",
                    "issue": f"No backup configured for '{comp.get('name', '?')}'",
                    "resource": comp.get("name", ""),
                    "fix_command": f"kctl-dokploy backups create --compose {comp.get('composeId', '')}",
                }
            )

    # --- Wrong domainType ---
    for d in data["domains"]:
        if d.get("domainType") == "application":
            findings.append(
                {
                    "category": "Domain",
                    "severity": "high",
                    "issue": f"Wrong domainType on '{d.get('host', '?')}'",
                    "resource": d.get("_service", ""),
                    "fix_command": "Recreate domain with domainType=compose",
                }
            )

    # --- Services without domains ---
    services_with_domains = {d.get("_service", "") for d in data["domains"]}
    for comp in data["composes"]:
        comp_name = comp.get("name", "")
        if comp_name and comp_name not in services_with_domains:
            findings.append(
                {
                    "category": "Exposure",
                    "severity": "info",
                    "issue": f"Service '{comp_name}' has no domains configured",
                    "resource": comp_name,
                    "fix_command": "kctl-dokploy domains create <compose-id> --host <hostname>",
                }
            )

    # --- Admin user count ---
    try:
        users = c.client.get("/user.all")
        if not isinstance(users, list):
            users = []
    except Exception:
        users = []

    admin_count = sum(1 for u in users if u.get("rol", u.get("role", "")) == "admin")
    if admin_count > 3:
        findings.append(
            {
                "category": "Access",
                "severity": "warning",
                "issue": f"{admin_count} users with admin role (consider reducing)",
                "resource": "users",
                "fix_command": "kctl user list",
            }
        )

    # --- Output findings ---
    rows: list[list[str]] = []
    for f_ in findings:
        rows.append(
            [
                f_["category"],
                _severity_label(f_["severity"]),
                f_["issue"],
                f_["resource"],
                f_["fix_command"],
            ]
        )

    if not rows:
        c.output.success("No security findings detected")
    else:
        c.output.table(
            f"Security Audit ({len(findings)} findings)",
            [("Category", ""), ("Severity", ""), ("Issue", "cyan"), ("Resource", ""), ("Fix Command", "dim")],
            rows,
            data_for_json=findings,
        )


@app.command()
def ssl(ctx: typer.Context) -> None:
    """Detailed SSL certificate audit with expiry tracking."""
    c: AppContext = ctx.obj
    try:
        certs = c.client.get("/certificates.all")
        if not isinstance(certs, list):
            certs = []
    except Exception as exc:
        c.output.error(f"Failed to fetch certificates: {exc}")
        raise typer.Exit(1) from exc

    if not certs:
        c.output.info("No SSL certificates found")
        return

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for cert in certs:
        cert_name = cert.get("name", "unknown")
        domain = cert.get("domain", cert.get("host", "-"))
        auto_renew = "yes" if cert.get("autoRenew") else "no"
        expiry_str = cert.get("expiresAt", cert.get("expiration"))
        expiry_dt = _parse_expiry(expiry_str)

        if expiry_dt is not None:
            days = _days_until(expiry_dt)
            expiry_display = fmt_timestamp(expiry_str)
            if days < 7:
                days_display = f"[red]{days}d[/red]"
                urgency = "critical"
            elif days < 30:
                days_display = f"[yellow]{days}d[/yellow]"
                urgency = "warning"
            else:
                days_display = f"[green]{days}d[/green]"
                urgency = "ok"
        else:
            expiry_display = "-"
            days_display = "-"
            days = -1
            urgency = "unknown"

        rows.append([cert_name, domain, expiry_display, days_display, auto_renew])
        json_data.append(
            {
                "name": cert_name,
                "domain": domain,
                "expiresAt": expiry_str or "-",
                "daysUntilExpiry": days,
                "autoRenew": cert.get("autoRenew", False),
                "urgency": urgency,
                "certificateId": cert.get("certificateId", ""),
            }
        )

    c.output.table(
        "SSL Certificate Audit",
        [("Name", "cyan"), ("Domain", ""), ("Expires", ""), ("Days Left", ""), ("Auto Renew", "")],
        rows,
        data_for_json=json_data,
    )

    # --- Domain HTTPS status from all services ---
    data = collect_all_services(c.client)
    domain_rows: list[list[str]] = []
    domain_json: list[dict] = []
    for d in data["domains"]:
        host = d.get("host", "")
        has_https = d.get("https", False)
        cert_type = d.get("certificateType", "none")
        service = d.get("_service", "")
        https_display = "[green]yes[/green]" if has_https else "[red]no[/red]"
        domain_rows.append([host, https_display, cert_type, service])
        domain_json.append(
            {
                "host": host,
                "https": has_https,
                "certificateType": cert_type,
                "service": service,
            }
        )

    if domain_rows:
        c.output.table(
            f"Domain HTTPS Status ({len(domain_rows)} domains)",
            [("Host", "cyan"), ("HTTPS", ""), ("Cert Type", ""), ("Service", "green")],
            domain_rows,
            data_for_json=domain_json,
        )


@app.command()
def users(ctx: typer.Context) -> None:
    """User access review grouped by role."""
    c: AppContext = ctx.obj
    try:
        user_list = c.client.get("/user.all")
        if not isinstance(user_list, list):
            user_list = []
    except Exception as exc:
        c.output.error(f"Failed to fetch users: {exc}")
        raise typer.Exit(1) from exc

    if not user_list:
        c.output.info("No users found")
        return

    # Group by role for summary
    role_counts: dict[str, int] = {}
    for u in user_list:
        role = u.get("rol", u.get("role", "unknown"))
        role_counts[role] = role_counts.get(role, 0) + 1

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for u in user_list:
        email = u.get("email", "")
        role = u.get("rol", u.get("role", "unknown"))
        created = fmt_timestamp(u.get("createdAt"))

        # Flag users without recent activity if lastLogin is available
        last_login = u.get("lastLogin", u.get("lastActivity"))
        if last_login:
            login_dt = _parse_expiry(last_login)
            if login_dt is not None:
                inactive_days = -_days_until(login_dt)
                activity = f"{inactive_days}d ago" if inactive_days > 0 else "recent"
                if inactive_days > 90:
                    activity = f"[yellow]{inactive_days}d ago[/yellow]"
            else:
                activity = "-"
        else:
            activity = "-"

        rows.append([email, role, created, activity])
        json_data.append(
            {
                "email": email,
                "role": role,
                "createdAt": u.get("createdAt", "-"),
                "lastActivity": last_login or "-",
                "userId": u.get("userId", u.get("id", "")),
            }
        )

    # Add role summary to header
    summary_parts = [f"{role}: {count}" for role, count in sorted(role_counts.items())]
    summary = " | ".join(summary_parts)

    c.output.table(
        f"User Access Audit ({len(user_list)} users — {summary})",
        [("Email", "cyan"), ("Role", ""), ("Created", "dim"), ("Last Activity", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def config(ctx: typer.Context) -> None:
    """Check platform configuration against best practices."""
    c: AppContext = ctx.obj
    checks: list[dict] = []

    # Check 1: Backup destinations
    try:
        destinations = c.client.get("/destination.all")
        has_backups = isinstance(destinations, list) and len(destinations) > 0
    except Exception:
        has_backups = False
    checks.append(
        {
            "check": "Backup destinations configured",
            "status": "pass" if has_backups else "fail",
            "recommendation": "" if has_backups else "Configure S3 or other backup destination via kctl backup",
        }
    )

    # Check 2: Notification channels
    try:
        notifications = c.client.get("/notification.all")
        has_notifications = isinstance(notifications, list) and len(notifications) > 0
    except Exception:
        has_notifications = False
    checks.append(
        {
            "check": "Notification channels configured",
            "status": "pass" if has_notifications else "warn",
            "recommendation": "" if has_notifications else "Set up Slack/email notifications via kctl notify",
        }
    )

    # Check 3: Git provider
    try:
        git_providers = c.client.get("/gitProvider.getAll")
        has_git = isinstance(git_providers, list) and len(git_providers) > 0
    except Exception:
        has_git = False
    checks.append(
        {
            "check": "Git provider connected",
            "status": "pass" if has_git else "warn",
            "recommendation": "" if has_git else "Connect GitHub/GitLab via kctl git",
        }
    )

    # Check 4: SSH keys
    try:
        ssh_keys = c.client.get("/sshKey.all")
        has_ssh = isinstance(ssh_keys, list) and len(ssh_keys) > 0
    except Exception:
        has_ssh = False
    checks.append(
        {
            "check": "SSH keys configured",
            "status": "pass" if has_ssh else "warn",
            "recommendation": "" if has_ssh else "Add SSH keys for server access",
        }
    )

    # Check 5: Docker cleanup
    try:
        servers = c.client.get("/server.all")
        cleanup_enabled = False
        if isinstance(servers, list):
            cleanup_enabled = any(s.get("enableDockerCleanup", False) for s in servers)
    except Exception:
        cleanup_enabled = False
    checks.append(
        {
            "check": "Docker cleanup enabled",
            "status": "pass" if cleanup_enabled else "warn",
            "recommendation": "" if cleanup_enabled else "Enable automatic Docker cleanup to reclaim disk space",
        }
    )

    # --- Output ---
    rows: list[list[str]] = []
    for chk in checks:
        status = chk["status"]
        if status == "pass":
            status_display = "[green]PASS[/green]"
        elif status == "warn":
            status_display = "[yellow]WARN[/yellow]"
        else:
            status_display = "[red]FAIL[/red]"
        rows.append([chk["check"], status_display, chk["recommendation"]])

    pass_count = sum(1 for chk in checks if chk["status"] == "pass")
    total = len(checks)

    c.output.table(
        f"Configuration Audit ({pass_count}/{total} passed)",
        [("Check", "cyan"), ("Status", ""), ("Recommendation", "dim")],
        rows,
        data_for_json=checks,
    )
