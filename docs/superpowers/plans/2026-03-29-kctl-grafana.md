# kctl-grafana Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build kctl-grafana CLI with 12 command groups for daily Grafana monitoring operations.

**Architecture:** Python CLI using kctl-lib v0.4.0 (APIClient subclass for Grafana HTTP API). Created inside existing kodemeio-grafana repo as cli/ directory alongside docker-compose and scripts.

**Tech Stack:** Python 3.12+, kctl-lib>=0.4.0, Typer, httpx, Rich

**Spec:** `docs/superpowers/specs/2026-03-29-kctl-service-clis-design.md` (Section 2)

**Working directory:** `/home/tgunawan/project/00-new-projects/kodemeio-core/kodemeio-grafana`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `cli/pyproject.toml` | Package config, dependencies, entry points |
| Create | `cli/src/kctl_grafana/__init__.py` | Version |
| Create | `cli/src/kctl_grafana/__main__.py` | python -m entry |
| Create | `cli/src/kctl_grafana/cli.py` | Main Typer app, global options, command registration |
| Create | `cli/src/kctl_grafana/core/__init__.py` | Empty |
| Create | `cli/src/kctl_grafana/core/config.py` | SERVICE_KEY, ServiceConfig, profile resolution |
| Create | `cli/src/kctl_grafana/core/client.py` | GrafanaClient(APIClient) |
| Create | `cli/src/kctl_grafana/core/callbacks.py` | AppContext dataclass |
| Create | `cli/src/kctl_grafana/core/exceptions.py` | CLI-specific exceptions |
| Create | `cli/src/kctl_grafana/commands/__init__.py` | Empty |
| Create | `cli/src/kctl_grafana/commands/config_cmd.py` | Config management (init/show/use/remove/export) |
| Create | `cli/src/kctl_grafana/commands/health.py` | Health check + detailed check |
| Create | `cli/src/kctl_grafana/commands/status.py` | Quick overview (counts, version) |
| Create | `cli/src/kctl_grafana/commands/dashboard.py` | Dashboard CRUD + search + export/import |
| Create | `cli/src/kctl_grafana/commands/datasource.py` | Datasource list/show/test |
| Create | `cli/src/kctl_grafana/commands/alert.py` | Alert rules, silence, contacts |
| Create | `cli/src/kctl_grafana/commands/folder.py` | Folder list/create/delete |
| Create | `cli/src/kctl_grafana/commands/annotation.py` | Annotation add/list |
| Create | `cli/src/kctl_grafana/commands/user.py` | User list/add |
| Create | `cli/src/kctl_grafana/commands/backup.py` | Backup create/restore |
| Create | `cli/src/kctl_grafana/commands/selftest.py` | Diagnostic self-test |
| Create | `cli/tests/__init__.py` | Empty |
| Create | `cli/tests/conftest.py` | Shared fixtures |
| Create | `cli/tests/test_smoke.py` | Smoke tests (--help, --version) |
| Create | `cli/tests/test_client.py` | GrafanaClient unit tests |
| Create | `cli/tests/test_health.py` | Health command tests |
| Create | `cli/tests/test_dashboard.py` | Dashboard command tests |
| Create | `cli/tests/test_datasource.py` | Datasource command tests |
| Create | `cli/tests/test_alert.py` | Alert command tests |
| Create | `cli/tests/test_folder.py` | Folder command tests |
| Create | `cli/tests/test_annotation.py` | Annotation command tests |
| Create | `cli/tests/test_user.py` | User command tests |
| Create | `cli/tests/test_backup.py` | Backup command tests |
| Modify | `CLAUDE.md` | Add CLI section |
| Create | `.github/workflows/validate.yml` | CI for lint + test |

---

### Task 1: Scaffold CLI structure

Create all boilerplate files for the CLI package.

**Files to create:**
- `cli/pyproject.toml`
- `cli/src/kctl_grafana/__init__.py`
- `cli/src/kctl_grafana/__main__.py`
- `cli/src/kctl_grafana/cli.py`
- `cli/src/kctl_grafana/core/__init__.py`
- `cli/src/kctl_grafana/core/config.py`
- `cli/src/kctl_grafana/core/client.py`
- `cli/src/kctl_grafana/core/callbacks.py`
- `cli/src/kctl_grafana/core/exceptions.py`
- `cli/src/kctl_grafana/commands/__init__.py`
- `cli/src/kctl_grafana/commands/config_cmd.py`
- `cli/tests/__init__.py`
- `cli/tests/conftest.py`
- `cli/tests/test_smoke.py`

- [ ] **Step 1: Create `cli/pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "kctl-grafana"
version = "0.1.0"
description = "Kodemeio Grafana CLI - manage Grafana monitoring platform"
readme = "README.md"
license = "MIT"
requires-python = ">=3.12"
authors = [{ name = "Kodemeio", email = "dev@kodeme.io" }]
keywords = ["grafana", "monitoring", "cli", "kodemeio"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Intended Audience :: System Administrators",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: System :: Monitoring",
]
dependencies = [
    "typer>=0.15.0",
    "httpx>=0.28.0",
    "rich>=13.9.0",
    "pydantic>=2.10.0",
    "pyyaml>=6.0.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-httpx>=0.35.0",
    "ruff>=0.9.0",
    "mypy>=1.14.0",
    "types-PyYAML>=6.0.0",
]

[project.scripts]
kctl-grafana = "kctl_grafana.cli:_run"
gf = "kctl_grafana.cli:_run"

[tool.hatch.build.targets.wheel]
packages = ["src/kctl_grafana"]

[tool.ruff]
target-version = "py312"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "W", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.12"
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "integration: tests that require a live Grafana instance",
    "smoke: basic connectivity tests",
]
```

- [ ] **Step 2: Create `cli/src/kctl_grafana/__init__.py`**

```python
"""kctl-grafana: Kodemeio Grafana CLI."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Create `cli/src/kctl_grafana/__main__.py`**

```python
"""Allow running as: python -m kctl_grafana."""

from kctl_grafana.cli import _run

_run()
```

- [ ] **Step 4: Create `cli/src/kctl_grafana/core/__init__.py`**

```python
"""Core modules for kctl-grafana."""
```

- [ ] **Step 5: Create `cli/src/kctl_grafana/core/exceptions.py`**

```python
"""Custom exception hierarchy for kctl-grafana."""

from __future__ import annotations

import httpx


class KctlError(Exception):
    """Base exception for all kctl errors."""


class ConfigError(KctlError):
    """Configuration-related errors."""


class AuthenticationError(KctlError):
    """Authentication/API key errors."""


class NotFoundError(KctlError):
    """Resource not found."""

    def __init__(self, resource_type: str, identifier: str):
        self.resource_type = resource_type
        self.identifier = identifier
        super().__init__(f"{resource_type} not found: {identifier}")


class ValidationError(KctlError):
    """Client-side input validation error."""


class TimeoutError(KctlError):
    """Request timeout error."""

    def __init__(self, url: str, timeout: float):
        self.url = url
        self.timeout = timeout
        super().__init__(f"Request to {url} timed out after {timeout}s")


class APIError(KctlError):
    """Grafana API error with response details."""

    def __init__(self, response: httpx.Response):
        self.status_code = response.status_code
        self.response = response
        try:
            body = response.json()
            self.detail = body.get("message", body.get("error", str(body)))
        except Exception:
            self.detail = response.text or f"HTTP {self.status_code}"
        super().__init__(f"API error {self.status_code}: {self.detail}")


class ConnectionError(KctlError):
    """Cannot connect to Grafana."""

    def __init__(self, url: str, cause: Exception | None = None):
        self.url = url
        self.cause = cause
        super().__init__(f"Cannot connect to {url}: {cause}")
```

- [ ] **Step 6: Create `cli/src/kctl_grafana/core/config.py`**

```python
"""Profile management and configuration resolution.

Shared config at ~/.config/kodemeio/config.yaml supports multiple services.
Each kctl-* CLI declares a SERVICE_KEY and reads its own section within a profile.

Config format:
  profiles:
    production:
      grafana:
        url: https://grafana.kodeme.io
        api_key: <key>
        org_id: 1
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from kctl_grafana.core.exceptions import ConfigError

CONFIG_DIR = Path.home() / ".config" / "kodemeio"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

SERVICE_KEY = "grafana"


class ServiceConfig(BaseModel):
    """Service-specific config within a profile."""

    url: str = ""
    api_key: str = ""
    org_id: int = 1


class ConfigFile(BaseModel):
    default_profile: str = "default"
    profiles: dict[str, dict[str, Any]] = {}


def load_raw_config() -> dict:
    """Load raw YAML config as dict."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}
    except yaml.YAMLError as e:
        raise ConfigError(f"Config file is corrupted ({CONFIG_FILE}): {e}") from e
    except OSError as e:
        raise ConfigError(f"Cannot read config file ({CONFIG_FILE}): {e}") from e


def save_raw_config(data: dict) -> None:
    """Save raw dict to config YAML."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def load_config() -> ConfigFile:
    """Load config file."""
    data = load_raw_config()
    return ConfigFile(
        default_profile=data.get("default_profile", "default"),
        profiles=data.get("profiles", {}),
    )


def _is_service_scoped(profile_data: dict) -> bool:
    """Check if a profile uses service-scoped format (new) vs flat format (old)."""
    return any(isinstance(val, dict) for val in profile_data.values())


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get this CLI's service config from a profile."""
    cfg = load_config()
    profile_data = cfg.profiles.get(profile_name, {})

    if not profile_data:
        return ServiceConfig()

    if _is_service_scoped(profile_data):
        svc_data = profile_data.get(SERVICE_KEY, {})
        if isinstance(svc_data, dict):
            return ServiceConfig(**{k: v for k, v in svc_data.items() if k in ServiceConfig.model_fields})
        return ServiceConfig()
    else:
        return ServiceConfig(**{k: v for k, v in profile_data.items() if k in ServiceConfig.model_fields})


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Write this CLI's service config into a profile (always scoped format)."""
    data = load_raw_config()
    if "profiles" not in data:
        data["profiles"] = {}
    if profile_name not in data["profiles"]:
        data["profiles"][profile_name] = {}

    profile = data["profiles"][profile_name]

    if not _is_service_scoped(profile):
        old_data = dict(profile)
        profile.clear()
        profile[SERVICE_KEY] = old_data

    svc_data = svc_config.model_dump(exclude_defaults=False)
    for key in list(svc_data.keys()):
        if not svc_data.get(key):
            svc_data.pop(key, None)

    profile[SERVICE_KEY] = svc_data
    save_raw_config(data)


def get_profile_names() -> list[str]:
    """Get all profile names."""
    cfg = load_config()
    return list(cfg.profiles.keys())


def get_all_services_in_profile(profile_name: str) -> dict[str, dict]:
    """Get all service configs in a profile (for display)."""
    cfg = load_config()
    profile_data = cfg.profiles.get(profile_name, {})

    if _is_service_scoped(profile_data):
        return {k: v for k, v in profile_data.items() if isinstance(v, dict)}
    else:
        return {SERVICE_KEY: profile_data}


