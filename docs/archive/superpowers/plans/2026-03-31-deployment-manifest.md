# Deployment Manifest System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `kctl-dokploy deploy apply` that reads YAML manifests (base + instance) and executes a 12-phase idempotent deployment across kctl-cf, kctl-pg, kctl-dokploy, and kctl-odoo.

**Architecture:** Three new files — `manifest.py` (YAML parsing + merging), `deployer.py` (12-phase executor with subprocess calls to kctl-* CLIs), `deploy.py` (Typer command group). The deployer shells out to kctl-* CLIs rather than importing their internals, keeping the system decoupled and debuggable.

**Tech Stack:** Python 3.12+, Typer, PyYAML, Pydantic 2, subprocess (for kctl-* CLI calls), httpx (for healthcheck polling)

---

## File Structure

| File | Responsibility |
|------|----------------|
| `packages/kctl-dokploy/src/kctl_dokploy/core/manifest.py` | Parse YAML, merge base+instance, interpolate variables, validate with Pydantic |
| `packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py` | 12-phase executor — each phase is a method, calls kctl-* via subprocess |
| `packages/kctl-dokploy/src/kctl_dokploy/commands/deploy.py` | Typer command group: apply, status, apply-all, list |
| `packages/kctl-dokploy/tests/core/test_manifest.py` | Tests for YAML parsing, merging, interpolation, validation |
| `packages/kctl-dokploy/tests/core/test_deployer.py` | Tests for each deployment phase (mocked subprocess) |
| `packages/kctl-dokploy/tests/commands/test_deploy.py` | Integration tests for CLI commands |
| `deploys/bases/odoo.yaml` | Base template for Odoo instances |
| `deploys/bases/react-pwa.yaml` | Base template for React PWA apps |
| `deploys/bases/infra.yaml` | Base template for infrastructure services |
| `deploys/instances/odoo-prod.yaml` | First real instance manifest (Odoo production) |

---

### Task 1: Manifest Pydantic Models

**Files:**
- Create: `packages/kctl-dokploy/src/kctl_dokploy/core/manifest.py`
- Test: `packages/kctl-dokploy/tests/core/test_manifest.py`

- [ ] **Step 1: Write test for loading a base manifest**

```python
# tests/core/test_manifest.py
"""Tests for deployment manifest parsing and merging."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from kctl_dokploy.core.manifest import (
    DeployManifest,
    load_manifest,
    merge_manifests,
    interpolate,
)


def write_yaml(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(content))
    return p


class TestLoadManifest:
    def test_load_base(self, tmp_path: Path) -> None:
        base = write_yaml(tmp_path, "base.yaml", """\
            kind: base
            type: odoo

            source:
              type: github
              owner: tgunawandev
              repo: kodemeio-odoo
              branch: "18.0"
              compose_path: ./docker-compose.prod.yml

            server: kodeme-service
            project: kodemeio-service

            healthcheck:
              path: /web/health
              port: 8069
              expected_status: 200
              timeout: 120

            env_defaults:
              TZ: Asia/Jakarta

            backup:
              destination: kodemeio-s3-backups
              type: postgres
              schedule: "0 2 * * *"
              prefix_template: "odoo-{instance_name}"

            schedules:
              - name: "{instance_name}-vacuum"
                cron: "0 4 * * 0"
                command: "vacuumdb -U {db_user} -d {db_name} --analyze"
                service: odoo
        """)
        manifest = load_manifest(base)
        assert manifest.kind == "base"
        assert manifest.type == "odoo"
        assert manifest.source.repo == "kodemeio-odoo"
        assert manifest.server == "kodeme-service"
        assert manifest.healthcheck.port == 8069
        assert manifest.env_defaults["TZ"] == "Asia/Jakarta"
        assert manifest.backup.destination == "kodemeio-s3-backups"
        assert len(manifest.schedules) == 1
```

- [ ] **Step 2: Run test — expect ImportError**

```bash
cd packages/kctl-dokploy && uv run pytest tests/core/test_manifest.py::TestLoadManifest::test_load_base -v
```
Expected: FAIL — `cannot import name 'DeployManifest' from 'kctl_dokploy.core.manifest'`

- [ ] **Step 3: Implement manifest models**

