# Deployment Reliability — Fix & Automate React PWA + Odoo Deployment

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate all manual post-deploy steps (CORS, JWT secrets, API URL validation) so that `kctl-dokploy deploy apply -f manifest.yaml` produces a fully working deployment for any customer, every time.

**Architecture:** Three layers of fixes: (1) Odoo module auto-initialization for CORS + JWT, (2) deploy pipeline env validation, (3) fix pakerti.com manifests with correct patterns.

**Tech Stack:** Python (Odoo 18 + Pydantic), YAML manifests, Docker Compose, kctl-dokploy CLI

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `kodemeio-odoo/src/private/base_management/hooks.py` | Modify | Add JWT + CORS auto-init to `post_init_hook` |
| `kodemeio-odoo/src/private/base_management/data/cors_defaults.xml` | Create | Default `cors_allowed_origins=*` on all app records |
| `kodemeio-odoo/src/private/bia_management/data/bia_cors_default.xml` | Create | Default `bia.cors_allowed_origins=*` system parameter |
| `kodemeio-odoo/src/private/bia_management/__manifest__.py` | Modify | Add data file |
| `kodemeio-odoo/src/private/base_management/__manifest__.py` | Modify | Add data file |
| `kodemeio-platform/packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py` | Modify | Add env validation in `phase_environment()` |
| `kodemeio-platform/deploys/env/pakerti.com-react-hrm.env` | Modify | Populate with correct vars |
| `kodemeio-platform/deploys/env/pakerti.com-react-sfa.env` | Modify | Populate with correct vars |
| `kodemeio-platform/deploys/instances/pakerti.com-react-hrm.yaml` | Modify | Fix API URL path |
| `kodemeio-platform/deploys/instances/pakerti.com-react-sfa.yaml` | Modify | Fix API URL path |

---

### Task 1: Auto-set CORS defaults on all app records via XML data

**Files:**
- Create: `kodemeio-odoo/src/private/base_management/data/cors_defaults.xml`
- Modify: `kodemeio-odoo/src/private/base_management/__manifest__.py`

This ensures every `{app}.app` record has `cors_allowed_origins=*` set on install, so CORS middleware is always active.

- [ ] **Step 1: Create CORS defaults data file**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data noupdate="0">
        <!-- 
            Set cors_allowed_origins=* on all mobile.app.mixin records.
            noupdate="0" ensures this runs on every module upgrade,
            resetting CORS to * if it was accidentally cleared.
        -->
        <function model="mobile.app.mixin" name="_set_default_cors"/>
    </data>
</odoo>
```

Wait — `mobile.app.mixin` is abstract. We need to set it on each concrete model. Instead, add it to `post_init_hook`. See Task 2.

- [ ] **Step 1 (revised): Create BIA CORS default as system parameter**

Create `kodemeio-odoo/src/private/bia_management/data/bia_cors_default.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data noupdate="1">
        <record id="bia_cors_default" model="ir.config_parameter">
            <field name="key">bia.cors_allowed_origins</field>
            <field name="value">*</field>
        </record>
    </data>
</odoo>
```

- [ ] **Step 2: Add data file to BIA manifest**

In `kodemeio-odoo/src/private/bia_management/__manifest__.py`, add to `data` list:

```python
"data": [
    # ... existing entries ...
    "data/bia_cors_default.xml",
],
```

- [ ] **Step 3: Commit**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-odoo
git add src/private/bia_management/data/bia_cors_default.xml src/private/bia_management/__manifest__.py
git commit -m "fix(bia): add default CORS=* system parameter on install"
```

---

### Task 2: Auto-generate JWT secrets and set CORS in base_management post_init_hook

**Files:**
- Modify: `kodemeio-odoo/src/private/base_management/hooks.py`

This ensures JWT secrets are generated and CORS is set on every `base_management` install/upgrade.

- [ ] **Step 1: Add JWT + CORS init to hooks.py**

Add these functions to `kodemeio-odoo/src/private/base_management/hooks.py`:

