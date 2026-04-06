# kctl-zulip Monorepo Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a mature kctl-zulip CLI package in `packages/kctl-zulip/` by migrating the existing standalone CLI from `kodemeio-zulip/cli/` with full kctl-lib integration, comprehensive tests, and standard commands.

**Architecture:** Port 20 existing command modules as-is (they only reference `ctx.obj.client` and `ctx.obj.output`). Rewrite core layer to use kctl-lib's Output, exceptions, doctor_base, self_update, completions, and skill_generator. Keep ZulipClient custom (Basic auth + form POST + error envelope). Match kctl-grafana's proven patterns exactly.

**Tech Stack:** Python 3.12+, Typer, httpx, kctl-lib>=0.4.0, Rich, Pydantic 2, pytest, Playwright (E2E)

**Source files:** `/home/tgunawan/project/00-new-projects/kodemeio-workspace/kodemeio-zulip/cli/src/kctl_zulip/`
**Target:** `/home/tgunawan/project/00-new-projects/kodemeio-workspace/kodemeio-platform/packages/kctl-zulip/`
**Reference CLI:** `/home/tgunawan/project/00-new-projects/kodemeio-workspace/kodemeio-platform/packages/kctl-grafana/` (match this pattern)

---

## File Structure

### New files to create

```
packages/kctl-zulip/
├── pyproject.toml
├── README.md
├── src/kctl_zulip/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── callbacks.py
│   │   ├── client.py
│   │   ├── config.py
│   │   └── output.py
│   └── commands/
│       ├── __init__.py
│       ├── alert_words.py          (port from source)
│       ├── announce.py             (port from source)
│       ├── config_cmd.py           (port from source, update imports)
│       ├── dashboard.py            (port from source)
│       ├── doctor_cmd.py           (NEW)
│       ├── drafts.py               (port from source)
│       ├── emoji.py                (port from source)
│       ├── groups.py               (port from source)
│       ├── health.py               (port from source)
│       ├── invitations.py          (port from source)
│       ├── linkifiers.py           (port from source)
│       ├── messages.py             (port from source)
│       ├── muted.py                (port from source)
│       ├── presence.py             (port from source)
│       ├── profile_fields.py       (port from source)
│       ├── reactions.py            (port from source)
│       ├── realm.py                (port from source)
│       ├── scheduled.py            (port from source)
│       ├── skill_cmd.py            (NEW)
│       ├── streams.py              (port from source)
│       ├── topics.py               (port from source)
│       └── users.py                (port from source)
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_cli.py
│   ├── test_client.py
│   ├── test_config.py
│   ├── test_doctor.py
│   ├── test_resolve_connection.py
│   ├── test_users.py
│   ├── test_streams.py
│   ├── test_messages.py
│   ├── test_groups.py
│   ├── test_health.py
│   ├── test_dashboard.py
│   ├── test_emoji.py
│   ├── test_invitations.py
│   ├── test_realm.py
│   ├── test_reactions.py
│   ├── test_presence.py
│   ├── test_scheduled.py
│   ├── test_muted.py
│   ├── test_drafts.py
│   ├── test_profile_fields.py
│   ├── test_alert_words.py
│   ├── test_linkifiers.py
│   ├── test_announce.py
│   └── test_topics.py
├── e2e/
│   ├── playwright.config.ts
│   ├── package.json
│   ├── tsconfig.json
│   ├── fixtures/
│   │   └── zulip-test.ts
│   └── tests/
│       ├── global-setup.ts
│       └── scenarios/
│           └── health.spec.ts
├── skills/
│   └── zulip-admin/
│       └── SKILL.md                (placeholder, auto-generated later)
└── docs/
    └── completions.md
```

### Files to modify

- `CLAUDE.md` (root) — add kctl-zulip to workspace members table (22nd CLI)

---

## Task 1: Package Skeleton (pyproject.toml + init files)

**Files:**
- Create: `packages/kctl-zulip/pyproject.toml`
- Create: `packages/kctl-zulip/src/kctl_zulip/__init__.py`
- Create: `packages/kctl-zulip/src/kctl_zulip/__main__.py`
- Create: `packages/kctl-zulip/src/kctl_zulip/core/__init__.py`
- Create: `packages/kctl-zulip/src/kctl_zulip/commands/__init__.py`
- Create: `packages/kctl-zulip/tests/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "kctl-zulip"
version = "0.2.0"
description = "Kodemeio Zulip CLI - manage Zulip team chat"
readme = "README.md"
license = "MIT"
requires-python = ">=3.12"
authors = [{ name = "Kodemeio", email = "dev@kodeme.io" }]
dependencies = [
    "kctl-lib>=0.4.0",
    "httpx>=0.28.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-httpx>=0.35.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.9.0",
    "mypy>=1.14.0",
    "types-PyYAML>=6.0.0",
]

[project.scripts]
kctl-zulip = "kctl_zulip.cli:_run"

[tool.hatch.build.targets.wheel]
packages = ["src/kctl_zulip"]

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
    "integration: tests that read real config files",
    "smoke: tests that require a live Zulip instance",
]
```

- [ ] **Step 2: Create __init__.py**

`packages/kctl-zulip/src/kctl_zulip/__init__.py`:
```python
__version__ = "0.2.0"
```

- [ ] **Step 3: Create __main__.py**

`packages/kctl-zulip/src/kctl_zulip/__main__.py`:
```python
from kctl_zulip.cli import _run

_run()
```

- [ ] **Step 4: Create empty __init__.py files**

Create empty files:
- `packages/kctl-zulip/src/kctl_zulip/core/__init__.py`
- `packages/kctl-zulip/src/kctl_zulip/commands/__init__.py`
- `packages/kctl-zulip/tests/__init__.py`

- [ ] **Step 5: Verify workspace sees the package**

Run: `cd /home/tgunawan/project/00-new-projects/kodemeio-workspace/kodemeio-platform && uv sync --all-packages 2>&1 | grep -i zulip`
Expected: package discovered (root pyproject.toml has `members = ["packages/*"]` glob)

- [ ] **Step 6: Commit**

```bash
git add packages/kctl-zulip/pyproject.toml packages/kctl-zulip/src/ packages/kctl-zulip/tests/__init__.py
git commit -m "feat(kctl-zulip): add package skeleton with pyproject.toml"
```

---

## Task 2: Core Layer — output.py, config.py, client.py, callbacks.py

