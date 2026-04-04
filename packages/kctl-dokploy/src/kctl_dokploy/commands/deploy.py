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
) -> None:
    """All-in-one: setup + deploy + post-deploy in sequence."""
    c: AppContext = ctx.obj
    manifest = _load(file, c)
    mode = " [dry-run]" if dry_run else ""
    c.output.info(f"Applying manifest: {manifest.instance.name}{mode}")

    deployer = Deployer(manifest=manifest, dry_run=dry_run)

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