```python
# packages/kctl-dokploy/src/kctl_dokploy/core/manifest.py
"""Deployment manifest parser — YAML loading, base+instance merging, variable interpolation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class SourceConfig(BaseModel):
    type: str = "github"
    owner: str = ""
    repo: str = ""
    branch: str = "main"
    compose_path: str = "./docker-compose.prod.yml"


class HealthcheckConfig(BaseModel):
    path: str = "/"
    port: int = 80
    expected_status: int = 200
    timeout: int = 120
    interval: int = 10


class DnsConfig(BaseModel):
    zone: str = ""
    type: str = "A"
    name: str = ""
    content: str = ""


class DomainConfig(BaseModel):
    host: str = ""
    port: int = 80
    service: str = ""
    https: bool = True
    cert: str = "letsencrypt"


class DatabaseConfig(BaseModel):
    host: str = "10.0.0.3"
    port: int = 5432
    name: str = ""
    user: str = ""


class BackupConfig(BaseModel):
    destination: str = ""
    type: str = "postgres"
    schedule: str = "0 2 * * *"
    prefix_template: str = "{instance_name}"
    keep_latest: int = 30


class ScheduleConfig(BaseModel):
    name: str = ""
    cron: str = ""
    command: str = ""
    service: str = ""
    shell: str = "bash"
    timezone: str = "Asia/Jakarta"


class PostDeployConfig(BaseModel):
    odoo_profile: str | None = None
    odoo_init_db: bool = False


class InstanceConfig(BaseModel):
    name: str = ""
    description: str = ""


class DeployManifest(BaseModel):
    """Unified manifest after base+instance merge."""

    kind: str = "base"
    type: str = ""
    extends: str | None = None

    source: SourceConfig = SourceConfig()
    server: str = ""
    project: str = ""

    instance: InstanceConfig = InstanceConfig()
    dns: DnsConfig | None = None
    domain: DomainConfig | None = None
    database: DatabaseConfig | None = None

    healthcheck: HealthcheckConfig = HealthcheckConfig()
    env_defaults: dict[str, str] = {}
    env_overrides: dict[str, str] = {}
    source_overrides: dict[str, str] = {}

    backup: BackupConfig | None = None
    schedules: list[ScheduleConfig] = []
    post_deploy: PostDeployConfig = PostDeployConfig()


def load_manifest(path: Path) -> DeployManifest:
    """Load a single YAML manifest file into a DeployManifest."""
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    return DeployManifest(**raw)


def merge_manifests(base: DeployManifest, instance: DeployManifest) -> DeployManifest:
    """Merge a base manifest with an instance manifest.

    Instance values override base values. env_overrides merges on top of env_defaults.
    source_overrides patches source fields. schedules and backup come from base unless
    instance provides them.
    """
    merged = base.model_dump()

    # Instance identity
    merged["kind"] = "instance"
    merged["instance"] = instance.instance.model_dump()

    # DNS, domain, database come from instance
    if instance.dns:
        merged["dns"] = instance.dns.model_dump()
    if instance.domain:
        merged["domain"] = instance.domain.model_dump()
    if instance.database:
        merged["database"] = instance.database.model_dump()

    # Merge env: base defaults + instance overrides
    env = dict(base.env_defaults)
    env.update(instance.env_overrides)
    merged["env_defaults"] = env
    merged["env_overrides"] = {}

    # Source overrides patch base source
    if instance.source_overrides:
        for k, v in instance.source_overrides.items():
            if k in merged.get("source", {}):
                merged["source"][k] = v

    # Post-deploy: instance overrides base
    inst_pd = instance.post_deploy.model_dump(exclude_defaults=True)
    if inst_pd:
        merged["post_deploy"] = {**base.post_deploy.model_dump(), **inst_pd}

    return DeployManifest(**merged)


def interpolate(manifest: DeployManifest) -> DeployManifest:
    """Replace {variable} placeholders in schedules, backup prefix, etc."""
    variables = {
        "instance_name": manifest.instance.name,
        "db_name": manifest.database.name if manifest.database else "",
        "db_user": manifest.database.user if manifest.database else "",
        "domain": manifest.domain.host if manifest.domain else "",
    }

    def _replace(text: str) -> str:
        def replacer(match: re.Match) -> str:
            key = match.group(1)
            return variables.get(key, match.group(0))
        return re.sub(r"\{(\w+)\}", replacer, text)

    # Interpolate schedules
    for sched in manifest.schedules:
        sched.name = _replace(sched.name)
        sched.command = _replace(sched.command)

    # Interpolate backup prefix
    if manifest.backup:
        manifest.backup.prefix_template = _replace(manifest.backup.prefix_template)

    return manifest


def load_and_resolve(instance_path: Path) -> DeployManifest:
    """Load an instance manifest, resolve its base, merge, and interpolate."""
    instance = load_manifest(instance_path)

    if instance.extends:
        base_path = instance_path.parent / instance.extends
        base = load_manifest(base_path)
        manifest = merge_manifests(base, instance)
    else:
        manifest = instance

    return interpolate(manifest)
```

- [ ] **Step 4: Run test — expect PASS**

```bash
cd packages/kctl-dokploy && uv run pytest tests/core/test_manifest.py::TestLoadManifest::test_load_base -v
```
Expected: PASS

- [ ] **Step 5: Write test for merge + interpolation**

