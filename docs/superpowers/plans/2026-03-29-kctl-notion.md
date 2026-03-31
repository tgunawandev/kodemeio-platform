# kctl-notion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build kctl-notion CLI with 7 command groups for wiki search, page management, and database querying.

**Architecture:** Python CLI using kctl-lib v0.4.0. NotionClient subclasses APIClient with Notion-Version header. Smallest of the 5 CLIs.

**Tech Stack:** Python 3.12+, kctl-lib>=0.4.0, Typer, httpx, Rich

**Spec:** `docs/superpowers/specs/2026-03-29-kctl-service-clis-design.md` (Section 6)

**Working directory:** `/home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-notion`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `cli/src/kctl_notion/core/config.py` | ServiceConfig with `token` field, remove placeholder `url` |
| Modify | `cli/src/kctl_notion/core/exceptions.py` | Add APIError, AuthenticationError, ConnectionError re-exports |
| Create | `cli/src/kctl_notion/core/client.py` | NotionClient(APIClient) with Notion-Version header |
| Modify | `cli/src/kctl_notion/core/__init__.py` | Re-export client |
| Modify | `cli/src/kctl_notion/core/callbacks.py` | Add `get_client()` helper method |
| Create | `cli/src/kctl_notion/commands/health.py` | `health` command |
| Create | `cli/src/kctl_notion/commands/search.py` | `search` command (POST /v1/search) |
| Create | `cli/src/kctl_notion/commands/pages.py` | `pages` subcommands: list, show, create, update |
| Create | `cli/src/kctl_notion/commands/databases.py` | `databases` subcommands: list, show, query, export |
| Create | `cli/src/kctl_notion/commands/blocks.py` | `blocks` subcommands: list, append |
| Create | `cli/src/kctl_notion/commands/users.py` | `users` subcommands: list, me |
| Modify | `cli/src/kctl_notion/commands/config_cmd.py` | Update prompts and validation for `token` |
| Modify | `cli/src/kctl_notion/cli.py` | Register all new command groups |
| Modify | `cli/pyproject.toml` | Add pytest-httpx dev dependency |
| Create | `cli/tests/conftest.py` | Shared fixtures (mock client, mock output) |
| Create | `cli/tests/test_client.py` | NotionClient unit tests |
| Create | `cli/tests/test_health.py` | Health command tests |
| Create | `cli/tests/test_search.py` | Search command tests |
| Create | `cli/tests/test_pages.py` | Pages command tests |
| Create | `cli/tests/test_databases.py` | Databases command tests |
| Create | `cli/tests/test_blocks.py` | Blocks command tests |
| Create | `cli/tests/test_users.py` | Users command tests |
| Modify | `cli/tests/test_smoke.py` | Add smoke tests for all new commands |
| Modify | `CLAUDE.md` | Update with complete CLI documentation |

---

### Task 1: Setup -- Replace scaffold core/ with NotionClient, config, exceptions

**Files:**
- Modify: `cli/pyproject.toml`
- Modify: `cli/src/kctl_notion/core/config.py`
- Modify: `cli/src/kctl_notion/core/exceptions.py`
- Create: `cli/src/kctl_notion/core/client.py`
- Modify: `cli/src/kctl_notion/core/__init__.py`
- Modify: `cli/src/kctl_notion/core/callbacks.py`
- Modify: `cli/src/kctl_notion/commands/config_cmd.py`

- [ ] **Step 1: Update pyproject.toml -- add pytest-httpx to dev deps**

In `cli/pyproject.toml`, update the `[project.optional-dependencies]` section:

```toml
[project]
name = "kctl-notion"
version = "0.1.0"
description = "Notion workspace management"
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
```

Key change: `kctl-lib>=0.4.0` (was 0.3.0), added `pytest-httpx>=0.35.0`.

- [ ] **Step 2: Update ServiceConfig in config.py**

Replace the entire `cli/src/kctl_notion/core/config.py` with:

```python
"""Config management for kctl-notion."""

from __future__ import annotations

from kctl_lib.config import (
    get_all_services_in_profile,
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
    "ServiceConfig",
    "get_all_services_in_profile",
    "get_profile_names",
    "get_service_config",
    "remove_profile",
    "resolve_active_profile_name",
    "set_default_profile",
    "set_service_config",
]

SERVICE_KEY = "notion"
ENV_PREFIX = "KCTL_NOTION"


class ServiceConfig(BaseModel):
    """Notion service config within a profile."""

    token: str = ""  # Internal integration token


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get the 'notion' service config from a profile."""
    data = _get_service_config(profile_name, SERVICE_KEY, list(ServiceConfig.model_fields.keys()))
    return ServiceConfig(**data) if data else ServiceConfig()


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Set the 'notion' service config within a profile."""
    cleaned = {k: v for k, v in svc_config.model_dump().items() if v}
    _set_service_config(profile_name, SERVICE_KEY, cleaned)


def resolve_active_profile_name(profile_name: str | None = None) -> str:
    """Resolve active profile: explicit > env > default."""
    return _resolve_active_profile_name(profile_name, ENV_PREFIX)
```

- [ ] **Step 3: Update exceptions.py to add API-related exceptions**

Replace `cli/src/kctl_notion/core/exceptions.py` with:

```python
"""Exception hierarchy -- re-exported from kctl-lib."""

from kctl_lib.exceptions import (
    APIError,
    AuthenticationError,
    CommandError,
    ConfigError,
    KctlError,
    NotFoundError,
)
from kctl_lib.exceptions import ConnectionError as KctlConnectionError

__all__ = [
    "APIError",
    "AuthenticationError",
    "CommandError",
    "ConfigError",
    "KctlConnectionError",
    "KctlError",
    "NotFoundError",
]
```

- [ ] **Step 4: Create NotionClient in core/client.py**

Create `cli/src/kctl_notion/core/client.py`:

```python
"""Notion API client using kctl-lib APIClient base.

Notion API v1: REST endpoints with Bearer token auth.
Requires Notion-Version header on all requests.
Search and database queries use POST (not GET).
"""

from __future__ import annotations

from typing import Any

from kctl_lib.api_client import APIClient


class NotionClient(APIClient):
    """Synchronous client for Notion REST API v1."""

    BASE_URL = "https://api.notion.com/v1"
    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"

    NOTION_VERSION = "2022-06-28"

    def _build_auth_header(self) -> dict[str, str]:
        """Add Notion-Version header alongside auth."""
        headers = super()._build_auth_header()
        headers["Notion-Version"] = self.NOTION_VERSION
        return headers

    # ------------------------------------------------------------------
    # Notion-specific convenience methods
    # ------------------------------------------------------------------

    def search(
        self,
        query: str = "",
        filter_type: str | None = None,
        start_cursor: str | None = None,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """Search workspace. POST /search."""
        payload: dict[str, Any] = {}
        if query:
            payload["query"] = query
        if filter_type:
            payload["filter"] = {"value": filter_type, "property": "object"}
        if start_cursor:
            payload["start_cursor"] = start_cursor
        if page_size != 100:
            payload["page_size"] = page_size
        return self.post("/search", json=payload)

    def get_page(self, page_id: str) -> dict[str, Any]:
        """Get a page by ID. GET /pages/{id}."""
        return self.get(f"/pages/{page_id}")

    def create_page(self, parent_id: str, title: str, parent_type: str = "page_id") -> dict[str, Any]:
        """Create a new page. POST /pages."""
        parent: dict[str, str] = {parent_type: parent_id}
        payload: dict[str, Any] = {
            "parent": parent,
            "properties": {
                "title": {
                    "title": [{"text": {"content": title}}],
                },
            },
        }
        return self.post("/pages", json=payload)

    def update_page(self, page_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        """Update page properties. PATCH /pages/{id}."""
        return self.patch(f"/pages/{page_id}", json={"properties": properties})

    def get_database(self, database_id: str) -> dict[str, Any]:
        """Get database schema. GET /databases/{id}."""
        return self.get(f"/databases/{database_id}")

    def query_database(
        self,
        database_id: str,
        filter_obj: dict[str, Any] | None = None,
        sorts: list[dict[str, Any]] | None = None,
        start_cursor: str | None = None,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """Query database rows. POST /databases/{id}/query."""
        payload: dict[str, Any] = {}
        if filter_obj:
            payload["filter"] = filter_obj
        if sorts:
            payload["sorts"] = sorts
        if start_cursor:
            payload["start_cursor"] = start_cursor
        if page_size != 100:
            payload["page_size"] = page_size
        return self.post(f"/databases/{database_id}/query", json=payload)

    def query_database_all(
        self,
        database_id: str,
        filter_obj: dict[str, Any] | None = None,
        sorts: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Query all rows from a database, handling pagination."""
        all_results: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            result = self.query_database(
                database_id, filter_obj=filter_obj, sorts=sorts, start_cursor=cursor
            )
            all_results.extend(result.get("results", []))
            if not result.get("has_more"):
                break
            cursor = result.get("next_cursor")
            if not cursor:
                break
        return all_results

    def get_block_children(self, block_id: str, start_cursor: str | None = None) -> dict[str, Any]:
        """List child blocks of a page/block. GET /blocks/{id}/children."""
        params: dict[str, Any] = {}
        if start_cursor:
            params["start_cursor"] = start_cursor
        return self.get(f"/blocks/{block_id}/children", params=params)

    def append_block_children(self, block_id: str, children: list[dict[str, Any]]) -> dict[str, Any]:
        """Append child blocks to a page/block. PATCH /blocks/{id}/children."""
        return self.patch(f"/blocks/{block_id}/children", json={"children": children})

    def list_users(self, start_cursor: str | None = None) -> dict[str, Any]:
        """List workspace users. GET /users."""
        params: dict[str, Any] = {}
        if start_cursor:
            params["start_cursor"] = start_cursor
        return self.get("/users", params=params)

    def get_me(self) -> dict[str, Any]:
        """Get the current bot user. GET /users/me."""
        return self.get("/users/me")
```

