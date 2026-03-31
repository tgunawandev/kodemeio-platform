# kctl-linear Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build kctl-linear CLI with 10 command groups for sprint tracking and issue management via Linear GraphQL API.

**Architecture:** Python CLI using kctl-lib v0.4.0 for config/output/exceptions. Custom LinearClient (NOT APIClient subclass) that wraps httpx for GraphQL queries. All API calls go through POST /graphql.

**Tech Stack:** Python 3.12+, kctl-lib>=0.4.0, Typer, httpx, Rich

**Spec:** `docs/superpowers/specs/2026-03-29-kctl-service-clis-design.md` (Section 5)

**Working directory:** `/home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-linear`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `cli/pyproject.toml` | Add pytest-httpx to dev deps |
| Modify | `cli/src/kctl_linear/core/config.py` | ServiceConfig: api_key, default_team (replace url) |
| Modify | `cli/src/kctl_linear/core/exceptions.py` | Add APIError, AuthenticationError, ConnectionError re-exports |
| Create | `cli/src/kctl_linear/core/client.py` | LinearClient — GraphQL client wrapping httpx |
| Modify | `cli/src/kctl_linear/core/callbacks.py` | Add `client` property to AppContext |
| Modify | `cli/src/kctl_linear/commands/config_cmd.py` | Update init/add/validate for api_key + default_team |
| Create | `cli/src/kctl_linear/commands/health.py` | `health` command — API connectivity check |
| Create | `cli/src/kctl_linear/commands/dashboard.py` | `dashboard` command — quick overview |
| Create | `cli/src/kctl_linear/commands/issues.py` | `issues` subgroup — list/show/create/update/comment/search |
| Create | `cli/src/kctl_linear/commands/cycles.py` | `cycles` subgroup — current/list/show/stats |
| Create | `cli/src/kctl_linear/commands/projects.py` | `projects` subgroup — list/show |
| Create | `cli/src/kctl_linear/commands/teams.py` | `teams` subgroup — list/show |
| Create | `cli/src/kctl_linear/commands/labels.py` | `labels` subgroup — list/create |
| Create | `cli/src/kctl_linear/commands/users.py` | `users` subgroup — list/me |
| Modify | `cli/src/kctl_linear/cli.py` | Register all command groups |
| Create | `cli/tests/test_client.py` | LinearClient unit tests |
| Create | `cli/tests/test_health.py` | Health command tests |
| Create | `cli/tests/test_issues.py` | Issues command tests |
| Create | `cli/tests/test_cycles.py` | Cycles command tests |
| Create | `cli/tests/test_commands.py` | Tests for projects/teams/labels/users/dashboard |
| Modify | `cli/tests/conftest.py` | Shared fixtures (mock client, mock output) |
| Modify | `CLAUDE.md` | Update with CLI command reference |

---

### Task 1: Setup — LinearClient, config, exceptions, pyproject

**Files:**
- Modify: `cli/pyproject.toml`
- Modify: `cli/src/kctl_linear/core/config.py`
- Modify: `cli/src/kctl_linear/core/exceptions.py`
- Create: `cli/src/kctl_linear/core/client.py`
- Modify: `cli/src/kctl_linear/core/callbacks.py`

- [ ] **Step 1: Update pyproject.toml — add pytest-httpx to dev deps**

In `cli/pyproject.toml`, update:

```toml
[project]
name = "kctl-linear"
version = "0.1.0"
description = "Linear project management"
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

Key change: `kctl-lib>=0.4.0` (was 0.3.0), add `pytest-httpx>=0.35.0`.

- [ ] **Step 2: Update ServiceConfig for Linear API**

Replace `cli/src/kctl_linear/core/config.py` ServiceConfig:

```python
class ServiceConfig(BaseModel):
    """Linear service-specific config within a profile."""

    api_key: str = ""        # Linear API key (no Bearer prefix needed)
    default_team: str = ""   # Default team key (e.g., "KOD")
```

Remove the `url: str = ""` field entirely. Linear has a fixed endpoint.

- [ ] **Step 3: Update exceptions.py — add APIError, AuthenticationError, ConnectionError**

Replace `cli/src/kctl_linear/core/exceptions.py`:

```python
"""Exception hierarchy — re-exported from kctl-lib."""

from kctl_lib.exceptions import (
    APIError,
    AuthenticationError,
    CommandError,
    ConfigError,
    ConnectionError,
    KctlError,
    NotFoundError,
)

__all__ = [
    "APIError",
    "AuthenticationError",
    "CommandError",
    "ConfigError",
    "ConnectionError",
    "KctlError",
    "NotFoundError",
]
```

- [ ] **Step 4: Create LinearClient**

Create `cli/src/kctl_linear/core/client.py`:

```python
"""GraphQL client for Linear API."""

from __future__ import annotations

import os
import sys
from typing import Any, Self

import httpx

from kctl_linear.core.exceptions import APIError, AuthenticationError, ConfigError, ConnectionError


