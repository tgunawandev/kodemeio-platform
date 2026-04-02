# Deploy Validation Gates — Design Specification

**Date:** 2026-04-02
**Status:** Approved
**Author:** Claude + tgunawan

---

## 1. Problem

An AI agent deployed terakidz.com with the wrong IP (168.119.233.161 instead of 49.13.14.79), wrong Cloudflare proxy settings, autodeploy enabled causing premature builds, and no service name validation — resulting in 30+ minutes of failed deployment and traffic routing to the wrong container (QuizTower instead of Terakidz).

**Root cause:** Zero validation at any step of the deployment pipeline. The pipeline blindly accepts whatever values are in the manifest without checking if they're correct.

## 2. Solution: 7 Validation Gates

### Gate 1: SERVER_IP_RESOLUTION (Phase 1 — DNS)

**Location:** `core/deployer.py` → `phase_dns()`

Before creating DNS records:
1. Read `manifest.server` name (e.g., `kodeme-service`)
2. Call `servers list` → resolve name to IP (e.g., `49.13.14.79`)
3. If `manifest.dns.content` is set:
   - Compare with resolved server IP
   - If mismatch → **FAIL**: `"DNS IP 168.119.233.161 does not match server kodeme-service (49.13.14.79). Fix manifest dns.content or remove it to auto-resolve."`
4. If `manifest.dns.content` is NOT set:
   - Auto-fill from server IP
   - Log: `"Auto-resolved DNS IP from server kodeme-service: 49.13.14.79"`

### Gate 2: PROJECT_EXISTS (Phase 4 — Compose)

**Location:** `core/deployer.py` → `phase_compose()`

Before creating compose:
1. Call `projects list` → find project by name
2. If not found → **FAIL**: `"Project 'xxx' not found. Available projects: [list names]"`
3. Extract environment ID from first environment
4. If no environments → **FAIL**: `"Project 'xxx' has no environments"`

### Gate 3: GITHUB_PROVIDER (Phase 4 — Compose)

**Location:** `core/deployer.py` → `phase_compose()` → `_find_github_id()`

Before linking GitHub source:
1. Call `/gitProvider.getAll` → find GitHub type provider
2. Extract inner `github.githubId` (NOT outer `gitProviderId`)
3. If not found → **FAIL**: `"No GitHub provider configured. Setup: Dokploy UI → Settings → Git → Install GitHub App"`
4. Verify branch exists: call `git branches <provider_id> --owner <owner> --repo <repo>`
5. If branch not found → **WARN**: `"Branch 'main' not found in repo. Deploy may fail."`

### Gate 4: AUTODEPLOY_OFF (Phase 4 — Compose)

**Location:** `core/deployer.py` → `phase_compose()` after create/update

After creating or updating compose:
1. Call `/compose.update` with `{"composeId": id, "autoDeploy": false}`
2. Re-fetch compose via `/compose.one`
3. Assert `autoDeploy == false`
4. If still true → **FAIL**: `"Could not disable autodeploy on compose"`

### Gate 5: SERVICE_NAME_EXISTS (Phase 6 — Domain)

**Location:** `core/deployer.py` → `phase_domain()`

Before creating domain:
1. If `manifest.domain.service` is set:
   - Call `/compose.loadServices` with composeId
   - Parse response for available service names
   - If service NOT in list → **FAIL**: `"Service 'terakidz-web' not found in compose file. Available services: [list]. Check domain.service in manifest matches a service in your docker-compose.yml."`
   - If loadServices returns empty (compose not yet built) → **WARN**: `"Cannot verify service name before first build. Proceeding with manifest value."`
2. If `manifest.domain.service` is NOT set → **FAIL**: `"domain.service is required. Set it to the service name in your docker-compose.yml file."`

### Gate 6: DEPLOY_SUCCESS (Phase 7 — Deploy)

**Location:** `core/deployer.py` → `phase_deploy()`

After triggering deploy:
1. Poll `/deployment.allByCompose` every 10s
2. On `status == "error"`:
   - Fetch deployment logs via `/deployment.readLog`
   - **FAIL**: `"Deployment FAILED. Build error:\n{first 500 chars of log}"`
3. On `status == "done"` → proceed
4. On timeout → **FAIL**: `"Deployment timed out after {timeout}s. Status: {last_status}. Check: kctl-dokploy deployments logs {deployment_id}"`
5. Default timeouts: 300s (react-pwa), 900s (odoo)

### Gate 7: TRAFFIC_ROUTING (Phase 8 — Verify)

**Location:** `core/deployer.py` → `phase_verify()`

After deploy completes:
1. Wait 15s for Traefik label propagation
2. Resolve domain via DNS → get IP
3. Compare resolved IP with server IP (from Gate 1)
4. If mismatch → **FAIL**: `"DNS for terakidz.com resolves to {dns_ip} but server is {server_ip}. Fix DNS records."`
5. HTTP GET to domain (follow redirects, allow self-signed)
6. If 200 → **PASS**
7. If 404 "page not found" → **FAIL**: `"Traefik returns 404. Domain service name may be wrong. Check: kctl-dokploy domains get {compose_id}"`
8. If 502/521 → **FAIL**: `"Origin server error. Check container is running: kctl-dokploy compose get {compose_id}"`
9. If 200 but wrong content → **WARN**: `"Domain responds but may serve wrong content. Verify manually."`

## 3. New File: `core/validators.py`

Reusable validation functions used by both `deployer.py` and `quickdeploy.py`:

```python
def resolve_server_ip(client, server_name: str) -> str | None
def validate_dns_ip(manifest_ip: str, server_ip: str) -> tuple[bool, str]
def validate_project_exists(client, project_name: str) -> tuple[str, str] | None  # (project_id, env_id)
def find_github_app_id(client) -> str | None
def validate_service_name(client, compose_id: str, service_name: str) -> tuple[bool, list[str]]
def check_domain_routing(domain: str, expected_ip: str, timeout: int) -> tuple[bool, str]
def disable_autodeploy(client, compose_id: str) -> bool
```

## 4. Manifest Auto-Resolution

If `dns.content` is not specified in the manifest, auto-resolve from the server:

```yaml
# dns.content is now OPTIONAL
dns:
  zone: terakidz.com
  name: "@"
  # content omitted → auto-resolved from server IP
```

In `deployer.py`, before `phase_dns()`:
```python
if not self.manifest.dns.content:
    server_ip = resolve_server_ip(self.client, self.manifest.server)
    self.manifest.dns.content = server_ip
```

## 5. Files Changed

| File | Change |
|---|---|
| `core/validators.py` | **NEW** — 7 validation functions |
| `core/deployer.py` | **MODIFY** — add gates to each phase method |
| `commands/quickdeploy.py` | **MODIFY** — use validators for same gates |
| `deploys/instances/react-terakidz-web.yaml` | **MODIFY** — remove hardcoded dns.content |

## 6. Validation Summary Table

| Phase | Gate | Validates | Fails on |
|---|---|---|---|
| DNS | SERVER_IP_RESOLUTION | IP matches server | Mismatch or server not found |
| Compose | PROJECT_EXISTS | Project + env exist | Not found |
| Compose | GITHUB_PROVIDER | GitHub App linked | No provider |
| Compose | AUTODEPLOY_OFF | autoDeploy disabled | Can't disable |
| Domain | SERVICE_NAME_EXISTS | Service in compose file | Service not found |
| Deploy | DEPLOY_SUCCESS | Build completes | Build error or timeout |
| Verify | TRAFFIC_ROUTING | Domain routes correctly | Wrong IP, 404, 502 |