def get_default_profile() -> str:
    """Get the default profile name."""
    cfg = load_config()
    return cfg.default_profile


def set_default_profile(name: str) -> None:
    """Set the default profile."""
    data = load_raw_config()
    data["default_profile"] = name
    save_raw_config(data)


def remove_profile(name: str) -> None:
    """Remove a profile entirely."""
    data = load_raw_config()
    profiles = data.get("profiles", {})
    profiles.pop(name, None)
    if data.get("default_profile") == name:
        data["default_profile"] = next(iter(profiles), "default")
    save_raw_config(data)


def _expand_key(api_key: str) -> str:
    """Expand ${ENV_VAR} references in API key values."""
    if api_key.startswith("${") and api_key.endswith("}"):
        env_name = api_key[2:-1]
        return os.environ.get(env_name, "")
    return api_key


def resolve_active_profile_name(
    profile_name: str | None = None,
) -> str:
    """Resolve the active profile name from all sources."""
    if profile_name:
        return profile_name
    if env := os.environ.get("KCTL_GRAFANA_PROFILE"):
        return env
    return get_default_profile()


def resolve_connection(
    profile_name: str | None = None,
    url_override: str | None = None,
    api_key_override: str | None = None,
) -> tuple[str, str, int]:
    """Resolve API URL, API key, and org_id from all sources.

    Priority:
    1. CLI flags (url_override, api_key_override)
    2. KCTL_GRAFANA_URL / KCTL_GRAFANA_API_KEY env vars
    3. Profile's grafana service config
    """
    url = ""
    api_key = ""
    org_id = 1

    # 3. Config file profile (service-scoped)
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    if svc.url:
        url = svc.url
    if svc.api_key:
        api_key = _expand_key(svc.api_key)
    org_id = svc.org_id

    # 2. KCTL env vars
    if env_url := os.environ.get("KCTL_GRAFANA_URL"):
        url = env_url
    if env_key := os.environ.get("KCTL_GRAFANA_API_KEY"):
        api_key = env_key
    if env_org := os.environ.get("KCTL_GRAFANA_ORG_ID"):
        try:
            org_id = int(env_org)
        except ValueError:
            pass

    # 1. CLI flags
    if url_override:
        url = url_override
    if api_key_override:
        api_key = api_key_override

    return url, api_key, org_id
```

- [ ] **Step 7: Create `cli/src/kctl_grafana/core/client.py`**

```python
"""Grafana API client, subclassing kctl-lib's APIClient.

Provides Grafana-specific auth (Bearer token), retry support,
and health check functionality.
"""

from __future__ import annotations

from typing import Any

import httpx
from kctl_lib.api_client import APIClient
from kctl_lib.exceptions import ConfigError


class GrafanaClient(APIClient):
    """Synchronous httpx client for Grafana API with retry support."""

    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"
    API_PREFIX = "/api"

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        org_id: int = 1,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_base_delay: float = 2.0,
        retry_max_delay: float = 60.0,
        **kwargs: Any,
    ):
        if not base_url:
            raise ConfigError("No URL configured. Run: kctl-grafana config init")

        self.org_id = org_id

        super().__init__(
            base_url=base_url,
            credential=api_key or "unset",
            timeout=timeout,
            retry_enabled=True,
            max_retries=max_retries,
            retry_base_delay=retry_base_delay,
            retry_max_delay=retry_max_delay,
            **kwargs,
        )

    @property
    def root_url(self) -> str:
        """Public accessor for the root URL (without /api)."""
        return self._base_url.rsplit("/api", 1)[0]

    def check_health(self) -> dict:
        """Check Grafana health endpoint. Returns health response dict."""
        try:
            r = httpx.get(f"{self.root_url}/api/health", timeout=5)
            return r.json()
        except httpx.HTTPError:
            return {"status": "error", "message": "unreachable"}

    def get_org(self) -> dict:
        """Get current organization info."""
        return self.get("/org")

    def get_version(self) -> str:
        """Get Grafana version from health endpoint."""
        health = self.check_health()
        return health.get("version", "unknown")
```

- [ ] **Step 8: Create `cli/src/kctl_grafana/core/callbacks.py`**

```python
"""Typer global callback and shared context."""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_grafana.core.client import GrafanaClient
from kctl_grafana.core.config import resolve_connection
from kctl_grafana.core.output import Output


@dataclass
class AppContext:
    """Shared application context passed through Typer's ctx.obj."""

    json_mode: bool = False
    quiet: bool = False
    format: str = "pretty"
    no_header: bool = False
    debug: bool = False
    profile: str | None = None
    url_override: str | None = None
    api_key_override: str | None = None
    _client: GrafanaClient | None = field(default=None, repr=False, init=False)
    _output: Output | None = field(default=None, repr=False, init=False)

    @property
    def output(self) -> Output:
        if self._output is None:
            self._output = Output(
                json_mode=self.json_mode,
                quiet=self.quiet,
                format=self.format,
                no_header=self.no_header,
            )
        return self._output

    @property
    def client(self) -> GrafanaClient:
        if self._client is None:
            url, api_key, org_id = resolve_connection(
                profile_name=self.profile,
                url_override=self.url_override,
                api_key_override=self.api_key_override,
            )
            self._client = GrafanaClient(base_url=url, api_key=api_key, org_id=org_id)
        return self._client

    def close(self) -> None:
        """Close underlying HTTP client."""
        if self._client is not None:
            self._client.close()
```

- [ ] **Step 9: Create `cli/src/kctl_grafana/core/output.py`**

Copy the Output class from kctl-dokploy verbatim. This is identical across all kctl-* CLIs:

```python
"""Centralized output handler with multi-format support.

Supports: pretty (Rich), JSON, CSV, YAML.
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
from typing import Any

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree


def _strip_markup(text: str) -> str:
    """Remove Rich markup tags from text."""
    return re.sub(r"\[/?[^\]]*\]", "", text)


class Output:
    """Output handler that switches between Rich (pretty), JSON, CSV, and YAML modes."""

    def __init__(
        self,
        json_mode: bool = False,
        quiet: bool = False,
        format: str = "pretty",
        no_header: bool = False,
    ):
        self.json_mode = json_mode or format == "json"
        self.quiet = quiet
        self.format = format if not json_mode else "json"
        self.no_header = no_header
        use_stderr = self.format != "pretty"
        self.console = Console(stderr=True) if use_stderr else Console()
        self._stdout = Console(file=sys.stdout)

    def _is_data_mode(self) -> bool:
        return self.format in ("json", "csv", "yaml")

    def table(
        self,
        title: str,
        columns: list[tuple[str, str]],
        rows: list[list[str]],
        data_for_json: list[dict] | None = None,
    ) -> None:
        """Print a Rich table, JSON array, CSV, or YAML list."""
        if self.format == "json":
            json_data = data_for_json or [
                {col[0].lower().replace(" ", "_"): val for col, val in zip(columns, row, strict=False)} for row in rows
            ]
            print(json.dumps(json_data, indent=2, default=str))
            return

        if self.format == "csv":
            buf = io.StringIO()
            writer = csv.writer(buf)
            if not self.no_header:
                writer.writerow([col[0] for col in columns])
            for row in rows:
                writer.writerow([_strip_markup(cell) for cell in row])
            sys.stdout.write(buf.getvalue())
            return

        if self.format == "yaml":
            json_data = data_for_json or [
                {col[0].lower().replace(" ", "_"): _strip_markup(val) for col, val in zip(columns, row, strict=False)}
                for row in rows
            ]
            yaml.dump(json_data, sys.stdout, default_flow_style=False, sort_keys=False)
            return

        t = Table(title=title, show_header=True, header_style="bold cyan")
        for col_name, col_style in columns:
            t.add_column(col_name, style=col_style)
        for row in rows:
            t.add_row(*row)
        self.console.print(t)

    def detail(
        self,
        title: str,
        sections: list[tuple[str, list[tuple[str, str]]]],
        data_for_json: dict | None = None,
    ) -> None:
        """Print a Rich panel with key-value sections."""
        if self.format == "json":
            if data_for_json is not None:
                print(json.dumps(data_for_json, indent=2, default=str))
            else:
                fallback = {}
                for _section_title, kvs in sections:
                    for k, v in kvs:
                        fallback[_strip_markup(k).lower().replace(" ", "_")] = _strip_markup(v)
                print(json.dumps(fallback, indent=2, default=str))
            return

        if self.format == "yaml":
            if data_for_json is not None:
                yaml.dump(data_for_json, sys.stdout, default_flow_style=False, sort_keys=False)
            else:
                data: dict[str, Any] = {}
                for section_title, kvs in sections:
                    data[_strip_markup(section_title)] = {_strip_markup(k): _strip_markup(v) for k, v in kvs}
                yaml.dump(data, sys.stdout, default_flow_style=False, sort_keys=False)
            return

        if self.format == "csv":
            buf = io.StringIO()
            writer = csv.writer(buf)
            if not self.no_header:
                writer.writerow(["section", "key", "value"])
            for section_title, kvs in sections:
                for k, v in kvs:
                    writer.writerow([_strip_markup(section_title), _strip_markup(k), _strip_markup(v)])
            sys.stdout.write(buf.getvalue())
            return

        lines: list[str] = []
        for section_title, kvs in sections:
            lines.append(f"[bold cyan]{section_title}[/bold cyan]")
            for key, value in kvs:
                lines.append(f"  [dim]{key}:[/dim] {value}")
            lines.append("")

        content = "\n".join(lines).rstrip()
        self.console.print(Panel(content, title=f"[bold]{title}[/bold]", border_style="blue"))

    def tree(self, title: str, nodes: list[dict], data_for_json: list[dict] | None = None) -> None:
        """Print Rich tree."""
        if self._is_data_mode():
            data = data_for_json or nodes
            if self.format == "json":
                print(json.dumps(data, indent=2, default=str))
            elif self.format == "yaml":
                yaml.dump(data, sys.stdout, default_flow_style=False, sort_keys=False)
            elif self.format == "csv":
                print(json.dumps(data, indent=2, default=str))
            return

        tree = Tree(f"[bold]{title}[/bold]")
        self._build_tree(tree, nodes)
        self.console.print(tree)

    def _build_tree(self, parent: Tree, nodes: list[dict]) -> None:
        for node in nodes:
            label = node.get("name", "")
            info = node.get("info", "")
            if info:
                label = f"{label} [dim]({info})[/dim]"
            branch = parent.add(label)
            children = node.get("children", [])
            if children:
                self._build_tree(branch, children)

    def success(self, message: str) -> None:
        if not self.quiet:
            self.console.print(f"[green]OK[/green] {message}")

    def error(self, message: str) -> None:
        self.console.print(f"[red]ERROR[/red] {message}")

    def warn(self, message: str) -> None:
        if not self.quiet:
            self.console.print(f"[yellow]WARN[/yellow] {message}")

    def info(self, message: str) -> None:
        if not self.quiet:
            self.console.print(f"[blue]INFO[/blue] {message}")

    def raw_json(self, data: Any) -> None:
        """Output raw JSON to stdout."""
        print(json.dumps(data, indent=2, default=str))

    def kv(self, key: str, value: str) -> None:
        """Print a single key-value pair."""
        if self._is_data_mode():
            return
        self.console.print(f"  [dim]{key}:[/dim] {value}")

    def header(self, title: str) -> None:
        if self.quiet or self._is_data_mode():
            return
        self.console.print()
        self.console.rule(f"[bold]{title}[/bold]", style="blue")

    def text(self, msg: str) -> None:
        if not self.quiet:
            self.console.print(msg)
```

- [ ] **Step 10: Create `cli/src/kctl_grafana/cli.py`**

```python
"""Main CLI entry point for kctl-grafana."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_grafana import __version__
from kctl_grafana.commands.alert import app as alert_app
from kctl_grafana.commands.annotation import app as annotation_app
from kctl_grafana.commands.backup import app as backup_app
from kctl_grafana.commands.config_cmd import app as config_app
from kctl_grafana.commands.dashboard import app as dashboard_app
from kctl_grafana.commands.datasource import app as datasource_app
from kctl_grafana.commands.folder import app as folder_app
from kctl_grafana.commands.health import app as health_app
from kctl_grafana.commands.selftest import app as selftest_app
from kctl_grafana.commands.status import app as status_app
from kctl_grafana.commands.user import app as user_app
from kctl_grafana.core.callbacks import AppContext


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-grafana {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-grafana",
    help="Kodemeio Grafana CLI - manage your Grafana monitoring platform.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


@app.callback()
def main(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON (shortcut for --format json)")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress info messages")] = False,
    output_format: Annotated[
        str, typer.Option("--format", "-f", help="Output format: pretty, json, csv, yaml")
    ] = "pretty",
    no_header: Annotated[bool, typer.Option("--no-header", help="Omit headers in CSV output")] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Enable debug logging")] = False,
    profile: Annotated[str | None, typer.Option("--profile", "-p", help="Config profile name")] = None,
    url: Annotated[str | None, typer.Option("--url", help="API URL override")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="API key override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio Grafana CLI."""
    import os

    if debug:
        os.environ["KCTL_DEBUG"] = "1"

    effective_format = "json" if json_output else output_format

    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output or effective_format == "json",
        quiet=quiet,
        format=effective_format,
        no_header=no_header,
        debug=debug,
        profile=profile,
        url_override=url,
        api_key_override=api_key,
    )


