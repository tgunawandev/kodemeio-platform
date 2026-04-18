"""Deployment manifest apply/setup/run/post/status/list commands.

Split into stages for resilience:
  - setup: DNS + DB + compose + env + domain (idempotent, no deploy)
  - run:   trigger deploy + wait for healthy
  - post:  backup + schedules + post-deploy hooks
  - apply: all three stages in sequence
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from pydantic import ValidationError

from kctl_dokploy.core.callbacks import AppContext
from kctl_dokploy.core.deployer import Deployer, PhaseResult
from kctl_dokploy.core.manifest import DeployManifest, load_and_resolve

app = typer.Typer(help="Declarative deployment from YAML manifests.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print_summary(c: AppContext, title: str, results: list[PhaseResult]) -> bool:
    """Print results table. Return True if any phase failed."""
    rows = []
    json_data = []
    for r in results:
        rows.append([r.phase, r.action, r.message])
        json_data.append({"phase": r.phase, "action": r.action, "message": r.message})

    c.output.table(
        title,
        [("Phase", "cyan"), ("Action", ""), ("Details", "dim")],
        rows,
        data_for_json=json_data,
    )
    return any(r.action == "failed" for r in results)


def _load(file: Path, c: AppContext) -> DeployManifest:
    try:
        return load_and_resolve(file)
    except Exception as exc:
        c.output.error(f"Failed to load manifest: {exc}")
        raise typer.Exit(1) from exc


# ---------------------------------------------------------------------------
# Validate manifest
# ---------------------------------------------------------------------------


@app.command()
def validate(
    ctx: typer.Context,
    file: Annotated[Path, typer.Option("--file", "-f", help="Manifest YAML file", exists=True)] = ...,  # type: ignore[assignment]
) -> None:
    """Validate a deploy manifest without deploying.

    Loads the manifest, resolves base extends and interpolation, and reports
    validation results. Exits 0 on success, 1 on validation failure.
    """
    c: AppContext = ctx.obj
    out = c.output

    try:
        manifest = load_and_resolve(file)
    except ValidationError as exc:
        out.error("Manifest validation failed:")
        errors = exc.errors()
        rows = []
        json_errors = []
        for err in errors:
            field_path = " -> ".join(str(loc) for loc in err["loc"])
            msg = err["msg"]
            rows.append([field_path, err["type"], msg])
            json_errors.append({"field": field_path, "type": err["type"], "message": msg})

        out.table(
            "Validation Errors",
            [("Field", "cyan"), ("Type", "yellow"), ("Message", "")],
            rows,
            data_for_json=json_errors,
        )
        raise typer.Exit(1) from exc
    except Exception as exc:
        out.error(f"Failed to load manifest: {exc}")
        raise typer.Exit(1) from exc

    # Build summary data
    summary = {
        "file": str(file),
        "instance": manifest.instance.name,
        "type": manifest.type,
        "domain": manifest.domain.host if manifest.domain else "-",
        "project": manifest.project,
        "server": manifest.server,
        "extends": manifest.extends or "-",
        "has_backup": manifest.backup is not None,
        "schedules": len(manifest.schedules),
        "env_file": manifest.env_file or "-",
    }

    out.table(
        f"Manifest Valid: {file.name}",
        [("Property", "cyan"), ("Value", "")],
        [[k, str(v)] for k, v in summary.items()],
        data_for_json=summary,
    )
    out.success(f"Manifest is valid: {manifest.instance.name} ({manifest.type})")


# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------


@app.command()
def preflight(
    ctx: typer.Context,
    file: Annotated[Path, typer.Option("--file", "-f", help="Manifest YAML file", exists=True)] = ...,  # type: ignore[assignment]
    gates: Annotated[str | None, typer.Option("--gates", "-g", help="Comma-separated gate names to run")] = None,
) -> None:
    """Run preflight checks before deployment.

    Validates server connectivity, firewall, DNS, database auth,
    env file sync, and more. Any FAIL blocks deployment.

    Use --gates to run only specific checks, e.g. --gates dns,ssl
    """
    from kctl_dokploy.core.preflight import run_preflight

    c: AppContext = ctx.obj
    manifest = _load(file, c)

    api_client = None
    try:
        api_client = c.client
    except Exception:
        pass

    gate_list = [g.strip() for g in gates.split(",")] if gates else None
    results = run_preflight(manifest, client=api_client, gates=gate_list)

    # Build display
    status_icons = {"pass": "✓", "warn": "⚠", "fail": "✗"}
    rows = []
    json_data = []
    for r in results:
        icon = status_icons.get(r.status, "?")
        rows.append([f"{icon} Gate: {r.gate}", r.status.upper(), r.message])
        json_data.append({"gate": r.gate, "status": r.status, "message": r.message})

    server_info = manifest.server or "(Dokploy host)"
    c.output.table(
        f"Preflight: {manifest.instance.name} → {server_info}",
        [("Gate", "cyan"), ("Status", ""), ("Details", "dim")],
        rows,
        data_for_json=json_data,
    )

    failures = [r for r in results if r.failed]
    warns = [r for r in results if r.status == "warn"]

    if failures:
        c.output.error(f"PREFLIGHT FAILED: {len(failures)} gate(s) failed")
        raise typer.Exit(1)
    elif warns:
        c.output.warn(f"PREFLIGHT PASSED with {len(warns)} warning(s)")
    else:
        c.output.success("PREFLIGHT PASSED: all gates clear")


@app.command(name="preflight-all")
def preflight_all(
    ctx: typer.Context,
    directory: Annotated[
        Path, typer.Option("--dir", "-d", help="Directory with manifest YAML files", exists=True)
    ] = ...,  # type: ignore[assignment]
    server: Annotated[str | None, typer.Option("--server", "-s", help="Filter by server name")] = None,
    gates: Annotated[str | None, typer.Option("--gates", "-g", help="Comma-separated gate names to run")] = None,
) -> None:
    """Run preflight checks on all manifests in a directory.

    Use --server to filter to manifests targeting a specific server.
    Use --gates to run only specific checks, e.g. --gates dns,ssl
    """
    c: AppContext = ctx.obj
    manifests = sorted(directory.glob("*.yaml"))
    if not manifests:
        c.output.warn(f"No manifests found in {directory}")
        raise typer.Exit(0)

    from kctl_dokploy.core.preflight import run_preflight

    api_client = None
    try:
        api_client = c.client
    except Exception:
        pass

    gate_list = [g.strip() for g in gates.split(",")] if gates else None
    total_pass = 0
    total_fail = 0
    total_warn = 0

    for mf in manifests:
        try:
            manifest = load_and_resolve(mf)
        except Exception as exc:
            c.output.error(f"{mf.name}: Failed to load — {exc}")
            total_fail += 1
            continue

        if server and manifest.server != server:
            continue

        results = run_preflight(manifest, client=api_client, gates=gate_list)
        failures = [r for r in results if r.failed]
        warns = [r for r in results if r.status == "warn"]

        if failures:
            c.output.error(f"✗ {manifest.instance.name}: {len(failures)} FAIL")
            for f in failures:
                c.output.info(f"    {f.gate}: {f.message}")
            total_fail += 1
        elif warns:
            c.output.warn(f"⚠ {manifest.instance.name}: {len(warns)} warnings")
            total_warn += 1
        else:
            c.output.success(f"✓ {manifest.instance.name}")
            total_pass += 1

    c.output.info(f"\nResults: {total_pass} pass, {total_warn} warn, {total_fail} fail")
    if total_fail > 0:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Troubleshoot
# ---------------------------------------------------------------------------


@app.command()
def troubleshoot(
    ctx: typer.Context,
    file: Annotated[Path | None, typer.Option("--file", "-f", help="Manifest YAML file", exists=True)] = None,
    compose_id: Annotated[str | None, typer.Option("--compose", "-c", help="Compose service ID")] = None,
) -> None:
    """Diagnose why a deployment failed.

    Checks deployment status, container logs, health endpoints, and
    classifies the error with suggested fixes. Provide either a manifest
    file or a compose ID.
    """
    from kctl_dokploy.core.troubleshoot import diagnose

    c: AppContext = ctx.obj

    if not file and not compose_id:
        c.output.error("Provide --file or --compose")
        raise typer.Exit(1)

    # Get API client
    try:
        api_client = c.client
    except Exception as exc:
        c.output.error(f"Cannot connect to Dokploy: {exc}")
        raise typer.Exit(1) from exc

    # Resolve compose_id from manifest if needed
    domain = ""
    health_path = "/"
    expected_status = 200
    if file:
        manifest = _load(file, c)
        domain = manifest.domain.host if manifest.domain else ""
        health_path = manifest.healthcheck.path
        expected_status = manifest.healthcheck.expected_status

        if not compose_id:
            # Find compose by instance name
            try:
                projects = api_client.get("/project.all")
                for p in projects if isinstance(projects, list) else []:
                    if p.get("name", "").lower() == manifest.project.lower():
                        for env in p.get("environments", []):
                            for comp in env.get("compose", []):
                                if comp.get("name") == manifest.instance.name:
                                    compose_id = comp.get("composeId")
                                    break
            except Exception:
                pass

        if not compose_id:
            c.output.error(
                f"Cannot find compose service for '{manifest.instance.name}' in project '{manifest.project}'"
            )
            raise typer.Exit(1)

    result = diagnose(
        client=api_client,
        compose_id=compose_id,
        domain=domain,
        health_path=health_path,
        expected_status=expected_status,
    )

    # Display diagnosis
    status_icon = {
        "build_failed": "🔨",
        "runtime_crash": "💥",
        "health_timeout": "⏱",
        "config_error": "⚙",
        "not_deployed": "○",
        "unknown": "?",
    }
    icon = status_icon.get(result.error_type.value, "?")

    rows = []
    json_data = result.to_dict()

    rows.append(["Error Type", f"{icon} {result.error_type.value.upper()}"])
    rows.append(["Summary", result.summary])
    rows.append(["Deploy Status", result.deployment_status])
    rows.append(["Health", result.health_status])

    c.output.table(
        f"Diagnosis: {result.service_name}",
        [("Check", "cyan"), ("Result", "")],
        rows,
        data_for_json=json_data,
    )

    # Containers
    if result.containers:
        ct_rows = []
        for ct in result.containers:
            state_icon = "✓" if ct.state == "running" else "✗"
            ct_rows.append([f"{state_icon} {ct.name}", ct.state, ct.status])
        c.output.table(
            "Containers",
            [("Name", "cyan"), ("State", ""), ("Status", "dim")],
            ct_rows,
        )

    # Container logs for crashed containers
    for ct in result.containers:
        if ct.logs and ct.state in ("exited", "dead", "restarting"):
            c.output.header(f"Logs: {ct.name}")
            c.output.text(ct.logs[-2000:])  # Last 2000 chars

    # Build log if available
    if result.deployment_log and result.deployment_status == "error":
        c.output.header("Build Log (last lines)")
        c.output.text(str(result.deployment_log)[-2000:])

    # Suggestions
    if result.suggestions:
        c.output.header("Suggested Fixes")
        for i, s in enumerate(result.suggestions, 1):
            c.output.text(f"  {i}. {s}")

    if result.error_type.value != "unknown":
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Stage: setup (DNS + DB + compose + env + domain)
# ---------------------------------------------------------------------------


@app.command()
def setup(
    ctx: typer.Context,
    file: Annotated[Path, typer.Option("--file", "-f", help="Instance manifest YAML", exists=True)] = ...,  # type: ignore[assignment]
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview changes")] = False,
) -> None:
    """Stage 1: Infrastructure setup — DNS, database, compose, env, domain.

    Idempotent and safe to re-run. Does NOT trigger a deploy.
    """
    c: AppContext = ctx.obj
    manifest = _load(file, c)
    mode = " [dry-run]" if dry_run else ""
    c.output.info(f"Setup: {manifest.instance.name}{mode}")

    deployer = Deployer(manifest=manifest, dry_run=dry_run)
    deployer.phase_dns()
    deployer.phase_database()
    deployer.phase_registry()
    deployer.phase_compose()
    deployer.phase_environment()
    deployer.phase_domain()

    has_failures = _print_summary(c, f"Setup: {manifest.instance.name}", deployer.results)
    if has_failures:
        c.output.error("Setup failed — fix errors before running deploy.")
        sys.exit(1)
    else:
        c.output.success(f"Setup complete. Run: kctl-dokploy deploy run -f {file}")


# ---------------------------------------------------------------------------
# Stage: run (deploy + verify)
# ---------------------------------------------------------------------------


@app.command()
def run(
    ctx: typer.Context,
    file: Annotated[Path, typer.Option("--file", "-f", help="Instance manifest YAML", exists=True)] = ...,  # type: ignore[assignment]
    skip_verify: Annotated[bool, typer.Option("--skip-verify", help="Skip healthcheck")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview changes")] = False,
) -> None:
    """Stage 2: Deploy + verify — trigger redeploy and wait for healthy.

    Requires setup to have been run first (compose must exist).
    """
    c: AppContext = ctx.obj
    manifest = _load(file, c)
    c.output.info(f"Deploy: {manifest.instance.name}")

    deployer = Deployer(manifest=manifest, dry_run=dry_run)

    # Need to find existing compose_id
    deployer.phase_compose()  # This will find or update existing compose
    deployer.phase_deploy()
    if not skip_verify:
        deployer.phase_verify()

    has_failures = _print_summary(c, f"Deploy: {manifest.instance.name}", deployer.results)
    if has_failures:
        c.output.error("Deploy failed — check logs with: kctl-dokploy deployments logs --compose <id>")
        sys.exit(1)
    else:
        c.output.success(f"Deploy complete. Run: kctl-dokploy deploy post -f {file}")


# ---------------------------------------------------------------------------
# Stage: post (backup + schedules + post-deploy hooks)
# ---------------------------------------------------------------------------


@app.command()
def post(
    ctx: typer.Context,
    file: Annotated[Path, typer.Option("--file", "-f", help="Instance manifest YAML", exists=True)] = ...,  # type: ignore[assignment]
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview changes")] = False,
) -> None:
    """Stage 3: Post-deploy — backup config, schedules, Odoo bundle install.

    Safe to re-run. Requires compose to exist and be deployed.
    """
    c: AppContext = ctx.obj
    manifest = _load(file, c)
    c.output.info(f"Post-deploy: {manifest.instance.name}")

    deployer = Deployer(manifest=manifest, dry_run=dry_run)

    # Find existing compose_id
    deployer.phase_compose()
    deployer.phase_backup()
    deployer.phase_schedules()
    deployer.phase_volume_backups()
    try:
        deployer.phase_post_deploy()
    except RuntimeError:
        pass  # Already recorded as failed in results

    # Filter out the compose phase from summary (it's just for ID resolution)
    results = [r for r in deployer.results if r.phase != "compose"]
    has_failures = _print_summary(c, f"Post-deploy: {manifest.instance.name}", results)
    if has_failures:
        c.output.error("Post-deploy had failures.")
        sys.exit(1)
    else:
        c.output.success("Post-deploy complete.")


# ---------------------------------------------------------------------------
# All-in-one: apply (setup + run + post)
# ---------------------------------------------------------------------------


@app.command()
def apply(
    ctx: typer.Context,
    file: Annotated[Path, typer.Option("--file", "-f", help="Instance manifest YAML", exists=True)] = ...,  # type: ignore[assignment]
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview changes")] = False,
    skip_deploy: Annotated[bool, typer.Option("--skip-deploy", help="Run setup only, skip deploy")] = False,
    skip_verify: Annotated[bool, typer.Option("--skip-verify", help="Skip healthcheck")] = False,
    skip_preflight: Annotated[
        bool, typer.Option("--skip-preflight", help="Skip preflight checks (emergency only)")
    ] = False,
) -> None:
    """All-in-one: setup + deploy + post-deploy in sequence."""
    c: AppContext = ctx.obj
    manifest = _load(file, c)
    mode = " [dry-run]" if dry_run else ""
    c.output.info(f"Applying manifest: {manifest.instance.name}{mode}")

    deployer = Deployer(manifest=manifest, dry_run=dry_run, skip_preflight=skip_preflight)

    # Stage 0: Preflight
    deployer.phase_preflight()
    if any(r.action == "failed" and r.phase == "preflight" for r in deployer.results):
        _print_summary(c, f"Preflight Failed: {manifest.instance.name}", deployer.results)
        c.output.error("Preflight failed — fix issues before deploying.")
        sys.exit(1)

    # Stage 1: Setup
    deployer.phase_dns()
    deployer.phase_database()
    deployer.phase_registry()
    deployer.phase_compose()
    deployer.phase_environment()
    deployer.phase_domain()

    # Check critical setup failures before proceeding (compose/env/domain are blockers)
    critical_phases = {"compose", "environment", "domain"}
    critical_failed = any(r.action == "failed" and r.phase in critical_phases for r in deployer.results)
    if critical_failed and not dry_run:
        _print_summary(c, f"Setup Failed: {manifest.instance.name}", deployer.results)
        c.output.error("Critical setup phase failed — stopping before deploy.")
        sys.exit(1)

    # Stage 2: Deploy
    if not skip_deploy:
        deployer.phase_deploy()
        if not skip_verify:
            deployer.phase_verify()

    # Stage 3: Post-deploy
    deployer.phase_backup()
    deployer.phase_schedules()
    deployer.phase_volume_backups()
    try:
        deployer.phase_post_deploy()
    except RuntimeError:
        pass  # Already recorded as failed in results

    has_failures = _print_summary(c, f"Deployment Summary: {manifest.instance.name}", deployer.results)
    if has_failures:
        c.output.error("One or more phases failed.")
        sys.exit(1)
    else:
        c.output.success("All phases completed successfully.")


# ---------------------------------------------------------------------------
# Batch: apply-all
# ---------------------------------------------------------------------------


@app.command("apply-all")
def apply_all(
    ctx: typer.Context,
    dir: Annotated[Path, typer.Option("--dir", "-d", help="Directory with manifests")] = Path("deploys/instances"),
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview changes")] = False,
) -> None:
    """Apply all manifests in a directory sequentially."""
    c: AppContext = ctx.obj

    if not dir.is_dir():
        c.output.error(f"Directory not found: {dir}")
        raise typer.Exit(1)

    files = sorted(list(dir.glob("*.yaml")) + list(dir.glob("*.yml")))
    if not files:
        c.output.warn(f"No YAML manifests found in {dir}")
        return

    c.output.info(f"Found {len(files)} manifest(s) in {dir}")
    any_failed = False

    for f in files:
        c.output.header(f"--- {f.name} ---")
        try:
            manifest = load_and_resolve(f)
        except Exception as exc:
            c.output.error(f"Failed to load {f.name}: {exc}")
            any_failed = True
            continue

        deployer = Deployer(manifest=manifest, dry_run=dry_run)
        deployer.phase_validate()
        if any(r.action == "failed" for r in deployer.results):
            c.output.error(f"{f.name}: validation FAILED")
            any_failed = True
            continue
        deployer.phase_dns()
        deployer.phase_database()
        deployer.phase_registry()
        deployer.phase_compose()
        deployer.phase_environment()
        deployer.phase_domain()
        deployer.phase_deploy()
        deployer.phase_verify()
        deployer.phase_backup()
        deployer.phase_schedules()
        deployer.phase_volume_backups()
        try:
            deployer.phase_post_deploy()
        except RuntimeError:
            pass  # Already recorded as failed in results

        if any(r.action == "failed" for r in deployer.results):
            c.output.error(f"{f.name}: FAILED")
            any_failed = True
        else:
            c.output.success(f"{f.name}: OK")

    if any_failed:
        sys.exit(1)


# ---------------------------------------------------------------------------
# Status & list
# ---------------------------------------------------------------------------


@app.command()
def status(
    ctx: typer.Context,
    file: Annotated[Path, typer.Option("--file", "-f", help="Instance manifest YAML", exists=True)] = ...,  # type: ignore[assignment]
) -> None:
    """Check current state vs manifest (dry-run preview)."""
    c: AppContext = ctx.obj
    manifest = _load(file, c)
    c.output.info(f"Status: {manifest.instance.name} [dry-run]")

    deployer = Deployer(manifest=manifest, dry_run=True)
    deployer.phase_dns()
    deployer.phase_database()
    deployer.phase_registry()
    deployer.phase_compose()
    deployer.phase_environment()
    deployer.phase_domain()
    deployer.phase_deploy()
    deployer.phase_verify()
    deployer.phase_backup()
    deployer.phase_schedules()
    deployer.phase_volume_backups()
    try:
        deployer.phase_post_deploy()
    except RuntimeError:
        pass  # Already recorded as failed in results

    _print_summary(c, f"Status: {manifest.instance.name}", deployer.results)


@app.command()
def verify(
    ctx: typer.Context,
    file: Annotated[Path, typer.Option("--file", "-f", help="Manifest YAML file", exists=True)] = ...,  # type: ignore[assignment]
) -> None:
    """Run pre-deploy validation and post-deploy smoke tests.

    Checks that the deployment configuration is correct and that the
    deployed service is healthy beyond just the healthcheck.
    """
    c: AppContext = ctx.obj
    manifest = _load(file, c)

    # Build merged env (same logic as phase_pre_validate in deployer)
    merged: dict[str, str] = dict(manifest.env_defaults)
    if manifest.env_file:
        env_path = Path(manifest.env_file)
        if env_path.exists():
            from kctl_dokploy.core.manifest import load_env_file

            merged.update(load_env_file(env_path))
    merged.update(manifest.env_overrides)

    from kctl_dokploy.core.deploy_validators import DeployValidator

    validator = DeployValidator(manifest=manifest, env_vars=merged)

    c.output.info(f"Verifying: {manifest.instance.name} (type: {validator.deploy_type})")

    # Pre-validate
    warnings, errors = validator.pre_validate()
    rows: list[list[str]] = []
    json_data: list[dict[str, str]] = []
    for e in errors:
        rows.append(["pre-validate", "FAIL", e])
        json_data.append({"check": "pre-validate", "status": "FAIL", "detail": e})
    for w in warnings:
        rows.append(["pre-validate", "WARN", w])
        json_data.append({"check": "pre-validate", "status": "WARN", "detail": w})
    if not errors and not warnings:
        rows.append(["pre-validate", "PASS", "All checks passed"])
        json_data.append({"check": "pre-validate", "status": "PASS", "detail": "All checks passed"})

    # Post-verify (smoke tests)
    smoke = validator.post_verify()
    for r in smoke:
        rows.append([r.name, r.status.upper(), r.detail])
        json_data.append({"check": r.name, "status": r.status.upper(), "detail": r.detail})

    c.output.table(
        f"Verification: {manifest.instance.name}",
        [("Check", "cyan"), ("Status", "yellow"), ("Detail", "")],
        rows,
        data_for_json=json_data,
    )

    fail_count = sum(1 for r in rows if r[1] == "FAIL")
    warn_count = sum(1 for r in rows if r[1] == "WARN")
    if fail_count:
        c.output.error(f"{fail_count} check(s) failed, {warn_count} warning(s)")
        raise typer.Exit(1)
    elif warn_count:
        c.output.warn(f"All passed with {warn_count} warning(s)")
    else:
        c.output.success("All checks passed")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all instance manifests and their status."""
    c: AppContext = ctx.obj
    deploy_dir = Path("deploys/instances")
    if not deploy_dir.is_dir():
        c.output.warn("No deploys/instances/ directory found")
        return

    files = sorted(list(deploy_dir.glob("*.yaml")) + list(deploy_dir.glob("*.yml")))
    if not files:
        c.output.warn("No YAML manifests found in deploys/instances/")
        return

    rows = []
    for f in files:
        try:
            m = load_and_resolve(f)
            rows.append([f.name, m.instance.name, m.type, m.domain.host if m.domain else "-"])
        except Exception as e:
            rows.append([f.name, "ERROR", "-", str(e)[:50]])

    c.output.table(
        f"Deployment Manifests ({len(rows)})",
        [("File", "dim"), ("Instance", "cyan"), ("Type", ""), ("Domain", "green")],
        rows,
    )