- [ ] **Step 5: Update core/__init__.py to re-export client**

Replace `cli/src/kctl_notion/core/__init__.py` with:

```python
"""Core modules for kctl-notion."""

from kctl_notion.core.client import NotionClient
from kctl_notion.core.config import ServiceConfig

__all__ = ["NotionClient", "ServiceConfig"]
```

- [ ] **Step 6: Update callbacks.py with get_client helper**

Replace `cli/src/kctl_notion/core/callbacks.py` with:

```python
"""Application context for kctl-notion."""

from __future__ import annotations

from dataclasses import dataclass

from kctl_lib.callbacks import AppContextBase

from kctl_notion.core.client import NotionClient
from kctl_notion.core.config import (
    ServiceConfig,
    get_service_config,
    resolve_active_profile_name,
)


@dataclass
class AppContext(AppContextBase):
    """kctl-notion application context."""

    _client: NotionClient | None = None

    def get_client(self) -> NotionClient:
        """Get or create a NotionClient from the active profile."""
        if self._client is None:
            profile = resolve_active_profile_name(self.profile)
            svc: ServiceConfig = get_service_config(profile)
            self._client = NotionClient(credential=svc.token)
        return self._client

    def close(self) -> None:
        """Close the client if open."""
        if self._client is not None:
            self._client.close()
            self._client = None
```

- [ ] **Step 7: Update config_cmd.py for token-based config**

Replace `cli/src/kctl_notion/commands/config_cmd.py` with:

```python
"""Config profile management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_notion.core.callbacks import AppContext
from kctl_notion.core.config import (
    ServiceConfig,
    get_all_services_in_profile,
    get_profile_names,
    get_service_config,
    remove_profile,
    resolve_active_profile_name,
    set_default_profile,
    set_service_config,
)

app = typer.Typer(help="Profile and configuration management.")


@app.command()
def init(ctx: typer.Context) -> None:
    """Interactive config setup."""
    actx: AppContext = ctx.obj
    out = actx.output
    profile_name = typer.prompt("Profile name", default="default")
    token = typer.prompt("Notion integration token", default="", hide_input=True)
    svc = ServiceConfig(token=token)
    set_service_config(profile_name, svc)
    set_default_profile(profile_name)
    out.success(f"Config saved to profile '{profile_name}'")


@app.command()
def add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name")],
) -> None:
    """Add a new config profile."""
    actx: AppContext = ctx.obj
    out = actx.output
    token = typer.prompt("Notion integration token", default="", hide_input=True)
    svc = ServiceConfig(token=token)
    set_service_config(name, svc)
    out.success(f"Profile '{name}' added")


@app.command()
def use(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to activate")],
) -> None:
    """Switch active config profile."""
    actx: AppContext = ctx.obj
    out = actx.output
    available = get_profile_names()
    if name not in available:
        out.error(f"Profile '{name}' not found. Available: {', '.join(available)}")
        raise typer.Exit(1)
    set_default_profile(name)
    out.success(f"Switched to profile '{name}'")


@app.command()
def show(ctx: typer.Context) -> None:
    """Show current configuration."""
    actx: AppContext = ctx.obj
    out = actx.output
    active = resolve_active_profile_name(actx.profile)
    profiles = get_profile_names()
    if out.json_mode:
        out.raw_json({"active_profile": active, "profiles": {n: get_all_services_in_profile(n) for n in profiles}})
        return
    out.header("Configuration")
    out.kv("Active profile", active)
    for name in profiles:
        marker = " (active)" if name == active else ""
        out.header(f"Profile: {name}{marker}")
        services = get_all_services_in_profile(name)
        for svc_name, svc_data in services.items():
            out.text(f"  [bold]{svc_name}:[/bold]")
            if isinstance(svc_data, dict):
                for k, v in svc_data.items():
                    display_v = "***" if k == "token" and v else str(v)
                    out.kv(f"    {k}", display_v)


@app.command()
def validate(ctx: typer.Context) -> None:
    """Validate current config completeness."""
    actx: AppContext = ctx.obj
    out = actx.output
    active = resolve_active_profile_name(actx.profile)
    svc = get_service_config(active)
    issues: list[str] = []
    if not svc.token:
        issues.append("token is not set")
    if out.json_mode:
        out.raw_json({"profile": active, "valid": len(issues) == 0, "issues": issues})
        return
    if issues:
        out.error(f"Profile '{active}' has {len(issues)} issue(s):")
        for issue in issues:
            out.text(f"  - {issue}")
        raise typer.Exit(1)
    out.success(f"Profile '{active}' is valid")


@app.command()
def remove(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to remove")],
) -> None:
    """Remove a config profile."""
    actx: AppContext = ctx.obj
    out = actx.output
    available = get_profile_names()
    if name not in available:
        out.error(f"Profile '{name}' not found")
        raise typer.Exit(1)
    remove_profile(name)
    out.success(f"Profile '{name}' removed")


@app.command("set")
def set_(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Config key")],
    value: Annotated[str, typer.Argument(help="Config value")],
) -> None:
    """Set a single config value."""
    actx: AppContext = ctx.obj
    out = actx.output
    active = resolve_active_profile_name(actx.profile)
    svc = get_service_config(active)
    if key not in ServiceConfig.model_fields:
        out.error(f"Unknown key '{key}'. Valid: {', '.join(ServiceConfig.model_fields)}")
        raise typer.Exit(1)
    data = svc.model_dump()
    data[key] = value
    set_service_config(active, ServiceConfig(**data))
    out.success(f"Set {key} in profile '{active}'")


@app.command()
def profiles(ctx: typer.Context) -> None:
    """List all config profiles."""
    actx: AppContext = ctx.obj
    out = actx.output
    active = resolve_active_profile_name(actx.profile)
    names = get_profile_names()
    if out.json_mode:
        out.raw_json({"profiles": names, "active": active})
        return
    rows = [[name, "active" if name == active else ""] for name in names]
    out.table("Profiles", [("Name", "cyan"), ("Status", "green")], rows)


@app.command()
def current(ctx: typer.Context) -> None:
    """Show active profile and resolved context."""
    actx: AppContext = ctx.obj
    out = actx.output
    active = resolve_active_profile_name(actx.profile)
    svc = get_service_config(active)
    if out.json_mode:
        safe = svc.model_dump()
        if safe.get("token"):
            safe["token"] = "***"
        out.raw_json({"profile": active, **safe})
        return
    fields = [(k, "***" if k == "token" and v else str(v) or "(not set)") for k, v in svc.model_dump().items()]
    sections = [("Active Profile", [("Name", active)] + fields)]
    out.detail("Current Config", sections)
```

- [ ] **Step 8: Sync dependencies and run existing smoke tests**

```bash
cd cli && uv sync --all-extras && uv run pytest tests/test_smoke.py -v --tb=short
```

Expected: 2 smoke tests pass. Dependencies install successfully.

- [ ] **Step 9: Commit**

```bash
git add cli/pyproject.toml cli/src/kctl_notion/core/ cli/src/kctl_notion/commands/config_cmd.py
git commit -m "feat: add NotionClient, update config for token-based auth

- NotionClient(APIClient) with Notion-Version header
- ServiceConfig.token replaces placeholder url field
- Re-export APIError, AuthenticationError in exceptions
- AppContext.get_client() creates client from profile
- Config commands updated for token prompts

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: health + search commands

**Files:**
- Create: `cli/src/kctl_notion/commands/health.py`
- Create: `cli/src/kctl_notion/commands/search.py`
- Modify: `cli/src/kctl_notion/cli.py`

- [ ] **Step 1: Create health command**

Create `cli/src/kctl_notion/commands/health.py`:

```python
"""Health check command -- verify Notion API connectivity."""

from __future__ import annotations

import typer

from kctl_notion.core.callbacks import AppContext

app = typer.Typer(help="API health check.")


