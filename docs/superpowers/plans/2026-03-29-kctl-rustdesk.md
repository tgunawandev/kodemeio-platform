# kctl-rustdesk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a Python CLI tool (`kctl-rustdesk`) for managing RustDesk server infrastructure, supporting both local and SSH-based remote execution against production.

**Architecture:** No HTTP API — RustDesk community edition exposes no REST API. All operations go through `docker exec` (compose) and `sqlite3` queries inside the hbbs container. A `RustDeskExecutor` class wraps local or SSH-tunneled command execution. Profile config stores connection details (host, ssh_user, compose_file, etc.).

**Tech Stack:** Python 3.12+, typer, rich, pydantic, pyyaml, kctl-lib>=0.3.0

**Package location:** `packages/kctl-rustdesk/` inside the kodemeio-platform monorepo.

---

## File Structure

```
packages/kctl-rustdesk/
├── pyproject.toml
├── src/kctl_rustdesk/
│   ├── __init__.py                 # Version string
│   ├── __main__.py                 # python -m entry point
│   ├── cli.py                      # Main Typer app, global options, command registration
│   ├── core/
│   │   ├── __init__.py
│   │   ├── callbacks.py            # AppContext(AppContextBase) with lazy executor
│   │   ├── executor.py             # RustDeskExecutor: docker exec, sqlite3, SSH transport
│   │   ├── config.py               # ServiceConfig, resolve_connection, SERVICE_KEY="rustdesk"
│   │   └── plugins.py              # Plugin discovery (entry point group)
│   └── commands/
│       ├── __init__.py
│       ├── config_cmd.py           # init, show, profiles, use, test
│       ├── health.py               # check (containers, ports, keys, db)
│       ├── dashboard.py            # show (services, resources, config, stats)
│       ├── peers.py                # list, get, count, search, export
│       ├── users.py                # list, get, count, groups, export
│       ├── audit.py                # connections, logins, stats, active
│       ├── backup.py               # create, list, restore, clean
│       ├── setup.py                # status, get-key, client-config, firewall
│       └── maintenance.py          # status, version, logs, db-optimize, db-stats, cleanup
└── tests/
    ├── __init__.py
    └── conftest.py                 # Shared fixtures
```

---

### Task 1: Project scaffold — pyproject.toml, __init__, __main__, empty cli.py

**Files:**
- Create: `packages/kctl-rustdesk/pyproject.toml`
- Create: `packages/kctl-rustdesk/src/kctl_rustdesk/__init__.py`
- Create: `packages/kctl-rustdesk/src/kctl_rustdesk/__main__.py`
- Create: `packages/kctl-rustdesk/src/kctl_rustdesk/cli.py`
- Create: `packages/kctl-rustdesk/tests/__init__.py`
- Create: `packages/kctl-rustdesk/tests/conftest.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "kctl-rustdesk"
version = "0.1.0"
description = "Kodemeio RustDesk CLI — manage RustDesk server infrastructure"
requires-python = ">=3.12"
dependencies = [
    "kctl-lib>=0.3.0",
    "typer>=0.15.0",
    "rich>=13.9.0",
    "pydantic>=2.10.0",
    "pyyaml>=6.0.2",
]

[project.scripts]
kctl-rustdesk = "kctl_rustdesk.cli:_run"

[project.entry-points."kctl_rustdesk.plugins"]

[tool.hatch.build.targets.wheel]
packages = ["src/kctl_rustdesk"]

[tool.ruff]
target-version = "py312"
line-length = 120

[tool.mypy]
python_version = "3.12"
strict = true
```

- [ ] **Step 2: Create __init__.py**

```python
"""kctl-rustdesk: Kodemeio RustDesk server management CLI."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Create __main__.py**

```python
from kctl_rustdesk.cli import _run

_run()
```

- [ ] **Step 4: Create minimal cli.py (will be expanded in Task 14)**

```python
"""kctl-rustdesk CLI entry point."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_lib import handle_cli_error
from kctl_lib.exceptions import KctlError

from kctl_rustdesk import __version__

def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-rustdesk {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-rustdesk",
    help="Kodemeio RustDesk CLI — manage RustDesk server infrastructure.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


@app.callback()
def main(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress info messages")] = False,
    profile: Annotated[str | None, typer.Option("--profile", "-p", help="Config profile")] = None,
    format: Annotated[str, typer.Option("--format", "-f", help="Output format")] = "pretty",
    no_header: Annotated[bool, typer.Option("--no-header", help="Omit column headers")] = False,
    host: Annotated[str | None, typer.Option("--host", help="Server host override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True)
    ] = False,
) -> None:
    """Manage RustDesk server infrastructure."""
    from kctl_rustdesk.core.callbacks import AppContext

    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        format=format,
        no_header=no_header,
        host_override=host,
    )


def _run() -> None:
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
```

- [ ] **Step 5: Create test scaffolding**

`tests/__init__.py`: empty file.

`tests/conftest.py`:
```python
"""Shared test fixtures for kctl-rustdesk."""
```

- [ ] **Step 6: Commit scaffold**

```bash
git add packages/kctl-rustdesk/
git commit -m "feat(kctl-rustdesk): scaffold project with pyproject.toml and entry point"
```

---

### Task 2: Core — config.py (ServiceConfig + profile resolution)

**Files:**
- Create: `packages/kctl-rustdesk/src/kctl_rustdesk/core/__init__.py`
- Create: `packages/kctl-rustdesk/src/kctl_rustdesk/core/config.py`

- [ ] **Step 1: Create core/__init__.py**

Empty file.

- [ ] **Step 2: Create core/config.py**

```python
"""RustDesk service configuration and profile resolution."""

from __future__ import annotations

import os

from pydantic import BaseModel

from kctl_lib.config import (
    CONFIG_FILE,
    get_default_profile,
    get_profile_names,
    get_service_config as _get_service_config,
    resolve_active_profile_name as _resolve_active_profile_name,
    set_default_profile,
    set_service_config as _set_service_config,
)

SERVICE_KEY = "rustdesk"
ENV_PREFIX = "KCTL_RUSTDESK"


class ServiceConfig(BaseModel):
    """RustDesk service config within a profile."""

    host: str = "localhost"
    ssh_user: str = "root"
    compose_file: str = "/opt/kodemeio-rustdesk/docker-compose.prod.yml"
    env_file: str = "/opt/kodemeio-rustdesk/.env.prod"
    project_name: str = "kodemeio-rustdesk"
    domain: str = "rustdesk.kodeme.io"


def get_rustdesk_config(profile_name: str) -> ServiceConfig:
    """Load RustDesk config from a profile."""
    raw = _get_service_config(
        profile_name,
        SERVICE_KEY,
        valid_fields=list(ServiceConfig.model_fields),
    )
    return ServiceConfig(**raw) if raw else ServiceConfig()


def set_rustdesk_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Save RustDesk config to a profile."""
    svc_data = {k: v for k, v in svc_config.model_dump().items() if v}
    _set_service_config(profile_name, SERVICE_KEY, svc_data)


def resolve_active_profile(profile_name: str | None = None) -> str:
    """Resolve active profile: explicit > env > default."""
    return _resolve_active_profile_name(profile_name, ENV_PREFIX)


