"""CI/CD pipeline commands."""

from __future__ import annotations

from datetime import UTC, datetime

import typer

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.config_manager import ConfigFile
from kctl_claw.core.exceptions import DockerError, GatewayError

app = typer.Typer(help="CI/CD pipeline: validate, deploy, status, history.")

_GATEWAY_HINT = "Start the gateway first: kctl-claw deploy up"


@app.command()
def validate(ctx: typer.Context) -> None:
    """Validate all configs before deployment."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Validating all configs...")
    results: list[tuple[str, str, str]] = []

    for cfg_name, cfg_file in [
        ("openclaw.json", ConfigFile.OPENCLAW),
        ("config.json (MCP)", ConfigFile.MCP_REGISTRY),
        ("cron/jobs.json", ConfigFile.CRON_JOBS),
    ]:
        errors = actx.config_mgr.validate_json(cfg_file)
        if errors:
            for err in errors:
                results.append((cfg_name, "FAIL", err))
        else:
            results.append((cfg_name, "OK", "Valid"))

    # Skills directory check
    skills_dir = actx.project_root / "config" / "skills"
    if skills_dir.exists():
        skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir()]
        missing_skill_md = [d.name for d in skill_dirs if not (d / "SKILL.md").exists()]
        if missing_skill_md:
            results.append(("skills", "WARN", f"Missing SKILL.md: {', '.join(missing_skill_md[:3])}"))
        else:
            results.append(("skills", "OK", f"{len(skill_dirs)} skill(s) valid"))
    else:
        results.append(("skills", "WARN", "config/skills/ directory not found"))

    rows = [[name, status, detail] for name, status, detail in results]
    json_data = [{"check": name, "status": status, "detail": detail} for name, status, detail in results]

    failures = [r for r in results if r[1] == "FAIL"]
    out.table(
        f"Validation ({len(results)} checks, {len(failures)} failed)",
        [("Config", "cyan"), ("Status", ""), ("Detail", "dim")],
        rows,
        data_for_json=json_data,
    )

    if failures:
        out.error(f"Validation failed: {len(failures)} error(s). Fix before deploying.")
        raise typer.Exit(1)
    else:
        out.success("All configs validated — ready to deploy.")


@app.command()
def deploy(ctx: typer.Context) -> None:
    """Run the full deployment pipeline: validate -> build -> up."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Starting deployment pipeline...")

    # Step 1: Validate
    out.info("Step 1/3: Validating configs...")
    validation_ok = True
    for cfg_file in [ConfigFile.OPENCLAW, ConfigFile.MCP_REGISTRY, ConfigFile.CRON_JOBS]:
        errors = actx.config_mgr.validate_json(cfg_file)
        if errors:
            for err in errors:
                out.error(f"  {cfg_file.value}: {err}")
            validation_ok = False

    if not validation_ok:
        out.error("Validation failed. Aborting deployment.")
        raise typer.Exit(1)
    out.success("Step 1/3: Validation passed.")

    # Step 2: Build
    out.info("Step 2/3: Building container...")
    try:
        actx.docker.up(build=True)
        out.success("Step 2/3: Build and start complete.")
    except DockerError as e:
        out.error(f"Step 2/3: Docker error: {e}")
        raise typer.Exit(1) from e

    # Step 3: Health check
    out.info("Step 3/3: Running health check...")
    import time

    time.sleep(3)  # Brief wait for gateway to start
    try:
        actx.gateway.health()
        out.success("Step 3/3: Gateway is healthy.")
    except GatewayError as e:
        out.warn(f"Step 3/3: Gateway not yet reachable: {e}")
        out.info("Gateway may still be starting. Check with: kctl-claw health check")

    out.success("Deployment pipeline complete.")


@app.command()
def status(ctx: typer.Context) -> None:
    """Show current deployment status."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Checking deployment status...")
    results: list[tuple[str, str, str]] = []

    # Docker container status
    try:
        ps_output = actx.docker.ps()
        running = "running" in ps_output.lower() if ps_output else False
        results.append(
            ("container", "UP" if running else "DOWN", ps_output.split("\n")[0] if ps_output else "no output")
        )
    except DockerError as e:
        results.append(("container", "ERROR", str(e)[:60]))

    # Gateway health
    try:
        data = actx.gateway.health()
        version = data.get("version", "?") if isinstance(data, dict) else "?"
        results.append(("gateway", "OK", f"version={version}"))
    except GatewayError as e:
        results.append(("gateway", "DOWN", str(e)[:60]))

    # Config loaded
    try:
        openclaw = actx.config_mgr.read(ConfigFile.OPENCLAW)
        version = openclaw.get("version", "?")
        agent_count = len(openclaw.get("agents", {}).get("list", []))
        results.append(("config", "OK", f"v{version}, {agent_count} agents"))
    except Exception as e:
        results.append(("config", "ERROR", str(e)[:60]))

    rows = [[name, status, detail] for name, status, detail in results]
    json_data = [{"component": name, "status": status, "detail": detail} for name, status, detail in results]

    out.table(
        "Deployment Status",
        [("Component", "cyan"), ("Status", ""), ("Detail", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def history(ctx: typer.Context) -> None:
    """Show deployment history from gateway API."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Fetching deployment history...")
    try:
        data = actx.gateway.get("/api/deployments/history")
        if isinstance(data, list):
            rows = [
                [
                    str(d.get("id", ""))[:8],
                    str(d.get("deployed_at", "")),
                    str(d.get("version", "")),
                    str(d.get("status", "")),
                ]
                for d in data
            ]
            out.table(
                f"Deployment History ({len(data)})",
                [("ID", "dim"), ("Deployed At", "cyan"), ("Version", ""), ("Status", "")],
                rows,
                data_for_json=data,
            )
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)
        # Show local fallback: current config version
        try:
            openclaw = actx.config_mgr.read(ConfigFile.OPENCLAW)
            version = openclaw.get("version", "unknown")
            ts = datetime.now(tz=UTC).isoformat()
            out.info(f"Local config version: {version} (as of {ts})")
        except Exception:
            pass