@app.callback(invoke_without_command=True)
def health(ctx: typer.Context) -> None:
    """Check Notion API reachability and accessible pages count."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        me = client.get_me()
        # Search with empty query to count accessible pages
        search_result = client.search(page_size=1)
        total_hint = len(search_result.get("results", []))
        has_more = search_result.get("has_more", False)

        bot_name = me.get("name", "Unknown")
        bot_type = me.get("type", "unknown")
        workspace = me.get("bot", {}).get("workspace_name", "Unknown") if me.get("bot") else "N/A"

        if out.json_mode:
            out.raw_json({
                "status": "healthy",
                "bot_name": bot_name,
                "bot_type": bot_type,
                "workspace": workspace,
                "has_accessible_content": total_hint > 0 or has_more,
            })
            return

        out.success("Notion API is reachable")
        out.kv("Bot name", bot_name)
        out.kv("Type", bot_type)
        out.kv("Workspace", workspace)
        out.kv("Accessible content", "Yes" if (total_hint > 0 or has_more) else "None found")
    finally:
        actx.close()
```

- [ ] **Step 2: Create search command**

Create `cli/src/kctl_notion/commands/search.py`:

```python
"""Search command -- global workspace search via POST /search."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_notion.core.callbacks import AppContext

app = typer.Typer(help="Search workspace.")


def _extract_title(obj: dict) -> str:
    """Extract a readable title from a Notion object."""
    props = obj.get("properties", {})
    # Try common title property patterns
    for key in ("title", "Title", "Name", "name"):
        prop = props.get(key)
        if prop and isinstance(prop, dict):
            title_parts = prop.get("title", [])
            if isinstance(title_parts, list) and title_parts:
                return "".join(t.get("plain_text", "") for t in title_parts)
    # Fallback: check all properties for title type
    for prop in props.values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            title_parts = prop.get("title", [])
            if isinstance(title_parts, list) and title_parts:
                return "".join(t.get("plain_text", "") for t in title_parts)
    return "(untitled)"


