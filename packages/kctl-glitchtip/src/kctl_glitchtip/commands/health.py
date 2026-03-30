"""Health and monitoring commands."""

from __future__ import annotations

import subprocess

import typer

from kctl_glitchtip.core.callbacks import AppContext
from kctl_common.exceptions import KctlError

app = typer.Typer(help="Health checks and monitoring.")


def _container_status(name: str) -> str:
    """Get Docker container health status."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "not_running"
    except Exception:
        return "unknown"


@app.command("check")
def health_check(ctx: typer.Context) -> None:
    """API health + container status."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    out.header("GlitchTip Health Check")

    # API health
    http_status = c.check_health()
    if http_status == 200:
        out.success(f"HTTP /_health/: {http_status}")
    else:
        out.error(f"HTTP /_health/: {http_status}")

    # API root
    try:
        root = c.get_api_root()
        user = root.get("user", {})
        out.success(f"API /api/0/: authenticated as {user.get('email', 'unknown')}")
    except KctlError as e:
        out.error(f"API /api/0/: {e}")

    # Container statuses
    containers = {
        "GlitchTip Web": "kodemeio-glitchtip",
        "Celery Worker": "kodemeio-glitchtip-worker",
        "Redis": "kodemeio-glitchtip-redis",
    }

    for label, container in containers.items():
        status = _container_status(container)
        if status == "healthy":
            out.success(f"{label}: {status}")
        elif status in ("unhealthy", "not_running"):
            out.error(f"{label}: {status}")
        else:
            out.warn(f"{label}: {status}")

    if out.json_mode:
        out.raw_json(
            {
                "http_health": http_status,
                "containers": {name: _container_status(cid) for name, cid in containers.items()},
            }
        )


@app.command()
def dashboard(ctx: typer.Context) -> None:
    """Overview: projects, issues, events, teams."""
    actx: AppContext = ctx.obj
    c, out = actx.client, actx.output

    out.header("GlitchTip Dashboard")

    # Get orgs
    orgs = c.get_list("organizations/")
    out.kv("Organizations", str(len(orgs)))

    json_data: dict = {"organizations": len(orgs), "details": []}

    for org in orgs:
        org_slug = org.get("slug", "")
        out.text(f"\n  [bold]{org.get('name', org_slug)}[/bold] ({org_slug})")

        # Projects
        projects = c.get_list(f"organizations/{org_slug}/projects/")
        out.kv("  Projects", str(len(projects)))

        # Teams
        teams = c.get_list(f"organizations/{org_slug}/teams/")
        out.kv("  Teams", str(len(teams)))

        # Issues
        issues = c.get_list(f"organizations/{org_slug}/issues/", params={"limit": 100})
        unresolved = sum(1 for i in issues if i.get("status") == "unresolved")
        out.kv("  Issues (unresolved)", str(unresolved))
        out.kv("  Issues (total)", str(len(issues)))

        # Members
        members = c.get_list(f"organizations/{org_slug}/members/")
        out.kv("  Members", str(len(members)))

        json_data["details"].append(
            {
                "org": org_slug,
                "projects": len(projects),
                "teams": len(teams),
                "unresolved_issues": unresolved,
                "total_issues": len(issues),
                "members": len(members),
            }
        )

    if out.json_mode:
        out.raw_json(json_data)


@app.command("celery-status")
def celery_status(ctx: typer.Context) -> None:
    """Celery worker status."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.header("Celery Worker Status")

    try:
        result = subprocess.run(
            [
                "docker",
                "exec",
                "kodemeio-glitchtip-worker",
                "celery",
                "-A",
                "glitchtip",
                "inspect",
                "active",
                "--timeout",
                "10",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            out.success("Worker responding")
            out.text(result.stdout.strip()[:1000])
        else:
            out.error(f"Worker not responding: {result.stderr.strip()}")
    except FileNotFoundError:
        out.error("Docker not found")
    except subprocess.TimeoutExpired:
        out.error("Worker inspection timed out")

    if out.json_mode:
        out.raw_json({"status": "check output above"})


@app.command("redis-info")
def redis_info(ctx: typer.Context) -> None:
    """Redis stats."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.header("Redis Info")

    sections = ["server", "memory", "keyspace"]
    redis_data: dict = {}

    for section in sections:
        try:
            result = subprocess.run(
                ["docker", "exec", "kodemeio-glitchtip-redis", "redis-cli", "INFO", section],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                out.text(f"\n[bold]{section.upper()}[/bold]")
                for line in result.stdout.strip().split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        out.text(f"  {line}")
                        if ":" in line:
                            k, v = line.split(":", 1)
                            redis_data[k] = v
        except Exception:
            out.warn(f"Could not get {section} info")

    if out.json_mode:
        out.raw_json(redis_data)