# Command groups
app.add_typer(config_app, name="config")
app.add_typer(health_app, name="health")
app.add_typer(status_app, name="status")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(datasource_app, name="datasource")
app.add_typer(alert_app, name="alert")
app.add_typer(folder_app, name="folder")
app.add_typer(annotation_app, name="annotation")
app.add_typer(user_app, name="user")
app.add_typer(backup_app, name="backup")
app.add_typer(selftest_app, name="selftest")


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
```

- [ ] **Step 11: Create `cli/src/kctl_grafana/commands/__init__.py`**

```python
"""CLI command modules for kctl-grafana."""
```

- [ ] **Step 12: Create `cli/src/kctl_grafana/commands/config_cmd.py`**

```python
"""Configuration management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_grafana.core.callbacks import AppContext
from kctl_grafana.core.config import (
    CONFIG_FILE,
    SERVICE_KEY,
    ServiceConfig,
    get_all_services_in_profile,
    get_default_profile,
    get_profile_names,
    load_raw_config,
    remove_profile,
    resolve_active_profile_name,
    set_default_profile,
    set_service_config,
)
from kctl_grafana.core.exceptions import KctlError

app = typer.Typer(help="Manage CLI configuration and profiles.")


def _mask(val: str) -> str:
    if not val:
        return "[dim]not set[/dim]"
    return f"{val[:4]}{'*' * max(0, len(val) - 8)}{val[-4:]}" if len(val) > 10 else "****"


@app.command()
def init(
    ctx: typer.Context,
    url: Annotated[str | None, typer.Option("--url")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key")] = None,
    org_id: Annotated[int, typer.Option("--org-id")] = 1,
    name: Annotated[str | None, typer.Option("--name", "-n")] = None,
) -> None:
    """Initialize CLI configuration."""
    c: AppContext = ctx.obj
    out = c.output
    profile_name = name or typer.prompt("Profile name", default="kodemeio")
    api_url = url or typer.prompt("Grafana URL (e.g. https://grafana.kodeme.io)")
    key = api_key or typer.prompt("API key", hide_input=True)

    svc = ServiceConfig(url=api_url, api_key=key, org_id=org_id)
    set_service_config(profile_name, svc)
    if len(get_profile_names()) <= 1:
        set_default_profile(profile_name)
    out.success(f"Configuration saved to {CONFIG_FILE}")
    out.kv("Profile", profile_name)
    out.kv("URL", api_url)
    out.kv("Org ID", str(org_id))
    out.kv("API Key", _mask(key))


@app.command()
def show(ctx: typer.Context) -> None:
    """Show configuration (keys masked)."""
    c: AppContext = ctx.obj
    out = c.output
    default = get_default_profile()
    sections = [
        (
            "General",
            [
                ("Config file", str(CONFIG_FILE)),
                ("Default profile", default),
                ("Service key", SERVICE_KEY),
            ],
        )
    ]
    for pname in get_profile_names():
        marker = " [green](default)[/green]" if pname == default else ""
        services = get_all_services_in_profile(pname)
        kvs = []
        for svc_name, svc_data in services.items():
            if not isinstance(svc_data, dict):
                continue
            indicator = "[green]●[/green]" if svc_name == SERVICE_KEY else "[dim]○[/dim]"
            kvs.append(
                (
                    f"{indicator} {svc_name}",
                    f"{svc_data.get('url', '')}  key: {_mask(svc_data.get('api_key', svc_data.get('token', '')))}",
                )
            )
        sections.append((f"Profile: {pname}{marker}", kvs or [("(empty)", "")]))
    out.detail("Configuration", sections)


@app.command()
def test(ctx: typer.Context) -> None:
    """Test API connection."""
    c: AppContext = ctx.obj
    out = c.output
    active = resolve_active_profile_name(c.profile)
    out.info(f"Testing profile '{active}' → {SERVICE_KEY}")
    try:
        health = c.client.check_health()
        if health.get("database", "") == "ok":
            out.success(f"Connected to Grafana (v{health.get('version', 'unknown')})")
        else:
            out.error(f"Grafana health check returned: {health}")
            raise typer.Exit(1)
    except KctlError as e:
        out.error(f"Connection failed: {e}")
        raise typer.Exit(1) from e


@app.command()
def use(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name")],
) -> None:
    """Switch default profile."""
    c: AppContext = ctx.obj
    if name not in get_profile_names():
        c.output.error(f"Profile '{name}' not found")
        raise typer.Exit(1)
    set_default_profile(name)
    c.output.success(f"Switched to '{name}'")


@app.command("remove")
def remove_cmd(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to remove")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Remove a profile."""
    c: AppContext = ctx.obj
    if name not in get_profile_names():
        c.output.error(f"Profile '{name}' not found")
        raise typer.Exit(1)
    if not force:
        typer.confirm(f"Remove profile '{name}'?", abort=True)
    remove_profile(name)
    c.output.success(f"Profile '{name}' removed")


@app.command()
def export(ctx: typer.Context) -> None:
    """Export current configuration as YAML."""
    import json
    import sys

    import yaml

    data = load_raw_config()
    if ctx.obj.json_mode:
        print(json.dumps(data, indent=2, default=str))
    else:
        yaml.dump(data, sys.stdout, default_flow_style=False, sort_keys=False)
```

- [ ] **Step 13: Create `cli/tests/__init__.py`**

```python
"""Tests for kctl-grafana."""
```

- [ ] **Step 14: Create `cli/tests/conftest.py`**

```python
"""Shared test fixtures for kctl-grafana."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_grafana.cli import app
from kctl_grafana.core.callbacks import AppContext
from kctl_grafana.core.client import GrafanaClient
from kctl_grafana.core.output import Output


@pytest.fixture
def runner() -> CliRunner:
    """Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    """Mock GrafanaClient."""
    client = MagicMock(spec=GrafanaClient)
    client.org_id = 1
    client.root_url = "https://grafana.kodeme.io"
    return client


@pytest.fixture
def mock_output() -> Output:
    """Output instance for testing."""
    return Output(json_mode=False, quiet=True, format="pretty")


@pytest.fixture
def mock_context(mock_client: MagicMock, mock_output: Output) -> AppContext:
    """AppContext with mocked client."""
    ctx = AppContext(quiet=True)
    ctx._client = mock_client
    ctx._output = mock_output
    return ctx


@pytest.fixture
def cli_app():
    """Return the Typer app for testing."""
    return app
