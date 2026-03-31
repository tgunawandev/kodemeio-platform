# kctl-github Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build kctl-github CLI with 10 command groups for cross-repo management of 21 kodemeio-* repositories.

**Architecture:** Python CLI using kctl-lib v0.4.0. GitHubClient subclasses APIClient for REST API. Also uses `gh` CLI subprocess for some operations. Key value: aggregation across multiple repos.

**Tech Stack:** Python 3.12+, kctl-lib>=0.4.0, Typer, httpx, Rich, gh CLI

**Spec:** `docs/superpowers/specs/2026-03-29-kctl-service-clis-design.md` (Section 4: kctl-github)

**Working directory:** `/home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-github`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `cli/src/kctl_github/core/config.py` | ServiceConfig with token, organization, repo_prefix |
| Modify | `cli/src/kctl_github/core/exceptions.py` | Add APIError, ConnectionError, AuthenticationError |
| Create | `cli/src/kctl_github/core/client.py` | GitHubClient(APIClient) + gh_run() helper |
| Modify | `cli/src/kctl_github/core/callbacks.py` | Add lazy client property to AppContext |
| Modify | `cli/src/kctl_github/cli.py` | Register all 10 command groups |
| Modify | `cli/src/kctl_github/commands/config_cmd.py` | Update init/validate for new ServiceConfig fields |
| Create | `cli/src/kctl_github/commands/health.py` | API check + rate limits |
| Create | `cli/src/kctl_github/commands/dashboard.py` | Quick overview (repos, PRs, CI, billing) |
| Create | `cli/src/kctl_github/commands/repos.py` | list/status/show across kodemeio-* repos |
| Create | `cli/src/kctl_github/commands/ci.py` | CI status/show/stats/rerun/bulk-status |
| Create | `cli/src/kctl_github/commands/prs.py` | Cross-repo PR list/show/stale |
| Create | `cli/src/kctl_github/commands/secrets.py` | Secret list/audit/set/rotate |
| Create | `cli/src/kctl_github/commands/labels.py` | Label list/sync/diff |
| Create | `cli/src/kctl_github/commands/stats.py` | overview/activity/languages/contributors |
| Create | `cli/src/kctl_github/commands/billing.py` | actions/storage/packages/overview |
| Create | `cli/tests/test_client.py` | GitHubClient unit tests |
| Create | `cli/tests/test_health.py` | Health command tests |
| Create | `cli/tests/test_repos.py` | Repos command tests |
| Create | `cli/tests/test_ci.py` | CI command tests |
| Create | `cli/tests/test_prs.py` | PRs command tests |
| Create | `cli/tests/test_stats.py` | Stats command tests |
| Create | `cli/tests/test_billing.py` | Billing command tests |
| Create | `cli/tests/test_dashboard.py` | Dashboard command tests |
| Modify | `cli/tests/test_smoke.py` | Add smoke tests for all command groups |
| Modify | `cli/pyproject.toml` | Add pytest-httpx to dev deps |
| Modify | `CLAUDE.md` | Update with CLI documentation |

---

### Task 1: Core infrastructure -- client, config, exceptions, callbacks

**Files:**
- Modify: `cli/src/kctl_github/core/config.py`
- Modify: `cli/src/kctl_github/core/exceptions.py`
- Create: `cli/src/kctl_github/core/client.py`
- Modify: `cli/src/kctl_github/core/callbacks.py`
- Modify: `cli/pyproject.toml`

- [ ] **Step 1: Update pyproject.toml -- add pytest-httpx to dev deps**

In `cli/pyproject.toml`, add `pytest-httpx` to dev deps:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-httpx>=0.35.0",
    "ruff>=0.9.0",
    "mypy>=1.14.0",
    "types-PyYAML>=6.0.0",
]
```

- [ ] **Step 2: Update ServiceConfig with GitHub-specific fields**

Replace the entire `ServiceConfig` class and update `validate` logic in `cli/src/kctl_github/core/config.py`:

```python
class ServiceConfig(BaseModel):
    """Service-specific config within a profile."""

    token: str = ""                    # GitHub Personal Access Token
    organization: str = "tgunawandev"  # GitHub org or username
    repo_prefix: str = "kodemeio-"     # Filter repos by this prefix
```

Update `init` function's `typer.prompt` calls in `config_cmd.py` accordingly (Task 1, Step 6).

- [ ] **Step 3: Update exceptions.py -- add API-related exceptions**

Replace `cli/src/kctl_github/core/exceptions.py` with:

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

- [ ] **Step 4: Create client.py -- GitHubClient + gh_run helper**

Create `cli/src/kctl_github/core/client.py`:

```python
"""GitHub API client and gh CLI helper."""

from __future__ import annotations

from typing import Any

from kctl_lib.api_client import APIClient
from kctl_lib.runner import run