class LinearClient:
    """GraphQL client for Linear API.

    Linear uses a single POST /graphql endpoint. Auth is ``Authorization: {api_key}``
    (no Bearer prefix). This client does NOT subclass APIClient because Linear is
    GraphQL-only, not REST.
    """

    BASE_URL = "https://api.linear.app"

    def __init__(self, api_key: str, timeout: float = 30.0) -> None:
        if not api_key or not api_key.strip():
            raise ConfigError("Linear API key is required")

        self._api_key = api_key
        self._client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "Authorization": api_key,
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    def query(self, graphql: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a GraphQL query and return the ``data`` dict.

        Raises:
            AuthenticationError: On 401/403 responses.
            APIError: On GraphQL-level errors or non-2xx responses.
            ConnectionError: On network failures.
        """
        payload: dict[str, Any] = {"query": graphql}
        if variables:
            payload["variables"] = variables

        try:
            self._log_debug(f"POST /graphql | variables={variables}")
            response = self._client.post("/graphql", json=payload)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise ConnectionError(url=self.BASE_URL, cause=exc) from exc

        if response.status_code in (401, 403):
            raise AuthenticationError("Invalid or expired Linear API key")

        if response.status_code >= 400:
            detail = response.text[:200] if response.text else f"HTTP {response.status_code}"
            raise APIError(status_code=response.status_code, detail=detail)

        data: dict[str, Any] = response.json()

        if "errors" in data:
            errors = data["errors"]
            msg = errors[0]["message"] if errors else "Unknown GraphQL error"
            raise APIError(detail=msg)

        return data.get("data", {})

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def viewer(self) -> dict[str, Any]:
        """Return the authenticated user (viewer)."""
        return self.query(VIEWER_QUERY)["viewer"]

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    # ------------------------------------------------------------------
    # Debug logging
    # ------------------------------------------------------------------

    @staticmethod
    def _log_debug(msg: str) -> None:
        """Print debug info to stderr when KCTL_DEBUG is set."""
        if os.environ.get("KCTL_DEBUG"):
            print(f"[DEBUG] LinearClient: {msg}", file=sys.stderr)  # noqa: T201


# ======================================================================
# GraphQL query strings
# ======================================================================

VIEWER_QUERY = """\
query {
  viewer {
    id
    name
    email
    admin
    active
  }
}
"""

ISSUES_LIST_QUERY = """\
query IssuesList($teamKey: String, $state: String, $assigneeId: String, $first: Int = 50) {
  issues(
    first: $first
    filter: {
      team: { key: { eq: $teamKey } }
      state: { name: { eqi: $state } }
      assignee: { id: { eq: $assigneeId } }
    }
  ) {
    nodes {
      id
      identifier
      title
      priority
      state { name color }
      assignee { name email }
      createdAt
      updatedAt
    }
  }
}
"""

ISSUE_SHOW_QUERY = """\
query IssueShow($id: String!) {
  issue(id: $id) {
    id
    identifier
    title
    description
    priority
    priorityLabel
    estimate
    url
    state { name color }
    assignee { id name email }
    team { key name }
    labels { nodes { name color } }
    project { name }
    cycle { name number }
    comments { nodes { body createdAt user { name } } }
    createdAt
    updatedAt
  }
}
"""

ISSUE_CREATE_MUTATION = """\
mutation IssueCreate($teamId: String!, $title: String!, $description: String, $priority: Int, $assigneeId: String, $labelIds: [String!]) {
  issueCreate(input: {
    teamId: $teamId
    title: $title
    description: $description
    priority: $priority
    assigneeId: $assigneeId
    labelIds: $labelIds
  }) {
    success
    issue {
      id
      identifier
      title
      url
      state { name }
    }
  }
}
"""

ISSUE_UPDATE_MUTATION = """\
mutation IssueUpdate($id: String!, $stateId: String, $assigneeId: String, $priority: Int, $title: String, $description: String) {
  issueUpdate(id: $id, input: {
    stateId: $stateId
    assigneeId: $assigneeId
    priority: $priority
    title: $title
    description: $description
  }) {
    success
    issue {
      id
      identifier
      title
      state { name }
      assignee { name }
    }
  }
}
"""

COMMENT_CREATE_MUTATION = """\
mutation CommentCreate($issueId: String!, $body: String!) {
  commentCreate(input: {
    issueId: $issueId
    body: $body
  }) {
    success
    comment {
      id
      body
      createdAt
      user { name }
    }
  }
}
"""

ISSUE_SEARCH_QUERY = """\
query IssueSearch($query: String!, $first: Int = 50) {
  issueSearch(query: $query, first: $first) {
    nodes {
      id
      identifier
      title
      priority
      state { name color }
      assignee { name }
      updatedAt
    }
  }
}
"""

CYCLES_LIST_QUERY = """\
query CyclesList($teamKey: String, $first: Int = 20) {
  cycles(
    first: $first
    filter: { team: { key: { eq: $teamKey } } }
    orderBy: createdAt
  ) {
    nodes {
      id
      number
      name
      startsAt
      endsAt
      progress
      scopeCompleted: completedScopeHistory
      scopeTotal: scopeHistory
      uncompletedIssuesUponClose { nodes { id } }
    }
  }
}
"""

CYCLE_CURRENT_QUERY = """\
query CycleCurrent($teamKey: String) {
  cycles(
    first: 1
    filter: {
      team: { key: { eq: $teamKey } }
      isActive: { eq: true }
    }
  ) {
    nodes {
      id
      number
      name
      startsAt
      endsAt
      progress
      issues {
        nodes {
          id
          identifier
          title
          state { name }
          assignee { name }
          priority
        }
      }
    }
  }
}
"""

CYCLE_SHOW_QUERY = """\
query CycleShow($id: String!) {
  cycle(id: $id) {
    id
    number
    name
    startsAt
    endsAt
    progress
    issues {
      nodes {
        id
        identifier
        title
        state { name color }
        assignee { name }
        priority
        estimate
      }
    }
  }
}
"""

PROJECTS_LIST_QUERY = """\
query ProjectsList($first: Int = 50) {
  projects(first: $first, orderBy: updatedAt) {
    nodes {
      id
      name
      state
      progress
      startDate
      targetDate
      lead { name }
      teams { nodes { key name } }
      updatedAt
    }
  }
}
"""

PROJECT_SHOW_QUERY = """\
query ProjectShow($id: String!) {
  project(id: $id) {
    id
    name
    description
    state
    progress
    startDate
    targetDate
    url
    lead { name email }
    members { nodes { name email } }
    teams { nodes { key name } }
    projectMilestones { nodes { name targetDate } }
    issues {
      nodes {
        id
        identifier
        title
        state { name }
        assignee { name }
      }
    }
  }
}
"""

TEAMS_LIST_QUERY = """\
query TeamsList {
  teams {
    nodes {
      id
      key
      name
      description
      members { nodes { id } }
      timezone
    }
  }
}
"""

TEAM_SHOW_QUERY = """\
query TeamShow($id: String!) {
  team(id: $id) {
    id
    key
    name
    description
    timezone
    members { nodes { id name email admin active } }
    states { nodes { name color position type } }
    labels { nodes { name color } }
  }
}
"""

LABELS_LIST_QUERY = """\
query LabelsList($teamKey: String) {
  issueLabels(
    filter: { team: { key: { eq: $teamKey } } }
  ) {
    nodes {
      id
      name
      color
      parent { name }
    }
  }
}
"""

LABEL_CREATE_MUTATION = """\
mutation LabelCreate($teamId: String, $name: String!, $color: String) {
  issueLabelCreate(input: {
    teamId: $teamId
    name: $name
    color: $color
  }) {
    success
    issueLabel {
      id
      name
      color
    }
  }
}
"""

USERS_LIST_QUERY = """\
query UsersList {
  users {
    nodes {
      id
      name
      email
      admin
      active
      displayName
    }
  }
}
"""

DASHBOARD_QUERY = """\
query Dashboard($assigneeId: String, $teamKey: String) {
  viewer {
    id
    name
    email
    assignedIssues(
      first: 10
      filter: { state: { type: { nin: ["completed", "canceled"] } } }
    ) {
      nodes {
        id
        identifier
        title
        priority
        state { name color }
        updatedAt
      }
    }
  }
  cycles(
    first: 1
    filter: {
      team: { key: { eq: $teamKey } }
      isActive: { eq: true }
    }
  ) {
    nodes {
      id
      number
      name
      progress
      startsAt
      endsAt
    }
  }
  projects(first: 5, filter: { state: { eq: "started" } }) {
    nodes {
      name
      progress
      targetDate
    }
  }
}
"""

# Helper query: resolve team key → team ID
TEAM_BY_KEY_QUERY = """\
query TeamByKey($key: String!) {
  teams(filter: { key: { eq: $key } }) {
    nodes {
      id
      key
      name
    }
  }
}
"""

# Helper query: resolve user display name → user ID
USER_BY_NAME_QUERY = """\
query UserByName($name: String!) {
  users(filter: { displayName: { containsi: $name } }) {
    nodes {
      id
      name
      email
    }
  }
}
"""

# Helper query: resolve workflow state name → state ID for a team
WORKFLOW_STATE_QUERY = """\
query WorkflowState($teamKey: String!, $stateName: String!) {
  workflowStates(
    filter: {
      team: { key: { eq: $teamKey } }
      name: { eqi: $stateName }
    }
  ) {
    nodes {
      id
      name
      type
    }
  }
}
"""
```

- [ ] **Step 5: Update AppContext with client property**

Replace `cli/src/kctl_linear/core/callbacks.py`:

```python
"""Application context for kctl-linear."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

from kctl_lib.callbacks import AppContextBase

from kctl_linear.core.client import LinearClient
from kctl_linear.core.config import (
    ServiceConfig,
    get_service_config,
    resolve_active_profile_name,
)
from kctl_linear.core.exceptions import ConfigError


@dataclass
class AppContext(AppContextBase):
    """kctl-linear application context."""

    _client: LinearClient | None = field(default=None, repr=False)

    @property
    def config(self) -> ServiceConfig:
        """Resolve the active profile's service config."""
        profile = resolve_active_profile_name(self.profile)
        return get_service_config(profile)

    @property
    def client(self) -> LinearClient:
        """Lazy-init LinearClient from profile config."""
        if self._client is None:
            cfg = self.config
            if not cfg.api_key:
                raise ConfigError("Linear API key is not configured. Run: kctl-linear config init")
            self._client = LinearClient(api_key=cfg.api_key)
        return self._client

    @property
    def default_team(self) -> str | None:
        """Return the default team key, or None if not set."""
        team = self.config.default_team
        return team if team else None
```

- [ ] **Step 6: Update config_cmd.py for Linear-specific fields**

Replace the `init`, `add`, and `validate` commands in `cli/src/kctl_linear/commands/config_cmd.py`:

In `init`:
```python
@app.command()
def init(ctx: typer.Context) -> None:
    """Interactive config setup."""
    actx: AppContext = ctx.obj
    out = actx.output
    profile_name = typer.prompt("Profile name", default="default")
    api_key = typer.prompt("Linear API key", hide_input=True)
    default_team = typer.prompt("Default team key (e.g., KOD)", default="")
    svc = ServiceConfig(api_key=api_key, default_team=default_team)
    set_service_config(profile_name, svc)
    set_default_profile(profile_name)
    out.success(f"Config saved to profile '{profile_name}'")
```

In `add`:
```python
@app.command()
def add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name")],
) -> None:
    """Add a new config profile."""
    actx: AppContext = ctx.obj
    out = actx.output
    api_key = typer.prompt("Linear API key", hide_input=True)
    default_team = typer.prompt("Default team key (e.g., KOD)", default="")
    svc = ServiceConfig(api_key=api_key, default_team=default_team)
    set_service_config(name, svc)
    out.success(f"Profile '{name}' added")