```

- [ ] **Step 15: Create `cli/tests/test_smoke.py`**

```python
"""Smoke tests for kctl-grafana CLI."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from kctl_grafana import __version__
from kctl_grafana.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestSmoke:
    """Basic CLI smoke tests."""

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "kctl-grafana" in result.output.lower() or "grafana" in result.output.lower()

    def test_version(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_no_args_shows_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, [])
        assert result.exit_code == 0

    def test_config_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0
        assert "init" in result.output

    def test_dashboard_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["dashboard", "--help"])
        assert result.exit_code == 0

    def test_datasource_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["datasource", "--help"])
        assert result.exit_code == 0

    def test_alert_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["alert", "--help"])
        assert result.exit_code == 0

    def test_health_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["health", "--help"])
        assert result.exit_code == 0

    def test_folder_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["folder", "--help"])
        assert result.exit_code == 0

    def test_annotation_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["annotation", "--help"])
        assert result.exit_code == 0

    def test_user_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["user", "--help"])
        assert result.exit_code == 0

    def test_backup_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["backup", "--help"])
        assert result.exit_code == 0

    def test_status_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["status", "--help"])
        assert result.exit_code == 0

    def test_selftest_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["selftest", "--help"])
        assert result.exit_code == 0
```

- [ ] **Step 16: Sync and verify smoke tests pass**

```bash
cd cli && uv sync --all-extras && uv run pytest tests/test_smoke.py -v --tb=short
```

Note: This step will fail until all command modules exist (Task 2+). The scaffold is verified structurally first by checking imports work.

- [ ] **Step 17: Commit**

```bash
git add cli/
git commit -m "feat: scaffold kctl-grafana CLI structure with core modules and config commands"
```

---

### Task 2: Implement health + status commands

**Files to create:**
- `cli/src/kctl_grafana/commands/health.py`
- `cli/src/kctl_grafana/commands/status.py`
- `cli/tests/test_health.py`

- [ ] **Step 1: Create `cli/src/kctl_grafana/commands/health.py`**

```python
"""Health check commands."""

from __future__ import annotations

import typer

from kctl_grafana.core.callbacks import AppContext
from kctl_grafana.core.config import resolve_active_profile_name

app = typer.Typer(help="Health checks for Grafana API.")


@app.command("check")
def check(ctx: typer.Context) -> None:
    """Check Grafana API connectivity, version, and org info."""
    c: AppContext = ctx.obj
    out = c.output
    active = resolve_active_profile_name(c.profile)
    out.info(f"Checking profile '{active}'...")

    health = c.client.check_health()
    status = health.get("database", "unknown")

    if status == "ok":
        out.success(f"Grafana API reachable — v{health.get('version', 'unknown')}")
    else:
        out.error(f"Grafana health check failed: {health}")
        raise typer.Exit(1)

    # Fetch org info
    try:
        org = c.client.get_org()
        sections = [
            (
                "Health",
                [
                    ("Status", "[green]healthy[/green]"),
                    ("Version", health.get("version", "unknown")),
                    ("Commit", health.get("commit", "unknown")),
                    ("Database", status),
                ],
            ),
            (
                "Organization",
                [
                    ("ID", str(org.get("id", "unknown"))),
                    ("Name", org.get("name", "unknown")),
                ],
            ),
        ]
        out.detail(
            "Grafana Health",
            sections,
            data_for_json={
                "health": health,
                "organization": org,
            },
        )
    except Exception:
        out.warn("Could not fetch org info (check API key permissions)")


@app.command("detailed")
def detailed(ctx: typer.Context) -> None:
    """Detailed health check including all datasources."""
    c: AppContext = ctx.obj
    out = c.output

    # Basic health
    health = c.client.check_health()
    if health.get("database") != "ok":
        out.error(f"Grafana unhealthy: {health}")
        raise typer.Exit(1)

    out.success(f"Grafana API healthy — v{health.get('version', 'unknown')}")

    # Test all datasources
    out.header("Datasource Health")
    try:
        datasources = c.client.get("/datasources")
        rows: list[list[str]] = []
        all_ok = True
        for ds in datasources:
            ds_uid = ds.get("uid", "")
            ds_name = ds.get("name", "unknown")
            ds_type = ds.get("type", "unknown")
            try:
                result = c.client.post(f"/datasources/uid/{ds_uid}/health", json_body={})
                ds_status = result.get("status", "unknown")
                if ds_status == "OK":
                    status_display = "[green]OK[/green]"
                else:
                    status_display = f"[red]{ds_status}[/red]"
                    all_ok = False
            except Exception:
                status_display = "[red]ERROR[/red]"
                all_ok = False

            rows.append([ds_name, ds_type, status_display])

        out.table(
            "Datasource Health",
            [("Name", "cyan"), ("Type", ""), ("Status", "")],
            rows,
        )

        if all_ok:
            out.success("All datasources healthy")
        else:
            out.warn("Some datasources have issues")
    except Exception as e:
        out.error(f"Could not check datasources: {e}")
```

- [ ] **Step 2: Create `cli/src/kctl_grafana/commands/status.py`**

```python
"""Status overview command."""

from __future__ import annotations

import typer

from kctl_grafana.core.callbacks import AppContext

app = typer.Typer(help="Quick status overview.")


@app.command("overview")
def overview(ctx: typer.Context) -> None:
    """Show Grafana status overview: dashboard count, datasource health, active alerts, version."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    # Gather data
    health = client.check_health()
    version = health.get("version", "unknown")

    dashboard_count = 0
    datasource_count = 0
    alert_count = 0

    try:
        dashboards = client.get("/search", params={"type": "dash-db", "limit": 5000})
        dashboard_count = len(dashboards)
    except Exception:
        pass

    try:
        datasources = client.get("/datasources")
        datasource_count = len(datasources)
    except Exception:
        pass

    try:
        alerts = client.get("/v1/provisioning/alert-rules")
        alert_count = len(alerts)
    except Exception:
        pass

    # Count firing alerts
    firing_count = 0
    try:
        alert_instances = client.get("/alertmanager/grafana/api/v2/alerts")
        firing_count = sum(1 for a in alert_instances if a.get("status", {}).get("state") == "active")
    except Exception:
        pass

    db_status = health.get("database", "unknown")
    db_display = "[green]ok[/green]" if db_status == "ok" else f"[red]{db_status}[/red]"
    firing_display = f"[red]{firing_count}[/red]" if firing_count > 0 else "[green]0[/green]"

    sections = [
        (
            "Grafana Status",
            [
                ("Version", version),
                ("Database", db_display),
                ("Dashboards", str(dashboard_count)),
                ("Datasources", str(datasource_count)),
                ("Alert rules", str(alert_count)),
                ("Firing alerts", firing_display),
            ],
        ),
    ]

    out.detail(
        "Status Overview",
        sections,
        data_for_json={
            "version": version,
            "database": db_status,
            "dashboards": dashboard_count,
            "datasources": datasource_count,
            "alert_rules": alert_count,
            "firing_alerts": firing_count,
        },
    )
```

- [ ] **Step 3: Create `cli/tests/test_health.py`**

```python
"""Tests for health commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_grafana.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestHealthCheck:
    """Test health check command."""

    @patch("kctl_grafana.commands.health.AppContext")
    def test_health_check_success(self, runner: CliRunner) -> None:
        mock_client = MagicMock()
        mock_client.check_health.return_value = {
            "commit": "abc123",
            "database": "ok",
            "version": "11.4.0",
        }
        mock_client.get_org.return_value = {
            "id": 1,
            "name": "Kodemeio",
        }

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "test-key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "test-key", "health", "check"])

        # Should not error (exit 0)
        assert result.exit_code == 0

    @patch("kctl_grafana.commands.health.AppContext")
    def test_health_check_failure(self, runner: CliRunner) -> None:
        mock_client = MagicMock()
        mock_client.check_health.return_value = {
            "database": "error",
            "version": "unknown",
        }

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "test-key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "test-key", "health", "check"])

        assert result.exit_code == 1


class TestStatusOverview:
    """Test status overview command."""

    def test_status_overview(self, runner: CliRunner) -> None:
        mock_client = MagicMock()
        mock_client.check_health.return_value = {
            "database": "ok",
            "version": "11.4.0",
        }
        mock_client.get.side_effect = lambda path, **kw: {
            "/search": [{"uid": "abc", "title": "Test"}],
            "/datasources": [{"name": "Prometheus", "type": "prometheus"}],
            "/v1/provisioning/alert-rules": [{"uid": "rule1"}],
            "/alertmanager/grafana/api/v2/alerts": [],
        }.get(path, [])

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "test-key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "test-key", "status", "overview"])

        assert result.exit_code == 0
```

- [ ] **Step 4: Run tests**

```bash
cd cli && uv run pytest tests/test_health.py -v --tb=short
```

- [ ] **Step 5: Commit**

```bash
git add cli/src/kctl_grafana/commands/health.py cli/src/kctl_grafana/commands/status.py cli/tests/test_health.py
git commit -m "feat: add health and status commands for kctl-grafana"
```

---

### Task 3: Implement dashboard commands

**Files to create:**
- `cli/src/kctl_grafana/commands/dashboard.py`
- `cli/tests/test_dashboard.py`

- [ ] **Step 1: Create `cli/src/kctl_grafana/commands/dashboard.py`**

```python
"""Dashboard management commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from kctl_grafana.core.callbacks import AppContext

app = typer.Typer(help="Dashboard management.")


@app.command("list")
def list_dashboards(ctx: typer.Context) -> None:
    """List all dashboards."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    dashboards = client.get("/search", params={"type": "dash-db", "limit": 5000})

    rows: list[list[str]] = []
    for d in dashboards:
        uid = d.get("uid", "")
        title = d.get("title", "")
        folder = d.get("folderTitle", "General")
        tags = ", ".join(d.get("tags", []))
        starred = "[yellow]*[/yellow]" if d.get("isStarred") else ""
        rows.append([uid, title, folder, tags, starred])

    out.table(
        f"Dashboards ({len(dashboards)})",
        [("UID", "cyan"), ("Title", ""), ("Folder", "dim"), ("Tags", "dim"), ("Starred", "")],
        rows,
        data_for_json=dashboards,
    )


@app.command("show")
def show_dashboard(
    ctx: typer.Context,
    uid: Annotated[str, typer.Argument(help="Dashboard UID")],
) -> None:
    """Show dashboard metadata and panel summary."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    result = client.get(f"/dashboards/uid/{uid}")
    meta = result.get("meta", {})
    dashboard = result.get("dashboard", {})
    panels = dashboard.get("panels", [])

    sections = [
        (
            "Dashboard",
            [
                ("UID", dashboard.get("uid", "")),
                ("Title", dashboard.get("title", "")),
                ("Version", str(dashboard.get("version", 0))),
                ("Created", meta.get("created", "")),
                ("Updated", meta.get("updated", "")),
                ("Created by", meta.get("createdBy", "")),
                ("Updated by", meta.get("updatedBy", "")),
                ("Folder", meta.get("folderTitle", "General")),
                ("URL", meta.get("url", "")),
            ],
        ),
        (
            f"Panels ({len(panels)})",
            [(p.get("title", "Untitled"), p.get("type", "unknown")) for p in panels],
        ),
    ]

    out.detail(
        f"Dashboard: {dashboard.get('title', uid)}",
        sections,
        data_for_json=result,
    )


@app.command("export")
def export_dashboard(
    ctx: typer.Context,
    uid: Annotated[str, typer.Argument(help="Dashboard UID")],
    output_file: Annotated[str | None, typer.Option("--output", "-o", help="Output file path")] = None,
) -> None:
    """Export dashboard JSON to file."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    result = client.get(f"/dashboards/uid/{uid}")
    dashboard = result.get("dashboard", {})
    title = dashboard.get("title", uid).replace(" ", "-").replace("/", "-").lower()

    if output_file is None:
        output_file = f"{title}-{uid}.json"

    # Clean for export (remove id so it can be imported fresh)
    export_data = {
        "dashboard": dashboard,
        "overwrite": True,
        "message": f"Exported from kctl-grafana",
    }
    # Remove the internal id for portability
    export_data["dashboard"].pop("id", None)

    path = Path(output_file)
    path.write_text(json.dumps(export_data, indent=2))
    out.success(f"Dashboard exported to {path}")


@app.command("import")
def import_dashboard(
    ctx: typer.Context,
    file_path: Annotated[str, typer.Argument(help="JSON file to import")],
    folder_uid: Annotated[str | None, typer.Option("--folder", help="Target folder UID")] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite", help="Overwrite existing")] = True,
) -> None:
    """Import dashboard from JSON file."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    path = Path(file_path)
    if not path.exists():
        out.error(f"File not found: {path}")
        raise typer.Exit(1)

    data = json.loads(path.read_text())

    # Handle both raw dashboard JSON and export format
    if "dashboard" in data:
        payload = data
    else:
        payload = {"dashboard": data}

    payload["overwrite"] = overwrite
    if folder_uid:
        payload["folderUid"] = folder_uid

    # Remove id for fresh import
    payload.get("dashboard", {}).pop("id", None)

    result = client.post("/dashboards/db", json_body=payload)
    out.success(f"Dashboard imported: {result.get('slug', 'unknown')} (uid: {result.get('uid', 'unknown')})")
    out.kv("URL", result.get("url", ""))


