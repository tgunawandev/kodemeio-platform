# Deploy Validation Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 7 validation gates to the kctl-dokploy deploy pipeline so wrong IPs, missing services, and broken routing are caught BEFORE they cause damage.

**Architecture:** New `core/validators.py` with reusable validation functions. Each function takes a `DokployClient` and returns `(ok: bool, message: str)`. The deployer.py phase methods call validators before executing. The quickdeploy.py command uses the same validators.

**Tech Stack:** Python 3.12, Typer, httpx (via DokployClient), kctl-lib APIClient

**Spec:** `docs/specs/2026-04-02-deploy-validation-gates-design.md`

---

## File Structure

```
packages/kctl-dokploy/src/kctl_dokploy/
  core/
    validators.py    — NEW: 7 validation functions
    deployer.py      — MODIFY: call validators in each phase
  commands/
    quickdeploy.py   — MODIFY: call validators in each step
```

---

## Task 1: Create `core/validators.py` with all 7 validation functions

**Files:**
- Create: `packages/kctl-dokploy/src/kctl_dokploy/core/validators.py`

- [ ] **Step 1: Create validators.py**

```python
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

    return False, (
        "No GitHub provider configured. "
        "Setup: Dokploy UI → Settings → Git → Install GitHub App"
    ), ""


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
        return False, (
            "domain.service is REQUIRED. Set it to the service name "
            "in your docker-compose.yml file."
        )
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
            f"WARNING: Cannot verify service '{service_name}' before first build. "
            f"Proceeding with manifest value."
        )
    except APIError:
        return True, f"WARNING: Could not load services (compose may need first build). Using '{service_name}'."
    except Exception as e:
        return True, f"WARNING: Service validation skipped: {e}"


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
        return False, (
            f"DNS for {domain} resolves to {resolved} but expected {expected_ip}. "
            f"Fix DNS records."
        )

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
```

- [ ] **Step 2: Verify imports**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
uv run python -c "from kctl_dokploy.core.validators import resolve_server_ip, validate_dns_ip, validate_project_exists, find_github_app_id, disable_autodeploy, validate_service_name, check_domain_routing; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/core/validators.py
git commit -m "feat(kctl-dokploy): add 7 deploy validation gate functions"
```

---

## Task 2: Integrate validators into deployer.py

**Files:**
- Modify: `packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py`

- [ ] **Step 1: Add import**

At the top of deployer.py (after existing imports), add:

```python
from kctl_dokploy.core.validators import (
    resolve_server_ip,
    validate_dns_ip,
    validate_project_exists,
    find_github_app_id,
    disable_autodeploy,
    validate_service_name,
    check_domain_routing,
)
```

- [ ] **Step 2: Add `_get_client()` helper method**

The deployer currently doesn't hold a client. Add a method to lazily create one (same pattern as `_disable_auto_deploy` lines 156-176):

```python
def _get_client(self):
    """Get a DokployClient instance for direct API calls."""
    if hasattr(self, "_client") and self._client:
        return self._client
    try:
        from kctl_lib.config import load_config
        from kctl_dokploy.core.client import DokployClient

        cfg = load_config()
        profile = cfg.get("default_profile", "kodemeio")
        profiles = cfg.get("profiles", {})
        p = profiles.get(profile, {})
        dokploy_cfg = p.get("dokploy", {})
        url = dokploy_cfg.get("url", "")
        key = dokploy_cfg.get("api_key", "")
        if url and key:
            self._client = DokployClient(base_url=url, credential=key)
            return self._client
    except Exception:
        pass
    return None
```

- [ ] **Step 3: Add Gate 1 (SERVER_IP_RESOLUTION) to phase_dns()**

At the START of `phase_dns()` (line 182), before any DNS operations, add:

```python
    # Gate 1: Validate DNS IP matches server
    client = self._get_client()
    if client and self.manifest.server:
        ok, msg, server_ip = resolve_server_ip(client, self.manifest.server)
        if not ok:
            self._record_phase("dns", "failed", f"[VALIDATION] {msg}")
            return
        # Auto-resolve DNS IP if not set
        if self.manifest.dns and not self.manifest.dns.content and server_ip:
            self.manifest.dns.content = server_ip
            self._log(f"Auto-resolved DNS IP from server: {server_ip}")
        # Validate IP matches
        if self.manifest.dns and self.manifest.dns.content:
            ok2, msg2 = validate_dns_ip(self.manifest.dns.content, server_ip, self.manifest.server)
            if not ok2:
                self._record_phase("dns", "failed", f"[VALIDATION] {msg2}")
                return
```

- [ ] **Step 4: Add Gate 4 (AUTODEPLOY_OFF) to phase_compose()**

In `phase_compose()`, after compose is created or updated (after the line that sets `self._compose_id`), replace the existing `self._disable_auto_deploy()` call with the validated version:

```python
    # Gate 4: Disable autodeploy
    if self._compose_id and client:
        ok, msg = disable_autodeploy(client, self._compose_id)
        if not ok:
            self._log(f"WARNING: {msg}")
```

- [ ] **Step 5: Add Gate 5 (SERVICE_NAME_EXISTS) to phase_domain()**

At the START of `phase_domain()` (line 469), after the existing checks, add:

```python
    # Gate 5: Validate service name exists in compose
    client = self._get_client()
    if client and self._compose_id and domain.service:
        ok, msg = validate_service_name(client, self._compose_id, domain.service)
        if not ok:
            self._record_phase("domain", "failed", f"[VALIDATION] {msg}")
            return
        self._log(msg)
    elif not domain.service:
        self._record_phase("domain", "failed", "[VALIDATION] domain.service is REQUIRED")
        return