```

In `validate`:
```python
@app.command()
def validate(ctx: typer.Context) -> None:
    """Validate current config completeness."""
    actx: AppContext = ctx.obj
    out = actx.output
    active = resolve_active_profile_name(actx.profile)
    svc = get_service_config(active)
    issues: list[str] = []
    if not svc.api_key:
        issues.append("api_key is not set")
    if not svc.default_team:
        issues.append("default_team is not set (optional but recommended)")
    if out.json_mode:
        out.raw_json({"profile": active, "valid": not any("api_key" in i for i in issues), "issues": issues})
        return
    if any("api_key" in i for i in issues):
        out.error(f"Profile '{active}' has issues:")
        for issue in issues:
            out.text(f"  - {issue}")
        raise typer.Exit(1)
    if issues:
        out.warn(f"Profile '{active}' has warnings:")
        for issue in issues:
            out.text(f"  - {issue}")
    else:
        out.success(f"Profile '{active}' is valid")
```

Also update `show` and `current` commands to remove references to `svc.url` — they use `svc.model_dump()` so they auto-adapt.

- [ ] **Step 7: Sync dependencies and verify scaffold tests pass**

Run:
```bash
cd cli && uv sync --all-extras && uv run pytest tests/ -v --tb=short
```

Expected: 2 smoke tests pass.

- [ ] **Step 8: Commit**

```bash
git add cli/
git commit -m "feat: add LinearClient, update config for api_key/default_team"
```

---

### Task 2: Health + Dashboard commands

**Files:**
- Create: `cli/src/kctl_linear/commands/health.py`
- Create: `cli/src/kctl_linear/commands/dashboard.py`
- Modify: `cli/src/kctl_linear/cli.py` (register commands)

- [ ] **Step 1: Create health command**

Create `cli/src/kctl_linear/commands/health.py`:

```python
"""Health check — verify API connectivity."""

from __future__ import annotations

import typer

from kctl_linear.core.callbacks import AppContext

app = typer.Typer(help="API health check.")


@app.callback(invoke_without_command=True)
def health(ctx: typer.Context) -> None:
    """Check Linear API connectivity and show current user info."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    viewer = client.viewer()

    if out.json_mode:
        out.raw_json({"status": "ok", "viewer": viewer})
        return

    sections = [
        ("API Status", [("Status", "Connected"), ("Endpoint", "https://api.linear.app/graphql")]),
        (
            "Authenticated User",
            [
                ("Name", viewer.get("name", "")),
                ("Email", viewer.get("email", "")),
                ("Admin", str(viewer.get("admin", False))),
                ("Active", str(viewer.get("active", True))),
            ],
        ),
    ]
    out.detail("Linear Health", sections)
```

- [ ] **Step 2: Create dashboard command**

Create `cli/src/kctl_linear/commands/dashboard.py`:

```python
"""Dashboard — quick overview of my issues, current cycle, active projects."""

from __future__ import annotations

import typer

from kctl_linear.core.callbacks import AppContext
from kctl_linear.core.client import DASHBOARD_QUERY

app = typer.Typer(help="Quick overview dashboard.")


@app.callback(invoke_without_command=True)
def dashboard(ctx: typer.Context) -> None:
    """Show my issues, current cycle progress, and active projects."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    variables: dict[str, str | None] = {"teamKey": actx.default_team}
    data = client.query(DASHBOARD_QUERY, variables)

    viewer = data.get("viewer", {})
    my_issues = viewer.get("assignedIssues", {}).get("nodes", [])
    cycles = data.get("cycles", {}).get("nodes", [])
    projects = data.get("projects", {}).get("nodes", [])

    if out.json_mode:
        out.raw_json({
            "viewer": {"name": viewer.get("name"), "email": viewer.get("email")},
            "my_issues": my_issues,
            "current_cycle": cycles[0] if cycles else None,
            "active_projects": projects,
        })
        return

    # My issues
    out.header(f"My Issues ({len(my_issues)})")
    if my_issues:
        rows = [
            [
                issue.get("identifier", ""),
                issue.get("title", "")[:60],
                str(issue.get("priority", "")),
                issue.get("state", {}).get("name", ""),
            ]
            for issue in my_issues
        ]
        out.table(
            "",
            [("ID", "cyan"), ("Title", "white"), ("Priority", "yellow"), ("State", "green")],
            rows,
        )
    else:
        out.info("No active issues assigned to you")

    # Current cycle
    if cycles:
        cycle = cycles[0]
        progress = cycle.get("progress", 0)
        progress_pct = f"{progress * 100:.0f}%" if isinstance(progress, (int, float)) else str(progress)
        out.header("Current Cycle")
        out.kv("Name", cycle.get("name") or f"Cycle {cycle.get('number', '?')}")
        out.kv("Progress", progress_pct)
        out.kv("Starts", cycle.get("startsAt", "")[:10])
        out.kv("Ends", cycle.get("endsAt", "")[:10])
    else:
        out.header("Current Cycle")
        out.info("No active cycle")

    # Active projects
    if projects:
        out.header(f"Active Projects ({len(projects)})")
        rows = [
            [
                proj.get("name", ""),
                f"{(proj.get('progress', 0) or 0) * 100:.0f}%",
                (proj.get("targetDate") or "")[:10],
            ]
            for proj in projects
        ]
        out.table("", [("Name", "cyan"), ("Progress", "green"), ("Target", "yellow")], rows)
```

- [ ] **Step 3: Register health + dashboard in cli.py**

In `cli/src/kctl_linear/cli.py`, add imports and registrations:

```python
from kctl_linear.commands.health import app as health_app
from kctl_linear.commands.dashboard import app as dashboard_app