**Files:**
- Create: `packages/kctl-zulip/src/kctl_zulip/core/output.py`
- Create: `packages/kctl-zulip/src/kctl_zulip/core/config.py`
- Create: `packages/kctl-zulip/src/kctl_zulip/core/client.py`
- Create: `packages/kctl-zulip/src/kctl_zulip/core/callbacks.py`

- [ ] **Step 1: Create output.py (re-export from kctl-lib)**

`packages/kctl-zulip/src/kctl_zulip/core/output.py`:
```python
"""Output formatting — re-export from kctl-lib."""

from kctl_lib.output import Output

__all__ = ["Output"]
```

- [ ] **Step 2: Create config.py**

Port from `/home/tgunawan/project/00-new-projects/kodemeio-workspace/kodemeio-zulip/cli/src/kctl_zulip/core/config.py` with these changes:
- Replace `from kctl_zulip.core.exceptions import ConfigError` with `from kctl_lib.exceptions import ConfigError`
- Keep all functions (load_raw_config, save_raw_config, load_config, get_service_config, set_service_config, get_profile_names, get_all_services_in_profile, get_default_profile, set_default_profile, remove_profile, resolve_active_profile_name, resolve_connection)
- This matches kctl-grafana's pattern where config is local per-CLI

The file is copied verbatim from the source except the exception import change. Source: `kodemeio-zulip/cli/src/kctl_zulip/core/config.py` (244 lines).

- [ ] **Step 3: Create client.py**

Port from `/home/tgunawan/project/00-new-projects/kodemeio-workspace/kodemeio-zulip/cli/src/kctl_zulip/core/client.py` with these changes:
- Replace `from kctl_zulip.core.exceptions import APIError, AuthenticationError` with `from kctl_lib.exceptions import AuthenticationError`
- Replace `from kctl_zulip.core.exceptions import ConnectionError as KctlConnectionError` with `from kctl_lib.exceptions import ConnectionError as KctlConnectionError`
- The `APIError` class must stay local because Zulip's APIError takes an `httpx.Response` and extracts `msg` from JSON body, which differs from kctl-lib's `APIError(status_code, detail)`. Define it locally at the top of client.py:

```python
"""Zulip API client using httpx."""

from __future__ import annotations

import httpx

from kctl_lib.exceptions import AuthenticationError, KctlError
from kctl_lib.exceptions import ConnectionError as KctlConnectionError


class ZulipAPIError(KctlError):
    """Zulip API error with response details."""

    def __init__(self, response: httpx.Response):
        self.status_code = response.status_code
        self.response = response
        try:
            body = response.json()
            self.detail = body.get("msg", str(body))
        except Exception:
            text = response.text or ""
            if "<html" in text.lower():
                self.detail = f"HTTP {self.status_code}"
            else:
                self.detail = text[:200] if text else f"HTTP {self.status_code}"
        super().__init__(f"API error {self.status_code}: {self.detail}")


class ZulipClient:
    # ... rest of client.py unchanged, but use ZulipAPIError instead of APIError
```

Replace all `raise APIError(response)` with `raise ZulipAPIError(response)` in the client.

- [ ] **Step 4: Create callbacks.py**

`packages/kctl-zulip/src/kctl_zulip/core/callbacks.py`:
```python
"""Typer global callback and shared context."""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_zulip.core.client import ZulipClient
from kctl_zulip.core.config import resolve_connection
from kctl_zulip.core.output import Output


@dataclass
class AppContext:
    """Shared application context passed through Typer's ctx.obj."""

    json_mode: bool = False
    quiet: bool = False
    format: str = "pretty"
    no_header: bool = False
    profile: str | None = None
    url_override: str | None = None
    email_override: str | None = None
    api_key_override: str | None = None
    _client: ZulipClient | None = field(default=None, repr=False, init=False)
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
    def client(self) -> ZulipClient:
        if self._client is None:
            url, email, api_key = resolve_connection(
                profile_name=self.profile,
                url_override=self.url_override,
                email_override=self.email_override,
                api_key_override=self.api_key_override,
            )
            self._client = ZulipClient(base_url=url, email=email, api_key=api_key)
        return self._client

    def close(self) -> None:
        """Close underlying HTTP client."""
        if self._client is not None:
            self._client.close()
```

- [ ] **Step 5: Commit**

```bash
git add packages/kctl-zulip/src/kctl_zulip/core/
git commit -m "feat(kctl-zulip): add core layer (output, config, client, callbacks)"
```

---

## Task 3: CLI Entry Point (cli.py)

**Files:**
- Create: `packages/kctl-zulip/src/kctl_zulip/cli.py`

- [ ] **Step 1: Create cli.py**

