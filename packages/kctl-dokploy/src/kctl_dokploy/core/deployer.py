"""12-phase deployment executor that drives kctl-* CLIs via subprocess.

Each phase shells out to the appropriate kctl-* CLI tool to check current
state and apply changes when needed.  A ``dry_run=True`` flag skips all
mutating commands while still executing read-only ones (list / get / show /
test / status / check).
"""

from __future__ import annotations

import json
import logging
import pathlib
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from kctl_dokploy.core.deploy_validators import DeployValidator
from kctl_dokploy.core.manifest import DeployManifest, load_env_file

_logger = logging.getLogger(__name__)
from kctl_dokploy.core.validators import (
    resolve_server_ip,
    validate_dns_ip,
    validate_dns_resolution,
    validate_project_exists,
    find_github_app_id,
    disable_autodeploy,
    validate_service_name,
    check_domain_routing,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Verbs that are always safe to run even in dry-run mode.
_READONLY_VERBS: frozenset[str] = frozenset({"list", "get", "show", "test", "status", "check", "health"})


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class PhaseResult:
    """Result from a single deployment phase."""

    phase: str
    """Name of the phase (e.g. ``"dns"``)."""
    action: str
    """Outcome: ``"created"``, ``"updated"``, ``"skipped"``, or ``"failed"``."""
    message: str
    """Human-readable description of what happened."""

    def __repr__(self) -> str:  # noqa: D401
        return f"PhaseResult(phase={self.phase!r}, action={self.action!r}, message={self.message!r})"


# ---------------------------------------------------------------------------
# Deployer
# ---------------------------------------------------------------------------


@dataclass
class Deployer:
    """Execute all 12 deployment phases for a resolved :class:`DeployManifest`."""

    manifest: DeployManifest
    dry_run: bool = False
    skip_preflight: bool = False

    # Populated during execution
    results: list[PhaseResult] = field(default_factory=list)
    _compose_id: str = field(default="", init=False)
    _merged_env: dict[str, str] = field(default_factory=dict, init=False)

    # ------------------------------------------------------------------
    # Low-level subprocess helpers
    # ------------------------------------------------------------------

    def _is_mutating(self, cmd: list[str]) -> bool:
        """Return True when *cmd* will modify remote state.

        A command is mutating when none of its tokens (after the binary name)
        is a known read-only verb.  This is intentionally conservative:
        anything we cannot classify as read-only is treated as mutating.
        """
        # Walk through tokens looking for the first "verb-like" token
        # (skip the binary name and any --flags).
        verbs = [t for t in cmd[1:] if not t.startswith("-")]
        if not verbs:
            return True
        # If *any* verb is in the read-only set we treat the command as safe.
        return not any(v in _READONLY_VERBS for v in verbs)

    def _run_kctl(self, cmd: list[str]) -> tuple[int, str]:
        """Run *cmd* via :mod:`subprocess`.

        In dry-run mode, mutating commands are skipped and ``(0, "")`` is
        returned.  Read-only commands are always executed.

        Returns:
            ``(returncode, stdout)``
        """
        if self.dry_run and self._is_mutating(cmd):
            return 0, "[dry-run] skipped"

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        return proc.returncode, proc.stdout.strip()

    def _run_kctl_json(self, cmd: list[str]) -> list | dict:
        """Run *cmd* with ``--json`` injected after the binary name, parse output.

        Falls back to an empty list on non-zero exit or JSON parse errors.
        """
        # Insert --json right after the binary
        json_cmd = [cmd[0], "--json"] + cmd[1:]
        code, out = self._run_kctl(json_cmd)
        if code != 0 or not out:
            return []
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return []

    def _record_phase(self, phase: str, action: str, message: str) -> None:
        """Append a :class:`PhaseResult` to :attr:`results`."""
        self.results.append(PhaseResult(phase=phase, action=action, message=message))

    def _log(self, message: str) -> None:
        """Log an informational message (non-phase, for validation feedback)."""
        import sys

        print(f"[deploy] {message}", file=sys.stderr)

    def _action(self, action: str) -> str:
        """Prefix action with 'would-' in dry-run mode."""
        return f"would-{action}" if self.dry_run else action

    def _msg(self, message: str) -> str:
        """Prefix message with '[dry-run]' in dry-run mode."""
        return f"[dry-run] {message}" if self.dry_run else message

    def _resolve_server_id(self, server_name: str) -> str:
        """Resolve a server name (e.g. 'kodeme-service') to its Dokploy server ID."""
        servers = self._run_kctl_json(["kctl-dokploy", "servers", "list"])
        if isinstance(servers, list):
            for s in servers:
                if s.get("name", "") == server_name or s.get("serverName", "") == server_name:
                    return s.get("serverId", "")
        return ""

    def _find_github_id(self) -> str:
        """Discover the Dokploy GitHub app ID from configured git providers.

        The compose API needs ``github.githubId`` (the GitHub App installation ID),
        NOT ``gitProviderId`` (the Dokploy provider record ID).
        """
        providers: list | dict = self._run_kctl_json(["kctl-dokploy", "git", "list"])
        if isinstance(providers, list):
            for p in providers:
                if p.get("providerType") == "github":
                    # The githubId is nested under the github sub-object
                    github = p.get("github", {})
                    if isinstance(github, dict):
                        return github.get("githubId", "")
        return ""

    def _disable_auto_deploy(self) -> None:
        """Disable autoDeploy on the compose service via direct API call."""
        if not self._compose_id or self.dry_run:
            return
        try:
            from kctl_dokploy.core.callbacks import AppContext
            from kctl_dokploy.core.client import DokployClient
            from kctl_lib.config import load_config

            cfg = load_config()
            profile = cfg.get("default_profile", "kodemeio")
            profiles = cfg.get("profiles", {})
            p = profiles.get(profile, {})
            dokploy_cfg = p.get("dokploy", {})
            url = dokploy_cfg.get("url", "")
            key = dokploy_cfg.get("api_key", "")
            if url and key:
                client = DokployClient(base_url=url, credential=key)
                client.post("/compose.update", json={"composeId": self._compose_id, "autoDeploy": False})
        except Exception:
            pass  # Best-effort; autoDeploy can be disabled manually

    def _apply_advanced_compose_settings(self) -> None:
        """Apply advanced compose settings (command, triggerType, submodules) via direct API."""
        if not self._compose_id or self.dry_run:
            return
        client = self._get_client()
        if not client:
            return
        advanced_payload: dict[str, Any] = {"composeId": self._compose_id}
        changed = False
        if self.manifest.command:
            advanced_payload["command"] = self.manifest.command
            changed = True
        if self.manifest.trigger_type:
            advanced_payload["triggerType"] = self.manifest.trigger_type
            changed = True
        if self.manifest.enable_submodules:
            advanced_payload["enableSubmodules"] = self.manifest.enable_submodules
            changed = True
        if changed:
            try:
                client.post("/compose.update", json=advanced_payload)
                self._log(f"Applied advanced settings: {list(advanced_payload.keys())}")
            except Exception:
                pass  # Best-effort

    def _get_client(self):
        """Get a DokployClient instance for direct API calls (validation)."""
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

    # ------------------------------------------------------------------
    # Phase preflight — pre-deploy gate checks
    # ------------------------------------------------------------------

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
            self._record_phase("preflight", "passed", f"{len(results)} gates checked ({warns} warnings)")

    # ------------------------------------------------------------------
    # Phase 0b — Pre-validate (type-aware)
    # ------------------------------------------------------------------

    def phase_pre_validate(self) -> None:
        """Type-aware pre-deploy validation (before DNS phase)."""
        # Build merged env for validation
        merged: dict[str, str] = dict(self.manifest.env_defaults)
        if self.manifest.env_file:
            env_path = pathlib.Path(self.manifest.env_file)
            if env_path.exists():
                merged.update(load_env_file(env_path))
        merged.update(self.manifest.env_overrides)
        self._merged_env = merged

        validator = DeployValidator(
            manifest=self.manifest,
            env_vars=self._merged_env,
            dry_run=self.dry_run,
        )

        warnings, errors = validator.pre_validate()

        for w in warnings:
            _logger.warning("PRE-VALIDATE: %s", w)

        if errors:
            for e in errors:
                _logger.error("PRE-VALIDATE: %s", e)
            msg = f"Pre-validation failed ({len(errors)} error(s)): " + "; ".join(errors)
            self._record_phase("pre_validate", "failed", msg)
        elif warnings:
            msg = f"Pre-validation passed with {len(warnings)} warning(s)"
            self._record_phase("pre_validate", self._action("updated"), msg)
        else:
            self._record_phase("pre_validate", self._action("updated"), "All pre-deploy checks passed")

    # ------------------------------------------------------------------
    # Phase 1 — DNS
    # ------------------------------------------------------------------

    def phase_dns(self) -> None:
        """Ensure the DNS A/CNAME record exists in Cloudflare (idempotent).

        The server IP is always resolved dynamically from the Dokploy servers
        API.  If the manifest has a hardcoded ``dns.content``, it is validated
        against the resolved IP (mismatch = hard failure) and a deprecation
        warning is emitted encouraging removal of the hardcoded value.

        After record creation the FQDN is resolved via ``socket.getaddrinfo``
        and compared against the expected IP as a post-creation sanity check.
        """
        # Gate 1: Resolve server IP dynamically
        client = self._get_client()
        server_ip = ""
        if client and self.manifest.server:
            ok, msg, server_ip = resolve_server_ip(client, self.manifest.server)
            if not ok:
                self._record_phase("dns", "failed", f"[VALIDATION] {msg}")
                return

            # Auto-fill dns.content from resolved server IP
            if self.manifest.dns and not self.manifest.dns.content and server_ip:
                self.manifest.dns.content = server_ip
                self._log(f"Auto-resolved DNS IP from server '{self.manifest.server}': {server_ip}")
            elif self.manifest.dns and self.manifest.dns.content and server_ip:
                # Warn about hardcoded IP that matches — encourage removal
                if self.manifest.dns.content == server_ip:
                    self._log(
                        f"DEPRECATION: dns.content is hardcoded to {self.manifest.dns.content} "
                        f"which matches server '{self.manifest.server}'. "
                        f"Remove dns.content from manifest to auto-resolve."
                    )
                # Validate hardcoded IP against server (mismatch = failure)
                ok2, msg2 = validate_dns_ip(self.manifest.dns.content, server_ip, self.manifest.server)
                if not ok2:
                    self._record_phase("dns", "failed", f"[VALIDATION] {msg2}")
                    return

        dns = self.manifest.dns
        if not dns.zone or not dns.name:
            self._record_phase("dns", "skipped", "No DNS config specified")
            return

        fqdn = f"{dns.name}.{dns.zone}" if not dns.name.endswith(dns.zone) else dns.name

        # Use JSON output for reliable matching (text output truncates long names)
        existing_records = self._run_kctl_json(["kctl-cf", "records", "list", "--zone", dns.zone])
        if isinstance(existing_records, list):
            for rec in existing_records:
                if rec.get("name") == fqdn or rec.get("name", "").startswith(dns.name):
                    self._record_phase("dns", "skipped", f"Record {dns.name} already exists")
                    return

        # Create the record
        code, out = self._run_kctl(
            [
                "kctl-cf",
                "records",
                "create",
                "--zone",
                dns.zone,
                "--type",
                dns.type,
                "--name",
                dns.name,
                "--content",
                dns.content,
            ]
        )

        if code == 0:
            self._record_phase(
                "dns",
                self._action("created"),
                self._msg(f"Create {dns.type} record {dns.name} → {dns.content}"),
            )
            # Post-creation validation: resolve FQDN and assert it matches
            if not self.dry_run and server_ip:
                ok_v, msg_v = validate_dns_resolution(fqdn, server_ip)
                if ok_v:
                    self._log(f"Post-DNS validation passed: {msg_v}")
                else:
                    self._log(f"Post-DNS validation warning: {msg_v}")
                    self._record_phase(
                        "dns-verify",
                        "warning",
                        f"DNS created but resolution check failed: {msg_v}",
                    )
        else:
            # Idempotent: if creation fails because record already exists, treat as success
            if "already exists" in out.lower() or "duplicate" in out.lower():
                self._record_phase("dns", "skipped", f"Record {dns.name} already exists")
            else:
                self._record_phase("dns", "failed", f"Failed to create DNS record: {out}")

    # ------------------------------------------------------------------
    # Phase 2 — Database
    # ------------------------------------------------------------------

    def phase_database(self) -> None:
        """Ensure the PostgreSQL role and database exist (idempotent).

        Uses ``kctl-pg`` which connects via SSH tunnel to the database server.
        """
        db = self.manifest.database
        if not db.name or not db.user:
            self._record_phase("database", "skipped", "No database config specified")
            return

        if self.dry_run:
            self._record_phase("database", "would-created", f"[dry-run] Provision role={db.user}, db={db.name}")
            return

        # Check if database already exists via kctl-pg
        existing_dbs = self._run_kctl_json(["kctl-pg", "db", "list"])
        db_names = {d.get("datname", "") for d in (existing_dbs if isinstance(existing_dbs, list) else [])}
        if db.name in db_names:
            self._record_phase("database", "skipped", f"Database {db.name} already exists")
            return

        # Check if role exists
        existing_users = self._run_kctl_json(["kctl-pg", "users", "list"])
        user_names = {u.get("rolname", "") for u in (existing_users if isinstance(existing_users, list) else [])}
        if db.user not in user_names:
            code, out = self._run_kctl(["kctl-pg", "users", "create", db.user])
            if code != 0 and "already exists" not in out:
                self._record_phase("database", "failed", f"Failed to create role {db.user}: {out}")
                return

        # Create database (positional NAME, --owner flag)
        code, out = self._run_kctl(["kctl-pg", "db", "create", db.name, "--owner", db.user])
        if code == 0:
            self._record_phase("database", "created", f"Created database {db.name} (owner={db.user})")
        elif "already exists" in out:
            self._record_phase("database", "skipped", f"Database {db.name} already exists")
        else:
            self._record_phase("database", "failed", f"Failed to create database: {out}")

    # ------------------------------------------------------------------
    # Phase 3 — Registry
    # ------------------------------------------------------------------

    def phase_registry(self) -> None:
        """Verify that a GHCR registry entry exists (manual setup only)."""
        registries: list | dict = self._run_kctl_json(["kctl-dokploy", "registry", "list"])
        if isinstance(registries, list):
            for reg in registries:
                if reg.get("registryType") == "ghcr":
                    self._record_phase("registry", "skipped", "GHCR registry already configured")
                    return

        self._record_phase(
            "registry",
            "skipped",
            "No GHCR registry found — manual setup required in Dokploy UI",
        )

    # ------------------------------------------------------------------
    # Phase 4 — Compose
    # ------------------------------------------------------------------

    def phase_compose(self) -> None:
        """Find or create the Docker Compose service in the Dokploy project."""
        src = self.manifest.source
        instance_name = self.manifest.instance.name
        project_name = self.manifest.project

        # Fetch all projects to find matching project + compose
        projects: list | dict = self._run_kctl_json(["kctl-dokploy", "projects", "list"])
        project_data: dict[str, Any] | None = None
        if isinstance(projects, list):
            for proj in projects:
                if proj.get("name") == project_name:
                    project_data = proj
                    break

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

        # Fall back to default environment ONLY for production
        if not target_env_id:
            if target_env_name.lower() != "production":
                self._record_phase(
                    "compose",
                    "failed",
                    f"Dokploy environment '{target_env_name}' not found and could not be created",
                )
                return
            target_env_id = default_environment_id
            for env in (project_data or {}).get("environments", []):
                if env.get("environmentId") == default_environment_id:
                    target_env_data = env
                    break

        # Search ONLY the target environment for existing compose
        existing_composes: list[dict[str, Any]] = []
        for comp in target_env_data.get("compose", []):
            existing_composes.append(comp)

        # Check if compose already exists
        for comp in existing_composes:
            if comp.get("name") == instance_name:
                self._compose_id = comp["composeId"]
                github_id = comp.get("githubId", "")
                if not github_id:
                    github_id = self._find_github_id()
                # Update the GitHub source using --id flag
                update_args = [
                    "kctl-dokploy",
                    "compose",
                    "update",
                    "--id",
                    self._compose_id,
                    "--source-type",
                    "github",
                    "--owner",
                    src.owner,
                    "--repo",
                    src.repo,
                    "--branch",
                    src.branch,
                    "--compose-path",
                    src.compose_path,
                ]
                if github_id:
                    update_args += ["--github-id", github_id]
                self._run_kctl(update_args)
                # Gate 4: Disable autodeploy on existing compose too
                self._disable_auto_deploy()
                client = self._get_client()
                if client and self._compose_id:
                    ok, msg = disable_autodeploy(client, self._compose_id)
                    if not ok:
                        self._log(f"WARNING: autodeploy: {msg}")
                self._apply_advanced_compose_settings()
                self._record_phase("compose", "updated", f"Updated compose {instance_name} (id={self._compose_id})")
                return

        # Create new compose in the target environment
        env_id = target_env_id or default_environment_id
        if not env_id:
            self._record_phase("compose", "failed", "No environment ID resolved — cannot create compose")
            return
        create_args = [
            "kctl-dokploy",
            "compose",
            "create",
            env_id,
            "--name",
            instance_name,
        ]
        # Deploy on specific server if manifest specifies one
        server_name = self.manifest.server
        if server_name:
            server_id = self._resolve_server_id(server_name)
            if server_id:
                create_args += ["--server", server_id]
        code, out = self._run_kctl(create_args)

        # Parse the returned compose ID from text output
        # Format: "OK Compose 'name' created: <compose-id>"
        new_compose_id = ""
        if code == 0 and out:
            try:
                resp = json.loads(out)
                new_compose_id = resp.get("composeId", "")
            except json.JSONDecodeError:
                # Parse from text: last word after "created:" or last non-empty token
                for line in out.splitlines():
                    if "created:" in line:
                        new_compose_id = line.split("created:")[-1].strip()
                        break

        if new_compose_id:
            self._compose_id = new_compose_id
            # Discover githubId from git providers for linking GitHub source
            github_id = self._find_github_id()
            update_args = [
                "kctl-dokploy",
                "compose",
                "update",
                "--id",
                self._compose_id,
                "--source-type",
                "github",
                "--owner",
                src.owner,
                "--repo",
                src.repo,
                "--branch",
                src.branch,
                "--compose-path",
                src.compose_path,
            ]
            if github_id:
                update_args += ["--github-id", github_id]
            self._run_kctl(update_args)
            # Gate 4: Disable autodeploy — ALWAYS, using both methods
            self._disable_auto_deploy()  # Direct API call (fast)
            client = self._get_client()
            if client and self._compose_id:
                ok, msg = disable_autodeploy(client, self._compose_id)
                if not ok:
                    self._log(f"WARNING: autodeploy: {msg}")
                else:
                    self._log(msg)
            self._apply_advanced_compose_settings()
            self._record_phase(
                "compose", self._action("created"), self._msg(f"Create compose {instance_name} (id={self._compose_id})")
            )
        else:
            if self.dry_run:
                self._record_phase("compose", "would-created", f"[dry-run] Would create compose {instance_name}")
            else:
                self._record_phase("compose", "failed", f"Failed to create compose {instance_name}: {out}")

    # ------------------------------------------------------------------
    # Phase 5 — Environment
    # ------------------------------------------------------------------

    def phase_environment(self) -> None:
        """Push merged environment variables to the compose service.

        Merge priority (lowest to highest):
        1. ``env_file`` — loaded from dotenv file if specified
        2. ``env_defaults`` — base manifest defaults
        3. ``env_overrides`` — instance-specific overrides
        4. Auto-injected ``ODOO_DEPLOY_PROFILE`` from ``post_deploy.odoo_profile``
        """
        if not self._compose_id:
            self._record_phase("environment", "skipped", "No compose_id set — skipping env push")
            return

        # Layer 1: env_file (lowest priority)
        env: dict[str, str] = {}
        if self.manifest.env_file:
            from pathlib import Path

            env_path = Path(self.manifest.env_file)
            if env_path.exists():
                env.update(load_env_file(env_path))
            else:
                self._record_phase("environment", "failed", f"Env file not found: {self.manifest.env_file}")
                return

        # Layer 2 + 3: defaults and overrides
        env.update(self.manifest.env_defaults)
        env.update(self.manifest.env_overrides)

        # Layer 4: auto-sync ODOO_DEPLOY_PROFILE from post_deploy.odoo_profile
        if self.manifest.post_deploy.odoo_profile:
            profile = self.manifest.post_deploy.odoo_profile.removeprefix("profile-")
            env["ODOO_DEPLOY_PROFILE"] = profile

        if not env:
            self._record_phase("environment", "skipped", "No environment variables to push")
            return

        env_content = "\n".join(f"{k}={v}" for k, v in env.items())

        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as tmp:
            tmp.write(env_content)
            tmp_path = tmp.name

        try:
            # env push: options before --, positional args (compose_id, file) after --
            code, out = self._run_kctl(["kctl-dokploy", "env", "push", "--force", "--", self._compose_id, tmp_path])
            if code == 0:
                # Validate React PWA env vars
                warnings = self._validate_react_env(env)
                if warnings:
                    for w in warnings:
                        self._log(f"ENV VALIDATION: {w}")
                self._record_phase("environment", "updated", f"Pushed {len(env)} env vars to {self._compose_id}")
            else:
                self._record_phase("environment", "failed", f"Failed to push env vars: {out}")
        finally:
            pathlib.Path(tmp_path).unlink(missing_ok=True)

    def _validate_react_env(self, env_vars: dict[str, str]) -> list[str]:
        """Validate React PWA environment variables. Returns list of warnings."""
        warnings: list[str] = []
        compose_path = ""
        if hasattr(self.manifest, "source_overrides") and isinstance(self.manifest.source_overrides, dict):
            compose_path = self.manifest.source_overrides.get("compose_path", "")
        elif hasattr(self.manifest, "source") and hasattr(self.manifest.source, "compose_path"):
            compose_path = self.manifest.source.compose_path or ""

        # Only validate React PWA composes
        react_apps = ["sfa", "lfa", "shop", "wms", "bia", "hrm", "mrp", "eam", "tpm", "dms", "saas"]
        if not any(app in compose_path for app in react_apps):
            return warnings

        # Check API base URL includes app path
        fastapi_paths = [
            "sfa",
            "lfa",
            "shop",
            "wms",
            "bia",
            "hrm",
            "mrp",
            "eam",
            "asset",
            "dms",
            "tpm",
            "recruitment",
            "saas",
        ]
        for key, val in env_vars.items():
            if key.startswith("VITE_") and key.endswith("_API_BASE_URL") and val:
                if not any(val.endswith(f"/{app}/api") for app in fastapi_paths):
                    warnings.append(
                        f"  {key}={val} — missing app path (e.g., /wms/api). "
                        f"Login will fail without the FastAPI root path."
                    )

        # Check auth mode is set
        auth_mode = env_vars.get("VITE_AUTH_MODE", "")
        if not auth_mode:
            warnings.append("  VITE_AUTH_MODE not set — defaults to 'oidc'")

        return warnings

    # ------------------------------------------------------------------
    # Phase 6 — Domain
    # ------------------------------------------------------------------

    def phase_domain(self) -> None:
        """Ensure the reverse-proxy domain mapping exists."""
        domain = self.manifest.domain
        if not domain.host:
            self._record_phase("domain", "skipped", "No domain config specified")
            return

        if not self._compose_id:
            self._record_phase("domain", "skipped", "No compose_id set — skipping domain config")
            return

        # Gate 5: Validate service name
        client = self._get_client()
        if client and self._compose_id and domain and domain.service:
            ok, msg = validate_service_name(client, self._compose_id, domain.service)
            if not ok:
                self._record_phase("domain", "failed", f"[VALIDATION] {msg}")
                return
            self._log(msg)

        existing: list | dict = self._run_kctl_json(["kctl-dokploy", "domains", "get", "--", self._compose_id])
        if isinstance(existing, list):
            for d in existing:
                if d.get("host") == domain.host:
                    self._record_phase("domain", "skipped", f"Domain {domain.host} already configured")
                    return
        elif isinstance(existing, dict) and existing.get("host") == domain.host:
            self._record_phase("domain", "skipped", f"Domain {domain.host} already configured")
            return

        https_flag = "--https" if domain.https else "--no-https"
        # Bug fix #2: include --service and --cert flags for proper Dokploy routing
        # Options before --, positional compose_id after --
        create_args = [
            "kctl-dokploy",
            "domains",
            "create",
            "--host",
            domain.host,
            "--port",
            str(domain.port),
            https_flag,
            "--cert",
            domain.cert,
        ]
        if domain.service:
            create_args += ["--service", domain.service]
        create_args += ["--", self._compose_id]
        code, out = self._run_kctl(create_args)
        if code == 0:
            self._record_phase(
                "domain", self._action("created"), self._msg(f"Create domain {domain.host}:{domain.port}")
            )
        else:
            self._record_phase("domain", "failed", f"Failed to create domain: {out}")

    # ------------------------------------------------------------------
    # Phase 7 — Deploy
    # ------------------------------------------------------------------

    def phase_deploy(self) -> None:
        """Trigger a redeploy and wait for Dokploy to finish (fail-fast on error)."""
        if not self._compose_id:
            if self.dry_run:
                self._record_phase("deploy", "would-updated", "[dry-run] Would redeploy")
            else:
                self._record_phase("deploy", "failed", "No compose_id set — cannot redeploy")
            return

        code, out = self._run_kctl(["kctl-dokploy", "compose", "redeploy", "--", self._compose_id])
        if code != 0:
            self._record_phase("deploy", "failed", f"Redeploy trigger failed: {out}")
            self._auto_diagnose("deploy")
            return

        # Poll Dokploy deployment status — fail fast if deployment errors
        deadline = time.monotonic() + self.manifest.healthcheck.timeout
        while time.monotonic() < deadline:
            deploys = self._run_kctl_json(
                ["kctl-dokploy", "deployments", "list", "--compose", self._compose_id, "--limit", "1"]
            )
            if isinstance(deploys, list) and deploys:
                status = deploys[0].get("status", "")
                if status == "done":
                    self._record_phase("deploy", "updated", f"Deployment completed for {self._compose_id}")
                    return
                if status == "error":
                    title = deploys[0].get("title", "")[:80]
                    self._record_phase("deploy", "failed", f"Deployment error: {title}")
                    self._auto_diagnose("deploy")
                    return
                # status is "running" or "queued" — keep waiting
            time.sleep(10)

        self._record_phase("deploy", "failed", f"Deployment timed out after {self.manifest.healthcheck.timeout}s")
        self._auto_diagnose("deploy")

    # ------------------------------------------------------------------
    # Phase 8 — Verify (healthcheck)
    # ------------------------------------------------------------------

    def phase_verify(self) -> None:
        """Poll the healthcheck URL until it responds or times out.

        Fail-fast: if the previous deploy phase already failed, skip.
        Also checks Dokploy deployment status during polling to detect errors early.
        """
        # Skip if deploy phase already failed
        if any(r.phase == "deploy" and r.action == "failed" for r in self.results):
            self._record_phase("verify", "skipped", "Deploy phase failed — skipping healthcheck")
            return

        if self.dry_run:
            domain = self.manifest.domain
            host = domain.host or "localhost"
            self._record_phase("verify", "would-verify", f"[dry-run] Would poll https://{host}")
            return

        hc = self.manifest.healthcheck
        domain = self.manifest.domain

        host = domain.host or "localhost"
        scheme = "https" if domain.https else "http"
        # Use standard HTTPS port (no :8069 in URL — Traefik handles routing)
        url = f"{scheme}://{host}{hc.path}"

        deadline = time.monotonic() + hc.timeout
        last_error: str = ""

        while time.monotonic() < deadline:
            try:
                resp = httpx.get(url, timeout=5.0, follow_redirects=True, verify=False)
                if resp.status_code == hc.expected_status:
                    self._record_phase("verify", "updated", f"Healthcheck passed: {url} → {resp.status_code}")

                    # Run post-deploy smoke tests (warnings only)
                    validator = DeployValidator(
                        manifest=self.manifest,
                        env_vars=self._merged_env,
                        compose_id=self._compose_id,
                    )
                    smoke_results = validator.post_verify()
                    for r in smoke_results:
                        _logger.log(
                            logging.WARNING if r.status == "warn" else logging.INFO,
                            "SMOKE [%s] %s: %s",
                            r.status.upper(),
                            r.name,
                            r.detail,
                        )

                    warn_count = sum(1 for r in smoke_results if r.status == "warn")
                    if smoke_results:
                        msg = f"{len(smoke_results)} smoke test(s), {warn_count} warning(s)"
                        self._record_phase("smoke_tests", "updated", msg)

                    return
                last_error = f"unexpected status {resp.status_code}"
            except Exception as exc:
                last_error = str(exc)
            time.sleep(hc.interval)

        self._record_phase("verify", "failed", f"Healthcheck timed out after {hc.timeout}s: {last_error}")
        self._auto_diagnose("verify")

    # ------------------------------------------------------------------
    # Auto-diagnosis helper
    # ------------------------------------------------------------------

    def _auto_diagnose(self, failed_phase: str) -> None:
        """Automatically diagnose deployment failure and record findings.

        Called when phase_deploy or phase_verify fails. Uses the Dokploy API
        to gather container status, logs, and health info, then records
        the diagnosis as additional phase results.
        """
        if not self._compose_id:
            return

        client = self._get_client()
        if not client:
            return

        try:
            from kctl_dokploy.core.troubleshoot import diagnose

            domain = self.manifest.domain.host if self.manifest.domain else ""
            hc = self.manifest.healthcheck

            result = diagnose(
                client=client,
                compose_id=self._compose_id,
                domain=domain,
                health_path=hc.path,
                expected_status=hc.expected_status,
            )

            # Record diagnosis as a phase result
            diag_lines = [f"[{result.error_type.value.upper()}] {result.summary}"]

            # Add container info
            for c in result.containers:
                state_icon = "✓" if c.state == "running" else "✗"
                diag_lines.append(f"  {state_icon} {c.name}: {c.state} ({c.status})")
                if c.logs and c.state in ("exited", "dead", "restarting"):
                    # Last 5 lines of logs for crashed containers
                    for log_line in c.logs.strip().splitlines()[-5:]:
                        diag_lines.append(f"    | {log_line}")

            # Add build log excerpt if available
            if result.deployment_log and result.deployment_status == "error":
                diag_lines.append("  Build log (last lines):")
                for log_line in str(result.deployment_log).strip().splitlines()[-5:]:
                    diag_lines.append(f"    | {log_line}")

            # Add suggestions
            if result.suggestions:
                diag_lines.append("  Suggested fixes:")
                for s in result.suggestions:
                    diag_lines.append(f"    → {s}")

            self._record_phase("diagnosis", "info", "\n".join(diag_lines))
        except Exception as e:
            self._record_phase("diagnosis", "info", f"Auto-diagnosis failed: {e}")

    # ------------------------------------------------------------------
    # Phase 9 — Backup
    # ------------------------------------------------------------------

    def _resolve_destination_id(self, destination_name: str) -> str:
        """Resolve an S3 backup destination name to its Dokploy destination ID."""
        destinations = self._run_kctl_json(["kctl-dokploy", "backups", "destinations"])
        if isinstance(destinations, list):
            for d in destinations:
                if d.get("name", "") == destination_name:
                    return d.get("destinationId", "")
        return ""

    def phase_backup(self) -> None:
        """Ensure a backup job is configured for the compose service."""
        backup = self.manifest.backup
        if backup is None:
            self._record_phase("backup", "skipped", "No backup config specified")
            return

        if not self._compose_id:
            self._record_phase("backup", "skipped", "No compose_id — skipping backup setup")
            return

        existing: list | dict = self._run_kctl_json(["kctl-dokploy", "backups", "list", "--compose", self._compose_id])
        if isinstance(existing, list) and existing:
            self._record_phase("backup", "skipped", "Backup job already configured")
            return

        # Resolve destination name → ID
        destination_id = self._resolve_destination_id(backup.destination)
        if not destination_id and not self.dry_run:
            self._record_phase("backup", "failed", f"Destination '{backup.destination}' not found — create it first")
            return

        db_name = self.manifest.database.name
        code, out = self._run_kctl(
            [
                "kctl-dokploy",
                "backups",
                "create",
                "--destination",
                destination_id or backup.destination,
                "--database",
                db_name,
                "--type",
                backup.type,
                "--compose",
                self._compose_id,
                "--schedule",
                backup.schedule,
                "--prefix",
                backup.prefix_template,
            ]
        )
        if code == 0:
            self._record_phase(
                "backup", self._action("created"), self._msg(f"Create backup job → {backup.destination}")
            )
        else:
            self._record_phase("backup", "failed", f"Failed to create backup: {out}")

    # ------------------------------------------------------------------
    # Phase 10 — Schedules
    # ------------------------------------------------------------------

    def phase_schedules(self) -> None:
        """Create any missing scheduled tasks."""
        schedules = self.manifest.schedules
        if not schedules:
            self._record_phase("schedules", "skipped", "No schedules defined")
            return

        if not self._compose_id:
            self._record_phase("schedules", "skipped", "No compose_id — skipping schedule setup")
            return

        # schedules list takes positional resource_id
        existing: list | dict = self._run_kctl_json(["kctl-dokploy", "schedules", "list", self._compose_id])
        existing_names = {s.get("name", "") for s in (existing if isinstance(existing, list) else [])}

        created: list[str] = []
        failed: list[str] = []

        for sched in schedules:
            if sched.name in existing_names:
                continue
            # Normalize shell: manifest uses "bash"/"sh", API expects shellType
            shell_type = sched.shell.split("/")[-1] if "/" in sched.shell else sched.shell
            create_cmd = [
                "kctl-dokploy",
                "schedules",
                "create",
                "--name",
                sched.name,
                "--cron",
                sched.cron,
                "--command",
                sched.command,
                "--compose",
                self._compose_id,
                "--shell",
                shell_type,
                "--timezone",
                sched.timezone,
            ]
            if sched.service:
                create_cmd += ["--service", sched.service]
            code, out = self._run_kctl(create_cmd)
            if code == 0:
                created.append(sched.name)
            else:
                failed.append(sched.name)

        if failed:
            self._record_phase("schedules", "failed", f"Failed to create: {failed}")
        elif created:
            self._record_phase("schedules", self._action("created"), self._msg(f"Create schedules: {created}"))
        else:
            self._record_phase("schedules", "skipped", "All schedules already exist")

    # ------------------------------------------------------------------
    # Phase 11 — Volume Backups
    # ------------------------------------------------------------------

    def phase_volume_backups(self) -> None:
        """Configure volume backups for compose services."""
        vbs = self.manifest.volume_backups
        if not vbs:
            self._record_phase("volume_backups", "skipped", "No volume backups configured")
            return

        if not self._compose_id:
            self._record_phase("volume_backups", "skipped", "No compose_id — skipping volume backups")
            return

        # Check existing volume backups to avoid duplicates
        existing: list | dict = self._run_kctl_json(
            ["kctl-dokploy", "volume-backups", "list", "--resource-id", self._compose_id, "--type", "compose"]
        )
        existing_names = {b.get("name", "") for b in (existing if isinstance(existing, list) else [])}

        created: list[str] = []
        failed: list[str] = []
        for vb in vbs:
            vb_name = f"vb-{vb.service or 'default'}-{self._compose_id[:8]}"
            if vb_name in existing_names:
                continue
            destination_id = self._resolve_destination_id(vb.destination) if vb.destination else ""
            cmd = [
                "kctl-dokploy",
                "volume-backups",
                "create",
                "--name",
                vb_name,
                "--compose",
                self._compose_id,
                "--schedule",
                vb.cron_schedule,
            ]
            if vb.service:
                cmd += ["--service", vb.service]
            if destination_id:
                cmd += ["--destination", destination_id]
            if vb.prefix:
                cmd += ["--prefix", vb.prefix]

            code, out = self._run_kctl(cmd)
            if code == 0:
                created.append(vb.service or "default")
            else:
                failed.append(f"{vb.service}: {out}")

        if created:
            self._record_phase("volume_backups", self._action("created"), f"Volume backups: {', '.join(created)}")
        if failed:
            self._record_phase("volume_backups", "failed", f"Failed: {'; '.join(failed)}")
        if not created and not failed:
            self._record_phase("volume_backups", "skipped", "All volume backups already exist")

    # ------------------------------------------------------------------
    # Phase 12 — Post-deploy
    # ------------------------------------------------------------------

    def phase_validate(self) -> None:
        """Validate manifest before deployment (Phase 0).

        Checks:
        - If ``odoo_profile`` is set, verify the profile exists via kctl-odoo.
        - If ``env_file`` is set, verify the file exists on disk.
        """
        errors: list[str] = []

        # Validate odoo_profile exists
        if self.manifest.post_deploy.odoo_profile:
            profile = self.manifest.post_deploy.odoo_profile
            code, out = self._run_kctl(["kctl-odoo", "bundles", "show-profile", profile.removeprefix("profile-")])
            if code != 0:
                errors.append(f"Odoo profile '{profile}' not found or failed to resolve")

        # Validate env_file exists
        if self.manifest.env_file:
            from pathlib import Path

            if not Path(self.manifest.env_file).exists():
                errors.append(f"Env file not found: {self.manifest.env_file}")

        if errors:
            self._record_phase("validate", "failed", "; ".join(errors))
            return

        # Pre-flight: verify project exists (Gate 2)
        if self.manifest.project:
            client = self._get_client()
            if client:
                ok, msg, _, _ = validate_project_exists(client, self.manifest.project)
                if not ok:
                    self._record_phase("validate", "failed", f"[PRE-FLIGHT] {msg}")
                    return

        # Pre-flight: verify GitHub provider exists (Gate 3)
        src = self.manifest.source
        if src and src.type == "github":
            client = self._get_client()
            if client:
                ok, msg, _ = find_github_app_id(client)
                if not ok:
                    self._record_phase("validate", "failed", f"[PRE-FLIGHT] {msg}")
                    return

        self._record_phase("validate", "ok", "Manifest validation passed")

    def phase_post_deploy(self) -> None:
        """Run post-deployment actions (Odoo bundle install + custom commands)."""
        pd = self.manifest.post_deploy
        has_profile = bool(pd.odoo_profile)
        has_commands = bool(pd.commands)

        if not has_profile and not has_commands:
            self._record_phase("post_deploy", "skipped", "No post-deploy actions configured")
            return

        actions: list[str] = []
        failed: list[str] = []

        # Odoo profile installation
        if has_profile:
            code, out = self._run_kctl(
                ["kctl-odoo", "bundles", "profile-install", pd.odoo_profile.removeprefix("profile-")]
            )
            if code == 0:
                actions.append(f"profile={pd.odoo_profile}")
            else:
                failed.append(f"Odoo bundle install failed: {out}")

        # Custom shell commands (run via subprocess, not kctl)
        for cmd in pd.commands:
            code, out = self._run_kctl(cmd.split())
            if code == 0:
                actions.append(cmd.split()[0])
            else:
                failed.append(f"Command '{cmd}' failed: {out}")

        if failed:
            msg = "; ".join(failed)
            self._record_phase("post_deploy", "failed", msg)
            raise RuntimeError(f"Post-deploy failed: {msg}")
        else:
            self._record_phase("post_deploy", self._action("updated"), self._msg(f"Post-deploy: {', '.join(actions)}"))

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------

    def run_all(self) -> list[PhaseResult]:
        """Execute all phases in order and return the accumulated results.

        Phase 0 (validate) and Phase 0b (pre_validate) run first and fail fast
        on invalid manifests or type-specific validation errors.
        """
        self.phase_preflight()
        # Abort if preflight failed
        if any(r.action == "failed" and r.phase == "preflight" for r in self.results):
            return self.results

        self.phase_validate()

        # Abort if validation failed
        if self.results and self.results[-1].action == "failed":
            return self.results

        self.phase_pre_validate()
        if self.results and self.results[-1].action == "failed":
            return self.results

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
        self.phase_volume_backups()
        try:
            self.phase_post_deploy()
        except RuntimeError:
            pass  # Already recorded as failed in results
        return self.results