```python
import secrets

# Known app models that inherit mobile.app.mixin
_APP_MODELS = [
    "sfa.app", "lfa.app", "shop.app", "wms.app", "mrp.app",
    "hrm.app", "asset.app", "dms.app", "tpm.app",
    "recruitment.app", "saas.app",
]

# Known app prefixes for JWT secrets
_JWT_APP_PREFIXES = [
    "sfa", "lfa", "shop", "wms", "mrp", "hrm", "bia",
    "asset", "dms", "tpm", "recruitment", "saas",
]


def _init_cors_defaults(env):
    """Set cors_allowed_origins=* on all app records that have it empty."""
    for model_name in _APP_MODELS:
        if model_name not in env:
            continue
        apps = env[model_name].search([
            "|",
            ("cors_allowed_origins", "=", False),
            ("cors_allowed_origins", "=", ""),
        ])
        if apps:
            apps.write({"cors_allowed_origins": "*"})
            _logger.info(
                "base_management: Set CORS=* on %d %s records",
                len(apps), model_name,
            )


def _init_jwt_secrets(env):
    """Generate JWT secrets for apps that don't have one set."""
    ICP = env["ir.config_parameter"].sudo()
    placeholder = "CHANGE-IN-PRODUCTION"
    for prefix in _JWT_APP_PREFIXES:
        key = f"{prefix}.jwt_secret"
        current = ICP.get_param(key, "")
        if not current or placeholder in current or len(current) < 32:
            new_secret = secrets.token_hex(32)
            ICP.set_param(key, new_secret)
            _logger.info("base_management: Generated JWT secret for %s", key)
```

- [ ] **Step 2: Call from post_init_hook**

In the existing `post_init_hook(env)` function, add at the end:

```python
def post_init_hook(env):
    """Auto-subscribe auditlog rules created by this module."""
    # ... existing auditlog code ...

    # Auto-initialize CORS and JWT for all apps
    _init_cors_defaults(env)
    _init_jwt_secrets(env)
```

- [ ] **Step 3: Test locally**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-odoo
./run mod update base_management
./run shell -c "
env['ir.config_parameter'].get_param('wms.jwt_secret')
"
```

Expected: a 64-char hex string (not empty, not placeholder)

- [ ] **Step 4: Commit**

```bash
git add src/private/base_management/hooks.py
git commit -m "fix(base_management): auto-init JWT secrets + CORS on install

post_init_hook now generates random JWT secrets for all 12 app
prefixes and sets cors_allowed_origins=* on all app records.
Eliminates manual post-deploy CORS/JWT configuration."
```

---

### Task 3: Add env validation to deploy pipeline

**Files:**
- Modify: `kodemeio-platform/packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py`

Add validation in `phase_environment()` that warns when React PWA env vars are misconfigured.

- [ ] **Step 1: Add validation helper**

Add this method to the `Deployer` class in `deployer.py`, after `phase_environment()`:

```python
def _validate_react_env(self, env_vars: dict[str, str]) -> list[str]:
    """Validate React PWA environment variables. Returns list of warnings."""
    warnings = []
    manifest_type = self.manifest.source_overrides.get("compose_path", "")

    # Only validate React PWA composes
    if not any(app in manifest_type for app in [
        "sfa", "lfa", "shop", "wms", "bia", "hrm", "mrp",
        "eam", "tpm", "dms", "saas",
    ]):
        return warnings

    # Check API base URL includes app path
    for key, val in env_vars.items():
        if key.startswith("VITE_") and key.endswith("_API_BASE_URL") and val:
            if not any(val.endswith(f"/{app}/api") for app in [
                "sfa", "lfa", "shop", "wms", "bia", "hrm", "mrp",
                "asset", "dms", "tpm", "recruitment", "saas",
            ]):
                warnings.append(
                    f"  {key}={val} — missing app path (e.g., /wms/api). "
                    f"Login will fail without the FastAPI root path."
                )

    # Check auth mode is set
    auth_mode = env_vars.get("VITE_AUTH_MODE", "")
    if not auth_mode:
        warnings.append("  VITE_AUTH_MODE not set — defaults to 'oidc'")

    return warnings
```

- [ ] **Step 2: Call validation in phase_environment()**

At the end of `phase_environment()`, after pushing env vars, add:

```python
# Validate React PWA env vars
warnings = self._validate_react_env(merged)
if warnings:
    for w in warnings:
        _logger.warning("ENV VALIDATION: %s", w)
    if not self.dry_run:
        _logger.warning(
            "React PWA env validation warnings detected. "
            "Deploy will continue, but login may fail."
        )