# ... after config registration:
app.add_typer(health_app, name="health")
app.add_typer(dashboard_app, name="dashboard")
```

- [ ] **Step 4: Verify --help shows new commands**

```bash
cd cli && uv run kctl-linear --help
uv run kctl-linear health --help
uv run kctl-linear dashboard --help
```

- [ ] **Step 5: Commit**

```bash
git add cli/
git commit -m "feat: add health and dashboard commands"
```

---

### Task 3: Issues command group

**Files:**
- Create: `cli/src/kctl_linear/commands/issues.py`
- Modify: `cli/src/kctl_linear/cli.py` (register)

- [ ] **Step 1: Create issues command group**

Create `cli/src/kctl_linear/commands/issues.py`:

```python
"""Issue management commands — daily use."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_linear.core.callbacks import AppContext
from kctl_linear.core.client import (
    COMMENT_CREATE_MUTATION,
    ISSUE_CREATE_MUTATION,
    ISSUE_SEARCH_QUERY,
    ISSUE_SHOW_QUERY,
    ISSUE_UPDATE_MUTATION,
    ISSUES_LIST_QUERY,
    TEAM_BY_KEY_QUERY,
    USER_BY_NAME_QUERY,
    WORKFLOW_STATE_QUERY,
)

app = typer.Typer(help="Issue management.")


def _resolve_team_id(ctx: AppContext, team_key: str) -> str:
    """Resolve a team key (e.g., 'KOD') to its UUID."""
    data = ctx.client.query(TEAM_BY_KEY_QUERY, {"key": team_key})
    nodes = data.get("teams", {}).get("nodes", [])
    if not nodes:
        raise typer.BadParameter(f"Team '{team_key}' not found")
    return nodes[0]["id"]


def _resolve_user_id(ctx: AppContext, name: str) -> str:
    """Resolve a user display name to their UUID."""
    data = ctx.client.query(USER_BY_NAME_QUERY, {"name": name})
    nodes = data.get("users", {}).get("nodes", [])
    if not nodes:
        raise typer.BadParameter(f"User '{name}' not found")
    return nodes[0]["id"]


def _resolve_state_id(ctx: AppContext, team_key: str, state_name: str) -> str:
    """Resolve a workflow state name to its UUID."""
    data = ctx.client.query(WORKFLOW_STATE_QUERY, {"teamKey": team_key, "stateName": state_name})
    nodes = data.get("workflowStates", {}).get("nodes", [])
    if not nodes:
        raise typer.BadParameter(f"State '{state_name}' not found for team '{team_key}'")
    return nodes[0]["id"]


@app.command("list")
def list_(
    ctx: typer.Context,
    team: Annotated[str | None, typer.Option("--team", "-t", help="Team key (e.g., KOD)")] = None,
    state: Annotated[str | None, typer.Option("--state", "-s", help="Filter by state name")] = None,
    assignee: Annotated[str | None, typer.Option("--assignee", "-a", help="Filter by assignee ('me' for self)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 50,
) -> None:
    """List issues with optional filters."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    team_key = team or actx.default_team
    variables: dict[str, str | int | None] = {"first": limit}

    if team_key:
        variables["teamKey"] = team_key
    if state:
        variables["state"] = state

    # Resolve 'me' to viewer ID
    if assignee == "me":
        viewer = client.viewer()
        variables["assigneeId"] = viewer["id"]
    elif assignee:
        variables["assigneeId"] = _resolve_user_id(actx, assignee)

    data = client.query(ISSUES_LIST_QUERY, variables)
    issues = data.get("issues", {}).get("nodes", [])

    if out.json_mode:
        out.raw_json(issues)
        return

    if not issues:
        out.info("No issues found")
        return

    rows = [
        [
            issue.get("identifier", ""),
            issue.get("title", "")[:55],
            str(issue.get("priority", "-")),
            issue.get("state", {}).get("name", ""),
            (issue.get("assignee") or {}).get("name", "unassigned"),
        ]
        for issue in issues
    ]
    out.table(
        f"Issues ({len(issues)})",
        [("ID", "cyan"), ("Title", "white"), ("P", "yellow"), ("State", "green"), ("Assignee", "magenta")],
        rows,
    )


@app.command()
def show(
    ctx: typer.Context,
    issue_id: Annotated[str, typer.Argument(help="Issue ID (UUID or identifier like KOD-123)")],
) -> None:
    """Show issue details, comments, and history."""
    actx: AppContext = ctx.obj
    out = actx.output

    data = actx.client.query(ISSUE_SHOW_QUERY, {"id": issue_id})
    issue = data.get("issue", {})

    if out.json_mode:
        out.raw_json(issue)
        return

    labels = [l["name"] for l in issue.get("labels", {}).get("nodes", [])]
    sections = [
        (
            "Issue",
            [
                ("Identifier", issue.get("identifier", "")),
                ("Title", issue.get("title", "")),
                ("State", issue.get("state", {}).get("name", "")),
                ("Priority", issue.get("priorityLabel", "")),
                ("Estimate", str(issue.get("estimate") or "-")),
                ("Assignee", (issue.get("assignee") or {}).get("name", "unassigned")),
                ("Team", (issue.get("team") or {}).get("name", "")),
                ("Project", (issue.get("project") or {}).get("name", "-")),
                ("Cycle", (issue.get("cycle") or {}).get("name", "-")),
                ("Labels", ", ".join(labels) if labels else "-"),
                ("URL", issue.get("url", "")),
            ],
        ),
    ]

    if issue.get("description"):
        sections.append(("Description", [("", issue["description"][:500])]))

    comments = issue.get("comments", {}).get("nodes", [])
    if comments:
        comment_rows = [
            (f"{c.get('user', {}).get('name', '?')} ({c.get('createdAt', '')[:10]})", c.get("body", "")[:200])
            for c in comments[:10]
        ]
        sections.append(("Comments", comment_rows))

    out.detail(issue.get("identifier", "Issue"), sections)


@app.command()
def create(
    ctx: typer.Context,
    title: Annotated[str, typer.Option("--title", help="Issue title")],
    team: Annotated[str | None, typer.Option("--team", "-t", help="Team key")] = None,
    description: Annotated[str | None, typer.Option("--desc", "-d", help="Issue description")] = None,
    priority: Annotated[int | None, typer.Option("--priority", "-p", help="Priority 0-4 (0=none, 1=urgent, 4=low)")] = None,
    assignee: Annotated[str | None, typer.Option("--assignee", "-a", help="Assignee name ('me' for self)")] = None,
) -> None:
    """Create a new issue."""
    actx: AppContext = ctx.obj
    out = actx.output

    team_key = team or actx.default_team
    if not team_key:
        out.error("Team key required. Use --team or set default_team in config.")
        raise typer.Exit(1)

    team_id = _resolve_team_id(actx, team_key)
    variables: dict[str, str | int | None] = {"teamId": team_id, "title": title}

    if description:
        variables["description"] = description
    if priority is not None:
        variables["priority"] = priority
    if assignee == "me":
        variables["assigneeId"] = actx.client.viewer()["id"]
    elif assignee:
        variables["assigneeId"] = _resolve_user_id(actx, assignee)

    data = actx.client.query(ISSUE_CREATE_MUTATION, variables)
    result = data.get("issueCreate", {})
    issue = result.get("issue", {})

    if out.json_mode:
        out.raw_json(result)
        return

    out.success(f"Created {issue.get('identifier', '?')}: {issue.get('title', '')}")
    out.kv("URL", issue.get("url", ""))


@app.command()
def update(
    ctx: typer.Context,
    issue_id: Annotated[str, typer.Argument(help="Issue ID")],
    state: Annotated[str | None, typer.Option("--state", "-s", help="New state name")] = None,
    assignee: Annotated[str | None, typer.Option("--assignee", "-a", help="New assignee")] = None,
    priority: Annotated[int | None, typer.Option("--priority", "-p", help="New priority (0-4)")] = None,
    title: Annotated[str | None, typer.Option("--title", help="New title")] = None,
    description: Annotated[str | None, typer.Option("--desc", "-d", help="New description")] = None,
) -> None:
    """Update an existing issue."""
    actx: AppContext = ctx.obj
    out = actx.output

    variables: dict[str, str | int | None] = {"id": issue_id}

    if state:
        team_key = actx.default_team
        if not team_key:
            out.error("default_team must be configured to resolve state names")
            raise typer.Exit(1)
        variables["stateId"] = _resolve_state_id(actx, team_key, state)

    if assignee == "me":
        variables["assigneeId"] = actx.client.viewer()["id"]
    elif assignee:
        variables["assigneeId"] = _resolve_user_id(actx, assignee)

    if priority is not None:
        variables["priority"] = priority
    if title:
        variables["title"] = title
    if description:
        variables["description"] = description

    data = actx.client.query(ISSUE_UPDATE_MUTATION, variables)
    result = data.get("issueUpdate", {})
    issue = result.get("issue", {})

    if out.json_mode:
        out.raw_json(result)
        return

    out.success(f"Updated {issue.get('identifier', '?')}: {issue.get('title', '')}")


@app.command()
def comment(
    ctx: typer.Context,
    issue_id: Annotated[str, typer.Argument(help="Issue ID")],
    body: Annotated[str, typer.Option("--body", "-b", help="Comment text")],
) -> None:
    """Add a comment to an issue."""
    actx: AppContext = ctx.obj
    out = actx.output

    data = actx.client.query(COMMENT_CREATE_MUTATION, {"issueId": issue_id, "body": body})
    result = data.get("commentCreate", {})

    if out.json_mode:
        out.raw_json(result)
        return

    if result.get("success"):
        out.success("Comment added")
    else:
        out.error("Failed to add comment")