@app.command("search")
def search_dashboards(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Search query")],
) -> None:
    """Search dashboards by name or tag."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    results = client.get("/search", params={"query": query, "type": "dash-db"})

    rows: list[list[str]] = []
    for d in results:
        uid = d.get("uid", "")
        title = d.get("title", "")
        folder = d.get("folderTitle", "General")
        tags = ", ".join(d.get("tags", []))
        rows.append([uid, title, folder, tags])

    out.table(
        f"Search results for '{query}' ({len(results)})",
        [("UID", "cyan"), ("Title", ""), ("Folder", "dim"), ("Tags", "dim")],
        rows,
        data_for_json=results,
    )


@app.command("star")
def star_dashboard(
    ctx: typer.Context,
    uid: Annotated[str, typer.Argument(help="Dashboard UID")],
    unstar: Annotated[bool, typer.Option("--unstar", help="Remove star")] = False,
) -> None:
    """Star or unstar a dashboard."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    # First get the dashboard id from uid
    result = client.get(f"/dashboards/uid/{uid}")
    dash_id = result.get("dashboard", {}).get("id")

    if not dash_id:
        out.error(f"Dashboard not found: {uid}")
        raise typer.Exit(1)

    if unstar:
        client.delete(f"/user/stars/dashboard/{dash_id}")
        out.success(f"Unstarred dashboard {uid}")
    else:
        client.post(f"/user/stars/dashboard/{dash_id}", json_body={})
        out.success(f"Starred dashboard {uid}")
```

- [ ] **Step 2: Create `cli/tests/test_dashboard.py`**

```python
"""Tests for dashboard commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_grafana.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.org_id = 1
    return client


class TestDashboardList:
    def test_list_dashboards(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [
            {"uid": "abc123", "title": "Overview", "folderTitle": "General", "tags": ["prod"], "isStarred": False},
            {"uid": "def456", "title": "Node Exporter", "folderTitle": "Infra", "tags": [], "isStarred": True},
        ]

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "dashboard", "list"])

        assert result.exit_code == 0
        mock_client.get.assert_called_with("/search", params={"type": "dash-db", "limit": 5000})


class TestDashboardShow:
    def test_show_dashboard(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "meta": {"created": "2024-01-01", "updated": "2024-06-01", "createdBy": "admin", "updatedBy": "admin", "folderTitle": "General", "url": "/d/abc123"},
            "dashboard": {"uid": "abc123", "title": "Overview", "version": 5, "panels": [{"title": "CPU", "type": "graph"}]},
        }

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "dashboard", "show", "abc123"])

        assert result.exit_code == 0


class TestDashboardExport:
    def test_export_dashboard(self, runner: CliRunner, mock_client: MagicMock, tmp_path) -> None:
        mock_client.get.return_value = {
            "meta": {},
            "dashboard": {"uid": "abc123", "title": "Test Dashboard", "id": 42, "panels": []},
        }
        output_file = str(tmp_path / "test.json")

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "dashboard", "export", "abc123", "--output", output_file])

        assert result.exit_code == 0
        import json
        from pathlib import Path
        exported = json.loads(Path(output_file).read_text())
        assert "dashboard" in exported
        assert "id" not in exported["dashboard"]  # id removed for portability


class TestDashboardImport:
    def test_import_dashboard(self, runner: CliRunner, mock_client: MagicMock, tmp_path) -> None:
        import json

        dashboard_file = tmp_path / "dash.json"
        dashboard_file.write_text(json.dumps({
            "dashboard": {"uid": "new123", "title": "Imported", "panels": []},
        }))

        mock_client.post.return_value = {"slug": "imported", "uid": "new123", "url": "/d/new123"}

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "dashboard", "import", str(dashboard_file)])

        assert result.exit_code == 0
        mock_client.post.assert_called_once()


class TestDashboardSearch:
    def test_search_dashboards(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [
            {"uid": "abc123", "title": "CPU Overview", "folderTitle": "General", "tags": []},
        ]

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "dashboard", "search", "CPU"])

        assert result.exit_code == 0
```

- [ ] **Step 3: Run tests**

```bash
cd cli && uv run pytest tests/test_dashboard.py -v --tb=short
```

- [ ] **Step 4: Commit**

```bash
git add cli/src/kctl_grafana/commands/dashboard.py cli/tests/test_dashboard.py
git commit -m "feat: add dashboard commands (list/show/export/import/search/star)"
```

---

### Task 4: Implement datasource commands

**Files to create:**
- `cli/src/kctl_grafana/commands/datasource.py`
- `cli/tests/test_datasource.py`

- [ ] **Step 1: Create `cli/src/kctl_grafana/commands/datasource.py`**

```python
"""Datasource management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_grafana.core.callbacks import AppContext

app = typer.Typer(help="Datasource management.")


@app.command("list")
def list_datasources(ctx: typer.Context) -> None:
    """List all datasources with type and status."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    datasources = client.get("/datasources")

    rows: list[list[str]] = []
    for ds in datasources:
        uid = ds.get("uid", "")
        name = ds.get("name", "")
        ds_type = ds.get("type", "")
        url = ds.get("url", "")
        is_default = "[green]*[/green]" if ds.get("isDefault") else ""
        rows.append([uid, name, ds_type, url, is_default])

    out.table(
        f"Datasources ({len(datasources)})",
        [("UID", "cyan"), ("Name", ""), ("Type", ""), ("URL", "dim"), ("Default", "")],
        rows,
        data_for_json=datasources,
    )


@app.command("show")
def show_datasource(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Datasource name")],
) -> None:
    """Show datasource configuration details."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    ds = client.get(f"/datasources/name/{name}")

    sections = [
        (
            "Datasource",
            [
                ("UID", ds.get("uid", "")),
                ("Name", ds.get("name", "")),
                ("Type", ds.get("type", "")),
                ("URL", ds.get("url", "")),
                ("Database", ds.get("database", "")),
                ("Default", str(ds.get("isDefault", False))),
                ("Read-only", str(ds.get("readOnly", False))),
                ("Access", ds.get("access", "")),
            ],
        ),
    ]

    json_data = ds.get("jsonData", {})
    if json_data:
        sections.append(
            (
                "JSON Data",
                [(k, str(v)) for k, v in json_data.items()],
            )
        )

    out.detail(
        f"Datasource: {name}",
        sections,
        data_for_json=ds,
    )


@app.command("test")
def test_datasource(
    ctx: typer.Context,
    name: Annotated[str | None, typer.Argument(help="Datasource name (tests all if omitted)")] = None,
) -> None:
    """Test datasource connectivity. Tests all datasources if no name given."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    if name:
        # Test single datasource
        ds = client.get(f"/datasources/name/{name}")
        ds_uid = ds.get("uid", "")
        try:
            result = client.post(f"/datasources/uid/{ds_uid}/health", json_body={})
            status = result.get("status", "unknown")
            if status == "OK":
                out.success(f"Datasource '{name}' is healthy")
            else:
                out.error(f"Datasource '{name}' health: {status} — {result.get('message', '')}")
                raise typer.Exit(1)
        except Exception as e:
            out.error(f"Datasource '{name}' test failed: {e}")
            raise typer.Exit(1)
    else:
        # Test all datasources
        datasources = client.get("/datasources")
        rows: list[list[str]] = []
        all_ok = True

        for ds in datasources:
            ds_uid = ds.get("uid", "")
            ds_name = ds.get("name", "unknown")
            ds_type = ds.get("type", "unknown")

            try:
                result = client.post(f"/datasources/uid/{ds_uid}/health", json_body={})
                status = result.get("status", "unknown")
                message = result.get("message", "")
                if status == "OK":
                    status_display = "[green]OK[/green]"
                else:
                    status_display = f"[red]{status}[/red]"
                    all_ok = False
            except Exception as e:
                status_display = "[red]ERROR[/red]"
                message = str(e)
                all_ok = False

            rows.append([ds_name, ds_type, status_display, message])

        out.table(
            f"Datasource Health ({len(datasources)})",
            [("Name", ""), ("Type", "dim"), ("Status", ""), ("Message", "dim")],
            rows,
        )

        if all_ok:
            out.success("All datasources healthy")
        else:
            out.warn("Some datasources have issues")
            raise typer.Exit(1)
```

- [ ] **Step 2: Create `cli/tests/test_datasource.py`**

```python
"""Tests for datasource commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_grafana.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.org_id = 1
    return client


class TestDatasourceList:
    def test_list_datasources(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [
            {"uid": "prom1", "name": "Prometheus", "type": "prometheus", "url": "http://prometheus:9090", "isDefault": True},
            {"uid": "loki1", "name": "Loki", "type": "loki", "url": "http://loki:3100", "isDefault": False},
        ]

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "datasource", "list"])

        assert result.exit_code == 0
        mock_client.get.assert_called_with("/datasources")


class TestDatasourceShow:
    def test_show_datasource(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "uid": "prom1",
            "name": "Prometheus",
            "type": "prometheus",
            "url": "http://prometheus:9090",
            "database": "",
            "isDefault": True,
            "readOnly": False,
            "access": "proxy",
            "jsonData": {"httpMethod": "POST"},
        }

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "datasource", "show", "Prometheus"])

        assert result.exit_code == 0


class TestDatasourceTest:
    def test_test_single_datasource_ok(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"uid": "prom1", "name": "Prometheus"}
        mock_client.post.return_value = {"status": "OK", "message": ""}

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "datasource", "test", "Prometheus"])

        assert result.exit_code == 0

    def test_test_all_datasources(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [
            {"uid": "prom1", "name": "Prometheus", "type": "prometheus"},
            {"uid": "loki1", "name": "Loki", "type": "loki"},
        ]
        mock_client.post.return_value = {"status": "OK", "message": ""}

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "datasource", "test"])

        assert result.exit_code == 0
```

- [ ] **Step 3: Run tests**

```bash
cd cli && uv run pytest tests/test_datasource.py -v --tb=short
```

- [ ] **Step 4: Commit**

```bash
git add cli/src/kctl_grafana/commands/datasource.py cli/tests/test_datasource.py
git commit -m "feat: add datasource commands (list/show/test)"
```

---

### Task 5: Implement alert commands

**Files to create:**
- `cli/src/kctl_grafana/commands/alert.py`
- `cli/tests/test_alert.py`

- [ ] **Step 1: Create `cli/src/kctl_grafana/commands/alert.py`**

```python
"""Alert management commands."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

import typer

from kctl_grafana.core.callbacks import AppContext

app = typer.Typer(help="Alert rule management.")


@app.command("list")
def list_alerts(ctx: typer.Context) -> None:
    """List alert rules with current state."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    rules = client.get("/v1/provisioning/alert-rules")

    rows: list[list[str]] = []
    for rule in rules:
        uid = rule.get("uid", "")
        title = rule.get("title", "")
        folder = rule.get("folderUID", "")
        rule_group = rule.get("ruleGroup", "")
        for_duration = rule.get("for", "")

        # Determine state from labels/annotations if available
        state = rule.get("labels", {}).get("severity", "")
        rows.append([uid, title, folder, rule_group, for_duration, state])

    out.table(
        f"Alert Rules ({len(rules)})",
        [("UID", "cyan"), ("Title", ""), ("Folder", "dim"), ("Group", "dim"), ("For", ""), ("Severity", "")],
        rows,
        data_for_json=rules,
    )