@app.callback(invoke_without_command=True)
def search(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Search query text")],
    type: Annotated[str | None, typer.Option("--type", "-t", help="Filter: page or database")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 20,
) -> None:
    """Search across the Notion workspace."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        result = client.search(query=query, filter_type=type, page_size=limit)
        items = result.get("results", [])

        if out.json_mode:
            out.raw_json({"results": items, "count": len(items), "has_more": result.get("has_more", False)})
            return

        if not items:
            out.warn("No results found")
            return

        rows: list[list[str]] = []
        for item in items:
            obj_type = item.get("object", "unknown")
            obj_id = item.get("id", "")[:8]
            title = _extract_title(item)
            last_edited = item.get("last_edited_time", "")[:10]
            rows.append([obj_id, obj_type, title[:60], last_edited])

        out.table(
            f"Search results for '{query}' ({len(items)} found)",
            [("ID", "cyan"), ("Type", "green"), ("Title", "white"), ("Edited", "yellow")],
            rows,
        )
    finally:
        actx.close()
```

- [ ] **Step 3: Register health and search in cli.py**

Replace `cli/src/kctl_notion/cli.py` with:

```python
"""Main CLI entry point for kctl-notion."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_notion import __version__
from kctl_notion.commands.config_cmd import app as config_app
from kctl_notion.commands.health import app as health_app
from kctl_notion.commands.search import app as search_app
from kctl_notion.core.callbacks import AppContext
from kctl_notion.core.plugins import discover_and_load_plugins


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-notion {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-notion",
    help="Notion workspace management",
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
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Notion workspace management."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        format=format,
        no_header=no_header,
    )


app.add_typer(config_app, name="config")
app.add_typer(health_app, name="health")
app.add_typer(search_app, name="search")

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

Note: This file will be updated again in later tasks to register pages, databases, blocks, and users commands. The final version is shown in Task 5.

- [ ] **Step 4: Run smoke tests**

```bash
cd cli && uv run pytest tests/test_smoke.py -v --tb=short
```

Expected: 2 smoke tests pass.

- [ ] **Step 5: Commit**

```bash
git add cli/src/kctl_notion/commands/health.py cli/src/kctl_notion/commands/search.py cli/src/kctl_notion/cli.py
git commit -m "feat: add health and search commands

- health: GET /users/me + POST /search to verify connectivity
- search: POST /search with --type and --limit filters
- Both registered in main CLI app

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: pages command group

**Files:**
- Create: `cli/src/kctl_notion/commands/pages.py`

- [ ] **Step 1: Create pages command group**

Create `cli/src/kctl_notion/commands/pages.py`:

```python
"""Pages command group -- page management."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from kctl_notion.core.callbacks import AppContext

app = typer.Typer(help="Page management.")


def _extract_title(obj: dict[str, Any]) -> str:
    """Extract a readable title from a Notion page object."""
    props = obj.get("properties", {})
    for prop in props.values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            title_parts = prop.get("title", [])
            if isinstance(title_parts, list) and title_parts:
                return "".join(t.get("plain_text", "") for t in title_parts)
    return "(untitled)"


def _extract_parent_info(obj: dict[str, Any]) -> str:
    """Extract parent type and ID from a Notion page."""
    parent = obj.get("parent", {})
    parent_type = parent.get("type", "unknown")
    if parent_type == "database_id":
        return f"db:{parent.get('database_id', '')[:8]}"
    if parent_type == "page_id":
        return f"page:{parent.get('page_id', '')[:8]}"
    if parent_type == "workspace":
        return "workspace"
    return parent_type


@app.command("list")
def list_(
    ctx: typer.Context,
    parent: Annotated[str | None, typer.Option("--parent", help="Parent page/database ID")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 20,
) -> None:
    """List pages (recently edited). Uses search with page filter."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        if parent:
            # Query parent as database to list child pages
            result = client.query_database(parent, page_size=limit)
            pages = result.get("results", [])
        else:
            # Search for all pages
            result = client.search(filter_type="page", page_size=limit)
            pages = result.get("results", [])

        if out.json_mode:
            out.raw_json({"pages": pages, "count": len(pages)})
            return

        if not pages:
            out.warn("No pages found")
            return

        rows: list[list[str]] = []
        for page in pages:
            page_id = page.get("id", "")[:8]
            title = _extract_title(page)
            parent_info = _extract_parent_info(page)
            last_edited = page.get("last_edited_time", "")[:10]
            rows.append([page_id, title[:50], parent_info, last_edited])

        out.table(
            f"Pages ({len(pages)})",
            [("ID", "cyan"), ("Title", "white"), ("Parent", "green"), ("Edited", "yellow")],
            rows,
        )
    finally:
        actx.close()


@app.command()
def show(
    ctx: typer.Context,
    page_id: Annotated[str, typer.Argument(help="Page ID")],
) -> None:
    """Show page title, properties, and content preview."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        page = client.get_page(page_id)

        if out.json_mode:
            out.raw_json(page)
            return

        title = _extract_title(page)
        parent_info = _extract_parent_info(page)
        created = page.get("created_time", "")[:10]
        edited = page.get("last_edited_time", "")[:10]
        archived = page.get("archived", False)
        url = page.get("url", "")

        sections: list[tuple[str, list[tuple[str, str]]]] = [
            (
                "Page Info",
                [
                    ("ID", page.get("id", "")),
                    ("Title", title),
                    ("Parent", parent_info),
                    ("Created", created),
                    ("Last edited", edited),
                    ("Archived", str(archived)),
                    ("URL", url),
                ],
            ),
        ]

        # Show properties
        props = page.get("properties", {})
        if props:
            prop_fields: list[tuple[str, str]] = []
            for name, prop in props.items():
                prop_type = prop.get("type", "unknown")
                prop_fields.append((name, prop_type))
            sections.append(("Properties", prop_fields))

        # Fetch first few blocks for content preview
        try:
            blocks_result = client.get_block_children(page_id)
            blocks = blocks_result.get("results", [])[:5]
            if blocks:
                content_fields: list[tuple[str, str]] = []
                for i, block in enumerate(blocks):
                    block_type = block.get("type", "unknown")
                    text = _extract_block_text(block)
                    content_fields.append((f"Block {i + 1} ({block_type})", text[:80]))
                sections.append(("Content Preview", content_fields))
        except Exception:  # noqa: BLE001
            pass

        out.detail(f"Page: {title}", sections)
    finally:
        actx.close()


@app.command()
def create(
    ctx: typer.Context,
    parent: Annotated[str, typer.Option("--parent", help="Parent page or database ID")],
    title: Annotated[str, typer.Option("--title", help="Page title")],
    database: Annotated[bool, typer.Option("--database", help="Parent is a database (not a page)")] = False,
) -> None:
    """Create a new page under a parent page or database."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        parent_type = "database_id" if database else "page_id"
        result = client.create_page(parent, title, parent_type=parent_type)

        if out.json_mode:
            out.raw_json(result)
            return

        new_id = result.get("id", "")
        url = result.get("url", "")
        out.success(f"Page created: {new_id}")
        if url:
            out.kv("URL", url)
    finally:
        actx.close()


@app.command()
def update(
    ctx: typer.Context,
    page_id: Annotated[str, typer.Argument(help="Page ID")],
    title: Annotated[str | None, typer.Option("--title", help="New page title")] = None,
    archived: Annotated[bool | None, typer.Option("--archived/--no-archived", help="Archive or unarchive")] = None,
) -> None:
    """Update page properties (title, archived status)."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        payload: dict[str, Any] = {}
        if title is not None:
            payload["title"] = {"title": [{"text": {"content": title}}]}

        update_body: dict[str, Any] = {}
        if payload:
            update_body["properties"] = payload
        if archived is not None:
            update_body["archived"] = archived

        if not update_body:
            out.error("No changes specified. Use --title or --archived/--no-archived")
            raise typer.Exit(1)

        # Build the PATCH request manually for flexibility
        result = client.patch(f"/pages/{page_id}", json=update_body)

        if out.json_mode:
            out.raw_json(result)
            return

        out.success(f"Page {page_id[:8]} updated")
    finally:
        actx.close()


def _extract_block_text(block: dict[str, Any]) -> str:
    """Extract plain text from a block."""
    block_type = block.get("type", "")
    type_data = block.get(block_type, {})
    rich_text = type_data.get("rich_text", [])
    if isinstance(rich_text, list):
        return "".join(t.get("plain_text", "") for t in rich_text)
    return ""
```

- [ ] **Step 2: Register pages in cli.py**

Add to `cli/src/kctl_notion/cli.py` after the search import:

```python
from kctl_notion.commands.pages import app as pages_app
```

And after the search registration:

```python
app.add_typer(pages_app, name="pages")
```

- [ ] **Step 3: Smoke test**

```bash
cd cli && uv run pytest tests/test_smoke.py -v --tb=short
```

- [ ] **Step 4: Commit**

```bash
git add cli/src/kctl_notion/commands/pages.py cli/src/kctl_notion/cli.py
git commit -m "feat: add pages command group (list/show/create/update)

- pages list: search with page filter or query parent database
- pages show: page details with properties and content preview
- pages create: new page under parent page or database
- pages update: change title and archived status

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: databases command group

**Files:**
- Create: `cli/src/kctl_notion/commands/databases.py`

- [ ] **Step 1: Create databases command group**

Create `cli/src/kctl_notion/commands/databases.py`:

```python
"""Databases command group -- database management and querying."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Annotated, Any

import typer

from kctl_notion.core.callbacks import AppContext

app = typer.Typer(help="Database management.")


def _extract_db_title(db: dict[str, Any]) -> str:
    """Extract database title."""
    title_parts = db.get("title", [])
    if isinstance(title_parts, list) and title_parts:
        return "".join(t.get("plain_text", "") for t in title_parts)
    return "(untitled)"


def _extract_row_values(row: dict[str, Any], prop_names: list[str]) -> list[str]:
    """Extract property values from a database row for tabular display."""
    values: list[str] = []
    props = row.get("properties", {})
    for name in prop_names:
        prop = props.get(name, {})
        values.append(_format_property_value(prop))
    return values


def _format_property_value(prop: dict[str, Any]) -> str:
    """Format a single Notion property value to a string."""
    prop_type = prop.get("type", "")

    if prop_type == "title":
        parts = prop.get("title", [])
        return "".join(t.get("plain_text", "") for t in parts) if parts else ""

    if prop_type == "rich_text":
        parts = prop.get("rich_text", [])
        return "".join(t.get("plain_text", "") for t in parts) if parts else ""

    if prop_type == "number":
        val = prop.get("number")
        return str(val) if val is not None else ""

    if prop_type == "select":
        sel = prop.get("select")
        return sel.get("name", "") if sel else ""

    if prop_type == "multi_select":
        items = prop.get("multi_select", [])
        return ", ".join(s.get("name", "") for s in items)

    if prop_type == "date":
        date_obj = prop.get("date")
        if date_obj:
            start = date_obj.get("start", "")
            end = date_obj.get("end")
            return f"{start} - {end}" if end else start
        return ""

    if prop_type == "checkbox":
        return str(prop.get("checkbox", False))

    if prop_type == "url":
        return prop.get("url", "") or ""

    if prop_type == "email":
        return prop.get("email", "") or ""

    if prop_type == "phone_number":
        return prop.get("phone_number", "") or ""

    if prop_type == "status":
        status = prop.get("status")
        return status.get("name", "") if status else ""

    if prop_type == "people":
        people = prop.get("people", [])
        return ", ".join(p.get("name", p.get("id", "")) for p in people)

    if prop_type == "relation":
        relations = prop.get("relation", [])
        return ", ".join(r.get("id", "")[:8] for r in relations)

    if prop_type == "formula":
        formula = prop.get("formula", {})
        f_type = formula.get("type", "")
        return str(formula.get(f_type, ""))

    return f"({prop_type})"


@app.command("list")
def list_(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 20,
) -> None:
    """List all databases accessible to the integration."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        result = client.search(filter_type="database", page_size=limit)
        databases = result.get("results", [])

        if out.json_mode:
            out.raw_json({"databases": databases, "count": len(databases)})
            return

        if not databases:
            out.warn("No databases found")
            return

        rows: list[list[str]] = []
        for db in databases:
            db_id = db.get("id", "")[:8]
            title = _extract_db_title(db)
            prop_count = len(db.get("properties", {}))
            last_edited = db.get("last_edited_time", "")[:10]
            rows.append([db_id, title[:50], str(prop_count), last_edited])

        out.table(
            f"Databases ({len(databases)})",
            [("ID", "cyan"), ("Title", "white"), ("Props", "green"), ("Edited", "yellow")],
            rows,
        )
    finally:
        actx.close()


@app.command()
def show(
    ctx: typer.Context,
    database_id: Annotated[str, typer.Argument(help="Database ID")],
) -> None:
    """Show database schema (properties and their types)."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        db = client.get_database(database_id)

        if out.json_mode:
            out.raw_json(db)
            return

        title = _extract_db_title(db)
        created = db.get("created_time", "")[:10]
        edited = db.get("last_edited_time", "")[:10]
        url = db.get("url", "")

        sections: list[tuple[str, list[tuple[str, str]]]] = [
            (
                "Database Info",
                [
                    ("ID", db.get("id", "")),
                    ("Title", title),
                    ("Created", created),
                    ("Last edited", edited),
                    ("URL", url),
                ],
            ),
        ]

        # Show schema (properties)
        props = db.get("properties", {})
        if props:
            schema_fields: list[tuple[str, str]] = []
            for name, prop_def in props.items():
                prop_type = prop_def.get("type", "unknown")
                schema_fields.append((name, prop_type))
            sections.append(("Schema", schema_fields))

        out.detail(f"Database: {title}", sections)
    finally:
        actx.close()


@app.command()
def query(
    ctx: typer.Context,
    database_id: Annotated[str, typer.Argument(help="Database ID")],
    filter: Annotated[str | None, typer.Option("--filter", help="Filter JSON object")] = None,
    sort: Annotated[str | None, typer.Option("--sort", help="Sort by property name")] = None,
    descending: Annotated[bool, typer.Option("--desc", help="Sort descending")] = False,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 50,
) -> None:
    """Query database rows with optional filter and sort."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        filter_obj = json.loads(filter) if filter else None
        sorts: list[dict[str, Any]] | None = None
        if sort:
            sorts = [{"property": sort, "direction": "descending" if descending else "ascending"}]

        result = client.query_database(
            database_id, filter_obj=filter_obj, sorts=sorts, page_size=limit
        )
        rows_data = result.get("results", [])

        if out.json_mode:
            out.raw_json({
                "results": rows_data,
                "count": len(rows_data),
                "has_more": result.get("has_more", False),
            })
            return

        if not rows_data:
            out.warn("No rows found")
            return

        # Discover property names from first row
        first_props = rows_data[0].get("properties", {})
        prop_names = list(first_props.keys())[:6]  # Limit columns for readability

        rows: list[list[str]] = []
        for row in rows_data:
            row_id = row.get("id", "")[:8]
            row_values = _extract_row_values(row, prop_names)
            rows.append([row_id, *[v[:30] for v in row_values]])

        columns: list[tuple[str, str]] = [("ID", "cyan")]
        for name in prop_names:
            columns.append((name[:20], "white"))

        out.table(f"Query results ({len(rows_data)} rows)", columns, rows)
    finally:
        actx.close()


@app.command()
def export(
    ctx: typer.Context,
    database_id: Annotated[str, typer.Argument(help="Database ID")],
    format: Annotated[str, typer.Option("--format", "-f", help="Export format: csv or json")] = "csv",
    output: Annotated[str | None, typer.Option("--output", "-o", help="Output file path")] = None,
) -> None:
    """Export database to CSV or JSON file."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        # Fetch all rows
        all_rows = client.query_database_all(database_id)

        if not all_rows:
            out.warn("Database is empty, nothing to export")
            return

        # Get property names from schema
        db = client.get_database(database_id)
        db_title = _extract_db_title(db)
        prop_names = list(db.get("properties", {}).keys())

        if format == "json":
            export_data = []
            for row in all_rows:
                row_dict: dict[str, str] = {"id": row.get("id", "")}
                for name in prop_names:
                    prop = row.get("properties", {}).get(name, {})
                    row_dict[name] = _format_property_value(prop)
                export_data.append(row_dict)

            content = json.dumps(export_data, indent=2, ensure_ascii=False)
            default_ext = ".json"
        else:
            # CSV
            string_io = io.StringIO()
            writer = csv.writer(string_io)
            writer.writerow(["id", *prop_names])
            for row in all_rows:
                values = _extract_row_values(row, prop_names)
                writer.writerow([row.get("id", ""), *values])
            content = string_io.getvalue()
            default_ext = ".csv"

        if output:
            filepath = Path(output)
        else:
            safe_title = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in db_title)
            filepath = Path(f"{safe_title}{default_ext}")

        filepath.write_text(content, encoding="utf-8")
        out.success(f"Exported {len(all_rows)} rows to {filepath}")
    finally:
        actx.close()
