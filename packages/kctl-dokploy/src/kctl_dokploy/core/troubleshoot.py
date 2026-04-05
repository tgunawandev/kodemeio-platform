"""Deployment failure diagnosis engine.

Provides a single `diagnose()` function that investigates why a deployment
failed by checking deployment history, container status, container logs,
and health endpoints. Returns a structured Diagnosis with error classification
and suggested fixes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx


class ErrorType(StrEnum):
    BUILD_FAILED = "build_failed"
    RUNTIME_CRASH = "runtime_crash"
    HEALTH_TIMEOUT = "health_timeout"
    CONFIG_ERROR = "config_error"
    NOT_DEPLOYED = "not_deployed"
    UNKNOWN = "unknown"


@dataclass
class ContainerInfo:
    """Status of a single Docker container."""

    name: str
    state: str  # running, exited, created, restarting
    status: str  # e.g. "Up 2 minutes", "Exited (1) 5 minutes ago"
    logs: str = ""  # Last N lines of container logs


@dataclass
class Diagnosis:
    """Result of diagnosing a deployment failure."""

    compose_id: str
    service_name: str
    error_type: ErrorType
    summary: str  # One-line summary of what went wrong
    details: str  # Multi-line details

    # Evidence gathered
    deployment_status: str = ""  # Latest deployment status from Dokploy
    deployment_log: str = ""  # Build/deployment log excerpt
    containers: list[ContainerInfo] = field(default_factory=list)
    health_status: str = ""  # Health endpoint result

    # Suggested actions
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "compose_id": self.compose_id,
            "service_name": self.service_name,
            "error_type": self.error_type.value,
            "summary": self.summary,
            "details": self.details,
            "deployment_status": self.deployment_status,
            "deployment_log": self.deployment_log,
            "containers": [
                {"name": c.name, "state": c.state, "status": c.status, "logs": c.logs} for c in self.containers
            ],
            "health_status": self.health_status,
            "suggestions": self.suggestions,
        }


def _get_deployment_info(client: Any, compose_id: str) -> tuple[str, str, str]:
    """Get latest deployment status, title, and log content.

    Returns (status, title, log_text).
    """
    try:
        deps = client.get("/deployment.allByCompose", params={"composeId": compose_id})
        if not isinstance(deps, list) or not deps:
            return "none", "No deployments found", ""

        # Sort newest first
        sorted_deps = sorted(deps, key=lambda d: d.get("createdAt", ""), reverse=True)
        latest = sorted_deps[0]

        status = latest.get("status", "unknown")
        title = latest.get("title", "")

        # Try to get log content — logPath is a server file path, not directly readable
        # But some deployments store inline log content
        log = latest.get("logPath", "")

        return status, title, log
    except Exception as e:
        return "error", f"Failed to fetch deployments: {e}", ""


def _get_containers(client: Any, compose_id: str) -> list[ContainerInfo]:
    """Get container status and logs for a compose service."""
    containers: list[ContainerInfo] = []

    try:
        # Get compose details for appName and serverId
        compose = client.get("/compose.one", params={"composeId": compose_id})
        if not isinstance(compose, dict):
            return containers

        app_name = compose.get("appName", "")
        server_id = compose.get("serverId")

        if not app_name:
            return containers

        # Get all containers, optionally filtered by server
        params: dict[str, str] = {}
        if server_id:
            params["serverId"] = server_id

        all_containers = client.get("/docker.getContainers", params=params)
        if not isinstance(all_containers, list):
            return containers

        # Filter to containers matching this compose
        matching = [c for c in all_containers if app_name in c.get("name", "")]

        for ct in matching:
            name = ct.get("name", "")
            state = ct.get("state", "unknown")
            status = ct.get("status", "")

            # Fetch container logs via API
            log_text = ""
            try:
                log_data = client.post(
                    "/docker.getContainerLogs",
                    json={"containerId": name, "tail": 50},
                )
                if isinstance(log_data, dict):
                    log_text = str(log_data.get("logs", log_data.get("data", "")))
                elif isinstance(log_data, str):
                    log_text = log_data
                elif isinstance(log_data, list):
                    log_text = "\n".join(str(line) for line in log_data)
                else:
                    log_text = str(log_data) if log_data else ""
            except Exception:
                log_text = "(failed to fetch logs)"

            containers.append(
                ContainerInfo(
                    name=name,
                    state=state,
                    status=status,
                    logs=log_text,
                )
            )
    except Exception:
        pass

    return containers


def _check_health(domain: str, path: str = "/", expected_status: int = 200) -> str:
    """Check health endpoint. Returns status description."""
    if not domain:
        return "No domain configured"

    url = f"https://{domain}{path}"
    try:
        resp = httpx.get(url, timeout=10.0, follow_redirects=True, verify=False)
        if resp.status_code == expected_status:
            return f"OK ({resp.status_code})"
        return f"FAIL: {url} → {resp.status_code} (expected {expected_status})"
    except httpx.ConnectError:
        return f"FAIL: Cannot connect to {url}"
    except httpx.TimeoutException:
        return f"FAIL: Timeout connecting to {url}"
    except Exception as e:
        return f"FAIL: {url} → {e}"


def _classify_error(
    deployment_status: str,
    deployment_title: str,
    containers: list[ContainerInfo],
    health_status: str,
) -> tuple[ErrorType, str, list[str]]:
    """Classify the error type and generate suggestions.

    Returns (error_type, summary, suggestions).
    """
    # Check 1: Build failed
    if deployment_status == "error":
        title_lower = deployment_title.lower()
        if any(kw in title_lower for kw in ["build", "dockerfile", "npm", "yarn", "pip"]):
            return (
                ErrorType.BUILD_FAILED,
                f"Build failed: {deployment_title[:100]}",
                [
                    "Check the Dockerfile and build commands",
                    "Verify all dependencies are available",
                    "Run: kctl-dokploy deploy troubleshoot -f <manifest> for full logs",
                ],
            )
        return (
            ErrorType.BUILD_FAILED,
            f"Deployment error: {deployment_title[:100]}",
            [
                "Check deployment logs for the specific error",
                "Verify compose file syntax is correct",
                "Check that the source repository and branch exist",
            ],
        )

    # Check 2: No containers at all
    if not containers:
        if deployment_status == "none":
            return (
                ErrorType.NOT_DEPLOYED,
                "Service has never been deployed",
                [
                    "Run: kctl-dokploy deploy apply -f <manifest>",
                    "Check that the compose service exists in Dokploy",
                ],
            )
        return (
            ErrorType.UNKNOWN,
            "No containers found (deployment may still be starting)",
            [
                "Wait a moment and check again",
                "Verify the compose service exists in Dokploy",
            ],
        )

    # Check 3: Containers crashed/restarting
    crashed = [c for c in containers if c.state in ("exited", "dead")]
    restarting = [c for c in containers if c.state == "restarting"]

    if crashed or restarting:
        # Look for common error patterns in logs
        all_logs = "\n".join(c.logs for c in (crashed + restarting) if c.logs)
        error_patterns: dict[str, tuple[str, list[str]]] = {
            "ECONNREFUSED": (
                "Database connection refused",
                [
                    "Check PGHOST, PGPORT, PGUSER env vars",
                    "Verify database is running and accessible",
                ],
            ),
            "password authentication failed": (
                "Database auth failed",
                [
                    "Check PGPASSWORD env var",
                    "Verify database user credentials",
                ],
            ),
            "MODULE_NOT_FOUND": (
                "Missing Node.js module",
                [
                    "Run npm install / pnpm install",
                    "Check package.json dependencies",
                ],
            ),
            "ModuleNotFoundError": (
                "Missing Python module",
                [
                    "Check requirements.txt / pyproject.toml",
                    "Verify Docker image has all dependencies",
                ],
            ),
            "FATAL": (
                "Fatal error in application",
                ["Check application logs for the specific error"],
            ),
            "OOMKilled": (
                "Out of memory",
                [
                    "Increase memory limits in compose file",
                    "Check for memory leaks",
                ],
            ),
            "permission denied": (
                "Permission error",
                [
                    "Check file permissions in Docker image",
                    "Verify volume mounts",
                ],
            ),
            "address already in use": (
                "Port conflict",
                [
                    "Check if another service is using the same port",
                    "Verify port configuration",
                ],
            ),
            "no such file or directory": (
                "Missing file/path",
                [
                    "Check volume mounts and file paths",
                    "Verify Docker image contains required files",
                ],
            ),
        }

        for pattern, (desc, fixes) in error_patterns.items():
            if pattern.lower() in all_logs.lower():
                container_name = (crashed + restarting)[0].name
                return (
                    ErrorType.RUNTIME_CRASH,
                    f"{desc} in {container_name}",
                    fixes,
                )

        container_names = ", ".join(c.name for c in (crashed + restarting))
        return (
            ErrorType.RUNTIME_CRASH,
            f"Container(s) crashed: {container_names}",
            [
                "Check container logs above for the specific error",
                "Verify all environment variables are set correctly",
                "Check database connectivity and credentials",
            ],
        )

    # Check 4: Containers running but health check fails
    if health_status.startswith("FAIL"):
        running = [c for c in containers if c.state == "running"]
        if running:
            return (
                ErrorType.HEALTH_TIMEOUT,
                f"Containers running but health check failed: {health_status}",
                [
                    "Check the health endpoint path and port in the manifest",
                    "Verify the application is listening on the correct port",
                    "Check Traefik domain routing configuration",
                    "Container may still be starting — wait and retry",
                ],
            )

    # Check 5: Config issues (containers running, health OK, but something else wrong)
    if health_status.startswith("OK"):
        return (
            ErrorType.UNKNOWN,
            "Service appears healthy — no obvious errors detected",
            [
                "Service may have recovered after a transient failure",
                "Check application-level logs for business logic errors",
            ],
        )

    return (
        ErrorType.UNKNOWN,
        "Could not determine failure cause",
        [
            "Check deployment logs and container logs above",
            "Verify environment variables and database connectivity",
            "Try redeploying: kctl-dokploy compose redeploy <compose-id>",
        ],
    )


def diagnose(
    client: Any,
    compose_id: str,
    domain: str = "",
    health_path: str = "/",
    expected_status: int = 200,
) -> Diagnosis:
    """Run full diagnosis on a compose service.

    Gathers deployment status, container info, logs, and health check results,
    then classifies the error and suggests fixes.

    Args:
        client: DokployClient instance.
        compose_id: Dokploy compose service ID.
        domain: Domain hostname for health check (optional).
        health_path: Health check path (default: /).
        expected_status: Expected HTTP status code (default: 200).

    Returns:
        Diagnosis with error classification and evidence.
    """
    # Step 1: Get service name
    service_name = compose_id
    try:
        compose = client.get("/compose.one", params={"composeId": compose_id})
        if isinstance(compose, dict):
            service_name = compose.get("name", compose_id)
    except Exception:
        pass

    # Step 2: Get deployment info
    dep_status, dep_title, dep_log = _get_deployment_info(client, compose_id)

    # Step 3: Get container info + logs
    containers = _get_containers(client, compose_id)

    # Step 4: Health check
    health = _check_health(domain, health_path, expected_status)

    # Step 5: Classify error
    error_type, summary, suggestions = _classify_error(dep_status, dep_title, containers, health)

    # Build details text
    details_parts = []
    details_parts.append(f"Deployment status: {dep_status}")
    if dep_title:
        details_parts.append(f"Last deployment: {dep_title}")
    details_parts.append(f"Health: {health}")
    details_parts.append(f"Containers: {len(containers)}")
    for c in containers:
        details_parts.append(f"  {c.name}: {c.state} ({c.status})")
        if c.logs and c.state in ("exited", "dead", "restarting"):
            # Include last 10 lines of logs for crashed containers
            log_lines = c.logs.strip().splitlines()[-10:]
            details_parts.append("  Recent logs:")
            for line in log_lines:
                details_parts.append(f"    {line}")

    return Diagnosis(
        compose_id=compose_id,
        service_name=service_name,
        error_type=error_type,
        summary=summary,
        details="\n".join(details_parts),
        deployment_status=dep_status,
        deployment_log=dep_log,
        containers=containers,
        health_status=health,
        suggestions=suggestions,
    )