@app.command("show")
def show_alert(
    ctx: typer.Context,
    uid: Annotated[str, typer.Argument(help="Alert rule UID")],
) -> None:
    """Show alert rule details."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    rule = client.get(f"/v1/provisioning/alert-rules/{uid}")

    labels = rule.get("labels", {})
    annotations = rule.get("annotations", {})

    sections = [
        (
            "Alert Rule",
            [
                ("UID", rule.get("uid", "")),
                ("Title", rule.get("title", "")),
                ("Folder UID", rule.get("folderUID", "")),
                ("Group", rule.get("ruleGroup", "")),
                ("For", rule.get("for", "")),
                ("Condition", rule.get("condition", "")),
                ("No Data State", rule.get("noDataState", "")),
                ("Exec Error State", rule.get("execErrState", "")),
                ("Updated", rule.get("updated", "")),
                ("Provisioned", str(rule.get("provenance", "") != "")),
            ],
        ),
    ]

    if labels:
        sections.append(("Labels", [(k, v) for k, v in labels.items()]))

    if annotations:
        sections.append(("Annotations", [(k, v) for k, v in annotations.items()]))

    out.detail(
        f"Alert Rule: {rule.get('title', uid)}",
        sections,
        data_for_json=rule,
    )


@app.command("silence")
def silence_alert(
    ctx: typer.Context,
    uid: Annotated[str, typer.Argument(help="Alert rule UID")],
    duration: Annotated[str, typer.Option("--duration", "-d", help="Silence duration (e.g., 1h, 30m, 2d)")] = "1h",
    comment: Annotated[str, typer.Option("--comment", "-c", help="Silence comment")] = "Silenced via kctl-grafana",
) -> None:
    """Silence an alert rule for a given duration."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    # Parse duration
    now = datetime.now(timezone.utc)
    if duration.endswith("h"):
        delta = timedelta(hours=int(duration[:-1]))
    elif duration.endswith("m"):
        delta = timedelta(minutes=int(duration[:-1]))
    elif duration.endswith("d"):
        delta = timedelta(days=int(duration[:-1]))
    else:
        out.error(f"Invalid duration format: {duration}. Use 1h, 30m, or 2d.")
        raise typer.Exit(1)

    ends_at = now + delta

    # Get the alert rule to extract labels for matching
    rule = client.get(f"/v1/provisioning/alert-rules/{uid}")
    rule_title = rule.get("title", uid)

    # Create silence
    silence_payload = {
        "matchers": [
            {
                "name": "alertname",
                "value": rule_title,
                "isRegex": False,
                "isEqual": True,
            }
        ],
        "startsAt": now.isoformat(),
        "endsAt": ends_at.isoformat(),
        "createdBy": "kctl-grafana",
        "comment": comment,
    }

    result = client.post("/alertmanager/grafana/api/v2/silences", json_body=silence_payload)
    silence_id = result.get("silenceID", "unknown")
    out.success(f"Alert '{rule_title}' silenced for {duration} (silence ID: {silence_id})")


@app.command("contacts")
def list_contacts(ctx: typer.Context) -> None:
    """List notification contact points."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    contacts = client.get("/v1/provisioning/contact-points")

    rows: list[list[str]] = []
    for cp in contacts:
        name = cp.get("name", "")
        cp_type = cp.get("type", "")
        uid = cp.get("uid", "")
        provisioned = "[green]yes[/green]" if cp.get("provenance", "") else "[dim]no[/dim]"
        rows.append([uid, name, cp_type, provisioned])

    out.table(
        f"Contact Points ({len(contacts)})",
        [("UID", "cyan"), ("Name", ""), ("Type", ""), ("Provisioned", "")],
        rows,
        data_for_json=contacts,
    )
```

- [ ] **Step 2: Create `cli/tests/test_alert.py`**

```python
"""Tests for alert commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_grafana.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.org_id = 1
    return client


class TestAlertList:
    def test_list_alerts(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [
            {"uid": "rule1", "title": "High CPU", "folderUID": "infra", "ruleGroup": "cpu", "for": "5m", "labels": {"severity": "critical"}},
            {"uid": "rule2", "title": "Low Disk", "folderUID": "infra", "ruleGroup": "disk", "for": "10m", "labels": {"severity": "warning"}},
        ]

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "alert", "list"])

        assert result.exit_code == 0


class TestAlertShow:
    def test_show_alert(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "uid": "rule1",
            "title": "High CPU",
            "folderUID": "infra",
            "ruleGroup": "cpu",
            "for": "5m",
            "condition": "B",
            "noDataState": "NoData",
            "execErrState": "Error",
            "updated": "2024-01-01T00:00:00Z",
            "provenance": "",
            "labels": {"severity": "critical"},
            "annotations": {"summary": "CPU usage above 90%"},
        }

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "alert", "show", "rule1"])

        assert result.exit_code == 0


class TestAlertSilence:
    def test_silence_alert(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"uid": "rule1", "title": "High CPU"}
        mock_client.post.return_value = {"silenceID": "silence-abc"}

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "alert", "silence", "rule1", "--duration", "2h"])

        assert result.exit_code == 0
        mock_client.post.assert_called_once()


class TestAlertContacts:
    def test_list_contacts(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [
            {"uid": "cp1", "name": "Telegram", "type": "telegram", "provenance": "file"},
            {"uid": "cp2", "name": "Email", "type": "email", "provenance": ""},
        ]

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "alert", "contacts"])

        assert result.exit_code == 0
```

- [ ] **Step 3: Run tests**

```bash
cd cli && uv run pytest tests/test_alert.py -v --tb=short
```

- [ ] **Step 4: Commit**

```bash
git add cli/src/kctl_grafana/commands/alert.py cli/tests/test_alert.py
git commit -m "feat: add alert commands (list/show/silence/contacts)"
```

---

### Task 6: Implement folder, annotation, user commands

**Files to create:**
- `cli/src/kctl_grafana/commands/folder.py`
- `cli/src/kctl_grafana/commands/annotation.py`
- `cli/src/kctl_grafana/commands/user.py`
- `cli/tests/test_folder.py`
- `cli/tests/test_annotation.py`
- `cli/tests/test_user.py`

- [ ] **Step 1: Create `cli/src/kctl_grafana/commands/folder.py`**

```python
"""Folder management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_grafana.core.callbacks import AppContext

app = typer.Typer(help="Folder organization.")


@app.command("list")
def list_folders(ctx: typer.Context) -> None:
    """List all folders."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    folders = client.get("/folders")

    rows: list[list[str]] = []
    for f in folders:
        uid = f.get("uid", "")
        title = f.get("title", "")
        folder_id = str(f.get("id", ""))
        url = f.get("url", "")
        rows.append([uid, title, folder_id, url])

    out.table(
        f"Folders ({len(folders)})",
        [("UID", "cyan"), ("Title", ""), ("ID", "dim"), ("URL", "dim")],
        rows,
        data_for_json=folders,
    )


@app.command("create")
def create_folder(
    ctx: typer.Context,
    title: Annotated[str, typer.Argument(help="Folder name")],
    uid: Annotated[str | None, typer.Option("--uid", help="Custom UID (auto-generated if omitted)")] = None,
) -> None:
    """Create a new folder."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    payload: dict = {"title": title}
    if uid:
        payload["uid"] = uid

    result = client.post("/folders", json_body=payload)
    out.success(f"Folder created: {result.get('title', title)} (uid: {result.get('uid', '')})")


@app.command("delete")
def delete_folder(
    ctx: typer.Context,
    uid: Annotated[str, typer.Argument(help="Folder UID")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete a folder and all its dashboards."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    if not force:
        typer.confirm(f"Delete folder '{uid}' and ALL its dashboards?", abort=True)

    client.delete(f"/folders/{uid}")
    out.success(f"Folder '{uid}' deleted")
```

- [ ] **Step 2: Create `cli/src/kctl_grafana/commands/annotation.py`**

```python
"""Annotation commands for deploy markers and events."""

from __future__ import annotations

import time
from typing import Annotated

import typer

from kctl_grafana.core.callbacks import AppContext

app = typer.Typer(help="Annotation management (deploy markers, events).")


@app.command("add")
def add_annotation(
    ctx: typer.Context,
    text: Annotated[str, typer.Argument(help="Annotation text")],
    tags: Annotated[str | None, typer.Option("--tags", "-t", help="Comma-separated tags")] = None,
    dashboard_uid: Annotated[str | None, typer.Option("--dashboard", help="Dashboard UID (global if omitted)")] = None,
) -> None:
    """Add an annotation (useful for deploy markers)."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    payload: dict = {
        "text": text,
        "time": int(time.time() * 1000),  # Grafana expects milliseconds
    }

    if tags:
        payload["tags"] = [t.strip() for t in tags.split(",")]

    if dashboard_uid:
        # Resolve dashboard id from uid
        try:
            result = client.get(f"/dashboards/uid/{dashboard_uid}")
            dash_id = result.get("dashboard", {}).get("id")
            if dash_id:
                payload["dashboardId"] = dash_id
        except Exception:
            out.warn(f"Could not resolve dashboard '{dashboard_uid}', creating global annotation")

    result = client.post("/annotations", json_body=payload)
    out.success(f"Annotation created (id: {result.get('id', 'unknown')})")


