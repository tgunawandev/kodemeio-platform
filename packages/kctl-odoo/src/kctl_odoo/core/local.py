"""Local Docker Compose client for development operations.

Delegates to docker compose exec to run bin/ scripts inside the Odoo container,
providing the same operations as ./run but from kctl-odoo.
"""

from __future__ import annotations

import contextlib
import subprocess
from pathlib import Path


class LocalClient:
    """Execute Odoo operations via Docker Compose."""

    def __init__(
        self,
        project_dir: Path | None = None,
        service: str = "odoo",
    ):
        self._service = service
        self._project_dir = project_dir or _find_project_dir()

    @property
    def project_dir(self) -> Path:
        return self._project_dir

    @property
    def service(self) -> str:
        """Container service name."""
        return self._service

    def compose_cmd(self) -> list[str]:
        """Base docker compose command."""
        return ["docker", "compose", "-f", str(self._project_dir / "docker-compose.yml")]

    # Keep backward compat alias
    _compose_cmd = compose_cmd

    def compose(self, *args: str, capture: bool = False) -> subprocess.CompletedProcess:
        """Run a docker compose command."""
        cmd = self._compose_cmd() + list(args)
        if capture:
            return subprocess.run(cmd, capture_output=True, text=True, cwd=str(self._project_dir))
        return subprocess.run(cmd, cwd=str(self._project_dir))

    def exec(self, *args: str, interactive: bool = False, capture: bool = False) -> subprocess.CompletedProcess:
        """Run a command inside the Odoo container."""
        cmd = self._compose_cmd() + ["exec"]
        if not interactive:
            cmd.append("-T")
        cmd.append(self._service)
        cmd.extend(args)
        if capture:
            return subprocess.run(cmd, capture_output=True, text=True, cwd=str(self._project_dir))
        return subprocess.run(cmd, cwd=str(self._project_dir))

    # ========================================================================
    # Module operations (delegates to bin/mod)
    # ========================================================================

    def mod_install(self, modules: list[str]) -> subprocess.CompletedProcess:
        """Install modules via bin/mod install."""
        return self.exec("mod", "install", ",".join(modules))

    def mod_install_bundle(self, bundle_file: str, groups: str | None = None) -> subprocess.CompletedProcess:
        """Install from a bundle YAML file."""
        args = ["mod", "install", "-f", bundle_file]
        if groups:
            args.extend(["-g", groups])
        return self.exec(*args)

    def mod_update(self, modules: list[str]) -> subprocess.CompletedProcess:
        """Update modules via bin/mod update."""
        return self.exec("mod", "update", ",".join(modules))

    def mod_list(self, installed_only: bool = False) -> subprocess.CompletedProcess:
        """List modules."""
        args = ["mod", "list"]
        if installed_only:
            args.append("--installed")
        return self.exec(*args, capture=True)

    # ========================================================================
    # Database operations (delegates to bin/db)
    # ========================================================================

    def db_create(self, name: str, modules: str = "base") -> subprocess.CompletedProcess:
        return self.exec("db", "create", name, modules)

    def db_drop(self, name: str, yes: bool = False) -> subprocess.CompletedProcess:
        args = ["db", "drop", name]
        if yes:
            args.append("-y")
        return self.exec(*args)

    def db_list(self) -> subprocess.CompletedProcess:
        return self.exec("db", "list", capture=True)

    def db_backup(self, name: str, output: str | None = None) -> subprocess.CompletedProcess:
        args = ["db", "backup", name]
        if output:
            args.append(output)
        return self.exec(*args)

    def db_restore(self, name: str, file: str) -> subprocess.CompletedProcess:
        return self.exec("db", "restore", name, file)

    # ========================================================================
    # Testing (delegates to bin/test)
    # ========================================================================

    def test(self, module: str, tags: str = "", database: str = "", clean: bool = False) -> subprocess.CompletedProcess:
        """Run tests for a module."""
        args = ["test", module]
        if tags:
            args.extend(["--tags", tags])
        if database:
            args.extend(["-d", database])
        if clean:
            args.append("--clean")
        return self.exec(*args)

    # ========================================================================
    # Shell
    # ========================================================================

    def shell(self, database: str = "") -> None:
        """Open interactive Odoo shell."""
        args = ["shell"]
        if database:
            args.append(database)
        self.exec(*args, interactive=True)

    # ========================================================================
    # Docker Compose lifecycle
    # ========================================================================

    def up(self, tunnel: bool = False, debug: bool = False, cron: bool = False) -> subprocess.CompletedProcess:
        """Start the development environment."""
        args = ["up", "-d"]
        profiles = []
        if tunnel:
            profiles.extend(["--profile", "tunnel"])
        if debug:
            profiles.extend(["--profile", "debug"])
        if cron:
            profiles.extend(["--profile", "cron"])
        return self.compose(*profiles, *args)

    def down(self) -> subprocess.CompletedProcess:
        return self.compose("down")

    def restart(self, service: str | None = None) -> subprocess.CompletedProcess:
        args = ["restart"]
        if service:
            args.append(service)
        return self.compose(*args)

    def logs(self, follow: bool = False, lines: int = 100, service: str | None = None) -> None:
        """Stream container logs (interactive, writes to stdout)."""
        args = ["logs", f"--tail={lines}"]
        if follow:
            args.append("-f")
        if service:
            args.append(service)
        cmd = self._compose_cmd() + args
        with contextlib.suppress(KeyboardInterrupt):
            subprocess.run(cmd, cwd=str(self._project_dir))

    def status(self) -> subprocess.CompletedProcess:
        return self.compose("ps", "--format", "table {{.Name}}\t{{.Status}}\t{{.Ports}}", capture=True)

    def build(self, no_cache: bool = False) -> subprocess.CompletedProcess:
        args = ["build"]
        if no_cache:
            args.append("--no-cache")
        return self.compose(*args)

    # ========================================================================
    # Asset / Cache management
    # ========================================================================

    def clear_assets(self, database: str = "") -> subprocess.CompletedProcess:
        """Delete compiled asset bundles from ir_attachment."""
        db = database or self._default_database()
        return self.exec(
            "psql",
            "-U",
            "odoo",
            "-d",
            db,
            "-c",
            "DELETE FROM ir_attachment WHERE name LIKE '%assets%';",
            capture=True,
        )

    def _default_database(self) -> str:
        """Read default database from .env file."""
        env_file = self._project_dir / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("PGDATABASE="):
                    return line.split("=", 1)[1].strip()
        return "odoo"

    def is_running(self) -> bool:
        """Check if the Odoo service is running."""
        result = self.compose("ps", "--filter", f"name={self._service}", "--format", "{{.State}}", capture=True)
        return "running" in (result.stdout or "").lower()

    def safe_update(self, modules: list[str], database: str = "", restart: bool = True) -> subprocess.CompletedProcess:
        """Stop Odoo service, update modules, restart.

        Stops only the Odoo service (not DB) to avoid SerializationFailure
        from concurrent access during module update.
        """
        was_running = self.is_running()
        if was_running:
            self.compose("stop", self._service)

        args = ["mod", "update", ",".join(modules)]
        if database:
            args.extend(["--database", database])
        result = self.exec(*args)

        if was_running and restart:
            self.compose("start", self._service)

        return result

    # ========================================================================
    # Aggregate and link
    # ========================================================================

    def aggregate(self) -> subprocess.CompletedProcess:
        return self.exec("aggregate")

    def link_addons(self) -> subprocess.CompletedProcess:
        return self.exec("link-addons")


def _find_project_dir() -> Path:
    """Find the project directory by looking for docker-compose.yml.

    Falls back to config profile ``project_root`` if CWD walk fails.
    """
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / "docker-compose.yml").exists():
            return parent

    # Config profile fallback
    try:
        from kctl_odoo.core.config import get_project_root_from_config

        config_root = get_project_root_from_config()
        if config_root is not None and (config_root / "docker-compose.yml").exists():
            return config_root
    except Exception:
        pass

    return cwd
