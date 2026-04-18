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

if False:  # TYPE_CHECKING — avoid circular import at runtime
    from kctl_dokploy.core.manifest import DeployManifest  # noqa: F401


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


# ---------------------------------------------------------------------------
# Reconciler helpers — added for `deploy apply-local` (Phase 4).
#
# Thin wrappers around the Dokploy HTTP API so the LocalReconciler can stay
# declarative. Each returns a reconcile-style dict with `changed` (+ ids)
# so callers can OR results together.
# ---------------------------------------------------------------------------


def ensure_project_and_env(client: Any, manifest: Any) -> dict[str, Any]:
    """Ensure the manifest's project + environment exist; return their IDs.

    Creates the environment under an existing project if it doesn't exist
    yet. Returns ``{"project_id": str, "environment_id": str, "changed": bool}``.
    """
    changed = False
    project_name = manifest.project
    env_name = manifest.environment or "production"

    projects = client.get("/project.all")
    project_data: dict[str, Any] | None = None
    if isinstance(projects, list):
        for p in projects:
            if p.get("name") == project_name:
                project_data = p
                break
    if project_data is None:
        raise DeploymentError(f"Project {project_name!r} not found in Dokploy")

    project_id = project_data.get("projectId", "")
    env_id = ""
    default_env_id = ""
    for env in project_data.get("environments", []) or []:
        if env.get("isDefault"):
            default_env_id = env.get("environmentId", "")
        if (env.get("name") or "").lower() == env_name.lower():
            env_id = env.get("environmentId", "")
            break

    if not env_id and env_name.lower() != "production":
        result = client.post(
            "/environment.create",
            json={
                "projectId": project_id,
                "name": env_name,
                "description": f"{env_name} environment",
            },
        )
        env_id = result.get("environmentId", "") if isinstance(result, dict) else ""
        changed = True

    if not env_id:
        env_id = default_env_id

    if not env_id:
        raise DeploymentError(f"Could not resolve or create environment {env_name!r} in project {project_name!r}")

    return {"project_id": project_id, "environment_id": env_id, "changed": changed}


def ensure_compose_service(
    client: Any,
    manifest: Any,
    env_info: dict[str, Any],
) -> dict[str, Any]:
    """Ensure the compose service exists under *env_info['environment_id']*.

    Returns ``{"changed": bool, "compose_id": str}``.
    """
    instance_name = manifest.instance.name
    env_id = env_info["environment_id"]

    # Look for an existing compose with this name in the environment.
    projects = client.get("/project.all")
    if isinstance(projects, list):
        for p in projects:
            for env in p.get("environments", []) or []:
                if env.get("environmentId") != env_id:
                    continue
                for comp in env.get("compose", []) or []:
                    if (comp.get("name") or "").lower() == instance_name.lower():
                        return {"changed": False, "compose_id": comp.get("composeId", "")}

    # Create a new compose in this environment.
    result = client.post(
        "/compose.create",
        json={"name": instance_name, "environmentId": env_id},
    )
    compose_id = result.get("composeId", "") if isinstance(result, dict) else ""
    if not compose_id:
        raise DeploymentError(f"Failed to create compose {instance_name!r} in env {env_id!r}")
    return {"changed": True, "compose_id": compose_id}


def push_env_file(
    client: Any,
    compose_id: str,
    env_file_path: Any,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Push the contents of *env_file_path* to the compose service's env.

    Returns ``{"changed": bool, "count": int}``. When *env_file_path* is
    ``None`` or missing, returns ``{"changed": False, "count": 0}``.
    """
    if env_file_path is None:
        return {"changed": False, "count": 0}
    path = Path(env_file_path)
    if not path.exists():
        raise DeploymentError(f"Env file not found: {env_file_path}")

    new_content = path.read_text()

    # Read current env, skip if unchanged (unless forced).
    current = ""
    try:
        snap = client.get("/compose.one", params={"composeId": compose_id})
        if isinstance(snap, dict):
            current = snap.get("env", "") or ""
    except Exception:
        current = ""

    if not force and current == new_content:
        count = sum(1 for line in new_content.splitlines() if line.strip() and not line.strip().startswith("#"))
        return {"changed": False, "count": count}

    client.post("/compose.update", json={"composeId": compose_id, "env": new_content})
    count = sum(1 for line in new_content.splitlines() if line.strip() and not line.strip().startswith("#"))
    return {"changed": True, "count": count}


def list_domains_for_compose(client: Any, compose_id: str) -> list[dict[str, Any]]:
    """Return domains attached to *compose_id*, normalized to reconciler keys.

    Dokploy's wire format uses camelCase (``certificateType``, ``serviceName``);
    the reconciler compares snake_case. This helper translates so
    :meth:`LocalReconciler.reconcile_domain` can do direct dict comparisons.
    """
    data = client.get("/domain.byComposeId", params={"composeId": compose_id})
    if not isinstance(data, list):
        return []
    out: list[dict[str, Any]] = []
    for d in data:
        if not isinstance(d, dict):
            continue
        out.append(
            {
                "domain_id": d.get("domainId", ""),
                "composeId": d.get("composeId", compose_id),
                "host": d.get("host", ""),
                "port": d.get("port", 0),
                "https": bool(d.get("https")),
                "cert_type": d.get("certificateType", "none"),
                "service_name": d.get("serviceName", ""),
            }
        )
    return out


def create_domain(
    client: Any,
    *,
    compose_id: str,
    host: str,
    port: int,
    service_name: str,
    https: bool = True,
    cert_type: str = "none",
) -> dict[str, Any]:
    """Create a Dokploy domain on *compose_id* with the given spec."""
    payload = {
        "composeId": compose_id,
        "host": host,
        "port": port,
        "https": https,
        "certificateType": cert_type,
        "serviceName": service_name,
        "domainType": "compose",
    }
    result = client.post("/domain.create", json=payload)
    return result if isinstance(result, dict) else {}


def update_domain(
    client: Any,
    *,
    domain_id: str,
    host: str | None = None,
    port: int | None = None,
    service_name: str | None = None,
    https: bool | None = None,
    cert_type: str | None = None,
) -> dict[str, Any]:
    """Update fields on an existing Dokploy domain.

    The Dokploy API requires ``host`` on every update; if not provided,
    the current host is read and re-sent.
    """
    current = client.get("/domain.one", params={"domainId": domain_id})
    if not isinstance(current, dict):
        raise DeploymentError(f"Domain {domain_id!r} not found")

    payload: dict[str, Any] = {
        "domainId": domain_id,
        "host": host if host is not None else current.get("host", ""),
    }
    if port is not None:
        payload["port"] = port
    if https is not None:
        payload["https"] = https
    if cert_type is not None:
        payload["certificateType"] = cert_type
    if service_name is not None:
        payload["serviceName"] = service_name

    result = client.post("/domain.update", json=payload)
    return result if isinstance(result, dict) else {}