def resolve_connection(
    profile_name: str | None = None,
    host_override: str | None = None,
) -> ServiceConfig:
    """Resolve full connection config with overrides."""
    pname = resolve_active_profile(profile_name)
    svc = get_rustdesk_config(pname)

    # Environment variable overrides
    if env_host := os.environ.get(f"{ENV_PREFIX}_HOST"):
        svc = svc.model_copy(update={"host": env_host})
    if env_user := os.environ.get(f"{ENV_PREFIX}_SSH_USER"):
        svc = svc.model_copy(update={"ssh_user": env_user})

    # Explicit override (highest priority)
    if host_override:
        svc = svc.model_copy(update={"host": host_override})

    return svc
```

- [ ] **Step 3: Commit**

```bash
git add packages/kctl-rustdesk/src/kctl_rustdesk/core/
git commit -m "feat(kctl-rustdesk): add ServiceConfig and profile resolution"
```

---

### Task 3: Core — executor.py (RustDeskExecutor with local/SSH transport)

**Files:**
- Create: `packages/kctl-rustdesk/src/kctl_rustdesk/core/executor.py`

- [ ] **Step 1: Create core/executor.py**

```python
"""RustDesk server executor — runs commands locally or via SSH."""

from __future__ import annotations

import csv
import json
import shlex
from io import StringIO

from kctl_lib.exceptions import CommandError, DockerError
from kctl_lib.runner import run, run_quiet

from kctl_rustdesk.core.config import ServiceConfig


class RustDeskExecutor:
    """Execute commands on RustDesk server (local or remote via SSH)."""

    DB_PATH = "/root/db_v2.sqlite3"
    KEY_PUB_PATH = "/root/id_ed25519.pub"
    KEY_PRIV_PATH = "/root/id_ed25519"

    def __init__(self, config: ServiceConfig) -> None:
        self.config = config
        self.is_remote = config.host not in ("localhost", "127.0.0.1", "")
        self.hbbs_container = f"{config.project_name}-hbbs-1"
        self.hbbr_container = f"{config.project_name}-hbbr-1"

    def _wrap_ssh(self, cmd: list[str]) -> list[str]:
        """Wrap a command in SSH if targeting a remote host."""
        if not self.is_remote:
            return cmd
        remote_cmd = shlex.join(cmd)
        return [
            "ssh", "-o", "StrictHostKeyChecking=accept-new",
            f"{self.config.ssh_user}@{self.config.host}",
            remote_cmd,
        ]

    def shell(self, cmd: list[str], check: bool = True, timeout: int = 30) -> str:
        """Run a shell command on the server."""
        wrapped = self._wrap_ssh(cmd)
        if check:
            result = run(wrapped, timeout=timeout)
        else:
            result = run_quiet(wrapped, timeout=timeout)
        return result.stdout.strip()

    def _dc_cmd(self) -> list[str]:
        """Base docker compose command."""
        return [
            "docker", "compose",
            "-f", self.config.compose_file,
            "-p", self.config.project_name,
        ]

    def docker_exec(self, container: str, cmd: list[str], check: bool = True) -> str:
        """Execute a command inside a container."""
        full_cmd = [*self._dc_cmd(), "exec", "-T", container, *cmd]
        return self.shell(full_cmd, check=check)

    def exec_hbbs(self, cmd: list[str], check: bool = True) -> str:
        """Execute a command in the hbbs container."""
        return self.docker_exec("hbbs", cmd, check=check)

    def exec_hbbr(self, cmd: list[str], check: bool = True) -> str:
        """Execute a command in the hbbr container."""
        return self.docker_exec("hbbr", cmd, check=check)

    def container_running(self, service: str) -> bool:
        """Check if a compose service container is running."""
        try:
            output = self.shell(
                [*self._dc_cmd(), "ps", "--status", "running", "--format", "{{.Service}}"],
                check=False,
            )
            return service in output.splitlines()
        except (CommandError, DockerError):
            return False

    def docker_ps(self) -> list[dict[str, str]]:
        """Get container status as list of dicts."""
        try:
            output = self.shell([*self._dc_cmd(), "ps", "--format", "json"], check=False)
            if not output:
                return []
            containers: list[dict[str, str]] = []
            for line in output.splitlines():
                try:
                    containers.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return containers
        except (CommandError, DockerError):
            return []

    def docker_logs(self, service: str | None = None, tail: int = 100) -> str:
        """Get container logs."""
        cmd = [*self._dc_cmd(), "logs", "--tail", str(tail), "--no-color"]
        if service:
            cmd.append(service)
        return self.shell(cmd, check=False)

    def query_db(self, sql: str) -> list[dict[str, str]]:
        """Run a SQLite query on hbbs and return rows as list of dicts."""
        output = self.exec_hbbs(
            ["sqlite3", "-header", "-csv", self.DB_PATH, sql],
        )
        if not output.strip():
            return []
        reader = csv.DictReader(StringIO(output))
        return [dict(row) for row in reader]

    def query_db_scalar(self, sql: str) -> str:
        """Run a SQLite query that returns a single value."""
        output = self.exec_hbbs(["sqlite3", self.DB_PATH, sql])
        return output.strip()

    def read_file(self, container: str, path: str) -> str:
        """Read a file from inside a container."""
        return self.docker_exec(container, ["cat", path])

    def file_exists(self, container: str, path: str) -> bool:
        """Check if a file exists in a container."""
        try:
            self.docker_exec(container, ["test", "-f", path])
            return True
        except CommandError:
            return False

    def get_public_key(self) -> str:
        """Get the server's public key."""
        return self.exec_hbbs(["cat", self.KEY_PUB_PATH])

    def get_compose_version(self) -> str:
        """Get docker compose version."""
        return self.shell(["docker", "compose", "version", "--short"], check=False)

    def get_container_stats(self, service: str) -> dict[str, str]:
        """Get CPU/memory stats for a container."""
        output = self.shell(
            ["docker", "stats", "--no-stream", "--format",
             "{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}",
             f"{self.config.project_name}-{service}-1"],
            check=False,
        )
        parts = output.split("\t") if output else []
        return {
            "cpu": parts[0] if len(parts) > 0 else "-",
            "mem_usage": parts[1] if len(parts) > 1 else "-",
            "mem_pct": parts[2] if len(parts) > 2 else "-",
        }
```

- [ ] **Step 2: Commit**

```bash
git add packages/kctl-rustdesk/src/kctl_rustdesk/core/executor.py
git commit -m "feat(kctl-rustdesk): add RustDeskExecutor with local/SSH transport"
```

---

### Task 4: Core — callbacks.py and plugins.py

**Files:**
- Create: `packages/kctl-rustdesk/src/kctl_rustdesk/core/callbacks.py`
- Create: `packages/kctl-rustdesk/src/kctl_rustdesk/core/plugins.py`

- [ ] **Step 1: Create core/callbacks.py**

```python
"""Application context for kctl-rustdesk."""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_lib.callbacks import AppContextBase

from kctl_rustdesk.core.config import resolve_connection
from kctl_rustdesk.core.executor import RustDeskExecutor


