"""Atomic deployment orchestration with automatic rollback.

Provides a step-tracked deployment pipeline for Docker Compose applications
via Dokploy. Each step is recorded so that on failure the rollback handler
knows exactly what to undo.

Ported from lib/deploy.sh, redesigned for Python idioms.

Pipeline steps (in order):
  1. compose_upsert  - Create or find existing compose service
  2. snapshot        - Capture current state for rollback
  3. compose_file    - Upload docker-compose.yml
  4. env_update      - Update environment variables
  5. domain_config   - Configure domain routing
  6. deploy          - Trigger deployment
  7. health_check    - Verify deployment health (optional)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from kctl_dokploy.core.exceptions import DeploymentError


class DeployStep(StrEnum):
    """Deployment pipeline steps in forward order."""

    COMPOSE_UPSERT = "compose_upsert"
    SNAPSHOT = "snapshot"
    COMPOSE_FILE = "compose_file"
    ENV_UPDATE = "env_update"
    DOMAIN_CONFIG = "domain_config"
    DEPLOY = "deploy"
    HEALTH_CHECK = "health_check"


@dataclass
class DeploymentState:
    """Tracks the current deployment's state for rollback."""

    compose_id: str = ""
    domain_id: str = ""
    previous_snapshot: dict | None = None
    step: DeployStep | None = None
    is_new: bool = False


@dataclass
class DeploymentResult:
    """Result of a deployment pipeline execution."""

    success: bool
    compose_id: str = ""
    duration_seconds: float = 0.0
    steps_completed: list[str] = field(default_factory=list)
    error: str = ""
    rolled_back: bool = False


def backup_compose_state(client: Any, compose_id: str) -> dict | None:
    """Capture a JSON snapshot of the current compose configuration."""
    try:
        data = client.get("/compose.one", params={"composeId": compose_id})
        if isinstance(data, dict):
            return data
        return None
    except Exception:
        return None


def rollback_on_failure(
    client: Any,
    state: DeploymentState,
    output: Any | None = None,
) -> bool:
    """Unwind completed deployment steps in reverse order.

    Returns True if rollback succeeded (best-effort).
    """

    def _log(msg: str) -> None:
        if output:
            output.warn(msg)

    if not state.compose_id:
        _log("No compose_id in state; nothing to roll back")
        return True

    _log(f"Rolling back deployment. Failed at step: {state.step}")
    step = state.step

    try:
        # Rollback domain if it was created this run
        if step in (DeployStep.HEALTH_CHECK, DeployStep.DEPLOY, DeployStep.DOMAIN_CONFIG) and state.domain_id:
            _log(f"Removing domain {state.domain_id}")
            try:
                client.post("/domain.delete", json={"domainId": state.domain_id})
            except Exception:
                _log(f"Failed to remove domain {state.domain_id}")

        # Restore previous compose file and env if we have a snapshot
        if (
            step in (DeployStep.HEALTH_CHECK, DeployStep.DEPLOY, DeployStep.ENV_UPDATE, DeployStep.COMPOSE_FILE)
            and state.previous_snapshot
        ):
            _log("Restoring previous compose file and environment...")
            restore_payload: dict = {"composeId": state.compose_id}
            prev_file = state.previous_snapshot.get("composeFile", "")
            prev_env = state.previous_snapshot.get("env", "")
            if prev_file:
                restore_payload["composeFile"] = prev_file
                restore_payload["sourceType"] = "raw"
            if prev_env:
                restore_payload["env"] = prev_env
            try:
                client.post("/compose.update", json=restore_payload)
                # Re-deploy with previous config
                if step in (DeployStep.HEALTH_CHECK, DeployStep.DEPLOY):
                    _log("Re-deploying previous version...")
                    client.post("/compose.deploy", json={"composeId": state.compose_id})
            except Exception:
                _log("Failed to restore previous state")

        # Delete compose if it was newly created this run
        if step == DeployStep.COMPOSE_UPSERT and state.is_new:
            _log(f"Deleting newly-created compose {state.compose_id}")
            try:
                client.post("/compose.remove", json={"composeId": state.compose_id})
            except Exception:
                _log(f"Failed to delete compose {state.compose_id}")

    except Exception as e:
        _log(f"Rollback error: {e}")
        return False

    return True


def _find_or_create_compose(
    client: Any,
    name: str,
    project_id: str,
    state: DeploymentState,
) -> str:
    """Find existing compose by name in project, or create a new one."""
    # Search existing
    projects = client.get("/project.all")
    if isinstance(projects, list):
        for p in projects:
            if p.get("projectId") == project_id:
                for comp in p.get("compose", []):
                    if comp.get("name", "").lower() == name.lower():
                        state.is_new = False
                        return comp.get("composeId", "")

    # Create new
    result = client.post("/compose.create", json={"name": name, "projectId": project_id})
    compose_id = result.get("composeId", "") if isinstance(result, dict) else ""
    if not compose_id:
        raise DeploymentError(f"Failed to create compose '{name}' in project '{project_id}'")
    state.is_new = True
    return compose_id