`packages/kctl-zulip/src/kctl_zulip/cli.py`:
```python
"""Main CLI entry point for kctl-zulip."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_zulip import __version__
from kctl_zulip.core.callbacks import AppContext


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-zulip {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-zulip",
    help="Kodemeio Zulip CLI - manage your Zulip team chat.",
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
    profile: Annotated[str | None, typer.Option("--profile", "-p", help="Config profile name")] = None,
    url: Annotated[str | None, typer.Option("--url", help="API URL override")] = None,
    email: Annotated[str | None, typer.Option("--email", help="Auth email override")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="API key override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio Zulip CLI."""
    effective_format = "json" if json_output else output_format

    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output or effective_format == "json",
        quiet=quiet,
        format=effective_format,
        no_header=no_header,
        profile=profile,
        url_override=url,
        email_override=email,
        api_key_override=api_key,
    )


# --- Lazy imports to avoid circular imports and speed up startup ---

# Admin & Config
from kctl_zulip.commands.config_cmd import app as config_app
from kctl_zulip.commands.users import app as users_app
from kctl_zulip.commands.groups import app as groups_app
from kctl_zulip.commands.realm import app as realm_app
from kctl_zulip.commands.invitations import app as invitations_app

app.add_typer(config_app, name="config", rich_help_panel="Admin & Config")
app.add_typer(users_app, name="users", rich_help_panel="Admin & Config")
app.add_typer(groups_app, name="groups", rich_help_panel="Admin & Config")
app.add_typer(realm_app, name="realm", rich_help_panel="Admin & Config")
app.add_typer(invitations_app, name="invitations", rich_help_panel="Admin & Config")

# Messaging
from kctl_zulip.commands.messages import app as messages_app
from kctl_zulip.commands.streams import app as streams_app
from kctl_zulip.commands.topics import app as topics_app
from kctl_zulip.commands.announce import app as announce_app
from kctl_zulip.commands.drafts import app as drafts_app
from kctl_zulip.commands.scheduled import app as scheduled_app

app.add_typer(messages_app, name="messages", rich_help_panel="Messaging")
app.add_typer(streams_app, name="streams", rich_help_panel="Messaging")
app.add_typer(topics_app, name="topics", rich_help_panel="Messaging")
app.add_typer(announce_app, name="announce", rich_help_panel="Messaging")
app.add_typer(drafts_app, name="drafts", rich_help_panel="Messaging")
app.add_typer(scheduled_app, name="scheduled", rich_help_panel="Messaging")

# Personalization
from kctl_zulip.commands.emoji import app as emoji_app
from kctl_zulip.commands.reactions import app as reactions_app
from kctl_zulip.commands.presence import app as presence_app
from kctl_zulip.commands.muted import app as muted_app
from kctl_zulip.commands.alert_words import app as alert_words_app
from kctl_zulip.commands.profile_fields import app as profile_fields_app
from kctl_zulip.commands.linkifiers import app as linkifiers_app

app.add_typer(emoji_app, name="emoji", rich_help_panel="Personalization")
app.add_typer(reactions_app, name="reactions", rich_help_panel="Personalization")
app.add_typer(presence_app, name="presence", rich_help_panel="Personalization")
app.add_typer(muted_app, name="muted", rich_help_panel="Personalization")
app.add_typer(alert_words_app, name="alert-words", rich_help_panel="Personalization")
app.add_typer(profile_fields_app, name="profile-fields", rich_help_panel="Personalization")
app.add_typer(linkifiers_app, name="linkifiers", rich_help_panel="Personalization")

# Monitoring
from kctl_zulip.commands.health import app as health_app
from kctl_zulip.commands.dashboard import app as dashboard_app

app.add_typer(health_app, name="health", rich_help_panel="Monitoring")
app.add_typer(dashboard_app, name="dashboard", rich_help_panel="Monitoring")

# Tools
from kctl_zulip.commands.doctor_cmd import app as doctor_app
from kctl_zulip.commands.skill_cmd import app as skill_app

app.add_typer(doctor_app, name="doctor", rich_help_panel="Tools")
app.add_typer(skill_app, name="skill", hidden=True)


@app.command("self-update", rich_help_panel="Tools")
def self_update_cmd(ctx: typer.Context) -> None:
    """Check for updates and upgrade kctl-zulip."""
    actx = ctx.obj
    out = actx.output

    from kctl_lib.self_update import check_update
    from kctl_lib.self_update import update as do_update

    latest = check_update("kctl-zulip", __version__)
    if latest:
        out.info(f"Updating to {latest}...")
        do_update("kctl-zulip")
        out.success(f"Updated to {latest}")
    else:
        out.success("Already up to date")


@app.command(rich_help_panel="Tools")
def completions(
    shell: Annotated[str, typer.Argument(help="Shell type: zsh, bash, fish")] = "zsh",
    install: Annotated[bool, typer.Option("--install", help="Install completions")] = False,
) -> None:
    """Generate or install shell completions."""
    from kctl_lib.completions import get_completion_script, install_completions

    if install:
        path = install_completions("kctl-zulip", shell)
        if path:
            typer.echo(f"Completions installed to {path}")
        else:
            typer.echo(f"Could not install completions for {shell}", err=True)
            raise typer.Exit(code=1)
    else:
        script = get_completion_script("kctl-zulip", shell)
        typer.echo(script)


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
```

- [ ] **Step 2: Commit**

```bash
git add packages/kctl-zulip/src/kctl_zulip/cli.py
git commit -m "feat(kctl-zulip): add CLI entry point with global options and standard commands"
```

---

## Task 4: Port 20 Command Modules

**Files:**
- Create: all 20 command files in `packages/kctl-zulip/src/kctl_zulip/commands/`

- [ ] **Step 1: Copy all command files from source**

Copy each file from `/home/tgunawan/project/00-new-projects/kodemeio-workspace/kodemeio-zulip/cli/src/kctl_zulip/commands/` to `packages/kctl-zulip/src/kctl_zulip/commands/`. Files to copy:

- `alert_words.py`
- `announce.py`
- `config_cmd.py`
- `dashboard.py`
- `drafts.py`
- `emoji.py`
- `groups.py`
- `health.py`
- `invitations.py`
- `linkifiers.py`
- `messages.py`
- `muted.py`
- `presence.py`
- `profile_fields.py`
- `reactions.py`
- `realm.py`
- `scheduled.py`
- `streams.py`
- `topics.py`
- `users.py`

- [ ] **Step 2: Update imports in config_cmd.py**

In `config_cmd.py`, change:
- `from kctl_zulip.core.exceptions import KctlError` → `from kctl_lib.exceptions import KctlError`

All other command files only import `from kctl_zulip.core.callbacks import AppContext` — no changes needed.

- [ ] **Step 3: Verify the CLI loads**

Run: `cd /home/tgunawan/project/00-new-projects/kodemeio-workspace/kodemeio-platform && uv run python -m kctl_zulip --help`
Expected: Help output showing all 22 command groups organized by panels

- [ ] **Step 4: Commit**

```bash
git add packages/kctl-zulip/src/kctl_zulip/commands/
git commit -m "feat(kctl-zulip): port 20 command modules from standalone CLI"
```

---

## Task 5: Doctor Command

**Files:**
- Create: `packages/kctl-zulip/src/kctl_zulip/commands/doctor_cmd.py`

- [ ] **Step 1: Create doctor_cmd.py**

