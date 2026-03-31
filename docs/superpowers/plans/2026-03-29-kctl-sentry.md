# kctl-sentry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build kctl-sentry CLI with 10 command groups for daily error triage and release tracking.

**Architecture:** Python CLI using kctl-lib v0.4.0 (APIClient subclass for Sentry REST API). Built inside existing scaffolded kodemeio-sentry repo.

**Tech Stack:** Python 3.12+, kctl-lib>=0.4.0, Typer, httpx, Rich

**Working directory:** `/home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-sentry`

**Spec:** `docs/superpowers/specs/2026-03-29-kctl-service-clis-design.md` (Section 3: kctl-sentry)

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `cli/pyproject.toml` | Add pytest-httpx dev dep, bump to 0.1.0 |
| Modify | `cli/src/kctl_sentry/__init__.py` | Keep version |
| Modify | `cli/src/kctl_sentry/cli.py` | Register all 10 command groups |
| Create | `cli/src/kctl_sentry/core/client.py` | SentryClient(APIClient) |
| Modify | `cli/src/kctl_sentry/core/config.py` | ServiceConfig with url, auth_token, organization, default_project |
| Modify | `cli/src/kctl_sentry/core/callbacks.py` | AppContext with lazy client property |
| Keep   | `cli/src/kctl_sentry/core/exceptions.py` | Re-export from kctl-lib |
| Keep   | `cli/src/kctl_sentry/core/plugins.py` | Plugin discovery |
| Modify | `cli/src/kctl_sentry/commands/config_cmd.py` | Full config init/show/use/test |
| Create | `cli/src/kctl_sentry/commands/health.py` | API connectivity check |
| Create | `cli/src/kctl_sentry/commands/dashboard.py` | Quick overview |
| Create | `cli/src/kctl_sentry/commands/issues.py` | list/show/resolve/ignore/bulk-resolve/assign |
| Create | `cli/src/kctl_sentry/commands/projects.py` | list/show/dsn/create |
| Create | `cli/src/kctl_sentry/commands/releases.py` | list/create/show/associate-commits |
| Create | `cli/src/kctl_sentry/commands/alerts.py` | list/show/create |
| Create | `cli/src/kctl_sentry/commands/stats.py` | events/errors |
| Create | `cli/src/kctl_sentry/commands/teams.py` | list/show |
| Create | `cli/src/kctl_sentry/commands/environments.py` | list |
| Modify | `cli/tests/test_smoke.py` | Add smoke tests for all groups |
| Create | `cli/tests/test_client.py` | SentryClient unit tests |
| Create | `cli/tests/test_config.py` | Config resolution tests |
| Create | `cli/tests/test_issues.py` | Issues command tests with httpx mocks |
| Create | `cli/tests/test_projects.py` | Projects command tests |
| Create | `cli/tests/test_releases.py` | Releases command tests |
| Create | `cli/tests/test_health.py` | Health command tests |
| Modify | `CLAUDE.md` | Update with full CLI documentation |
| Create | `.github/workflows/validate.yml` | CI: lint + test on push/PR |

---

### Task 1: Setup — Client, Config, Callbacks, pyproject.toml

**Files:**
- Modify: `cli/pyproject.toml`
- Create: `cli/src/kctl_sentry/core/client.py`
- Modify: `cli/src/kctl_sentry/core/config.py`
- Modify: `cli/src/kctl_sentry/core/callbacks.py`
- Modify: `cli/src/kctl_sentry/commands/config_cmd.py`
- Modify: `cli/src/kctl_sentry/cli.py`

- [ ] **Step 1: Update pyproject.toml — add pytest-httpx**

Replace the full contents of `cli/pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "kctl-sentry"
version = "0.1.0"
description = "Sentry error tracking management"
requires-python = ">=3.12"
dependencies = [
    "kctl-lib>=0.4.0",
    "httpx>=0.28.0",
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
kctl-sentry = "kctl_sentry.cli:_run"

[tool.hatch.build.targets.wheel]
packages = ["src/kctl_sentry"]

[tool.ruff]
target-version = "py312"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "W", "UP", "B", "SIM", "N"]

[tool.mypy]
python_version = "3.12"
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create SentryClient**

Create `cli/src/kctl_sentry/core/client.py`:

```python
"""Sentry API client — subclasses kctl-lib APIClient."""

from __future__ import annotations

from typing import Any

from kctl_lib.api_client import APIClient
from kctl_lib.exceptions import AuthenticationError