```

- [ ] **Step 2: Register databases in cli.py**

Add to `cli/src/kctl_notion/cli.py`:

Import:
```python
from kctl_notion.commands.databases import app as databases_app
```

Registration:
```python
app.add_typer(databases_app, name="databases")
```

- [ ] **Step 3: Smoke test**

```bash
cd cli && uv run pytest tests/test_smoke.py -v --tb=short
```

- [ ] **Step 4: Commit**

```bash
git add cli/src/kctl_notion/commands/databases.py cli/src/kctl_notion/cli.py
git commit -m "feat: add databases command group (list/show/query/export)

- databases list: search with database filter
- databases show: schema with property names and types
- databases query: POST query with --filter JSON and --sort
- databases export: full pagination to CSV or JSON file

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: blocks + users command groups

**Files:**
- Create: `cli/src/kctl_notion/commands/blocks.py`
- Create: `cli/src/kctl_notion/commands/users.py`
- Modify: `cli/src/kctl_notion/cli.py` (final version)

- [ ] **Step 1: Create blocks command group**

Create `cli/src/kctl_notion/commands/blocks.py`:

```python
"""Blocks command group -- content block management."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from kctl_notion.core.callbacks import AppContext

app = typer.Typer(help="Content block management.")


def _extract_block_text(block: dict[str, Any]) -> str:
    """Extract plain text from a block's rich_text content."""
    block_type = block.get("type", "")
    type_data = block.get(block_type, {})
    rich_text = type_data.get("rich_text", [])
    if isinstance(rich_text, list):
        return "".join(t.get("plain_text", "") for t in rich_text)
    return ""


def _format_block_summary(block: dict[str, Any]) -> str:
    """Format a block into a one-line summary."""
    block_type = block.get("type", "")
    text = _extract_block_text(block)
    if text:
        return text[:80]
    if block_type in ("image", "file", "pdf"):
        type_data = block.get(block_type, {})
        file_data = type_data.get("file", type_data.get("external", {}))
        return file_data.get("url", "(media)")[:60] if file_data else "(media)"
    if block_type == "child_page":
        return block.get("child_page", {}).get("title", "(child page)")
    if block_type == "child_database":
        return block.get("child_database", {}).get("title", "(child database)")
    if block_type == "divider":
        return "---"
    if block_type == "table_of_contents":
        return "(table of contents)"
    return f"({block_type})"


@app.command("list")
def list_(
    ctx: typer.Context,
    page_id: Annotated[str, typer.Argument(help="Page or block ID to list children of")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max blocks to show")] = 50,
) -> None:
    """List blocks in a page."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        all_blocks: list[dict[str, Any]] = []
        cursor: str | None = None

        while len(all_blocks) < limit:
            result = client.get_block_children(page_id, start_cursor=cursor)
            blocks = result.get("results", [])
            all_blocks.extend(blocks)
            if not result.get("has_more"):
                break
            cursor = result.get("next_cursor")
            if not cursor:
                break

        all_blocks = all_blocks[:limit]

        if out.json_mode:
            out.raw_json({"blocks": all_blocks, "count": len(all_blocks)})
            return

        if not all_blocks:
            out.warn("No blocks found")
            return

        rows: list[list[str]] = []
        for i, block in enumerate(all_blocks):
            block_id = block.get("id", "")[:8]
            block_type = block.get("type", "unknown")
            has_children = "+" if block.get("has_children") else ""
            summary = _format_block_summary(block)
            rows.append([str(i + 1), block_id, block_type, has_children, summary[:60]])

        out.table(
            f"Blocks ({len(all_blocks)})",
            [("#", "dim"), ("ID", "cyan"), ("Type", "green"), ("Children", "yellow"), ("Content", "white")],
            rows,
        )
    finally:
        actx.close()


@app.command()
def append(
    ctx: typer.Context,
    page_id: Annotated[str, typer.Argument(help="Page ID to append to")],
    text: Annotated[str, typer.Option("--text", "-t", help="Paragraph text to add")],
    block_type: Annotated[str, typer.Option("--type", help="Block type: paragraph, heading_1, heading_2, heading_3, bulleted_list_item, numbered_list_item, to_do, quote, callout, divider")] = "paragraph",
) -> None:
    """Append a text block to a page."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        if block_type == "divider":
            children = [{"object": "block", "type": "divider", "divider": {}}]
        else:
            children = [
                {
                    "object": "block",
                    "type": block_type,
                    block_type: {
                        "rich_text": [{"type": "text", "text": {"content": text}}],
                    },
                }
            ]

        result = client.append_block_children(page_id, children)

        if out.json_mode:
            out.raw_json(result)
            return

        out.success(f"Appended {block_type} block to page {page_id[:8]}")
    finally:
        actx.close()
```

- [ ] **Step 2: Create users command group**

Create `cli/src/kctl_notion/commands/users.py`:

```python
"""Users command group -- workspace user management."""

from __future__ import annotations

from typing import Any

import typer

from kctl_notion.core.callbacks import AppContext

app = typer.Typer(help="Workspace user management.")


def _format_user_type(user: dict[str, Any]) -> str:
    """Format user type (person or bot)."""
    user_type = user.get("type", "unknown")
    if user_type == "bot":
        owner = user.get("bot", {}).get("owner", {})
        owner_type = owner.get("type", "")
        return f"bot ({owner_type})"
    return user_type


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List workspace members and bots."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        all_users: list[dict[str, Any]] = []
        cursor: str | None = None

        while True:
            result = client.list_users(start_cursor=cursor)
            users = result.get("results", [])
            all_users.extend(users)
            if not result.get("has_more"):
                break
            cursor = result.get("next_cursor")
            if not cursor:
                break

        if out.json_mode:
            out.raw_json({"users": all_users, "count": len(all_users)})
            return

        if not all_users:
            out.warn("No users found")
            return

        rows: list[list[str]] = []
        for user in all_users:
            user_id = user.get("id", "")[:8]
            name = user.get("name", "(unnamed)")
            user_type = _format_user_type(user)
            email = ""
            if user.get("type") == "person":
                email = user.get("person", {}).get("email", "")
            rows.append([user_id, name, user_type, email])

        out.table(
            f"Users ({len(all_users)})",
            [("ID", "cyan"), ("Name", "white"), ("Type", "green"), ("Email", "yellow")],
            rows,
        )
    finally:
        actx.close()


@app.command()
def me(ctx: typer.Context) -> None:
    """Show current bot/integration user."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        user = client.get_me()

        if out.json_mode:
            out.raw_json(user)
            return

        name = user.get("name", "Unknown")
        user_type = user.get("type", "unknown")
        user_id = user.get("id", "")
        bot_info = user.get("bot", {})
        workspace = bot_info.get("workspace_name", "N/A") if bot_info else "N/A"

        sections = [
            (
                "Bot Info",
                [
                    ("ID", user_id),
                    ("Name", name),
                    ("Type", user_type),
                    ("Workspace", workspace),
                ],
            ),
        ]
        out.detail("Current User", sections)
    finally:
        actx.close()
```

- [ ] **Step 3: Final cli.py with all command groups registered**

Replace `cli/src/kctl_notion/cli.py` with the final version:

```python
"""Main CLI entry point for kctl-notion."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_notion import __version__
from kctl_notion.commands.blocks import app as blocks_app
from kctl_notion.commands.config_cmd import app as config_app
from kctl_notion.commands.databases import app as databases_app
from kctl_notion.commands.health import app as health_app
from kctl_notion.commands.pages import app as pages_app
from kctl_notion.commands.search import app as search_app
from kctl_notion.commands.users import app as users_app
from kctl_notion.core.callbacks import AppContext
from kctl_notion.core.plugins import discover_and_load_plugins


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-notion {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-notion",
    help="Notion workspace management",
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
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Notion workspace management."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        format=format,
        no_header=no_header,
    )


# Register command groups
app.add_typer(config_app, name="config")
app.add_typer(health_app, name="health")
app.add_typer(search_app, name="search")
app.add_typer(pages_app, name="pages")
app.add_typer(databases_app, name="databases")
app.add_typer(blocks_app, name="blocks")
app.add_typer(users_app, name="users")

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

- [ ] **Step 4: Smoke test**

```bash
cd cli && uv run pytest tests/test_smoke.py -v --tb=short
```

- [ ] **Step 5: Commit**

```bash
git add cli/src/kctl_notion/commands/blocks.py cli/src/kctl_notion/commands/users.py cli/src/kctl_notion/cli.py
git commit -m "feat: add blocks and users command groups

- blocks list: paginated block children with content preview
- blocks append: add paragraph/heading/list/quote/divider blocks
- users list: workspace members and bots with email
- users me: current bot/integration details
- All 7 command groups now registered in cli.py

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: Tests + CI + CLAUDE.md

**Files:**
- Modify: `cli/tests/conftest.py`
- Create: `cli/tests/test_client.py`
- Create: `cli/tests/test_health.py`
- Create: `cli/tests/test_search.py`
- Create: `cli/tests/test_pages.py`
- Create: `cli/tests/test_databases.py`
- Create: `cli/tests/test_blocks.py`
- Create: `cli/tests/test_users.py`
- Modify: `cli/tests/test_smoke.py`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update conftest.py with shared fixtures**

