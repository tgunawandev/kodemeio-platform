"""Deploy validation gates for kctl-dokploy.

Each function returns (ok: bool, message: str).
ok=True means validation passed.
ok=False means validation failed with an error message.
"""

from __future__ import annotations

import socket
from typing import Any

from kctl_lib.exceptions import APIError


def resolve_server_ip(client: Any, server_name: str) -> tuple[bool, str, str]:
    """Gate 1: Resolve server name to IP address.

    Returns (ok, message, ip).
    """
    if not server_name:
        return True, "No server specified (using Dokploy host)", ""
    try:
        servers = client.get("/server.all")
    except Exception as e:
        return False, f"Failed to fetch servers: {e}", ""
    if not isinstance(servers, list):
        return False, "Invalid server list response", ""

    for s in servers:
        name = s.get("name", s.get("serverName", ""))
        if name == server_name:
            ip = s.get("ipAddress", "")
            if ip:
                return True, f"Server '{server_name}' → {ip}", ip
            return False, f"Server '{server_name}' found but has no IP address", ""

    names = [s.get("name", "?") for s in servers]
    return False, f"Server '{server_name}' not found. Available: {', '.join(names)}", ""


def validate_dns_ip(manifest_ip: str, server_ip: str, server_name: str) -> tuple[bool, str]:
    """Gate 1b: Validate DNS IP matches server IP.

    If manifest_ip is empty, it will be auto-filled by the caller.
    """
    if not manifest_ip:
        return True, f"DNS IP will be auto-resolved from server '{server_name}': {server_ip}"
    if not server_ip:
        return True, "No server IP to validate against (using Dokploy host)"
    if manifest_ip != server_ip:
        return False, (
            f"DNS IP MISMATCH: manifest says {manifest_ip} but server "
            f"'{server_name}' is {server_ip}. "
            f"Fix dns.content in manifest or remove it to auto-resolve."
        )
    return True, f"DNS IP {manifest_ip} matches server '{server_name}'"


def validate_project_exists(client: Any, project_name: str) -> tuple[bool, str, str, str]:
    """Gate 2: Validate project exists and has an environment.

    Returns (ok, message, project_id, environment_id).
    """
    try:
        projects = client.get("/project.all")
    except Exception as e:
        return False, f"Failed to fetch projects: {e}", "", ""
    if not isinstance(projects, list):
        return False, "Invalid project list response", "", ""

    for p in projects:
        if p.get("name", "").lower() == project_name.lower():
            pid = p.get("projectId", "")
            envs = p.get("environments", [])
            if envs:
                eid = envs[0].get("environmentId", "")
                return True, f"Project '{project_name}' → env {eid}", pid, eid
            return False, f"Project '{project_name}' has no environments", pid, ""

    names = [p.get("name", "?") for p in projects]
    return False, f"Project '{project_name}' not found. Available: {', '.join(names)}", "", ""


def find_github_app_id(client: Any) -> tuple[bool, str, str]:
    """Gate 3: Find GitHub App ID for compose linking.

    Returns (ok, message, github_app_id).
    """
    try:
        providers = client.get("/gitProvider.getAll")
    except Exception as e:
        return False, f"Failed to fetch git providers: {e}", ""
    if not isinstance(providers, list):
        return False, "Invalid git provider response", ""

    for p in providers:
        ptype = p.get("gitProviderType", p.get("providerType", ""))
        if ptype == "github":
            github = p.get("github", {})
            if isinstance(github, dict) and github.get("githubId"):
                gid = github["githubId"]
                return True, f"GitHub provider → githubId {gid}", gid

    return False, ("No GitHub provider configured. Setup: Dokploy UI → Settings → Git → Install GitHub App"), ""


def disable_autodeploy(client: Any, compose_id: str) -> tuple[bool, str]:
    """Gate 4: Disable autoDeploy on compose.

    Returns (ok, message).
    """
    if not compose_id:
        return False, "No compose ID to disable autodeploy on"
    try:
        client.post("/compose.update", json={"composeId": compose_id, "autoDeploy": False})
        # Verify
        comp = client.get("/compose.one", params={"composeId": compose_id})
        if isinstance(comp, dict) and comp.get("autoDeploy") is False:
            return True, "Autodeploy disabled and verified"
        if isinstance(comp, dict) and comp.get("autoDeploy") is True:
            return False, "Autodeploy still enabled after update attempt"
        return True, "Autodeploy disabled (could not verify)"
    except Exception as e:
        return False, f"Failed to disable autodeploy: {e}"


