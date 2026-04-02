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
    deployer.phase_post_deploy()

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
    deployer.phase_post_deploy()

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
        deployer.phase_post_deploy()

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
    deployer.phase_post_deploy()

    _print_summary(c, f"Status: {manifest.instance.name}", deployer.results)


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