@app.command("list")
def list_annotations(
    ctx: typer.Context,
    from_time: Annotated[str | None, typer.Option("--from", help="Start time (epoch ms or relative: 1h, 24h, 7d)")] = None,
    to_time: Annotated[str | None, typer.Option("--to", help="End time (epoch ms or 'now')")] = None,
    tags: Annotated[str | None, typer.Option("--tags", "-t", help="Filter by tags (comma-separated)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 100,
) -> None:
    """List recent annotations."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    params: dict = {"limit": limit}

    if from_time:
        params["from"] = _parse_time(from_time)
    else:
        # Default: last 24h
        params["from"] = int((time.time() - 86400) * 1000)

    if to_time:
        params["to"] = _parse_time(to_time)
    else:
        params["to"] = int(time.time() * 1000)

    if tags:
        params["tags"] = tags

    annotations = client.get("/annotations", params=params)

    rows: list[list[str]] = []
    for a in annotations:
        ann_id = str(a.get("id", ""))
        text = a.get("text", "")[:60]
        ann_tags = ", ".join(a.get("tags", []))
        created = a.get("created", "")
        dashboard = a.get("dashboardUID", "global")
        rows.append([ann_id, text, ann_tags, dashboard, str(created)])

    out.table(
        f"Annotations ({len(annotations)})",
        [("ID", "cyan"), ("Text", ""), ("Tags", "dim"), ("Dashboard", "dim"), ("Created", "dim")],
        rows,
        data_for_json=annotations,
    )


def _parse_time(value: str) -> int:
    """Parse time value: epoch ms, or relative (1h, 24h, 7d)."""
    try:
        return int(value)
    except ValueError:
        pass

    now = time.time()
    if value == "now":
        return int(now * 1000)

    if value.endswith("h"):
        hours = int(value[:-1])
        return int((now - hours * 3600) * 1000)
    elif value.endswith("d"):
        days = int(value[:-1])
        return int((now - days * 86400) * 1000)
    elif value.endswith("m"):
        minutes = int(value[:-1])
        return int((now - minutes * 60) * 1000)

    return int(now * 1000)
```

- [ ] **Step 3: Create `cli/src/kctl_grafana/commands/user.py`**

```python
"""User management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_grafana.core.callbacks import AppContext

app = typer.Typer(help="Organization user management.")


@app.command("list")
def list_users(ctx: typer.Context) -> None:
    """List organization users."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    users = client.get("/org/users")

    rows: list[list[str]] = []
    for u in users:
        user_id = str(u.get("userId", ""))
        login = u.get("login", "")
        email = u.get("email", "")
        role = u.get("role", "")
        last_seen = u.get("lastSeenAt", "")
        rows.append([user_id, login, email, role, last_seen])

    out.table(
        f"Organization Users ({len(users)})",
        [("ID", "cyan"), ("Login", ""), ("Email", ""), ("Role", ""), ("Last Seen", "dim")],
        rows,
        data_for_json=users,
    )


@app.command("add")
def add_user(
    ctx: typer.Context,
    email: Annotated[str, typer.Argument(help="User email address")],
    role: Annotated[str, typer.Option("--role", "-r", help="Role: Viewer, Editor, Admin")] = "Viewer",
) -> None:
    """Add a user to the organization."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    valid_roles = {"Viewer", "Editor", "Admin"}
    if role not in valid_roles:
        out.error(f"Invalid role: {role}. Must be one of: {', '.join(valid_roles)}")
        raise typer.Exit(1)

    payload = {
        "loginOrEmail": email,
        "role": role,
    }

    result = client.post("/org/users", json_body=payload)
    out.success(f"User '{email}' added as {role} (message: {result.get('message', 'ok')})")
```

- [ ] **Step 4: Create `cli/tests/test_folder.py`**

```python
"""Tests for folder commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_grafana.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.org_id = 1
    return client


class TestFolderList:
    def test_list_folders(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [
            {"uid": "infra", "title": "Infrastructure", "id": 1, "url": "/dashboards/f/infra"},
            {"uid": "apps", "title": "Applications", "id": 2, "url": "/dashboards/f/apps"},
        ]

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "folder", "list"])

        assert result.exit_code == 0


class TestFolderCreate:
    def test_create_folder(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"uid": "new-folder", "title": "New Folder"}

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "folder", "create", "New Folder"])

        assert result.exit_code == 0
        mock_client.post.assert_called_once()


class TestFolderDelete:
    def test_delete_folder_force(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.delete.return_value = {"message": "Folder deleted"}

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "folder", "delete", "infra", "--force"])

        assert result.exit_code == 0
        mock_client.delete.assert_called_with("/folders/infra")
```

- [ ] **Step 5: Create `cli/tests/test_annotation.py`**

```python
"""Tests for annotation commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_grafana.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.org_id = 1
    return client


class TestAnnotationAdd:
    def test_add_annotation(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"id": 42, "message": "Annotation added"}

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, [
                    "--url", "https://grafana.kodeme.io", "--api-key", "key",
                    "annotation", "add", "Deploy v1.2.3", "--tags", "deploy,production",
                ])

        assert result.exit_code == 0
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[1]["json_body"]["text"] == "Deploy v1.2.3"
        assert call_args[1]["json_body"]["tags"] == ["deploy", "production"]


class TestAnnotationList:
    def test_list_annotations(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [
            {"id": 1, "text": "Deploy v1.2.3", "tags": ["deploy"], "dashboardUID": "global", "created": 1700000000000},
            {"id": 2, "text": "Config change", "tags": ["config"], "dashboardUID": "abc", "created": 1700001000000},
        ]

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "annotation", "list"])

        assert result.exit_code == 0
```

- [ ] **Step 6: Create `cli/tests/test_user.py`**

```python
"""Tests for user commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_grafana.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.org_id = 1
    return client


class TestUserList:
    def test_list_users(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [
            {"userId": 1, "login": "admin", "email": "admin@kodeme.io", "role": "Admin", "lastSeenAt": "2024-01-01"},
            {"userId": 2, "login": "viewer", "email": "viewer@kodeme.io", "role": "Viewer", "lastSeenAt": "2024-06-01"},
        ]

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "user", "list"])

        assert result.exit_code == 0


class TestUserAdd:
    def test_add_user(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"message": "User added to organization"}

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, [
                    "--url", "https://grafana.kodeme.io", "--api-key", "key",
                    "user", "add", "newuser@kodeme.io", "--role", "Editor",
                ])

        assert result.exit_code == 0
        mock_client.post.assert_called_once()

    def test_add_user_invalid_role(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, [
                    "--url", "https://grafana.kodeme.io", "--api-key", "key",
                    "user", "add", "user@test.com", "--role", "SuperAdmin",
                ])

        assert result.exit_code == 1
```

- [ ] **Step 7: Run tests**

```bash
cd cli && uv run pytest tests/test_folder.py tests/test_annotation.py tests/test_user.py -v --tb=short
```

- [ ] **Step 8: Commit**

```bash
git add cli/src/kctl_grafana/commands/folder.py cli/src/kctl_grafana/commands/annotation.py cli/src/kctl_grafana/commands/user.py cli/tests/test_folder.py cli/tests/test_annotation.py cli/tests/test_user.py
git commit -m "feat: add folder, annotation, and user commands"
```

---

### Task 7: Implement backup commands

**Files to create:**
- `cli/src/kctl_grafana/commands/backup.py`
- `cli/tests/test_backup.py`

- [ ] **Step 1: Create `cli/src/kctl_grafana/commands/backup.py`**

```python
"""Backup and restore commands."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer

from kctl_grafana.core.callbacks import AppContext

app = typer.Typer(help="Backup and restore dashboards and datasources.")


@app.command("create")
def create_backup(
    ctx: typer.Context,
    output_dir: Annotated[str | None, typer.Option("--output", "-o", help="Output directory")] = None,
) -> None:
    """Export all dashboards and datasources to a backup directory."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    if output_dir is None:
        output_dir = f"grafana-backup-{timestamp}"

    backup_path = Path(output_dir)
    dashboards_path = backup_path / "dashboards"
    datasources_path = backup_path / "datasources"
    dashboards_path.mkdir(parents=True, exist_ok=True)
    datasources_path.mkdir(parents=True, exist_ok=True)

    # Export dashboards
    out.info("Exporting dashboards...")
    dashboards = client.get("/search", params={"type": "dash-db", "limit": 5000})
    dashboard_count = 0

    for dash in dashboards:
        uid = dash.get("uid", "")
        if not uid:
            continue
        try:
            result = client.get(f"/dashboards/uid/{uid}")
            dashboard_data = result.get("dashboard", {})
            dashboard_data.pop("id", None)  # Remove id for portability

            export_data = {
                "dashboard": dashboard_data,
                "meta": result.get("meta", {}),
                "overwrite": True,
            }

            title_slug = dash.get("title", uid).replace(" ", "-").replace("/", "-").lower()
            file_path = dashboards_path / f"{title_slug}-{uid}.json"
            file_path.write_text(json.dumps(export_data, indent=2))
            dashboard_count += 1
        except Exception as e:
            out.warn(f"Failed to export dashboard '{dash.get('title', uid)}': {e}")

    # Export datasources
    out.info("Exporting datasources...")
    datasources = client.get("/datasources")
    datasource_count = 0

    for ds in datasources:
        ds_name = ds.get("name", "unknown")
        try:
            # Remove sensitive fields
            safe_ds = dict(ds)
            safe_ds.pop("secureJsonFields", None)
            safe_ds.pop("secureJsonData", None)
            safe_ds.pop("id", None)

            name_slug = ds_name.replace(" ", "-").replace("/", "-").lower()
            file_path = datasources_path / f"{name_slug}.json"
            file_path.write_text(json.dumps(safe_ds, indent=2))
            datasource_count += 1
        except Exception as e:
            out.warn(f"Failed to export datasource '{ds_name}': {e}")

    # Write manifest
    manifest = {
        "created_at": timestamp,
        "grafana_version": client.get_version(),
        "dashboards": dashboard_count,
        "datasources": datasource_count,
    }
    (backup_path / "manifest.json").write_text(json.dumps(manifest, indent=2))

    out.success(f"Backup created: {backup_path}")
    out.kv("Dashboards", str(dashboard_count))
    out.kv("Datasources", str(datasource_count))


@app.command("restore")
def restore_backup(
    ctx: typer.Context,
    backup_dir: Annotated[str, typer.Argument(help="Backup directory to restore from")],
    skip_datasources: Annotated[bool, typer.Option("--skip-datasources", help="Skip datasource restore")] = False,
    skip_dashboards: Annotated[bool, typer.Option("--skip-dashboards", help="Skip dashboard restore")] = False,
) -> None:
    """Restore dashboards and datasources from a backup directory."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    backup_path = Path(backup_dir)
    if not backup_path.exists():
        out.error(f"Backup directory not found: {backup_path}")
        raise typer.Exit(1)

    manifest_path = backup_path / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        out.info(f"Restoring backup from {manifest.get('created_at', 'unknown')} (Grafana v{manifest.get('grafana_version', 'unknown')})")

    # Restore datasources first (dashboards may depend on them)
    ds_restored = 0
    if not skip_datasources:
        datasources_path = backup_path / "datasources"
        if datasources_path.exists():
            out.info("Restoring datasources...")
            for ds_file in sorted(datasources_path.glob("*.json")):
                try:
                    ds_data = json.loads(ds_file.read_text())
                    ds_name = ds_data.get("name", ds_file.stem)

                    # Check if datasource already exists
                    try:
                        existing = client.get(f"/datasources/name/{ds_name}")
                        # Update existing
                        ds_data["id"] = existing.get("id")
                        client.put(f"/datasources/{existing.get('id')}", json_body=ds_data)
                        out.info(f"  Updated datasource: {ds_name}")
                    except Exception:
                        # Create new
                        client.post("/datasources", json_body=ds_data)
                        out.info(f"  Created datasource: {ds_name}")

                    ds_restored += 1
                except Exception as e:
                    out.warn(f"  Failed to restore datasource from {ds_file.name}: {e}")

    # Restore dashboards
    dash_restored = 0
    if not skip_dashboards:
        dashboards_path = backup_path / "dashboards"
        if dashboards_path.exists():
            out.info("Restoring dashboards...")
            for dash_file in sorted(dashboards_path.glob("*.json")):
                try:
                    dash_data = json.loads(dash_file.read_text())

                    # Ensure proper import format
                    if "dashboard" in dash_data:
                        payload = dash_data
                    else:
                        payload = {"dashboard": dash_data}

                    payload["overwrite"] = True
                    payload.get("dashboard", {}).pop("id", None)

                    result = client.post("/dashboards/db", json_body=payload)
                    title = payload.get("dashboard", {}).get("title", dash_file.stem)
                    out.info(f"  Restored dashboard: {title}")
                    dash_restored += 1
                except Exception as e:
                    out.warn(f"  Failed to restore dashboard from {dash_file.name}: {e}")

    out.success("Restore complete")
    out.kv("Datasources restored", str(ds_restored))
    out.kv("Dashboards restored", str(dash_restored))