def validate_service_name(client: Any, compose_id: str, service_name: str) -> tuple[bool, str]:
    """Gate 5: Validate service name exists in compose file.

    Returns (ok, message).
    """
    if not service_name:
        return False, ("domain.service is REQUIRED. Set it to the service name in your docker-compose.yml file.")
    if not compose_id:
        return False, "No compose ID to validate service against"
    try:
        services = client.get("/compose.loadServices", params={"composeId": compose_id})
        if isinstance(services, list) and services:
            svc_names = [s.get("serviceName", s.get("name", "")) for s in services]
            if service_name in svc_names:
                return True, f"Service '{service_name}' found in compose"
            return False, (
                f"Service '{service_name}' NOT found in compose file. "
                f"Available: {', '.join(svc_names)}. "
                f"Fix domain.service in manifest to match a service in docker-compose.yml."
            )
        # Empty list = compose file not yet parsed (needs first deploy)
        return True, (
            f"WARNING: Cannot verify service '{service_name}' before first build. Proceeding with manifest value."
        )
    except APIError:
        return True, f"WARNING: Could not load services (compose may need first build). Using '{service_name}'."
    except Exception as e:
        return True, f"WARNING: Service validation skipped: {e}"


def validate_dns_resolution(
    fqdn: str, expected_ip: str, max_retries: int = 3, retry_delay: float = 2.0
) -> tuple[bool, str]:
    """Gate 1c: Post-creation DNS resolution validation.

    After creating a DNS record, resolve the FQDN and assert it points to
    the expected IP.  Retries a few times to allow for propagation delay.

    Returns (ok, message).
    """
    import time

    if not expected_ip:
        return True, "No expected IP to validate against (skipping DNS resolution check)"

    last_error = ""
    for attempt in range(1, max_retries + 1):
        try:
            results = socket.getaddrinfo(fqdn, None, socket.AF_INET, socket.SOCK_STREAM)
            resolved_ips = sorted({r[4][0] for r in results})
            if expected_ip in resolved_ips:
                return True, f"DNS verified: {fqdn} → {expected_ip}"
            last_error = f"DNS mismatch: {fqdn} resolves to {', '.join(resolved_ips)} but expected {expected_ip}"
        except socket.gaierror as e:
            last_error = f"DNS resolution failed for {fqdn}: {e}"

        if attempt < max_retries:
            time.sleep(retry_delay)

    return False, f"{last_error} (after {max_retries} attempts, may need more propagation time)"


def check_domain_routing(domain: str, expected_ip: str, timeout: int = 30) -> tuple[bool, str]:
    """Gate 7: Verify domain DNS resolves to expected IP and responds.

    Returns (ok, message).
    """
    import httpx as _httpx

    # Step 1: DNS resolution
    try:
        resolved = socket.gethostbyname(domain)
    except socket.gaierror:
        return False, f"DNS resolution failed for {domain}"

    if expected_ip and resolved != expected_ip:
        return False, (f"DNS for {domain} resolves to {resolved} but expected {expected_ip}. Fix DNS records.")

    # Step 2: HTTP check
    for scheme in ("https", "http"):
        try:
            r = _httpx.get(f"{scheme}://{domain}", timeout=10, follow_redirects=True, verify=False)
            if r.status_code == 200:
                return True, f"{scheme}://{domain} → 200 OK"
            if r.status_code == 404:
                return False, (
                    f"{scheme}://{domain} → 404. Traefik can't route to container. "
                    f"Check domain.service matches a service in docker-compose.yml."
                )
            if r.status_code in (502, 521):
                return False, (
                    f"{scheme}://{domain} → {r.status_code}. Origin server unreachable. "
                    f"Check container is running: kctl-dokploy compose get <id>"
                )
        except Exception:
            continue

    return False, f"Could not connect to {domain} via HTTP or HTTPS"