`packages/kctl-zulip/src/kctl_zulip/commands/doctor_cmd.py`:
```python
"""Doctor diagnostic checks for kctl-zulip."""

from __future__ import annotations

from dataclasses import dataclass

import typer

from kctl_zulip.core.callbacks import AppContext
from kctl_lib.doctor_base import CheckResult, DoctorCheck, run_doctor


@dataclass
class ConfigCheck:
    """Check that a Zulip profile is configured."""

    name: str = "Configuration"

    def run(self) -> CheckResult:
        try:
            from kctl_zulip.core.config import get_service_config, resolve_active_profile_name

            profile = resolve_active_profile_name()
            cfg = get_service_config(profile)
            if not cfg.url:
                return CheckResult(
                    name=self.name,
                    status="fail",
                    message="No URL configured",
                    fix_command="kctl-zulip config init",
                )
            return CheckResult(
                name=self.name,
                status="ok",
                message=f"Profile: {profile}, URL: {cfg.url}",
            )
        except Exception as e:
            return CheckResult(name=self.name, status="warn", message=str(e))


@dataclass
class APIConnectivityCheck:
    """Check that the Zulip server is reachable (no auth needed)."""

    name: str = "API Connectivity"

    def run(self) -> CheckResult:
        try:
            import httpx
            from kctl_zulip.core.config import get_service_config, resolve_active_profile_name

            profile = resolve_active_profile_name()
            cfg = get_service_config(profile)
            if not cfg.url:
                return CheckResult(
                    name=self.name,
                    status="fail",
                    message="No URL configured",
                    fix_command="kctl-zulip config init",
                )

            r = httpx.get(f"{cfg.url.rstrip('/')}/api/v1/server_settings", timeout=10)
            if r.status_code == 200:
                version = r.json().get("zulip_version", "unknown")
                return CheckResult(
                    name=self.name,
                    status="ok",
                    message=f"Zulip {version} (200 OK)",
                )
            return CheckResult(
                name=self.name,
                status="fail",
                message=f"HTTP {r.status_code}",
            )
        except Exception as e:
            return CheckResult(name=self.name, status="fail", message=str(e))


@dataclass
class AuthCheck:
    """Check that authentication credentials work."""

    name: str = "Authentication"

    def run(self) -> CheckResult:
        try:
            from kctl_zulip.core.config import resolve_connection

            url, email, api_key = resolve_connection()
            if not email or not api_key:
                return CheckResult(
                    name=self.name,
                    status="fail",
                    message="No email/api_key configured",
                    fix_command="kctl-zulip config init",
                )

            from kctl_zulip.core.client import ZulipClient

            client = ZulipClient(base_url=url, email=email, api_key=api_key)
            data = client.get("users/me")
            client.close()
            user = data.get("email", "unknown")
            role = data.get("role", "")
            role_name = {100: "owner", 200: "admin", 300: "moderator", 400: "member", 600: "guest"}.get(role, str(role))
            return CheckResult(
                name=self.name,
                status="ok",
                message=f"Authenticated as {user} ({role_name})",
            )
        except Exception as e:
            return CheckResult(
                name=self.name,
                status="fail",
                message=str(e),
                fix_command="kctl-zulip config set api_key <new-key>",
            )


app = typer.Typer(help="Run diagnostic checks.", no_args_is_help=False, invoke_without_command=True)


@app.callback(invoke_without_command=True)
def doctor(ctx: typer.Context) -> None:
    """Run all diagnostic checks."""
    if ctx.invoked_subcommand is not None:
        return
    actx: AppContext = ctx.obj
    out = actx.output

    checks: list[DoctorCheck] = [
        ConfigCheck(),
        APIConnectivityCheck(),
        AuthCheck(),
    ]

    all_passed = run_doctor(checks, out)  # type: ignore[arg-type]
    if not all_passed:
        raise typer.Exit(code=1)
```

- [ ] **Step 2: Commit**

```bash
git add packages/kctl-zulip/src/kctl_zulip/commands/doctor_cmd.py
git commit -m "feat(kctl-zulip): add doctor command with 3 diagnostic checks"
```

---

## Task 6: Skill Command

**Files:**
- Create: `packages/kctl-zulip/src/kctl_zulip/commands/skill_cmd.py`
- Create: `packages/kctl-zulip/skills/zulip-admin/SKILL.md` (placeholder)

- [ ] **Step 1: Create skill_cmd.py**

`packages/kctl-zulip/src/kctl_zulip/commands/skill_cmd.py`:
```python
"""Skill generation for Claude Code integration."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from kctl_zulip.core.callbacks import AppContext

app = typer.Typer(help="Claude Code skill management.")


@app.command()
def generate(
    ctx: typer.Context,
    output: Annotated[str, typer.Option("--output", "-o", help="Output directory")] = "",
    install: Annotated[bool, typer.Option("--install", help="Install to ~/.claude/skills/")] = False,
    check: Annotated[bool, typer.Option("--check", help="Check if SKILL.md is stale (exit 1 if stale)")] = False,
) -> None:
    """Auto-generate SKILL.md from CLI command registry."""
    actx: AppContext = ctx.obj
    out = actx.output
    from kctl_lib.skill_generator import check_stale, generate_skill

    from kctl_zulip.cli import app as cli_app

    skill_name = "zulip-admin"
    description = "Zulip team chat administration via kctl-zulip CLI"

    if output:
        output_dir = Path(output)
    elif install:
        output_dir = Path.home() / ".claude" / "skills" / skill_name
    else:
        cli_root = Path(__file__).resolve().parents[3]
        output_dir = cli_root / "skills" / skill_name

    if check:
        skill_file = output_dir / "SKILL.md"
        is_stale, reason = check_stale(cli_app, skill_file)
        if is_stale:
            out.warn(f"SKILL.md is stale: {reason}")
            out.info("Run: kctl-zulip skill generate")
            raise typer.Exit(1)
        out.success(f"SKILL.md is up to date: {reason}")
        return

    extra = output_dir / "SKILL.extra.md"

    generate_skill(
        cli_app,
        "kctl-zulip",
        skill_name,
        description,
        output_dir=output_dir,
        extra_file=extra if extra.exists() else None,
    )
    out.success(f"Generated {output_dir / 'SKILL.md'}")
    if install:
        out.success(f"Installed to ~/.claude/skills/{skill_name}/")
```

- [ ] **Step 2: Create placeholder SKILL.md**

Create directory `packages/kctl-zulip/skills/zulip-admin/` and a placeholder `SKILL.md`:
```markdown
---
name: zulip-admin
description: Zulip team chat administration via kctl-zulip CLI. Auto-generate with `kctl-zulip skill generate`.
---

Run `kctl-zulip skill generate` to auto-generate this file from the CLI command registry.
```

- [ ] **Step 3: Commit**

```bash
git add packages/kctl-zulip/src/kctl_zulip/commands/skill_cmd.py packages/kctl-zulip/skills/
git commit -m "feat(kctl-zulip): add skill generate command and placeholder SKILL.md"
```

---

## Task 7: Test Infrastructure (conftest.py + test_cli.py + test_client.py)

**Files:**
- Create: `packages/kctl-zulip/tests/conftest.py`
- Create: `packages/kctl-zulip/tests/test_cli.py`
- Create: `packages/kctl-zulip/tests/test_client.py`

- [ ] **Step 1: Create conftest.py**