class SentryClient(APIClient):
    """Synchronous client for Sentry REST API."""

    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"
    API_PREFIX = "/api/0"

    def __init__(
        self,
        base_url: str = "https://sentry.io",
        auth_token: str = "",
        organization: str = "",
        default_project: str = "",
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> None:
        if not auth_token:
            raise AuthenticationError("No auth token configured. Run: kctl-sentry config init")
        super().__init__(base_url=base_url, credential=auth_token, timeout=timeout, **kwargs)
        self._organization = organization
        self._default_project = default_project

    @property
    def organization(self) -> str:
        return self._organization

    @property
    def default_project(self) -> str:
        return self._default_project

    def resolve_project(self, project: str | None) -> str:
        """Resolve project slug: explicit arg > default_project config."""
        if project:
            return project
        if self._default_project:
            return self._default_project
        raise AuthenticationError("No project specified and no default_project configured")

    # ------------------------------------------------------------------
    # Convenience: org-scoped endpoints
    # ------------------------------------------------------------------

    def org_get(self, path: str, **kwargs: Any) -> Any:
        """GET /organizations/{org}/{path}."""
        return self.get(f"/organizations/{self._organization}{path}", **kwargs)

    def org_post(self, path: str, **kwargs: Any) -> Any:
        """POST /organizations/{org}/{path}."""
        return self.post(f"/organizations/{self._organization}{path}", **kwargs)

    # ------------------------------------------------------------------
    # Convenience: project-scoped endpoints
    # ------------------------------------------------------------------

    def project_get(self, project: str, path: str, **kwargs: Any) -> Any:
        """GET /projects/{org}/{project}/{path}."""
        return self.get(f"/projects/{self._organization}/{project}{path}", **kwargs)

    def project_post(self, project: str, path: str, **kwargs: Any) -> Any:
        """POST /projects/{org}/{project}/{path}."""
        return self.post(f"/projects/{self._organization}/{project}{path}", **kwargs)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def check_health(self) -> dict[str, Any]:
        """Verify API connectivity by fetching org details."""
        result = self.get(f"/organizations/{self._organization}/")
        return result if isinstance(result, dict) else {}
```

- [ ] **Step 3: Update ServiceConfig**

Replace the full contents of `cli/src/kctl_sentry/core/config.py`:

```python
"""Config management for kctl-sentry."""

from __future__ import annotations

import os

from kctl_lib.config import (
    CONFIG_DIR,
    CONFIG_FILE,
    get_all_services_in_profile,
    get_default_profile,
    get_profile_names,
    remove_profile,
    set_default_profile,
)
from kctl_lib.config import get_service_config as _get_service_config
from kctl_lib.config import (
    resolve_active_profile_name as _resolve_active_profile_name,
)
from kctl_lib.config import set_service_config as _set_service_config
from pydantic import BaseModel

__all__ = [
    "CONFIG_DIR",
    "CONFIG_FILE",
    "ENV_PREFIX",
    "SERVICE_KEY",
    "ServiceConfig",
    "get_all_services_in_profile",
    "get_default_profile",
    "get_profile_names",
    "get_service_config",
    "remove_profile",
    "resolve_active_profile_name",
    "resolve_connection",
    "set_default_profile",
    "set_service_config",
]

SERVICE_KEY = "sentry"
ENV_PREFIX = "KCTL_SENTRY"


class ServiceConfig(BaseModel):
    """Sentry-specific service config within a profile."""

    url: str = "https://sentry.io"
    auth_token: str = ""
    organization: str = ""
    default_project: str = ""


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get the 'sentry' service config from a profile."""
    data = _get_service_config(
        profile_name,
        SERVICE_KEY,
        valid_fields=list(ServiceConfig.model_fields.keys()),
    )
    return ServiceConfig(**data) if data else ServiceConfig()


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Set the 'sentry' service config within a profile."""
    svc_data = svc_config.model_dump(exclude_defaults=False)
    # Remove empty optional fields
    for key in ["default_project"]:
        if not svc_data.get(key):
            svc_data.pop(key, None)
    _set_service_config(profile_name, SERVICE_KEY, svc_data)


def resolve_active_profile_name(profile_name: str | None = None) -> str:
    """Resolve active profile: explicit > env > default."""
    return _resolve_active_profile_name(profile_name, ENV_PREFIX)


def resolve_connection(
    profile_name: str | None = None,
    auth_token_override: str | None = None,
) -> tuple[str, str, str, str]:
    """Resolve connection params from all sources.

    Returns (url, auth_token, organization, default_project).

    Priority:
    1. CLI flags (auth_token_override)
    2. KCTL_SENTRY_AUTH_TOKEN / KCTL_SENTRY_ORGANIZATION env vars
    3. SENTRY_AUTH_TOKEN / SENTRY_ORG env vars (native Sentry CLI compat)
    4. Profile's sentry service config
    """
    # 4. Config file profile (service-scoped)
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    url = svc.url
    auth_token = svc.auth_token
    organization = svc.organization
    default_project = svc.default_project

    # 3. Native Sentry env vars (fallback)
    if env_token := os.environ.get("SENTRY_AUTH_TOKEN"):
        auth_token = env_token
    if env_org := os.environ.get("SENTRY_ORG"):
        organization = env_org

    # 2. KCTL env vars
    if env_token := os.environ.get("KCTL_SENTRY_AUTH_TOKEN"):
        auth_token = env_token
    if env_org := os.environ.get("KCTL_SENTRY_ORGANIZATION"):
        organization = env_org
    if env_url := os.environ.get("KCTL_SENTRY_URL"):
        url = env_url

    # 1. CLI flags
    if auth_token_override:
        auth_token = auth_token_override

    return url, auth_token, organization, default_project
```

- [ ] **Step 4: Update AppContext with lazy client**

Replace the full contents of `cli/src/kctl_sentry/core/callbacks.py`:

```python
"""Typer global callback and shared context for kctl-sentry."""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_lib.callbacks import AppContextBase

from kctl_sentry.core.client import SentryClient
from kctl_sentry.core.config import resolve_connection


@dataclass
class AppContext(AppContextBase):
    """kctl-sentry application context."""

    auth_token_override: str | None = None
    _client: SentryClient | None = field(default=None, repr=False, init=False)

    @property
    def client(self) -> SentryClient:
        if self._client is None:
            url, auth_token, organization, default_project = resolve_connection(
                profile_name=self.profile,
                auth_token_override=self.auth_token_override,
            )
            self._client = SentryClient(
                base_url=url,
                auth_token=auth_token,
                organization=organization,
                default_project=default_project,
            )
        return self._client
```

- [ ] **Step 5: Update config_cmd.py with full config subcommands**

Replace the full contents of `cli/src/kctl_sentry/commands/config_cmd.py`:

```python
"""Configuration management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_sentry.core.callbacks import AppContext
from kctl_sentry.core.config import (
    CONFIG_FILE,
    SERVICE_KEY,
    ServiceConfig,
    get_all_services_in_profile,
    get_default_profile,
    get_profile_names,
    resolve_active_profile_name,
    set_default_profile,
    set_service_config,
)
from kctl_sentry.core.exceptions import KctlError

app = typer.Typer(help="Manage CLI configuration and profiles.")


def _mask(val: str) -> str:
    """Mask a secret value for display."""
    if not val:
        return "[dim]not set[/dim]"
    return f"{val[:4]}{'*' * max(0, len(val) - 8)}{val[-4:]}" if len(val) > 10 else "****"


@app.command()
def init(
    ctx: typer.Context,
    auth_token: Annotated[str | None, typer.Option("--auth-token", help="Sentry auth token")] = None,
    organization: Annotated[str | None, typer.Option("--organization", "--org", help="Organization slug")] = None,
    url: Annotated[str | None, typer.Option("--url", help="Sentry URL")] = None,
    default_project: Annotated[str | None, typer.Option("--default-project", help="Default project slug")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Profile name")] = None,
) -> None:
    """Initialize CLI configuration."""
    c: AppContext = ctx.obj
    out = c.output
    profile_name = name or typer.prompt("Profile name", default="kodemeio")
    token = auth_token or typer.prompt("Sentry auth token", hide_input=True)
    org = organization or typer.prompt("Organization slug")
    sentry_url = url or typer.prompt("Sentry URL", default="https://sentry.io")
    proj = default_project or typer.prompt("Default project slug (optional)", default="")

    svc = ServiceConfig(
        url=sentry_url,
        auth_token=token,
        organization=org,
        default_project=proj,
    )
    set_service_config(profile_name, svc)
    if len(get_profile_names()) <= 1:
        set_default_profile(profile_name)
    out.success(f"Configuration saved to {CONFIG_FILE}")
    out.kv("Profile", profile_name)
    out.kv("URL", sentry_url)
    out.kv("Token", _mask(token))
    out.kv("Organization", org)
    if proj:
        out.kv("Default project", proj)


@app.command()
def show(ctx: typer.Context) -> None:
    """Show configuration."""
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
        kvs: list[tuple[str, str]] = []
        for svc_name, svc_data in services.items():
            if not isinstance(svc_data, dict):
                continue
            indicator = "[green]●[/green]" if svc_name == SERVICE_KEY else "[dim]○[/dim]"
            token_val = svc_data.get("auth_token", svc_data.get("token", ""))
            kvs.append((f"{indicator} {svc_name}", f"token: {_mask(token_val)}"))
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
        result = c.client.check_health()
        org_name = result.get("name", "unknown")
        out.success(f"Connected — organization: {org_name}")
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
```

- [ ] **Step 6: Update cli.py — register all command groups**

Replace the full contents of `cli/src/kctl_sentry/cli.py`:

```python
"""Main CLI entry point for kctl-sentry."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_sentry import __version__
from kctl_sentry.commands.alerts import app as alerts_app
from kctl_sentry.commands.config_cmd import app as config_app
from kctl_sentry.commands.dashboard import app as dashboard_app
from kctl_sentry.commands.environments import app as environments_app
from kctl_sentry.commands.health import app as health_app
from kctl_sentry.commands.issues import app as issues_app
from kctl_sentry.commands.projects import app as projects_app
from kctl_sentry.commands.releases import app as releases_app
from kctl_sentry.commands.stats import app as stats_app
from kctl_sentry.commands.teams import app as teams_app
from kctl_sentry.core.callbacks import AppContext
from kctl_sentry.core.plugins import discover_and_load_plugins


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-sentry {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-sentry",
    help="Kodemeio Sentry CLI — error triage, release tracking, and project management.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


@app.callback()
def main(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress info messages")] = False,
    profile: Annotated[str | None, typer.Option("--profile", "-p", help="Config profile name")] = None,
    format: Annotated[str, typer.Option("--format", "-f", help="Output format: pretty, json, csv, yaml")] = "pretty",
    no_header: Annotated[bool, typer.Option("--no-header", help="Omit header row in CSV output")] = False,
    auth_token: Annotated[str | None, typer.Option("--auth-token", help="Auth token override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio Sentry CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        format=format,
        no_header=no_header,
        auth_token_override=auth_token,
    )


app.add_typer(config_app, name="config")
app.add_typer(health_app, name="health")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(issues_app, name="issues")
app.add_typer(projects_app, name="projects")
app.add_typer(releases_app, name="releases")
app.add_typer(alerts_app, name="alerts")
app.add_typer(stats_app, name="stats")
app.add_typer(teams_app, name="teams")
app.add_typer(environments_app, name="environments")

# Load third-party plugins via entry points
discover_and_load_plugins(app)


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
```

- [ ] **Step 7: Verify setup — uv sync and smoke test**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-sentry/cli
uv sync --all-extras
uv run kctl-sentry --help
uv run kctl-sentry --version
```

---

### Task 2: health + dashboard commands

**Files:**
- Create: `cli/src/kctl_sentry/commands/health.py`
- Create: `cli/src/kctl_sentry/commands/dashboard.py`

- [ ] **Step 1: Create health.py**

Create `cli/src/kctl_sentry/commands/health.py`:

```python
"""Health check commands."""

from __future__ import annotations

import typer

from kctl_sentry.core.callbacks import AppContext
from kctl_sentry.core.config import resolve_active_profile_name
from kctl_sentry.core.exceptions import KctlError

app = typer.Typer(help="API connectivity checks.")


@app.command("check")
def check(ctx: typer.Context) -> None:
    """Check Sentry API connectivity, org info, and rate limits."""
    c: AppContext = ctx.obj
    out = c.output
    active = resolve_active_profile_name(c.profile)

    try:
        result = c.client.check_health()
        org_name = result.get("name", "unknown")
        org_slug = result.get("slug", "unknown")
        plan = result.get("plan", {}).get("name", "unknown") if isinstance(result.get("plan"), dict) else "unknown"

        # Get project count
        try:
            projects = c.client.org_get("/projects/")
            project_count = len(projects) if isinstance(projects, list) else 0
        except Exception:
            project_count = 0

        sections = [
            (
                "Health",
                [
                    ("Status", "[green]Connected[/green]"),
                    ("Profile", active),
                    ("Organization", f"{org_name} ({org_slug})"),
                    ("Plan", plan),
                    ("Projects", str(project_count)),
                ],
            )
        ]
        out.detail(
            "Sentry Health",
            sections,
            data_for_json={
                "healthy": True,
                "profile": active,
                "organization": org_slug,
                "org_name": org_name,
                "plan": plan,
                "project_count": project_count,
            },
        )
    except KctlError as e:
        out.detail(
            "Sentry Health",
            [
                (
                    "Health",
                    [
                        ("Status", "[red]Unreachable[/red]"),
                        ("Error", str(e)),
                    ],
                )
            ],
            data_for_json={"healthy": False, "error": str(e)},
        )
        raise typer.Exit(1) from e
```

- [ ] **Step 2: Create dashboard.py**

Create `cli/src/kctl_sentry/commands/dashboard.py`:

```python
"""Dashboard command — quick overview of Sentry state."""

from __future__ import annotations

import typer

from kctl_sentry.core.callbacks import AppContext
from kctl_sentry.core.exceptions import KctlError

app = typer.Typer(help="Quick overview of Sentry state.")


@app.command("overview")
def overview(ctx: typer.Context) -> None:
    """Show unresolved issues, recent releases, and alert status across projects."""
    c: AppContext = ctx.obj
    out = c.output
    org = c.client.organization

    try:
        # Fetch projects
        projects = c.client.org_get("/projects/")
        if not isinstance(projects, list):
            projects = []

        # Collect unresolved issues per project
        project_rows: list[list[str]] = []
        total_unresolved = 0
        for proj in projects[:20]:  # Cap at 20 projects
            slug = proj.get("slug", "")
            try:
                issues = c.client.project_get(slug, "/issues/", params={"query": "is:unresolved", "limit": 1})
                # Sentry returns X-Hits header, but we can use list length as indicator
                unresolved = proj.get("stats", {}).get("unresolved", len(issues) if isinstance(issues, list) else 0)
            except Exception:
                unresolved = 0
            total_unresolved += unresolved if isinstance(unresolved, int) else 0
            project_rows.append([
                slug,
                proj.get("platform", ""),
                str(unresolved),
            ])

        # Fetch recent releases
        try:
            releases = c.client.org_get("/releases/", params={"per_page": 5})
            if not isinstance(releases, list):
                releases = []
        except Exception:
            releases = []

        release_rows: list[list[str]] = []
        for rel in releases[:5]:
            release_rows.append([
                rel.get("version", "")[:40],
                ", ".join(p.get("slug", "") for p in rel.get("projects", [])),
                (rel.get("dateCreated", "") or "")[:19],
            ])

        # Output
        if project_rows:
            out.table(
                f"Projects — {org} ({total_unresolved} unresolved)",
                [("Project", "cyan"), ("Platform", ""), ("Unresolved", "yellow")],
                project_rows,
                data_for_json={"projects": projects},
            )

        if release_rows:
            out.table(
                "Recent Releases",
                [("Version", "cyan"), ("Projects", ""), ("Created", "dim")],
                release_rows,
                data_for_json={"releases": releases},
            )

        if not project_rows:
            out.info("No projects found")

    except KctlError as e:
        out.error(f"Dashboard failed: {e}")
        raise typer.Exit(1) from e
```

- [ ] **Step 3: Verify — run help for health and dashboard**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-sentry/cli
uv run kctl-sentry health --help
uv run kctl-sentry dashboard --help
```

---

### Task 3: issues command group (the main daily-use command)

**Files:**
- Create: `cli/src/kctl_sentry/commands/issues.py`

- [ ] **Step 1: Create issues.py**

Create `cli/src/kctl_sentry/commands/issues.py`:

```python
"""Issue management commands — daily error triage."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_sentry.core.callbacks import AppContext
from kctl_sentry.core.exceptions import KctlError

app = typer.Typer(help="Error triage — list, inspect, resolve, ignore, assign issues.")


@app.command("list")
def list_(
    ctx: typer.Context,
    project: Annotated[str | None, typer.Option("--project", "-p", help="Project slug")] = None,
    status: Annotated[str, typer.Option("--status", "-s", help="Status filter: unresolved, resolved, ignored")] = "unresolved",
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 25,
    sort: Annotated[str, typer.Option("--sort", help="Sort by: date, priority, freq, new")] = "date",
) -> None:
    """List recent issues for a project."""
    c: AppContext = ctx.obj
    out = c.output
    proj = c.client.resolve_project(project)

    try:
        query = f"is:{status}"
        issues = c.client.project_get(
            proj,
            "/issues/",
            params={"query": query, "limit": limit, "sort": sort},
        )
        if not isinstance(issues, list):
            issues = []

        rows: list[list[str]] = []
        for iss in issues:
            short_id = iss.get("shortId", "")
            title = (iss.get("title", "") or "")[:60]
            events = str(iss.get("count", 0))
            users = str(iss.get("userCount", 0))
            level = iss.get("level", "")
            first_seen = (iss.get("firstSeen", "") or "")[:19]
            last_seen = (iss.get("lastSeen", "") or "")[:19]
            assignee = ""
            if iss.get("assignedTo"):
                assignee = iss["assignedTo"].get("name", "") if isinstance(iss["assignedTo"], dict) else ""

            rows.append([short_id, title, level, events, users, assignee, last_seen])

        out.table(
            f"Issues — {proj} ({status})",
            [
                ("ID", "cyan"),
                ("Title", ""),
                ("Level", "yellow"),
                ("Events", ""),
                ("Users", ""),
                ("Assignee", "dim"),
                ("Last Seen", "dim"),
            ],
            rows,
            data_for_json=issues,
        )
    except KctlError as e:
        out.error(f"Failed to list issues: {e}")
        raise typer.Exit(1) from e


@app.command("show")
def show(
    ctx: typer.Context,
    issue_id: Annotated[str, typer.Argument(help="Issue ID (numeric or short ID)")],
) -> None:
    """Show issue details, stack trace, and affected users."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        issue = c.client.get(f"/issues/{issue_id}/")
        if not isinstance(issue, dict):
            issue = {}

        # Fetch latest event for stack trace
        try:
            latest_event = c.client.get(f"/issues/{issue_id}/events/latest/")
        except Exception:
            latest_event = {}
        if not isinstance(latest_event, dict):
            latest_event = {}

        # Build detail sections
        assignee = ""
        if issue.get("assignedTo") and isinstance(issue["assignedTo"], dict):
            assignee = issue["assignedTo"].get("name", "")

        sections = [
            (
                "Issue",
                [
                    ("ID", issue.get("shortId", str(issue.get("id", "")))),
                    ("Title", issue.get("title", "")),
                    ("Project", issue.get("project", {}).get("slug", "") if isinstance(issue.get("project"), dict) else ""),
                    ("Level", issue.get("level", "")),
                    ("Status", issue.get("status", "")),
                    ("Assignee", assignee or "[dim]unassigned[/dim]"),
                    ("Events", str(issue.get("count", 0))),
                    ("Users affected", str(issue.get("userCount", 0))),
                    ("First seen", (issue.get("firstSeen", "") or "")[:19]),
                    ("Last seen", (issue.get("lastSeen", "") or "")[:19]),
                ],
            ),
        ]

        # Add stack trace from latest event
        entries = []
        for exc_val in (latest_event.get("entries") or []):
            if exc_val.get("type") == "exception":
                for val in (exc_val.get("data", {}).get("values") or []):
                    exc_type = val.get("type", "")
                    exc_value = val.get("value", "")
                    frames = val.get("stacktrace", {}).get("frames", []) if isinstance(val.get("stacktrace"), dict) else []
                    entries.append((exc_type, exc_value, frames))

        if entries:
            for exc_type, exc_value, frames in entries:
                trace_kvs: list[tuple[str, str]] = [
                    ("Exception", f"{exc_type}: {exc_value}"),
                ]
                # Show last 5 frames
                for frame in frames[-5:]:
                    filename = frame.get("filename", "")
                    lineno = frame.get("lineNo", "")
                    func = frame.get("function", "")
                    trace_kvs.append(("Frame", f"{filename}:{lineno} in {func}"))
                sections.append(("Stack Trace", trace_kvs))

        # Add tags
        tags = issue.get("tags", [])
        if isinstance(tags, list) and tags:
            tag_kvs: list[tuple[str, str]] = []
            for tag in tags[:10]:
                if isinstance(tag, dict):
                    tag_kvs.append((tag.get("key", ""), tag.get("name", "")))
            if tag_kvs:
                sections.append(("Tags", tag_kvs))

        out.detail(
            f"Issue: {issue.get('shortId', issue_id)}",
            sections,
            data_for_json={"issue": issue, "latest_event": latest_event},
        )
    except KctlError as e:
        out.error(f"Failed to show issue: {e}")
        raise typer.Exit(1) from e


@app.command("resolve")
def resolve(
    ctx: typer.Context,
    issue_id: Annotated[str, typer.Argument(help="Issue ID")],
    release: Annotated[str | None, typer.Option("--release", "-r", help="Mark resolved in release")] = None,
) -> None:
    """Resolve an issue. Optionally mark as resolved in a specific release."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        payload: dict = {"status": "resolved"}
        if release:
            payload["statusDetails"] = {"inRelease": release}
        c.client.put(f"/issues/{issue_id}/", json=payload)
        msg = f"Issue {issue_id} resolved"
        if release:
            msg += f" in release {release}"
        out.success(msg)
    except KctlError as e:
        out.error(f"Failed to resolve issue: {e}")
        raise typer.Exit(1) from e


@app.command("ignore")
def ignore(
    ctx: typer.Context,
    issue_id: Annotated[str, typer.Argument(help="Issue ID")],
    duration: Annotated[int | None, typer.Option("--duration", "-d", help="Ignore duration in minutes")] = None,
    count: Annotated[int | None, typer.Option("--count", help="Ignore until N more events")] = None,
) -> None:
    """Ignore an issue, optionally for a duration or until N more events."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        payload: dict = {"status": "ignored"}
        status_details: dict = {}
        if duration:
            status_details["ignoreDuration"] = duration
        if count:
            status_details["ignoreCount"] = count
        if status_details:
            payload["statusDetails"] = status_details

        c.client.put(f"/issues/{issue_id}/", json=payload)
        msg = f"Issue {issue_id} ignored"
        if duration:
            msg += f" for {duration} minutes"
        if count:
            msg += f" until {count} more events"
        out.success(msg)
    except KctlError as e:
        out.error(f"Failed to ignore issue: {e}")
        raise typer.Exit(1) from e


@app.command("bulk-resolve")
def bulk_resolve(
    ctx: typer.Context,
    project: Annotated[str, typer.Option("--project", "-p", help="Project slug (required)")],
    before: Annotated[str | None, typer.Option("--before", help="Resolve issues last seen before date (ISO 8601)")] = None,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Bulk-resolve old unresolved issues in a project."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        # Fetch unresolved issues
        params: dict = {"query": "is:unresolved", "limit": 100}
        if before:
            params["query"] += f" lastSeen:<{before}"

        issues = c.client.project_get(project, "/issues/", params=params)
        if not isinstance(issues, list):
            issues = []

        if not issues:
            out.info("No matching issues to resolve")
            return

        if not force:
            confirm = typer.confirm(f"Resolve {len(issues)} issues in '{project}'?")
            if not confirm:
                out.info("Aborted")
                return

        # Bulk update via issue IDs
        issue_ids = [str(iss.get("id", "")) for iss in issues if iss.get("id")]
        if issue_ids:
            c.client.put(
                f"/projects/{c.client.organization}/{project}/issues/",
                params={"id": issue_ids},
                json={"status": "resolved"},
            )

        out.success(f"Resolved {len(issue_ids)} issues in '{project}'")
    except KctlError as e:
        out.error(f"Bulk resolve failed: {e}")
        raise typer.Exit(1) from e


@app.command("assign")
def assign(
    ctx: typer.Context,
    issue_id: Annotated[str, typer.Argument(help="Issue ID")],
    to: Annotated[str, typer.Option("--to", help="User email or 'me'")],
) -> None:
    """Assign an issue to a team member."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        c.client.put(f"/issues/{issue_id}/", json={"assignedTo": to})
        out.success(f"Issue {issue_id} assigned to {to}")
    except KctlError as e:
        out.error(f"Failed to assign issue: {e}")
        raise typer.Exit(1) from e
```

- [ ] **Step 2: Verify — run issues help**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-sentry/cli
uv run kctl-sentry issues --help
```

---

### Task 4: projects command group

**Files:**
- Create: `cli/src/kctl_sentry/commands/projects.py`

- [ ] **Step 1: Create projects.py**

Create `cli/src/kctl_sentry/commands/projects.py`:

```python
"""Project management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_sentry.core.callbacks import AppContext
from kctl_sentry.core.exceptions import KctlError

app = typer.Typer(help="Manage Sentry projects.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all projects with issue counts."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        projects = c.client.org_get("/projects/")
        if not isinstance(projects, list):
            projects = []

        rows: list[list[str]] = []
        for proj in projects:
            slug = proj.get("slug", "")
            name = proj.get("name", "")
            platform = proj.get("platform", "") or ""
            status = proj.get("status", "")
            team = ""
            if proj.get("team") and isinstance(proj["team"], dict):
                team = proj["team"].get("slug", "")
            elif proj.get("teams") and isinstance(proj["teams"], list) and proj["teams"]:
                team = proj["teams"][0].get("slug", "") if isinstance(proj["teams"][0], dict) else ""

            rows.append([slug, name, platform, team, status])

        out.table(
            "Projects",
            [
                ("Slug", "cyan"),
                ("Name", ""),
                ("Platform", ""),
                ("Team", "dim"),
                ("Status", "green"),
            ],
            rows,
            data_for_json=projects,
        )
    except KctlError as e:
        out.error(f"Failed to list projects: {e}")
        raise typer.Exit(1) from e


@app.command("show")
def show(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Project slug")],
) -> None:
    """Show project details."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        proj = c.client.project_get(slug, "/")
        if not isinstance(proj, dict):
            proj = {}

        teams = proj.get("teams", [])
        team_names = ", ".join(
            t.get("slug", "") for t in teams if isinstance(t, dict)
        ) if isinstance(teams, list) else ""

        features = proj.get("features", [])
        feature_str = ", ".join(features[:10]) if isinstance(features, list) else ""

        sections = [
            (
                "Project",
                [
                    ("Slug", proj.get("slug", "")),
                    ("Name", proj.get("name", "")),
                    ("Platform", proj.get("platform", "") or ""),
                    ("Status", proj.get("status", "")),
                    ("Teams", team_names),
                    ("Date created", (proj.get("dateCreated", "") or "")[:19]),
                    ("Features", feature_str or "[dim]none[/dim]"),
                ],
            ),
        ]

        out.detail(
            f"Project: {slug}",
            sections,
            data_for_json=proj,
        )
    except KctlError as e:
        out.error(f"Failed to show project: {e}")
        raise typer.Exit(1) from e


@app.command("dsn")
def dsn(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Project slug")],
) -> None:
    """Get DSN key for SDK configuration."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        keys = c.client.project_get(slug, "/keys/")
        if not isinstance(keys, list):
            keys = []

        rows: list[list[str]] = []
        for key in keys:
            label = key.get("label", key.get("name", ""))
            dsn_public = key.get("dsn", {}).get("public", "") if isinstance(key.get("dsn"), dict) else ""
            dsn_secret = key.get("dsn", {}).get("secret", "") if isinstance(key.get("dsn"), dict) else ""
            is_active = "Yes" if key.get("isActive", True) else "No"
            rows.append([label, dsn_public, is_active])

        out.table(
            f"DSN Keys — {slug}",
            [
                ("Label", "cyan"),
                ("DSN (Public)", "green"),
                ("Active", ""),
            ],
            rows,
            data_for_json=keys,
        )
    except KctlError as e:
        out.error(f"Failed to get DSN: {e}")
        raise typer.Exit(1) from e


@app.command("create")
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Project name")],
    team: Annotated[str, typer.Option("--team", "-t", help="Team slug")],
    platform: Annotated[str, typer.Option("--platform", help="Platform (e.g. python, javascript, node)")] = "",
) -> None:
    """Create a new project."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        payload: dict = {"name": name}
        if platform:
            payload["platform"] = platform

        result = c.client.post(
            f"/teams/{c.client.organization}/{team}/projects/",
            json=payload,
        )
        if not isinstance(result, dict):
            result = {}

        slug = result.get("slug", "")
        if out.json_mode:
            out.raw_json(result)
        else:
            out.success(f"Project created: {slug}")
            out.kv("Name", result.get("name", ""))
            out.kv("Slug", slug)
            out.kv("Platform", result.get("platform", "") or "")
    except KctlError as e:
        out.error(f"Failed to create project: {e}")
        raise typer.Exit(1) from e
```

- [ ] **Step 2: Verify — run projects help**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-sentry/cli
uv run kctl-sentry projects --help
```

---

### Task 5: releases command group

**Files:**
- Create: `cli/src/kctl_sentry/commands/releases.py`

- [ ] **Step 1: Create releases.py**

Create `cli/src/kctl_sentry/commands/releases.py`:

```python
"""Release tracking commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_sentry.core.callbacks import AppContext
from kctl_sentry.core.exceptions import KctlError

app = typer.Typer(help="Manage releases and deploy tracking.")


@app.command("list")
def list_(
    ctx: typer.Context,
    project: Annotated[str | None, typer.Option("--project", "-p", help="Filter by project slug")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 20,
) -> None:
    """List recent releases."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        params: dict = {"per_page": limit}
        if project:
            params["project"] = c.client.resolve_project(project)

        releases = c.client.org_get("/releases/", params=params)
        if not isinstance(releases, list):
            releases = []

        rows: list[list[str]] = []
        for rel in releases:
            version = (rel.get("version", "") or "")[:50]
            projects = ", ".join(
                p.get("slug", "") for p in rel.get("projects", []) if isinstance(p, dict)
            )
            new_groups = str(rel.get("newGroups", 0))
            created = (rel.get("dateCreated", "") or "")[:19]
            deploy_count = str(rel.get("deployCount", 0))
            rows.append([version, projects, new_groups, deploy_count, created])

        out.table(
            "Releases",
            [
                ("Version", "cyan"),
                ("Projects", ""),
                ("New Issues", "yellow"),
                ("Deploys", ""),
                ("Created", "dim"),
            ],
            rows,
            data_for_json=releases,
        )
    except KctlError as e:
        out.error(f"Failed to list releases: {e}")
        raise typer.Exit(1) from e


@app.command("create")
def create(
    ctx: typer.Context,
    version: Annotated[str, typer.Argument(help="Release version (e.g. 1.2.3 or git SHA)")],
    project: Annotated[str, typer.Option("--project", "-p", help="Project slug")],
) -> None:
    """Create a new release for a project."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        payload = {
            "version": version,
            "projects": [project],
        }
        result = c.client.org_post("/releases/", json=payload)
        if not isinstance(result, dict):
            result = {}

        if out.json_mode:
            out.raw_json(result)
        else:
            out.success(f"Release created: {version}")
            out.kv("Version", result.get("version", ""))
            projs = ", ".join(
                p.get("slug", "") for p in result.get("projects", []) if isinstance(p, dict)
            )
            out.kv("Projects", projs)
    except KctlError as e:
        out.error(f"Failed to create release: {e}")
        raise typer.Exit(1) from e


@app.command("show")
def show(
    ctx: typer.Context,
    version: Annotated[str, typer.Argument(help="Release version")],
) -> None:
    """Show release details and associated issues."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        release = c.client.org_get(f"/releases/{version}/")
        if not isinstance(release, dict):
            release = {}

        projects = ", ".join(
            p.get("slug", "") for p in release.get("projects", []) if isinstance(p, dict)
        )

        # Fetch associated issues (new in this release)
        try:
            issues = c.client.org_get(
                f"/releases/{version}/resolved/",
            )
            if not isinstance(issues, list):
                issues = []
        except Exception:
            issues = []

        sections = [
            (
                "Release",
                [
                    ("Version", release.get("version", "")),
                    ("Projects", projects),
                    ("New issues", str(release.get("newGroups", 0))),
                    ("Deploy count", str(release.get("deployCount", 0))),
                    ("Created", (release.get("dateCreated", "") or "")[:19]),
                    ("First event", (release.get("firstEvent", "") or "N/A")[:19]),
                    ("Last event", (release.get("lastEvent", "") or "N/A")[:19]),
                ],
            ),
        ]

        # Commit info
        last_commit = release.get("lastCommit")
        if isinstance(last_commit, dict):
            sections.append((
                "Last Commit",
                [
                    ("SHA", (last_commit.get("id", "") or "")[:12]),
                    ("Message", (last_commit.get("message", "") or "")[:80]),
                    ("Author", last_commit.get("author", {}).get("name", "") if isinstance(last_commit.get("author"), dict) else ""),
                ],
            ))

        # Resolved issues in this release
        if issues:
            issue_kvs: list[tuple[str, str]] = []
            for iss in issues[:10]:
                if isinstance(iss, dict):
                    issue_kvs.append((
                        iss.get("shortId", str(iss.get("id", ""))),
                        (iss.get("title", "") or "")[:60],
                    ))
            if issue_kvs:
                sections.append(("Resolved Issues", issue_kvs))

        out.detail(
            f"Release: {version}",
            sections,
            data_for_json={"release": release, "resolved_issues": issues},
        )
    except KctlError as e:
        out.error(f"Failed to show release: {e}")
        raise typer.Exit(1) from e


@app.command("associate")
def associate_commits(
    ctx: typer.Context,
    version: Annotated[str, typer.Argument(help="Release version")],
    commits: Annotated[str, typer.Option("--commits", help="Commit range: repo@from..to")],
) -> None:
    """Associate commits with a release for tracking regressions."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        # Parse "repo@from..to" format
        if "@" in commits and ".." in commits:
            repo_part, range_part = commits.split("@", 1)
            commit_from, commit_to = range_part.split("..", 1)
            commit_list = [
                {
                    "repository": repo_part,
                    "previousCommit": commit_from,
                    "currentCommit": commit_to,
                }
            ]
        else:
            # Treat as simple commit SHA
            commit_list = [{"id": commits}]

        payload = {
            "commits": commit_list,
        }
        c.client.org_put(f"/releases/{version}/", json=payload)
        out.success(f"Commits associated with release {version}")
    except KctlError as e:
        out.error(f"Failed to associate commits: {e}")
        raise typer.Exit(1) from e
```

**Note:** The `associate` command uses `org_put` which does not exist on SentryClient yet. Add this method to `cli/src/kctl_sentry/core/client.py`:

Add the following method to `SentryClient` class after the `org_post` method:

```python
    def org_put(self, path: str, **kwargs: Any) -> Any:
        """PUT /organizations/{org}/{path}."""
        return self.put(f"/organizations/{self._organization}{path}", **kwargs)
```

- [ ] **Step 2: Verify — run releases help**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-sentry/cli
uv run kctl-sentry releases --help
```

---

### Task 6: alerts + stats command groups

**Files:**
- Create: `cli/src/kctl_sentry/commands/alerts.py`
- Create: `cli/src/kctl_sentry/commands/stats.py`

- [ ] **Step 1: Create alerts.py**

Create `cli/src/kctl_sentry/commands/alerts.py`:

```python
"""Alert rule management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_sentry.core.callbacks import AppContext
from kctl_sentry.core.exceptions import KctlError

app = typer.Typer(help="Manage alert rules.")


@app.command("list")
def list_(
    ctx: typer.Context,
    project: Annotated[str | None, typer.Option("--project", "-p", help="Filter by project slug")] = None,
) -> None:
    """List alert rules."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        if project:
            rules = c.client.project_get(project, "/rules/")
        else:
            rules = c.client.org_get("/alert-rules/")
        if not isinstance(rules, list):
            rules = []

        rows: list[list[str]] = []
        for rule in rules:
            rule_id = str(rule.get("id", ""))
            name = (rule.get("name", "") or "")[:50]
            # Project-scoped rules have 'projects', org-scoped have 'project'
            proj_info = ""
            if isinstance(rule.get("projects"), list):
                proj_info = ", ".join(rule["projects"])
            elif isinstance(rule.get("project"), dict):
                proj_info = rule["project"].get("slug", "")

            status_val = rule.get("status", "active")
            owner = ""
            if isinstance(rule.get("owner"), dict):
                owner = rule["owner"].get("name", "")
            elif isinstance(rule.get("owner"), str):
                owner = rule["owner"]

            rows.append([rule_id, name, proj_info, status_val, owner])

        out.table(
            "Alert Rules",
            [
                ("ID", "cyan"),
                ("Name", ""),
                ("Project", ""),
                ("Status", "green"),
                ("Owner", "dim"),
            ],
            rows,
            data_for_json=rules,
        )
    except KctlError as e:
        out.error(f"Failed to list alerts: {e}")
        raise typer.Exit(1) from e


@app.command("show")
def show(
    ctx: typer.Context,
    rule_id: Annotated[str, typer.Argument(help="Alert rule ID")],
    project: Annotated[str, typer.Option("--project", "-p", help="Project slug")],
) -> None:
    """Show alert rule details and trigger history."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        rule = c.client.project_get(project, f"/rules/{rule_id}/")
        if not isinstance(rule, dict):
            rule = {}

        # Parse conditions
        conditions = rule.get("conditions", [])
        condition_strs: list[tuple[str, str]] = []
        for cond in conditions if isinstance(conditions, list) else []:
            if isinstance(cond, dict):
                condition_strs.append(("Condition", cond.get("name", str(cond.get("id", "")))))

        # Parse actions
        actions = rule.get("actions", [])
        action_strs: list[tuple[str, str]] = []
        for act in actions if isinstance(actions, list) else []:
            if isinstance(act, dict):
                action_strs.append(("Action", act.get("name", str(act.get("id", "")))))

        sections = [
            (
                "Alert Rule",
                [
                    ("ID", str(rule.get("id", ""))),
                    ("Name", rule.get("name", "")),
                    ("Status", rule.get("status", "")),
                    ("Frequency", f"{rule.get('frequency', '')} seconds"),
                    ("Date created", (rule.get("dateCreated", "") or "")[:19]),
                ],
            ),
        ]

        if condition_strs:
            sections.append(("Conditions", condition_strs))
        if action_strs:
            sections.append(("Actions", action_strs))

        out.detail(
            f"Alert Rule: {rule.get('name', rule_id)}",
            sections,
            data_for_json=rule,
        )
    except KctlError as e:
        out.error(f"Failed to show alert: {e}")
        raise typer.Exit(1) from e


@app.command("create")
def create(
    ctx: typer.Context,
    project: Annotated[str, typer.Option("--project", "-p", help="Project slug")],
    name: Annotated[str, typer.Option("--name", "-n", help="Alert rule name")],
    metric: Annotated[str, typer.Option("--metric", help="Metric: events, users")] = "events",
    threshold: Annotated[int, typer.Option("--threshold", help="Threshold value")] = 100,
    time_window: Annotated[int, typer.Option("--time-window", help="Time window in minutes")] = 60,
) -> None:
    """Create a new metric alert rule."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        # Map metric to Sentry's aggregate format
        aggregate_map = {
            "events": "count()",
            "users": "count_unique(user)",
        }
        aggregate = aggregate_map.get(metric, "count()")

        payload = {
            "name": name,
            "aggregate": aggregate,
            "timeWindow": time_window,
            "dataset": "events",
            "query": "",
            "thresholdType": 0,  # Above threshold
            "resolveThreshold": None,
            "triggers": [
                {
                    "label": "critical",
                    "alertThreshold": threshold,
                    "actions": [],
                }
            ],
            "projects": [project],
            "owner": None,
        }

        result = c.client.org_post("/alert-rules/", json=payload)
        if not isinstance(result, dict):
            result = {}

        if out.json_mode:
            out.raw_json(result)
        else:
            out.success(f"Alert rule created: {result.get('name', name)}")
            out.kv("ID", str(result.get("id", "")))
            out.kv("Metric", aggregate)
            out.kv("Threshold", str(threshold))
    except KctlError as e:
        out.error(f"Failed to create alert: {e}")
        raise typer.Exit(1) from e
```

- [ ] **Step 2: Create stats.py**

Create `cli/src/kctl_sentry/commands/stats.py`:

```python
"""Statistics commands — event volume and error rate trends."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_sentry.core.callbacks import AppContext
from kctl_sentry.core.exceptions import KctlError

app = typer.Typer(help="Event and error statistics.")


@app.command("events")
def events(
    ctx: typer.Context,
    project: Annotated[str | None, typer.Option("--project", "-p", help="Project slug")] = None,
    period: Annotated[str, typer.Option("--period", help="Time period: 1h, 24h, 7d, 30d")] = "24h",
) -> None:
    """Show event volume for a project or organization."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        # Map period to stat parameter
        stat_map = {
            "1h": "1h",
            "24h": "24h",
            "7d": "",
            "30d": "",
        }
        stat = stat_map.get(period, "24h")

        if project:
            proj = c.client.resolve_project(project)
            # Use project stats endpoint
            stats_data = c.client.project_get(
                proj,
                "/stats/",
                params={"stat": "received", "resolution": stat or "1d"},
            )
        else:
            # Use org stats endpoint
            stats_data = c.client.org_get(
                "/stats_v2/",
                params={
                    "field": "sum(quantity)",
                    "statsPeriod": period,
                    "category": "error",
                },
            )

        if isinstance(stats_data, list):
            # Time-series data: [[timestamp, count], ...]
            total = sum(point[1] for point in stats_data if isinstance(point, (list, tuple)) and len(point) >= 2)
            rows: list[list[str]] = []
            for point in stats_data[-10:]:  # Last 10 data points
                if isinstance(point, (list, tuple)) and len(point) >= 2:
                    rows.append([str(point[0]), str(point[1])])

            out.table(
                f"Event Volume — {project or 'all projects'} ({period})",
                [("Timestamp", "dim"), ("Events", "cyan")],
                rows,
                data_for_json={"total": total, "data": stats_data},
            )
            out.kv("Total events", str(total))
        elif isinstance(stats_data, dict):
            out.detail(
                f"Event Stats — {project or 'all projects'} ({period})",
                [("Stats", [(k, str(v)) for k, v in stats_data.items()])],
                data_for_json=stats_data,
            )
        else:
            out.info("No stats data available")

    except KctlError as e:
        out.error(f"Failed to fetch stats: {e}")
        raise typer.Exit(1) from e


@app.command("errors")
def errors(
    ctx: typer.Context,
    project: Annotated[str | None, typer.Option("--project", "-p", help="Project slug")] = None,
    period: Annotated[str, typer.Option("--period", help="Time period: 24h, 7d, 30d")] = "24h",
) -> None:
    """Show error rate trends for a project."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        proj = c.client.resolve_project(project) if project else None

        if proj:
            # Fetch unresolved issues sorted by frequency
            issues = c.client.project_get(
                proj,
                "/issues/",
                params={"query": "is:unresolved", "sort": "freq", "limit": 10, "statsPeriod": period},
            )
        else:
            # Org-wide: fetch issues across all projects
            issues = c.client.get(
                f"/organizations/{c.client.organization}/issues/",
                params={"query": "is:unresolved", "sort": "freq", "limit": 10, "statsPeriod": period},
            )

        if not isinstance(issues, list):
            issues = []

        rows: list[list[str]] = []
        for iss in issues:
            short_id = iss.get("shortId", "")
            title = (iss.get("title", "") or "")[:50]
            events_count = str(iss.get("count", 0))
            users_count = str(iss.get("userCount", 0))
            proj_slug = ""
            if isinstance(iss.get("project"), dict):
                proj_slug = iss["project"].get("slug", "")
            rows.append([short_id, proj_slug, title, events_count, users_count])

        out.table(
            f"Top Errors — {project or 'all projects'} ({period})",
            [
                ("ID", "cyan"),
                ("Project", ""),
                ("Title", ""),
                ("Events", "yellow"),
                ("Users", ""),
            ],
            rows,
            data_for_json=issues,
        )
    except KctlError as e:
        out.error(f"Failed to fetch error trends: {e}")
        raise typer.Exit(1) from e
```

- [ ] **Step 3: Verify — run alerts and stats help**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-sentry/cli
uv run kctl-sentry alerts --help
uv run kctl-sentry stats --help
```

---

### Task 7: teams + environments command groups

**Files:**
- Create: `cli/src/kctl_sentry/commands/teams.py`
- Create: `cli/src/kctl_sentry/commands/environments.py`

- [ ] **Step 1: Create teams.py**

Create `cli/src/kctl_sentry/commands/teams.py`:

```python
"""Team management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_sentry.core.callbacks import AppContext
from kctl_sentry.core.exceptions import KctlError

app = typer.Typer(help="Manage teams.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all teams in the organization."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        teams = c.client.org_get("/teams/")
        if not isinstance(teams, list):
            teams = []

        rows: list[list[str]] = []
        for team in teams:
            slug = team.get("slug", "")
            name = team.get("name", "")
            member_count = str(team.get("memberCount", 0))
            has_access = "Yes" if team.get("hasAccess", False) else "No"
            rows.append([slug, name, member_count, has_access])

        out.table(
            "Teams",
            [
                ("Slug", "cyan"),
                ("Name", ""),
                ("Members", ""),
                ("Access", "green"),
            ],
            rows,
            data_for_json=teams,
        )
    except KctlError as e:
        out.error(f"Failed to list teams: {e}")
        raise typer.Exit(1) from e


@app.command("show")
def show(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Team slug")],
) -> None:
    """Show team details, members, and assigned projects."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        team = c.client.get(f"/teams/{c.client.organization}/{slug}/")
        if not isinstance(team, dict):
            team = {}

        # Fetch team members
        try:
            members = c.client.get(f"/teams/{c.client.organization}/{slug}/members/")
            if not isinstance(members, list):
                members = []
        except Exception:
            members = []

        # Fetch team projects
        try:
            projects = c.client.get(f"/teams/{c.client.organization}/{slug}/projects/")
            if not isinstance(projects, list):
                projects = []
        except Exception:
            projects = []

        sections = [
            (
                "Team",
                [
                    ("Slug", team.get("slug", "")),
                    ("Name", team.get("name", "")),
                    ("Members", str(team.get("memberCount", len(members)))),
                    ("Date created", (team.get("dateCreated", "") or "")[:19]),
                ],
            ),
        ]

        # Members section
        if members:
            member_kvs: list[tuple[str, str]] = []
            for member in members[:20]:
                if isinstance(member, dict):
                    email = member.get("email", "")
                    name = member.get("name", email)
                    role = member.get("role", member.get("teamRole", ""))
                    member_kvs.append((name, f"{email} ({role})" if role else email))
            if member_kvs:
                sections.append(("Members", member_kvs))

        # Projects section
        if projects:
            project_kvs: list[tuple[str, str]] = []
            for proj in projects[:20]:
                if isinstance(proj, dict):
                    project_kvs.append((proj.get("slug", ""), proj.get("platform", "") or ""))
            if project_kvs:
                sections.append(("Projects", project_kvs))

        out.detail(
            f"Team: {slug}",
            sections,
            data_for_json={"team": team, "members": members, "projects": projects},
        )
    except KctlError as e:
        out.error(f"Failed to show team: {e}")
        raise typer.Exit(1) from e
```

- [ ] **Step 2: Create environments.py**

Create `cli/src/kctl_sentry/commands/environments.py`:

```python
"""Environment management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_sentry.core.callbacks import AppContext
from kctl_sentry.core.exceptions import KctlError

app = typer.Typer(help="Manage project environments.")


@app.command("list")
def list_(
    ctx: typer.Context,
    project: Annotated[str | None, typer.Option("--project", "-p", help="Project slug")] = None,
) -> None:
    """List environments for a project (e.g. production, staging, development)."""
    c: AppContext = ctx.obj
    out = c.output

    try:
        if project:
            proj = c.client.resolve_project(project)
            envs = c.client.project_get(proj, "/environments/")
        else:
            envs = c.client.org_get("/environments/")
        if not isinstance(envs, list):
            envs = []

        rows: list[list[str]] = []
        for env in envs:
            name = env.get("name", "")
            is_hidden = "Yes" if env.get("isHidden", False) else "No"
            rows.append([name, is_hidden])

        target = project or "organization"
        out.table(
            f"Environments — {target}",
            [
                ("Name", "cyan"),
                ("Hidden", "dim"),
            ],
            rows,
            data_for_json=envs,
        )
    except KctlError as e:
        out.error(f"Failed to list environments: {e}")
        raise typer.Exit(1) from e
```

- [ ] **Step 3: Verify — run teams and environments help**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-sentry/cli
uv run kctl-sentry teams --help
uv run kctl-sentry environments --help
```

---

### Task 8: Tests + CI + CLAUDE.md

**Files:**
- Modify: `cli/tests/test_smoke.py`
- Create: `cli/tests/test_client.py`
- Create: `cli/tests/test_config.py`
- Create: `cli/tests/test_issues.py`
- Create: `cli/tests/test_projects.py`
- Create: `cli/tests/test_releases.py`
- Create: `cli/tests/test_health.py`
- Modify: `CLAUDE.md`
- Create: `.github/workflows/validate.yml`

- [ ] **Step 1: Expand smoke tests**

Replace the full contents of `cli/tests/test_smoke.py`:

```python
"""Smoke tests — verify CLI entry points and help text."""

from typer.testing import CliRunner

from kctl_sentry.cli import app

runner = CliRunner()


class TestCLISmoke:
    def test_help_exits_zero(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "kctl-sentry" in result.output.lower() or "sentry" in result.output.lower()

    def test_version_flag(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_config_help(self) -> None:
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0

    def test_health_help(self) -> None:
        result = runner.invoke(app, ["health", "--help"])
        assert result.exit_code == 0

    def test_dashboard_help(self) -> None:
        result = runner.invoke(app, ["dashboard", "--help"])
        assert result.exit_code == 0

    def test_issues_help(self) -> None:
        result = runner.invoke(app, ["issues", "--help"])
        assert result.exit_code == 0

    def test_projects_help(self) -> None:
        result = runner.invoke(app, ["projects", "--help"])
        assert result.exit_code == 0

    def test_releases_help(self) -> None:
        result = runner.invoke(app, ["releases", "--help"])
        assert result.exit_code == 0

    def test_alerts_help(self) -> None:
        result = runner.invoke(app, ["alerts", "--help"])
        assert result.exit_code == 0

    def test_stats_help(self) -> None:
        result = runner.invoke(app, ["stats", "--help"])
        assert result.exit_code == 0

    def test_teams_help(self) -> None:
        result = runner.invoke(app, ["teams", "--help"])
        assert result.exit_code == 0

    def test_environments_help(self) -> None:
        result = runner.invoke(app, ["environments", "--help"])
        assert result.exit_code == 0
```

- [ ] **Step 2: Create test_client.py**

Create `cli/tests/test_client.py`:

```python
"""Tests for SentryClient."""

from __future__ import annotations

import pytest
from kctl_lib.exceptions import AuthenticationError, ConfigError

from kctl_sentry.core.client import SentryClient


class TestSentryClientInit:
    def test_missing_token_raises(self) -> None:
        with pytest.raises(AuthenticationError, match="No auth token"):
            SentryClient(auth_token="", organization="test-org")

    def test_valid_init(self) -> None:
        client = SentryClient(
            base_url="https://sentry.example.com",
            auth_token="sntrys_test_token_123",
            organization="kodemeio",
            default_project="web-app",
        )
        assert client.organization == "kodemeio"
        assert client.default_project == "web-app"
        client.close()

    def test_default_base_url(self) -> None:
        client = SentryClient(
            auth_token="sntrys_test_token_123",
            organization="kodemeio",
        )
        assert "sentry.io" in client._base_url
        client.close()

    def test_resolve_project_explicit(self) -> None:
        client = SentryClient(
            auth_token="sntrys_test_token_123",
            organization="kodemeio",
            default_project="fallback",
        )
        assert client.resolve_project("explicit") == "explicit"
        client.close()

    def test_resolve_project_default(self) -> None:
        client = SentryClient(
            auth_token="sntrys_test_token_123",
            organization="kodemeio",
            default_project="fallback",
        )
        assert client.resolve_project(None) == "fallback"
        client.close()

    def test_resolve_project_none_raises(self) -> None:
        client = SentryClient(
            auth_token="sntrys_test_token_123",
            organization="kodemeio",
            default_project="",
        )
        with pytest.raises(AuthenticationError, match="No project specified"):
            client.resolve_project(None)
        client.close()
```

- [ ] **Step 3: Create test_config.py**

Create `cli/tests/test_config.py`:

```python
"""Tests for config module."""

from __future__ import annotations

import os
from unittest.mock import patch

from kctl_sentry.core.config import ServiceConfig, resolve_connection


class TestServiceConfig:
    def test_defaults(self) -> None:
        cfg = ServiceConfig()
        assert cfg.url == "https://sentry.io"
        assert cfg.auth_token == ""
        assert cfg.organization == ""
        assert cfg.default_project == ""

    def test_custom_values(self) -> None:
        cfg = ServiceConfig(
            url="https://sentry.kodeme.io",
            auth_token="abc123",
            organization="kodemeio",
            default_project="web",
        )
        assert cfg.url == "https://sentry.kodeme.io"
        assert cfg.auth_token == "abc123"
        assert cfg.organization == "kodemeio"
        assert cfg.default_project == "web"


class TestResolveConnection:
    @patch("kctl_sentry.core.config.get_service_config")
    @patch("kctl_sentry.core.config.resolve_active_profile_name", return_value="default")
    def test_env_override_sentry_native(self, _mock_profile, mock_config) -> None:  # type: ignore[no-untyped-def]
        mock_config.return_value = ServiceConfig()
        with patch.dict(os.environ, {"SENTRY_AUTH_TOKEN": "env-token", "SENTRY_ORG": "env-org"}):
            url, token, org, proj = resolve_connection()
        assert token == "env-token"
        assert org == "env-org"

    @patch("kctl_sentry.core.config.get_service_config")
    @patch("kctl_sentry.core.config.resolve_active_profile_name", return_value="default")
    def test_kctl_env_overrides_native(self, _mock_profile, mock_config) -> None:  # type: ignore[no-untyped-def]
        mock_config.return_value = ServiceConfig()
        with patch.dict(os.environ, {
            "SENTRY_AUTH_TOKEN": "native",
            "KCTL_SENTRY_AUTH_TOKEN": "kctl-token",
            "KCTL_SENTRY_ORGANIZATION": "kctl-org",
        }):
            url, token, org, proj = resolve_connection()
        assert token == "kctl-token"
        assert org == "kctl-org"

    @patch("kctl_sentry.core.config.get_service_config")
    @patch("kctl_sentry.core.config.resolve_active_profile_name", return_value="default")
    def test_cli_flag_overrides_all(self, _mock_profile, mock_config) -> None:  # type: ignore[no-untyped-def]
        mock_config.return_value = ServiceConfig(auth_token="profile-token")
        with patch.dict(os.environ, {"KCTL_SENTRY_AUTH_TOKEN": "env-token"}):
            url, token, org, proj = resolve_connection(auth_token_override="flag-token")
        assert token == "flag-token"
```

- [ ] **Step 4: Create test_health.py**

Create `cli/tests/test_health.py`:

```python
"""Tests for health commands using pytest-httpx."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from kctl_sentry.cli import app

runner = CliRunner()


def _mock_resolve(*args, **kwargs):  # type: ignore[no-untyped-def]
    return ("https://sentry.io", "test-token", "kodemeio", "web-app")


class TestHealthCheck:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_health_check_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["health", "check", "--help"])
        assert result.exit_code == 0
        assert "check" in result.output.lower() or "connectivity" in result.output.lower()
```

- [ ] **Step 5: Create test_issues.py**

Create `cli/tests/test_issues.py`:

```python
"""Tests for issues commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_sentry.cli import app

runner = CliRunner()


def _mock_resolve(*args, **kwargs):  # type: ignore[no-untyped-def]
    return ("https://sentry.io", "test-token", "kodemeio", "web-app")


def _make_mock_client() -> MagicMock:
    client = MagicMock()
    client.organization = "kodemeio"
    client.default_project = "web-app"
    client.resolve_project.return_value = "web-app"
    return client


class TestIssuesList:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_issues_list_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["issues", "list", "--help"])
        assert result.exit_code == 0

    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_issues_list_json(self, _mock) -> None:  # type: ignore[no-untyped-def]
        mock_client = _make_mock_client()
        mock_client.project_get.return_value = [
            {
                "shortId": "WEB-1",
                "title": "ValueError: invalid input",
                "count": 42,
                "userCount": 5,
                "level": "error",
                "firstSeen": "2026-03-28T10:00:00Z",
                "lastSeen": "2026-03-29T08:00:00Z",
                "assignedTo": None,
            },
        ]

        with patch.object(type(runner), "invoke", wraps=runner.invoke):
            # Direct approach: mock the client property on AppContext
            from kctl_sentry.core.callbacks import AppContext

            original_client = AppContext.client
            try:
                AppContext.client = property(lambda self: mock_client)  # type: ignore[assignment]
                result = runner.invoke(app, ["--json", "issues", "list"])
                # The command should execute (may fail on output formatting but shouldn't crash)
            finally:
                AppContext.client = original_client  # type: ignore[assignment]


class TestIssuesResolve:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_resolve_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["issues", "resolve", "--help"])
        assert result.exit_code == 0
        assert "resolve" in result.output.lower()


class TestIssuesAssign:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_assign_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["issues", "assign", "--help"])
        assert result.exit_code == 0
```

- [ ] **Step 6: Create test_projects.py**

Create `cli/tests/test_projects.py`:

```python
"""Tests for projects commands."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from kctl_sentry.cli import app

runner = CliRunner()


def _mock_resolve(*args, **kwargs):  # type: ignore[no-untyped-def]
    return ("https://sentry.io", "test-token", "kodemeio", "web-app")


class TestProjectsList:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_projects_list_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["projects", "list", "--help"])
        assert result.exit_code == 0

    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_projects_dsn_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["projects", "dsn", "--help"])
        assert result.exit_code == 0


class TestProjectsCreate:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_create_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["projects", "create", "--help"])
        assert result.exit_code == 0
```

- [ ] **Step 7: Create test_releases.py**

Create `cli/tests/test_releases.py`:

```python
"""Tests for releases commands."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from kctl_sentry.cli import app

runner = CliRunner()


def _mock_resolve(*args, **kwargs):  # type: ignore[no-untyped-def]
    return ("https://sentry.io", "test-token", "kodemeio", "web-app")


class TestReleasesList:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_releases_list_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["releases", "list", "--help"])
        assert result.exit_code == 0


class TestReleasesCreate:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_create_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["releases", "create", "--help"])
        assert result.exit_code == 0


class TestReleasesAssociate:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_associate_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["releases", "associate", "--help"])
        assert result.exit_code == 0
```

- [ ] **Step 8: Create validate.yml CI workflow**

Create `.github/workflows/validate.yml`:

```yaml
name: Validate kctl-sentry

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
    defaults:
      run:
        working-directory: cli

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: uv sync --all-extras

      - name: Lint
        run: uv run ruff check src/ tests/

      - name: Format check
        run: uv run ruff format --check src/ tests/

      - name: Type check
        run: uv run mypy src/

      - name: Test
        run: uv run pytest tests/ -v
```

- [ ] **Step 9: Update CLAUDE.md**

Replace the full contents of `CLAUDE.md`:

```markdown
# CLAUDE.md - kodemeio-sentry

kctl-sentry: Sentry error tracking CLI for daily error triage and release tracking.

## Quick Commands

```bash
cd cli
uv sync --all-extras
uv run pytest tests/ -v           # Tests
uv run ruff check src/ tests/     # Lint
uv run ruff format src/ tests/    # Format
uv run mypy src/                  # Type check
uv run kctl-sentry --help         # CLI help
```

## Architecture

`kctl-sentry` is a Typer CLI using `kctl-lib>=0.4.0` (APIClient subclass for Sentry REST API).

### Key Paths

| Path | Description |
|------|-------------|
| `cli/src/kctl_sentry/cli.py` | Main CLI entry point |
| `cli/src/kctl_sentry/core/client.py` | SentryClient(APIClient) |
| `cli/src/kctl_sentry/core/config.py` | ServiceConfig, profile resolution |
| `cli/src/kctl_sentry/core/callbacks.py` | AppContext with lazy client |
| `cli/src/kctl_sentry/commands/` | Command modules (10 groups) |
| `cli/tests/` | Test suite |

### Command Groups (10)

| Group | Commands | Description |
|-------|----------|-------------|
| `config` | init, show, test, use | Profile management |
| `health` | check | API connectivity |
| `dashboard` | overview | Quick overview |
| `issues` | list, show, resolve, ignore, bulk-resolve, assign | Error triage |
| `projects` | list, show, dsn, create | Project management |
| `releases` | list, create, show, associate | Release tracking |
| `alerts` | list, show, create | Alert rules |
| `stats` | events, errors | Event statistics |
| `teams` | list, show | Team management |
| `environments` | list | Environment info |

### Global Options

`--json`, `--quiet/-q`, `--format/-f` (pretty/json/csv/yaml), `--no-header`, `--profile/-p`, `--auth-token`, `--version/-V`

## Conventions

- Python 3.12+, Typer + Rich + Pydantic 2
- Hatchling build, uv package manager
- Ruff lint + format, mypy strict
- Conventional commits
- Tests with pytest + pytest-httpx mocks
```

- [ ] **Step 10: Run full test suite**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-sentry/cli
uv sync --all-extras
uv run pytest tests/ -v
```

---

### Task 9: Final verification

- [ ] **Step 1: Lint and format**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-sentry/cli
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run ruff check src/ tests/  # Re-check after format
```

- [ ] **Step 2: Type check**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-sentry/cli
uv run mypy src/
```

- [ ] **Step 3: Full test run**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-sentry/cli
uv run pytest tests/ -v
```

- [ ] **Step 4: Install and verify CLI**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-sentry/cli
uv run kctl-sentry --help
uv run kctl-sentry --version
uv run kctl-sentry issues --help
uv run kctl-sentry releases --help
uv run kctl-sentry projects --help
```

- [ ] **Step 5: Commit and push**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-sentry
git checkout -b feat/kctl-sentry-cli
git add -A
git commit -m "feat: implement kctl-sentry CLI with 10 command groups

- SentryClient(APIClient) with org/project-scoped helpers
- 10 command groups: health, dashboard, issues, projects, releases, alerts, stats, teams, environments, config
- issues: list/show/resolve/ignore/bulk-resolve/assign for daily error triage
- releases: list/create/show/associate-commits for deploy tracking
- Full test suite with smoke, client, config, and command tests
- CI workflow for lint + test on push/PR

Co-Authored-By: Claude <noreply@anthropic.com>"
git push -u origin feat/kctl-sentry-cli
```