```

- [ ] **Step 3: Test with dry-run**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
kctl-dokploy deploy apply -f deploys/instances/mandiriagro.com-react-wms.yaml --dry-run
```

Expected: no warnings (URL now includes `/wms/api`)

- [ ] **Step 4: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py
git commit -m "feat(deploy): add React PWA env validation in environment phase

Warns when VITE_*_API_BASE_URL is missing the FastAPI app path
(e.g., /wms/api) or when VITE_AUTH_MODE is not set. Prevents
the 'Failed to fetch' login issue we hit on MAC deployment."
```

---

### Task 4: Fix pakerti.com React manifest env files and API URLs

**Files:**
- Modify: `kodemeio-platform/deploys/env/pakerti.com-react-hrm.env`
- Modify: `kodemeio-platform/deploys/env/pakerti.com-react-sfa.env`
- Modify: `kodemeio-platform/deploys/instances/pakerti.com-react-hrm.yaml`
- Modify: `kodemeio-platform/deploys/instances/pakerti.com-react-sfa.yaml`

- [ ] **Step 1: Populate pakerti HRM env file**

Write to `deploys/env/pakerti.com-react-hrm.env`:

```env
VITE_HRM_APP_NAME=Pakerti HRM
VITE_HRM_API_BASE_URL=https://odoo-hrms-tpp.kodeme.io/hrm/api
VITE_AUTH_MODE=native
VITE_OIDC_AUTHORITY=
VITE_HRM_OIDC_CLIENT_ID=
VITE_HRM_OIDC_REDIRECT_URI=
VITE_HRM_THEME=hrm
```

- [ ] **Step 2: Populate pakerti SFA env file**

Write to `deploys/env/pakerti.com-react-sfa.env`:

```env
VITE_SFA_APP_NAME=Pakerti SFA
VITE_SFA_API_BASE_URL=https://odoo-trading-tpp.kodeme.io/sfa/api
VITE_AUTH_MODE=native
VITE_OIDC_AUTHORITY=
VITE_SFA_OIDC_CLIENT_ID=
VITE_SFA_OIDC_REDIRECT_URI=
VITE_SFA_THEME=sfa
```

- [ ] **Step 3: Fix pakerti HRM manifest API URL**

In `deploys/instances/pakerti.com-react-hrm.yaml`, change:

```yaml
# OLD:
env_overrides:
  VITE_HRM_API_BASE_URL: "https://odoo-hrms.pakerti.com"

# NEW:
env_overrides:
  VITE_HRM_APP_NAME: "Pakerti HRM"
  VITE_HRM_API_BASE_URL: "https://odoo-hrms-tpp.kodeme.io/hrm/api"
  VITE_AUTH_MODE: "native"
  VITE_HRM_OIDC_CLIENT_ID: ""
  VITE_HRM_OIDC_REDIRECT_URI: ""
```

- [ ] **Step 4: Fix pakerti SFA manifest API URL**

In `deploys/instances/pakerti.com-react-sfa.yaml`, change:

```yaml
# OLD:
env_overrides:
  VITE_SFA_API_BASE_URL: "https://odoo-trading.pakerti.com"

# NEW:
env_overrides:
  VITE_SFA_APP_NAME: "Pakerti SFA"
  VITE_SFA_API_BASE_URL: "https://odoo-trading-tpp.kodeme.io/sfa/api"
  VITE_AUTH_MODE: "native"
  VITE_SFA_OIDC_CLIENT_ID: ""
  VITE_SFA_OIDC_REDIRECT_URI: ""
```

- [ ] **Step 5: Commit**

```bash
git add deploys/env/pakerti.com-react-*.env deploys/instances/pakerti.com-react-*.yaml
git commit -m "fix(pakerti): populate .env files and fix API URLs with app path

Apply lessons from MAC deployment:
- .env files must have all VITE vars (not blank)
- API URLs must include FastAPI root path (/hrm/api, /sfa/api)
- VITE_AUTH_MODE=native for non-OIDC deployments"
```

---

### Task 5: Clean up MAC-specific compose files (no longer needed)

**Files:**
- Delete: `kodemeio-react/compose/docker-compose.wms-mac.yml`
- Delete: `kodemeio-react/compose/docker-compose.bia-mac.yml`
- Delete: `kodemeio-react/compose/docker-compose.hrm-mac.yml`

These were a workaround for the env var issue. Now that `.env` files are properly populated, the generic compose files work correctly.

- [ ] **Step 1: Delete MAC-specific compose files**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-react
rm compose/docker-compose.wms-mac.yml compose/docker-compose.bia-mac.yml compose/docker-compose.hrm-mac.yml
```