`packages/kctl-zulip/tests/conftest.py`:
```python
"""Shared test fixtures for kctl-zulip."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_zulip.cli import app
from kctl_zulip.core.callbacks import AppContext
from kctl_zulip.core.client import ZulipClient
from kctl_zulip.core.output import Output


@pytest.fixture
def runner() -> CliRunner:
    """Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    """Mock ZulipClient."""
    client = MagicMock(spec=ZulipClient)
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


@pytest.fixture
def mock_config(tmp_path: Path):
    """Redirect config to a temp directory."""
    config_dir = tmp_path / "kodemeio"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.yaml"
    config_file.write_text("default_profile: default\nprofiles: {}\n")
    with patch("kctl_zulip.core.config.CONFIG_FILE", config_file), \
         patch("kctl_zulip.core.config.CONFIG_DIR", config_dir):
        yield config_file
```

- [ ] **Step 2: Create test_cli.py**

`packages/kctl-zulip/tests/test_cli.py`:
```python
"""Tests for CLI entry point."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_zulip.cli import app


def test_version_flag(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "kctl-zulip" in result.output


def test_help(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Kodemeio Zulip CLI" in result.output


def test_no_args_shows_help(runner: CliRunner) -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Usage" in result.output


def test_unknown_command(runner: CliRunner) -> None:
    result = runner.invoke(app, ["nonexistent"])
    assert result.exit_code != 0
```

- [ ] **Step 3: Create test_client.py**

`packages/kctl-zulip/tests/test_client.py`:
```python
"""Tests for ZulipClient."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from kctl_zulip.core.client import ZulipAPIError, ZulipClient


def test_client_init_requires_url() -> None:
    from kctl_lib.exceptions import ConnectionError as KctlConnectionError
    with pytest.raises(KctlConnectionError, match="No API URL"):
        ZulipClient(base_url="", email="a@b.com", api_key="key")


def test_client_init_requires_credentials() -> None:
    from kctl_lib.exceptions import AuthenticationError
    with pytest.raises(AuthenticationError, match="No email/api_key"):
        ZulipClient(base_url="https://zulip.example.com", email="", api_key="")


def test_check_response_error_envelope() -> None:
    """Zulip returns 200 with result=error — client should raise."""
    client = ZulipClient.__new__(ZulipClient)
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.content = b'{"result": "error", "msg": "Stream not found"}'
    response.json.return_value = {"result": "error", "msg": "Stream not found"}
    response.text = '{"result": "error", "msg": "Stream not found"}'

    with pytest.raises(ZulipAPIError, match="Stream not found"):
        client._check_response(response)


def test_check_response_401() -> None:
    from kctl_lib.exceptions import AuthenticationError
    client = ZulipClient.__new__(ZulipClient)
    response = MagicMock(spec=httpx.Response)
    response.status_code = 401

    with pytest.raises(AuthenticationError):
        client._check_response(response)


def test_check_response_success() -> None:
    """200 with result=success should not raise."""
    client = ZulipClient.__new__(ZulipClient)
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.content = b'{"result": "success"}'
    response.json.return_value = {"result": "success"}

    client._check_response(response)  # Should not raise
```

- [ ] **Step 4: Run tests**

Run: `cd /home/tgunawan/project/00-new-projects/kodemeio-workspace/kodemeio-platform && uv run pytest packages/kctl-zulip/tests/ -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add packages/kctl-zulip/tests/
git commit -m "test(kctl-zulip): add conftest, CLI, and client tests"
```

---

## Task 8: Command Unit Tests — Batch 1 (users, streams, messages, groups)

**Files:**
- Create: `packages/kctl-zulip/tests/test_users.py`
- Create: `packages/kctl-zulip/tests/test_streams.py`
- Create: `packages/kctl-zulip/tests/test_messages.py`
- Create: `packages/kctl-zulip/tests/test_groups.py`

- [ ] **Step 1: Create test_users.py**

`packages/kctl-zulip/tests/test_users.py`:
```python
"""Tests for users commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("url", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_users_list(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.get.return_value = {
        "members": [
            {"user_id": 1, "email": "alice@x.com", "full_name": "Alice", "role": 200, "is_active": True, "is_bot": False},
        ]
    }
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["users", "list", "--json"])
    assert result.exit_code == 0
    mock_client.get.assert_called_once()


def test_users_get(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.get.return_value = {
        "user": {"user_id": 1, "email": "alice@x.com", "full_name": "Alice", "role": 400}
    }
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["users", "get", "1", "--json"])
    assert result.exit_code == 0


def test_users_create(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.post.return_value = {"user_id": 42}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["users", "create", "bob@x.com", "--name", "Bob", "--password", "secret", "--json"])
    assert result.exit_code == 0
    mock_client.post.assert_called_once()


def test_users_deactivate_with_force(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.delete.return_value = {}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["users", "deactivate", "1", "--force"])
    assert result.exit_code == 0
    mock_client.delete.assert_called_once()


def test_users_reactivate(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.post.return_value = {}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["users", "reactivate", "1"])
    assert result.exit_code == 0
```

- [ ] **Step 2: Create test_streams.py**

`packages/kctl-zulip/tests/test_streams.py`:
```python
"""Tests for streams commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("url", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_streams_list(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.get.return_value = {
        "streams": [{"stream_id": 1, "name": "general", "description": "General chat", "invite_only": False, "stream_weekly_traffic": 42}]
    }
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["streams", "list", "--json"])
    assert result.exit_code == 0


def test_streams_get(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.get.side_effect = [
        {"stream_id": 1},  # get_stream_id
        {"stream": {"stream_id": 1, "name": "general"}},  # streams/1
        {"subscribers": [1, 2, 3]},  # streams/1/members
    ]
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["streams", "get", "1", "--json"])
    assert result.exit_code == 0


def test_streams_create(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.post.return_value = {"subscribed": {"user@x.com": ["test-stream"]}}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["streams", "create", "test-stream"])
    assert result.exit_code == 0


def test_streams_delete_force(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.get.return_value = {"stream_id": 1}
    mock_client.delete.return_value = {}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["streams", "delete", "1", "--force"])
    assert result.exit_code == 0


def test_streams_subscribe(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.post.return_value = {"subscribed": {"user@x.com": ["general"]}, "already_subscribed": {}}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["streams", "subscribe", "general"])
    assert result.exit_code == 0
```

- [ ] **Step 3: Create test_messages.py**

`packages/kctl-zulip/tests/test_messages.py`:
```python
"""Tests for messages commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("url", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_messages_send_stream(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.post.return_value = {"id": 123}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["messages", "send", "Hello", "--stream", "general", "--topic", "test"])
    assert result.exit_code == 0
    mock_client.post.assert_called_once()


def test_messages_send_dm(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.post.return_value = {"id": 124}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["messages", "send", "Hi", "--to", "alice@x.com"])
    assert result.exit_code == 0


def test_messages_delete_force(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.delete.return_value = {}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["messages", "delete", "123", "--force"])
    assert result.exit_code == 0
```