```python
# Append to tests/core/test_manifest.py

class TestMergeManifests:
    def test_merge_base_and_instance(self, tmp_path: Path) -> None:
        base = write_yaml(tmp_path, "bases/odoo.yaml", """\
            kind: base
            type: odoo
            source:
              type: github
              owner: tgunawandev
              repo: kodemeio-odoo
              branch: "18.0"
              compose_path: ./docker-compose.prod.yml
            server: kodeme-service
            project: kodemeio-service
            env_defaults:
              TZ: Asia/Jakarta
              RUNNING_ENV: production
            backup:
              destination: kodemeio-s3-backups
              type: postgres
              schedule: "0 2 * * *"
              prefix_template: "odoo-{instance_name}"
            schedules:
              - name: "{instance_name}-vacuum"
                cron: "0 4 * * 0"
                command: "vacuumdb -U {db_user} -d {db_name} --analyze"
                service: odoo
        """)

        instance = write_yaml(tmp_path, "instances/odoo-prod.yaml", """\
            kind: instance
            extends: ../bases/odoo.yaml
            instance:
              name: kodemeio-odoo-prod
              description: Production ERP
            dns:
              zone: kodeme.io
              name: odoo
              content: 49.13.14.79
            domain:
              host: odoo.kodeme.io
              port: 8069
              service: odoo
              https: true
            database:
              name: kodemeio_prod
              user: odoo
            env_overrides:
              PGDATABASE: kodemeio_prod
              DOMAIN: odoo.kodeme.io
            post_deploy:
              odoo_profile: profile-distribution
        """)

        (tmp_path / "bases").mkdir(exist_ok=True)
        (tmp_path / "instances").mkdir(exist_ok=True)
        # Move files to correct dirs
        import shutil
        shutil.move(str(base), str(tmp_path / "bases" / "odoo.yaml"))
        shutil.move(str(instance), str(tmp_path / "instances" / "odoo-prod.yaml"))

        result = load_and_resolve(tmp_path / "instances" / "odoo-prod.yaml")

        # Base fields inherited
        assert result.source.repo == "kodemeio-odoo"
        assert result.server == "kodeme-service"

        # Instance fields applied
        assert result.instance.name == "kodemeio-odoo-prod"
        assert result.domain.host == "odoo.kodeme.io"
        assert result.database.name == "kodemeio_prod"

        # Env merged
        assert result.env_defaults["TZ"] == "Asia/Jakarta"
        assert result.env_defaults["PGDATABASE"] == "kodemeio_prod"

        # Variables interpolated
        assert result.schedules[0].name == "kodemeio-odoo-prod-vacuum"
        assert "kodemeio_prod" in result.schedules[0].command
        assert result.backup.prefix_template == "odoo-kodemeio-odoo-prod"

        # Post-deploy
        assert result.post_deploy.odoo_profile == "profile-distribution"
```

- [ ] **Step 6: Run test — expect PASS**

```bash
cd packages/kctl-dokploy && uv run pytest tests/core/test_manifest.py -v
```
Expected: 2 tests PASS

- [ ] **Step 7: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/core/manifest.py packages/kctl-dokploy/tests/core/test_manifest.py
git commit -m "feat(deploy): add manifest parser with base+instance merge and variable interpolation"
```

---

### Task 2: Deployer — Phase Executor

**Files:**
- Create: `packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py`
- Test: `packages/kctl-dokploy/tests/core/test_deployer.py`

- [ ] **Step 1: Write test for the deployer's kctl runner**

```python
# tests/core/test_deployer.py
"""Tests for deployment phase executor."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kctl_dokploy.core.deployer import Deployer, PhaseResult
from kctl_dokploy.core.manifest import DeployManifest, load_and_resolve


class TestDeployerKctl:
    def test_run_kctl_success(self) -> None:
        deployer = Deployer(manifest=DeployManifest(), dry_run=False)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="OK Connected\n", stderr="")
            rc, out = deployer._run_kctl(["kctl-cf", "config", "test"])
            assert rc == 0
            assert "OK" in out

    def test_run_kctl_dry_run_skips(self) -> None:
        deployer = Deployer(manifest=DeployManifest(), dry_run=True)
        rc, out = deployer._run_kctl(["kctl-cf", "records", "create", "--zone", "test"])
        assert rc == 0
        assert "dry-run" in out.lower()

    def test_phase_result_tracking(self) -> None:
        deployer = Deployer(manifest=DeployManifest(), dry_run=False)
        deployer._record_phase("dns", "created", "Created A record odoo.kodeme.io")
        assert len(deployer.results) == 1
        assert deployer.results[0].phase == "dns"
        assert deployer.results[0].action == "created"
```

- [ ] **Step 2: Run test — expect ImportError**

```bash
cd packages/kctl-dokploy && uv run pytest tests/core/test_deployer.py -v
```

- [ ] **Step 3: Implement deployer core**

```python
# packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py
"""12-phase deployment executor — orchestrates kctl-* CLIs."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field

import httpx

from kctl_dokploy.core.manifest import DeployManifest


@dataclass
class PhaseResult:
    """Result of a single deployment phase."""

    phase: str
    action: str  # "created", "updated", "skipped", "failed"
    message: str