- [ ] **Step 2: Verify MAC manifests point to generic compose files**

Check that `mandiriagro.com-react-wms.yaml`, `mandiriagro.com-react-bia.yaml`, `mandiriagro.com-react-hrm.yaml` all use the generic compose paths (`docker-compose.wms.yml`, etc.). These were already reverted earlier.

- [ ] **Step 3: Commit**

```bash
git add -A compose/docker-compose.*-mac.yml
git commit -m "chore(docker): remove MAC-specific compose files

No longer needed now that .env files are properly populated.
Generic compose files with ${VAR} substitution work correctly
when Dokploy writes the .env file before docker compose build."
```

---

### Task 6: Document deployment checklist

**Files:**
- Create: `kodemeio-platform/docs/deployment-checklist.md`

- [ ] **Step 1: Write deployment checklist**

Create `kodemeio-platform/docs/deployment-checklist.md`:

```markdown
# React PWA + Odoo Deployment Checklist

## Before Deploy

### Odoo Instance
- [ ] Profile selected (distribution, hrms, trading, etc.)
- [ ] `.env` file populated (PGHOST, PGPASSWORD, ODOO_ADMIN_PASSWD, etc.)
- [ ] Database name follows convention: `odoo_{profile}_{customer}`

### React PWA
- [ ] `.env` file populated with ALL VITE vars (NOT blank)
- [ ] `VITE_{APP}_API_BASE_URL` includes FastAPI root path (e.g., `/wms/api`)
- [ ] `VITE_AUTH_MODE` set explicitly (`native` or `oidc`)
- [ ] `openapi.json` committed in git for the app (`git add -f apps/spa/{app}/openapi.json`)
- [ ] Docker build tested locally: `NODE_OPTIONS='--experimental-strip-types' pnpm turbo build --filter=@kodemeio/{app}`

### Deploy Manifest
- [ ] `compose_path` points to correct compose file
- [ ] `domain.service` matches service name in docker-compose.yml
- [ ] `env_overrides` API URL includes `/{app}/api` path

## Deploy

```bash
# 1. Dry-run first
kctl-dokploy deploy apply -f deploys/instances/{manifest}.yaml --dry-run

# 2. Deploy Odoo first (takes 5-10 min for init)
kctl-dokploy deploy apply -f deploys/instances/{customer}-odoo-{profile}.yaml

# 3. Deploy React apps (after Odoo is healthy)
kctl-dokploy deploy apply -f deploys/instances/{customer}-react-{app}.yaml

# 4. If env vars changed, prune Docker cache and redeploy
ssh root@{server} docker builder prune -f
kctl-dokploy compose redeploy {compose-id}
```

## After Deploy

### Auto-verified (by base_management post_init_hook)
- [x] JWT secrets generated for all apps
- [x] CORS origins set to `*` on all app records

### Manual verification
- [ ] Odoo web login works: `https://{odoo-host}/web/login`
- [ ] React app loads: `https://{app-host}/`
- [ ] React app login works (admin/admin or configured credentials)
- [ ] Enable Cloudflare proxy after Let's Encrypt cert is issued
```

- [ ] **Step 2: Commit**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
git add docs/deployment-checklist.md
git commit -m "docs: add React PWA + Odoo deployment checklist

Captures all lessons from MAC deployment: env file requirements,
API URL format, CORS/JWT auto-init, Docker cache gotchas."
```

---

## Execution Order

1. **Task 1** (BIA CORS default) — kodemeio-odoo repo
2. **Task 2** (JWT + CORS auto-init in hooks.py) — kodemeio-odoo repo
3. **Task 3** (env validation in deploy pipeline) — kodemeio-platform repo
4. **Task 4** (fix pakerti.com manifests) — kodemeio-platform repo
5. **Task 5** (clean up MAC compose files) — kodemeio-react repo
6. **Task 6** (deployment checklist doc) — kodemeio-platform repo

Tasks 1-2 can run in parallel with Tasks 3-6 (different repos).