class GitHubClient(APIClient):
    """Synchronous GitHub REST API client.

    Subclasses APIClient with GitHub-specific defaults.
    Provides helpers for paginated listing and repo filtering.
    """

    BASE_URL = "https://api.github.com"
    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"

    def __init__(
        self,
        credential: str = "",
        organization: str = "tgunawandev",
        repo_prefix: str = "kodemeio-",
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(credential=credential, timeout=timeout, **kwargs)
        self._organization = organization
        self._repo_prefix = repo_prefix
        # Add Accept header for GitHub API v3
        self._client.headers["Accept"] = "application/vnd.github+json"
        self._client.headers["X-GitHub-Api-Version"] = "2022-11-28"

    # ------------------------------------------------------------------
    # Pagination helper
    # ------------------------------------------------------------------

    def get_paginated(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch all pages from a paginated GitHub endpoint.

        GitHub uses Link headers for pagination. This method follows
        `next` links up to max_pages.
        """
        all_items: list[dict[str, Any]] = []
        _params = dict(params or {})
        _params.setdefault("per_page", 100)

        for _ in range(max_pages):
            response = self._request("GET", endpoint, params=_params)
            data = response.json()
            if isinstance(data, list):
                all_items.extend(data)
            else:
                # Some endpoints return objects with items inside
                break

            # Check for next page via Link header
            link = response.headers.get("link", "")
            if 'rel="next"' not in link:
                break

            # Parse next URL from Link header
            next_url = _parse_next_link(link)
            if not next_url:
                break

            # For subsequent requests, use the full URL
            # Extract query params from the next URL
            from urllib.parse import parse_qs, urlparse

            parsed = urlparse(next_url)
            _params = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        return all_items

    # ------------------------------------------------------------------
    # Repo helpers
    # ------------------------------------------------------------------

    def get_repos(self) -> list[dict[str, Any]]:
        """Get all repos matching the configured prefix."""
        repos = self.get_paginated(f"/users/{self._organization}/repos")
        return [
            r for r in repos
            if r.get("name", "").startswith(self._repo_prefix)
        ]

    def get_repo(self, name: str) -> dict[str, Any]:
        """Get a single repo by name (short name, not full_name)."""
        return self.get(f"/repos/{self._organization}/{name}")

    @property
    def organization(self) -> str:
        return self._organization

    @property
    def repo_prefix(self) -> str:
        return self._repo_prefix


def _parse_next_link(link_header: str) -> str | None:
    """Parse the 'next' URL from a GitHub Link header."""
    for part in link_header.split(","):
        if 'rel="next"' in part:
            url = part.split(";")[0].strip().strip("<>")
            return url
    return None


def gh_run(args: list[str], check: bool = True) -> str:
    """Run a gh CLI command and return stdout.

    Args:
        args: Arguments to pass to `gh` (e.g., ["pr", "view", "123"]).
        check: If True, raise CommandError on non-zero exit.

    Returns:
        The stdout output as a string.
    """
    result = run(["gh", *args], check=check)
    return result.stdout.strip()
```

- [ ] **Step 5: Update callbacks.py -- add lazy client property**

Replace `cli/src/kctl_github/core/callbacks.py`:

```python
"""Application context for kctl-github."""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_lib.callbacks import AppContextBase

from kctl_github.core.client import GitHubClient
from kctl_github.core.config import (
    ServiceConfig,
    get_service_config,
    resolve_active_profile_name,
)


@dataclass
class AppContext(AppContextBase):
    """kctl-github application context."""

    _client: GitHubClient | None = field(default=None, repr=False)

    @property
    def client(self) -> GitHubClient:
        """Lazy-initialize GitHub API client from active profile config."""
        if self._client is None:
            profile = resolve_active_profile_name(self.profile)
            cfg = get_service_config(profile)
            self._client = GitHubClient(
                credential=cfg.token,
                organization=cfg.organization,
                repo_prefix=cfg.repo_prefix,
            )
        return self._client

    @property
    def config(self) -> ServiceConfig:
        """Get the resolved service config."""
        profile = resolve_active_profile_name(self.profile)
        return get_service_config(profile)
```

- [ ] **Step 6: Update config_cmd.py for new ServiceConfig fields**

In `cli/src/kctl_github/commands/config_cmd.py`, update the `init` command:

```python
@app.command()
def init(ctx: typer.Context) -> None:
    """Interactive config setup."""
    actx: AppContext = ctx.obj
    out = actx.output
    profile_name = typer.prompt("Profile name", default="default")
    token = typer.prompt("GitHub token (PAT)", default="", hide_input=True)
    organization = typer.prompt("GitHub organization/user", default="tgunawandev")
    repo_prefix = typer.prompt("Repository prefix filter", default="kodemeio-")
    svc = ServiceConfig(token=token, organization=organization, repo_prefix=repo_prefix)
    set_service_config(profile_name, svc)
    set_default_profile(profile_name)
    out.success(f"Config saved to profile '{profile_name}'")
```

Update the `add` command similarly (prompt for token, organization, repo_prefix instead of url).

Update the `validate` command to check `token` instead of `url`:

```python
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
    if not svc.organization:
        issues.append("organization is not set")
    if out.json_mode:
        out.raw_json({"profile": active, "valid": len(issues) == 0, "issues": issues})
        return
    if issues:
        out.error(f"Profile '{active}' has {len(issues)} issue(s):")
        for issue in issues:
            out.text(f"  - {issue}")
        raise typer.Exit(1)
    out.success(f"Profile '{active}' is valid")
```

- [ ] **Step 7: Sync and verify scaffold still builds**

```bash
cd cli && uv sync --all-extras && uv run pytest tests/ -v --tb=short
```

Expected: Smoke tests pass. No import errors.

- [ ] **Step 8: Commit**

```bash
git add cli/src/kctl_github/core/ cli/src/kctl_github/commands/config_cmd.py cli/pyproject.toml
git commit -m "feat: add GitHubClient, ServiceConfig, and core infrastructure

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: health + dashboard commands

**Files:**
- Create: `cli/src/kctl_github/commands/health.py`
- Create: `cli/src/kctl_github/commands/dashboard.py`
- Modify: `cli/src/kctl_github/cli.py`

- [ ] **Step 1: Create health.py**

Create `cli/src/kctl_github/commands/health.py`:

```python
"""Health check commands."""

from __future__ import annotations

import typer

from kctl_github.core.callbacks import AppContext

app = typer.Typer(help="API connectivity and rate limits.")


@app.callback(invoke_without_command=True)
def health(ctx: typer.Context) -> None:
    """Check GitHub API reachability, rate limits, and token scopes."""
    if ctx.invoked_subcommand is not None:
        return

    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    # Check rate limits
    rate = client.get("/rate_limit")
    core = rate.get("resources", {}).get("core", {})
    search = rate.get("resources", {}).get("search", {})

    # Get authenticated user info
    user = client.get("/user")

    if out.json_mode:
        out.raw_json({
            "status": "healthy",
            "user": user.get("login"),
            "rate_limit": {
                "core_remaining": core.get("remaining"),
                "core_limit": core.get("limit"),
                "search_remaining": search.get("remaining"),
                "search_limit": search.get("limit"),
            },
        })
        return

    out.success("GitHub API is reachable")
    sections = [
        ("Connection", [
            ("User", user.get("login", "unknown")),
            ("Name", user.get("name", "")),
            ("Plan", user.get("plan", {}).get("name", "unknown")),
        ]),
        ("Rate Limits", [
            ("Core", f"{core.get('remaining', '?')}/{core.get('limit', '?')}"),
            ("Search", f"{search.get('remaining', '?')}/{search.get('limit', '?')}"),
        ]),
    ]
    out.detail("GitHub Health", sections)
```

- [ ] **Step 2: Create dashboard.py**

Create `cli/src/kctl_github/commands/dashboard.py`:

```python
"""Dashboard -- quick overview command."""

from __future__ import annotations

from datetime import datetime, timezone

import typer

from kctl_github.core.callbacks import AppContext

app = typer.Typer(help="Quick overview dashboard.")


@app.callback(invoke_without_command=True)
def dashboard(ctx: typer.Context) -> None:
    """Show repos count, open PRs, failing CI, rate limits summary."""
    if ctx.invoked_subcommand is not None:
        return

    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    # Get repos
    repos = client.get_repos()
    repo_count = len(repos)

    # Count open PRs across repos
    total_open_prs = 0
    failing_ci = 0
    for repo in repos:
        name = repo["name"]
        # Get open PRs
        prs = client.get(
            f"/repos/{client.organization}/{name}/pulls",
            params={"state": "open", "per_page": 100},
        )
        if isinstance(prs, list):
            total_open_prs += len(prs)

        # Get latest workflow run
        runs = client.get(
            f"/repos/{client.organization}/{name}/actions/runs",
            params={"per_page": 1},
        )
        workflow_runs = runs.get("workflow_runs", [])
        if workflow_runs and workflow_runs[0].get("conclusion") == "failure":
            failing_ci += 1

    # Rate limits
    rate = client.get("/rate_limit")
    core = rate.get("resources", {}).get("core", {})

    if out.json_mode:
        out.raw_json({
            "repos": repo_count,
            "open_prs": total_open_prs,
            "failing_ci": failing_ci,
            "rate_limit_remaining": core.get("remaining"),
        })
        return

    sections = [
        ("Repositories", [
            ("Total kodemeio-* repos", str(repo_count)),
        ]),
        ("Pull Requests", [
            ("Open PRs (all repos)", str(total_open_prs)),
        ]),
        ("CI/CD", [
            ("Repos with failing CI", str(failing_ci)),
        ]),
        ("API", [
            ("Rate limit remaining", f"{core.get('remaining', '?')}/{core.get('limit', '?')}"),
        ]),
    ]
    out.detail("GitHub Dashboard", sections)
```

- [ ] **Step 3: Register health and dashboard in cli.py**

Add imports and register in `cli/src/kctl_github/cli.py`:

```python
from kctl_github.commands.health import app as health_app
from kctl_github.commands.dashboard import app as dashboard_app

# After config registration:
app.add_typer(health_app, name="health")
app.add_typer(dashboard_app, name="dashboard")
```

- [ ] **Step 4: Verify help output**

```bash
cd cli && uv run kctl-github --help
uv run kctl-github health --help
uv run kctl-github dashboard --help
```

- [ ] **Step 5: Commit**

```bash
git add cli/src/kctl_github/commands/health.py cli/src/kctl_github/commands/dashboard.py cli/src/kctl_github/cli.py
git commit -m "feat: add health and dashboard commands

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: repos command group

**Files:**
- Create: `cli/src/kctl_github/commands/repos.py`
- Modify: `cli/src/kctl_github/cli.py`

- [ ] **Step 1: Create repos.py**

Create `cli/src/kctl_github/commands/repos.py`:

```python
"""Cross-repo overview commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_github.core.callbacks import AppContext

app = typer.Typer(help="Cross-repo overview for kodemeio-* repositories.")


@app.command("list")
def list_repos(ctx: typer.Context) -> None:
    """List all kodemeio-* repos with visibility, default branch, last push."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    repos = client.get_repos()

    if out.json_mode:
        out.raw_json([{
            "name": r["name"],
            "visibility": "private" if r.get("private") else "public",
            "default_branch": r.get("default_branch", "main"),
            "pushed_at": r.get("pushed_at", ""),
            "description": r.get("description", ""),
        } for r in repos])
        return

    rows = []
    for r in sorted(repos, key=lambda x: x["name"]):
        rows.append([
            r["name"],
            "private" if r.get("private") else "public",
            r.get("default_branch", "main"),
            _format_date(r.get("pushed_at", "")),
        ])

    out.table(
        f"Repositories ({len(rows)} matching '{client.repo_prefix}*')",
        [("Name", "cyan"), ("Visibility", ""), ("Branch", ""), ("Last Push", "yellow")],
        rows,
    )


@app.command()
def status(ctx: typer.Context) -> None:
    """Aggregated status: open PRs, failing CI, stale branches per repo."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    repos = client.get_repos()
    rows = []

    for repo in sorted(repos, key=lambda x: x["name"]):
        name = repo["name"]
        owner = client.organization

        # Open PRs count
        prs = client.get(f"/repos/{owner}/{name}/pulls", params={"state": "open", "per_page": 100})
        pr_count = len(prs) if isinstance(prs, list) else 0

        # Latest CI status
        runs = client.get(f"/repos/{owner}/{name}/actions/runs", params={"per_page": 1})
        workflow_runs = runs.get("workflow_runs", [])
        if workflow_runs:
            ci_status = workflow_runs[0].get("conclusion") or workflow_runs[0].get("status", "unknown")
        else:
            ci_status = "none"

        # Branch count
        branches = client.get(f"/repos/{owner}/{name}/branches", params={"per_page": 100})
        branch_count = len(branches) if isinstance(branches, list) else 0

        rows.append([name, str(pr_count), ci_status, str(branch_count)])

    if out.json_mode:
        out.raw_json([{
            "repo": r[0], "open_prs": int(r[1]), "ci_status": r[2], "branches": int(r[3]),
        } for r in rows])
        return

    out.table(
        "Repository Status",
        [("Repo", "cyan"), ("Open PRs", "yellow"), ("CI", "green"), ("Branches", "")],
        rows,
    )


@app.command()
def show(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Repository name (e.g., kodemeio-next)")],
) -> None:
    """Show single repo details (size, languages, contributors)."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client
    owner = client.organization

    repo = client.get_repo(name)
    languages = client.get(f"/repos/{owner}/{name}/languages")
    contributors = client.get(f"/repos/{owner}/{name}/contributors", params={"per_page": 10})

    if out.json_mode:
        out.raw_json({
            "name": repo["name"],
            "description": repo.get("description", ""),
            "size_kb": repo.get("size", 0),
            "default_branch": repo.get("default_branch"),
            "languages": languages,
            "top_contributors": [
                {"login": c["login"], "contributions": c["contributions"]}
                for c in (contributors if isinstance(contributors, list) else [])[:5]
            ],
        })
        return

    total_bytes = sum(languages.values()) if isinstance(languages, dict) else 0
    lang_lines = []
    if isinstance(languages, dict):
        for lang, bytes_count in sorted(languages.items(), key=lambda x: x[1], reverse=True)[:5]:
            pct = (bytes_count / total_bytes * 100) if total_bytes else 0
            lang_lines.append((lang, f"{pct:.1f}%"))

    contrib_lines = []
    if isinstance(contributors, list):
        for c in contributors[:5]:
            contrib_lines.append((c["login"], f"{c['contributions']} commits"))

    sections = [
        ("Repository", [
            ("Name", repo["name"]),
            ("Description", repo.get("description") or "(none)"),
            ("Visibility", "private" if repo.get("private") else "public"),
            ("Default Branch", repo.get("default_branch", "main")),
            ("Size", f"{repo.get('size', 0)} KB"),
            ("Open Issues", str(repo.get("open_issues_count", 0))),
            ("Created", _format_date(repo.get("created_at", ""))),
            ("Last Push", _format_date(repo.get("pushed_at", ""))),
        ]),
        ("Languages (top 5)", lang_lines),
        ("Contributors (top 5)", contrib_lines),
    ]
    out.detail(f"Repository: {name}", sections)


def _format_date(iso_date: str) -> str:
    """Format an ISO date string to a shorter readable format."""
    if not iso_date:
        return ""
    try:
        return iso_date[:10]
    except Exception:
        return iso_date
```

- [ ] **Step 2: Register in cli.py**

```python
from kctl_github.commands.repos import app as repos_app
app.add_typer(repos_app, name="repos")
```

- [ ] **Step 3: Verify**

```bash
cd cli && uv run kctl-github repos --help
```

- [ ] **Step 4: Commit**

```bash
git add cli/src/kctl_github/commands/repos.py cli/src/kctl_github/cli.py
git commit -m "feat: add repos command group (list/status/show)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: ci command group

**Files:**
- Create: `cli/src/kctl_github/commands/ci.py`
- Modify: `cli/src/kctl_github/cli.py`

- [ ] **Step 1: Create ci.py**

Create `cli/src/kctl_github/commands/ci.py`:

```python
"""CI/CD monitoring commands."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

import typer

from kctl_github.core.callbacks import AppContext
from kctl_github.core.client import gh_run

app = typer.Typer(help="CI/CD monitoring across kodemeio-* repositories.")


@app.command()
def status(ctx: typer.Context) -> None:
    """Latest workflow run status across ALL repos (pass/fail/running)."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    repos = client.get_repos()
    rows = []

    for repo in sorted(repos, key=lambda x: x["name"]):
        name = repo["name"]
        runs = client.get(
            f"/repos/{client.organization}/{name}/actions/runs",
            params={"per_page": 1},
        )
        workflow_runs = runs.get("workflow_runs", [])
        if workflow_runs:
            run_data = workflow_runs[0]
            conclusion = run_data.get("conclusion") or run_data.get("status", "unknown")
            workflow = run_data.get("name", "")
            created = run_data.get("created_at", "")[:10]
            rows.append([name, workflow, conclusion, created])
        else:
            rows.append([name, "-", "no runs", ""])

    if out.json_mode:
        out.raw_json([{
            "repo": r[0], "workflow": r[1], "conclusion": r[2], "date": r[3],
        } for r in rows])
        return

    out.table(
        "CI Status (latest run per repo)",
        [("Repo", "cyan"), ("Workflow", ""), ("Status", "green"), ("Date", "yellow")],
        rows,
    )


@app.command()
def show(
    ctx: typer.Context,
    repo: Annotated[str, typer.Argument(help="Repository name")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of runs")] = 10,
) -> None:
    """Show workflow runs for a specific repo."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    runs = client.get(
        f"/repos/{client.organization}/{repo}/actions/runs",
        params={"per_page": limit},
    )
    workflow_runs = runs.get("workflow_runs", [])

    if out.json_mode:
        out.raw_json([{
            "id": r["id"],
            "name": r.get("name", ""),
            "status": r.get("status"),
            "conclusion": r.get("conclusion"),
            "branch": r.get("head_branch"),
            "created_at": r.get("created_at"),
            "run_number": r.get("run_number"),
        } for r in workflow_runs])
        return

    rows = []
    for r in workflow_runs:
        conclusion = r.get("conclusion") or r.get("status", "unknown")
        rows.append([
            str(r.get("run_number", "")),
            r.get("name", ""),
            r.get("head_branch", ""),
            conclusion,
            r.get("created_at", "")[:10],
        ])

    out.table(
        f"Workflow Runs: {repo}",
        [("Run #", ""), ("Workflow", "cyan"), ("Branch", ""), ("Status", "green"), ("Date", "yellow")],
        rows,
    )


@app.command()
def stats(
    ctx: typer.Context,
    period: Annotated[str, typer.Option("--period", help="Time period (e.g., 7d, 30d)")] = "7d",
) -> None:
    """CI statistics: success rate, avg duration, failure trends."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    # Parse period
    days = int(period.rstrip("d"))
    since = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
    from datetime import timedelta
    since = since - timedelta(days=days)
    since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")

    repos = client.get_repos()
    total_runs = 0
    total_success = 0
    total_failure = 0
    repo_stats: list[dict] = []

    for repo in repos:
        name = repo["name"]
        runs = client.get(
            f"/repos/{client.organization}/{name}/actions/runs",
            params={"per_page": 100, "created": f">={since_str}"},
        )
        workflow_runs = runs.get("workflow_runs", [])
        count = len(workflow_runs)
        success = sum(1 for r in workflow_runs if r.get("conclusion") == "success")
        failure = sum(1 for r in workflow_runs if r.get("conclusion") == "failure")

        total_runs += count
        total_success += success
        total_failure += failure

        if count > 0:
            repo_stats.append({
                "repo": name,
                "runs": count,
                "success": success,
                "failure": failure,
                "success_rate": f"{(success / count * 100):.0f}%",
            })

    if out.json_mode:
        out.raw_json({
            "period_days": days,
            "total_runs": total_runs,
            "total_success": total_success,
            "total_failure": total_failure,
            "success_rate": f"{(total_success / total_runs * 100):.0f}%" if total_runs else "N/A",
            "repos": repo_stats,
        })
        return

    # Summary
    rate = f"{(total_success / total_runs * 100):.0f}%" if total_runs else "N/A"
    out.success(f"CI Stats (last {days} days): {total_runs} runs, {rate} success rate")

    rows = [
        [s["repo"], str(s["runs"]), str(s["success"]), str(s["failure"]), s["success_rate"]]
        for s in sorted(repo_stats, key=lambda x: x["runs"], reverse=True)
    ]
    out.table(
        "Per-Repo CI Stats",
        [("Repo", "cyan"), ("Runs", ""), ("Pass", "green"), ("Fail", "red"), ("Rate", "yellow")],
        rows,
    )


@app.command()
def rerun(
    ctx: typer.Context,
    repo: Annotated[str, typer.Argument(help="Repository name")],
    workflow: Annotated[str | None, typer.Option("--workflow", "-w", help="Workflow name filter")] = None,
) -> None:
    """Re-trigger the latest failed workflow run."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client
    owner = client.organization

    runs = client.get(
        f"/repos/{owner}/{repo}/actions/runs",
        params={"status": "failure", "per_page": 5},
    )
    workflow_runs = runs.get("workflow_runs", [])

    if workflow and workflow_runs:
        workflow_runs = [r for r in workflow_runs if workflow.lower() in r.get("name", "").lower()]

    if not workflow_runs:
        out.warn("No failed workflow runs found")
        return

    run_data = workflow_runs[0]
    run_id = run_data["id"]

    # Use gh CLI for rerun (simpler auth)
    gh_run(["run", "rerun", str(run_id), "--repo", f"{owner}/{repo}", "--failed"])
    out.success(f"Re-triggered run #{run_data.get('run_number')} ({run_data.get('name')}) in {repo}")


@app.command("bulk-status")
def bulk_status(ctx: typer.Context) -> None:
    """Table of all repos x workflows with pass/fail matrix."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    repos = client.get_repos()
    all_workflows: set[str] = set()
    repo_workflow_status: dict[str, dict[str, str]] = {}

    for repo in sorted(repos, key=lambda x: x["name"]):
        name = repo["name"]
        runs = client.get(
            f"/repos/{client.organization}/{name}/actions/runs",
            params={"per_page": 20},
        )
        workflow_runs = runs.get("workflow_runs", [])

        seen: dict[str, str] = {}
        for r in workflow_runs:
            wf_name = r.get("name", "unknown")
            if wf_name not in seen:
                conclusion = r.get("conclusion") or r.get("status", "?")
                seen[wf_name] = conclusion
                all_workflows.add(wf_name)

        repo_workflow_status[name] = seen

    sorted_workflows = sorted(all_workflows)

    if out.json_mode:
        out.raw_json(repo_workflow_status)
        return

    columns: list[tuple[str, str]] = [("Repo", "cyan")]
    columns.extend((wf, "") for wf in sorted_workflows)

    rows = []
    for repo_name in sorted(repo_workflow_status.keys()):
        row = [repo_name]
        for wf in sorted_workflows:
            row.append(repo_workflow_status[repo_name].get(wf, "-"))
        rows.append(row)

    out.table("CI Bulk Status", columns, rows)
```

- [ ] **Step 2: Register in cli.py**

```python
from kctl_github.commands.ci import app as ci_app
app.add_typer(ci_app, name="ci")
```

- [ ] **Step 3: Commit**

```bash
git add cli/src/kctl_github/commands/ci.py cli/src/kctl_github/cli.py
git commit -m "feat: add ci command group (status/show/stats/rerun/bulk-status)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: prs command group

**Files:**
- Create: `cli/src/kctl_github/commands/prs.py`
- Modify: `cli/src/kctl_github/cli.py`

- [ ] **Step 1: Create prs.py**

Create `cli/src/kctl_github/commands/prs.py`:

```python
"""Cross-repo pull request management."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

import typer

from kctl_github.core.callbacks import AppContext
from kctl_github.core.client import gh_run

app = typer.Typer(help="Cross-repo PR management.")


@app.command("list")
def list_prs(ctx: typer.Context) -> None:
    """Open PRs across all kodemeio-* repos."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    repos = client.get_repos()
    all_prs = []

    for repo in repos:
        name = repo["name"]
        prs = client.get(
            f"/repos/{client.organization}/{name}/pulls",
            params={"state": "open", "per_page": 100},
        )
        if isinstance(prs, list):
            for pr in prs:
                all_prs.append({
                    "repo": name,
                    "number": pr["number"],
                    "title": pr["title"],
                    "author": pr.get("user", {}).get("login", ""),
                    "created_at": pr.get("created_at", ""),
                    "draft": pr.get("draft", False),
                    "labels": [l["name"] for l in pr.get("labels", [])],
                })

    if out.json_mode:
        out.raw_json(all_prs)
        return

    rows = []
    for pr in sorted(all_prs, key=lambda x: x["created_at"], reverse=True):
        draft_marker = " (draft)" if pr["draft"] else ""
        rows.append([
            pr["repo"],
            f"#{pr['number']}",
            pr["title"][:60] + draft_marker,
            pr["author"],
            pr["created_at"][:10],
        ])

    out.table(
        f"Open Pull Requests ({len(rows)} total)",
        [("Repo", "cyan"), ("#", ""), ("Title", ""), ("Author", "yellow"), ("Created", "")],
        rows,
    )


@app.command()
def show(
    ctx: typer.Context,
    repo: Annotated[str, typer.Argument(help="Repository name")],
    number: Annotated[int, typer.Argument(help="PR number")],
) -> None:
    """Show PR details (delegates to gh pr view)."""
    actx: AppContext = ctx.obj
    out = actx.output
    owner = actx.client.organization

    if out.json_mode:
        result = gh_run(["pr", "view", str(number), "--repo", f"{owner}/{repo}", "--json",
                         "title,body,state,author,createdAt,mergeable,reviews,labels"])
        import json
        out.raw_json(json.loads(result))
        return

    result = gh_run(["pr", "view", str(number), "--repo", f"{owner}/{repo}"])
    out.text(result)


@app.command()
def stale(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", "-d", help="Days without activity")] = 14,
) -> None:
    """Find PRs with no activity for N days."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    repos = client.get_repos()
    stale_prs = []

    for repo in repos:
        name = repo["name"]
        prs = client.get(
            f"/repos/{client.organization}/{name}/pulls",
            params={"state": "open", "per_page": 100, "sort": "updated", "direction": "asc"},
        )
        if isinstance(prs, list):
            for pr in prs:
                updated = pr.get("updated_at", "")
                if updated:
                    try:
                        updated_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                        if updated_dt < cutoff:
                            stale_prs.append({
                                "repo": name,
                                "number": pr["number"],
                                "title": pr["title"],
                                "author": pr.get("user", {}).get("login", ""),
                                "updated_at": updated[:10],
                                "days_stale": (datetime.now(timezone.utc) - updated_dt).days,
                            })
                    except (ValueError, TypeError):
                        pass

    if out.json_mode:
        out.raw_json(stale_prs)
        return

    rows = [
        [p["repo"], f"#{p['number']}", p["title"][:50], p["author"],
         p["updated_at"], f"{p['days_stale']}d"]
        for p in sorted(stale_prs, key=lambda x: x["days_stale"], reverse=True)
    ]

    out.table(
        f"Stale PRs (no activity for {days}+ days)",
        [("Repo", "cyan"), ("#", ""), ("Title", ""), ("Author", "yellow"),
         ("Last Update", ""), ("Stale", "red")],
        rows,
    )
```

- [ ] **Step 2: Register in cli.py**

```python
from kctl_github.commands.prs import app as prs_app
app.add_typer(prs_app, name="prs")
```

- [ ] **Step 3: Commit**

```bash
git add cli/src/kctl_github/commands/prs.py cli/src/kctl_github/cli.py
git commit -m "feat: add prs command group (list/show/stale)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: secrets + labels command groups

**Files:**
- Create: `cli/src/kctl_github/commands/secrets.py`
- Create: `cli/src/kctl_github/commands/labels.py`
- Modify: `cli/src/kctl_github/cli.py`

- [ ] **Step 1: Create secrets.py**

Create `cli/src/kctl_github/commands/secrets.py`:

```python
"""Cross-repo secret management."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_github.core.callbacks import AppContext
from kctl_github.core.client import gh_run

app = typer.Typer(help="Cross-repo Actions secret management.")


@app.command("list")
def list_secrets(
    ctx: typer.Context,
    repo: Annotated[str, typer.Argument(help="Repository name")],
) -> None:
    """List Actions secrets for a repo."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client
    owner = client.organization

    data = client.get(f"/repos/{owner}/{repo}/actions/secrets")
    secrets = data.get("secrets", [])

    if out.json_mode:
        out.raw_json([{"name": s["name"], "updated_at": s.get("updated_at", "")} for s in secrets])
        return

    rows = [[s["name"], s.get("updated_at", "")[:10]] for s in secrets]
    out.table(
        f"Secrets: {repo}",
        [("Name", "cyan"), ("Last Updated", "yellow")],
        rows,
    )


@app.command()
def audit(ctx: typer.Context) -> None:
    """Check which repos have which secrets (matrix view)."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client
    owner = client.organization

    repos = client.get_repos()
    all_secret_names: set[str] = set()
    repo_secrets: dict[str, set[str]] = {}

    for repo in repos:
        name = repo["name"]
        try:
            data = client.get(f"/repos/{owner}/{name}/actions/secrets")
            secrets = data.get("secrets", [])
            secret_names = {s["name"] for s in secrets}
            all_secret_names.update(secret_names)
            repo_secrets[name] = secret_names
        except Exception:
            repo_secrets[name] = set()

    sorted_secrets = sorted(all_secret_names)

    if out.json_mode:
        out.raw_json({
            repo: [s for s in sorted_secrets if s in secs]
            for repo, secs in repo_secrets.items()
        })
        return

    columns: list[tuple[str, str]] = [("Repo", "cyan")]
    columns.extend((s, "") for s in sorted_secrets)

    rows = []
    for repo_name in sorted(repo_secrets.keys()):
        row = [repo_name]
        for secret in sorted_secrets:
            row.append("Y" if secret in repo_secrets[repo_name] else "-")
        rows.append(row)

    out.table("Secrets Audit", columns, rows)


@app.command("set")
def set_secret(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Secret name")],
    repos: Annotated[str, typer.Option("--repos", "-r", help="Comma-separated repo names")],
) -> None:
    """Set a secret across multiple repos (prompts for value)."""
    actx: AppContext = ctx.obj
    out = actx.output
    owner = actx.client.organization

    value = typer.prompt(f"Secret value for {name}", hide_input=True)
    repo_list = [r.strip() for r in repos.split(",")]

    for repo in repo_list:
        try:
            gh_run(["secret", "set", name, "--repo", f"{owner}/{repo}", "--body", value])
            out.success(f"Set {name} in {repo}")
        except Exception as e:
            out.error(f"Failed to set {name} in {repo}: {e}")


@app.command()
def rotate(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Secret name to rotate")],
) -> None:
    """Update a secret across all repos that have it."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client
    owner = client.organization

    value = typer.prompt(f"New value for {name}", hide_input=True)
    repos = client.get_repos()
    updated = 0

    for repo in repos:
        repo_name = repo["name"]
        try:
            data = client.get(f"/repos/{owner}/{repo_name}/actions/secrets")
            secret_names = {s["name"] for s in data.get("secrets", [])}
            if name in secret_names:
                gh_run(["secret", "set", name, "--repo", f"{owner}/{repo_name}", "--body", value])
                out.success(f"Rotated {name} in {repo_name}")
                updated += 1
        except Exception as e:
            out.error(f"Failed for {repo_name}: {e}")

    out.info(f"Rotated {name} in {updated} repo(s)")
```

- [ ] **Step 2: Create labels.py**

Create `cli/src/kctl_github/commands/labels.py`:

```python
"""Cross-repo label standardization."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_github.core.callbacks import AppContext

app = typer.Typer(help="Cross-repo label management.")


@app.command("list")
def list_labels(
    ctx: typer.Context,
    repo: Annotated[str, typer.Argument(help="Repository name")],
) -> None:
    """List labels for a repo."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client
    owner = client.organization

    labels = client.get(f"/repos/{owner}/{repo}/labels", params={"per_page": 100})

    if out.json_mode:
        out.raw_json([{
            "name": l["name"], "color": l.get("color", ""), "description": l.get("description", ""),
        } for l in labels])
        return

    rows = [[l["name"], f"#{l.get('color', '')}", l.get("description", "") or ""] for l in labels]
    out.table(
        f"Labels: {repo}",
        [("Name", "cyan"), ("Color", "yellow"), ("Description", "")],
        rows,
    )


@app.command()
def sync(
    ctx: typer.Context,
    source: Annotated[str, typer.Option("--source", "-s", help="Source repo to copy labels from")],
) -> None:
    """Copy labels from source repo to all other kodemeio-* repos."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client
    owner = client.organization

    # Get source labels
    source_labels = client.get(f"/repos/{owner}/{source}/labels", params={"per_page": 100})
    if not isinstance(source_labels, list):
        out.error("Failed to fetch source labels")
        raise typer.Exit(1)

    repos = client.get_repos()
    target_repos = [r for r in repos if r["name"] != source]

    for repo in target_repos:
        name = repo["name"]
        existing = client.get(f"/repos/{owner}/{name}/labels", params={"per_page": 100})
        existing_names = {l["name"] for l in existing} if isinstance(existing, list) else set()

        created = 0
        for label in source_labels:
            if label["name"] not in existing_names:
                try:
                    client.post(f"/repos/{owner}/{name}/labels", json={
                        "name": label["name"],
                        "color": label.get("color", "000000"),
                        "description": label.get("description", ""),
                    })
                    created += 1
                except Exception:
                    pass  # Label may already exist with different casing

        if created > 0:
            out.success(f"{name}: added {created} label(s)")
        else:
            out.info(f"{name}: already in sync")


@app.command()
def diff(ctx: typer.Context) -> None:
    """Show label differences across repos."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client
    owner = client.organization

    repos = client.get_repos()
    all_labels: set[str] = set()
    repo_labels: dict[str, set[str]] = {}

    for repo in repos:
        name = repo["name"]
        labels = client.get(f"/repos/{owner}/{name}/labels", params={"per_page": 100})
        label_names = {l["name"] for l in labels} if isinstance(labels, list) else set()
        all_labels.update(label_names)
        repo_labels[name] = label_names

    sorted_labels = sorted(all_labels)

    if out.json_mode:
        out.raw_json({
            repo: sorted(names) for repo, names in repo_labels.items()
        })
        return

    columns: list[tuple[str, str]] = [("Label", "cyan")]
    sorted_repos = sorted(repo_labels.keys())
    columns.extend((r.removeprefix("kodemeio-")[:12], "") for r in sorted_repos)

    rows = []
    for label in sorted_labels:
        row = [label]
        for repo_name in sorted_repos:
            row.append("Y" if label in repo_labels[repo_name] else "-")
        rows.append(row)

    out.table("Label Diff", columns, rows)
```

- [ ] **Step 3: Register in cli.py**

```python
from kctl_github.commands.secrets import app as secrets_app
from kctl_github.commands.labels import app as labels_app
app.add_typer(secrets_app, name="secrets")
app.add_typer(labels_app, name="labels")
```

- [ ] **Step 4: Commit**

```bash
git add cli/src/kctl_github/commands/secrets.py cli/src/kctl_github/commands/labels.py cli/src/kctl_github/cli.py
git commit -m "feat: add secrets and labels command groups

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: stats command group

**Files:**
- Create: `cli/src/kctl_github/commands/stats.py`
- Modify: `cli/src/kctl_github/cli.py`

- [ ] **Step 1: Create stats.py**

Create `cli/src/kctl_github/commands/stats.py`:

```python
"""Repository statistics commands."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

import typer

from kctl_github.core.callbacks import AppContext

app = typer.Typer(help="Repository statistics across kodemeio-* repos.")


@app.command()
def overview(ctx: typer.Context) -> None:
    """Total repos, total stars, total issues, total PRs."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    repos = client.get_repos()
    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    total_forks = sum(r.get("forks_count", 0) for r in repos)
    total_issues = sum(r.get("open_issues_count", 0) for r in repos)
    total_size = sum(r.get("size", 0) for r in repos)

    if out.json_mode:
        out.raw_json({
            "repos": len(repos),
            "stars": total_stars,
            "forks": total_forks,
            "open_issues": total_issues,
            "total_size_kb": total_size,
        })
        return

    sections = [
        ("Overview", [
            ("Repositories", str(len(repos))),
            ("Total Stars", str(total_stars)),
            ("Total Forks", str(total_forks)),
            ("Open Issues", str(total_issues)),
            ("Total Size", f"{total_size:,} KB ({total_size // 1024} MB)"),
        ]),
    ]
    out.detail("GitHub Stats Overview", sections)


@app.command()
def activity(
    ctx: typer.Context,
    period: Annotated[str, typer.Option("--period", help="Time period (e.g., 7d, 30d)")] = "30d",
) -> None:
    """Commit activity, PR merge rate, issue velocity."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    days = int(period.rstrip("d"))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")

    repos = client.get_repos()
    rows = []

    for repo in sorted(repos, key=lambda x: x["name"]):
        name = repo["name"]
        owner = client.organization

        # Commits since period
        try:
            commits = client.get(
                f"/repos/{owner}/{name}/commits",
                params={"since": since_str, "per_page": 100},
            )
            commit_count = len(commits) if isinstance(commits, list) else 0
        except Exception:
            commit_count = 0

        # Merged PRs in period
        try:
            prs = client.get(
                f"/repos/{owner}/{name}/pulls",
                params={"state": "closed", "sort": "updated", "direction": "desc", "per_page": 50},
            )
            merged_count = 0
            if isinstance(prs, list):
                for pr in prs:
                    if pr.get("merged_at"):
                        try:
                            merged_dt = datetime.fromisoformat(
                                pr["merged_at"].replace("Z", "+00:00")
                            )
                            if merged_dt >= since:
                                merged_count += 1
                        except (ValueError, TypeError):
                            pass
        except Exception:
            merged_count = 0

        if commit_count > 0 or merged_count > 0:
            rows.append([name, str(commit_count), str(merged_count)])

    if out.json_mode:
        out.raw_json([{
            "repo": r[0], "commits": int(r[1]), "merged_prs": int(r[2]),
        } for r in rows])
        return

    out.table(
        f"Activity (last {days} days)",
        [("Repo", "cyan"), ("Commits", "green"), ("Merged PRs", "yellow")],
        rows,
    )


@app.command()
def languages(ctx: typer.Context) -> None:
    """Language breakdown across all repos."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    repos = client.get_repos()
    lang_totals: dict[str, int] = {}

    for repo in repos:
        name = repo["name"]
        try:
            langs = client.get(f"/repos/{client.organization}/{name}/languages")
            if isinstance(langs, dict):
                for lang, bytes_count in langs.items():
                    lang_totals[lang] = lang_totals.get(lang, 0) + bytes_count
        except Exception:
            pass

    total = sum(lang_totals.values())
    sorted_langs = sorted(lang_totals.items(), key=lambda x: x[1], reverse=True)

    if out.json_mode:
        out.raw_json({
            lang: {"bytes": b, "percentage": f"{(b / total * 100):.1f}%"} if total else {"bytes": b}
            for lang, b in sorted_langs
        })
        return

    rows = []
    for lang, bytes_count in sorted_langs[:20]:
        pct = (bytes_count / total * 100) if total else 0
        bar = "#" * int(pct / 2)
        rows.append([lang, f"{bytes_count:,}", f"{pct:.1f}%", bar])

    out.table(
        "Languages (all repos)",
        [("Language", "cyan"), ("Bytes", ""), ("%", "yellow"), ("Distribution", "green")],
        rows,
    )


@app.command()
def contributors(ctx: typer.Context) -> None:
    """Contributor activity across all repos."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    repos = client.get_repos()
    contributor_totals: dict[str, int] = {}

    for repo in repos:
        name = repo["name"]
        try:
            contribs = client.get(
                f"/repos/{client.organization}/{name}/contributors",
                params={"per_page": 30},
            )
            if isinstance(contribs, list):
                for c in contribs:
                    login = c.get("login", "unknown")
                    contributor_totals[login] = (
                        contributor_totals.get(login, 0) + c.get("contributions", 0)
                    )
        except Exception:
            pass

    sorted_contribs = sorted(contributor_totals.items(), key=lambda x: x[1], reverse=True)

    if out.json_mode:
        out.raw_json([
            {"login": login, "total_contributions": count}
            for login, count in sorted_contribs
        ])
        return

    rows = [[login, str(count)] for login, count in sorted_contribs[:20]]
    out.table(
        "Top Contributors (all repos)",
        [("Login", "cyan"), ("Total Contributions", "yellow")],
        rows,
    )
```

- [ ] **Step 2: Register in cli.py**

```python
from kctl_github.commands.stats import app as stats_app
app.add_typer(stats_app, name="stats")
```

- [ ] **Step 3: Commit**

```bash
git add cli/src/kctl_github/commands/stats.py cli/src/kctl_github/cli.py
git commit -m "feat: add stats command group (overview/activity/languages/contributors)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: billing command group

**Files:**
- Create: `cli/src/kctl_github/commands/billing.py`
- Modify: `cli/src/kctl_github/cli.py`

- [ ] **Step 1: Create billing.py**

Create `cli/src/kctl_github/commands/billing.py`:

```python
"""GitHub billing and usage commands."""

from __future__ import annotations

import typer

from kctl_github.core.callbacks import AppContext

app = typer.Typer(help="GitHub Actions billing and usage.")


@app.command()
def actions(ctx: typer.Context) -> None:
    """Actions minutes used this billing cycle."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client
    org = client.organization

    # Try org endpoint first, fall back to user
    try:
        data = client.get(f"/orgs/{org}/settings/billing/actions")
    except Exception:
        try:
            data = client.get(f"/users/{org}/settings/billing/actions")
        except Exception:
            out.error("Unable to fetch billing data. Token may lack billing scope.")
            raise typer.Exit(1)

    if out.json_mode:
        out.raw_json(data)
        return

    total_min = data.get("total_minutes_used", 0)
    included_min = data.get("included_minutes", 0)
    paid_min = data.get("total_paid_minutes_used", 0)

    sections = [
        ("Actions Minutes", [
            ("Total Used", f"{total_min} min"),
            ("Included", f"{included_min} min"),
            ("Paid Overage", f"{paid_min} min"),
        ]),
    ]

    # Per-OS breakdown if available
    breakdown = data.get("minutes_used_breakdown", {})
    if breakdown:
        os_lines = [(os_name, f"{minutes} min") for os_name, minutes in breakdown.items() if minutes > 0]
        if os_lines:
            sections.append(("By OS", os_lines))

    out.detail("Actions Billing", sections)


@app.command()
def storage(ctx: typer.Context) -> None:
    """Git LFS + Packages storage usage."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client
    org = client.organization

    try:
        data = client.get(f"/orgs/{org}/settings/billing/shared-storage")
    except Exception:
        try:
            data = client.get(f"/users/{org}/settings/billing/shared-storage")
        except Exception:
            out.error("Unable to fetch storage billing data.")
            raise typer.Exit(1)

    if out.json_mode:
        out.raw_json(data)
        return

    sections = [
        ("Storage", [
            ("Days Left in Cycle", str(data.get("days_left_in_billing_cycle", "?"))),
            ("Estimated Paid Storage (GB)", f"{data.get('estimated_paid_storage_for_month', 0):.2f}"),
            ("Estimated Storage (GB)", f"{data.get('estimated_storage_for_month', 0):.2f}"),
        ]),
    ]
    out.detail("Storage Billing", sections)


@app.command()
def packages(ctx: typer.Context) -> None:
    """Packages data transfer."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client
    org = client.organization

    try:
        data = client.get(f"/orgs/{org}/settings/billing/packages")
    except Exception:
        try:
            data = client.get(f"/users/{org}/settings/billing/packages")
        except Exception:
            out.error("Unable to fetch packages billing data.")
            raise typer.Exit(1)

    if out.json_mode:
        out.raw_json(data)
        return

    sections = [
        ("Packages", [
            ("Total Bandwidth (GB)", f"{data.get('total_gigabytes_bandwidth_used', 0):.2f}"),
            ("Included Bandwidth (GB)", f"{data.get('included_gigabytes_bandwidth', 0)}"),
            ("Paid Bandwidth (GB)", f"{data.get('total_paid_gigabytes_bandwidth_used', 0):.2f}"),
        ]),
    ]
    out.detail("Packages Billing", sections)


@app.command()
def overview(ctx: typer.Context) -> None:
    """Combined billing summary."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client
    org = client.organization

    results: dict = {}

    # Fetch all billing endpoints
    for endpoint_name, path_suffix in [
        ("actions", "actions"),
        ("storage", "shared-storage"),
        ("packages", "packages"),
    ]:
        try:
            data = client.get(f"/orgs/{org}/settings/billing/{path_suffix}")
        except Exception:
            try:
                data = client.get(f"/users/{org}/settings/billing/{path_suffix}")
            except Exception:
                data = {}
        results[endpoint_name] = data

    if out.json_mode:
        out.raw_json(results)
        return

    actions_data = results.get("actions", {})
    storage_data = results.get("storage", {})
    packages_data = results.get("packages", {})

    sections = [
        ("Actions", [
            ("Minutes Used", f"{actions_data.get('total_minutes_used', 0)}"),
            ("Minutes Included", f"{actions_data.get('included_minutes', 0)}"),
        ]),
        ("Storage", [
            ("Estimated (GB)", f"{storage_data.get('estimated_storage_for_month', 0):.2f}"),
        ]),
        ("Packages", [
            ("Bandwidth Used (GB)", f"{packages_data.get('total_gigabytes_bandwidth_used', 0):.2f}"),
            ("Bandwidth Included (GB)", f"{packages_data.get('included_gigabytes_bandwidth', 0)}"),
        ]),
    ]
    out.detail("Billing Overview", sections)
```

- [ ] **Step 2: Register in cli.py**

```python
from kctl_github.commands.billing import app as billing_app
app.add_typer(billing_app, name="billing")
```

- [ ] **Step 3: Commit**

```bash
git add cli/src/kctl_github/commands/billing.py cli/src/kctl_github/cli.py
git commit -m "feat: add billing command group (actions/storage/packages/overview)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 9: Tests + CLAUDE.md

**Files:**
- Create: `cli/tests/test_client.py`
- Create: `cli/tests/test_health.py`
- Create: `cli/tests/test_repos.py`
- Create: `cli/tests/test_ci.py`
- Create: `cli/tests/test_prs.py`
- Create: `cli/tests/test_stats.py`
- Create: `cli/tests/test_billing.py`
- Create: `cli/tests/test_dashboard.py`
- Modify: `cli/tests/test_smoke.py`
- Modify: `cli/tests/conftest.py`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update conftest.py with shared fixtures**

Update `cli/tests/conftest.py`:

```python
"""Shared test configuration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_github.cli import app
from kctl_github.core.callbacks import AppContext


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def cli_app():
    return app


@pytest.fixture
def mock_client():
    """Mock GitHubClient for command tests."""
    client = MagicMock()
    client.organization = "tgunawandev"
    client.repo_prefix = "kodemeio-"
    return client


@pytest.fixture
def mock_context(mock_client):
    """Patch AppContext.client to return mock_client."""
    with patch.object(AppContext, "client", new_callable=lambda: property(lambda self: mock_client)):
        yield mock_client
```

- [ ] **Step 2: Create test_client.py**

Create `cli/tests/test_client.py`:

```python
"""Tests for GitHubClient."""

from __future__ import annotations

import pytest
from kctl_lib.exceptions import ConfigError

from kctl_github.core.client import GitHubClient, _parse_next_link, gh_run


class TestGitHubClient:
    def test_requires_credential(self):
        with pytest.raises(ConfigError, match="credential"):
            GitHubClient(credential="")

    def test_init_sets_headers(self):
        client = GitHubClient(credential="ghp_test123")
        assert client._client.headers["Authorization"] == "Bearer ghp_test123"
        assert "application/vnd.github+json" in client._client.headers["Accept"]
        client.close()

    def test_default_organization(self):
        client = GitHubClient(credential="ghp_test123")
        assert client.organization == "tgunawandev"
        assert client.repo_prefix == "kodemeio-"
        client.close()

    def test_custom_organization(self):
        client = GitHubClient(credential="ghp_test123", organization="myorg", repo_prefix="myapp-")
        assert client.organization == "myorg"
        assert client.repo_prefix == "myapp-"
        client.close()


class TestParseNextLink:
    def test_parses_next_url(self):
        header = '<https://api.github.com/user/repos?page=2>; rel="next", <https://api.github.com/user/repos?page=5>; rel="last"'
        assert _parse_next_link(header) == "https://api.github.com/user/repos?page=2"

    def test_returns_none_without_next(self):
        header = '<https://api.github.com/user/repos?page=5>; rel="last"'
        assert _parse_next_link(header) is None

    def test_returns_none_for_empty(self):
        assert _parse_next_link("") is None
```

- [ ] **Step 3: Create test_health.py**

Create `cli/tests/test_health.py`:

```python
"""Tests for health command."""

from __future__ import annotations


class TestHealth:
    def test_health_help(self, runner, cli_app):
        result = runner.invoke(cli_app, ["health", "--help"])
        assert result.exit_code == 0
        assert "rate limit" in result.output.lower() or "connectivity" in result.output.lower()

    def test_health_json(self, runner, cli_app, mock_context):
        mock_context.get.side_effect = [
            {"resources": {"core": {"remaining": 4999, "limit": 5000}, "search": {"remaining": 30, "limit": 30}}},
            {"login": "testuser", "name": "Test", "plan": {"name": "free"}},
        ]
        result = runner.invoke(cli_app, ["--json", "health"])
        assert result.exit_code == 0
        assert "healthy" in result.output
```

- [ ] **Step 4: Create test_repos.py**

Create `cli/tests/test_repos.py`:

```python
"""Tests for repos commands."""

from __future__ import annotations


MOCK_REPOS = [
    {"name": "kodemeio-next", "private": False, "default_branch": "main", "pushed_at": "2026-03-28T10:00:00Z", "description": "Next.js"},
    {"name": "kodemeio-odoo", "private": True, "default_branch": "main", "pushed_at": "2026-03-27T10:00:00Z", "description": "Odoo"},
]


class TestReposList:
    def test_list_help(self, runner, cli_app):
        result = runner.invoke(cli_app, ["repos", "list", "--help"])
        assert result.exit_code == 0

    def test_list_json(self, runner, cli_app, mock_context):
        mock_context.get_repos.return_value = MOCK_REPOS
        result = runner.invoke(cli_app, ["--json", "repos", "list"])
        assert result.exit_code == 0
        assert "kodemeio-next" in result.output


class TestReposShow:
    def test_show_help(self, runner, cli_app):
        result = runner.invoke(cli_app, ["repos", "show", "--help"])
        assert result.exit_code == 0

    def test_show_json(self, runner, cli_app, mock_context):
        mock_context.get_repo.return_value = {
            "name": "kodemeio-next", "description": "Next.js", "private": False,
            "default_branch": "main", "size": 1024, "open_issues_count": 3,
            "created_at": "2024-01-01T00:00:00Z", "pushed_at": "2026-03-28T00:00:00Z",
        }
        mock_context.get.side_effect = [
            {"Python": 50000, "TypeScript": 30000},
            [{"login": "user1", "contributions": 100}],
        ]
        result = runner.invoke(cli_app, ["--json", "repos", "show", "kodemeio-next"])
        assert result.exit_code == 0
        assert "kodemeio-next" in result.output
```

- [ ] **Step 5: Create test_ci.py**

Create `cli/tests/test_ci.py`:

```python
"""Tests for ci commands."""

from __future__ import annotations


MOCK_REPOS = [
    {"name": "kodemeio-next"},
    {"name": "kodemeio-odoo"},
]


class TestCIStatus:
    def test_status_help(self, runner, cli_app):
        result = runner.invoke(cli_app, ["ci", "status", "--help"])
        assert result.exit_code == 0

    def test_status_json(self, runner, cli_app, mock_context):
        mock_context.get_repos.return_value = MOCK_REPOS
        mock_context.get.return_value = {
            "workflow_runs": [{"name": "CI", "conclusion": "success", "status": "completed", "created_at": "2026-03-28T10:00:00Z"}],
        }
        result = runner.invoke(cli_app, ["--json", "ci", "status"])
        assert result.exit_code == 0


class TestCIShow:
    def test_show_help(self, runner, cli_app):
        result = runner.invoke(cli_app, ["ci", "show", "--help"])
        assert result.exit_code == 0
```

- [ ] **Step 6: Create test_prs.py**

Create `cli/tests/test_prs.py`:

```python
"""Tests for prs commands."""

from __future__ import annotations


MOCK_REPOS = [{"name": "kodemeio-next"}]


class TestPRsList:
    def test_list_help(self, runner, cli_app):
        result = runner.invoke(cli_app, ["prs", "list", "--help"])
        assert result.exit_code == 0

    def test_list_json(self, runner, cli_app, mock_context):
        mock_context.get_repos.return_value = MOCK_REPOS
        mock_context.get.return_value = [
            {"number": 1, "title": "Fix bug", "user": {"login": "dev1"}, "created_at": "2026-03-27T00:00:00Z", "draft": False, "labels": []},
        ]
        result = runner.invoke(cli_app, ["--json", "prs", "list"])
        assert result.exit_code == 0
        assert "Fix bug" in result.output


class TestPRsStale:
    def test_stale_help(self, runner, cli_app):
        result = runner.invoke(cli_app, ["prs", "stale", "--help"])
        assert result.exit_code == 0
```

- [ ] **Step 7: Create test_stats.py**

Create `cli/tests/test_stats.py`:

```python
"""Tests for stats commands."""

from __future__ import annotations


MOCK_REPOS = [
    {"name": "kodemeio-next", "stargazers_count": 5, "forks_count": 2, "open_issues_count": 3, "size": 1024},
]


class TestStatsOverview:
    def test_overview_help(self, runner, cli_app):
        result = runner.invoke(cli_app, ["stats", "overview", "--help"])
        assert result.exit_code == 0

    def test_overview_json(self, runner, cli_app, mock_context):
        mock_context.get_repos.return_value = MOCK_REPOS
        result = runner.invoke(cli_app, ["--json", "stats", "overview"])
        assert result.exit_code == 0
        assert '"repos": 1' in result.output


class TestStatsLanguages:
    def test_languages_help(self, runner, cli_app):
        result = runner.invoke(cli_app, ["stats", "languages", "--help"])
        assert result.exit_code == 0
```

- [ ] **Step 8: Create test_billing.py**

Create `cli/tests/test_billing.py`:

```python
"""Tests for billing commands."""

from __future__ import annotations


class TestBillingActions:
    def test_actions_help(self, runner, cli_app):
        result = runner.invoke(cli_app, ["billing", "actions", "--help"])
        assert result.exit_code == 0

    def test_actions_json(self, runner, cli_app, mock_context):
        mock_context.get.return_value = {
            "total_minutes_used": 500,
            "included_minutes": 2000,
            "total_paid_minutes_used": 0,
            "minutes_used_breakdown": {"UBUNTU": 450, "MACOS": 50},
        }
        result = runner.invoke(cli_app, ["--json", "billing", "actions"])
        assert result.exit_code == 0


class TestBillingOverview:
    def test_overview_help(self, runner, cli_app):
        result = runner.invoke(cli_app, ["billing", "overview", "--help"])
        assert result.exit_code == 0
```

- [ ] **Step 9: Create test_dashboard.py**

Create `cli/tests/test_dashboard.py`:

```python
"""Tests for dashboard command."""

from __future__ import annotations


class TestDashboard:
    def test_dashboard_help(self, runner, cli_app):
        result = runner.invoke(cli_app, ["dashboard", "--help"])
        assert result.exit_code == 0
```

- [ ] **Step 10: Update test_smoke.py with full command coverage**

Replace `cli/tests/test_smoke.py`:

```python
"""Smoke tests for all CLI commands."""

from typer.testing import CliRunner

from kctl_github.cli import app

runner = CliRunner()


class TestCLISmoke:
    def test_help_exits_zero(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_version_flag(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0

    def test_config_help(self):
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0

    def test_health_help(self):
        result = runner.invoke(app, ["health", "--help"])
        assert result.exit_code == 0

    def test_dashboard_help(self):
        result = runner.invoke(app, ["dashboard", "--help"])
        assert result.exit_code == 0

    def test_repos_help(self):
        result = runner.invoke(app, ["repos", "--help"])
        assert result.exit_code == 0

    def test_ci_help(self):
        result = runner.invoke(app, ["ci", "--help"])
        assert result.exit_code == 0

    def test_prs_help(self):
        result = runner.invoke(app, ["prs", "--help"])
        assert result.exit_code == 0

    def test_secrets_help(self):
        result = runner.invoke(app, ["secrets", "--help"])
        assert result.exit_code == 0

    def test_labels_help(self):
        result = runner.invoke(app, ["labels", "--help"])
        assert result.exit_code == 0

    def test_stats_help(self):
        result = runner.invoke(app, ["stats", "--help"])
        assert result.exit_code == 0

    def test_billing_help(self):
        result = runner.invoke(app, ["billing", "--help"])
        assert result.exit_code == 0
```

- [ ] **Step 11: Update CLAUDE.md**

Update `CLAUDE.md` at the repo root with CLI documentation:

```markdown
# CLAUDE.md - kodemeio-github

kctl-github: Cross-repo GitHub management CLI for 21 kodemeio-* repositories.

## Quick Commands

```bash
cd cli
uv sync --all-extras
uv run pytest tests/ -v
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy src/
```

## Architecture

kctl-github uses kctl-lib v0.4.0 (APIClient, config profiles, Output formatting).

- **GitHubClient(APIClient)** — REST API client for api.github.com
- **gh_run()** — Subprocess helper for `gh` CLI operations
- **ServiceConfig** — token, organization, repo_prefix fields

## Command Groups (10)

| Group | Commands | Purpose |
|-------|----------|---------|
| config | init/add/use/show/validate/remove/set/profiles/current | Profile management |
| health | (root) | API check + rate limits |
| dashboard | (root) | Quick overview |
| repos | list/status/show | Cross-repo overview |
| ci | status/show/stats/rerun/bulk-status | CI/CD monitoring |
| prs | list/show/stale | Cross-repo PR management |
| secrets | list/audit/set/rotate | Secret management |
| labels | list/sync/diff | Label standardization |
| stats | overview/activity/languages/contributors | Statistics |
| billing | actions/storage/packages/overview | Usage & billing |

## Key Design

- All list commands filter by `repo_prefix` automatically (default: "kodemeio-")
- `get_repos()` helper lists all matching repos
- `get_paginated()` follows GitHub Link headers for pagination
- Uses `gh` CLI for operations that benefit from its auth (rerun, secrets set, PR view)

## Conventions

- Python 3.12+, Typer + Rich + Pydantic 2
- kctl-lib for shared infrastructure
- Hatchling build, uv package manager
- Ruff linting, mypy strict typing
- Conventional commits
```

- [ ] **Step 12: Run tests**

```bash
cd cli && uv sync --all-extras && uv run pytest tests/ -v --tb=short
```

- [ ] **Step 13: Lint and type check**

```bash
cd cli && uv run ruff check src/ tests/ && uv run ruff format src/ tests/ --check
```

- [ ] **Step 14: Commit**

```bash
git add cli/tests/ CLAUDE.md
git commit -m "test: add comprehensive test suite and update CLAUDE.md

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 10: Final verification and cli.py assembly

**Files:**
- Modify: `cli/src/kctl_github/cli.py` (final version with all registrations)

- [ ] **Step 1: Verify final cli.py has all registrations**

The final `cli/src/kctl_github/cli.py` should look like:

```python
"""Main CLI entry point for kctl-github."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_github import __version__
from kctl_github.commands.billing import app as billing_app
from kctl_github.commands.ci import app as ci_app
from kctl_github.commands.config_cmd import app as config_app
from kctl_github.commands.dashboard import app as dashboard_app
from kctl_github.commands.health import app as health_app
from kctl_github.commands.labels import app as labels_app
from kctl_github.commands.prs import app as prs_app
from kctl_github.commands.repos import app as repos_app
from kctl_github.commands.secrets import app as secrets_app
from kctl_github.commands.stats import app as stats_app
from kctl_github.core.callbacks import AppContext
from kctl_github.core.plugins import discover_and_load_plugins


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-github {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-github",
    help="GitHub cross-repo management for kodemeio-* repositories",
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
    """GitHub cross-repo management for kodemeio-* repositories."""
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
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(repos_app, name="repos")
app.add_typer(ci_app, name="ci")
app.add_typer(prs_app, name="prs")
app.add_typer(secrets_app, name="secrets")
app.add_typer(labels_app, name="labels")
app.add_typer(stats_app, name="stats")
app.add_typer(billing_app, name="billing")

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

- [ ] **Step 2: Full test run**

```bash
cd cli && uv sync --all-extras && uv run pytest tests/ -v
```

- [ ] **Step 3: Lint and format**

```bash
cd cli && uv run ruff check src/ tests/ --fix && uv run ruff format src/ tests/
```

- [ ] **Step 4: Type check**

```bash
cd cli && uv run mypy src/
```

- [ ] **Step 5: Install and smoke test**

```bash
cd cli && uv pip install -e . && kctl-github --help && kctl-github --version
```

- [ ] **Step 6: Final commit**

```bash
git add .
git commit -m "feat: complete kctl-github CLI with 10 command groups

Co-Authored-By: Claude <noreply@anthropic.com>"
```

- [ ] **Step 7: Push to feature branch**

```bash
git checkout -b feat/kctl-github-cli
git push -u origin feat/kctl-github-cli
```

---

## Summary

| Task | Commands Added | Files |
|------|---------------|-------|
| 1 | (core infra) | client.py, config.py, exceptions.py, callbacks.py, config_cmd.py |
| 2 | health, dashboard | health.py, dashboard.py |
| 3 | repos list/status/show | repos.py |
| 4 | ci status/show/stats/rerun/bulk-status | ci.py |
| 5 | prs list/show/stale | prs.py |
| 6 | secrets list/audit/set/rotate + labels list/sync/diff | secrets.py, labels.py |
| 7 | stats overview/activity/languages/contributors | stats.py |
| 8 | billing actions/storage/packages/overview | billing.py |
| 9 | tests + CLAUDE.md | 8 test files, conftest.py, CLAUDE.md |
| 10 | final verification | cli.py final assembly |

**Total: ~30 commands across 10 groups, ~8 test files, full linting + type checking.**

**GitHub API endpoints used:**
- `GET /rate_limit` -- health/rate limits
- `GET /user` -- authenticated user info
- `GET /users/{user}/repos` -- list repos (paginated)
- `GET /repos/{owner}/{repo}` -- single repo details
- `GET /repos/{owner}/{repo}/actions/runs` -- workflow runs
- `GET /repos/{owner}/{repo}/pulls` -- pull requests
- `GET /repos/{owner}/{repo}/actions/secrets` -- secrets list
- `GET /repos/{owner}/{repo}/labels` -- labels
- `POST /repos/{owner}/{repo}/labels` -- create label
- `GET /repos/{owner}/{repo}/languages` -- language stats
- `GET /repos/{owner}/{repo}/contributors` -- contributor list
- `GET /repos/{owner}/{repo}/commits` -- commit list
- `GET /repos/{owner}/{repo}/branches` -- branch list
- `GET /orgs/{org}/settings/billing/actions` -- billing actions
- `GET /orgs/{org}/settings/billing/shared-storage` -- billing storage
- `GET /orgs/{org}/settings/billing/packages` -- billing packages