Replace `cli/tests/conftest.py` with:

```python
"""Shared test configuration and fixtures."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kctl_notion.core.callbacks import AppContext
from kctl_notion.core.client import NotionClient


@pytest.fixture
def mock_client(httpx_mock):
    """Create a NotionClient pointing at the mock."""
    client = NotionClient(credential="ntn_test_token_123")
    yield client
    client.close()


@pytest.fixture
def mock_app_context(mock_client):
    """Create an AppContext with a mocked client."""
    ctx = AppContext(json_mode=False, quiet=False)
    ctx._client = mock_client
    return ctx


@pytest.fixture
def json_app_context(mock_client):
    """Create an AppContext with JSON output mode."""
    ctx = AppContext(json_mode=True, quiet=False)
    ctx._client = mock_client
    return ctx


@pytest.fixture
def mock_notion_me():
    """Standard /users/me response."""
    return {
        "object": "user",
        "id": "bot-user-id-1234",
        "type": "bot",
        "name": "Test Integration",
        "bot": {
            "owner": {"type": "workspace"},
            "workspace_name": "Test Workspace",
        },
    }


@pytest.fixture
def mock_search_results():
    """Standard search results."""
    return {
        "object": "list",
        "results": [
            {
                "object": "page",
                "id": "page-1234-5678",
                "created_time": "2026-01-15T10:00:00.000Z",
                "last_edited_time": "2026-03-20T14:30:00.000Z",
                "parent": {"type": "workspace", "workspace": True},
                "properties": {
                    "title": {
                        "id": "title",
                        "type": "title",
                        "title": [{"type": "text", "plain_text": "Meeting Notes"}],
                    }
                },
                "url": "https://www.notion.so/Meeting-Notes-page1234",
            },
        ],
        "has_more": False,
        "next_cursor": None,
    }


@pytest.fixture
def mock_database():
    """Standard database object."""
    return {
        "object": "database",
        "id": "db-1234-5678",
        "title": [{"type": "text", "plain_text": "Project Tracker"}],
        "created_time": "2026-01-01T00:00:00.000Z",
        "last_edited_time": "2026-03-25T12:00:00.000Z",
        "url": "https://www.notion.so/db1234",
        "properties": {
            "Name": {"id": "title", "type": "title", "title": {}},
            "Status": {"id": "status", "type": "select", "select": {"options": []}},
            "Priority": {"id": "priority", "type": "number", "number": {"format": "number"}},
        },
    }


@pytest.fixture
def mock_database_query_results():
    """Standard database query results."""
    return {
        "object": "list",
        "results": [
            {
                "object": "page",
                "id": "row-1234-5678",
                "properties": {
                    "Name": {"type": "title", "title": [{"plain_text": "Task Alpha"}]},
                    "Status": {"type": "select", "select": {"name": "In Progress"}},
                    "Priority": {"type": "number", "number": 1},
                },
            },
            {
                "object": "page",
                "id": "row-abcd-efgh",
                "properties": {
                    "Name": {"type": "title", "title": [{"plain_text": "Task Beta"}]},
                    "Status": {"type": "select", "select": {"name": "Done"}},
                    "Priority": {"type": "number", "number": 2},
                },
            },
        ],
        "has_more": False,
        "next_cursor": None,
    }


@pytest.fixture
def mock_blocks():
    """Standard block children response."""
    return {
        "object": "list",
        "results": [
            {
                "object": "block",
                "id": "block-1111",
                "type": "heading_1",
                "has_children": False,
                "heading_1": {
                    "rich_text": [{"type": "text", "plain_text": "Introduction"}],
                },
            },
            {
                "object": "block",
                "id": "block-2222",
                "type": "paragraph",
                "has_children": False,
                "paragraph": {
                    "rich_text": [{"type": "text", "plain_text": "This is a test paragraph."}],
                },
            },
        ],
        "has_more": False,
        "next_cursor": None,
    }


@pytest.fixture
def mock_users_list():
    """Standard users list response."""
    return {
        "object": "list",
        "results": [
            {
                "object": "user",
                "id": "user-1111",
                "type": "person",
                "name": "Alice Smith",
                "person": {"email": "alice@example.com"},
            },
            {
                "object": "user",
                "id": "user-2222",
                "type": "bot",
                "name": "Test Bot",
                "bot": {"owner": {"type": "workspace"}, "workspace_name": "Test"},
            },
        ],
        "has_more": False,
        "next_cursor": None,
    }
```

- [ ] **Step 2: Create test_client.py**

Create `cli/tests/test_client.py`:

```python
"""Tests for NotionClient."""

from __future__ import annotations

import pytest

from kctl_lib.exceptions import APIError, AuthenticationError, ConfigError
from kctl_lib.exceptions import ConnectionError as KctlConnectionError
from kctl_notion.core.client import NotionClient


class TestNotionClientConstructor:
    def test_requires_credential(self):
        with pytest.raises(ConfigError):
            NotionClient()

    def test_default_base_url(self):
        client = NotionClient(credential="ntn_test")
        assert client._base_url == "https://api.notion.com/v1"
        client.close()

    def test_notion_version_header(self):
        client = NotionClient(credential="ntn_test")
        headers = client._build_auth_header()
        assert headers["Notion-Version"] == "2022-06-28"
        assert headers["Authorization"] == "Bearer ntn_test"
        client.close()

    def test_context_manager(self):
        with NotionClient(credential="ntn_test") as client:
            assert client is not None


class TestNotionClientMethods:
    def test_search(self, httpx_mock, mock_search_results):
        httpx_mock.add_response(json=mock_search_results)
        with NotionClient(credential="ntn_test") as client:
            result = client.search(query="meeting")
        assert result["results"][0]["object"] == "page"

    def test_search_with_filter(self, httpx_mock, mock_search_results):
        httpx_mock.add_response(json=mock_search_results)
        with NotionClient(credential="ntn_test") as client:
            result = client.search(query="test", filter_type="page")
        req = httpx_mock.get_request()
        import json
        body = json.loads(req.content)
        assert body["filter"]["value"] == "page"

    def test_get_page(self, httpx_mock):
        page_data = {"object": "page", "id": "page-123"}
        httpx_mock.add_response(json=page_data)
        with NotionClient(credential="ntn_test") as client:
            result = client.get_page("page-123")
        assert result["id"] == "page-123"

    def test_create_page(self, httpx_mock):
        httpx_mock.add_response(json={"object": "page", "id": "new-page-123"}, status_code=200)
        with NotionClient(credential="ntn_test") as client:
            result = client.create_page("parent-123", "Test Page")
        assert result["id"] == "new-page-123"

    def test_update_page(self, httpx_mock):
        httpx_mock.add_response(json={"object": "page", "id": "page-123"})
        with NotionClient(credential="ntn_test") as client:
            result = client.update_page("page-123", {"title": {"title": []}})
        assert result["id"] == "page-123"

    def test_get_database(self, httpx_mock, mock_database):
        httpx_mock.add_response(json=mock_database)
        with NotionClient(credential="ntn_test") as client:
            result = client.get_database("db-123")
        assert result["object"] == "database"

    def test_query_database(self, httpx_mock, mock_database_query_results):
        httpx_mock.add_response(json=mock_database_query_results)
        with NotionClient(credential="ntn_test") as client:
            result = client.query_database("db-123")
        assert len(result["results"]) == 2

    def test_query_database_all(self, httpx_mock, mock_database_query_results):
        httpx_mock.add_response(json=mock_database_query_results)
        with NotionClient(credential="ntn_test") as client:
            rows = client.query_database_all("db-123")
        assert len(rows) == 2

    def test_get_block_children(self, httpx_mock, mock_blocks):
        httpx_mock.add_response(json=mock_blocks)
        with NotionClient(credential="ntn_test") as client:
            result = client.get_block_children("page-123")
        assert len(result["results"]) == 2

    def test_append_block_children(self, httpx_mock):
        httpx_mock.add_response(json={"object": "list", "results": []})
        with NotionClient(credential="ntn_test") as client:
            children = [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": []}}]
            result = client.append_block_children("page-123", children)
        assert result["object"] == "list"

    def test_list_users(self, httpx_mock, mock_users_list):
        httpx_mock.add_response(json=mock_users_list)
        with NotionClient(credential="ntn_test") as client:
            result = client.list_users()
        assert len(result["results"]) == 2

    def test_get_me(self, httpx_mock, mock_notion_me):
        httpx_mock.add_response(json=mock_notion_me)
        with NotionClient(credential="ntn_test") as client:
            result = client.get_me()
        assert result["name"] == "Test Integration"


class TestNotionClientErrors:
    def test_401_raises_auth_error(self, httpx_mock):
        httpx_mock.add_response(status_code=401, json={"message": "API token is invalid."})
        with NotionClient(credential="bad_token") as client:
            with pytest.raises(AuthenticationError):
                client.get("/users/me")

    def test_403_raises_auth_error(self, httpx_mock):
        httpx_mock.add_response(status_code=403, json={"message": "Forbidden"})
        with NotionClient(credential="ntn_test") as client:
            with pytest.raises(AuthenticationError):
                client.get("/pages/restricted")

    def test_404_raises_api_error(self, httpx_mock):
        httpx_mock.add_response(status_code=404, json={"message": "Not found"})
        with NotionClient(credential="ntn_test") as client:
            with pytest.raises(APIError) as exc_info:
                client.get("/pages/missing")
        assert exc_info.value.status_code == 404
```