@dataclass
class Deployer:
    """Executes the 12-phase deployment from a resolved manifest."""

    manifest: DeployManifest
    dry_run: bool = False
    results: list[PhaseResult] = field(default_factory=list)

    def _record_phase(self, phase: str, action: str, message: str) -> None:
        self.results.append(PhaseResult(phase=phase, action=action, message=message))

    def _run_kctl(self, cmd: list[str], check: bool = False) -> tuple[int, str]:
        """Run a kctl-* CLI command. In dry-run mode, log but don't execute mutating commands."""
        cmd_str = " ".join(cmd)

        # Read-only commands always execute (list, get, config test)
        readonly_verbs = ("list", "get", "show", "test", "status", "check")
        is_readonly = any(v in cmd for v in readonly_verbs)

        if self.dry_run and not is_readonly:
            self._record_phase("dry-run", "skipped", f"Would run: {cmd_str}")
            return 0, f"[dry-run] {cmd_str}"

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        output = result.stdout + result.stderr
        if check and result.returncode != 0:
            raise RuntimeError(f"Command failed: {cmd_str}\n{output}")
        return result.returncode, output

    def _run_kctl_json(self, cmd: list[str]) -> list | dict:
        """Run a kctl command with --json and parse output."""
        full_cmd = cmd.copy()
        # Insert --json after the CLI name
        if len(full_cmd) > 1:
            full_cmd.insert(1, "--json")
        rc, out = self._run_kctl(full_cmd)
        if rc != 0:
            return {}
        try:
            return json.loads(out)
        except (json.JSONDecodeError, ValueError):
            return {}

    # ------------------------------------------------------------------
    # Phase 1: Resolve (done before Deployer is created)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Phase 2: DNS
    # ------------------------------------------------------------------
    def phase_dns(self) -> None:
        dns = self.manifest.dns
        if not dns or not dns.zone or not dns.name:
            self._record_phase("dns", "skipped", "No DNS config")
            return

        # Check if record exists
        rc, out = self._run_kctl([
            "kctl-cf", "records", "list", "--zone", dns.zone,
        ])
        fqdn = f"{dns.name}.{dns.zone}"
        if fqdn in out:
            self._record_phase("dns", "skipped", f"{fqdn} already exists")
            return

        # Create record
        rc, out = self._run_kctl([
            "kctl-cf", "records", "create",
            "--zone", dns.zone, "--type", dns.type,
            "--name", dns.name, "--content", dns.content,
        ])
        if rc == 0:
            self._record_phase("dns", "created", f"Created {dns.type} record {fqdn} → {dns.content}")
        else:
            self._record_phase("dns", "failed", f"DNS create failed: {out[:200]}")

    # ------------------------------------------------------------------
    # Phase 3: Database
    # ------------------------------------------------------------------
    def phase_database(self) -> None:
        db = self.manifest.database
        if not db or not db.name:
            self._record_phase("database", "skipped", "No database config")
            return

        # Check if role exists
        rc, out = self._run_kctl(["kctl-pg", "users", "list"])
        if db.user and db.user in out:
            self._record_phase("database", "skipped", f"Role '{db.user}' already exists")
        elif db.user:
            rc, out = self._run_kctl([
                "kctl-pg", "users", "create", db.user, "--password", db.user,
            ])
            if rc == 0:
                self._record_phase("database", "created", f"Created role '{db.user}'")
            else:
                self._record_phase("database", "failed", f"Role create failed: {out[:200]}")

        # Check if database exists
        rc, out = self._run_kctl(["kctl-pg", "db", "list"])
        if db.name in out:
            self._record_phase("database", "skipped", f"Database '{db.name}' already exists")
            return

        rc, out = self._run_kctl([
            "kctl-pg", "db", "create", db.name, "--owner", db.user or "postgres",
        ])
        if rc == 0:
            self._record_phase("database", "created", f"Created database '{db.name}'")
        else:
            self._record_phase("database", "failed", f"DB create failed: {out[:200]}")

    # ------------------------------------------------------------------
    # Phase 4: Registry (GHCR)
    # ------------------------------------------------------------------
    def phase_registry(self) -> None:
        rc, out = self._run_kctl(["kctl-dokploy", "registry", "list"])
        if "ghcr" in out.lower():
            self._record_phase("registry", "skipped", "GHCR registry already configured")
            return
        self._record_phase("registry", "skipped", "Registry setup requires manual GHCR token — skipped")

    # ------------------------------------------------------------------
    # Phase 5: Compose Service
    # ------------------------------------------------------------------
    def phase_compose(self) -> None:
        m = self.manifest
        name = m.instance.name
        if not name:
            self._record_phase("compose", "failed", "No instance name")
            return

        # Find existing compose by name
        data = self._run_kctl_json(["kctl-dokploy", "projects", "get", m.project])
        compose_id = None
        env_id = None
        if isinstance(data, dict):
            for env in data.get("environments", []):
                if not env_id and env.get("isDefault"):
                    env_id = env.get("environmentId")
                for comp in env.get("compose", []):
                    if comp.get("name") == name:
                        compose_id = comp.get("composeId")
                        break

        if compose_id:
            # Update existing
            update_cmd = [
                "kctl-dokploy", "compose", "update",
                "--id", compose_id,
                "--source-type", m.source.type,
                "--owner", m.source.owner,
                "--repo", m.source.repo,
                "--branch", m.source.branch,
                "--compose-path", m.source.compose_path,
            ]
            rc, out = self._run_kctl(update_cmd)
            action = "updated" if rc == 0 else "failed"
            self._record_phase("compose", action, f"Compose '{name}': {action}")
        else:
            if not env_id:
                self._record_phase("compose", "failed", f"No environment found in project '{m.project}'")
                return
            # Find server ID
            server_id = ""
            srv_data = self._run_kctl_json(["kctl-dokploy", "servers", "list"])
            if isinstance(srv_data, list):
                for s in srv_data:
                    if s.get("name") == m.server:
                        server_id = s.get("serverId", "")
                        break

            create_cmd = [
                "kctl-dokploy", "compose", "create", env_id,
                "--name", name,
            ]
            if server_id:
                create_cmd.extend(["--server", server_id])
            rc, out = self._run_kctl(create_cmd)

            # Extract compose ID from output
            if rc == 0 and ":" in out:
                compose_id = out.split(":")[-1].strip()
                # Link to GitHub
                self._run_kctl([
                    "kctl-dokploy", "compose", "update",
                    "--id", compose_id,
                    "--source-type", m.source.type,
                    "--owner", m.source.owner,
                    "--repo", m.source.repo,
                    "--branch", m.source.branch,
                    "--compose-path", m.source.compose_path,
                ])
                self._record_phase("compose", "created", f"Compose '{name}' created: {compose_id}")
            else:
                self._record_phase("compose", "failed", f"Compose create failed: {out[:200]}")

        # Store compose_id for later phases
        self._compose_id = compose_id

    # ------------------------------------------------------------------
    # Phase 6: Environment
    # ------------------------------------------------------------------
    def phase_environment(self) -> None:
        compose_id = getattr(self, "_compose_id", None)
        if not compose_id:
            self._record_phase("environment", "skipped", "No compose ID")
            return

        # Write merged env to temp file
        import tempfile
        env_lines = [f"{k}={v}" for k, v in self.manifest.env_defaults.items()]
        env_content = "\n".join(env_lines) + "\n"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write(env_content)
            env_file = f.name

        # Push env
        rc, out = self._run_kctl([
            "kctl-dokploy", "env", "push", "--", compose_id, env_file,
        ], check=False)

        import os
        os.unlink(env_file)

        if rc == 0 or "Pushed" in out:
            self._record_phase("environment", "updated", f"Pushed {len(env_lines)} env vars")
        else:
            self._record_phase("environment", "failed", f"Env push failed: {out[:200]}")

    # ------------------------------------------------------------------
    # Phase 7: Domain
    # ------------------------------------------------------------------
    def phase_domain(self) -> None:
        domain = self.manifest.domain
        compose_id = getattr(self, "_compose_id", None)
        if not domain or not domain.host or not compose_id:
            self._record_phase("domain", "skipped", "No domain config or compose ID")
            return

        # Check existing domains
        rc, out = self._run_kctl(["kctl-dokploy", "domains", "get", "--", compose_id])
        if domain.host in out:
            self._record_phase("domain", "skipped", f"Domain {domain.host} already exists")
            return

        cmd = [
            "kctl-dokploy", "domains", "create", "--", compose_id,
            "--host", domain.host,
            "--port", str(domain.port),
            "--service", domain.service,
        ]
        if domain.https:
            cmd.append("--https")
        rc, out = self._run_kctl(cmd)
        action = "created" if rc == 0 else "failed"
        self._record_phase("domain", action, f"Domain {domain.host}: {action}")

    # ------------------------------------------------------------------
    # Phase 8: Deploy
    # ------------------------------------------------------------------
    def phase_deploy(self) -> None:
        compose_id = getattr(self, "_compose_id", None)
        if not compose_id:
            self._record_phase("deploy", "skipped", "No compose ID")
            return

        rc, out = self._run_kctl(["kctl-dokploy", "compose", "redeploy", "--", compose_id])
        action = "updated" if rc == 0 else "failed"
        self._record_phase("deploy", action, f"Deployment triggered: {action}")

    # ------------------------------------------------------------------
    # Phase 9: Verify
    # ------------------------------------------------------------------
    def phase_verify(self) -> None:
        hc = self.manifest.healthcheck
        domain = self.manifest.domain
        if not domain or not domain.host:
            self._record_phase("verify", "skipped", "No domain to verify")
            return

        scheme = "https" if domain.https else "http"
        url = f"{scheme}://{domain.host}{hc.path}"

        if self.dry_run:
            self._record_phase("verify", "skipped", f"[dry-run] Would poll {url}")
            return

        deadline = time.time() + hc.timeout
        while time.time() < deadline:
            try:
                r = httpx.get(url, timeout=5, follow_redirects=True)
                if r.status_code == hc.expected_status:
                    self._record_phase("verify", "updated", f"Healthy: {url} → {r.status_code}")
                    return
            except httpx.HTTPError:
                pass
            time.sleep(hc.interval)

        self._record_phase("verify", "failed", f"Timeout after {hc.timeout}s waiting for {url}")

    # ------------------------------------------------------------------
    # Phase 10: Backup
    # ------------------------------------------------------------------
    def phase_backup(self) -> None:
        backup = self.manifest.backup
        compose_id = getattr(self, "_compose_id", None)
        if not backup or not backup.destination or not compose_id:
            self._record_phase("backup", "skipped", "No backup config")
            return

        # Check existing backups
        rc, out = self._run_kctl(["kctl-dokploy", "backups", "list", "--compose", compose_id])
        if backup.prefix_template in out:
            self._record_phase("backup", "skipped", "Backup config already exists")
            return

        db = self.manifest.database
        cmd = [
            "kctl-dokploy", "backups", "create",
            "--destination", backup.destination,
            "--database", db.name if db else "postgres",
            "--type", backup.type,
            "--compose", compose_id,
            "--schedule", backup.schedule,
            "--prefix", backup.prefix_template,
        ]
        rc, out = self._run_kctl(cmd)
        action = "created" if rc == 0 else "failed"
        self._record_phase("backup", action, f"Backup config: {action}")

    # ------------------------------------------------------------------
    # Phase 11: Schedules
    # ------------------------------------------------------------------
    def phase_schedules(self) -> None:
        compose_id = getattr(self, "_compose_id", None)
        if not self.manifest.schedules or not compose_id:
            self._record_phase("schedules", "skipped", "No schedules")
            return

        # Get existing schedules
        rc, out = self._run_kctl([
            "kctl-dokploy", "schedules", "list", compose_id, "--type", "compose",
        ])

        created = 0
        for sched in self.manifest.schedules:
            if sched.name in out:
                continue
            cmd = [
                "kctl-dokploy", "schedules", "create",
                "--name", sched.name,
                "--cron", sched.cron,
                "--command", sched.command,
                "--type", "compose",
                "--compose", compose_id,
                "--service", sched.service,
                "--shell", sched.shell,
                "--timezone", sched.timezone,
            ]
            rc, _ = self._run_kctl(cmd)
            if rc == 0:
                created += 1

        if created > 0:
            self._record_phase("schedules", "created", f"Created {created} schedule(s)")
        else:
            self._record_phase("schedules", "skipped", "All schedules already exist")

    # ------------------------------------------------------------------
    # Phase 12: Post-deploy
    # ------------------------------------------------------------------
    def phase_post_deploy(self) -> None:
        pd = self.manifest.post_deploy
        if not pd.odoo_profile:
            self._record_phase("post-deploy", "skipped", "No post-deploy hooks")
            return

        rc, out = self._run_kctl([
            "kctl-odoo", "bundles", "install", pd.odoo_profile,
        ])
        action = "updated" if rc == 0 else "failed"
        self._record_phase("post-deploy", action, f"Odoo profile '{pd.odoo_profile}': {action}")

    # ------------------------------------------------------------------
    # Run all phases
    # ------------------------------------------------------------------
    def run_all(self) -> list[PhaseResult]:
        """Execute all 12 phases in order."""
        self.phase_dns()
        self.phase_database()
        self.phase_registry()
        self.phase_compose()
        self.phase_environment()
        self.phase_domain()
        self.phase_deploy()
        self.phase_verify()
        self.phase_backup()
        self.phase_schedules()
        self.phase_post_deploy()
        return self.results
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd packages/kctl-dokploy && uv run pytest tests/core/test_deployer.py -v
```
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py packages/kctl-dokploy/tests/core/test_deployer.py
git commit -m "feat(deploy): add 12-phase deployer executor with subprocess kctl-* calls"
```

