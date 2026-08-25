# Deploy Preflight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `deploy preflight` command that validates a target server is ready for deployment, and integrate it into `deploy apply` so deployments abort on failure.

**Architecture:** New `core/preflight.py` with 10 gate functions that each return a `GateResult`. The `deploy preflight` CLI command runs all gates and displays results. The `Deployer` gets a new `phase_preflight()` that runs gates before any deployment. Gates use SSH (via subprocess), Dokploy API, Cloudflare API, and Hetzner API to validate.

**Tech Stack:** Python 3.12, Pydantic 2, Typer, subprocess (SSH), httpx, pytest

**Spec:** `docs/superpowers/specs/2026-04-05-migration-preflight-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `packages/kctl-dokploy/src/kctl_dokploy/core/preflight.py` | 10 gate functions + `run_preflight()` orchestrator |
| Create | `packages/kctl-dokploy/tests/core/test_preflight.py` | Tests for all gates |
| Modify | `packages/kctl-dokploy/src/kctl_dokploy/commands/deploy.py` | Add `preflight` and `preflight-all` commands |
| Modify | `packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py` | Add `phase_preflight()` + `--skip-preflight` |

---

### Task 1: Create GateResult model and gate runner

**Files:**
- Create: `packages/kctl-dokploy/src/kctl_dokploy/core/preflight.py`
- Create: `packages/kctl-dokploy/tests/core/test_preflight.py`

- [ ] **Step 1: Write failing test for GateResult and run_preflight**

Create `packages/kctl-dokploy/tests/core/test_preflight.py`:

```python
"""Tests for deployment preflight gates."""

from __future__ import annotations

from kctl_dokploy.core.preflight import GateResult, run_preflight
from kctl_dokploy.core.manifest import DeployManifest


def test_gate_result_pass():
    r = GateResult(gate="test", status="pass", message="OK")
    assert r.passed
    assert not r.failed


def test_gate_result_fail():
    r = GateResult(gate="test", status="fail", message="Bad")
    assert not r.passed
    assert r.failed


def test_gate_result_warn():
    r = GateResult(gate="test", status="warn", message="Maybe")
    assert r.passed  # warn is not a failure
    assert not r.failed


def test_run_preflight_returns_results():
    """run_preflight returns a list of GateResults."""
    manifest = DeployManifest(
        server="test-server",
        project="test",
        environment="production",
    )
    # With no real connections, all gates should fail or be skipped
    results = run_preflight(manifest, client=None, ssh_available=False)
    assert isinstance(results, list)
    assert len(results) > 0
    assert all(isinstance(r, GateResult) for r in results)