- [ ] **Step 3: Create test_health.py**

Create `cli/tests/test_health.py`:

```python
"""Tests for health command."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_notion.cli import app

runner = CliRunner()


class TestHealthCommand:
    def test_health_success(self, httpx_mock, mock_notion_me, mock_search_results):
        httpx_mock.add_response(json=mock_notion_me)
        httpx_mock.add_response(json=mock_search_results)
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        assert "reachable" in result.output.lower() or "healthy" in result.output.lower()

    def test_health_json(self, httpx_mock, mock_notion_me, mock_search_results):
        httpx_mock.add_response(json=mock_notion_me)
        httpx_mock.add_response(json=mock_search_results)
        result = runner.invoke(app, ["--json", "health"])
        assert result.exit_code == 0
        assert "healthy" in result.output
```

- [ ] **Step 4: Create test_search.py**

Create `cli/tests/test_search.py`:

```python
"""Tests for search command."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_notion.cli import app

runner = CliRunner()


class TestSearchCommand:
    def test_search_results(self, httpx_mock, mock_search_results):
        httpx_mock.add_response(json=mock_search_results)
        result = runner.invoke(app, ["search", "meeting"])
        assert result.exit_code == 0
        assert "Meeting Notes" in result.output

    def test_search_json(self, httpx_mock, mock_search_results):
        httpx_mock.add_response(json=mock_search_results)
        result = runner.invoke(app, ["--json", "search", "meeting"])
        assert result.exit_code == 0
        assert "results" in result.output

    def test_search_empty(self, httpx_mock):
        httpx_mock.add_response(json={"object": "list", "results": [], "has_more": False})
        result = runner.invoke(app, ["search", "nonexistent"])
        assert result.exit_code == 0
        assert "no results" in result.output.lower()

    def test_search_with_type_filter(self, httpx_mock, mock_search_results):
        httpx_mock.add_response(json=mock_search_results)
        result = runner.invoke(app, ["search", "meeting", "--type", "page"])
        assert result.exit_code == 0
```

- [ ] **Step 5: Create test_pages.py**

Create `cli/tests/test_pages.py`:

```python
"""Tests for pages command group."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_notion.cli import app

runner = CliRunner()


class TestPagesList:
    def test_list_pages(self, httpx_mock, mock_search_results):
        httpx_mock.add_response(json=mock_search_results)
        result = runner.invoke(app, ["pages", "list"])
        assert result.exit_code == 0
        assert "Meeting Notes" in result.output

    def test_list_pages_json(self, httpx_mock, mock_search_results):
        httpx_mock.add_response(json=mock_search_results)
        result = runner.invoke(app, ["--json", "pages", "list"])
        assert result.exit_code == 0
        assert "pages" in result.output

    def test_list_pages_empty(self, httpx_mock):
        httpx_mock.add_response(json={"object": "list", "results": [], "has_more": False})
        result = runner.invoke(app, ["pages", "list"])
        assert result.exit_code == 0
        assert "no pages" in result.output.lower()


class TestPagesShow:
    def test_show_page(self, httpx_mock, mock_blocks):
        page_data = {
            "object": "page",
            "id": "page-1234-5678",
            "created_time": "2026-01-15T10:00:00.000Z",
            "last_edited_time": "2026-03-20T14:30:00.000Z",
            "parent": {"type": "workspace", "workspace": True},
            "archived": False,
            "url": "https://www.notion.so/page1234",
            "properties": {
                "title": {
                    "type": "title",
                    "title": [{"plain_text": "Test Page"}],
                }
            },
        }
        httpx_mock.add_response(json=page_data)
        httpx_mock.add_response(json=mock_blocks)
        result = runner.invoke(app, ["pages", "show", "page-1234-5678"])
        assert result.exit_code == 0
        assert "Test Page" in result.output

    def test_show_page_json(self, httpx_mock):
        page_data = {"object": "page", "id": "page-1234", "properties": {}}
        httpx_mock.add_response(json=page_data)
        result = runner.invoke(app, ["--json", "pages", "show", "page-1234"])
        assert result.exit_code == 0


class TestPagesCreate:
    def test_create_page(self, httpx_mock):
        httpx_mock.add_response(json={
            "object": "page",
            "id": "new-page-123",
            "url": "https://www.notion.so/newpage",
        })
        result = runner.invoke(app, ["pages", "create", "--parent", "parent-123", "--title", "New Page"])
        assert result.exit_code == 0
        assert "created" in result.output.lower()


class TestPagesUpdate:
    def test_update_title(self, httpx_mock):
        httpx_mock.add_response(json={"object": "page", "id": "page-123"})
        result = runner.invoke(app, ["pages", "update", "page-123", "--title", "Updated Title"])
        assert result.exit_code == 0
        assert "updated" in result.output.lower()

    def test_update_no_changes(self):
        result = runner.invoke(app, ["pages", "update", "page-123"])
        assert result.exit_code == 1
```

- [ ] **Step 6: Create test_databases.py**

Create `cli/tests/test_databases.py`:

```python
"""Tests for databases command group."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_notion.cli import app

runner = CliRunner()


class TestDatabasesList:
    def test_list_databases(self, httpx_mock, mock_database):
        search_result = {
            "object": "list",
            "results": [mock_database],
            "has_more": False,
        }
        httpx_mock.add_response(json=search_result)
        result = runner.invoke(app, ["databases", "list"])
        assert result.exit_code == 0
        assert "Project Tracker" in result.output

    def test_list_databases_empty(self, httpx_mock):
        httpx_mock.add_response(json={"object": "list", "results": [], "has_more": False})
        result = runner.invoke(app, ["databases", "list"])
        assert result.exit_code == 0
        assert "no databases" in result.output.lower()


class TestDatabasesShow:
    def test_show_database(self, httpx_mock, mock_database):
        httpx_mock.add_response(json=mock_database)
        result = runner.invoke(app, ["databases", "show", "db-1234"])
        assert result.exit_code == 0
        assert "Project Tracker" in result.output
        assert "Status" in result.output

    def test_show_database_json(self, httpx_mock, mock_database):
        httpx_mock.add_response(json=mock_database)
        result = runner.invoke(app, ["--json", "databases", "show", "db-1234"])
        assert result.exit_code == 0


class TestDatabasesQuery:
    def test_query(self, httpx_mock, mock_database_query_results):
        httpx_mock.add_response(json=mock_database_query_results)
        result = runner.invoke(app, ["databases", "query", "db-1234"])
        assert result.exit_code == 0
        assert "Task Alpha" in result.output

    def test_query_json(self, httpx_mock, mock_database_query_results):
        httpx_mock.add_response(json=mock_database_query_results)
        result = runner.invoke(app, ["--json", "databases", "query", "db-1234"])
        assert result.exit_code == 0
        assert "results" in result.output

    def test_query_with_sort(self, httpx_mock, mock_database_query_results):
        httpx_mock.add_response(json=mock_database_query_results)
        result = runner.invoke(app, ["databases", "query", "db-1234", "--sort", "Name"])
        assert result.exit_code == 0

    def test_query_empty(self, httpx_mock):
        httpx_mock.add_response(json={"object": "list", "results": [], "has_more": False})
        result = runner.invoke(app, ["databases", "query", "db-1234"])
        assert result.exit_code == 0
        assert "no rows" in result.output.lower()


class TestDatabasesExport:
    def test_export_csv(self, httpx_mock, mock_database, mock_database_query_results, tmp_path):
        httpx_mock.add_response(json=mock_database_query_results)
        httpx_mock.add_response(json=mock_database)
        out_file = tmp_path / "export.csv"
        result = runner.invoke(app, ["databases", "export", "db-1234", "--output", str(out_file)])
        assert result.exit_code == 0
        assert "exported" in result.output.lower()
        assert out_file.exists()
        content = out_file.read_text()
        assert "Name" in content
        assert "Task Alpha" in content

    def test_export_json(self, httpx_mock, mock_database, mock_database_query_results, tmp_path):
        httpx_mock.add_response(json=mock_database_query_results)
        httpx_mock.add_response(json=mock_database)
        out_file = tmp_path / "export.json"
        result = runner.invoke(app, ["databases", "export", "db-1234", "--format", "json", "--output", str(out_file)])
        assert result.exit_code == 0
        assert out_file.exists()

    def test_export_empty(self, httpx_mock):
        httpx_mock.add_response(json={"object": "list", "results": [], "has_more": False})
        result = runner.invoke(app, ["databases", "export", "db-1234"])
        assert result.exit_code == 0
        assert "empty" in result.output.lower()
```

- [ ] **Step 7: Create test_blocks.py**

Create `cli/tests/test_blocks.py`:

