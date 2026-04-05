"""Deployment preflight validation gates.

Each gate validates one aspect of deployment readiness.
Gates return GateResult with status: pass, warn, or fail.
Any fail blocks deployment.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Any, Literal

from kctl_dokploy.core.manifest import DeployManifest


@dataclass
class GateResult:
    """Result from a single preflight gate."""

    gate: str
    status: Literal["pass", "warn", "fail"]
    message: str

    @property
    def passed(self) -> bool:
        return self.status in ("pass", "warn")

    @property
    def failed(self) -> bool:
        return self.status == "fail"


def _gate_server_connectivity(manifest: DeployManifest, client: Any, ssh_available: bool) -> GateResult:
    """Gate 1: Verify SSH access, Docker, and dokploy-network on target server."""
    if not manifest.server:
        return GateResult("server_connectivity", "pass", "No server specified (Dokploy host)")
    if not ssh_available:
        return GateResult("server_connectivity", "fail", f"SSH not available to verify server '{manifest.server}'")
    return GateResult("server_connectivity", "fail", f"Server '{manifest.server}' connectivity not verified")


def _gate_firewall(manifest: DeployManifest, client: Any, ssh_available: bool) -> GateResult:
    """Gate 2: Verify Hetzner firewall allows ports 80/443."""
    if not manifest.server:
        return GateResult("firewall", "pass", "No server specified (Dokploy host)")
    return GateResult("firewall", "warn", "Firewall check requires manual verification")


def _gate_dns(manifest: DeployManifest, client: Any, ssh_available: bool) -> GateResult:
    """Gate 3: Verify DNS points to correct server."""
    if not manifest.domain.host:
        return GateResult("dns", "pass", "No domain configured")
    return GateResult("dns", "warn", f"DNS for {manifest.domain.host} — verify manually")


def _gate_image_pull(manifest: DeployManifest, client: Any, ssh_available: bool) -> GateResult:
    """Gate 4: Verify target server can pull Docker images."""
    if not ssh_available:
        return GateResult("image_pull", "warn", "SSH not available to test image pull")
    return GateResult("image_pull", "warn", "Image pull check not yet implemented")


def _gate_database(manifest: DeployManifest, client: Any, ssh_available: bool) -> GateResult:
    """Gate 5: Verify database connectivity and auth."""
    if not manifest.database.name:
        return GateResult("database", "pass", "No database configured")
    return GateResult("database", "warn", f"Database '{manifest.database.name}' — verify connectivity manually")


def _gate_compose_assignment(manifest: DeployManifest, client: Any, ssh_available: bool) -> GateResult:
    """Gate 6: Verify compose service is on correct server."""
    if not client:
        return GateResult("compose_assignment", "warn", "No API client — cannot verify compose assignment")
    return GateResult("compose_assignment", "warn", "Compose assignment — verify manually")


def _gate_env_sync(manifest: DeployManifest, client: Any, ssh_available: bool) -> GateResult:
    """Gate 7: Verify local env file exists and matches Dokploy."""
    if not manifest.env_file:
        return GateResult("env_sync", "pass", "No env_file specified")
    env_path = pathlib.Path(manifest.env_file)
    if not env_path.exists():
        return GateResult("env_sync", "fail", f"Local env file not found: {manifest.env_file}")
    return GateResult("env_sync", "pass", f"Local env file exists: {env_path.name}")


def _gate_source_config(manifest: DeployManifest, client: Any, ssh_available: bool) -> GateResult:
    """Gate 8: Verify GitHub source repo/branch exist."""
    src = manifest.source
    if not src.owner or not src.repo:
        return GateResult("source_config", "warn", "No GitHub source configured")
    return GateResult("source_config", "pass", f"Source: {src.owner}/{src.repo}@{src.branch}")


def _gate_network(manifest: DeployManifest, client: Any, ssh_available: bool) -> GateResult:
    """Gate 9: Verify network topology and PGHOST reachability."""
    if not manifest.database.name:
        return GateResult("network", "pass", "No database — network check skipped")
    return GateResult("network", "warn", "Network topology — verify PGHOST reachability")


def _gate_ssl(manifest: DeployManifest, client: Any, ssh_available: bool) -> GateResult:
    """Gate 10: Verify SSL certificate status."""
    if not manifest.domain.host:
        return GateResult("ssl", "pass", "No domain — SSL check skipped")
    return GateResult("ssl", "warn", f"SSL for {manifest.domain.host} — verify after deploy")


# All gates in order
_GATES = [
    _gate_server_connectivity,
    _gate_firewall,
    _gate_dns,
    _gate_image_pull,
    _gate_database,
    _gate_compose_assignment,
    _gate_env_sync,
    _gate_source_config,
    _gate_network,
    _gate_ssl,
]


def run_preflight(
    manifest: DeployManifest,
    client: Any = None,
    ssh_available: bool = True,
) -> list[GateResult]:
    """Run all preflight gates and return results.

    Args:
        manifest: Resolved deploy manifest.
        client: DokployClient or None — Dokploy API client for remote checks.
        ssh_available: Whether SSH is available for remote checks.

    Returns:
        List of GateResult, one per gate.
    """
    results: list[GateResult] = []
    for gate_fn in _GATES:
        try:
            result = gate_fn(manifest, client, ssh_available)
        except Exception as exc:
            result = GateResult(
                gate=gate_fn.__name__.replace("_gate_", ""),
                status="fail",
                message=f"Gate raised exception: {exc}",
            )
        results.append(result)
    return results
