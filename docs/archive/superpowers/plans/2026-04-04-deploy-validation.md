# Deploy Pre/Post Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add type-aware pre-deploy validation and post-deploy smoke tests to the kctl-dokploy deploy pipeline, catching misconfigurations before they reach users.

**Architecture:** A new `deploy_validators.py` module contains all validation logic, used by both the pipeline (pre-validate + post-verify phases) and a standalone `deploy verify` command. App type is detected from `manifest.type` field (set by base templates: `react-pwa`, `odoo`, `nextjs`, `infrastructure`).

**Tech Stack:** Python 3.12+, httpx, Pydantic, pytest, kctl-dokploy CLI

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `packages/kctl-dokploy/src/kctl_dokploy/core/deploy_validators.py` | Create | Type detection + pre-validate + post-verify logic |
| `packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py` | Modify | Add `phase_pre_validate()`, enhance `phase_verify()` |
| `packages/kctl-dokploy/src/kctl_dokploy/commands/deploy.py` | Modify | Add `verify` command |
| `packages/kctl-dokploy/tests/core/test_deploy_validators.py` | Create | Tests for validators |
| `packages/kctl-dokploy/tests/core/test_deployer.py` | Modify | Tests for new phases |

---

### Task 1: Create `deploy_validators.py` with type detection and pre-validation

**Files:**
- Create: `packages/kctl-dokploy/src/kctl_dokploy/core/deploy_validators.py`
- Create: `packages/kctl-dokploy/tests/core/test_deploy_validators.py`

- [ ] **Step 1: Write tests for type detection**

Create `packages/kctl-dokploy/tests/core/test_deploy_validators.py`:

```python
"""Tests for deploy_validators — type detection and pre/post validation."""

from __future__ import annotations

import pytest

from kctl_dokploy.core.deploy_validators import DeployValidator
from kctl_dokploy.core.manifest import DeployManifest, DomainConfig, SourceConfig


class TestTypeDetection:
    def test_detect_react_pwa(self):
        m = DeployManifest(type="react-pwa")
        v = DeployValidator(manifest=m, env_vars={})
        assert v.app_type == "react-pwa"

    def test_detect_odoo(self):
        m = DeployManifest(type="odoo")
        v = DeployValidator(manifest=m, env_vars={})
        assert v.app_type == "odoo"

    def test_detect_nextjs(self):
        m = DeployManifest(type="nextjs")
        v = DeployValidator(manifest=m, env_vars={})
        assert v.app_type == "nextjs"

    def test_detect_infra(self):
        m = DeployManifest(type="infrastructure")
        v = DeployValidator(manifest=m, env_vars={})
        assert v.app_type == "infrastructure"

    def test_detect_unknown_fallback(self):
        m = DeployManifest(type="compose")
        v = DeployValidator(manifest=m, env_vars={})
        assert v.app_type == "unknown"


class TestPreValidateCommon:
    def test_valid_domain(self):
        m = DeployManifest(domain=DomainConfig(host="wms.pakerti.com", service="wms"))
        v = DeployValidator(manifest=m, env_vars={})
        warnings, errors = v.pre_validate()
        assert not errors

    def test_invalid_domain_host(self):
        m = DeployManifest(domain=DomainConfig(host="not a domain!", service="wms"))
        v = DeployValidator(manifest=m, env_vars={})
        warnings, errors = v.pre_validate()
        assert any("domain.host" in e for e in errors)

    def test_empty_service_with_domain(self):
        m = DeployManifest(domain=DomainConfig(host="app.example.com", service=""))
        v = DeployValidator(manifest=m, env_vars={})
        warnings, errors = v.pre_validate()
        assert any("domain.service" in e for e in errors)


class TestPreValidateReactPWA:
    def test_api_url_with_app_path(self):
        m = DeployManifest(type="react-pwa")
        env = {"VITE_WMS_API_BASE_URL": "https://odoo.example.com/wms/api", "VITE_AUTH_MODE": "native"}
        v = DeployValidator(manifest=m, env_vars=env)
        warnings, errors = v.pre_validate()
        assert not errors

    def test_api_url_missing_app_path(self):
        m = DeployManifest(type="react-pwa")
        env = {"VITE_WMS_API_BASE_URL": "https://odoo.example.com", "VITE_AUTH_MODE": "native"}
        v = DeployValidator(manifest=m, env_vars=env)
        warnings, errors = v.pre_validate()
        assert any("missing app path" in e for e in errors)

    def test_auth_mode_missing(self):
        m = DeployManifest(type="react-pwa")
        env = {"VITE_WMS_API_BASE_URL": "https://odoo.example.com/wms/api"}
        v = DeployValidator(manifest=m, env_vars=env)
        warnings, errors = v.pre_validate()
        assert any("VITE_AUTH_MODE" in w for w in warnings)

    def test_auth_mode_invalid(self):
        m = DeployManifest(type="react-pwa")
        env = {"VITE_AUTH_MODE": "invalid_mode"}
        v = DeployValidator(manifest=m, env_vars=env)
        warnings, errors = v.pre_validate()
        assert any("VITE_AUTH_MODE" in e for e in errors)

    def test_auth_mode_oidc_missing_authority(self):
        m = DeployManifest(type="react-pwa")
        env = {"VITE_AUTH_MODE": "oidc", "VITE_SFA_API_BASE_URL": "https://x.com/sfa/api"}
        v = DeployValidator(manifest=m, env_vars=env)
        warnings, errors = v.pre_validate()
        assert any("VITE_OIDC_AUTHORITY" in w for w in warnings)


class TestPreValidateOdoo:
    def test_db_name_too_long(self):
        m = DeployManifest(type="odoo")
        env = {"PGDATABASE": "a" * 64, "ODOO_ADMIN_PASSWD": "secret"}
        v = DeployValidator(manifest=m, env_vars=env)
        warnings, errors = v.pre_validate()
        assert any("63 characters" in e for e in errors)

    def test_admin_passwd_missing(self):
        m = DeployManifest(type="odoo")
        env = {"PGDATABASE": "odoo_test"}
        v = DeployValidator(manifest=m, env_vars=env)
        warnings, errors = v.pre_validate()
        assert any("ODOO_ADMIN_PASSWD" in w for w in warnings)

    def test_valid_odoo_env(self):
        m = DeployManifest(type="odoo")
        env = {"PGDATABASE": "odoo_test", "ODOO_ADMIN_PASSWD": "secret"}
        v = DeployValidator(manifest=m, env_vars=env)
        warnings, errors = v.pre_validate()
        assert not errors
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/kctl-dokploy && uv run pytest tests/core/test_deploy_validators.py -v`
Expected: ImportError (module doesn't exist yet)

- [ ] **Step 3: Implement `deploy_validators.py`**

Create `packages/kctl-dokploy/src/kctl_dokploy/core/deploy_validators.py`:

```python
"""Type-aware pre-deploy validation and post-deploy smoke tests.

Used by the deploy pipeline (pre_validate + post_verify phases)
and the standalone ``deploy verify`` command.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import httpx

from kctl_dokploy.core.manifest import DeployManifest

_logger = logging.getLogger(__name__)

# Known manifest types from base templates
_KNOWN_TYPES = {"react-pwa", "odoo", "nextjs", "infrastructure", "fastapi"}

# Valid FastAPI root paths (used in API URL validation)
_FASTAPI_APP_PATHS = [
    "sfa", "lfa", "shop", "wms", "bia", "hrm", "mrp",
    "eam", "asset", "dms", "tpm", "recruitment", "saas",
]

# Valid VITE_AUTH_MODE values
_VALID_AUTH_MODES = {"native", "oidc", "development"}

# FQDN regex (lowercase, dots, hyphens, no trailing dot)
_FQDN_RE = re.compile(
    r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$"
)


@dataclass
class CheckResult:
    """Result of a single validation or smoke test check."""

    name: str
    status: str  # "pass", "warn", "fail", "skip"
    detail: str = ""


@dataclass
class DeployValidator:
    """Type-aware pre-deploy validation and post-deploy smoke tests."""

    manifest: DeployManifest
    env_vars: dict[str, str] = field(default_factory=dict)
    compose_id: str = ""
    dry_run: bool = False

    @property
    def app_type(self) -> str:
        """Detect app type from manifest.type field."""
        t = self.manifest.type
        return t if t in _KNOWN_TYPES else "unknown"

    # ------------------------------------------------------------------
    # Pre-deploy validation
    # ------------------------------------------------------------------

    def pre_validate(self) -> tuple[list[str], list[str]]:
        """Run pre-deploy checks. Returns (warnings, errors)."""
        warnings: list[str] = []
        errors: list[str] = []

        self._validate_common(warnings, errors)

        if self.app_type == "react-pwa":
            self._validate_react_pwa(warnings, errors)
        elif self.app_type == "odoo":
            self._validate_odoo(warnings, errors)

        return warnings, errors

    def _validate_common(self, warnings: list[str], errors: list[str]) -> None:
        """Checks that apply to all manifest types."""
        domain = self.manifest.domain

        # domain.host must be a valid FQDN if set
        if domain.host and not _FQDN_RE.match(domain.host):
            errors.append(
                f"domain.host '{domain.host}' is not a valid FQDN"
            )

        # domain.service must be set if domain.host is configured
        if domain.host and not domain.service:
            errors.append(
                "domain.service is empty — Traefik routing will fail. "
                "Must match a service name in the docker-compose file."
            )

    def _validate_react_pwa(self, warnings: list[str], errors: list[str]) -> None:
        """Checks specific to React PWA deployments."""
        env = self.env_vars

        # API base URL must include FastAPI root path
        for key, val in env.items():
            if key.startswith("VITE_") and key.endswith("_API_BASE_URL") and val:
                if not any(val.endswith(f"/{app}/api") for app in _FASTAPI_APP_PATHS):
                    errors.append(
                        f"{key}={val} — missing app path (e.g., /wms/api). "
                        f"Login will fail without the FastAPI root path."
                    )

        # VITE_AUTH_MODE must be set
        auth_mode = env.get("VITE_AUTH_MODE", "")
        if not auth_mode:
            warnings.append("VITE_AUTH_MODE not set — defaults to 'oidc'")
        elif auth_mode not in _VALID_AUTH_MODES:
            errors.append(
                f"VITE_AUTH_MODE='{auth_mode}' is invalid. "
                f"Must be one of: {', '.join(sorted(_VALID_AUTH_MODES))}"
            )

        # OIDC mode needs authority
        if auth_mode == "oidc":
            authority = env.get("VITE_OIDC_AUTHORITY", "")
            if not authority:
                warnings.append(
                    "VITE_AUTH_MODE=oidc but VITE_OIDC_AUTHORITY is empty — "
                    "OIDC login will fail"
                )

    def _validate_odoo(self, warnings: list[str], errors: list[str]) -> None:
        """Checks specific to Odoo deployments."""
        env = self.env_vars

        # Database name length
        db_name = env.get("PGDATABASE", "") or env.get("ODOO_DB_NAME", "")
        if db_name and len(db_name) > 63:
            errors.append(
                f"Database name '{db_name}' exceeds PostgreSQL limit of 63 characters"
            )

        # Admin password should be set
        if not env.get("ODOO_ADMIN_PASSWD"):
            warnings.append("ODOO_ADMIN_PASSWD not set in environment")

    # ------------------------------------------------------------------
    # Post-deploy smoke tests
    # ------------------------------------------------------------------

    def post_verify(self) -> list[CheckResult]:
        """Run post-deploy smoke tests. Returns list of check results."""
        results: list[CheckResult] = []

        if self.app_type == "react-pwa":
            self._verify_react_pwa(results)
        elif self.app_type == "odoo":
            self._verify_odoo(results)
        elif self.app_type == "nextjs":
            self._verify_nextjs(results)

        return results

    def _verify_react_pwa(self, results: list[CheckResult]) -> None:
        """Post-deploy checks for React PWA apps."""
        domain = self.manifest.domain
        env = self.env_vars

        # Find API base URL from env
        api_url = ""
        for key, val in env.items():
            if key.startswith("VITE_") and key.endswith("_API_BASE_URL") and val:
                api_url = val
                break

        if not api_url:
            results.append(CheckResult("api_url", "skip", "No VITE_*_API_BASE_URL in env"))
            return

        # Check 1: CORS preflight
        try:
            resp = httpx.options(
                f"{api_url}/auth/login",
                headers={
                    "Origin": f"https://{domain.host}",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                },
                verify=False,
                timeout=10,
            )
            if resp.status_code == 200 and "access-control-allow-origin" in resp.headers:
                results.append(CheckResult("cors_preflight", "pass", "CORS headers present"))
            elif resp.status_code == 405:
                results.append(CheckResult(
                    "cors_preflight", "warn",
                    "OPTIONS returned 405 — CORS middleware not active. "
                    "Set cors_allowed_origins=* on the app record in Odoo."
                ))
            else:
                results.append(CheckResult(
                    "cors_preflight", "warn",
                    f"Unexpected status {resp.status_code}"
                ))
        except Exception as exc:
            results.append(CheckResult("cors_preflight", "skip", f"Connection error: {exc}"))

        # Check 2: Login endpoint reachable (not 404)
        try:
            resp = httpx.post(
                f"{api_url}/auth/login",
                json={"login": "__probe__", "password": "__probe__"},
                headers={"Content-Type": "application/json"},
                verify=False,
                timeout=10,
            )
            if resp.status_code == 404:
                results.append(CheckResult(
                    "login_endpoint", "warn",
                    f"POST {api_url}/auth/login returned 404 — "
                    "FastAPI endpoint not registered or wrong app path"
                ))
            else:
                results.append(CheckResult(
                    "login_endpoint", "pass",
                    f"Endpoint reachable (status {resp.status_code})"
                ))
        except Exception as exc:
            results.append(CheckResult("login_endpoint", "skip", f"Connection error: {exc}"))

    def _verify_odoo(self, results: list[CheckResult]) -> None:
        """Post-deploy checks for Odoo instances."""
        domain = self.manifest.domain
        env = self.env_vars
        host = domain.host or "localhost"
        scheme = "https" if domain.https else "http"
        db_name = env.get("PGDATABASE", "") or env.get("ODOO_DB_NAME", "")

        if not db_name:
            results.append(CheckResult("odoo_db", "skip", "No database name in env"))
            return

        # Check 1: Query ir.config_parameter for JWT secrets
        jwt_apps = [
            "sfa", "lfa", "shop", "wms", "mrp", "hrm", "bia",
            "asset", "dms", "tpm", "recruitment", "saas", "intercompany",
        ]
        missing_jwt: list[str] = []
        try:
            for app in jwt_apps:
                resp = httpx.post(
                    f"{scheme}://{host}/jsonrpc",
                    json={
                        "jsonrpc": "2.0",
                        "method": "call",
                        "params": {
                            "service": "object",
                            "method": "execute_kw",
                            "args": [
                                db_name, 2, "admin",
                                "ir.config_parameter", "get_param",
                                [f"{app}.jwt_secret", ""],
                            ],
                        },
                        "id": 1,
                    },
                    verify=False,
                    timeout=10,
                )
                data = resp.json()
                secret = data.get("result", "")
                if not secret or len(secret) < 32 or "CHANGE-IN-PRODUCTION" in secret:
                    missing_jwt.append(app)

            if missing_jwt:
                results.append(CheckResult(
                    "jwt_secrets", "warn",
                    f"Missing/weak JWT secrets for: {', '.join(missing_jwt)}. "
                    "Run: kctl-odoo bundles profile-install or upgrade base_management."
                ))
            else:
                results.append(CheckResult("jwt_secrets", "pass", "All JWT secrets set"))
        except Exception as exc:
            results.append(CheckResult("jwt_secrets", "skip", f"JSON-RPC error: {exc}"))

        # Check 2: No stuck modules
        try:
            resp = httpx.post(
                f"{scheme}://{host}/jsonrpc",
                json={
                    "jsonrpc": "2.0",
                    "method": "call",
                    "params": {
                        "service": "object",
                        "method": "execute_kw",
                        "args": [
                            db_name, 2, "admin",
                            "ir.module.module", "search_count",
                            [[["state", "in", ["to upgrade", "to install", "to remove"]]]],
                        ],
                    },
                    "id": 1,
                },
                verify=False,
                timeout=10,
            )
            count = resp.json().get("result", 0)
            if count > 0:
                results.append(CheckResult(
                    "stuck_modules", "warn",
                    f"{count} module(s) stuck in to_upgrade/to_install/to_remove state"
                ))
            else:
                results.append(CheckResult("stuck_modules", "pass", "No stuck modules"))
        except Exception as exc:
            results.append(CheckResult("stuck_modules", "skip", f"JSON-RPC error: {exc}"))

    def _verify_nextjs(self, results: list[CheckResult]) -> None:
        """Post-deploy checks for Next.js apps."""
        domain = self.manifest.domain
        host = domain.host or "localhost"
        scheme = "https" if domain.https else "http"

        # Check: root path returns 200 or 30x (not 404)
        try:
            resp = httpx.get(
                f"{scheme}://{host}/",
                follow_redirects=False,
                verify=False,
                timeout=10,
            )
            if resp.status_code == 404:
                results.append(CheckResult(
                    "root_path", "warn",
                    "Root / returns 404 — missing i18n middleware? "
                    "Add middleware.ts with next-intl createMiddleware."
                ))
            else:
                results.append(CheckResult(
                    "root_path", "pass",
                    f"Root / returns {resp.status_code}"
                ))
        except Exception as exc:
            results.append(CheckResult("root_path", "skip", f"Connection error: {exc}"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/kctl-dokploy && uv run pytest tests/core/test_deploy_validators.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/core/deploy_validators.py \
       packages/kctl-dokploy/tests/core/test_deploy_validators.py
git commit -m "feat(deploy): add deploy_validators module with type-aware checks

Pre-validate: domain format, React API URL path, auth mode, Odoo DB
name length. Post-verify: CORS preflight, login endpoint, JWT secrets,
stuck modules, Next.js root path."
```

---

### Task 2: Integrate pre-validate into deployer pipeline

**Files:**
- Modify: `packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py`
- Modify: `packages/kctl-dokploy/tests/core/test_deployer.py`

- [ ] **Step 1: Write test for phase_pre_validate**

Add to `packages/kctl-dokploy/tests/core/test_deployer.py`:

```python
class TestPhasePreValidate:
    """Tests for phase_pre_validate — type-aware config validation."""

    def test_react_pwa_valid_env_passes(self):
        m = DeployManifest(
            type="react-pwa",
            domain=DomainConfig(host="wms.example.com", service="wms"),
        )
        deployer = Deployer(manifest=m, dry_run=True)
        deployer._merged_env = {
            "VITE_WMS_API_BASE_URL": "https://odoo.example.com/wms/api",
            "VITE_AUTH_MODE": "native",
        }
        deployer.phase_pre_validate()
        result = deployer.results[-1]
        assert result.action != "failed"

    def test_react_pwa_bad_url_blocks(self):
        m = DeployManifest(
            type="react-pwa",
            domain=DomainConfig(host="wms.example.com", service="wms"),
        )
        deployer = Deployer(manifest=m, dry_run=True)
        deployer._merged_env = {
            "VITE_WMS_API_BASE_URL": "https://odoo.example.com",
            "VITE_AUTH_MODE": "native",
        }
        deployer.phase_pre_validate()
        result = deployer.results[-1]
        assert result.action == "failed"
```

- [ ] **Step 2: Add `phase_pre_validate()` to deployer**

In `packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py`, add the import at the top:

```python
from kctl_dokploy.core.deploy_validators import DeployValidator
```

Add a new field to the `Deployer` dataclass (after `_compose_id`):

```python
    _merged_env: dict[str, str] = field(default_factory=dict, init=False)
```

Add the method (before `phase_dns`, around line 240):

```python
    def phase_pre_validate(self) -> None:
        """Type-aware pre-deploy validation (before DNS phase)."""
        validator = DeployValidator(
            manifest=self.manifest,
            env_vars=self._merged_env,
            dry_run=self.dry_run,
        )

        warnings, errors = validator.pre_validate()

        for w in warnings:
            _logger.warning("PRE-VALIDATE: %s", w)

        if errors:
            msg = f"Pre-validation failed ({len(errors)} error(s)): " + "; ".join(errors)
            self._record_phase("pre_validate", "failed", msg)
        elif warnings:
            msg = f"Pre-validation passed with {len(warnings)} warning(s)"
            self._record_phase("pre_validate", self._action("updated"), msg)
        else:
            self._record_phase("pre_validate", self._action("updated"), "All checks passed")
```

In `phase_environment()`, save the merged env to `self._merged_env` after merging (find the line where `merged` dict is built, add `self._merged_env = merged` after it).

In `run_all()`, add `self.phase_pre_validate()` after `self.phase_validate()` and its abort check, BEFORE `self.phase_dns()`:

```python
        self.phase_validate()

        if self.results and self.results[-1].action == "failed":
            return self.results

        self.phase_pre_validate()

        if self.results and self.results[-1].action == "failed":
            return self.results

        self.phase_dns()
```

Note: `phase_pre_validate` needs env vars, but `phase_environment` hasn't run yet. The pre-validate should load env vars itself from the manifest's `env_file` + `env_defaults` + `env_overrides` (same merge logic). Add this to the beginning of `phase_pre_validate`:

```python
    def phase_pre_validate(self) -> None:
        """Type-aware pre-deploy validation (before DNS phase)."""
        # Build merged env for validation (same logic as phase_environment)
        if not self._merged_env:
            merged = dict(self.manifest.env_defaults)
            if self.manifest.env_file:
                import pathlib
                env_path = pathlib.Path(self.manifest.env_file)
                if env_path.exists():
                    for line in env_path.read_text().splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, _, v = line.partition("=")
                            merged[k.strip()] = v.strip()
            merged.update(self.manifest.env_overrides)
            self._merged_env = merged

        validator = DeployValidator(
            manifest=self.manifest,
            env_vars=self._merged_env,
            dry_run=self.dry_run,
        )
        # ... rest as above
```

- [ ] **Step 3: Run tests**

Run: `cd packages/kctl-dokploy && uv run pytest tests/core/test_deployer.py -v -k "pre_validate"`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py \
       packages/kctl-dokploy/tests/core/test_deployer.py
git commit -m "feat(deploy): integrate phase_pre_validate into pipeline

Runs type-aware validation after manifest validation but before DNS.
Errors block the deploy. Warnings are logged but don't block."
```

---

### Task 3: Enhance phase_verify with post-deploy smoke tests

**Files:**
- Modify: `packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py`

- [ ] **Step 1: Enhance `phase_verify()` to run smoke tests after healthcheck**

In `deployer.py`, modify `phase_verify()`. After the healthcheck passes (the line `self._record_phase("verify", "updated", f"Healthcheck passed: ...")`), add smoke test execution:

```python
                if resp.status_code == hc.expected_status:
                    self._record_phase("verify", "updated", f"Healthcheck passed: {url} → {resp.status_code}")

                    # Run post-deploy smoke tests (warnings only, non-blocking)
                    validator = DeployValidator(
                        manifest=self.manifest,
                        env_vars=self._merged_env,
                        compose_id=self._compose_id,
                    )
                    smoke_results = validator.post_verify()
                    for r in smoke_results:
                        if r.status == "warn":
                            _logger.warning("SMOKE TEST [%s]: %s — %s", r.status.upper(), r.name, r.detail)
                        elif r.status == "pass":
                            _logger.info("SMOKE TEST [%s]: %s — %s", r.status.upper(), r.name, r.detail)
                        else:
                            _logger.info("SMOKE TEST [%s]: %s — %s", r.status.upper(), r.name, r.detail)

                    warn_count = sum(1 for r in smoke_results if r.status == "warn")
                    if warn_count:
                        self._record_phase(
                            "smoke_tests", "updated",
                            f"{len(smoke_results)} checks run, {warn_count} warning(s)"
                        )
                    elif smoke_results:
                        self._record_phase("smoke_tests", "updated", f"{len(smoke_results)} checks passed")

                    return
```

- [ ] **Step 2: Test manually with dry-run**

Run: `kctl-dokploy deploy apply -f deploys/instances/mandiriagro.com-react-wms.yaml --dry-run`
Expected: Pre-validate phase appears in output, no errors

- [ ] **Step 3: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py
git commit -m "feat(deploy): add post-deploy smoke tests after healthcheck

After healthcheck passes, runs type-specific checks: CORS preflight,
login endpoint reachability (React PWA), JWT secrets, stuck modules
(Odoo), root path (Next.js). All warnings, non-blocking."
```

---

### Task 4: Add standalone `deploy verify` command

**Files:**
- Modify: `packages/kctl-dokploy/src/kctl_dokploy/commands/deploy.py`

- [ ] **Step 1: Add verify command**

In `packages/kctl-dokploy/src/kctl_dokploy/commands/deploy.py`, add a new command after the existing ones:

```python
@app.command()
def verify(
    file: Annotated[Path, typer.Option("-f", "--file", help="Manifest YAML file")] = ...,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview checks")] = False,
) -> None:
    """Run post-deploy smoke tests on an existing deployment.

    Validates that the deployment is healthy beyond just the healthcheck:
    CORS, JWT secrets, login endpoints, stuck modules, etc.
    """
    c = ctx()
    manifest = load_and_resolve(str(file))

    # Build merged env
    merged: dict[str, str] = dict(manifest.env_defaults)
    if manifest.env_file:
        env_path = Path(manifest.env_file)
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    merged[k.strip()] = v.strip()
    merged.update(manifest.env_overrides)

    from kctl_dokploy.core.deploy_validators import DeployValidator, CheckResult

    validator = DeployValidator(manifest=manifest, env_vars=merged, dry_run=dry_run)

    # Pre-validate
    c.output.info(f"Type: {validator.app_type}")
    warnings, errors = validator.pre_validate()

    rows = []
    for e in errors:
        rows.append({"Check": "pre-validate", "Status": "FAIL", "Detail": e})
    for w in warnings:
        rows.append({"Check": "pre-validate", "Status": "WARN", "Detail": w})
    if not errors and not warnings:
        rows.append({"Check": "pre-validate", "Status": "PASS", "Detail": "All checks passed"})

    # Post-verify (smoke tests)
    if not dry_run:
        smoke = validator.post_verify()
        for r in smoke:
            rows.append({"Check": r.name, "Status": r.status.upper(), "Detail": r.detail})
    else:
        rows.append({"Check": "smoke_tests", "Status": "SKIP", "Detail": "Dry-run mode"})

    c.output.table(rows, title=f"Deployment Verification: {manifest.instance.name}")
```

- [ ] **Step 2: Add import for Path**

Make sure `from pathlib import Path` is imported at the top of `deploy.py`.

- [ ] **Step 3: Test**

Run: `kctl-dokploy deploy verify -f deploys/instances/mandiriagro.com-react-wms.yaml`
Expected: Table output with pre-validate + smoke test results

- [ ] **Step 4: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/commands/deploy.py
git commit -m "feat(deploy): add standalone 'deploy verify' command

Runs pre-validate checks and post-deploy smoke tests on an existing
deployment. Useful for monitoring and debugging without redeploying."
```

---

## Execution Order

1. **Task 1**: Create `deploy_validators.py` + tests (foundation)
2. **Task 2**: Integrate `phase_pre_validate` into pipeline
3. **Task 3**: Enhance `phase_verify` with smoke tests
4. **Task 4**: Add `deploy verify` standalone command

Tasks are sequential — each builds on the previous.