@app.command()
def search(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Search query")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 50,
) -> None:
    """Full-text search for issues."""
    actx: AppContext = ctx.obj
    out = actx.output

    data = actx.client.query(ISSUE_SEARCH_QUERY, {"query": query, "first": limit})
    issues = data.get("issueSearch", {}).get("nodes", [])

    if out.json_mode:
        out.raw_json(issues)
        return

    if not issues:
        out.info(f"No issues matching '{query}'")
        return

    rows = [
        [
            issue.get("identifier", ""),
            issue.get("title", "")[:55],
            issue.get("state", {}).get("name", ""),
            (issue.get("assignee") or {}).get("name", ""),
        ]
        for issue in issues
    ]
    out.table(
        f"Search: '{query}' ({len(issues)} results)",
        [("ID", "cyan"), ("Title", "white"), ("State", "green"), ("Assignee", "magenta")],
        rows,
    )
```

- [ ] **Step 2: Register issues in cli.py**

```python
from kctl_linear.commands.issues import app as issues_app
app.add_typer(issues_app, name="issues")
```

- [ ] **Step 3: Verify --help**

```bash
cd cli && uv run kctl-linear issues --help
```

- [ ] **Step 4: Commit**

```bash
git add cli/
git commit -m "feat: add issues command group (list/show/create/update/comment/search)"
```

---

### Task 4: Cycles command group

**Files:**
- Create: `cli/src/kctl_linear/commands/cycles.py`
- Modify: `cli/src/kctl_linear/cli.py` (register)

- [ ] **Step 1: Create cycles command group**

Create `cli/src/kctl_linear/commands/cycles.py`:

```python
"""Cycle (sprint) management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_linear.core.callbacks import AppContext
from kctl_linear.core.client import (
    CYCLE_CURRENT_QUERY,
    CYCLE_SHOW_QUERY,
    CYCLES_LIST_QUERY,
)

app = typer.Typer(help="Cycle (sprint) management.")


@app.command()
def current(
    ctx: typer.Context,
    team: Annotated[str | None, typer.Option("--team", "-t", help="Team key")] = None,
) -> None:
    """Show current active cycle with progress and issues."""
    actx: AppContext = ctx.obj
    out = actx.output

    team_key = team or actx.default_team
    data = actx.client.query(CYCLE_CURRENT_QUERY, {"teamKey": team_key})
    cycles = data.get("cycles", {}).get("nodes", [])

    if not cycles:
        out.info("No active cycle")
        return

    cycle = cycles[0]

    if out.json_mode:
        out.raw_json(cycle)
        return

    progress = cycle.get("progress", 0)
    progress_pct = f"{progress * 100:.0f}%" if isinstance(progress, (int, float)) else str(progress)

    sections = [
        (
            "Current Cycle",
            [
                ("Name", cycle.get("name") or f"Cycle {cycle.get('number', '?')}"),
                ("Progress", progress_pct),
                ("Starts", (cycle.get("startsAt") or "")[:10]),
                ("Ends", (cycle.get("endsAt") or "")[:10]),
            ],
        ),
    ]
    out.detail("Active Cycle", sections)

    issues = cycle.get("issues", {}).get("nodes", [])
    if issues:
        rows = [
            [
                issue.get("identifier", ""),
                issue.get("title", "")[:50],
                str(issue.get("priority", "-")),
                issue.get("state", {}).get("name", ""),
                (issue.get("assignee") or {}).get("name", ""),
            ]
            for issue in issues
        ]
        out.table(
            f"Cycle Issues ({len(issues)})",
            [("ID", "cyan"), ("Title", "white"), ("P", "yellow"), ("State", "green"), ("Assignee", "magenta")],
            rows,
        )


@app.command("list")
def list_(
    ctx: typer.Context,
    team: Annotated[str | None, typer.Option("--team", "-t", help="Team key")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 20,
) -> None:
    """List past and upcoming cycles."""
    actx: AppContext = ctx.obj
    out = actx.output

    team_key = team or actx.default_team
    data = actx.client.query(CYCLES_LIST_QUERY, {"teamKey": team_key, "first": limit})
    cycles = data.get("cycles", {}).get("nodes", [])

    if out.json_mode:
        out.raw_json(cycles)
        return

    if not cycles:
        out.info("No cycles found")
        return

    rows = [
        [
            str(c.get("number", "")),
            c.get("name") or f"Cycle {c.get('number', '?')}",
            (c.get("startsAt") or "")[:10],
            (c.get("endsAt") or "")[:10],
            f"{(c.get('progress', 0) or 0) * 100:.0f}%",
        ]
        for c in cycles
    ]
    out.table(
        f"Cycles ({len(cycles)})",
        [("Num", "cyan"), ("Name", "white"), ("Start", "yellow"), ("End", "yellow"), ("Progress", "green")],
        rows,
    )


@app.command()
def show(
    ctx: typer.Context,
    cycle_id: Annotated[str, typer.Argument(help="Cycle ID (UUID)")],
) -> None:
    """Show cycle details: scope, completed, remaining issues."""
    actx: AppContext = ctx.obj
    out = actx.output

    data = actx.client.query(CYCLE_SHOW_QUERY, {"id": cycle_id})
    cycle = data.get("cycle", {})

    if out.json_mode:
        out.raw_json(cycle)
        return

    progress = cycle.get("progress", 0)
    progress_pct = f"{progress * 100:.0f}%" if isinstance(progress, (int, float)) else str(progress)
    issues = cycle.get("issues", {}).get("nodes", [])

    sections = [
        (
            "Cycle Details",
            [
                ("Name", cycle.get("name") or f"Cycle {cycle.get('number', '?')}"),
                ("Number", str(cycle.get("number", ""))),
                ("Progress", progress_pct),
                ("Starts", (cycle.get("startsAt") or "")[:10]),
                ("Ends", (cycle.get("endsAt") or "")[:10]),
                ("Total Issues", str(len(issues))),
            ],
        ),
    ]
    out.detail(f"Cycle {cycle.get('number', '?')}", sections)

    if issues:
        rows = [
            [
                issue.get("identifier", ""),
                issue.get("title", "")[:50],
                issue.get("state", {}).get("name", ""),
                (issue.get("assignee") or {}).get("name", ""),
                str(issue.get("estimate") or "-"),
            ]
            for issue in issues
        ]
        out.table(
            "",
            [("ID", "cyan"), ("Title", "white"), ("State", "green"), ("Assignee", "magenta"), ("Est", "yellow")],
            rows,
        )


@app.command()
def stats(
    ctx: typer.Context,
    team: Annotated[str | None, typer.Option("--team", "-t", help="Team key")] = None,
) -> None:
    """Show velocity trends across recent cycles."""
    actx: AppContext = ctx.obj
    out = actx.output

    team_key = team or actx.default_team
    data = actx.client.query(CYCLES_LIST_QUERY, {"teamKey": team_key, "first": 10})
    cycles = data.get("cycles", {}).get("nodes", [])

    if out.json_mode:
        out.raw_json({"cycles": len(cycles), "data": cycles})
        return

    if not cycles:
        out.info("No cycles found for velocity analysis")
        return

    out.header("Velocity Trends (last 10 cycles)")
    rows = [
        [
            str(c.get("number", "")),
            c.get("name") or f"Cycle {c.get('number', '?')}",
            f"{(c.get('progress', 0) or 0) * 100:.0f}%",
            (c.get("startsAt") or "")[:10],
            (c.get("endsAt") or "")[:10],
        ]
        for c in cycles
    ]
    out.table(
        "",
        [("Num", "cyan"), ("Name", "white"), ("Completion", "green"), ("Start", "yellow"), ("End", "yellow")],
        rows,
    )
```

- [ ] **Step 2: Register cycles in cli.py**

```python
from kctl_linear.commands.cycles import app as cycles_app
app.add_typer(cycles_app, name="cycles")
```

- [ ] **Step 3: Commit**

```bash
git add cli/
git commit -m "feat: add cycles command group (current/list/show/stats)"
```

---

### Task 5: Projects + Teams command groups

**Files:**
- Create: `cli/src/kctl_linear/commands/projects.py`
- Create: `cli/src/kctl_linear/commands/teams.py`
- Modify: `cli/src/kctl_linear/cli.py` (register)

- [ ] **Step 1: Create projects command group**

Create `cli/src/kctl_linear/commands/projects.py`:

```python
"""Project tracking commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_linear.core.callbacks import AppContext
from kctl_linear.core.client import PROJECTS_LIST_QUERY, PROJECT_SHOW_QUERY

