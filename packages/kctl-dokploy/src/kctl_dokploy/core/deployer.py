"""12-phase deployment executor that drives kctl-* CLIs via subprocess.

Each phase shells out to the appropriate kctl-* CLI tool to check current
state and apply changes when needed.  A ``dry_run=True`` flag skips all
mutating commands while still executing read-only ones (list / get / show /
test / status / check).
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from kctl_dokploy.core.manifest import DeployManifest

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

    # Populated during execution
    results: list[PhaseResult] = field(default_factory=list)
    _compose_id: str = field(default="", init=False)

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

    def _action(self, action: str) -> str:
        """Prefix action with 'would-' in dry-run mode."""
        return f"would-{action}" if self.dry_run else action

    def _msg(self, message: str) -> str:
        """Prefix message with '[dry-run]' in dry-run mode."""
        return f"[dry-run] {message}" if self.dry_run else message

    # ------------------------------------------------------------------
    # Phase 1 — DNS
    # ------------------------------------------------------------------

    def phase_dns(self) -> None:
        """Ensure the DNS A/CNAME record exists in Cloudflare."""
        dns = self.manifest.dns
        if not dns.zone or not dns.name:
            self._record_phase("dns", "skipped", "No DNS config specified")
            return

        fqdn = f"{dns.name}.{dns.zone}" if not dns.name.endswith(dns.zone) else dns.name
        code, out = self._run_kctl(["kctl-cloudflare", "records", "list", "--zone", dns.zone])
        if code == 0 and fqdn in out:
            self._record_phase("dns", "skipped", f"Record {dns.name} already exists")
            return

        # Create the record
        code, out = self._run_kctl(
            [
                "kctl-cloudflare",
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
                "dns", self._action("created"), self._msg(f"Create {dns.type} record {dns.name} → {dns.content}")
            )
        else:
            self._record_phase("dns", "failed", f"Failed to create DNS record: {out}")

    # ------------------------------------------------------------------
    # Phase 2 — Database
    # ------------------------------------------------------------------

    def phase_database(self) -> None:
        """Ensure the PostgreSQL role and database exist."""
        db = self.manifest.database
        if not db.name or not db.user:
            self._record_phase("database", "skipped", "No database config specified")
            return

        # --- role ---
        users: list | dict = self._run_kctl_json(
            ["kctl-pg", "users", "list", "--host", db.host, "--port", str(db.port)]
        )
        user_names = {u.get("rolname", "") for u in (users if isinstance(users, list) else [])}
        user_created = False
        if db.user not in user_names:
            code, out = self._run_kctl(
                ["kctl-pg", "users", "create", "--host", db.host, "--port", str(db.port), "--name", db.user]
            )
            user_created = code == 0

        # --- database ---
        dbs: list | dict = self._run_kctl_json(["kctl-pg", "db", "list", "--host", db.host, "--port", str(db.port)])
        db_names = {d.get("datname", "") for d in (dbs if isinstance(dbs, list) else [])}
        db_created = False
        if db.name not in db_names:
            code, out = self._run_kctl(
                [
                    "kctl-pg",
                    "db",
                    "create",
                    "--host",
                    db.host,
                    "--port",
                    str(db.port),
                    "--name",
                    db.name,
                    "--owner",
                    db.user,
                ]
            )
            db_created = code == 0

        if user_created or db_created:
            self._record_phase(
                "database", self._action("created"), self._msg(f"Provision role={db.user}, db={db.name}")
            )
        else:
            self._record_phase("database", "skipped", f"Role and database already exist: {db.user}/{db.name}")

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

        # Search environments[].compose[] for existing compose by name
        existing_composes: list[dict[str, Any]] = []
        default_environment_id: str = ""
        for env in (project_data or {}).get("environments", []):
            if env.get("isDefault"):
                default_environment_id = env.get("environmentId", "")
            for comp in env.get("compose", []):
                existing_composes.append(comp)

        # Check if compose already exists
        for comp in existing_composes:
            if comp.get("name") == instance_name:
                self._compose_id = comp["composeId"]
                github_id = comp.get("githubId", "")
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
                self._record_phase("compose", "updated", f"Updated compose {instance_name} (id={self._compose_id})")
                return

        # Create new compose using positional environment_id
        create_args = ["kctl-dokploy", "compose", "create", default_environment_id, "--name", instance_name]
        code, out = self._run_kctl(create_args)

        # Parse the returned compose ID
        new_compose_id = ""
        if code == 0 and out:
            try:
                resp = json.loads(out)
                new_compose_id = resp.get("composeId", "")
            except json.JSONDecodeError:
                pass

        if new_compose_id:
            self._compose_id = new_compose_id
            # Update with GitHub source using --id flag
            self._run_kctl(
                [
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
            )
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
        """Push merged env_defaults to the compose service."""
        if not self._compose_id:
            self._record_phase("environment", "skipped", "No compose_id set — skipping env push")
            return

        env = {**self.manifest.env_defaults, **self.manifest.env_overrides}
        if not env:
            self._record_phase("environment", "skipped", "No environment variables to push")
            return

        env_content = "\n".join(f"{k}={v}" for k, v in env.items())

        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as tmp:
            tmp.write(env_content)
            tmp_path = tmp.name

        code, out = self._run_kctl(["kctl-dokploy", "env", "push", "--", self._compose_id, "--file", tmp_path])
        if code == 0:
            self._record_phase("environment", "updated", f"Pushed {len(env)} env vars to {self._compose_id}")
        else:
            self._record_phase("environment", "failed", f"Failed to push env vars: {out}")

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
        code, out = self._run_kctl(
            [
                "kctl-dokploy",
                "domains",
                "create",
                "--",
                self._compose_id,
                "--host",
                domain.host,
                "--port",
                str(domain.port),
                "--service",
                domain.service,
                https_flag,
            ]
        )
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
        """Trigger a redeploy of the compose service."""
        if not self._compose_id:
            if self.dry_run:
                self._record_phase("deploy", "would-updated", "[dry-run] Would redeploy")
            else:
                self._record_phase("deploy", "failed", "No compose_id set — cannot redeploy")
            return

        code, out = self._run_kctl(["kctl-dokploy", "compose", "redeploy", "--", self._compose_id])
        if code == 0:
            self._record_phase("deploy", self._action("updated"), self._msg(f"Redeploy compose {self._compose_id}"))
        else:
            self._record_phase("deploy", "failed", f"Redeploy failed: {out}")

    # ------------------------------------------------------------------
    # Phase 8 — Verify (healthcheck)
    # ------------------------------------------------------------------

    def phase_verify(self) -> None:
        """Poll the healthcheck URL until it responds or times out."""
        if self.dry_run:
            domain = self.manifest.domain
            host = domain.host or "localhost"
            self._record_phase("verify", "would-verify", f"[dry-run] Would poll https://{host}")
            return

        hc = self.manifest.healthcheck
        domain = self.manifest.domain

        host = domain.host or "localhost"
        scheme = "https" if domain.https else "http"
        url = f"{scheme}://{host}:{hc.port}{hc.path}"

        deadline = time.monotonic() + hc.timeout
        last_error: str = ""

        while time.monotonic() < deadline:
            try:
                resp = httpx.get(url, timeout=5.0)
                if resp.status_code == hc.expected_status:
                    self._record_phase("verify", "updated", f"Healthcheck passed: {url} → {resp.status_code}")
                    return
                last_error = f"unexpected status {resp.status_code}"
            except Exception as exc:
                last_error = str(exc)
            time.sleep(hc.interval)

        self._record_phase("verify", "failed", f"Healthcheck timed out after {hc.timeout}s: {last_error}")

    # ------------------------------------------------------------------
    # Phase 9 — Backup
    # ------------------------------------------------------------------

    def phase_backup(self) -> None:
        """Ensure a backup job is configured for the compose service."""
        backup = self.manifest.backup
        if backup is None:
            self._record_phase("backup", "skipped", "No backup config specified")
            return

        if not self._compose_id:
            self._record_phase("backup", "skipped", "No compose_id — skipping backup setup")
            return

        existing: list | dict = self._run_kctl_json(["kctl-dokploy", "backups", "list", "--", self._compose_id])
        if isinstance(existing, list) and existing:
            self._record_phase("backup", "skipped", "Backup job already configured")
            return

        code, out = self._run_kctl(
            [
                "kctl-dokploy",
                "backups",
                "create",
                "--",
                self._compose_id,
                "--destination",
                backup.destination,
                "--type",
                backup.type,
                "--schedule",
                backup.schedule,
                "--prefix",
                backup.prefix_template,
                "--keep-latest",
                str(backup.keep_latest),
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

        list_cmd = ["kctl-dokploy", "schedules", "list"]
        if self._compose_id:
            list_cmd += ["--", self._compose_id]
        existing: list | dict = self._run_kctl_json(list_cmd)
        existing_names = {s.get("name", "") for s in (existing if isinstance(existing, list) else [])}

        created: list[str] = []
        failed: list[str] = []

        for sched in schedules:
            if sched.name in existing_names:
                continue
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
                "--service",
                sched.service,
                "--shell",
                sched.shell,
                "--timezone",
                sched.timezone,
            ]
            if self._compose_id:
                create_cmd += ["--", self._compose_id]
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
    # Phase 11 — Post-deploy
    # ------------------------------------------------------------------

    def phase_post_deploy(self) -> None:
        """Run post-deployment actions (e.g. Odoo bundle install)."""
        pd = self.manifest.post_deploy
        if not pd.odoo_profile:
            self._record_phase("post_deploy", "skipped", "No post-deploy actions configured")
            return

        code, out = self._run_kctl(["kctl-odoo", "bundles", "install", "--profile", pd.odoo_profile])
        if code == 0:
            self._record_phase(
                "post_deploy", self._action("updated"), self._msg(f"Install Odoo bundles via profile {pd.odoo_profile}")
            )
        else:
            self._record_phase("post_deploy", "failed", f"Odoo bundle install failed: {out}")

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------

    def run_all(self) -> list[PhaseResult]:
        """Execute all 12 phases in order and return the accumulated results."""
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