```python
"""Tests for blocks command group."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_notion.cli import app

runner = CliRunner()


class TestBlocksList:
    def test_list_blocks(self, httpx_mock, mock_blocks):
        httpx_mock.add_response(json=mock_blocks)
        result = runner.invoke(app, ["blocks", "list", "page-123"])
        assert result.exit_code == 0
        assert "Introduction" in result.output
        assert "paragraph" in result.output

    def test_list_blocks_json(self, httpx_mock, mock_blocks):
        httpx_mock.add_response(json=mock_blocks)
        result = runner.invoke(app, ["--json", "blocks", "list", "page-123"])
        assert result.exit_code == 0
        assert "blocks" in result.output

    def test_list_blocks_empty(self, httpx_mock):
        httpx_mock.add_response(json={"object": "list", "results": [], "has_more": False})
        result = runner.invoke(app, ["blocks", "list", "page-123"])
        assert result.exit_code == 0
        assert "no blocks" in result.output.lower()


class TestBlocksAppend:
    def test_append_paragraph(self, httpx_mock):
        httpx_mock.add_response(json={"object": "list", "results": []})
        result = runner.invoke(app, ["blocks", "append", "page-123", "--text", "Hello world"])
        assert result.exit_code == 0
        assert "appended" in result.output.lower()

    def test_append_heading(self, httpx_mock):
        httpx_mock.add_response(json={"object": "list", "results": []})
        result = runner.invoke(app, ["blocks", "append", "page-123", "--text", "Title", "--type", "heading_1"])
        assert result.exit_code == 0

    def test_append_json(self, httpx_mock):
        httpx_mock.add_response(json={"object": "list", "results": []})
        result = runner.invoke(app, ["--json", "blocks", "append", "page-123", "--text", "Test"])
        assert result.exit_code == 0
```

- [ ] **Step 8: Create test_users.py**

Create `cli/tests/test_users.py`:

```python
"""Tests for users command group."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_notion.cli import app

runner = CliRunner()


class TestUsersList:
    def test_list_users(self, httpx_mock, mock_users_list):
        httpx_mock.add_response(json=mock_users_list)
        result = runner.invoke(app, ["users", "list"])
        assert result.exit_code == 0
        assert "Alice Smith" in result.output
        assert "Test Bot" in result.output

    def test_list_users_json(self, httpx_mock, mock_users_list):
        httpx_mock.add_response(json=mock_users_list)
        result = runner.invoke(app, ["--json", "users", "list"])
        assert result.exit_code == 0
        assert "users" in result.output

    def test_list_users_empty(self, httpx_mock):
        httpx_mock.add_response(json={"object": "list", "results": [], "has_more": False})
        result = runner.invoke(app, ["users", "list"])
        assert result.exit_code == 0
        assert "no users" in result.output.lower()


class TestUsersMe:
    def test_me(self, httpx_mock, mock_notion_me):
        httpx_mock.add_response(json=mock_notion_me)
        result = runner.invoke(app, ["users", "me"])
        assert result.exit_code == 0
        assert "Test Integration" in result.output

    def test_me_json(self, httpx_mock, mock_notion_me):
        httpx_mock.add_response(json=mock_notion_me)
        result = runner.invoke(app, ["--json", "users", "me"])
        assert result.exit_code == 0
        assert "Test Integration" in result.output
```

- [ ] **Step 9: Update test_smoke.py with all command groups**

Replace `cli/tests/test_smoke.py` with:

```python
"""Smoke tests for CLI entry points."""

from typer.testing import CliRunner

from kctl_notion.cli import app

runner = CliRunner()


class TestCLISmoke:
    def test_help_exits_zero(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_version_flag(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "kctl-notion" in result.output

    def test_config_help(self):
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0

    def test_health_help(self):
        result = runner.invoke(app, ["health", "--help"])
        assert result.exit_code == 0

    def test_search_help(self):
        result = runner.invoke(app, ["search", "--help"])
        assert result.exit_code == 0

    def test_pages_help(self):
        result = runner.invoke(app, ["pages", "--help"])
        assert result.exit_code == 0

    def test_databases_help(self):
        result = runner.invoke(app, ["databases", "--help"])
        assert result.exit_code == 0

    def test_blocks_help(self):
        result = runner.invoke(app, ["blocks", "--help"])
        assert result.exit_code == 0

    def test_users_help(self):
        result = runner.invoke(app, ["users", "--help"])
        assert result.exit_code == 0
```

- [ ] **Step 10: Update CLAUDE.md**

Replace `CLAUDE.md` in the repo root with:

```markdown
# CLAUDE.md - kodemeio-notion

Notion integration management via kctl-notion CLI.

## Quick Commands

```bash
cd cli
uv sync --all-extras
uv run pytest tests/ -v           # Tests
uv run ruff check src/ tests/     # Lint
uv run ruff format src/ tests/    # Format
uv run kctl-notion --help         # CLI help
```

## Architecture

kctl-notion is a CLI tool built on `kctl-lib>=0.4.0` for managing Notion workspaces, databases, and pages via the Notion REST API v1.

### Key Paths

| Path | Description |
|------|-------------|
| `cli/src/kctl_notion/` | CLI source code |
| `cli/src/kctl_notion/core/` | Core modules (client, config, exceptions, callbacks) |
| `cli/src/kctl_notion/core/client.py` | NotionClient(APIClient) with Notion-Version header |
| `cli/src/kctl_notion/commands/` | Command implementations (7 groups) |
| `cli/tests/` | Test suite with pytest-httpx mocks |
| `cli/pyproject.toml` | Package configuration |

### Core Modules

| Module | Purpose |
|--------|---------|
| `core/client.py` | NotionClient(APIClient) -- search, pages, databases, blocks, users |
| `core/config.py` | ServiceConfig (token), profile management |
| `core/exceptions.py` | Re-exports from kctl-lib |
| `core/callbacks.py` | AppContext with get_client() |
| `core/plugins.py` | Plugin discovery |

### Command Groups (7)

| Group | Commands | Notion API |
|-------|----------|------------|
| `health` | health | GET /users/me, POST /search |
| `search` | search | POST /search |
| `pages` | list, show, create, update | GET/POST/PATCH /pages |
| `databases` | list, show, query, export | GET /databases, POST /databases/{id}/query |
| `blocks` | list, append | GET/PATCH /blocks/{id}/children |
| `users` | list, me | GET /users, GET /users/me |
| `config` | init, add, use, show, validate, remove, set, profiles, current | N/A |

### Important: Notion API Patterns

- Search uses **POST** /search (not GET)
- Database queries use **POST** /databases/{id}/query (not GET)
- All requests require `Notion-Version: 2022-06-28` header
- Auth: `Authorization: Bearer {integration_token}`

### CLI Standards

- Global options: `--json`, `--quiet/-q`, `--format/-f`, `--no-header`, `--profile/-p`, `--version/-V`
- Config subcommands: init, add, use, show, validate, remove, set, profiles, current
- Entry point: `kctl_notion.cli:_run`
- Python 3.12+, Typer + Rich + Pydantic 2
```

- [ ] **Step 11: Run full test suite**

```bash
cd cli && uv sync --all-extras && uv run pytest tests/ -v --tb=short
```

Expected: All tests pass (smoke + client + command tests).

- [ ] **Step 12: Lint and format**

```bash
cd cli && uv run ruff check src/ tests/ --fix && uv run ruff format src/ tests/
```

- [ ] **Step 13: Commit**

```bash
git add cli/tests/ CLAUDE.md
git commit -m "test: add comprehensive test suite for kctl-notion

- NotionClient unit tests (constructor, methods, errors)
- Command tests for all 7 groups using pytest-httpx
- 9 smoke tests covering --help for every command group
- Shared fixtures in conftest.py
- Updated CLAUDE.md with complete CLI documentation

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: Final verification

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

```bash
cd cli && uv run pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 2: Run linter**

```bash
cd cli && uv run ruff check src/ tests/
```

Expected: No lint errors.

- [ ] **Step 3: Verify CLI help shows all groups**

```bash
cd cli && uv run kctl-notion --help
```

Expected output should show: config, health, search, pages, databases, blocks, users

- [ ] **Step 4: Verify each command group --help**

```bash
cd cli && uv run kctl-notion pages --help && uv run kctl-notion databases --help && uv run kctl-notion blocks --help && uv run kctl-notion users --help
```

Expected: Each shows its subcommands.

- [ ] **Step 5: Verify version**

```bash
cd cli && uv run kctl-notion --version
```

Expected: `kctl-notion 0.1.0`

- [ ] **Step 6: Final commit (if any fixes were needed)**

Only if fixes were made during verification:

```bash
git add -A cli/
git commit -m "fix: address lint/test issues from final verification

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Summary

| Task | Description | Files Changed | Est. Effort |
|------|-------------|---------------|-------------|
| 1 | Setup: client, config, exceptions | 7 | Medium |
| 2 | health + search commands | 3 | Small |
| 3 | pages command group | 2 | Medium |
| 4 | databases command group | 2 | Medium |
| 5 | blocks + users commands | 3 | Small |
| 6 | Tests + CI + CLAUDE.md | 10 | Medium |
| 7 | Final verification | 0 | Small |

**Total files:** 24 (10 new, 14 modified)
**Total commands:** ~20 commands across 7 groups
**Total estimated tests:** ~45-50 tests