```

- [ ] **Step 2: Create `cli/tests/test_backup.py`**

```python
"""Tests for backup commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_grafana.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.org_id = 1
    client.get_version.return_value = "11.4.0"
    return client


class TestBackupCreate:
    def test_backup_create(self, runner: CliRunner, mock_client: MagicMock, tmp_path) -> None:
        output_dir = str(tmp_path / "backup")

        mock_client.get.side_effect = lambda path, **kw: {
            "/search": [{"uid": "dash1", "title": "Overview"}],
            "/dashboards/uid/dash1": {
                "dashboard": {"uid": "dash1", "title": "Overview", "id": 1, "panels": []},
                "meta": {},
            },
            "/datasources": [{"uid": "prom1", "name": "Prometheus", "type": "prometheus", "url": "http://prometheus:9090"}],
        }.get(path, [])

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, [
                    "--url", "https://grafana.kodeme.io", "--api-key", "key",
                    "backup", "create", "--output", output_dir,
                ])

        assert result.exit_code == 0
        assert (Path(output_dir) / "manifest.json").exists()
        assert (Path(output_dir) / "dashboards").is_dir()
        assert (Path(output_dir) / "datasources").is_dir()


class TestBackupRestore:
    def test_backup_restore(self, runner: CliRunner, mock_client: MagicMock, tmp_path) -> None:
        # Create a mock backup directory
        backup_dir = tmp_path / "backup"
        (backup_dir / "dashboards").mkdir(parents=True)
        (backup_dir / "datasources").mkdir(parents=True)

        manifest = {"created_at": "20240101-120000", "grafana_version": "11.4.0", "dashboards": 1, "datasources": 1}
        (backup_dir / "manifest.json").write_text(json.dumps(manifest))

        dash_data = {"dashboard": {"uid": "dash1", "title": "Overview", "panels": []}, "overwrite": True}
        (backup_dir / "dashboards" / "overview-dash1.json").write_text(json.dumps(dash_data))

        ds_data = {"uid": "prom1", "name": "Prometheus", "type": "prometheus", "url": "http://prometheus:9090"}
        (backup_dir / "datasources" / "prometheus.json").write_text(json.dumps(ds_data))

        # Datasource does not exist yet
        mock_client.get.side_effect = Exception("Not found")
        mock_client.post.return_value = {"slug": "overview", "uid": "dash1", "url": "/d/dash1"}

        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, [
                    "--url", "https://grafana.kodeme.io", "--api-key", "key",
                    "backup", "restore", str(backup_dir),
                ])

        assert result.exit_code == 0

    def test_backup_restore_missing_dir(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)):
            with patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client):
                result = runner.invoke(app, [
                    "--url", "https://grafana.kodeme.io", "--api-key", "key",
                    "backup", "restore", "/nonexistent/path",
                ])

        assert result.exit_code == 1
```

- [ ] **Step 3: Run tests**

```bash
cd cli && uv run pytest tests/test_backup.py -v --tb=short
```

- [ ] **Step 4: Commit**

```bash
git add cli/src/kctl_grafana/commands/backup.py cli/tests/test_backup.py
git commit -m "feat: add backup create and restore commands"
```

---

### Task 8: Implement selftest + update CLAUDE.md + CI

**Files to create/modify:**
- `cli/src/kctl_grafana/commands/selftest.py`
- `CLAUDE.md` (modify)
- `.github/workflows/validate.yml`

- [ ] **Step 1: Create `cli/src/kctl_grafana/commands/selftest.py`**

```python
"""Self-test diagnostic command."""

from __future__ import annotations

import typer

from kctl_grafana.core.callbacks import AppContext

app = typer.Typer(help="Self-test diagnostics.")


@app.command("run")
def run_selftest(ctx: typer.Context) -> None:
    """Run diagnostic checks for kctl-grafana."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    checks_passed = 0
    checks_failed = 0

    # Check 1: API connectivity
    out.header("Self-Test")

    out.info("Checking API connectivity...")
    health = client.check_health()
    if health.get("database") == "ok":
        out.success(f"API reachable — v{health.get('version', 'unknown')}")
        checks_passed += 1
    else:
        out.error(f"API unreachable: {health}")
        checks_failed += 1

    # Check 2: Organization info
    out.info("Checking organization...")
    try:
        org = client.get_org()
        out.success(f"Organization: {org.get('name', 'unknown')} (id: {org.get('id', 'unknown')})")
        checks_passed += 1
    except Exception as e:
        out.error(f"Cannot read organization: {e}")
        checks_failed += 1

    # Check 3: Datasource connectivity
    out.info("Checking datasources...")
    try:
        datasources = client.get("/datasources")
        ds_ok = 0
        ds_fail = 0
        for ds in datasources:
            ds_uid = ds.get("uid", "")
            try:
                result = client.post(f"/datasources/uid/{ds_uid}/health", json_body={})
                if result.get("status") == "OK":
                    ds_ok += 1
                else:
                    ds_fail += 1
            except Exception:
                ds_fail += 1

        if ds_fail == 0:
            out.success(f"All {ds_ok} datasources healthy")
            checks_passed += 1
        else:
            out.warn(f"{ds_ok}/{ds_ok + ds_fail} datasources healthy, {ds_fail} failing")
            checks_failed += 1
    except Exception as e:
        out.error(f"Cannot list datasources: {e}")
        checks_failed += 1

    # Check 4: Folders accessible
    out.info("Checking folders...")
    try:
        folders = client.get("/folders")
        out.success(f"{len(folders)} folders accessible")
        checks_passed += 1
    except Exception as e:
        out.error(f"Cannot list folders: {e}")
        checks_failed += 1

    # Check 5: Dashboards accessible
    out.info("Checking dashboards...")
    try:
        dashboards = client.get("/search", params={"type": "dash-db", "limit": 1})
        out.success("Dashboard search working")
        checks_passed += 1
    except Exception as e:
        out.error(f"Cannot search dashboards: {e}")
        checks_failed += 1

    # Summary
    out.header("Summary")
    total = checks_passed + checks_failed
    if checks_failed == 0:
        out.success(f"All {total} checks passed")
    else:
        out.error(f"{checks_failed}/{total} checks failed")
        raise typer.Exit(1)
```

- [ ] **Step 2: Update `CLAUDE.md`**

Add the following section after the existing `## Quick Start Commands` section in `CLAUDE.md`:

```markdown

## CLI (kctl-grafana)

The `cli/` directory contains a Python CLI for managing Grafana via its HTTP API.

### Quick Commands

```bash
cd cli
uv sync --all-extras
uv run pytest tests/ -v              # Run tests
uv run ruff check src/ tests/        # Lint
uv run ruff format src/ tests/       # Format
uv run mypy src/                     # Type check
```

### CLI Commands

| Command | Description |
|---------|-------------|
| `kctl-grafana health check` | API connectivity + version |
| `kctl-grafana health detailed` | API + all datasource health |
| `kctl-grafana status overview` | Dashboard/datasource/alert counts |
| `kctl-grafana dashboard list/show/export/import/search/star` | Dashboard management |
| `kctl-grafana datasource list/show/test` | Datasource management |
| `kctl-grafana alert list/show/silence/contacts` | Alert management |
| `kctl-grafana folder list/create/delete` | Folder organization |
| `kctl-grafana annotation add/list` | Deploy markers |
| `kctl-grafana user list/add` | User management |
| `kctl-grafana backup create/restore` | Backup/restore |
| `kctl-grafana selftest run` | Diagnostic checks |
| `kctl-grafana config init/show/use/remove/export/test` | Configuration |

### Configuration

```bash
kctl-grafana config init --url https://grafana.kodeme.io --api-key <key> --name kodemeio
```

Config stored in `~/.config/kodemeio/config.yaml` under `grafana` service key.
```

- [ ] **Step 3: Create `.github/workflows/validate.yml`**

```yaml
name: Validate kctl-grafana

on:
  push:
    paths:
      - "cli/**"
  pull_request:
    paths:
      - "cli/**"

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python ${{ matrix.python-version }}
        run: uv python install ${{ matrix.python-version }}

      - name: Install dependencies
        working-directory: cli
        run: uv sync --all-extras

      - name: Lint
        working-directory: cli
        run: uv run ruff check src/ tests/

      - name: Format check
        working-directory: cli
        run: uv run ruff format --check src/ tests/

      - name: Type check
        working-directory: cli
        run: uv run mypy src/

      - name: Test
        working-directory: cli
        run: uv run pytest tests/ -v --tb=short
```

- [ ] **Step 4: Run all tests and lint**

```bash
cd cli && uv run pytest tests/ -v --tb=short && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/
```

- [ ] **Step 5: Commit**

```bash
git add cli/src/kctl_grafana/commands/selftest.py CLAUDE.md .github/workflows/validate.yml
git commit -m "feat: add selftest command, update CLAUDE.md, add CI workflow"
```

---

### Task 9: Final verification

- [ ] **Step 1: Run the full test suite**

```bash
cd cli && uv run pytest tests/ -v --tb=short
```

Expected: All tests pass.

- [ ] **Step 2: Run lint and format checks**

```bash
cd cli && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/
```

Expected: Clean output, no violations.

- [ ] **Step 3: Run type checking**

```bash
cd cli && uv run mypy src/
```

Expected: No errors (or only minor third-party stubs issues).

- [ ] **Step 4: Test CLI installation and commands**

```bash
cd cli && uv run kctl-grafana --version
uv run kctl-grafana --help
uv run kctl-grafana dashboard --help
uv run kctl-grafana datasource --help
uv run kctl-grafana alert --help
uv run kctl-grafana folder --help
uv run kctl-grafana annotation --help
uv run kctl-grafana user --help
uv run kctl-grafana backup --help
uv run kctl-grafana status --help
uv run kctl-grafana health --help
uv run kctl-grafana selftest --help
uv run kctl-grafana config --help
```

Expected: All commands show help text and exit cleanly.

- [ ] **Step 5: Fix any issues found in steps 1-4**

If any tests fail, lint errors are found, or commands do not work, fix them before proceeding.

- [ ] **Step 6: Final commit and push**

```bash
git add -A
git status
git commit -m "chore: final verification and cleanup for kctl-grafana v0.1.0"
git push origin main
```