- [ ] **Step 4: Create test_groups.py**

`packages/kctl-zulip/tests/test_groups.py`:
```python
"""Tests for groups commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("url", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_groups_list(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.get.return_value = {"user_groups": [{"id": 1, "name": "admins", "description": "Admin group", "members": [1, 2]}]}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["groups", "list", "--json"])
    assert result.exit_code == 0


def test_groups_create(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.post.return_value = {}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["groups", "create", "devs", "-d", "Developers"])
    assert result.exit_code == 0


def test_groups_delete_force(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.delete.return_value = {}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["groups", "delete", "1", "--force"])
    assert result.exit_code == 0
```

- [ ] **Step 5: Run tests**

Run: `cd /home/tgunawan/project/00-new-projects/kodemeio-workspace/kodemeio-platform && uv run pytest packages/kctl-zulip/tests/ -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add packages/kctl-zulip/tests/test_users.py packages/kctl-zulip/tests/test_streams.py packages/kctl-zulip/tests/test_messages.py packages/kctl-zulip/tests/test_groups.py
git commit -m "test(kctl-zulip): add unit tests for users, streams, messages, groups"
```

---

## Task 9: Command Unit Tests — Batch 2 (health, dashboard, emoji, invitations, realm, reactions)

**Files:**
- Create: `packages/kctl-zulip/tests/test_health.py`
- Create: `packages/kctl-zulip/tests/test_dashboard.py`
- Create: `packages/kctl-zulip/tests/test_emoji.py`
- Create: `packages/kctl-zulip/tests/test_invitations.py`
- Create: `packages/kctl-zulip/tests/test_realm.py`
- Create: `packages/kctl-zulip/tests/test_reactions.py`

- [ ] **Step 1: Create all 6 test files**

Each follows the same pattern — patch `resolve_connection` + `ZulipClient`, invoke CLI command, assert exit code 0 and correct client method called. Use the same `_patch_client` helper.

**test_health.py:** Test health check returns server info.
```python
"""Tests for health command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("url", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_health(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.check_health.return_value = {"zulip_version": "10.2"}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["health"])
    assert result.exit_code == 0
```

**test_dashboard.py:**
```python
"""Tests for dashboard command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("url", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_dashboard(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.check_health.return_value = {"zulip_version": "10.2"}
    mock_client.get.side_effect = [
        {"members": [{"user_id": 1, "is_active": True}]},  # users
        {"streams": [{"stream_id": 1}]},  # streams
    ]
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["dashboard", "--json"])
    assert result.exit_code == 0
```

**test_emoji.py:**
```python
"""Tests for emoji commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("url", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_emoji_list(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.get.return_value = {"emoji": {"smile": {"author_id": 1, "deactivated": False}}}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["emoji", "list", "--json"])
    assert result.exit_code == 0


def test_emoji_delete_force(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.delete.return_value = {}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["emoji", "delete", "smile", "--force"])
    assert result.exit_code == 0
```

**test_invitations.py:**
```python
"""Tests for invitations commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("url", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_invitations_list(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.get.return_value = {"invites": []}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["invitations", "list", "--json"])
    assert result.exit_code == 0


def test_invitations_create(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.post.return_value = {}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["invitations", "create", "bob@x.com"])
    assert result.exit_code == 0
```

**test_realm.py:**
```python
"""Tests for realm commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("url", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_realm_settings(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.get.return_value = {"name": "Kodemeio", "authentication_methods": {}}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["realm", "settings", "--json"])
    assert result.exit_code == 0
```