---

### Task 3: CLI Commands — deploy apply/status/list

**Files:**
- Create: `packages/kctl-dokploy/src/kctl_dokploy/commands/deploy.py`
- Modify: `packages/kctl-dokploy/src/kctl_dokploy/cli.py` (register command group)

- [ ] **Step 1: Create deploy command group**

```python
# packages/kctl-dokploy/src/kctl_dokploy/commands/deploy.py
"""Declarative deployment from YAML manifests."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext
from kctl_dokploy.core.deployer import Deployer
from kctl_dokploy.core.manifest import load_and_resolve

app = typer.Typer(help="Declarative deployment from YAML manifests.")


@app.command()
def apply(
    ctx: typer.Context,
    file: Annotated[Path, typer.Option("--file", "-f", help="Path to instance manifest YAML")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview changes without applying")] = False,
    skip_deploy: Annotated[bool, typer.Option("--skip-deploy", help="Set up everything but don't trigger deploy")] = False,
    skip_verify: Annotated[bool, typer.Option("--skip-verify", help="Skip healthcheck verification")] = False,
) -> None:
    """Apply a deployment manifest (create or update, idempotent)."""
    c: AppContext = ctx.obj
    out = c.output

    if not file.exists():
        out.error(f"Manifest not found: {file}")
        raise typer.Exit(1)

    out.info(f"Loading manifest: {file}")
    manifest = load_and_resolve(file)
    out.info(f"Instance: {manifest.instance.name} ({manifest.type})")

    if dry_run:
        out.warn("DRY RUN — no changes will be made")

    deployer = Deployer(manifest=manifest, dry_run=dry_run)

    # Run phases
    deployer.phase_dns()
    deployer.phase_database()
    deployer.phase_registry()
    deployer.phase_compose()
    deployer.phase_environment()
    deployer.phase_domain()

    if not skip_deploy:
        deployer.phase_deploy()
    else:
        deployer._record_phase("deploy", "skipped", "Skipped by --skip-deploy")

    if not skip_verify and not skip_deploy:
        deployer.phase_verify()
    else:
        deployer._record_phase("verify", "skipped", "Skipped")

    deployer.phase_backup()
    deployer.phase_schedules()
    deployer.phase_post_deploy()

    # Summary table
    rows = []
    for r in deployer.results:
        rows.append([r.phase, r.action, r.message])

    out.table(
        f"Deploy Summary: {manifest.instance.name}",
        [("Phase", "cyan"), ("Action", ""), ("Details", "dim")],
        rows,
        data_for_json=[{"phase": r.phase, "action": r.action, "message": r.message} for r in deployer.results],
    )

    failed = [r for r in deployer.results if r.action == "failed"]
    if failed:
        out.error(f"{len(failed)} phase(s) failed")
        raise typer.Exit(1)
    else:
        out.success("Deployment complete")


@app.command()
def status(
    ctx: typer.Context,
    file: Annotated[Path, typer.Option("--file", "-f", help="Path to instance manifest YAML")],
) -> None:
    """Check current state vs manifest (what would change)."""
    c: AppContext = ctx.obj
    if not file.exists():
        c.output.error(f"Manifest not found: {file}")
        raise typer.Exit(1)
    # Dry-run is effectively a status check
    manifest = load_and_resolve(file)
    c.output.info(f"Status for: {manifest.instance.name}")
    deployer = Deployer(manifest=manifest, dry_run=True)
    deployer.run_all()

    rows = [[r.phase, r.action, r.message] for r in deployer.results]
    c.output.table(
        f"Status: {manifest.instance.name}",
        [("Phase", "cyan"), ("Action", ""), ("Details", "dim")],
        rows,
    )


@app.command("apply-all")
def apply_all(
    ctx: typer.Context,
    dir: Annotated[Path, typer.Option("--dir", "-d", help="Directory with instance manifests")] = Path("deploys/instances"),
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview changes")] = False,
) -> None:
    """Apply all instance manifests in a directory."""
    c: AppContext = ctx.obj
    if not dir.exists():
        c.output.error(f"Directory not found: {dir}")
        raise typer.Exit(1)

    files = sorted(dir.glob("*.yaml")) + sorted(dir.glob("*.yml"))
    if not files:
        c.output.info(f"No manifest files found in {dir}")
        return

    c.output.info(f"Found {len(files)} manifest(s) in {dir}")
    for f in files:
        c.output.header(f"Applying: {f.name}")
        manifest = load_and_resolve(f)
        deployer = Deployer(manifest=manifest, dry_run=dry_run)
        deployer.run_all()

        failed = [r for r in deployer.results if r.action == "failed"]
        if failed:
            c.output.error(f"{f.name}: {len(failed)} phase(s) failed")
        else:
            c.output.success(f"{f.name}: OK")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all instance manifests and their status."""
    c: AppContext = ctx.obj
    deploy_dir = Path("deploys/instances")
    if not deploy_dir.exists():
        c.output.info("No deploys/instances/ directory found")
        return

    files = sorted(deploy_dir.glob("*.yaml")) + sorted(deploy_dir.glob("*.yml"))
    rows = []
    for f in files:
        try:
            manifest = load_and_resolve(f)
            domain = manifest.domain.host if manifest.domain else "-"
            rows.append([f.name, manifest.instance.name, manifest.type, domain])
        except Exception as e:
            rows.append([f.name, "ERROR", "-", str(e)[:50]])

    c.output.table(
        f"Deploy Manifests ({len(rows)})",
        [("File", "dim"), ("Instance", "cyan"), ("Type", ""), ("Domain", "")],
        rows,
    )
```