```

- [ ] **Step 6: Add Gate 7 (TRAFFIC_ROUTING) to phase_verify()**

At the END of `phase_verify()`, after the healthcheck passes, add routing validation:

```python
    # Gate 7: Verify traffic routes to correct server
    if self.manifest.server and not self.dry_run:
        client = self._get_client()
        if client:
            _, _, server_ip = resolve_server_ip(client, self.manifest.server)
            if server_ip:
                ok, msg = check_domain_routing(hc_domain, server_ip)
                if not ok:
                    self._log(f"WARNING: {msg}")
```

- [ ] **Step 7: Verify deployer still works**

```bash
kctl-dokploy deploy apply -f deploys/instances/react-terakidz-web.yaml --dry-run
```

- [ ] **Step 8: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py
git commit -m "feat(kctl-dokploy): integrate 7 validation gates into deploy pipeline"
```

---

## Task 3: Integrate validators into quickdeploy.py

**Files:**
- Modify: `packages/kctl-dokploy/src/kctl_dokploy/commands/quickdeploy.py`

- [ ] **Step 1: Add import**

```python
from kctl_dokploy.core.validators import (
    resolve_server_ip,
    validate_project_exists,
    find_github_app_id,
    disable_autodeploy,
    validate_service_name,
    check_domain_routing,
)
```

- [ ] **Step 2: Replace Step 1 (project resolution) with validated version**

Replace the `_resolve_environment` helper call with:

```python
    # --- Step 1: Resolve project (Gate 2) ---
    _step(c, 1, steps_total, "Resolving project...")
    if dry_run:
        env_id = "dry-run-env-id"
    else:
        ok, msg, pid, env_id = validate_project_exists(c.client, project)
        if not ok:
            _fail(c, 1, steps_total, msg)
            raise typer.Exit(1)
    _ok(c, 1, steps_total, msg if not dry_run else f"[dry-run] Project '{project}'")
```

- [ ] **Step 3: Replace Step 2 (GitHub provider) with validated version**

```python
    # --- Step 2: Find GitHub provider (Gate 3) ---
    _step(c, 2, steps_total, "Finding GitHub provider...")
    if dry_run:
        github_id = "dry-run-github-id"
    else:
        ok, msg, github_id = find_github_app_id(c.client)
        if not ok:
            _fail(c, 2, steps_total, msg)
            raise typer.Exit(1)
    _ok(c, 2, steps_total, msg if not dry_run else "[dry-run] GitHub provider")
```

- [ ] **Step 4: Add autodeploy disable (Gate 4) after compose creation**

After compose is created/updated in `_setup_compose`, add:

```python
    # Gate 4: Disable autodeploy
    if not dry_run:
        ok, msg = disable_autodeploy(c.client, compose_id)
        if not ok:
            c.output.warn(f"Autodeploy: {msg}")
```

- [ ] **Step 5: Add service name validation (Gate 5) before domain creation**

Before calling `_setup_domain`, add:

```python
    if domain and not dry_run:
        svc = service or name
        ok, msg = validate_service_name(c.client, compose_id, svc)
        if not ok:
            _fail(c, 6, steps_total, msg)
            raise typer.Exit(1)
        c.output.info(f"  {msg}")
```

- [ ] **Step 6: Verify quickdeploy dry-run**

```bash
uv tool install --force ./packages/kctl-dokploy
kctl-dokploy quickdeploy run --name test --project kidneuro-service \
  --repo tgunawandev/kodemeio-react --compose-path compose/docker-compose.terakidz.yml \
  --domain terakidz.com --port 3006 --service terakidz-web --dry-run
```

- [ ] **Step 7: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/commands/quickdeploy.py
git commit -m "feat(kctl-dokploy): add validation gates to quickdeploy command"
```

---

## Task 4: Fix manifest + deploy terakidz.com correctly

**Files:**
- Modify: `deploys/instances/react-terakidz-web.yaml`

- [ ] **Step 1: Remove hardcoded dns.content (let it auto-resolve)**

```yaml
dns:
  zone: terakidz.com
  name: "@"
  # content removed — auto-resolved from server IP
```

- [ ] **Step 2: Deploy with validation**

```bash
# Clean up any existing broken compose
kctl-dokploy compose list | grep terakidz
# Delete if exists: kctl-dokploy compose delete <id> --force

# Deploy with new validation gates
kctl-dokploy deploy apply -f deploys/instances/react-terakidz-web.yaml
```

Expected: Gate 1 auto-resolves DNS IP to 49.13.14.79 from `kodeme-service`.

- [ ] **Step 3: Verify site**

```bash
curl -sL http://terakidz.com | grep -o "<title>[^<]*</title>"
```

- [ ] **Step 4: Commit manifest fix**

```bash
git add deploys/instances/react-terakidz-web.yaml
git commit -m "fix: remove hardcoded DNS IP from terakidz manifest (auto-resolves from server)"
git push origin main
```

---

## Summary

| Task | What | Files |
|---|---|---|
| 1 | Create `validators.py` with 7 validation functions | NEW: core/validators.py |
| 2 | Integrate validators into deployer.py pipeline | MODIFY: core/deployer.py |
| 3 | Integrate validators into quickdeploy command | MODIFY: commands/quickdeploy.py |
| 4 | Fix manifest + deploy terakidz.com | MODIFY: deploys/instances/react-terakidz-web.yaml |
