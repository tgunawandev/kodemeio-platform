# Deploy Pre/Post Validation — Design Spec

**Goal:** Add type-aware pre-deploy validation and post-deploy smoke tests to the `kctl-dokploy deploy` pipeline, plus a standalone `deploy verify` command.

**Problem:** During MAC deployment, multiple issues went undetected until users hit "Failed to fetch" errors: blank .env files, API URLs missing FastAPI root path, CORS not configured, JWT secrets missing, Docker cache serving stale builds. The pipeline's only verification is an HTTP healthcheck (status 200), which passes even when the app is fundamentally broken.

## App Type Detection

Detect type from the manifest's `extends` field or `source.compose_path`:

| Type | Detection | Examples |
|------|-----------|---------|
| `react-pwa` | extends `react-pwa.yaml` OR compose_path matches app names | docker-compose.wms.yml, docker-compose.sfa.yml |
| `odoo` | extends `odoo.yaml` OR compose_path contains `odoo.prod` | compose/odoo.prod.yml |
| `nextjs` | extends `nextjs.yaml` OR compose_path contains `next` or app web names | docker-compose.prod.careers.yml |
| `infra` | extends `infra.yaml` | notify docker-compose.yml |
| `unknown` | no match | fallback, basic checks only |

Detection uses the RESOLVED manifest (after `extends` merging), checking `manifest.kind` and base template path.

## Pre-Deploy Validation (`phase_pre_validate`)

Runs before Phase 1 (DNS). Returns warnings and errors. Errors block deploy unless `--force`.

### All Types
- `env_file` path exists on disk (if specified)
- `domain.host` is a valid FQDN (regex: `^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*$`)
- `domain.service` is not empty when domain is configured
- `env_file` is not empty (warn if file has 0 env vars)

### React PWA
- Every `VITE_*_API_BASE_URL` in merged env must end with `/{app}/api` (error)
- `VITE_AUTH_MODE` must be set (warn if missing, defaults to oidc)
- `VITE_AUTH_MODE` value must be one of: `native`, `oidc`, `development` (error if invalid)
- If `VITE_AUTH_MODE=oidc`: `VITE_OIDC_AUTHORITY` and matching `VITE_*_OIDC_CLIENT_ID` must be set (warn)

### Odoo
- `post_deploy.odoo_profile` exists (already checked in phase_validate, but also here for early catch)
- Database name length < 63 characters (PostgreSQL limit)
- `ODOO_ADMIN_PASSWD` is set in env (warn if missing)

### Next.js
- No additional pre-deploy checks (manifest-level validation is sufficient)

## Post-Deploy Smoke Tests (enhanced `phase_verify`)

After the existing healthcheck passes (HTTP status 200), run type-specific smoke tests. All smoke tests are **warnings only** — the deploy already succeeded. Results logged as a summary table.

### React PWA Smoke Tests

1. **Baked API URL check**: SSH to server, exec into the container, grep for `localhost` in the JS bundle assets. Warn if `localhost` found in any `apiBaseUrl` or `API_BASE_URL` reference.

2. **CORS preflight**: Send OPTIONS request to `{api_base_url}/auth/login` with `Origin: https://{domain.host}`. Check response has `access-control-allow-origin` header. Warn if 405 or missing CORS headers.

3. **Login endpoint reachable**: Send POST to `{api_base_url}/auth/login` with dummy credentials. Check response is NOT 404 (any other status is OK — 401/500 means endpoint exists). Warn if 404.

### Odoo Smoke Tests

1. **FastAPI endpoints registered**: Call Odoo JSON-RPC to query `fastapi.endpoint` records. Warn if expected app endpoints are missing (based on profile — e.g., distribution profile should have wms, sfa, lfa, shop, bia, dms endpoints).

2. **JWT secrets set**: Call Odoo JSON-RPC to check `ir.config_parameter` for `{app}.jwt_secret`. Warn if any secret is empty, too short (< 32 chars), or contains the placeholder `CHANGE-IN-PRODUCTION`.

3. **CORS configured**: For each registered FastAPI endpoint app, check the corresponding `{app}.app` record has non-empty `cors_allowed_origins`. For BIA, check `ir.config_parameter` key `bia.cors_allowed_origins`.

4. **No stuck modules**: Query `ir.module.module` for records with `state` in (`to upgrade`, `to install`, `to remove`). Warn if any found.

### Next.js Smoke Tests

1. **Root path not 404**: Send GET to `https://{domain.host}/` (no redirect follow). Check response is 200 or 30x (redirect). Warn if 404 (missing i18n middleware).

### Infra Smoke Tests

No additional checks beyond healthcheck.