@dataclass
class AppContext(AppContextBase):
    """RustDesk CLI context with lazy-loaded executor."""

    host_override: str | None = None
    _executor: RustDeskExecutor | None = field(default=None, repr=False, init=False)

    @property
    def executor(self) -> RustDeskExecutor:
        """Lazy-initialized RustDesk executor."""
        if self._executor is None:
            config = resolve_connection(
                profile_name=self.profile,
                host_override=self.host_override,
            )
            self._executor = RustDeskExecutor(config)
        return self._executor
```

- [ ] **Step 2: Create core/plugins.py**

```python
"""Plugin discovery for kctl-rustdesk."""

from __future__ import annotations

import importlib.metadata
import logging
from typing import Protocol

import typer

logger = logging.getLogger(__name__)
ENTRY_POINT_GROUP = "kctl_rustdesk.plugins"


class KctlPlugin(Protocol):
    name: str

    def register(self, app: typer.Typer) -> None: ...


def discover_and_load_plugins(app: typer.Typer) -> list[str]:
    """Discover and load third-party plugins via entry points."""
    loaded: list[str] = []
    try:
        eps = importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
    except Exception:
        return loaded

    for ep in eps:
        try:
            plugin_cls = ep.load()
            plugin = plugin_cls()
            plugin.register(app)
            loaded.append(ep.name)
            logger.debug("Loaded plugin: %s", ep.name)
        except Exception as e:
            logger.warning("Failed to load plugin %s: %s", ep.name, e)

    return loaded
```

- [ ] **Step 3: Commit**

```bash
git add packages/kctl-rustdesk/src/kctl_rustdesk/core/callbacks.py
git add packages/kctl-rustdesk/src/kctl_rustdesk/core/plugins.py
git commit -m "feat(kctl-rustdesk): add AppContext and plugin discovery"
```

---

### Task 5: Command — config_cmd.py (init, show, profiles, use, test)

**Files:**
- Create: `packages/kctl-rustdesk/src/kctl_rustdesk/commands/__init__.py`
- Create: `packages/kctl-rustdesk/src/kctl_rustdesk/commands/config_cmd.py`

- [ ] **Step 1: Create commands/__init__.py**

Empty file.

- [ ] **Step 2: Create commands/config_cmd.py**

```python
"""Configuration management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_lib.config import (
    CONFIG_FILE,
    get_default_profile,
    get_profile_names,
    set_default_profile,
)

from kctl_rustdesk.core.callbacks import AppContext
from kctl_rustdesk.core.config import (
    SERVICE_KEY,
    ServiceConfig,
    get_rustdesk_config,
    resolve_active_profile,
    set_rustdesk_config,
)

app = typer.Typer(help="Manage CLI configuration and profiles.")


@app.command()
def init(
    ctx: typer.Context,
    host: Annotated[str | None, typer.Option("--host", help="Server hostname")] = None,
    ssh_user: Annotated[str | None, typer.Option("--ssh-user", help="SSH username")] = None,
    compose_file: Annotated[str | None, typer.Option("--compose-file")] = None,
    env_file: Annotated[str | None, typer.Option("--env-file")] = None,
    project_name: Annotated[str | None, typer.Option("--project-name")] = None,
    domain: Annotated[str | None, typer.Option("--domain")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Profile name")] = None,
) -> None:
    """Initialize CLI configuration with a new profile."""
    c: AppContext = ctx.obj
    out = c.output

    profile_name = name or typer.prompt("Profile name", default="production")
    h = host or typer.prompt("Server host", default="dokploy.kodeme.io")
    u = ssh_user or typer.prompt("SSH user", default="root")
    cf = compose_file or typer.prompt(
        "Compose file path", default="/opt/kodemeio-rustdesk/docker-compose.prod.yml"
    )
    ef = env_file or typer.prompt(
        "Env file path", default="/opt/kodemeio-rustdesk/.env.prod"
    )
    pn = project_name or typer.prompt(
        "Compose project name", default="kodemeio-rustdesk"
    )
    d = domain or typer.prompt("Domain", default="rustdesk.kodeme.io")

    svc = ServiceConfig(
        host=h, ssh_user=u, compose_file=cf,
        env_file=ef, project_name=pn, domain=d,
    )
    set_rustdesk_config(profile_name, svc)

    if len(get_profile_names()) <= 1:
        set_default_profile(profile_name)

    out.success(f"Profile '{profile_name}' saved to {CONFIG_FILE}")


@app.command()
def show(ctx: typer.Context) -> None:
    """Show current configuration."""
    c: AppContext = ctx.obj
    out = c.output
    default = get_default_profile()
    active = resolve_active_profile(c.profile)

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "General",
            [
                ("Config file", str(CONFIG_FILE)),
                ("Default profile", default),
                ("Active profile", active),
                ("Service key", SERVICE_KEY),
            ],
        ),
    ]

    for pname in get_profile_names():
        marker = " (default)" if pname == default else ""
        svc = get_rustdesk_config(pname)
        sections.append((
            f"Profile: {pname}{marker}",
            [
                ("Host", svc.host),
                ("SSH user", svc.ssh_user),
                ("Compose file", svc.compose_file),
                ("Env file", svc.env_file),
                ("Project name", svc.project_name),
                ("Domain", svc.domain),
            ],
        ))

    out.detail("RustDesk Configuration", sections, data_for_json={
        "config_file": str(CONFIG_FILE),
        "default_profile": default,
        "active_profile": active,
        "profiles": {
            pname: get_rustdesk_config(pname).model_dump()
            for pname in get_profile_names()
        },
    })


@app.command()
def profiles(ctx: typer.Context) -> None:
    """List all profiles."""
    c: AppContext = ctx.obj
    default = get_default_profile()
    rows: list[list[str]] = []
    for pname in get_profile_names():
        svc = get_rustdesk_config(pname)
        is_default = "yes" if pname == default else ""
        rows.append([pname, svc.host, svc.domain, is_default])

    c.output.table(
        "Profiles",
        [("Name", "cyan"), ("Host", ""), ("Domain", ""), ("Default", "green")],
        rows,
    )


@app.command()
def use(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to set as default")],
) -> None:
    """Set the default profile."""
    c: AppContext = ctx.obj
    if name not in get_profile_names():
        c.output.error(f"Profile '{name}' not found")
        raise typer.Exit(1)
    set_default_profile(name)
    c.output.success(f"Default profile set to '{name}'")


@app.command()
def test(ctx: typer.Context) -> None:
    """Test connection to the RustDesk server."""
    c: AppContext = ctx.obj
    out = c.output
    ex = c.executor

    out.info(f"Testing connection to {ex.config.host}...")

    try:
        version = ex.get_compose_version()
        out.success(f"Docker Compose: {version}")
    except Exception as e:
        out.error(f"Cannot reach server: {e}")
        raise typer.Exit(1)

    hbbs_ok = ex.container_running("hbbs")
    hbbr_ok = ex.container_running("hbbr")
    out.success(f"hbbs container: {'running' if hbbs_ok else 'NOT running'}")
    out.success(f"hbbr container: {'running' if hbbr_ok else 'NOT running'}")

    try:
        count = ex.query_db_scalar("SELECT count(*) FROM peer;")
        out.success(f"Database accessible: {count} peers")
    except Exception as e:
        out.warn(f"Database check failed: {e}")
```

- [ ] **Step 3: Commit**

```bash
git add packages/kctl-rustdesk/src/kctl_rustdesk/commands/
git commit -m "feat(kctl-rustdesk): add config command group"
```

---

### Task 6: Command — health.py

**Files:**
- Create: `packages/kctl-rustdesk/src/kctl_rustdesk/commands/health.py`

- [ ] **Step 1: Create commands/health.py**

```python
"""Health check commands."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from kctl_lib.exceptions import CommandError
from kctl_rustdesk.core.callbacks import AppContext
from kctl_rustdesk.core.executor import RustDeskExecutor