- [ ] **Step 2: Register in cli.py**

Add to imports in `packages/kctl-dokploy/src/kctl_dokploy/cli.py`:
```python
from kctl_dokploy.commands.deploy import app as deploy_app
```

Add to command registrations:
```python
app.add_typer(deploy_app, name="deploy")
```

- [ ] **Step 3: Run to verify CLI loads**

```bash
cd packages/kctl-dokploy && uv run kctl-dokploy deploy --help
```
Expected: Shows apply, status, apply-all, list commands

- [ ] **Step 4: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/commands/deploy.py packages/kctl-dokploy/src/kctl_dokploy/cli.py
git commit -m "feat(deploy): add deploy apply/status/apply-all/list CLI commands"
```

---

### Task 4: Base Templates

**Files:**
- Create: `deploys/bases/odoo.yaml`
- Create: `deploys/bases/react-pwa.yaml`
- Create: `deploys/bases/infra.yaml`

- [ ] **Step 1: Create Odoo base template**

```yaml
# deploys/bases/odoo.yaml
kind: base
type: odoo

source:
  type: github
  owner: tgunawandev
  repo: kodemeio-odoo
  branch: "18.0"
  compose_path: ./docker-compose.prod.yml

server: kodeme-service
project: kodemeio-service

healthcheck:
  path: /web/health
  port: 8069
  expected_status: 200
  timeout: 120
  interval: 10