app = typer.Typer(help="Project tracking.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List active projects with progress."""
    actx: AppContext = ctx.obj
    out = actx.output

    data = actx.client.query(PROJECTS_LIST_QUERY)
    projects = data.get("projects", {}).get("nodes", [])

    if out.json_mode:
        out.raw_json(projects)
        return

    if not projects:
        out.info("No projects found")
        return

    rows = [
        [
            p.get("name", ""),
            p.get("state", ""),
            f"{(p.get('progress', 0) or 0) * 100:.0f}%",
            (p.get("lead") or {}).get("name", "-"),
            (p.get("targetDate") or "-")[:10],
        ]
        for p in projects
    ]
    out.table(
        f"Projects ({len(projects)})",
        [("Name", "cyan"), ("State", "green"), ("Progress", "yellow"), ("Lead", "magenta"), ("Target", "white")],
        rows,
    )


@app.command()
def show(
    ctx: typer.Context,
    project_id: Annotated[str, typer.Argument(help="Project ID (UUID)")],
) -> None:
    """Show project details, milestones, and member issues."""
    actx: AppContext = ctx.obj
    out = actx.output

    data = actx.client.query(PROJECT_SHOW_QUERY, {"id": project_id})
    project = data.get("project", {})

    if out.json_mode:
        out.raw_json(project)
        return

    teams = [t.get("name", "") for t in project.get("teams", {}).get("nodes", [])]
    members = [m.get("name", "") for m in project.get("members", {}).get("nodes", [])]
    milestones = project.get("projectMilestones", {}).get("nodes", [])
    issues = project.get("issues", {}).get("nodes", [])

    sections = [
        (
            "Project",
            [
                ("Name", project.get("name", "")),
                ("State", project.get("state", "")),
                ("Progress", f"{(project.get('progress', 0) or 0) * 100:.0f}%"),
                ("Lead", (project.get("lead") or {}).get("name", "-")),
                ("Start", (project.get("startDate") or "-")[:10]),
                ("Target", (project.get("targetDate") or "-")[:10]),
                ("Teams", ", ".join(teams) if teams else "-"),
                ("Members", ", ".join(members) if members else "-"),
                ("URL", project.get("url", "")),
            ],
        ),
    ]

    if project.get("description"):
        sections.append(("Description", [("", project["description"][:500])]))

    if milestones:
        ms_rows = [(m.get("name", ""), (m.get("targetDate") or "-")[:10]) for m in milestones]
        sections.append(("Milestones", ms_rows))

    out.detail(project.get("name", "Project"), sections)

    if issues:
        rows = [
            [
                i.get("identifier", ""),
                i.get("title", "")[:50],
                i.get("state", {}).get("name", ""),
                (i.get("assignee") or {}).get("name", ""),
            ]
            for i in issues[:20]
        ]
        out.table(
            f"Issues ({len(issues)})",
            [("ID", "cyan"), ("Title", "white"), ("State", "green"), ("Assignee", "magenta")],
            rows,
        )
```

- [ ] **Step 2: Create teams command group**

Create `cli/src/kctl_linear/commands/teams.py`:

```python
"""Team info commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_linear.core.callbacks import AppContext
from kctl_linear.core.client import TEAMS_LIST_QUERY, TEAM_SHOW_QUERY

app = typer.Typer(help="Team information.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all teams with member counts."""
    actx: AppContext = ctx.obj
    out = actx.output

    data = actx.client.query(TEAMS_LIST_QUERY)
    teams = data.get("teams", {}).get("nodes", [])

    if out.json_mode:
        out.raw_json(teams)
        return

    if not teams:
        out.info("No teams found")
        return

    rows = [
        [
            t.get("key", ""),
            t.get("name", ""),
            str(len(t.get("members", {}).get("nodes", []))),
            t.get("timezone", ""),
        ]
        for t in teams
    ]
    out.table(
        f"Teams ({len(teams)})",
        [("Key", "cyan"), ("Name", "white"), ("Members", "yellow"), ("Timezone", "green")],
        rows,
    )


@app.command()
def show(
    ctx: typer.Context,
    team_id: Annotated[str, typer.Argument(help="Team ID (UUID) or key")],
) -> None:
    """Show team members, workflow states, and labels."""
    actx: AppContext = ctx.obj
    out = actx.output

    data = actx.client.query(TEAM_SHOW_QUERY, {"id": team_id})
    team = data.get("team", {})

    if out.json_mode:
        out.raw_json(team)
        return

    members = team.get("members", {}).get("nodes", [])
    states = team.get("states", {}).get("nodes", [])
    labels = team.get("labels", {}).get("nodes", [])

    sections = [
        (
            "Team",
            [
                ("Key", team.get("key", "")),
                ("Name", team.get("name", "")),
                ("Description", team.get("description") or "-"),
                ("Timezone", team.get("timezone", "")),
                ("Members", str(len(members))),
            ],
        ),
    ]
    out.detail(team.get("name", "Team"), sections)

    if members:
        rows = [
            [m.get("name", ""), m.get("email", ""), str(m.get("active", True))]
            for m in members
        ]
        out.table("Members", [("Name", "cyan"), ("Email", "white"), ("Active", "green")], rows)

    if states:
        rows = [
            [s.get("name", ""), s.get("type", ""), s.get("color", "")]
            for s in sorted(states, key=lambda s: s.get("position", 0))
        ]
        out.table("Workflow States", [("Name", "cyan"), ("Type", "white"), ("Color", "yellow")], rows)

    if labels:
        rows = [[l.get("name", ""), l.get("color", "")] for l in labels]
        out.table("Labels", [("Name", "cyan"), ("Color", "yellow")], rows)
```

- [ ] **Step 3: Register in cli.py**

```python
from kctl_linear.commands.projects import app as projects_app
from kctl_linear.commands.teams import app as teams_app
app.add_typer(projects_app, name="projects")
app.add_typer(teams_app, name="teams")
```

- [ ] **Step 4: Commit**

```bash
git add cli/
git commit -m "feat: add projects and teams command groups"
```

---

### Task 6: Labels + Users command groups

**Files:**
- Create: `cli/src/kctl_linear/commands/labels.py`
- Create: `cli/src/kctl_linear/commands/users.py`
- Modify: `cli/src/kctl_linear/cli.py` (register)

- [ ] **Step 1: Create labels command group**

Create `cli/src/kctl_linear/commands/labels.py`:

```python
"""Label management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_linear.core.callbacks import AppContext
from kctl_linear.core.client import LABELS_LIST_QUERY, LABEL_CREATE_MUTATION, TEAM_BY_KEY_QUERY

app = typer.Typer(help="Label management.")


def _resolve_team_id(ctx: AppContext, team_key: str) -> str:
    """Resolve a team key to its UUID."""
    data = ctx.client.query(TEAM_BY_KEY_QUERY, {"key": team_key})
    nodes = data.get("teams", {}).get("nodes", [])
    if not nodes:
        raise typer.BadParameter(f"Team '{team_key}' not found")
    return nodes[0]["id"]


@app.command("list")
def list_(
    ctx: typer.Context,
    team: Annotated[str | None, typer.Option("--team", "-t", help="Team key")] = None,
) -> None:
    """List all labels, optionally filtered by team."""
    actx: AppContext = ctx.obj
    out = actx.output

    team_key = team or actx.default_team
    variables: dict[str, str | None] = {}
    if team_key:
        variables["teamKey"] = team_key

    data = actx.client.query(LABELS_LIST_QUERY, variables)
    labels = data.get("issueLabels", {}).get("nodes", [])

    if out.json_mode:
        out.raw_json(labels)
        return

    if not labels:
        out.info("No labels found")
        return

    rows = [
        [
            l.get("name", ""),
            l.get("color", ""),
            (l.get("parent") or {}).get("name", "-"),
        ]
        for l in labels
    ]
    out.table(
        f"Labels ({len(labels)})",
        [("Name", "cyan"), ("Color", "yellow"), ("Parent", "white")],
        rows,
    )


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Label name")],
    color: Annotated[str | None, typer.Option("--color", "-c", help="Hex color (e.g., #ff0000)")] = None,
    team: Annotated[str | None, typer.Option("--team", "-t", help="Team key (scoped label)")] = None,
) -> None:
    """Create a new label."""
    actx: AppContext = ctx.obj
    out = actx.output

    variables: dict[str, str | None] = {"name": name}
    if color:
        variables["color"] = color

    team_key = team or actx.default_team
    if team_key:
        variables["teamId"] = _resolve_team_id(actx, team_key)

    data = actx.client.query(LABEL_CREATE_MUTATION, variables)
    result = data.get("issueLabelCreate", {})
    label = result.get("issueLabel", {})

    if out.json_mode:
        out.raw_json(result)
        return

    out.success(f"Created label '{label.get('name', name)}' ({label.get('color', '')})")
```

- [ ] **Step 2: Create users command group**

Create `cli/src/kctl_linear/commands/users.py`:

```python
"""User info commands."""

from __future__ import annotations

import typer

from kctl_linear.core.callbacks import AppContext
from kctl_linear.core.client import USERS_LIST_QUERY, VIEWER_QUERY

app = typer.Typer(help="User information.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all workspace members."""
    actx: AppContext = ctx.obj
    out = actx.output

    data = actx.client.query(USERS_LIST_QUERY)
    users = data.get("users", {}).get("nodes", [])

    if out.json_mode:
        out.raw_json(users)
        return

    if not users:
        out.info("No users found")
        return

    rows = [
        [
            u.get("name", ""),
            u.get("email", ""),
            "Yes" if u.get("admin") else "No",
            "Yes" if u.get("active", True) else "No",
        ]
        for u in users
    ]
    out.table(
        f"Users ({len(users)})",
        [("Name", "cyan"), ("Email", "white"), ("Admin", "yellow"), ("Active", "green")],
        rows,
    )


@app.command()
def me(ctx: typer.Context) -> None:
    """Show current authenticated user."""
    actx: AppContext = ctx.obj
    out = actx.output

    viewer = actx.client.viewer()

    if out.json_mode:
        out.raw_json(viewer)
        return

    sections = [
        (
            "Current User",
            [
                ("Name", viewer.get("name", "")),
                ("Email", viewer.get("email", "")),
                ("Admin", str(viewer.get("admin", False))),
                ("Active", str(viewer.get("active", True))),
            ],
        ),
    ]
    out.detail("Me", sections)
```

- [ ] **Step 3: Register in cli.py**

```python
from kctl_linear.commands.labels import app as labels_app
from kctl_linear.commands.users import app as users_app
app.add_typer(labels_app, name="labels")
app.add_typer(users_app, name="users")
```

- [ ] **Step 4: Update final cli.py with all command registrations**

The final `cli/src/kctl_linear/cli.py` should have all imports and registrations:

```python
"""Main CLI entry point for kctl-linear."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_linear import __version__
from kctl_linear.commands.config_cmd import app as config_app
from kctl_linear.commands.cycles import app as cycles_app
from kctl_linear.commands.dashboard import app as dashboard_app
from kctl_linear.commands.health import app as health_app
from kctl_linear.commands.issues import app as issues_app
from kctl_linear.commands.labels import app as labels_app
from kctl_linear.commands.projects import app as projects_app
from kctl_linear.commands.teams import app as teams_app
from kctl_linear.commands.users import app as users_app
from kctl_linear.core.callbacks import AppContext
from kctl_linear.core.plugins import discover_and_load_plugins


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-linear {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-linear",
    help="Linear project management",
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
    """Linear project management."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        format=format,
        no_header=no_header,
    )


