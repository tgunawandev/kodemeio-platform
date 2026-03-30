"""Configuration drift detection commands."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.config_manager import ConfigFile
from kctl_claw.core.exceptions import DockerError

app = typer.Typer(help="Detect config drift between local and deployed container.")

_SNAPSHOTS_DIR = ".kctl-snapshots"
_CONTAINER_CONFIG_PATH = "/opt/openclaw-config/openclaw.json"
_OPENCLAW_CONTAINER = "openclaw"


def _snapshots_dir(project_root: Path) -> Path:
    return project_root / _SNAPSHOTS_DIR


def _read_container_config(actx: AppContext) -> dict | None:
    """Read openclaw.json from running container via docker exec."""
    try:
        raw = actx.docker.exec(_OPENCLAW_CONTAINER, ["cat", _CONTAINER_CONFIG_PATH])
        return json.loads(raw)
    except (DockerError, json.JSONDecodeError, AttributeError):
        return None


@app.command()
def check(ctx: typer.Context) -> None:
    """Compare local config/ vs deployed container config (summary)."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Reading local config...")
    try:
        local_cfg = actx.config_mgr.read(ConfigFile.OPENCLAW)
    except FileNotFoundError as e:
        out.error(f"Local config not found: {e}")
        raise typer.Exit(1) from e

    out.info("Reading container config...")
    remote_cfg = _read_container_config(actx)

    if remote_cfg is None:
        out.warn("Cannot read container config — container may not be running.")
        out.info("Start with: kctl-claw deploy up")
        return

    diffs = actx.config_mgr.diff(ConfigFile.OPENCLAW, remote_cfg)

    if not diffs:
        out.success("No drift detected — local and deployed configs are in sync.")
        return

    rows = [[d.path, str(d.local_value)[:40], str(d.remote_value)[:40]] for d in diffs]
    json_data = [{"path": d.path, "local": d.local_value, "remote": d.remote_value} for d in diffs]
    out.table(
        f"Config Drift ({len(diffs)} differences)",
        [("Path", "cyan"), ("Local", "green"), ("Deployed", "red")],
        rows,
        data_for_json=json_data,
    )
    out.warn(f"{len(diffs)} drift(s) found. Run 'kctl-claw config-drift diff' for full details.")

    # Suppress unused variable warning
    _ = local_cfg


@app.command()
def diff(ctx: typer.Context) -> None:
    """Show detailed diff between local and deployed container config."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        actx.config_mgr.read(ConfigFile.OPENCLAW)
    except FileNotFoundError as e:
        out.error(f"Local config not found: {e}")
        raise typer.Exit(1) from e

    out.info("Reading container config...")
    remote_cfg = _read_container_config(actx)

    if remote_cfg is None:
        out.warn("Cannot read container config — container may not be running.")
        out.info("Start with: kctl-claw deploy up")
        return

    diffs = actx.config_mgr.diff(ConfigFile.OPENCLAW, remote_cfg)

    if not diffs:
        out.success("Configs are identical — no drift.")
        return

    rows = [[d.path, str(d.local_value), str(d.remote_value)] for d in diffs]
    json_data = [{"path": d.path, "local": d.local_value, "remote": d.remote_value} for d in diffs]

    out.table(
        f"Detailed Config Diff ({len(diffs)} differences)",
        [("Path", "cyan"), ("Local Value", "green"), ("Deployed Value", "red")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def snapshot(ctx: typer.Context) -> None:
    """Save deployed container config as a local baseline snapshot."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Reading container config to snapshot...")
    remote_cfg = _read_container_config(actx)

    if remote_cfg is None:
        out.warn("Cannot read container config — container may not be running.")
        out.info("Start with: kctl-claw deploy up")
        return

    snaps_dir = _snapshots_dir(actx.project_root)
    snaps_dir.mkdir(exist_ok=True)

    ts = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    snap_path = snaps_dir / f"openclaw-{ts}.json"
    snap_path.write_text(json.dumps(remote_cfg, indent=2, ensure_ascii=False))

    out.success(f"Snapshot saved: {snap_path.relative_to(actx.project_root)}")
    out.info("Restore with: kctl-claw config-drift restore <snapshot>")


@app.command()
def restore(
    ctx: typer.Context,
    snapshot_name: Annotated[str, typer.Argument(help="Snapshot filename (basename)")],
) -> None:
    """Restore local openclaw.json from a snapshot."""
    actx: AppContext = ctx.obj
    out = actx.output

    snaps_dir = _snapshots_dir(actx.project_root)
    snap_path = snaps_dir / snapshot_name
    if not snap_path.exists():
        available = sorted(snaps_dir.glob("*.json")) if snaps_dir.exists() else []
        names = [s.name for s in available]
        out.error(f"Snapshot not found: {snapshot_name!r}")
        if names:
            out.info(f"Available: {', '.join(names)}")
        raise typer.Exit(1)

    out.warn(f"This will overwrite local openclaw.json with snapshot: {snapshot_name}")
    confirmed = typer.confirm("Proceed?")
    if not confirmed:
        out.info("Aborted.")
        return

    actx.config_mgr.backup_before_modify(ConfigFile.OPENCLAW)
    dest = actx.project_root / ConfigFile.OPENCLAW.value
    shutil.copy2(snap_path, dest)
    out.success(f"Restored openclaw.json from snapshot: {snapshot_name}")
    out.info("Apply with: kctl-claw deploy up --build")