env_defaults:
  RUNNING_ENV: production
  ODOO_WORKERS: "4"
  ODOO_MAX_CRON_THREADS: "2"
  ODOO_LIST_DB: "False"
  WITHOUT_DEMO: "True"
  PGHOST: "10.0.0.3"
  PGPORT: "5432"
  TZ: "Asia/Jakarta"

backup:
  destination: kodemeio-s3-backups
  type: postgres
  schedule: "0 2 * * *"
  prefix_template: "odoo-{instance_name}"
  keep_latest: 30

schedules:
  - name: "{instance_name}-vacuum"
    cron: "0 4 * * 0"
    command: "vacuumdb -U {db_user} -d {db_name} --analyze"
    service: odoo
    shell: bash
    timezone: Asia/Jakarta
  - name: "{instance_name}-session-cleanup"
    cron: "0 3 * * *"
    command: "psql -U {db_user} -d {db_name} -c \"DELETE FROM ir_sessions WHERE write_date < NOW() - INTERVAL '7 days'\""
    service: odoo
    shell: bash
    timezone: Asia/Jakarta

post_deploy:
  odoo_profile: null
  odoo_init_db: true
```

- [ ] **Step 2: Create React PWA base template**

```yaml
# deploys/bases/react-pwa.yaml
kind: base
type: react-pwa