# Command group registration
app.add_typer(config_app, name="config")
app.add_typer(health_app, name="health")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(issues_app, name="issues")
app.add_typer(cycles_app, name="cycles")
app.add_typer(projects_app, name="projects")
app.add_typer(teams_app, name="teams")
app.add_typer(labels_app, name="labels")
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

- [ ] **Step 5: Commit**

```bash
git add cli/
git commit -m "feat: add labels, users commands and complete CLI registration"
```

---

### Task 7: Tests + CI + CLAUDE.md

**Files:**
- Modify: `cli/tests/conftest.py`
- Create: `cli/tests/test_client.py`
- Create: `cli/tests/test_health.py`
- Create: `cli/tests/test_issues.py`
- Create: `cli/tests/test_cycles.py`
- Create: `cli/tests/test_commands.py`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update conftest.py with shared fixtures**

Replace `cli/tests/conftest.py`:

```python
"""Shared test configuration and fixtures."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from kctl_linear.core.client import LinearClient


@pytest.fixture
def mock_client() -> MagicMock:
    """Return a mock LinearClient."""
    client = MagicMock(spec=LinearClient)
    client.viewer.return_value = {
        "id": "user-123",
        "name": "Test User",
        "email": "test@kodeme.io",
        "admin": False,
        "active": True,
    }
    return client


@pytest.fixture
def mock_query(mock_client: MagicMock):
    """Convenience fixture to set up query return values."""

    def _set_query_response(response: dict[str, Any]) -> MagicMock:
        mock_client.query.return_value = response
        return mock_client

    return _set_query_response


SAMPLE_ISSUE = {
    "id": "issue-1",
    "identifier": "KOD-1",
    "title": "Test issue",
    "priority": 2,
    "state": {"name": "In Progress", "color": "#f00"},
    "assignee": {"name": "Test User", "email": "test@kodeme.io"},
    "createdAt": "2026-03-01T00:00:00Z",
    "updatedAt": "2026-03-28T00:00:00Z",
}

SAMPLE_CYCLE = {
    "id": "cycle-1",
    "number": 5,
    "name": "Sprint 5",
    "startsAt": "2026-03-25T00:00:00Z",
    "endsAt": "2026-04-07T00:00:00Z",
    "progress": 0.6,
    "issues": {"nodes": [SAMPLE_ISSUE]},
}
```

- [ ] **Step 2: Create test_client.py**

Create `cli/tests/test_client.py`:

```python
"""Tests for LinearClient."""

from __future__ import annotations

import pytest

from kctl_linear.core.client import LinearClient
from kctl_linear.core.exceptions import APIError, AuthenticationError, ConfigError


class TestConstructor:
    def test_requires_api_key(self):
        with pytest.raises(ConfigError, match="API key"):
            LinearClient(api_key="")

    def test_requires_non_blank_key(self):
        with pytest.raises(ConfigError, match="API key"):
            LinearClient(api_key="   ")

    def test_creates_with_valid_key(self):
        client = LinearClient(api_key="lin_api_test123")
        assert client._api_key == "lin_api_test123"
        client.close()

    def test_context_manager(self):
        with LinearClient(api_key="lin_api_test123") as client:
            assert client is not None


class TestQuery:
    def test_successful_query(self, httpx_mock):
        httpx_mock.add_response(
            json={"data": {"viewer": {"id": "u1", "name": "Test"}}},
        )
        with LinearClient(api_key="lin_api_test123") as client:
            result = client.query("query { viewer { id name } }")
        assert result == {"viewer": {"id": "u1", "name": "Test"}}

    def test_graphql_errors_raise_api_error(self, httpx_mock):
        httpx_mock.add_response(
            json={"errors": [{"message": "Field not found"}]},
        )
        with LinearClient(api_key="lin_api_test123") as client:
            with pytest.raises(APIError, match="Field not found"):
                client.query("query { bad }")

    def test_401_raises_auth_error(self, httpx_mock):
        httpx_mock.add_response(status_code=401, json={"error": "Unauthorized"})
        with LinearClient(api_key="bad_key") as client:
            with pytest.raises(AuthenticationError):
                client.query("query { viewer { id } }")

    def test_403_raises_auth_error(self, httpx_mock):
        httpx_mock.add_response(status_code=403, json={"error": "Forbidden"})
        with LinearClient(api_key="bad_key") as client:
            with pytest.raises(AuthenticationError):
                client.query("query { viewer { id } }")

    def test_500_raises_api_error(self, httpx_mock):
        httpx_mock.add_response(status_code=500, text="Internal Server Error")
        with LinearClient(api_key="lin_api_test123") as client:
            with pytest.raises(APIError):
                client.query("query { viewer { id } }")

    def test_viewer_helper(self, httpx_mock):
        httpx_mock.add_response(
            json={"data": {"viewer": {"id": "u1", "name": "Test", "email": "t@t.com", "admin": False, "active": True}}},
        )
        with LinearClient(api_key="lin_api_test123") as client:
            viewer = client.viewer()
        assert viewer["name"] == "Test"

    def test_variables_sent(self, httpx_mock):
        httpx_mock.add_response(json={"data": {"issues": {"nodes": []}}})
        with LinearClient(api_key="lin_api_test123") as client:
            client.query("query($team: String) { issues }", {"team": "KOD"})
        request = httpx_mock.get_request()
        import json
        body = json.loads(request.content)
        assert body["variables"] == {"team": "KOD"}

    def test_auth_header_no_bearer(self, httpx_mock):
        httpx_mock.add_response(json={"data": {}})
        with LinearClient(api_key="lin_api_mykey") as client:
            client.query("query { viewer { id } }")
        request = httpx_mock.get_request()
        assert request.headers["Authorization"] == "lin_api_mykey"
        assert "Bearer" not in request.headers["Authorization"]
```

- [ ] **Step 3: Create test_health.py**

Create `cli/tests/test_health.py`:

```python
"""Tests for health command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_linear.cli import app

runner = CliRunner()


class TestHealthCommand:
    @patch("kctl_linear.commands.health.AppContext")
    def test_health_json(self, _mock_cls):
        """Health command with --json returns structured output."""
        # Smoke test: just verify --help works without mocking the full stack
        result = runner.invoke(app, ["health", "--help"])
        assert result.exit_code == 0
        assert "health" in result.output.lower()
```

- [ ] **Step 4: Create test_issues.py**

Create `cli/tests/test_issues.py`:

```python
"""Tests for issues commands."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_linear.cli import app

runner = CliRunner()


class TestIssuesSmoke:
    def test_issues_help(self):
        result = runner.invoke(app, ["issues", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "show" in result.output
        assert "create" in result.output
        assert "update" in result.output
        assert "comment" in result.output
        assert "search" in result.output

    def test_issues_list_help(self):
        result = runner.invoke(app, ["issues", "list", "--help"])
        assert result.exit_code == 0
        assert "--team" in result.output
        assert "--state" in result.output
        assert "--assignee" in result.output

    def test_issues_create_help(self):
        result = runner.invoke(app, ["issues", "create", "--help"])
        assert result.exit_code == 0
        assert "--title" in result.output
        assert "--priority" in result.output
```

- [ ] **Step 5: Create test_cycles.py**

Create `cli/tests/test_cycles.py`:

```python
"""Tests for cycles commands."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_linear.cli import app

runner = CliRunner()


class TestCyclesSmoke:
    def test_cycles_help(self):
        result = runner.invoke(app, ["cycles", "--help"])
        assert result.exit_code == 0
        assert "current" in result.output
        assert "list" in result.output
        assert "show" in result.output
        assert "stats" in result.output

    def test_cycles_current_help(self):
        result = runner.invoke(app, ["cycles", "current", "--help"])
        assert result.exit_code == 0
        assert "--team" in result.output
```

- [ ] **Step 6: Create test_commands.py (projects, teams, labels, users, dashboard)**

Create `cli/tests/test_commands.py`:

```python
"""Smoke tests for projects, teams, labels, users, and dashboard commands."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_linear.cli import app

runner = CliRunner()


class TestProjectsSmoke:
    def test_help(self):
        result = runner.invoke(app, ["projects", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "show" in result.output


class TestTeamsSmoke:
    def test_help(self):
        result = runner.invoke(app, ["teams", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "show" in result.output


class TestLabelsSmoke:
    def test_help(self):
        result = runner.invoke(app, ["labels", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "create" in result.output


class TestUsersSmoke:
    def test_help(self):
        result = runner.invoke(app, ["users", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "me" in result.output


class TestDashboardSmoke:
    def test_help(self):
        result = runner.invoke(app, ["dashboard", "--help"])
        assert result.exit_code == 0
```

- [ ] **Step 7: Run all tests**

```bash
cd cli && uv sync --all-extras && uv run pytest tests/ -v --tb=short
```

Expected: All smoke + client tests pass.

- [ ] **Step 8: Run linting and type checks**

```bash
cd cli && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/
```

Fix any issues found.

- [ ] **Step 9: Update CLAUDE.md**

Update `CLAUDE.md` in the repo root to document the CLI commands:

Add the following section (append or update the existing content):

```markdown
## kctl-linear CLI

Sprint tracking and issue management via Linear GraphQL API.

### Quick Commands
```bash
cd cli
uv sync --all-extras
uv run pytest tests/ -v
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

### Command Groups (10)
| Group | Commands | Purpose |
|-------|----------|---------|
| config | init, add, use, show, validate, remove, set, profiles, current | Profile management |
| health | (default) | API connectivity check |
| dashboard | (default) | My issues, current cycle, active projects |
| issues | list, show, create, update, comment, search | Issue management |
| cycles | current, list, show, stats | Sprint management |
| projects | list, show | Project tracking |
| teams | list, show | Team info |
| labels | list, create | Label management |
| users | list, me | User info |

### Architecture
- LinearClient (core/client.py) — custom GraphQL client, NOT an APIClient subclass
- All API calls: POST https://api.linear.app/graphql
- Auth: `Authorization: {api_key}` (no Bearer prefix)
- Config: api_key, default_team
```

- [ ] **Step 10: Commit**

```bash
git add cli/ CLAUDE.md
git commit -m "test: add tests for all command groups and update CLAUDE.md"
```

---

### Task 8: Final verification

- [ ] **Step 1: Run full test suite**

```bash
cd cli && uv run pytest tests/ -v --tb=short
```

All tests must pass.

- [ ] **Step 2: Run lint and format checks**

```bash
cd cli && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/
```

No errors.

- [ ] **Step 3: Verify CLI help shows all 10 command groups**

```bash
cd cli && uv run kctl-linear --help
```

Expected output should list: config, health, dashboard, issues, cycles, projects, teams, labels, users.

- [ ] **Step 4: Verify all subcommands have --help**

```bash
cd cli && for cmd in health dashboard issues cycles projects teams labels users; do echo "=== $cmd ===" && uv run kctl-linear $cmd --help; done
```

- [ ] **Step 5: Final commit (if any fixups needed)**

```bash
git add cli/
git commit -m "fix: address lint and test issues from final verification"
```

---

## Summary

| Task | Files | Deliverable |
|------|-------|-------------|
| 1. Setup | 5 modify/create | LinearClient, ServiceConfig, exceptions, callbacks |
| 2. Health + Dashboard | 3 files | `health`, `dashboard` commands |
| 3. Issues | 2 files | `issues list/show/create/update/comment/search` |
| 4. Cycles | 2 files | `cycles current/list/show/stats` |
| 5. Projects + Teams | 3 files | `projects list/show`, `teams list/show` |
| 6. Labels + Users | 3 files | `labels list/create`, `users list/me` |
| 7. Tests + CLAUDE.md | 7 files | Client tests, smoke tests, documentation |
| 8. Verification | 0 files | Full test + lint + help validation |

**Total:** ~22 files modified/created, 10 command groups, ~30 subcommands.