**test_reactions.py:**
```python
"""Tests for reactions commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("url", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_reactions_add(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.post.return_value = {}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["reactions", "add", "123", "thumbs_up"])
    assert result.exit_code == 0


def test_reactions_list(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.get.return_value = {"message": {"reactions": []}}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["reactions", "list", "123", "--json"])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run tests**

Run: `cd /home/tgunawan/project/00-new-projects/kodemeio-workspace/kodemeio-platform && uv run pytest packages/kctl-zulip/tests/ -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add packages/kctl-zulip/tests/test_health.py packages/kctl-zulip/tests/test_dashboard.py packages/kctl-zulip/tests/test_emoji.py packages/kctl-zulip/tests/test_invitations.py packages/kctl-zulip/tests/test_realm.py packages/kctl-zulip/tests/test_reactions.py
git commit -m "test(kctl-zulip): add unit tests for health, dashboard, emoji, invitations, realm, reactions"
```

---

## Task 10: Command Unit Tests — Batch 3 (remaining 10 command modules)

**Files:**
- Create: `packages/kctl-zulip/tests/test_presence.py`
- Create: `packages/kctl-zulip/tests/test_scheduled.py`
- Create: `packages/kctl-zulip/tests/test_muted.py`
- Create: `packages/kctl-zulip/tests/test_drafts.py`
- Create: `packages/kctl-zulip/tests/test_profile_fields.py`
- Create: `packages/kctl-zulip/tests/test_alert_words.py`
- Create: `packages/kctl-zulip/tests/test_linkifiers.py`
- Create: `packages/kctl-zulip/tests/test_announce.py`
- Create: `packages/kctl-zulip/tests/test_topics.py`
- Create: `packages/kctl-zulip/tests/test_doctor.py`

- [ ] **Step 1: Create all 10 test files**

Each follows the same `_patch_client` pattern. Core tests per file:

**test_presence.py:** test list, get, set-status
**test_scheduled.py:** test list, create, delete
**test_muted.py:** test topics, mute-topic, unmute-topic
**test_drafts.py:** test list, create, delete
**test_profile_fields.py:** test list, create, delete
**test_alert_words.py:** test list, add, remove
**test_linkifiers.py:** test list, create, delete
**test_announce.py:** test announce send
**test_topics.py:** test list
**test_doctor.py:** test doctor runs checks (patch config + httpx + ZulipClient)

Example `test_doctor.py`:
```python
"""Tests for doctor command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app
from kctl_zulip.core.config import ServiceConfig


def test_doctor_all_pass(runner: CliRunner) -> None:
    mock_svc = ServiceConfig(url="https://zulip.kodeme.io", email="bot@x.com", api_key="key123")

    with patch("kctl_zulip.commands.doctor_cmd.resolve_active_profile_name", return_value="default"), \
         patch("kctl_zulip.commands.doctor_cmd.get_service_config", return_value=mock_svc), \
         patch("kctl_zulip.commands.doctor_cmd.resolve_connection", return_value=("https://zulip.kodeme.io", "bot@x.com", "key123")), \
         patch("httpx.get") as mock_get, \
         patch("kctl_zulip.commands.doctor_cmd.ZulipClient") as mock_client_cls:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"zulip_version": "10.2"})
        mock_inst = MagicMock()
        mock_inst.get.return_value = {"email": "bot@x.com", "role": 200}
        mock_client_cls.return_value = mock_inst

        result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0


def test_doctor_no_config(runner: CliRunner) -> None:
    mock_svc = ServiceConfig()

    with patch("kctl_zulip.commands.doctor_cmd.resolve_active_profile_name", return_value="default"), \
         patch("kctl_zulip.commands.doctor_cmd.get_service_config", return_value=mock_svc), \
         patch("kctl_zulip.commands.doctor_cmd.resolve_connection", return_value=("", "", "")):
        result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
```

Example `test_announce.py`:
```python
"""Tests for announce command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("url", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_announce(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.post.return_value = {"id": 999}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["announce", "Hello everyone", "--stream", "general", "--topic", "Announcement"])
    assert result.exit_code == 0
```

Example `test_topics.py`:
```python
"""Tests for topics command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("url", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_topics_list(runner: CliRunner, mock_client: MagicMock) -> None:
    mock_client.get.return_value = {"topics": [{"name": "intro", "max_id": 100}]}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["topics", "list", "--stream", "general", "--json"])
    assert result.exit_code == 0
```

All remaining test files (presence, scheduled, muted, drafts, profile_fields, alert_words, linkifiers) follow the identical pattern: `_patch_client`, invoke command, assert exit_code == 0.

- [ ] **Step 2: Run all tests**

Run: `cd /home/tgunawan/project/00-new-projects/kodemeio-workspace/kodemeio-platform && uv run pytest packages/kctl-zulip/tests/ -v --tb=short`
Expected: 50+ tests pass

- [ ] **Step 3: Commit**

```bash
git add packages/kctl-zulip/tests/
git commit -m "test(kctl-zulip): add unit tests for remaining command modules and doctor"
```

---

## Task 11: Config Resolution Tests

**Files:**
- Create: `packages/kctl-zulip/tests/test_resolve_connection.py`
- Create: `packages/kctl-zulip/tests/test_config.py`

- [ ] **Step 1: Create test_resolve_connection.py**

`packages/kctl-zulip/tests/test_resolve_connection.py`:
```python
"""Tests for config resolution priority."""

from __future__ import annotations

from unittest.mock import patch

from kctl_zulip.core.config import ServiceConfig, resolve_connection


def test_cli_flags_override_everything() -> None:
    with patch("kctl_zulip.core.config.get_service_config", return_value=ServiceConfig(url="config-url", email="config@x", api_key="config-key")), \
         patch("kctl_zulip.core.config.resolve_active_profile_name", return_value="default"), \
         patch.dict("os.environ", {}, clear=True):
        url, email, key = resolve_connection(
            url_override="cli-url",
            email_override="cli@x",
            api_key_override="cli-key",
        )
    assert url == "cli-url"
    assert email == "cli@x"
    assert key == "cli-key"


def test_env_vars_override_config() -> None:
    import os
    with patch("kctl_zulip.core.config.get_service_config", return_value=ServiceConfig(url="config-url", email="config@x", api_key="config-key")), \
         patch("kctl_zulip.core.config.resolve_active_profile_name", return_value="default"), \
         patch.dict(os.environ, {"KCTL_ZULIP_URL": "env-url", "KCTL_ZULIP_EMAIL": "env@x", "KCTL_ZULIP_API_KEY": "env-key"}):
        url, email, key = resolve_connection()
    assert url == "env-url"
    assert email == "env@x"
    assert key == "env-key"


def test_config_file_is_baseline() -> None:
    with patch("kctl_zulip.core.config.get_service_config", return_value=ServiceConfig(url="cfg-url", email="cfg@x", api_key="cfg-key")), \
         patch("kctl_zulip.core.config.resolve_active_profile_name", return_value="default"), \
         patch.dict("os.environ", {}, clear=True):
        url, email, key = resolve_connection()
    assert url == "cfg-url"
    assert email == "cfg@x"
    assert key == "cfg-key"


def test_missing_config_returns_empty() -> None:
    with patch("kctl_zulip.core.config.get_service_config", return_value=ServiceConfig()), \
         patch("kctl_zulip.core.config.resolve_active_profile_name", return_value="default"), \
         patch.dict("os.environ", {}, clear=True):
        url, email, key = resolve_connection()
    assert url == ""
    assert email == ""
    assert key == ""
```

- [ ] **Step 2: Create test_config.py**

`packages/kctl-zulip/tests/test_config.py`:
```python
"""Tests for config commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import yaml
from typer.testing import CliRunner

from kctl_zulip.cli import app


def test_config_show(runner: CliRunner, mock_config: Path) -> None:
    # Write a profile to the temp config
    data = {
        "default_profile": "test",
        "profiles": {
            "test": {
                "zulip": {"url": "https://zulip.test.io", "email": "bot@test.io", "api_key": "secret123456"}
            }
        },
    }
    mock_config.write_text(yaml.dump(data))

    result = runner.invoke(app, ["config", "show", "--json"])
    assert result.exit_code == 0


def test_config_profiles_empty(runner: CliRunner, mock_config: Path) -> None:
    result = runner.invoke(app, ["config", "profiles"])
    assert result.exit_code == 0
```

- [ ] **Step 3: Run tests**

Run: `cd /home/tgunawan/project/00-new-projects/kodemeio-workspace/kodemeio-platform && uv run pytest packages/kctl-zulip/tests/ -v --tb=short`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add packages/kctl-zulip/tests/test_resolve_connection.py packages/kctl-zulip/tests/test_config.py
git commit -m "test(kctl-zulip): add config resolution and config command tests"
```

---

## Task 12: E2E Skeleton (Playwright)

**Files:**
- Create: `packages/kctl-zulip/e2e/package.json`
- Create: `packages/kctl-zulip/e2e/playwright.config.ts`
- Create: `packages/kctl-zulip/e2e/tsconfig.json`
- Create: `packages/kctl-zulip/e2e/fixtures/zulip-test.ts`
- Create: `packages/kctl-zulip/e2e/tests/global-setup.ts`
- Create: `packages/kctl-zulip/e2e/tests/scenarios/health.spec.ts`

- [ ] **Step 1: Create package.json**

`packages/kctl-zulip/e2e/package.json`:
```json
{
  "name": "kctl-zulip-e2e",
  "private": true,
  "scripts": {
    "test": "npx playwright test",
    "test:headed": "npx playwright test --headed",
    "report": "npx playwright show-report"
  },
  "devDependencies": {
    "@playwright/test": "^1.48.0",
    "typescript": "^5.6.0"
  }
}
```

- [ ] **Step 2: Create playwright.config.ts**

`packages/kctl-zulip/e2e/playwright.config.ts`:
```typescript
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  retries: 0,
  reporter: [['html', { open: 'never' }]],
  use: {
    baseURL: process.env.ZULIP_URL || 'https://zulip.kodeme.io',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'setup', testMatch: /global-setup\.ts/ },
    {
      name: 'desktop',
      dependencies: ['setup'],
      use: { viewport: { width: 1280, height: 720 } },
      testMatch: /scenarios\/.*\.spec\.ts/,
    },
  ],
});
```

- [ ] **Step 3: Create tsconfig.json**

`packages/kctl-zulip/e2e/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["**/*.ts"]
}
```

- [ ] **Step 4: Create fixtures/zulip-test.ts**

`packages/kctl-zulip/e2e/fixtures/zulip-test.ts`:
```typescript
import { test as base, expect } from '@playwright/test';

const ZULIP_URL = process.env.ZULIP_URL || 'https://zulip.kodeme.io';
const ZULIP_EMAIL = process.env.ZULIP_EMAIL || '';
const ZULIP_API_KEY = process.env.ZULIP_API_KEY || '';

export interface ZulipFixtures {
  zulipURL: string;
  zulipEmail: string;
  zulipAPIKey: string;
}

export const test = base.extend<ZulipFixtures>({
  zulipURL: ZULIP_URL,
  zulipEmail: ZULIP_EMAIL,
  zulipAPIKey: ZULIP_API_KEY,
});

export { expect };
```

- [ ] **Step 5: Create tests/global-setup.ts**

`packages/kctl-zulip/e2e/tests/global-setup.ts`:
```typescript
import { test } from '../fixtures/zulip-test';

test('verify environment', async ({ zulipURL }) => {
  test.skip(!zulipURL, 'ZULIP_URL not set');
  console.log(`Zulip URL: ${zulipURL}`);
});
```

- [ ] **Step 6: Create tests/scenarios/health.spec.ts**

`packages/kctl-zulip/e2e/tests/scenarios/health.spec.ts`:
```typescript
import { test, expect } from '../../fixtures/zulip-test';

test.describe('Zulip Health', () => {
  test('server settings endpoint returns 200', async ({ request, zulipURL }) => {
    test.skip(!zulipURL, 'ZULIP_URL not set');

    const response = await request.get(`${zulipURL}/api/v1/server_settings`);
    expect(response.status()).toBe(200);

    const body = await response.json();
    expect(body).toHaveProperty('zulip_version');
    expect(body.result).toBe('success');
  });
});
```

- [ ] **Step 7: Commit**

```bash
git add packages/kctl-zulip/e2e/
git commit -m "test(kctl-zulip): add Playwright E2E skeleton with health scenario"
```

---

## Task 13: README + Docs + CLAUDE.md Update

**Files:**
- Create: `packages/kctl-zulip/README.md`
- Create: `packages/kctl-zulip/docs/completions.md`
- Modify: `CLAUDE.md` (root)

- [ ] **Step 1: Create README.md**

`packages/kctl-zulip/README.md` — ~200 lines covering:
1. Title + description
2. Installation (`uv tool install` from workspace)
3. Quick Start (5 essential commands: config init, health, users list, streams list, messages send)
4. Command Groups table (22 rows with group name, description, example)
5. Global Options table
6. Configuration section (profiles, multi-instance, env vars)
7. Shell Completions (link to docs/completions.md)
8. Development section (testing, linting, type checking commands)

- [ ] **Step 2: Create docs/completions.md**

`packages/kctl-zulip/docs/completions.md`:
```markdown
# Shell Completions

## Install

```bash
kctl-zulip completions zsh --install
kctl-zulip completions bash --install
kctl-zulip completions fish --install
```

## Manual

```bash
# Generate and pipe to file
kctl-zulip completions zsh > ~/.zfunc/_kctl-zulip

# Reload shell
exec $SHELL
```
```

- [ ] **Step 3: Update CLAUDE.md**

Add kctl-zulip to the workspace members table in the root `CLAUDE.md`:
- Under "Developer & SaaS Tools" section, add: `- **kctl-zulip** — Zulip team chat administration (8 groups)`
- Update count from 21 to 22
- Add to Key Paths table: `| packages/kctl-zulip/ | Zulip team chat CLI |`

- [ ] **Step 4: Commit**

```bash
git add packages/kctl-zulip/README.md packages/kctl-zulip/docs/ CLAUDE.md
git commit -m "docs(kctl-zulip): add README, completions guide, update CLAUDE.md"
```

---

## Task 14: Lint + Type Check + Final Verification

**Files:** None created — verification only.

- [ ] **Step 1: Run ruff lint**

Run: `cd /home/tgunawan/project/00-new-projects/kodemeio-workspace/kodemeio-platform && uv run ruff check packages/kctl-zulip/src/ --fix`
Expected: No errors (or auto-fixed)

- [ ] **Step 2: Run full test suite**

Run: `cd /home/tgunawan/project/00-new-projects/kodemeio-workspace/kodemeio-platform && uv run pytest packages/kctl-zulip/tests/ -v --tb=short`
Expected: All 60+ tests pass

- [ ] **Step 3: Verify CLI help output**

Run: `cd /home/tgunawan/project/00-new-projects/kodemeio-workspace/kodemeio-platform && uv run python -m kctl_zulip --help`
Expected: All 22 command groups shown, organized by panels

- [ ] **Step 4: Verify standard commands exist**

Run:
```bash
uv run python -m kctl_zulip doctor --help
uv run python -m kctl_zulip self-update --help
uv run python -m kctl_zulip completions --help
```
Expected: Each shows help text

- [ ] **Step 5: Commit any lint fixes**

```bash
git add packages/kctl-zulip/
git commit -m "chore(kctl-zulip): fix lint issues from ruff check"
```

- [ ] **Step 6: Final summary commit if needed**

If no additional changes, skip this step.