## Standalone `deploy verify` Command

```bash
kctl-dokploy deploy verify -f deploys/instances/mandiriagro.com-react-wms.yaml
```

Runs all post-deploy smoke tests without redeploying. Requires the compose to already exist in Dokploy. Reads the manifest, detects type, resolves compose ID, and runs the smoke tests.

Output: table of check results (PASS/WARN/FAIL).

## File Structure

```
packages/kctl-dokploy/src/kctl_dokploy/
├── core/
│   ├── deployer.py          # MODIFY: add phase_pre_validate(), enhance phase_verify()
│   ├── manifest.py          # NO CHANGE
│   └── deploy_validators.py # NEW: type detection + all validation/smoke test logic
└── commands/
    └── deploy.py            # MODIFY: add verify command
```

### `deploy_validators.py` Module

```python
class DeployValidator:
    """Type-aware pre-deploy validation and post-deploy smoke tests."""

    def __init__(self, manifest, env_vars, compose_id=None, dry_run=False):
        self.manifest = manifest
        self.env_vars = env_vars
        self.compose_id = compose_id
        self.dry_run = dry_run
        self.app_type = self._detect_app_type()

    def _detect_app_type(self) -> str:
        """Detect app type from manifest extends/compose_path."""

    def pre_validate(self) -> tuple[list[str], list[str]]:
        """Run pre-deploy checks. Returns (warnings, errors)."""

    def post_verify(self) -> list[dict]:
        """Run post-deploy smoke tests. Returns list of {name, status, detail}."""
```

## Integration Points

### In `deployer.py`

1. `phase_pre_validate()` — called BEFORE `phase_dns()` in the pipeline sequence
2. `phase_verify()` — after existing healthcheck passes, call `DeployValidator.post_verify()`

### In `deploy.py` (commands)

1. New `verify` command — instantiates `DeployValidator` and runs `post_verify()` standalone

### Pipeline Sequence (updated)

```
Phase 0:  Validate (manifest schema)        — existing
Phase 0b: Pre-validate (type-aware checks)  — NEW
Phase 1:  DNS
Phase 2:  Database
Phase 3:  Registry
Phase 4:  Compose
Phase 5:  Environment
Phase 6:  Domain
Phase 7:  Deploy
Phase 8:  Verify (healthcheck + smoke tests) — ENHANCED
Phase 9:  Backup
Phase 10: Schedules
Phase 10b: Volume Backups
Phase 11: Post-Deploy (profile install)
```

## Smoke Test Execution Details

### CORS Preflight Test
```python
response = httpx.options(
    f"{api_base_url}/auth/login",
    headers={
        "Origin": f"https://{domain_host}",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    },
    verify=False,
    timeout=10,
)
# PASS if status 200 and access-control-allow-origin header present
# WARN if status 405 (CORS middleware not active)
# SKIP if API URL not resolvable
```

### Odoo JSON-RPC Test
```python
response = httpx.post(
    f"https://{domain_host}/jsonrpc",
    json={
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "service": "object",
            "method": "execute_kw",
            "args": [db_name, 2, "admin", "ir.config_parameter", "get_param", [f"{app}.jwt_secret"]],
        },
    },
    verify=False,
    timeout=15,
)
```

### Baked URL Check (SSH into container)
```python
# Uses kctl-dokploy docker to exec into container
# grep -o 'apiBaseUrl[^,]*' in nginx HTML assets
# WARN if "localhost" found
```

## Error Handling

- All smoke tests use try/except — network failures become SKIP (not FAIL)
- Timeout per check: 10 seconds
- Total smoke test timeout: 60 seconds
- Smoke test failures never block the pipeline (warnings only)
- Pre-validate errors DO block the pipeline (unless --force)

## Output Format

```
╭─ Pre-Deploy Validation ─────────────────────────────────╮
│ Type: react-pwa                                          │
│                                                          │
│ ✓ env_file exists and has 7 variables                   │
│ ✓ VITE_WMS_API_BASE_URL ends with /wms/api              │
│ ✓ VITE_AUTH_MODE=native (valid)                          │
│ ✓ domain.host is valid FQDN                             │
╰──────────────────────────────────────────────────────────╯

╭─ Post-Deploy Smoke Tests ───────────────────────────────╮
│ ✓ Healthcheck: 200 OK                                   │
│ ✓ API URL: odoo-dist-mac.mandiriagro.com/wms/api        │
│ ✓ CORS preflight: 200 (origin allowed)                  │
│ ✓ Login endpoint: reachable (non-404)                   │
│ ⚠ Baked URL check: skipped (SSH not available)          │
╰──────────────────────────────────────────────────────────╯
```
