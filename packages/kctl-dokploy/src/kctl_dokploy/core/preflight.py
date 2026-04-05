"""Deployment preflight validation gates.

Each gate validates one aspect of deployment readiness.
Gates return GateResult with status: pass, warn, or fail.
Any fail blocks deployment.
"""

from __future__ import annotations

import datetime
import json
import pathlib
import socket
import ssl
import subprocess
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
    if not client:
        return GateResult("server_connectivity", "warn", "No API client — cannot resolve server")

    from kctl_dokploy.core.validators import resolve_server_ip

    ok, msg, ip = resolve_server_ip(client, manifest.server)
    if not ok:
        return GateResult("server_connectivity", "fail", msg)

    if ssh_available:
        try:
            proc = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no", f"root@{ip}", "docker --version"],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            return GateResult("server_connectivity", "fail", f"SSH to {ip} timed out")
        if proc.returncode != 0:
            return GateResult("server_connectivity", "fail", f"SSH to {ip} failed or Docker not installed")

        try:
            proc2 = subprocess.run(
                [
                    "ssh",
                    "-o",
                    "ConnectTimeout=5",
                    "-o",
                    "StrictHostKeyChecking=no",
                    f"root@{ip}",
                    "docker network inspect dokploy-network",
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            return GateResult("server_connectivity", "fail", f"SSH network check on {ip} timed out")
        if proc2.returncode != 0:
            return GateResult(
                "server_connectivity",
                "fail",
                f"dokploy-network not found on {manifest.server}",
            )
        return GateResult(
            "server_connectivity",
            "pass",
            f"Server {manifest.server} ({ip}): SSH OK, Docker OK, dokploy-network OK",
        )

    return GateResult("server_connectivity", "pass", f"Server '{manifest.server}' resolved to {ip}")


def _gate_firewall(manifest: DeployManifest, client: Any, ssh_available: bool) -> GateResult:
    """Gate 2: Verify Hetzner firewall allows ports 80/443."""
    if not manifest.server:
        return GateResult("firewall", "pass", "No server specified (Dokploy host)")

    try:
        proc = subprocess.run(
            ["kctl-hz", "firewall", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return GateResult("firewall", "warn", "Could not check Hetzner firewalls (kctl-hz not available)")
    if proc.returncode != 0:
        return GateResult("firewall", "warn", "Could not check Hetzner firewalls (kctl-hz not configured?)")

    try:
        firewalls = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        return GateResult("firewall", "warn", "Could not parse firewall list")

    count = len(firewalls) if isinstance(firewalls, list) else 0
    return GateResult("firewall", "warn", f"Firewall check: {count} firewall(s) found — verify 80/443 manually")


def _gate_dns(manifest: DeployManifest, client: Any, ssh_available: bool) -> GateResult:
    """Gate 3: Verify DNS points to correct server."""
    if not manifest.domain.host:
        return GateResult("dns", "pass", "No domain configured")

    server_ip = ""
    if client and manifest.server:
        from kctl_dokploy.core.validators import resolve_server_ip

        ok, _, server_ip = resolve_server_ip(client, manifest.server)

    try:
        resolved_ip = socket.gethostbyname(manifest.domain.host)
    except socket.gaierror:
        return GateResult("dns", "fail", f"DNS lookup failed for {manifest.domain.host}")

    if server_ip and resolved_ip != server_ip:
        return GateResult(
            "dns",
            "fail",
            f"DNS mismatch: {manifest.domain.host} → {resolved_ip}, expected {server_ip}",
        )
    if server_ip:
        return GateResult("dns", "pass", f"DNS OK: {manifest.domain.host} → {resolved_ip} (matches server)")
    return GateResult("dns", "pass", f"DNS resolves: {manifest.domain.host} → {resolved_ip}")


def _gate_image_pull(manifest: DeployManifest, client: Any, ssh_available: bool) -> GateResult:
    """Gate 4: Verify GitHub source repo and branch are accessible."""
    src = manifest.source
    if not src.owner or not src.repo:
        return GateResult("image_pull", "warn", "No source configured — skipping image pull check")

    try:
        proc = subprocess.run(
            ["git", "ls-remote", "--heads", f"https://github.com/{src.owner}/{src.repo}.git", src.branch or "main"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return GateResult("image_pull", "warn", "git not available or timed out")
    if proc.returncode != 0:
        return GateResult("image_pull", "fail", f"Cannot access repo {src.owner}/{src.repo}")
    if not proc.stdout.strip():
        return GateResult(
            "image_pull",
            "fail",
            f"Branch '{src.branch or 'main'}' not found in {src.owner}/{src.repo}",
        )
    return GateResult(
        "image_pull",
        "pass",
        f"Source accessible: {src.owner}/{src.repo}@{src.branch or 'main'}",
    )


def _gate_database(manifest: DeployManifest, client: Any, ssh_available: bool) -> GateResult:
    """Gate 5: Verify database connectivity and auth."""
    if not manifest.database.name:
        return GateResult("database", "pass", "No database configured")

    # Try kctl-pg db test first
    try:
        proc = subprocess.run(
            ["kctl-pg", "db", "test", manifest.database.name, "--json"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode == 0:
            return GateResult("database", "pass", f"Database '{manifest.database.name}' is accessible")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: check if DB exists in the list
    try:
        proc2 = subprocess.run(
            ["kctl-pg", "db", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc2.returncode == 0:
            dbs = json.loads(proc2.stdout)
            db_names = [d.get("name", d.get("datname", "")) for d in dbs] if isinstance(dbs, list) else []
            if manifest.database.name in db_names:
                return GateResult("database", "pass", f"Database '{manifest.database.name}' exists")
            return GateResult(
                "database",
                "warn",
                f"Database '{manifest.database.name}' not found (will be created during deploy)",
            )
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
        pass

    return GateResult(
        "database",
        "warn",
        f"Could not verify database '{manifest.database.name}' (kctl-pg not configured?)",
    )


def _gate_compose_assignment(manifest: DeployManifest, client: Any, ssh_available: bool) -> GateResult:
    """Gate 6: Verify compose service is on correct server."""
    if not client:
        return GateResult("compose_assignment", "warn", "No API client — cannot verify compose assignment")

    try:
        projects = client.get("/project.all")
        target_project = None
        for p in projects:
            if p.get("name", "").lower() == manifest.project.lower():
                target_project = p
                break
        if not target_project:
            return GateResult(
                "compose_assignment",
                "warn",
                f"Project '{manifest.project}' not found in Dokploy (will be created)",
            )

        # Search for compose with matching name across environments
        for env in target_project.get("environments", []):
            for compose in env.get("compose", []):
                if compose.get("name") == manifest.instance.name:
                    if manifest.server:
                        servers = client.get("/server.all")
                        target_server_id = None
                        for s in servers:
                            if s.get("name") == manifest.server:
                                target_server_id = s.get("serverId")
                                break
                        compose_server_id = compose.get("serverId")
                        if target_server_id and compose_server_id != target_server_id:
                            return GateResult(
                                "compose_assignment",
                                "fail",
                                f"Compose '{manifest.instance.name}' is on wrong server, expected '{manifest.server}'",
                            )
                    return GateResult(
                        "compose_assignment",
                        "pass",
                        f"Compose '{manifest.instance.name}' found in correct project",
                    )

        return GateResult(
            "compose_assignment",
            "warn",
            f"Compose '{manifest.instance.name}' not found (will be created)",
        )
    except Exception as e:
        return GateResult("compose_assignment", "warn", f"Could not verify compose: {e}")


def _gate_env_sync(manifest: DeployManifest, client: Any, ssh_available: bool) -> GateResult:
    """Gate 7: Verify local env file exists, and OIDC credentials are valid."""
    if not manifest.env_file:
        return GateResult("env_sync", "pass", "No env_file specified")

    env_path = pathlib.Path(manifest.env_file)
    if not env_path.exists():
        return GateResult("env_sync", "fail", f"Local env file not found: {manifest.env_file}")

    # Parse env file
    env_vars: dict[str, str] = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env_vars[key.strip()] = value.strip()

    # Check OIDC credentials if auth mode is oidc
    auth_mode = env_vars.get("VITE_AUTH_MODE", "")
    if auth_mode == "oidc":
        # Find any OIDC_CLIENT_ID and OIDC_REDIRECT_URI vars
        client_id_keys = [k for k in env_vars if "OIDC_CLIENT_ID" in k]
        redirect_keys = [k for k in env_vars if "OIDC_REDIRECT_URI" in k]

        empty_client_ids = [k for k in client_id_keys if not env_vars[k]]
        empty_redirects = [k for k in redirect_keys if not env_vars[k]]

        if empty_client_ids or empty_redirects:
            missing = empty_client_ids + empty_redirects
            return GateResult(
                "env_sync",
                "fail",
                f"OIDC auth mode but empty credentials: {', '.join(missing)}",
            )

    return GateResult("env_sync", "pass", f"Env file valid: {env_path.name} ({len(env_vars)} vars)")


def _gate_source_config(manifest: DeployManifest, client: Any, ssh_available: bool) -> GateResult:
    """Gate 8: Verify GitHub source repo/branch exist."""
    src = manifest.source
    if not src.owner or not src.repo:
        return GateResult("source_config", "warn", "No GitHub source configured")

    try:
        proc = subprocess.run(
            ["git", "ls-remote", "--heads", f"https://github.com/{src.owner}/{src.repo}.git", src.branch or "main"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return GateResult("source_config", "warn", "git not available or timed out")
    if proc.returncode != 0:
        return GateResult("source_config", "fail", f"Cannot access GitHub repo: {src.owner}/{src.repo}")
    if not proc.stdout.strip():
        return GateResult(
            "source_config",
            "fail",
            f"Branch '{src.branch or 'main'}' not found in {src.owner}/{src.repo}",
        )
    return GateResult(
        "source_config",
        "pass",
        f"Source: {src.owner}/{src.repo}@{src.branch or 'main'} — verified",
    )


def _gate_network(manifest: DeployManifest, client: Any, ssh_available: bool) -> GateResult:
    """Gate 9: Verify network topology and PGHOST reachability."""
    if not manifest.database.name:
        return GateResult("network", "pass", "No database — network check skipped")

    db_host = manifest.database.host
    if not db_host:
        return GateResult("network", "warn", "No database host specified — cannot verify network")

    try:
        sock = socket.create_connection((db_host, manifest.database.port or 5432), timeout=5)
        sock.close()
        return GateResult(
            "network",
            "pass",
            f"PGHOST {db_host}:{manifest.database.port or 5432} is reachable",
        )
    except (socket.timeout, ConnectionRefusedError, OSError):
        return GateResult(
            "network",
            "warn",
            f"Cannot reach {db_host}:{manifest.database.port or 5432} from this host (may work from server)",
        )


def _gate_ssl(manifest: DeployManifest, client: Any, ssh_available: bool) -> GateResult:
    """Gate 10: Verify SSL certificate status."""
    if not manifest.domain.host:
        return GateResult("ssl", "pass", "No domain — SSL check skipped")

    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=manifest.domain.host) as s:
            s.settimeout(5)
            s.connect((manifest.domain.host, 443))
            cert = s.getpeercert()
            if cert:
                not_after = datetime.datetime.strptime(
                    cert["notAfter"],
                    "%b %d %H:%M:%S %Y %Z",
                )
                days_left = (not_after - datetime.datetime.utcnow()).days
                if days_left < 7:
                    return GateResult(
                        "ssl",
                        "warn",
                        f"SSL cert for {manifest.domain.host} expires in {days_left} days",
                    )
                return GateResult(
                    "ssl",
                    "pass",
                    f"SSL valid: {manifest.domain.host} ({days_left} days remaining)",
                )
            return GateResult("ssl", "warn", f"SSL: no certificate info for {manifest.domain.host}")
    except ssl.SSLError as e:
        return GateResult("ssl", "warn", f"SSL error for {manifest.domain.host}: {e}")
    except (socket.timeout, ConnectionRefusedError, OSError):
        return GateResult(
            "ssl",
            "warn",
            f"Cannot connect to {manifest.domain.host}:443 — SSL check skipped (may be new domain)",
        )


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
    gates: list[str] | None = None,
) -> list[GateResult]:
    """Run all preflight gates and return results.

    Args:
        manifest: Resolved deploy manifest.
        client: DokployClient or None — Dokploy API client for remote checks.
        ssh_available: Whether SSH is available for remote checks.
        gates: Optional list of gate names to run. If None or empty, runs all gates.
            Valid names: server_connectivity, firewall, dns, image_pull, database,
            compose_assignment, env_sync, source_config, network, ssl.

    Returns:
        List of GateResult, one per gate.
    """
    active_gates = _GATES
    if gates:
        gate_set = set(gates)
        active_gates = [g for g in _GATES if g.__name__.replace("_gate_", "") in gate_set]
        if not active_gates:
            return [GateResult("filter", "fail", f"No matching gates for: {', '.join(gates)}")]

    results: list[GateResult] = []
    for gate_fn in active_gates:
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