def deploy_atomic(
    client: Any,
    output: Any,
    *,
    name: str,
    project_id: str,
    compose_file: str | Path,
    env_file: str | Path | None = None,
    env_content: str | None = None,
    domain: str | None = None,
    port: int = 80,
    https: bool = True,
    cert_type: str = "letsencrypt",
    service_name: str | None = None,
    skip_health: bool = False,
    health_fn: Any | None = None,
    notify_fn: Any | None = None,
    rollback_on_fail: bool = True,
) -> DeploymentResult:
    """Execute the full atomic deployment pipeline.

    On any failure, automatically rolls back completed steps (unless rollback_on_fail=False).
    """
    state = DeploymentState()
    start_time = time.monotonic()
    steps_completed: list[str] = []

    try:
        # Step 1: Upsert compose
        output.info(f"Step 1/6: Finding or creating compose '{name}'...")
        compose_id = _find_or_create_compose(client, name, project_id, state)
        state.compose_id = compose_id
        state.step = DeployStep.COMPOSE_UPSERT
        steps_completed.append("compose_upsert")

        # Step 2: Snapshot current state
        output.info("Step 2/6: Snapshotting current state...")
        state.previous_snapshot = backup_compose_state(client, compose_id)
        state.step = DeployStep.SNAPSHOT
        steps_completed.append("snapshot")

        # Step 3: Upload compose file
        output.info("Step 3/6: Uploading compose file...")
        file_path = Path(compose_file)
        if not file_path.exists():
            raise DeploymentError(f"Compose file not found: {compose_file}")
        file_content = file_path.read_text()
        client.post(
            "/compose.update",
            json={
                "composeId": compose_id,
                "composeFile": file_content,
                "sourceType": "raw",
            },
        )
        state.step = DeployStep.COMPOSE_FILE
        steps_completed.append("compose_file")

        # Step 4: Update environment (optional)
        if env_file or env_content:
            output.info("Step 4/6: Updating environment variables...")
            env_str = env_content or ""
            if env_file:
                env_path = Path(env_file)
                if env_path.exists():
                    env_str = env_path.read_text()
                else:
                    raise DeploymentError(f"Env file not found: {env_file}")
            client.post("/compose.update", json={"composeId": compose_id, "env": env_str})
            state.step = DeployStep.ENV_UPDATE
            steps_completed.append("env_update")
        else:
            output.info("Step 4/6: Skipping environment (not provided)")

        # Step 5: Configure domain (optional)
        if domain:
            output.info(f"Step 5/6: Configuring domain '{domain}'...")
            domain_payload: dict = {
                "composeId": compose_id,
                "host": domain,
                "port": port,
                "https": https,
                "certificateType": cert_type,
            }
            if service_name:
                domain_payload["serviceName"] = service_name
            result = client.post("/domain.create", json=domain_payload)
            state.domain_id = result.get("domainId", "") if isinstance(result, dict) else ""
            state.step = DeployStep.DOMAIN_CONFIG
            steps_completed.append("domain_config")
        else:
            output.info("Step 5/6: Skipping domain (not provided)")

        # Step 6: Trigger deployment
        output.info("Step 6/6: Triggering deployment...")
        if notify_fn:
            notify_fn("info", "Deployment Started", f"Deploying '{name}'...")
        client.post("/compose.deploy", json={"composeId": compose_id})
        state.step = DeployStep.DEPLOY
        steps_completed.append("deploy")

        # Optional: Health check
        if not skip_health and health_fn:
            output.info("Running post-deployment health check...")
            health_ok, health_msg = health_fn(client, compose_id)
            state.step = DeployStep.HEALTH_CHECK
            if not health_ok:
                raise DeploymentError(f"Health check failed: {health_msg}")
            steps_completed.append("health_check")
            output.success(f"Health check passed: {health_msg}")

        duration = time.monotonic() - start_time
        output.success(f"Deployment of '{name}' completed in {duration:.1f}s")

        if notify_fn:
            notify_fn("success", "Deployment Succeeded", f"'{name}' deployed in {duration:.1f}s")

        return DeploymentResult(
            success=True,
            compose_id=compose_id,
            duration_seconds=duration,
            steps_completed=steps_completed,
        )

    except Exception as e:
        duration = time.monotonic() - start_time
        output.error(f"Deployment failed at step '{state.step}': {e}")

        rolled_back = False
        if rollback_on_fail:
            rolled_back = rollback_on_failure(client, state, output)

        if notify_fn:
            notify_fn("failure", "Deployment Failed", f"'{name}' failed: {e}")

        return DeploymentResult(
            success=False,
            compose_id=state.compose_id,
            duration_seconds=duration,
            steps_completed=steps_completed,
            error=str(e),
            rolled_back=rolled_back,
        )