# ---------------------------------------------------------------------------
# apply-local (Phase 4: dokploy-local-domains)
# ---------------------------------------------------------------------------


@app.command(name="apply-local")
def apply_local(
    ctx: typer.Context,
    file: Annotated[
        Path, typer.Option("--file", "-f", help="Local instance manifest (deploys/instances/local/*.yaml)", exists=True)
    ] = ...,  # type: ignore[assignment]
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview DNS reconcile only; no Dokploy mutations")
    ] = False,
) -> None:
    """Apply a local-only instance manifest.

    Converges:
      1. Cloudflare wildcard DNS records → current LAN IP.
      2. Dokploy project / environment / compose service exists with
         the manifest's source config.
      3. env_file contents pushed to the compose service.
      4. Dokploy domain attached with ``cert_type=none`` (falls through
         to Traefik's default wildcard cert).

    Refuses manifests whose ``environment`` is not ``local`` with exit code 2.
    """
    from kctl_dokploy.core.lan_ip import current_lan_ipv4
    from kctl_dokploy.core.local_reconciler import (
        KctlCfDnsAdapter,
        LocalDokployAdapter,
        LocalReconciler,
    )

    c: AppContext = ctx.obj
    manifest = _load(file, c)

    if manifest.environment != "local":
        c.output.error(
            f"{file}: environment={manifest.environment!r}, expected 'local' "
            "(use `deploy apply` for non-local manifests)"
        )
        raise typer.Exit(code=2)

    if not manifest.domain or not manifest.domain.host.endswith(".local.kodeme.io"):
        host = manifest.domain.host if manifest.domain else ""
        c.output.error(f"{file}: domain.host={host!r} must end with '.local.kodeme.io'")
        raise typer.Exit(code=2)

    reconciler = LocalReconciler(
        dns=KctlCfDnsAdapter(profile=c.profile or "kodemeio"),
        dokploy=LocalDokployAdapter(client=c.client),
        lan_ip_getter=current_lan_ipv4,
        zone="kodeme.io",
    )

    if dry_run:
        c.output.info("[dry-run] only DNS reconcile is safe to preview; skipping compose/env/domain")
        dns_r = reconciler.reconcile_dns()
        for m in dns_r.messages:
            c.output.info(m)
        c.output.success(f"[dry-run] DNS changed={dns_r.changed}")
        return

    outcome = reconciler.apply(manifest)
    for m in outcome.messages:
        c.output.info(m)
    c.output.success(f"apply-local complete. changed={outcome.changed}")


# ---------------------------------------------------------------------------
# Migrate sub-app
# ---------------------------------------------------------------------------

from kctl_dokploy.commands.migrate import app as migrate_app  # noqa: E402

app.add_typer(migrate_app, name="migrate", help="Server-to-server migration pipeline.")