source:
  type: github
  owner: tgunawandev
  repo: kodemeio-react
  branch: main
  compose_path: null

server: kodeme-service
project: kodemeio-app

healthcheck:
  path: /
  port: 80
  expected_status: 200
  timeout: 60
  interval: 5

env_defaults:
  NODE_ENV: production
  VITE_AUTH_MODE: oidc
  VITE_OIDC_AUTHORITY: "https://auth.kodeme.io/application/o/kodemeio/"
  TZ: "Asia/Jakarta"
```

- [ ] **Step 3: Create infrastructure base template**

```yaml
# deploys/bases/infra.yaml
kind: base
type: infrastructure

server: kodeme-service
project: kodemeio-service

healthcheck:
  path: /
  port: 80
  expected_status: 200
  timeout: 60
  interval: 10

env_defaults:
  TZ: "Asia/Jakarta"

backup:
  destination: kodemeio-s3-backups
  type: postgres
  schedule: "0 3 * * *"
  prefix_template: "{instance_name}"
  keep_latest: 14
```

- [ ] **Step 4: Commit**

```bash
git add deploys/
git commit -m "feat(deploy): add base templates for odoo, react-pwa, infrastructure"
```

---

### Task 5: First Real Instance — Odoo Production

**Files:**
- Create: `deploys/instances/odoo-prod.yaml`

- [ ] **Step 1: Create Odoo production instance manifest**

```yaml
# deploys/instances/odoo-prod.yaml
kind: instance
extends: ../bases/odoo.yaml

instance:
  name: kodemeio-odoo-prod
  description: "Kodemeio Production ERP — Distribution"

dns:
  zone: kodeme.io
  name: odoo
  content: 49.13.14.79

domain:
  host: odoo.kodeme.io
  port: 8069
  service: odoo
  https: true

database:
  name: kodemeio_prod
  user: odoo

env_overrides:
  PGDATABASE: kodemeio_prod
  PGUSER: odoo
  PGPASSWORD: "${OP_ODOO_PGPASSWORD}"
  ODOO_ADMIN_PASSWD: "${OP_ODOO_ADMIN_PASSWD}"
  ODOO_DB_FILTER: "^kodemeio_prod$"
  DOMAIN: odoo.kodeme.io

post_deploy:
  odoo_profile: profile-distribution
```

- [ ] **Step 2: Test with dry-run**

```bash
uv tool install --force --reinstall packages/kctl-dokploy
kctl-dokploy deploy apply --file deploys/instances/odoo-prod.yaml --dry-run
```
Expected: Summary table showing all phases as "skipped" (dry-run)

- [ ] **Step 3: Test manifest list**

```bash
kctl-dokploy deploy list
```
Expected: Shows odoo-prod.yaml with instance name and domain

- [ ] **Step 4: Commit**

```bash
git add deploys/instances/odoo-prod.yaml
git commit -m "feat(deploy): add Odoo production instance manifest"
```

---

### Task 6: Install, Reinstall, and End-to-End Test

- [ ] **Step 1: Reinstall kctl-dokploy**

```bash
uv tool install --force --reinstall packages/kctl-dokploy
```

- [ ] **Step 2: Run full test suite**

```bash
cd packages/kctl-dokploy && uv run pytest tests/core/test_manifest.py tests/core/test_deployer.py -v
```
Expected: All tests pass

- [ ] **Step 3: Dry-run the Odoo deployment**

```bash
kctl-dokploy deploy apply --file deploys/instances/odoo-prod.yaml --dry-run
```
Expected: 11-phase summary table, all "skipped" (dry-run mode)

- [ ] **Step 4: Run deploy list**

```bash
kctl-dokploy deploy list
```
Expected: Table showing odoo-prod.yaml

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: deployment manifest system — complete with bases, instances, and CLI"
git push
```
