"""Deployment manifest apply/status/list commands."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext
from kctl_dokploy.core.deployer import Deployer
from kctl_dokploy.core.manifest import DeployManifest, load_and_resolve

app = typer.Typer(help="Apply deployment manifests to Dokploy.")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PHASE_ORDER = [
    "dns",
    "database",
    "registry",
    "compose",
    "environment",
    "domain",
    "deploy",
    "verify",
    "backup",
    "schedules",
    "post_deploy",
]

_ACTION_COLOR: dict[str, str] = {
    "created": "green",
    "updated": "cyan",
    "skipped": "dim",
    "failed": "red",
}


def _run_phases(
    deployer: Deployer,
    skip_deploy: bool = False,
    skip_verify: bool = False,
) -> None:
    """Execute all phases individually, honouring skip flags."""
    deployer.phase_dns()
    deployer.phase_database()
    deployer.phase_registry()
    deployer.phase_compose()
    deployer.phase_environment()
    deployer.phase_domain()
    if not skip_deploy:
        deployer.phase_deploy()
    if not skip_verify:
        deployer.phase_verify()
    deployer.phase_backup()
    deployer.phase_schedules()
    deployer.phase_post_deploy()


def _print_summary(c: AppContext, deployer: Deployer) -> bool:
    """Print a results table. Return True if any phase failed."""
    rows = []
    json_data = []
    for result in deployer.results:
        action_color = _ACTION_COLOR.get(result.action, "")
        rows.append([result.phase, result.action, result.message])
        json_data.append(
            {
                "phase": result.phase,
                "action": result.action,
                "message": result.message,
            }
        )

    c.output.table(
        "Deployment Summary",
        [("Phase", "cyan"), ("Action", action_color), ("Message", "")],
        rows,
        data_for_json=json_data,
    )

    failed = [r for r in deployer.results if r.action == "failed"]
    return bool(failed)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def apply(
    ctx: typer.Context,
    file: Annotated[Path, typer.Option("--file", "-f", help="Path to deploy manifest YAML", exists=True)] = ...,  # type: ignore[assignment]
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Simulate without mutating state")] = False,
    skip_deploy: Annotated[bool, typer.Option("--skip-deploy", help="Skip the deploy phase")] = False,
    skip_verify: Annotated[bool, typer.Option("--skip-verify", help="Skip the healthcheck verify phase")] = False,
) -> None:
    """Apply a deployment manifest, running all phases in order."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        manifest = load_and_resolve(file)
    except Exception as exc:
        out.error(f"Failed to load manifest: {exc}")
        raise typer.Exit(1) from exc

    instance_name = manifest.instance.name or file.stem
    mode = " [dry-run]" if dry_run else ""
    out.info(f"Applying manifest: {instance_name}{mode}")

    deployer = Deployer(manifest=manifest, dry_run=dry_run)
    _run_phases(deployer, skip_deploy=skip_deploy, skip_verify=skip_verify)

    has_failures = _print_summary(c, deployer)
    if has_failures:
        out.error("One or more phases failed.")
        sys.exit(1)
    else:
        out.success("All phases completed successfully.")


@app.command()
def status(
    ctx: typer.Context,
    file: Annotated[Path, typer.Option("--file", "-f", help="Path to deploy manifest YAML", exists=True)] = ...,  # type: ignore[assignment]
) -> None:
    """Show deployment status by running all phases in dry-run mode."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        manifest = load_and_resolve(file)
    except Exception as exc:
        out.error(f"Failed to load manifest: {exc}")
        raise typer.Exit(1) from exc

    instance_name = manifest.instance.name or file.stem
    out.info(f"Checking status for: {instance_name} [dry-run]")

    deployer = Deployer(manifest=manifest, dry_run=True)
    _run_phases(deployer)
    _print_summary(c, deployer)


@app.command("apply-all")
def apply_all(
    ctx: typer.Context,
    dir: Annotated[Path, typer.Option("--dir", "-d", help="Directory containing manifest YAML files")] = Path(
        "deploys/instances"
    ),
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Simulate without mutating state")] = False,
) -> None:
    """Apply all deployment manifests found in a directory."""
    c: AppContext = ctx.obj
    out = c.output

    if not dir.is_dir():
        out.error(f"Directory not found: {dir}")
        raise typer.Exit(1)

    manifests = sorted(list(dir.glob("*.yaml")) + list(dir.glob("*.yml")))
    if not manifests:
        out.warn(f"No YAML manifests found in {dir}")
        return

    out.info(f"Found {len(manifests)} manifest(s) in {dir}")
    any_failed = False

    for manifest_path in manifests:
        out.info(f"--- {manifest_path.name} ---")
        try:
            manifest = load_and_resolve(manifest_path)
        except Exception as exc:
            out.error(f"Failed to load {manifest_path.name}: {exc}")
            any_failed = True
            continue

        deployer = Deployer(manifest=manifest, dry_run=dry_run)
        _run_phases(deployer)
        has_failures = _print_summary(c, deployer)
        if has_failures:
            any_failed = True

    if any_failed:
        out.error("One or more manifests had failures.")
        sys.exit(1)
    else:
        out.success(f"All {len(manifests)} manifest(s) completed successfully.")


@app.command("list")
def list_(
    ctx: typer.Context,
) -> None:
    """List all deployment manifests found in deploys/instances/."""
    c: AppContext = ctx.obj
    out = c.output

    instances_dir = Path("deploys/instances")
    if not instances_dir.is_dir():
        out.warn(f"Directory not found: {instances_dir}")
        return

    manifests = sorted(list(instances_dir.glob("*.yaml")) + list(instances_dir.glob("*.yml")))
    if not manifests:
        out.warn(f"No YAML manifests found in {instances_dir}")
        return

    rows = []
    json_data = []

    for manifest_path in manifests:
        try:
            manifest: DeployManifest = load_and_resolve(manifest_path)
            instance_name = manifest.instance.name or manifest_path.stem
            mtype = manifest.type
            domain = manifest.domain.host or "-"
        except Exception as exc:
            instance_name = manifest_path.stem
            mtype = "error"
            domain = str(exc)

        rows.append([manifest_path.name, instance_name, mtype, domain])
        json_data.append(
            {
                "file": manifest_path.name,
                "instance": instance_name,
                "type": mtype,
                "domain": domain,
            }
        )

    out.table(
        "Deployment Manifests",
        [("File", "dim"), ("Instance Name", "cyan"), ("Type", ""), ("Domain", "green")],
        rows,
        data_for_json=json_data,
    )
