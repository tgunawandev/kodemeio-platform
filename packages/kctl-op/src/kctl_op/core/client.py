"""1Password CLI (op) client wrapper.

Unlike other kctl-* CLIs that use httpx, this wraps the `op` binary
via subprocess. All 1Password operations go through the op CLI.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections import OrderedDict
from pathlib import Path

from kctl_op.core.diff import DiffResult

# Reuse models from the absorbed library (now in kctl_op.core)
from kctl_op.core.discovery import (
    EnvFile,
    get_environment_name,
    get_project_name,
)
from kctl_op.core.sync import (
    get_sync_status,
    pull_env_file,
    push_env_file,
)

from kctl_op.core.exceptions import (
    AuthenticationError,
    ConnectionError,
    OpCliError,
    VaultError,
)

# Default exclusion patterns
DEFAULT_EXCLUDE_PATTERNS = [
    "**/.env.example",
    "**/.env.*.example",
    "**/*.env.example",
    "**/.env.tmp",
    "**/node_modules/**",
    "**/archived/**",
    "**/.venv/**",
    "**/venv/**",
    "**/__pycache__/**",
    "kodemeio-op/**",
]


class OnePasswordClient:
    """Wraps the 1Password CLI binary (op) for vault operations."""

    def __init__(self, vault: str, token: str):
        self.vault = vault
        self.token = token
        # Set env var so op CLI can authenticate
        if token:
            os.environ["OP_SERVICE_ACCOUNT_TOKEN"] = token

    # ------------------------------------------------------------------
    # Low-level op CLI execution
    # ------------------------------------------------------------------

    def _run(
        self,
        args: list[str],
        *,
        expect_json: bool = True,
        check: bool = True,
    ) -> dict | list | str:
        """Run an op command and return parsed output."""
        cmd = ["op"] + args
        if expect_json and "--format" not in args:
            cmd += ["--format", "json"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except FileNotFoundError as err:
            raise ConnectionError(
                Exception("1Password CLI (op) is not installed. Install with: bin/install-op-cli")
            ) from err
        except subprocess.TimeoutExpired as err:
            raise ConnectionError(Exception("op command timed out after 60s")) from err

        if check and result.returncode != 0:
            stderr = result.stderr.strip()
            if "not signed in" in stderr.lower() or "authorization" in stderr.lower():
                raise AuthenticationError(
                    f"Not authenticated. Set OP_SERVICE_ACCOUNT_TOKEN or run: op signin\n{stderr}"
                )
            raise OpCliError(args[0] if args else "unknown", result.returncode, stderr)

        if not expect_json:
            return result.stdout.strip()

        stdout = result.stdout.strip()
        if not stdout:
            return {}
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return stdout

    # ------------------------------------------------------------------
    # Authentication & health
    # ------------------------------------------------------------------

    def whoami(self) -> dict:
        """Check authentication status. Returns account info."""
        return self._run(["whoami"])

    def is_authenticated(self) -> bool:
        """Check if op CLI is authenticated."""
        try:
            self.whoami()
            return True
        except (AuthenticationError, ConnectionError, OpCliError):
            return False

    def is_installed(self) -> bool:
        """Check if op CLI is installed."""
        try:
            subprocess.run(
                ["op", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def get_version(self) -> str:
        """Get op CLI version."""
        try:
            result = subprocess.run(
                ["op", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return "unknown"

    # ------------------------------------------------------------------
    # Vault operations
    # ------------------------------------------------------------------

    def vault_info(self) -> dict:
        """Get vault details."""
        try:
            return self._run(["vault", "get", self.vault])
        except OpCliError as e:
            raise VaultError(self.vault, str(e)) from e

    def vault_exists(self) -> bool:
        """Check if vault is accessible."""
        try:
            self.vault_info()
            return True
        except (VaultError, OpCliError):
            return False

    def create_vault(self, name: str | None = None, description: str = "") -> dict:
        """Create a new vault."""
        vault_name = name or self.vault
        args = ["vault", "create", vault_name]
        if description:
            args += ["--description", description]
        return self._run(args)

    # ------------------------------------------------------------------
    # Item operations
    # ------------------------------------------------------------------

    def list_items(self) -> list[dict]:
        """List all items in the vault."""
        return self._run(["item", "list", "--vault", self.vault])

    def get_item(self, title: str) -> dict:
        """Get a specific item by title (raw JSON)."""
        return self._run(["item", "get", title, "--vault", self.vault])

    def get_item_fields(self, title: str) -> OrderedDict:
        """Get item fields as an OrderedDict (key=value pairs)."""
        item = self.get_item(title)
        fields = OrderedDict()
        for field in item.get("fields", []):
            label = field.get("label", "")
            value = field.get("value", "")
            # Skip internal 1Password fields
            if (
                label
                and field.get("section", {}).get("id") != "add more"
                and field.get("type") in ("CONCEALED", "STRING")
                and label != "notesPlain"
            ):
                fields[label] = value
        return fields

    def item_exists(self, title: str) -> bool:
        """Check if an item exists in the vault."""
        try:
            self._run(["item", "get", title, "--vault", self.vault])
            return True
        except OpCliError:
            return False

    def create_item(
        self,
        title: str,
        fields: dict[str, str],
        tags: list[str] | None = None,
        notes: str = "",
    ) -> dict:
        """Create a new Secure Note with password-type fields."""
        args = [
            "item",
            "create",
            "--category",
            "Secure Note",
            "--vault",
            self.vault,
            "--title",
            title,
        ]
        if tags:
            args += ["--tags", ",".join(tags)]
        if notes:
            args += [f"notesPlain={notes}"]
        for key, value in fields.items():
            args.append(f"{key}[password]={value}")
        return self._run(args)

    def update_item(
        self,
        title: str,
        fields: dict[str, str],
        tags: list[str] | None = None,
        notes: str = "",
    ) -> dict:
        """Update an item (delete + recreate for clean field state)."""
        self.delete_item(title)
        return self.create_item(title, fields, tags, notes)

    def delete_item(self, title: str) -> None:
        """Delete an item from the vault."""
        self._run(
            ["item", "delete", title, "--vault", self.vault],
            expect_json=False,
        )

    # ------------------------------------------------------------------
    # Discovery (uses profile scan_roots)
    # ------------------------------------------------------------------

    def discover_files(
        self,
        scan_roots: list[str],
        exclude_patterns: list[str] | None = None,
        env_mappings: dict[str, str] | None = None,
        custom_env_pattern: str = "",
    ) -> list[EnvFile]:
        """Discover .env files across scan_roots.

        Reuses EnvFile and helpers from kctl_op.core.discovery
        but uses profile config instead of Config class.
        """
        from fnmatch import fnmatch

        excl = exclude_patterns or DEFAULT_EXCLUDE_PATTERNS

        # Build a config-like object for get_environment_name
        class _ConfigShim:
            pass

        cfg_shim = _ConfigShim()
        cfg_shim.env_mappings = env_mappings or {}
        cfg_shim.custom_env_pattern = custom_env_pattern or r"\.env\.(?P<prefix>[a-z]+)\.(?P<env>[a-z]+)"

        all_files: list[EnvFile] = []
        for root_str in scan_roots:
            root = Path(root_str).expanduser().resolve()
            if not root.exists():
                continue

            for env_path in sorted(root.rglob(".env*")):
                if not env_path.is_file():
                    continue
                if "example" in env_path.name.lower():
                    continue
                if env_path.name.endswith(".tmp"):
                    continue
                if env_path.name.endswith(".bak"):
                    continue

                # Check exclusion patterns
                rel = str(env_path.relative_to(root))
                excluded = False
                for pattern in excl:
                    if fnmatch(rel, pattern) or fnmatch(env_path.name, pattern):
                        excluded = True
                        break
                if excluded:
                    continue

                # Build EnvFile
                project = get_project_name(env_path, root)
                environment = get_environment_name(env_path.name, cfg_shim)
                all_files.append(
                    EnvFile(
                        path=env_path,
                        project=project,
                        environment=environment,
                        scan_root=root,
                    )
                )

        # Sort by project, then environment
        all_files.sort(key=lambda f: (f.project, f.environment))
        return all_files

    # ------------------------------------------------------------------
    # Sync operations (delegates to existing sync module)
    # ------------------------------------------------------------------

    def push_file(
        self,
        env_file: EnvFile,
        dry_run: bool = False,
        force: bool = False,
    ) -> tuple[bool, str, DiffResult | None]:
        """Push a single .env file to 1Password."""
        return push_env_file(env_file, self.vault, dry_run=dry_run, force=force)

    def pull_file(
        self,
        env_file: EnvFile,
        dry_run: bool = False,
        force: bool = False,
        backup: bool = True,
    ) -> tuple[bool, str, DiffResult | None]:
        """Pull a single .env file from 1Password."""
        return pull_env_file(env_file, self.vault, dry_run=dry_run, force=force, backup=backup)

    def file_status(self, env_file: EnvFile) -> dict:
        """Get sync status for a single file."""
        return get_sync_status(env_file, self.vault)

    def push_all(
        self,
        scan_roots: list[str],
        exclude_patterns: list[str] | None = None,
        env_mappings: dict[str, str] | None = None,
        custom_env_pattern: str = "",
        dry_run: bool = False,
        force: bool = False,
    ) -> list[tuple[EnvFile, bool, str]]:
        """Push all discovered .env files."""
        files = self.discover_files(scan_roots, exclude_patterns, env_mappings, custom_env_pattern)
        results = []
        for env_file in files:
            ok, msg, _ = self.push_file(env_file, dry_run=dry_run, force=force)
            results.append((env_file, ok, msg))
        return results

    def pull_all(
        self,
        scan_roots: list[str],
        exclude_patterns: list[str] | None = None,
        env_mappings: dict[str, str] | None = None,
        custom_env_pattern: str = "",
        dry_run: bool = False,
        force: bool = False,
        backup: bool = True,
    ) -> list[tuple[EnvFile, bool, str]]:
        """Pull all discovered .env files."""
        files = self.discover_files(scan_roots, exclude_patterns, env_mappings, custom_env_pattern)
        results = []
        for env_file in files:
            ok, msg, _ = self.pull_file(env_file, dry_run=dry_run, force=force, backup=backup)
            results.append((env_file, ok, msg))
        return results