app = typer.Typer(help="Health checks for RustDesk server.")


def _run_checks(ex: RustDeskExecutor) -> list[dict[str, str]]:
    """Run all health checks, return list of {name, status, message}."""
    checks: list[dict[str, str]] = []

    for svc in ("hbbs", "hbbr"):
        running = ex.container_running(svc)
        checks.append({
            "name": f"container:{svc}",
            "status": "pass" if running else "fail",
            "message": "running" if running else "not running",
        })

    for path_name, path in [("public key", ex.KEY_PUB_PATH), ("private key", ex.KEY_PRIV_PATH)]:
        exists = ex.file_exists("hbbs", path)
        checks.append({
            "name": f"key:{path_name}",
            "status": "pass" if exists else "fail",
            "message": "exists" if exists else "missing",
        })

    try:
        count = ex.query_db_scalar("SELECT count(*) FROM peer;")
        checks.append({
            "name": "database",
            "status": "pass",
            "message": f"accessible, {count} peers",
        })
    except (CommandError, Exception) as e:
        checks.append({
            "name": "database",
            "status": "fail",
            "message": str(e),
        })

    try:
        output = ex.exec_hbbs(["netstat", "-tlnp"], check=False)
        for port in ("21115", "21116", "21117", "21118"):
            listening = port in output
            checks.append({
                "name": f"port:{port}",
                "status": "pass" if listening else "warn",
                "message": "listening" if listening else "not detected",
            })
    except (CommandError, Exception):
        checks.append({
            "name": "port:check",
            "status": "warn",
            "message": "netstat not available in container",
        })

    return checks