def test_run_preflight_has_all_gates():
    """run_preflight checks all 10 gates."""
    manifest = DeployManifest(server="x", project="x")
    results = run_preflight(manifest, client=None, ssh_available=False)
    gate_names = {r.gate for r in results}
    expected = {
        "server_connectivity",
        "firewall",
        "dns",
        "image_pull",
        "database",
        "compose_assignment",
        "env_sync",
        "source_config",
        "network",
        "ssl",
    }
    assert gate_names == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/kctl-dokploy && uv run pytest tests/core/test_preflight.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'kctl_dokploy.core.preflight'`

- [ ] **Step 3: Create preflight.py with GateResult and run_preflight skeleton**

Create `packages/kctl-dokploy/src/kctl_dokploy/core/preflight.py`:

```python
"""Deployment preflight validation gates.

Each gate validates one aspect of deployment readiness.
Gates return GateResult with status: pass, warn, or fail.
Any fail blocks deployment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kctl_dokploy.core.manifest import DeployManifest


@dataclass
class GateResult:
    """Result from a single preflight gate."""

    gate: str
    status: str  # "pass", "warn", "fail"
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
    return GateResult("image_pull", "warn", "Image pull check requires SSH")


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
    import pathlib
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
        client: Dokploy API client (optional).
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/kctl-dokploy && uv run pytest tests/core/test_preflight.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/core/preflight.py packages/kctl-dokploy/tests/core/test_preflight.py
git commit -m "feat(preflight): add GateResult model and 10-gate preflight skeleton"
```

---

### Task 2: Implement Gate 7 (env_sync) with OIDC validation

**Files:**
- Modify: `packages/kctl-dokploy/src/kctl_dokploy/core/preflight.py`
- Modify: `packages/kctl-dokploy/tests/core/test_preflight.py`

This is the most critical gate — it caught the OIDC credential wipe issue.

- [ ] **Step 1: Write failing tests for env_sync gate**

Add to `packages/kctl-dokploy/tests/core/test_preflight.py`:

```python
import pathlib


class TestGateEnvSync:
    def test_pass_when_no_env_file(self):
        from kctl_dokploy.core.preflight import _gate_env_sync
        m = DeployManifest()
        r = _gate_env_sync(m, None, False)
        assert r.status == "pass"

    def test_fail_when_env_file_missing(self, tmp_path):
        from kctl_dokploy.core.preflight import _gate_env_sync
        m = DeployManifest(env_file=str(tmp_path / "nonexistent.env"))
        r = _gate_env_sync(m, None, False)
        assert r.status == "fail"
        assert "not found" in r.message

    def test_pass_when_env_file_exists(self, tmp_path):
        from kctl_dokploy.core.preflight import _gate_env_sync
        env_file = tmp_path / ".env.test"
        env_file.write_text("KEY=value\n")
        m = DeployManifest(env_file=str(env_file))
        r = _gate_env_sync(m, None, False)
        assert r.status == "pass"

    def test_fail_when_oidc_mode_but_empty_client_id(self, tmp_path):
        from kctl_dokploy.core.preflight import _gate_env_sync
        env_file = tmp_path / ".env.test"
        env_file.write_text(
            "VITE_AUTH_MODE=oidc\n"
            "VITE_SFA_OIDC_CLIENT_ID=\n"
            "VITE_SFA_OIDC_REDIRECT_URI=\n"
        )
        m = DeployManifest(env_file=str(env_file))
        r = _gate_env_sync(m, None, False)
        assert r.status == "fail"
        assert "OIDC" in r.message

    def test_pass_when_oidc_mode_with_credentials(self, tmp_path):
        from kctl_dokploy.core.preflight import _gate_env_sync
        env_file = tmp_path / ".env.test"
        env_file.write_text(
            "VITE_AUTH_MODE=oidc\n"
            "VITE_SFA_OIDC_CLIENT_ID=abc123\n"
            "VITE_SFA_OIDC_REDIRECT_URI=https://example.com/callback\n"
        )
        m = DeployManifest(env_file=str(env_file))
        r = _gate_env_sync(m, None, False)
        assert r.status == "pass"

    def test_pass_when_native_mode_empty_oidc(self, tmp_path):
        from kctl_dokploy.core.preflight import _gate_env_sync
        env_file = tmp_path / ".env.test"
        env_file.write_text(
            "VITE_AUTH_MODE=native\n"
            "VITE_SFA_OIDC_CLIENT_ID=\n"
        )
        m = DeployManifest(env_file=str(env_file))
        r = _gate_env_sync(m, None, False)
        assert r.status == "pass"
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `cd packages/kctl-dokploy && uv run pytest tests/core/test_preflight.py::TestGateEnvSync -v`
Expected: OIDC tests FAIL (current implementation doesn't check OIDC)

- [ ] **Step 3: Implement OIDC validation in _gate_env_sync**

Replace `_gate_env_sync` in `packages/kctl-dokploy/src/kctl_dokploy/core/preflight.py`:

```python
def _gate_env_sync(manifest: DeployManifest, client: Any, ssh_available: bool) -> GateResult:
    """Gate 7: Verify local env file exists, and OIDC credentials are valid."""
    if not manifest.env_file:
        return GateResult("env_sync", "pass", "No env_file specified")

    import pathlib
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/kctl-dokploy && uv run pytest tests/core/test_preflight.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/core/preflight.py packages/kctl-dokploy/tests/core/test_preflight.py
git commit -m "feat(preflight): implement env_sync gate with OIDC credential validation"
```

---

### Task 3: Add `deploy preflight` CLI command

**Files:**
- Modify: `packages/kctl-dokploy/src/kctl_dokploy/commands/deploy.py`

- [ ] **Step 1: Add preflight command**

Add to `packages/kctl-dokploy/src/kctl_dokploy/commands/deploy.py`, after the `validate` command:

```python
from kctl_dokploy.core.preflight import run_preflight, GateResult


@app.command()
def preflight(
    ctx: typer.Context,
    file: Annotated[Path, typer.Option("--file", "-f", help="Manifest YAML file", exists=True)] = ...,  # type: ignore[assignment]
) -> None:
    """Run preflight checks before deployment.

    Validates server connectivity, firewall, DNS, database auth,
    env file sync, and more. Any FAIL blocks deployment.
    """
    c: AppContext = ctx.obj
    manifest = _load(file, c)

    api_client = None
    try:
        from kctl_dokploy.core.callbacks import AppContext as AC
        from kctl_dokploy.core.client import DokployClient
        from kctl_lib.config import load_config
        cfg = load_config("dokploy", profile=c.profile)
        api_client = DokployClient(url=cfg["url"], api_key=cfg["api_key"])
    except Exception:
        pass

    results = run_preflight(manifest, client=api_client)

    # Build display
    status_icons = {"pass": "✓", "warn": "⚠", "fail": "✗"}
    rows = []
    json_data = []
    for r in results:
        icon = status_icons.get(r.status, "?")
        rows.append([f"{icon} Gate: {r.gate}", r.status.upper(), r.message])
        json_data.append({"gate": r.gate, "status": r.status, "message": r.message})

    server_info = manifest.server or "(Dokploy host)"
    c.output.table(
        f"Preflight: {manifest.instance.name} → {server_info}",
        [("Gate", "cyan"), ("Status", ""), ("Details", "dim")],
        rows,
        data_for_json=json_data,
    )

    failures = [r for r in results if r.failed]
    warns = [r for r in results if r.status == "warn"]

    if failures:
        c.output.error(f"PREFLIGHT FAILED: {len(failures)} gate(s) failed")
        raise typer.Exit(1)
    elif warns:
        c.output.warn(f"PREFLIGHT PASSED with {len(warns)} warning(s)")
    else:
        c.output.success("PREFLIGHT PASSED: all gates clear")
```

- [ ] **Step 2: Test CLI command**

```bash
uv tool install --reinstall --force packages/kctl-dokploy
kctl-dokploy deploy preflight -f deploys/instances/production/mac-odoo-hrms.yaml
```

Expected: Table output showing all 10 gates with pass/warn/fail status.

- [ ] **Step 3: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/commands/deploy.py
git commit -m "feat(deploy): add preflight CLI command"
```

---

### Task 4: Integrate preflight into deploy apply

**Files:**
- Modify: `packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py`
- Modify: `packages/kctl-dokploy/src/kctl_dokploy/commands/deploy.py`

- [ ] **Step 1: Add phase_preflight to Deployer**

Add to `packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py`, after the class fields:

```python
    skip_preflight: bool = False

    def phase_preflight(self) -> None:
        """Run preflight checks before deployment. Aborts if any gate fails."""
        if self.skip_preflight:
            self._record_phase("preflight", "skipped", "Skipped via --skip-preflight")
            return

        from kctl_dokploy.core.preflight import run_preflight

        client = self._get_client()
        results = run_preflight(self.manifest, client=client)
        failures = [r for r in results if r.failed]

        if failures:
            details = "; ".join(f"{r.gate}: {r.message}" for r in failures)
            self._record_phase("preflight", "failed", f"{len(failures)} gate(s) failed — {details}")
        else:
            warns = sum(1 for r in results if r.status == "warn")
            self._record_phase("preflight", "passed", f"10 gates checked ({warns} warnings)")
```

- [ ] **Step 2: Call phase_preflight in run_all()**

Find `run_all()` or the method that sequences all phases. Add `self.phase_preflight()` as the FIRST phase call, before `phase_dns()`. If preflight fails, the method should return early:

```python
    def run_all(self) -> list[PhaseResult]:
        """Execute all deployment phases."""
        self.phase_preflight()
        # Abort if preflight failed
        if any(r.action == "failed" and r.phase == "preflight" for r in self.results):
            return self.results

        self.phase_pre_validate()
        self.phase_dns()
        # ... rest of phases
```

- [ ] **Step 3: Add --skip-preflight flag to deploy apply command**

In `packages/kctl-dokploy/src/kctl_dokploy/commands/deploy.py`, find the `apply` command and add:

```python
    skip_preflight: Annotated[bool, typer.Option("--skip-preflight", help="Skip preflight checks (emergency only)")] = False,
```

Pass it to the Deployer:

```python
    deployer = Deployer(manifest=manifest, dry_run=dry_run, skip_preflight=skip_preflight)
```

- [ ] **Step 4: Run tests**

Run: `cd packages/kctl-dokploy && uv run pytest tests/core/test_deployer.py -v`
Expected: All existing tests PASS

- [ ] **Step 5: Reinstall and test**

```bash
uv tool install --reinstall --force packages/kctl-dokploy
kctl-dokploy deploy apply -f deploys/instances/production/mac-odoo-hrms.yaml --dry-run
```

Expected: Preflight results appear as the first phase in the deployment summary.

- [ ] **Step 6: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py packages/kctl-dokploy/src/kctl_dokploy/commands/deploy.py
git commit -m "feat(deploy): integrate preflight into deploy apply pipeline"
```

---

### Task 5: Add preflight-all command for batch validation

**Files:**
- Modify: `packages/kctl-dokploy/src/kctl_dokploy/commands/deploy.py`

- [ ] **Step 1: Add preflight-all command**

Add to `packages/kctl-dokploy/src/kctl_dokploy/commands/deploy.py`:

```python
@app.command(name="preflight-all")
def preflight_all(
    ctx: typer.Context,
    directory: Annotated[Path, typer.Option("--dir", "-d", help="Directory with manifest YAML files", exists=True)] = ...,  # type: ignore[assignment]
    server: Annotated[str | None, typer.Option("--server", "-s", help="Filter by server name")] = None,
) -> None:
    """Run preflight checks on all manifests in a directory.

    Use --server to filter to manifests targeting a specific server.
    """
    c: AppContext = ctx.obj
    manifests = sorted(directory.glob("*.yaml"))
    if not manifests:
        c.output.warn(f"No manifests found in {directory}")
        raise typer.Exit(0)

    api_client = None
    try:
        from kctl_dokploy.core.client import DokployClient
        from kctl_lib.config import load_config
        cfg = load_config("dokploy", profile=c.profile)
        api_client = DokployClient(url=cfg["url"], api_key=cfg["api_key"])
    except Exception:
        pass

    total_pass = 0
    total_fail = 0
    total_warn = 0

    for mf in manifests:
        try:
            manifest = load_and_resolve(mf)
        except Exception as exc:
            c.output.error(f"{mf.name}: Failed to load — {exc}")
            total_fail += 1
            continue

        if server and manifest.server != server:
            continue

        results = run_preflight(manifest, client=api_client)
        failures = [r for r in results if r.failed]
        warns = [r for r in results if r.status == "warn"]

        if failures:
            c.output.error(f"✗ {manifest.instance.name}: {len(failures)} FAIL")
            for f in failures:
                c.output.info(f"    {f.gate}: {f.message}")
            total_fail += 1
        elif warns:
            c.output.warn(f"⚠ {manifest.instance.name}: {len(warns)} warnings")
            total_warn += 1
        else:
            c.output.success(f"✓ {manifest.instance.name}")
            total_pass += 1

    c.output.info(f"\nResults: {total_pass} pass, {total_warn} warn, {total_fail} fail")
    if total_fail > 0:
        raise typer.Exit(1)
```

- [ ] **Step 2: Reinstall and test**

```bash
uv tool install --reinstall --force packages/kctl-dokploy
kctl-dokploy deploy preflight-all -d deploys/instances/production/
kctl-dokploy deploy preflight-all -d deploys/instances/production/ --server mac-prod-01
```

- [ ] **Step 3: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/commands/deploy.py
git commit -m "feat(deploy): add preflight-all command for batch validation"
```

---

### Task 6: Full test suite and lint

**Files:** None (testing only)

- [ ] **Step 1: Run all preflight tests**

Run: `cd packages/kctl-dokploy && uv run pytest tests/core/test_preflight.py -v`
Expected: All tests PASS

- [ ] **Step 2: Run full test suite**

Run: `cd packages/kctl-dokploy && uv run pytest tests/ -v --tb=short`
Expected: No new failures

- [ ] **Step 3: Lint**

Run: `cd packages/kctl-dokploy && uv run ruff check src/kctl_dokploy/core/preflight.py src/kctl_dokploy/commands/deploy.py`
Expected: No errors

- [ ] **Step 4: Reinstall final version**

```bash
uv tool install --reinstall --force packages/kctl-dokploy
```

- [ ] **Step 5: Integration test with real manifests**

```bash
# Test preflight on a production manifest
kctl-dokploy deploy preflight -f deploys/instances/production/mac-odoo-hrms.yaml

# Test preflight-all on all production manifests
kctl-dokploy deploy preflight-all -d deploys/instances/production/

# Test deploy apply includes preflight
kctl-dokploy deploy apply -f deploys/instances/production/mac-react-bia.yaml --dry-run
```

- [ ] **Step 6: Final commit and push**

```bash
git push
```
