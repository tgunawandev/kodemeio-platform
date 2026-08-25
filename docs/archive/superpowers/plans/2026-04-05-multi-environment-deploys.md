# Multi-Environment Deploys Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable production + staging deployment from the same manifest pipeline, with environment-scoped directories, env files, and kctl-dokploy deployer support.

**Architecture:** Split `deploys/instances/` and `deploys/env/` into `production/` and `staging/` subdirectories. Add `environment` field to `DeployManifest`. Update deployer `phase_compose()` to target the correct Dokploy environment. Update `generate.py` to produce both environments from tenant config.

**Tech Stack:** Python 3.12, Pydantic 2, Typer, PyYAML, pytest

**Spec:** `docs/superpowers/specs/2026-04-05-multi-environment-deploys-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `packages/kctl-dokploy/src/kctl_dokploy/core/manifest.py` | Add `environment` field to `DeployManifest` |
| Modify | `packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py` | Target correct Dokploy environment in `phase_compose()` |
| Modify | `packages/kctl-dokploy/tests/core/test_manifest.py` | Test `environment` field parsing and merging |
| Modify | `packages/kctl-dokploy/tests/core/test_deployer.py` | Test environment-aware compose creation |
| Move | `deploys/instances/*.yaml` → `deploys/instances/production/*.yaml` | Restructure directories |
| Move | `deploys/env/.env.*` → `deploys/env/production/.env.*` | Restructure directories |
| Modify | All 34 production manifests | Update `extends:` and `env_file:` paths |
| Modify | `deploys/tenants/mac.yaml` | Add `environments` block |
| Modify | `deploys/tenants/tpp.yaml` | Add `environments` block |
| Modify | `deploys/generate.py` | Generate both environments |
| Modify | `.gitignore` | Update env file patterns |
| Modify | `.github/workflows/deploy.yml` | Update paths |

---

### Task 1: Add `environment` field to DeployManifest

**Files:**
- Modify: `packages/kctl-dokploy/src/kctl_dokploy/core/manifest.py:119-148`
- Test: `packages/kctl-dokploy/tests/core/test_manifest.py`

- [ ] **Step 1: Write failing test for environment field**

Add to `packages/kctl-dokploy/tests/core/test_manifest.py`:

```python
def test_environment_field_defaults_to_production():
    """DeployManifest.environment defaults to 'production'."""
    from kctl_dokploy.core.manifest import DeployManifest
    m = DeployManifest()
    assert m.environment == "production"


def test_environment_field_from_yaml(tmp_path):
    """environment field is parsed from YAML."""
    manifest_file = tmp_path / "staging.yaml"
    manifest_file.write_text(
        "kind: instance\n"
        "environment: staging\n"
        "instance:\n"
        "  name: test-app\n"
    )
    m = load_manifest(manifest_file)
    assert m.environment == "staging"


def test_merge_environment_instance_wins():
    """Instance environment overrides base environment."""
    from kctl_dokploy.core.manifest import DeployManifest
    base = DeployManifest(environment="production")
    instance = DeployManifest(environment="staging")
    merged = merge_manifests(base, instance)
    assert merged.environment == "staging"


def test_merge_environment_base_kept_when_instance_default():
    """Base environment is kept when instance uses default."""
    from kctl_dokploy.core.manifest import DeployManifest
    base = DeployManifest(environment="production")
    instance = DeployManifest()  # environment defaults to "production"
    merged = merge_manifests(base, instance)
    assert merged.environment == "production"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/kctl-dokploy && uv run pytest tests/core/test_manifest.py -k "environment" -v`
Expected: FAIL — `DeployManifest` has no `environment` attribute

- [ ] **Step 3: Add environment field to DeployManifest**

In `packages/kctl-dokploy/src/kctl_dokploy/core/manifest.py`, add `environment` to the `DeployManifest` class after `project`:

```python
class DeployManifest(BaseModel):
    """Top-level deployment manifest."""

    kind: str = "deploy"
    type: str = "compose"
    extends: str | None = None

    source: SourceConfig = Field(default_factory=SourceConfig)
    server: str = ""
    project: str = ""
    environment: str = "production"  # NEW — targets Dokploy environment

    instance: InstanceConfig = Field(default_factory=InstanceConfig)
    # ... rest unchanged
```

- [ ] **Step 4: Add environment to merge_manifests**

In the `merge_manifests` function, add `environment` to the scalar picks:

```python
    # -- Top-level scalars --
    kind = _pick("kind")
    mtype = _pick("type")
    server = _pick("server")
    project = _pick("project")
    environment = _pick("environment")  # NEW
```

And include it in the return:

```python
    return DeployManifest(
        kind=kind,
        type=mtype,
        extends=None,
        source=SourceConfig(**source_merged),
        server=server,
        project=project,
        environment=environment,  # NEW
        instance=InstanceConfig(**instance_merged),
        # ... rest unchanged
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd packages/kctl-dokploy && uv run pytest tests/core/test_manifest.py -k "environment" -v`
Expected: 4 tests PASS

- [ ] **Step 6: Run full manifest test suite**

Run: `cd packages/kctl-dokploy && uv run pytest tests/core/test_manifest.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/core/manifest.py packages/kctl-dokploy/tests/core/test_manifest.py
git commit -m "feat(manifest): add environment field to DeployManifest"
```

---

### Task 2: Update deployer to target correct Dokploy environment

**Files:**
- Modify: `packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py:449-570`

- [ ] **Step 1: Refactor phase_compose to find environment by name**

In `packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py`, replace the environment search logic in `phase_compose()`. Find the block starting at line ~464:

```python
        # Search environments[].compose[] for existing compose by name
        existing_composes: list[dict[str, Any]] = []
        default_environment_id: str = ""
        for env in (project_data or {}).get("environments", []):
            if env.get("isDefault"):
                default_environment_id = env.get("environmentId", "")
            for comp in env.get("compose", []):
                existing_composes.append(comp)
```

Replace with:

```python
        # Find the target Dokploy environment by name
        target_env_name = self.manifest.environment or "production"
        target_env_id: str = ""
        target_env_data: dict[str, Any] = {}
        default_environment_id: str = ""

        for env in (project_data or {}).get("environments", []):
            if env.get("isDefault"):
                default_environment_id = env.get("environmentId", "")
            if (env.get("name") or "").lower() == target_env_name.lower():
                target_env_id = env.get("environmentId", "")
                target_env_data = env

        # Auto-create the environment if it doesn't exist
        if not target_env_id and target_env_name.lower() != "production":
            client = self._get_client()
            project_id = (project_data or {}).get("projectId", "")
            if client and project_id:
                try:
                    result = client.post(
                        "/environment.create",
                        json={
                            "projectId": project_id,
                            "name": target_env_name,
                            "description": f"{target_env_name} environment",
                        },
                    )
                    target_env_id = (result or {}).get("environmentId", "") if isinstance(result, dict) else ""
                    target_env_data = {"environmentId": target_env_id, "compose": []}
                    self._log(f"Created Dokploy environment '{target_env_name}': {target_env_id}")
                except Exception as exc:
                    self._log(f"WARNING: Failed to create environment '{target_env_name}': {exc}")

        # Fall back to default environment if target not found
        if not target_env_id:
            target_env_id = default_environment_id
            for env in (project_data or {}).get("environments", []):
                if env.get("environmentId") == default_environment_id:
                    target_env_data = env
                    break

        # Search ONLY the target environment for existing compose
        existing_composes: list[dict[str, Any]] = []
        for comp in target_env_data.get("compose", []):
            existing_composes.append(comp)
```

- [ ] **Step 2: Update compose create to use target_env_id**

Find the line (around ~512):

```python
        # Create new compose — positional arg is environment_id (or project_id for older API)
        create_args = [
            "kctl-dokploy",
            "compose",
            "create",
            default_environment_id or (project_data or {}).get("projectId", ""),
```

Replace with:

```python
        # Create new compose in the target environment
        create_args = [
            "kctl-dokploy",
            "compose",
            "create",
            target_env_id or default_environment_id or (project_data or {}).get("projectId", ""),
```

- [ ] **Step 3: Run deployer tests**

Run: `cd packages/kctl-dokploy && uv run pytest tests/core/test_deployer.py -v`
Expected: All existing tests PASS

- [ ] **Step 4: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py
git commit -m "feat(deployer): target correct Dokploy environment from manifest"
```

---

### Task 3: Restructure deploys/instances/ into production/ subdirectory

**Files:**
- Move: All 34 files in `deploys/instances/*.yaml` → `deploys/instances/production/*.yaml`
- Modify: All 34 production manifests — update `extends:` paths

- [ ] **Step 1: Create production subdirectory and move manifests**

```bash
mkdir -p deploys/instances/production
git mv deploys/instances/*.yaml deploys/instances/production/
```

- [ ] **Step 2: Update extends paths in all production manifests**

All manifests currently have `extends: ../bases/X.yaml`. After moving one level deeper, they need `extends: ../../bases/X.yaml`.

```bash
cd deploys/instances/production
sed -i 's|extends: ../bases/|extends: ../../bases/|' *.yaml
```

- [ ] **Step 3: Update env_file paths in all production manifests**

All manifests currently have `env_file: ../env/.env.X`. After moving one level deeper, they need `env_file: ../../env/production/.env.X`.

```bash
sed -i 's|env_file: ../env/|env_file: ../../env/production/|' *.yaml
```

- [ ] **Step 4: Verify extends paths are correct**

```bash
grep 'extends:' deploys/instances/production/*.yaml | grep -v '../../bases/' && echo "ERROR: Bad extends paths" || echo "ALL OK"
```

Expected: `ALL OK`

- [ ] **Step 5: Verify env_file paths are correct**

```bash
grep 'env_file:' deploys/instances/production/*.yaml | grep -v '../../env/production/' && echo "ERROR: Bad env_file paths" || echo "ALL OK"
```

Expected: `ALL OK`

- [ ] **Step 6: Commit**

```bash
git add deploys/instances/
git commit -m "refactor(deploys): move instances to instances/production/ subdirectory"
```

---

### Task 4: Restructure deploys/env/ into production/ subdirectory

**Files:**
- Move: All `.env.*` files from `deploys/env/` → `deploys/env/production/`
- Modify: `.gitignore`

- [ ] **Step 1: Create production env subdirectory and move files**

```bash
mkdir -p deploys/env/production deploys/env/staging
mv deploys/env/.env.* deploys/env/production/
```

Note: `mv` not `git mv` because env files are gitignored.

- [ ] **Step 2: Update .gitignore**

Replace the current env pattern in `.gitignore`:

```
# Deploy env files (.env.{tenant}-{stack}-{app})
deploys/env/production/.env.*
deploys/env/staging/.env.*
```

- [ ] **Step 3: Verify env files are in correct location**

```bash
ls deploys/env/production/ | head -5
ls deploys/env/.env.* 2>/dev/null && echo "ERROR: Files remain in root" || echo "ALL OK"
```

Expected: Files listed in production/, `ALL OK` for root check

- [ ] **Step 4: Update deploy.yml CI workflow paths**

In `.github/workflows/deploy.yml`, update the paths trigger:

```yaml
on:
  push:
    branches: [main]
    paths:
      - 'deploys/instances/**'
```

And update the diff command:

```yaml
          git diff --name-only HEAD~1 HEAD -- deploys/instances/ || true
```

These already use `**` globs so they work with the new subdirectory structure. No change needed.

- [ ] **Step 5: Commit**

```bash
git add .gitignore deploys/instances/ .github/workflows/deploy.yml
git commit -m "refactor(deploys): move env files to env/production/ subdirectory"
```

---

### Task 5: Update tenant configs with environments block

**Files:**
- Modify: `deploys/tenants/mac.yaml`
- Modify: `deploys/tenants/tpp.yaml`

- [ ] **Step 1: Update mac.yaml**

Add `environments` block to `deploys/tenants/mac.yaml` after the `tenant` block:

```yaml
tenant:
  code: mac
  name: "Mandiri Agro"
  short_name: "MAC"
  domain: mandiriagro.com

environments:
  production:
    server: mac-prod-01
    dns_prefix: ""
    db_prefix: ""
    auto_deploy: false
  staging:
    server: mac-stg-01
    dns_prefix: "stg-"
    db_prefix: "stg_"
    auto_deploy: true

odoo:
  - profile: distribution
    short: dist
    description: "Distribution (SFA, LFA, WMS, DMS, retail, marketplace, BI)"
    workers: 2
    apps: [bia, wms]
  - profile: hrms
    short: hrms
    description: "HRMS (employees, attendance, payroll, leaves, expenses)"
    workers: 2
    apps: [hrm]

web:
  corporate:
    compose_brand: mandiriagro
  careers: true

services:
  notify: true
```

- [ ] **Step 2: Update tpp.yaml**

Add `environments` block to `deploys/tenants/tpp.yaml` after the `tenant` block:

```yaml
tenant:
  code: tpp
  name: "Pakerti"
  short_name: "Pakerti"
  domain: pakerti.com

environments:
  production:
    server: kod-prod-01
    dns_prefix: ""
    db_prefix: ""
    auto_deploy: false
  staging:
    server: kod-prod-02
    dns_prefix: "stg-"
    db_prefix: "stg_"
    auto_deploy: true

odoo:
  - profile: trading
    short: trad
    description: "Trading (import/export, multi-currency, landed costs)"
    workers: 4
    apps: [sfa, bia, wms]
  - profile: hrms
    short: hrms
    description: "HRMS (employees, attendance, payroll, leaves, expenses)"
    workers: 2
    apps: [hrm]

web:
  corporate:
    compose_brand: pakerti
  careers: true

services:
  notify: true
```

- [ ] **Step 3: Commit**

```bash
git add deploys/tenants/
git commit -m "feat(tenants): add environments block with server/dns/db config"
```

---

### Task 6: Update generate.py for multi-environment output

**Files:**
- Modify: `deploys/generate.py`

- [ ] **Step 1: Update output directories**

Change the constants at the top of `deploys/generate.py`:

```python
DEPLOY_DIR = Path(__file__).parent
TENANTS_DIR = DEPLOY_DIR / "tenants"
INSTANCES_DIR = DEPLOY_DIR / "instances"
ENV_DIR = DEPLOY_DIR / "env"
```

These stay the same — the environment subdirectory is appended dynamically.

- [ ] **Step 2: Add environment parameters to all generators**

Update every `gen_*` function signature to accept environment config. Each generator needs these additional parameters:

```python
def gen_react_pwa(
    tenant: dict, odoo_entry: dict, app: str,
    env_name: str = "production",
    server: str = "",
    dns_prefix: str = "",
    db_prefix: str = "",
) -> tuple[str, str, str, str | None]:
```

Then inside each generator, apply the prefixes:

- `environment: {env_name}` field in the instance dict
- `server: {server}` field
- DNS name: `{dns_prefix}{code}-{app}`
- Domain host: `{dns_prefix}{code}-{app}.{domain}`
- Database name: `{db_prefix}{code}_odoo_{short}` (odoo only)
- `env_file: ../../env/{env_name}/.env.{code}-{stack}-{app}`
- `extends: ../../bases/{base}.yaml`
- Env override URLs use `{dns_prefix}` in all Odoo URL references

- [ ] **Step 3: Update generate_tenant to loop over environments**

Replace the current `generate_tenant` function body to loop over environments:

```python
def generate_tenant(tenant_path: Path) -> list[tuple[Path, str]]:
    raw = load_tenant(tenant_path)
    t = raw["tenant"]
    code = t["code"]

    t["_odoo_entries"] = raw.get("odoo", [])

    header = HEADER.format(code=code)
    files: list[tuple[Path, str]] = []

    # Default: production only (backward compatible)
    environments = raw.get("environments", {
        "production": {"server": "", "dns_prefix": "", "db_prefix": ""},
    })

    for env_name, env_config in environments.items():
        server = env_config.get("server", "")
        dns_prefix = env_config.get("dns_prefix", "")
        db_prefix = env_config.get("db_prefix", "")

        inst_dir = INSTANCES_DIR / env_name
        env_dir = ENV_DIR / env_name

        # Odoo + React PWAs
        for odoo_entry in raw.get("odoo", []):
            y_name, y_content, e_name, e_content = gen_odoo(
                t, odoo_entry, env_name, server, dns_prefix, db_prefix,
            )
            files.append((inst_dir / y_name, header + y_content))
            files.append((env_dir / e_name, e_content))

            for app in odoo_entry.get("apps", []):
                y_name, y_content, e_name, e_content = gen_react_pwa(
                    t, odoo_entry, app, env_name, server, dns_prefix, db_prefix,
                )
                files.append((inst_dir / y_name, header + y_content))
                files.append((env_dir / e_name, e_content))

        # Next.js corporate
        web = raw.get("web", {})
        if "corporate" in web:
            t["_web_corporate_brand"] = web["corporate"]["compose_brand"]
            y_name, y_content, e_name, e_content = gen_nextjs_corporate(
                t, env_name, server, dns_prefix,
            )
            files.append((inst_dir / y_name, header + y_content))
            files.append((env_dir / e_name, e_content))

        # Next.js careers
        if web.get("careers"):
            y_name, y_content, e_name, e_content = gen_nextjs_careers(
                t, env_name, server, dns_prefix,
            )
            files.append((inst_dir / y_name, header + y_content))
            files.append((env_dir / e_name, e_content))

        # Notify
        services = raw.get("services", {})
        if services.get("notify"):
            y_name, y_content, e_name, e_content = gen_notify(
                t, env_name, server, dns_prefix,
            )
            files.append((inst_dir / y_name, header + y_content))
            files.append((env_dir / e_name, e_content))

    return files
```

- [ ] **Step 4: Ensure output directories are created**

In the `main()` function, before writing files, ensure directories exist:

```python
    for path, content in all_files:
        path.parent.mkdir(parents=True, exist_ok=True)
        # ... rest of write logic
```

- [ ] **Step 5: Update is_secret_env for new paths**

```python
def is_secret_env(path: Path) -> bool:
    name = path.name
    return (
        "-odoo-" in name and name.startswith(".env.")
        or "-hono-notify" in name and name.startswith(".env.")
    )
```

This is unchanged — it checks the filename, not the directory.

- [ ] **Step 6: Test generator dry-run**

```bash
cd deploys && python generate.py --dry-run
```

Expected: Shows `WOULD WRITE` for both `instances/production/` and `instances/staging/` paths.

- [ ] **Step 7: Commit**

```bash
git add deploys/generate.py
git commit -m "feat(generate): produce manifests for production and staging environments"
```

---

### Task 7: Generate staging manifests and verify

**Files:**
- Generated: `deploys/instances/staging/*.yaml`
- Generated: `deploys/env/staging/.env.*`

- [ ] **Step 1: Run generator**

```bash
cd deploys && python generate.py
```

- [ ] **Step 2: Verify staging manifests exist**

```bash
ls deploys/instances/staging/
```

Expected: Staging manifests for mac and tpp tenants (same count as production tenant-generated files).

- [ ] **Step 3: Verify staging manifest content**

```bash
grep -E 'environment:|server:|host:' deploys/instances/staging/mac-react-sfa.yaml
```

Expected:
```
environment: staging
server: mac-stg-01
  host: stg-mac-sfa.mandiriagro.com
```

- [ ] **Step 4: Verify staging odoo has stg_ db prefix**

```bash
grep 'name:' deploys/instances/staging/mac-odoo-dist.yaml | head -3
```

Expected: database name contains `stg_mac_odoo_dist`

- [ ] **Step 5: Verify extends paths are correct**

```bash
grep 'extends:' deploys/instances/staging/*.yaml | grep -v '../../bases/' && echo "ERROR" || echo "ALL OK"
```

Expected: `ALL OK`

- [ ] **Step 6: Commit**

```bash
git add deploys/instances/staging/ deploys/tenants/
git commit -m "feat(deploys): generate staging manifests for mac and tpp tenants"
```

---

### Task 8: Reinstall kctl-dokploy and integration test

**Files:** None (testing only)

- [ ] **Step 1: Run all kctl-dokploy tests**

```bash
cd packages/kctl-dokploy && uv run pytest tests/ -v --tb=short
```

Expected: All tests PASS

- [ ] **Step 2: Reinstall kctl-dokploy**

```bash
uv tool install --reinstall --force packages/kctl-dokploy
```

- [ ] **Step 3: Verify manifest loading works with new structure**

```bash
kctl-dokploy deploy status -f deploys/instances/production/mac-react-sfa.yaml
```

Expected: Status output without path errors

- [ ] **Step 4: Verify staging manifest loads**

```bash
kctl-dokploy deploy status -f deploys/instances/staging/mac-react-sfa.yaml
```

Expected: Status shows `environment: staging`, `server: mac-stg-01`

- [ ] **Step 5: Lint**

```bash
cd packages/kctl-dokploy && uv run ruff check src/
```

Expected: No errors

- [ ] **Step 6: Final commit and push**

```bash
git push
```