@app.command("check")
def check(
    ctx: typer.Context,
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Run health checks on RustDesk server."""
    c: AppContext = ctx.obj
    out = c.output
    ex = c.executor

    checks = _run_checks(ex)

    if as_json or c.json_mode:
        passed = sum(1 for ch in checks if ch["status"] in ("pass", "warn"))
        total = len(checks)
        score = round(passed / total * 100) if total else 0
        print(json.dumps({"score": score, "checks": checks}, indent=2))
        return

    out.header("RustDesk Health Check")

    passed = 0
    total = len(checks)
    for ch in checks:
        status = ch["status"]
        name = ch["name"]
        message = ch["message"]
        if status == "pass":
            out.text(f"  [green]PASS[/green] {name}: {message}")
            passed += 1
        elif status == "warn":
            out.text(f"  [yellow]WARN[/yellow] {name}: {message}")
            passed += 1
        else:
            out.text(f"  [red]FAIL[/red] {name}: {message}")

    score = round(passed / total * 100) if total else 0
    out.text("")
    if score >= 80:
        out.success(f"Health score: {score}% ({passed}/{total})")
    elif score >= 50:
        out.warn(f"Health score: {score}% ({passed}/{total})")
    else:
        out.error(f"Health score: {score}% ({passed}/{total})")
```

- [ ] **Step 2: Commit**

```bash
git add packages/kctl-rustdesk/src/kctl_rustdesk/commands/health.py
git commit -m "feat(kctl-rustdesk): add health check command"
```

---

### Task 7: Command — peers.py

**Files:**
- Create: `packages/kctl-rustdesk/src/kctl_rustdesk/commands/peers.py`

- [ ] **Step 1: Create commands/peers.py**

```python
"""Peer (device) management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_rustdesk.core.callbacks import AppContext

app = typer.Typer(help="Manage RustDesk peers (devices).")


@app.command("list")
def list_(
    ctx: typer.Context,
    online: Annotated[bool, typer.Option("--online", help="Only online peers")] = False,
) -> None:
    """List all registered peers."""
    c: AppContext = ctx.obj
    ex = c.executor

    if online:
        sql = (
            "SELECT id, uuid, pk, created_at, last_online, note "
            "FROM peer WHERE last_online > datetime('now', '-5 minutes') "
            "ORDER BY last_online DESC;"
        )
    else:
        sql = (
            "SELECT id, uuid, pk, created_at, last_online, note "
            "FROM peer ORDER BY last_online DESC;"
        )

    rows_data = ex.query_db(sql)
    rows = [
        [r.get("id", ""), r.get("uuid", ""), r.get("last_online", ""), r.get("note", "")]
        for r in rows_data
    ]

    c.output.table(
        "Peers" + (" (online)" if online else ""),
        [("ID", "cyan"), ("UUID", "dim"), ("Last Online", ""), ("Note", "")],
        rows,
        data_for_json=rows_data,
    )


@app.command("get")
def get(
    ctx: typer.Context,
    peer_id: Annotated[str, typer.Argument(help="Peer ID")],
) -> None:
    """Get details for a specific peer."""
    c: AppContext = ctx.obj
    ex = c.executor

    rows = ex.query_db(f"SELECT * FROM peer WHERE id = '{peer_id}';")
    if not rows:
        c.output.error(f"Peer not found: {peer_id}")
        raise typer.Exit(1)

    peer = rows[0]
    sections = [("Peer Details", [(k, str(v)) for k, v in peer.items()])]
    c.output.detail(f"Peer: {peer_id}", sections, data_for_json=peer)


@app.command()
def count(ctx: typer.Context) -> None:
    """Count total peers."""
    c: AppContext = ctx.obj
    ex = c.executor

    total = ex.query_db_scalar("SELECT count(*) FROM peer;")
    recent = ex.query_db_scalar(
        "SELECT count(*) FROM peer WHERE last_online > datetime('now', '-5 minutes');"
    )

    sections = [("Peer Count", [("Total", total), ("Online (5m)", recent)])]
    c.output.detail("Peer Count", sections, data_for_json={
        "total": int(total), "online": int(recent),
    })


@app.command()
def search(
    ctx: typer.Context,
    term: Annotated[str, typer.Argument(help="Search term (ID, UUID, or note)")],
) -> None:
    """Search peers by ID, UUID, or note."""
    c: AppContext = ctx.obj
    ex = c.executor

    sql = (
        f"SELECT id, uuid, last_online, note FROM peer "
        f"WHERE id LIKE '%{term}%' OR uuid LIKE '%{term}%' OR note LIKE '%{term}%' "
        f"ORDER BY last_online DESC;"
    )
    rows_data = ex.query_db(sql)
    rows = [
        [r.get("id", ""), r.get("uuid", ""), r.get("last_online", ""), r.get("note", "")]
        for r in rows_data
    ]

    c.output.table(
        f"Search: {term}",
        [("ID", "cyan"), ("UUID", "dim"), ("Last Online", ""), ("Note", "")],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def export(ctx: typer.Context) -> None:
    """Export all peers as JSON."""
    c: AppContext = ctx.obj
    rows = c.executor.query_db("SELECT * FROM peer ORDER BY last_online DESC;")
    c.output.raw_json(rows)
```

- [ ] **Step 2: Commit**

```bash
git add packages/kctl-rustdesk/src/kctl_rustdesk/commands/peers.py
git commit -m "feat(kctl-rustdesk): add peers command group"
```

---

### Task 8: Command — users.py

**Files:**
- Create: `packages/kctl-rustdesk/src/kctl_rustdesk/commands/users.py`

- [ ] **Step 1: Create commands/users.py**

```python
"""User management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_rustdesk.core.callbacks import AppContext

app = typer.Typer(help="Manage RustDesk users.")


@app.command("list")
def list_(
    ctx: typer.Context,
    active: Annotated[bool, typer.Option("--active", help="Only active users")] = False,
) -> None:
    """List all users."""
    c: AppContext = ctx.obj
    ex = c.executor

    where = "WHERE status = 1" if active else ""
    sql = f"SELECT name, email, is_admin, created_at, status FROM user {where} ORDER BY name;"

    rows_data = ex.query_db(sql)
    rows = [
        [
            r.get("name", ""),
            r.get("email", ""),
            "yes" if r.get("is_admin") == "1" else "",
            r.get("status", ""),
            r.get("created_at", ""),
        ]
        for r in rows_data
    ]

    c.output.table(
        "Users" + (" (active)" if active else ""),
        [("Name", "cyan"), ("Email", ""), ("Admin", "green"), ("Status", ""), ("Created", "dim")],
        rows,
        data_for_json=rows_data,
    )


@app.command("get")
def get(
    ctx: typer.Context,
    username: Annotated[str, typer.Argument(help="Username")],
) -> None:
    """Get details for a specific user."""
    c: AppContext = ctx.obj
    ex = c.executor

    users = ex.query_db(f"SELECT * FROM user WHERE name = '{username}';")
    if not users:
        c.output.error(f"User not found: {username}")
        raise typer.Exit(1)

    user = users[0]
    peer_count = ex.query_db_scalar(
        f"SELECT count(*) FROM peer WHERE user_id = "
        f"(SELECT rowid FROM user WHERE name = '{username}');"
    )

    sections = [
        ("User Details", [(k, str(v)) for k, v in user.items()] + [("Peers", peer_count)]),
    ]
    data = dict(user)
    data["peer_count"] = int(peer_count) if peer_count.isdigit() else 0
    c.output.detail(f"User: {username}", sections, data_for_json=data)


@app.command()
def count(ctx: typer.Context) -> None:
    """Count users."""
    c: AppContext = ctx.obj
    ex = c.executor

    total = ex.query_db_scalar("SELECT count(*) FROM user;")
    active = ex.query_db_scalar("SELECT count(*) FROM user WHERE status = 1;")
    admins = ex.query_db_scalar("SELECT count(*) FROM user WHERE is_admin = 1;")

    sections = [("User Count", [("Total", total), ("Active", active), ("Admins", admins)])]
    c.output.detail("User Count", sections, data_for_json={
        "total": int(total), "active": int(active), "admins": int(admins),
    })


@app.command()
def groups(ctx: typer.Context) -> None:
    """List user groups."""
    c: AppContext = ctx.obj
    rows_data = c.executor.query_db("SELECT * FROM grp ORDER BY name;")
    rows = [
        [r.get("name", ""), r.get("note", ""), r.get("created_at", "")]
        for r in rows_data
    ]

    c.output.table(
        "Groups",
        [("Name", "cyan"), ("Note", ""), ("Created", "dim")],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def export(ctx: typer.Context) -> None:
    """Export all users as JSON."""
    c: AppContext = ctx.obj
    rows = c.executor.query_db("SELECT * FROM user ORDER BY name;")
    c.output.raw_json(rows)
```

- [ ] **Step 2: Commit**

```bash
git add packages/kctl-rustdesk/src/kctl_rustdesk/commands/users.py
git commit -m "feat(kctl-rustdesk): add users command group"
```

---

### Task 9: Command — audit.py

**Files:**
- Create: `packages/kctl-rustdesk/src/kctl_rustdesk/commands/audit.py`

- [ ] **Step 1: Create commands/audit.py**

```python
"""Audit log and connection history commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_rustdesk.core.callbacks import AppContext

app = typer.Typer(help="Audit logs and connection history.")


@app.command()
def connections(
    ctx: typer.Context,
    today: Annotated[bool, typer.Option("--today", help="Only today")] = False,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max rows")] = 50,
) -> None:
    """Show connection history."""
    c: AppContext = ctx.obj
    ex = c.executor

    where = "WHERE date(created_at) = date('now')" if today else ""
    sql = (
        f"SELECT peer_id, ip, created_at FROM conn_log {where} "
        f"ORDER BY created_at DESC LIMIT {limit};"
    )

    rows_data = ex.query_db(sql)
    rows = [
        [r.get("peer_id", ""), r.get("ip", ""), r.get("created_at", "")]
        for r in rows_data
    ]

    title = "Connections (today)" if today else f"Connections (last {limit})"
    c.output.table(
        title,
        [("Peer ID", "cyan"), ("IP", ""), ("Time", "dim")],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def logins(
    ctx: typer.Context,
    failed: Annotated[bool, typer.Option("--failed", help="Only failed logins")] = False,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max rows")] = 50,
) -> None:
    """Show login history."""
    c: AppContext = ctx.obj
    ex = c.executor

    where = "WHERE type != 0" if failed else ""
    sql = (
        f"SELECT user_id, ip, type, created_at FROM login_log {where} "
        f"ORDER BY created_at DESC LIMIT {limit};"
    )

    rows_data = ex.query_db(sql)
    rows = [
        [
            r.get("user_id", ""),
            r.get("ip", ""),
            "failed" if r.get("type", "0") != "0" else "ok",
            r.get("created_at", ""),
        ]
        for r in rows_data
    ]

    title = "Failed Logins" if failed else f"Logins (last {limit})"
    c.output.table(
        title,
        [("User", "cyan"), ("IP", ""), ("Status", ""), ("Time", "dim")],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def stats(ctx: typer.Context) -> None:
    """Show connection statistics."""
    c: AppContext = ctx.obj
    ex = c.executor

    total_conns = ex.query_db_scalar("SELECT count(*) FROM conn_log;")
    today_conns = ex.query_db_scalar(
        "SELECT count(*) FROM conn_log WHERE date(created_at) = date('now');"
    )
    unique_peers = ex.query_db_scalar("SELECT count(DISTINCT peer_id) FROM conn_log;")
    unique_ips = ex.query_db_scalar("SELECT count(DISTINCT ip) FROM conn_log;")
    total_logins = ex.query_db_scalar("SELECT count(*) FROM login_log;")
    failed_logins = ex.query_db_scalar("SELECT count(*) FROM login_log WHERE type != 0;")

    top_peers = ex.query_db(
        "SELECT peer_id, count(*) as cnt FROM conn_log "
        "GROUP BY peer_id ORDER BY cnt DESC LIMIT 5;"
    )

    sections = [
        ("Connection Stats", [
            ("Total connections", total_conns),
            ("Today", today_conns),
            ("Unique peers", unique_peers),
            ("Unique IPs", unique_ips),
        ]),
        ("Login Stats", [
            ("Total logins", total_logins),
            ("Failed logins", failed_logins),
        ]),
        ("Top Peers", [
            (p.get("peer_id", ""), f"{p.get('cnt', 0)} connections") for p in top_peers
        ]),
    ]

    c.output.detail("Audit Statistics", sections, data_for_json={
        "connections": {
            "total": int(total_conns), "today": int(today_conns),
            "unique_peers": int(unique_peers), "unique_ips": int(unique_ips),
        },
        "logins": {"total": int(total_logins), "failed": int(failed_logins)},
        "top_peers": top_peers,
    })


@app.command()
def active(ctx: typer.Context) -> None:
    """Show currently active sessions."""
    c: AppContext = ctx.obj
    ex = c.executor

    sql = (
        "SELECT peer_id, ip, created_at FROM conn_log "
        "WHERE created_at > datetime('now', '-5 minutes') "
        "ORDER BY created_at DESC;"
    )

    rows_data = ex.query_db(sql)
    rows = [
        [r.get("peer_id", ""), r.get("ip", ""), r.get("created_at", "")]
        for r in rows_data
    ]

    c.output.table(
        "Active Sessions (last 5m)",
        [("Peer ID", "cyan"), ("IP", ""), ("Connected", "dim")],
        rows,
        data_for_json=rows_data,
    )
```

- [ ] **Step 2: Commit**

```bash
git add packages/kctl-rustdesk/src/kctl_rustdesk/commands/audit.py
git commit -m "feat(kctl-rustdesk): add audit command group"
```

---

### Task 10: Command — backup.py

**Files:**
- Create: `packages/kctl-rustdesk/src/kctl_rustdesk/commands/backup.py`

- [ ] **Step 1: Create commands/backup.py**

```python
"""Backup and restore commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_rustdesk.core.callbacks import AppContext
from kctl_rustdesk.core.executor import RustDeskExecutor

app = typer.Typer(help="Backup and restore RustDesk server data.")

BACKUP_DIR = "/opt/kodemeio-rustdesk/backups"
DATA_DIR = "/root"


@app.command()
def create(ctx: typer.Context) -> None:
    """Create a backup of keys and database."""
    c: AppContext = ctx.obj
    out = c.output
    ex = c.executor

    out.info("Creating backup...")
    ex.shell(["mkdir", "-p", BACKUP_DIR])

    timestamp = ex.shell(["date", "+%Y%m%d-%H%M%S"])
    backup_name = f"rustdesk-backup-{timestamp}.tar.gz"
    backup_path = f"{BACKUP_DIR}/{backup_name}"

    ex.exec_hbbs([
        "tar", "czf", f"/tmp/{backup_name}", "-C", DATA_DIR,
        "id_ed25519", "id_ed25519.pub", "db_v2.sqlite3",
    ])

    container_name = f"{ex.config.project_name}-hbbs-1"
    ex.shell(["docker", "cp", f"{container_name}:/tmp/{backup_name}", backup_path])
    ex.exec_hbbs(["rm", "-f", f"/tmp/{backup_name}"], check=False)

    out.success(f"Backup created: {backup_path}")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List available backups."""
    c: AppContext = ctx.obj
    ex = c.executor

    output = ex.shell(
        ["find", BACKUP_DIR, "-name", "rustdesk-backup-*.tar.gz",
         "-printf", r"%f\t%s\t%T+\n"],
        check=False,
    )

    if not output.strip():
        c.output.info("No backups found.")
        return

    rows: list[list[str]] = []
    for line in output.strip().splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            name = parts[0]
            size_bytes = int(parts[1]) if parts[1].isdigit() else 0
            if size_bytes < 1048576:
                size = f"{size_bytes / 1024:.1f} KB"
            else:
                size = f"{size_bytes / 1048576:.1f} MB"
            date = parts[2][:19].replace("T", " ")
            rows.append([name, size, date])

    c.output.table(
        "Backups",
        [("File", "cyan"), ("Size", ""), ("Date", "dim")],
        rows,
    )


@app.command()
def restore(
    ctx: typer.Context,
    backup_file: Annotated[str, typer.Argument(help="Backup filename or full path")],
) -> None:
    """Restore from a backup file."""
    c: AppContext = ctx.obj
    out = c.output
    ex = c.executor

    if "/" not in backup_file:
        backup_file = f"{BACKUP_DIR}/{backup_file}"

    if not typer.confirm(
        f"Restore from {backup_file}? This will overwrite current data."
    ):
        out.info("Restore cancelled.")
        raise typer.Exit()

    out.info(f"Restoring from {backup_file}...")

    container_name = f"{ex.config.project_name}-hbbs-1"
    ex.shell(["docker", "cp", backup_file, f"{container_name}:/tmp/restore.tar.gz"])
    ex.exec_hbbs(["tar", "xzf", "/tmp/restore.tar.gz", "-C", DATA_DIR])
    ex.exec_hbbs(["rm", "-f", "/tmp/restore.tar.gz"])

    out.info("Restarting services...")
    ex.shell([*ex._dc_cmd(), "restart"])

    out.success("Restore complete. Services restarted.")


@app.command()
def clean(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", "-d", help="Delete backups older than N days")] = 30,
) -> None:
    """Remove old backups."""
    c: AppContext = ctx.obj
    out = c.output
    ex = c.executor

    old_files = ex.shell(
        ["find", BACKUP_DIR, "-name", "rustdesk-backup-*.tar.gz", "-mtime", f"+{days}"],
        check=False,
    )

    if not old_files.strip():
        out.info(f"No backups older than {days} days.")
        return

    file_count = len(old_files.strip().splitlines())
    if not typer.confirm(f"Delete {file_count} backup(s) older than {days} days?"):
        out.info("Cleanup cancelled.")
        raise typer.Exit()

    ex.shell([
        "find", BACKUP_DIR, "-name", "rustdesk-backup-*.tar.gz",
        "-mtime", f"+{days}", "-delete",
    ])
    out.success(f"Deleted {file_count} old backup(s).")
```

- [ ] **Step 2: Commit**

```bash
git add packages/kctl-rustdesk/src/kctl_rustdesk/commands/backup.py
git commit -m "feat(kctl-rustdesk): add backup command group"
```

---

### Task 11: Command — dashboard.py

**Files:**
- Create: `packages/kctl-rustdesk/src/kctl_rustdesk/commands/dashboard.py`

- [ ] **Step 1: Create commands/dashboard.py**

```python
"""Dashboard overview commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_rustdesk.core.callbacks import AppContext

app = typer.Typer(help="System overview dashboard.")


@app.command("show")
def show(
    ctx: typer.Context,
    compact: Annotated[bool, typer.Option("--compact", help="Compact output")] = False,
) -> None:
    """Show system overview dashboard."""
    c: AppContext = ctx.obj
    out = c.output
    ex = c.executor

    hbbs_running = ex.container_running("hbbs")
    hbbr_running = ex.container_running("hbbr")

    hbbs_status = "[green]running[/green]" if hbbs_running else "[red]stopped[/red]"
    hbbr_status = "[green]running[/green]" if hbbr_running else "[red]stopped[/red]"

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        ("Services", [
            ("hbbs (ID server)", hbbs_status),
            ("hbbr (Relay)", hbbr_status),
        ]),
    ]

    if not compact:
        hbbs_stats = ex.get_container_stats("hbbs")
        hbbr_stats = ex.get_container_stats("hbbr")
        sections.append(("Resources", [
            ("hbbs CPU", hbbs_stats["cpu"]),
            ("hbbs Memory", f"{hbbs_stats['mem_usage']} ({hbbs_stats['mem_pct']})"),
            ("hbbr CPU", hbbr_stats["cpu"]),
            ("hbbr Memory", f"{hbbr_stats['mem_usage']} ({hbbr_stats['mem_pct']})"),
        ]))

    try:
        public_key = ex.get_public_key()
    except Exception:
        public_key = "(unavailable)"

    key_display = public_key[:20] + "..." if len(public_key) > 20 else public_key
    sections.append(("Configuration", [
        ("Domain", ex.config.domain),
        ("ID Server", f"{ex.config.domain}:21116"),
        ("Relay Server", f"{ex.config.domain}:21117"),
        ("Public Key", key_display),
    ]))

    if not compact:
        try:
            peer_count = ex.query_db_scalar("SELECT count(*) FROM peer;")
            user_count = ex.query_db_scalar("SELECT count(*) FROM user;")
            group_count = ex.query_db_scalar("SELECT count(*) FROM grp;")
            sections.append(("Database", [
                ("Peers", peer_count),
                ("Users", user_count),
                ("Groups", group_count),
            ]))
        except Exception:
            sections.append(("Database", [("Status", "[yellow]unavailable[/yellow]")]))

    out.detail("RustDesk Dashboard", sections, data_for_json={
        "services": {"hbbs": hbbs_running, "hbbr": hbbr_running},
        "config": {"domain": ex.config.domain, "public_key": public_key},
    })
```

- [ ] **Step 2: Commit**

```bash
git add packages/kctl-rustdesk/src/kctl_rustdesk/commands/dashboard.py
git commit -m "feat(kctl-rustdesk): add dashboard command"
```

---

### Task 12: Command — setup.py

**Files:**
- Create: `packages/kctl-rustdesk/src/kctl_rustdesk/commands/setup.py`

- [ ] **Step 1: Create commands/setup.py**

```python
"""Setup and configuration commands."""

from __future__ import annotations

import typer

from kctl_rustdesk.core.callbacks import AppContext

app = typer.Typer(help="Server setup and configuration.")


@app.command()
def status(ctx: typer.Context) -> None:
    """Show setup status checklist."""
    c: AppContext = ctx.obj
    out = c.output
    ex = c.executor

    checks: list[tuple[str, bool]] = []
    checks.append(("hbbs container running", ex.container_running("hbbs")))
    checks.append(("hbbr container running", ex.container_running("hbbr")))
    checks.append(("Public key exists", ex.file_exists("hbbs", ex.KEY_PUB_PATH)))
    checks.append(("Private key exists", ex.file_exists("hbbs", ex.KEY_PRIV_PATH)))

    try:
        ex.query_db_scalar("SELECT count(*) FROM peer;")
        checks.append(("Database accessible", True))
    except Exception:
        checks.append(("Database accessible", False))

    out.header("Setup Status")
    all_ok = True
    for name, ok in checks:
        icon = "[green]OK[/green]" if ok else "[red]MISSING[/red]"
        out.text(f"  {icon} {name}")
        if not ok:
            all_ok = False

    out.text("")
    if all_ok:
        out.success("All checks passed. Server is ready.")
    else:
        out.warn("Some checks failed. Review and fix issues above.")


@app.command("get-key")
def get_key(ctx: typer.Context) -> None:
    """Display the server's public key."""
    c: AppContext = ctx.obj
    try:
        key = c.executor.get_public_key()
        if c.json_mode:
            c.output.raw_json({"public_key": key})
        else:
            c.output.text(key)
    except Exception as e:
        c.output.error(f"Cannot read public key: {e}")
        raise typer.Exit(1)


@app.command("client-config")
def client_config(ctx: typer.Context) -> None:
    """Generate RustDesk client configuration string."""
    c: AppContext = ctx.obj
    out = c.output
    ex = c.executor

    try:
        key = ex.get_public_key()
    except Exception as e:
        out.error(f"Cannot read public key: {e}")
        raise typer.Exit(1)

    domain = ex.config.domain
    config_str = (
        f"rs-pub-key={key},"
        f"rendezvous-server={domain}:21116,"
        f"relay-server={domain}:21117"
    )

    if c.json_mode:
        out.raw_json({
            "config_string": config_str,
            "id_server": f"{domain}:21116",
            "relay_server": f"{domain}:21117",
            "public_key": key,
        })
        return

    out.header("Client Configuration")
    out.kv("ID Server", f"{domain}:21116")
    out.kv("Relay Server", f"{domain}:21117")
    out.kv("Public Key", key)
    out.text("")
    out.text("[bold]Config string (paste into client):[/bold]")
    out.text(f"  {config_str}")


@app.command()
def firewall(ctx: typer.Context) -> None:
    """Show required firewall rules."""
    c: AppContext = ctx.obj
    rows = [
        ["21115", "TCP", "NAT type test"],
        ["21116", "TCP", "ID/Rendezvous server"],
        ["21116", "UDP", "ID/Rendezvous server (heartbeat)"],
        ["21117", "TCP", "Relay server"],
        ["21118", "TCP", "WebSocket (hbbs)"],
        ["21119", "TCP", "WebSocket (hbbr)"],
    ]

    c.output.table(
        "Required Firewall Rules",
        [("Port", "cyan"), ("Protocol", ""), ("Service", "")],
        rows,
    )
```

- [ ] **Step 2: Commit**

```bash
git add packages/kctl-rustdesk/src/kctl_rustdesk/commands/setup.py
git commit -m "feat(kctl-rustdesk): add setup command group"
```

---

### Task 13: Command — maintenance.py

**Files:**
- Create: `packages/kctl-rustdesk/src/kctl_rustdesk/commands/maintenance.py`

- [ ] **Step 1: Create commands/maintenance.py**

```python
"""Maintenance and operational commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_rustdesk.core.callbacks import AppContext

app = typer.Typer(help="Maintenance and operational tasks.")


@app.command()
def status(ctx: typer.Context) -> None:
    """Show container status and resource usage."""
    c: AppContext = ctx.obj
    ex = c.executor

    containers = ex.docker_ps()
    rows = [
        [
            ct.get("Service", ct.get("Name", "")),
            ct.get("State", ct.get("Status", "")),
            ct.get("Health", ""),
            ct.get("Ports", ""),
        ]
        for ct in containers
    ]

    c.output.table(
        "Container Status",
        [("Service", "cyan"), ("State", "green"), ("Health", ""), ("Ports", "dim")],
        rows,
        data_for_json=containers,
    )


@app.command()
def version(ctx: typer.Context) -> None:
    """Show version information."""
    c: AppContext = ctx.obj
    ex = c.executor

    from kctl_rustdesk import __version__

    compose_ver = ex.get_compose_version()

    try:
        hbbs_image = ex.shell(
            ["docker", "inspect", "--format", "{{.Config.Image}}",
             f"{ex.config.project_name}-hbbs-1"],
            check=False,
        )
    except Exception:
        hbbs_image = "unknown"

    sections = [("Versions", [
        ("kctl-rustdesk", __version__),
        ("Docker Compose", compose_ver),
        ("hbbs image", hbbs_image),
    ])]

    c.output.detail("Version Info", sections, data_for_json={
        "kctl_rustdesk": __version__,
        "docker_compose": compose_ver,
        "hbbs_image": hbbs_image,
    })


@app.command()
def logs(
    ctx: typer.Context,
    service: Annotated[str | None, typer.Argument(help="Service (hbbs or hbbr)")] = None,
    lines: Annotated[int, typer.Option("--lines", "-n", help="Number of lines")] = 100,
) -> None:
    """View container logs."""
    c: AppContext = ctx.obj
    output = c.executor.docker_logs(service=service, tail=lines)
    c.output.text(output)


@app.command("db-optimize")
def db_optimize(ctx: typer.Context) -> None:
    """Optimize the SQLite database (VACUUM + ANALYZE)."""
    c: AppContext = ctx.obj
    out = c.output
    ex = c.executor

    out.info("Running integrity check...")
    integrity = ex.exec_hbbs(["sqlite3", ex.DB_PATH, "PRAGMA integrity_check;"])
    out.kv("Integrity", integrity)

    out.info("Running VACUUM...")
    ex.exec_hbbs(["sqlite3", ex.DB_PATH, "VACUUM;"])

    out.info("Running ANALYZE...")
    ex.exec_hbbs(["sqlite3", ex.DB_PATH, "ANALYZE;"])

    out.success("Database optimized.")


@app.command("db-stats")
def db_stats(ctx: typer.Context) -> None:
    """Show database statistics."""
    c: AppContext = ctx.obj
    ex = c.executor

    tables = ["peer", "user", "grp", "conn_log", "login_log"]
    rows: list[list[str]] = []
    json_data: dict[str, int] = {}

    for table in tables:
        try:
            count = ex.query_db_scalar(f"SELECT count(*) FROM {table};")
            rows.append([table, count])
            json_data[table] = int(count)
        except Exception:
            rows.append([table, "(error)"])
            json_data[table] = -1

    try:
        size = ex.exec_hbbs(
            ["stat", "-c", "%s", ex.DB_PATH], check=False,
        )
        if size.strip().isdigit():
            size_mb = f"{int(size) / 1048576:.2f} MB"
        else:
            size_mb = "unknown"
    except Exception:
        size_mb = "unknown"

    rows.append(["---", "---"])
    rows.append(["DB size", size_mb])

    c.output.table(
        "Database Statistics",
        [("Table", "cyan"), ("Rows", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def cleanup(ctx: typer.Context) -> None:
    """Clean up unused Docker resources."""
    c: AppContext = ctx.obj
    out = c.output
    ex = c.executor

    if not typer.confirm("Remove dangling images and build cache?"):
        out.info("Cleanup cancelled.")
        raise typer.Exit()

    out.info("Removing dangling images...")
    ex.shell(["docker", "image", "prune", "-f"], check=False)

    out.info("Clearing build cache...")
    ex.shell(["docker", "builder", "prune", "-f"], check=False)

    out.success("Cleanup complete.")
```

- [ ] **Step 2: Commit**

```bash
git add packages/kctl-rustdesk/src/kctl_rustdesk/commands/maintenance.py
git commit -m "feat(kctl-rustdesk): add maintenance command group"
```

---

### Task 14: Wire up all commands in cli.py

**Files:**
- Modify: `packages/kctl-rustdesk/src/kctl_rustdesk/cli.py`

- [ ] **Step 1: Replace cli.py with full version registering all 9 command groups**

```python
"""kctl-rustdesk CLI entry point."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_lib import handle_cli_error
from kctl_lib.exceptions import KctlError

from kctl_rustdesk import __version__
from kctl_rustdesk.commands.audit import app as audit_app
from kctl_rustdesk.commands.backup import app as backup_app
from kctl_rustdesk.commands.config_cmd import app as config_app
from kctl_rustdesk.commands.dashboard import app as dashboard_app
from kctl_rustdesk.commands.health import app as health_app
from kctl_rustdesk.commands.maintenance import app as maintenance_app
from kctl_rustdesk.commands.peers import app as peers_app
from kctl_rustdesk.commands.setup import app as setup_app
from kctl_rustdesk.commands.users import app as users_app
from kctl_rustdesk.core.plugins import discover_and_load_plugins


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-rustdesk {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-rustdesk",
    help="Kodemeio RustDesk CLI — manage RustDesk server infrastructure.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


@app.callback()
def main(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress info messages")] = False,
    profile: Annotated[str | None, typer.Option("--profile", "-p", help="Config profile")] = None,
    format: Annotated[str, typer.Option("--format", "-f", help="Output format")] = "pretty",
    no_header: Annotated[bool, typer.Option("--no-header", help="Omit column headers")] = False,
    host: Annotated[str | None, typer.Option("--host", help="Server host override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True)
    ] = False,
) -> None:
    """Manage RustDesk server infrastructure."""
    from kctl_rustdesk.core.callbacks import AppContext

    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        format=format,
        no_header=no_header,
        host_override=host,
    )


app.add_typer(config_app, name="config")
app.add_typer(health_app, name="health")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(peers_app, name="peers")
app.add_typer(users_app, name="users")
app.add_typer(audit_app, name="audit")
app.add_typer(backup_app, name="backup")
app.add_typer(setup_app, name="setup")
app.add_typer(maintenance_app, name="maintenance")

discover_and_load_plugins(app)


def _run() -> None:
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
```

- [ ] **Step 2: Commit**

```bash
git add packages/kctl-rustdesk/src/kctl_rustdesk/cli.py
git commit -m "feat(kctl-rustdesk): wire up all 9 command groups in CLI"
```

---

### Task 15: Install and verify CLI runs

- [ ] **Step 1: Install in dev mode**

```bash
cd packages/kctl-rustdesk && uv pip install -e .
```

- [ ] **Step 2: Verify version**

```bash
kctl-rustdesk --version
```

Expected: `kctl-rustdesk 0.1.0`

- [ ] **Step 3: Verify help shows all groups**

```bash
kctl-rustdesk --help
```

Expected: 9 command groups listed (config, health, dashboard, peers, users, audit, backup, setup, maintenance).

- [ ] **Step 4: Verify each subcommand help**

```bash
kctl-rustdesk config --help
kctl-rustdesk health --help
kctl-rustdesk peers --help
kctl-rustdesk users --help
kctl-rustdesk audit --help
kctl-rustdesk backup --help
kctl-rustdesk dashboard --help
kctl-rustdesk setup --help
kctl-rustdesk maintenance --help
```

Expected: Each shows its subcommands without import errors.

- [ ] **Step 5: Fix any issues found, commit fixes**

```bash
git add -u packages/kctl-rustdesk/
git commit -m "fix(kctl-rustdesk): resolve import/registration issues"
```

---

### Task 16: Lint and final verification

- [ ] **Step 1: Run ruff check**

```bash
cd packages/kctl-rustdesk && ruff check src/
```

- [ ] **Step 2: Fix any lint issues**

- [ ] **Step 3: Final commit**

```bash
git add packages/kctl-rustdesk/
git commit -m "chore(kctl-rustdesk): pass ruff lint checks"
```
