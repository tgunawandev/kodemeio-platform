# kctl-* Service CLIs — 5 New CLI Implementations

**Date:** 2026-03-29
**Scope:** Build out service-specific commands for kctl-grafana, kctl-sentry, kctl-github, kctl-linear, kctl-notion
**Goal:** Day-to-day operational CLIs for Kodemeio platform infrastructure management

---

## 1. Overview

5 CLIs to implement, each focused on daily operations for managing Kodemeio infrastructure. All use kctl-lib v0.4.0 (APIClient, config profiles, Output formatting).

| CLI | Repo | API Type | Command Groups | Priority |
|-----|------|----------|---------------|----------|
| kctl-grafana | kodemeio-core/kodemeio-grafana | REST | 12 | 1 (daily monitoring) |
| kctl-sentry | kodemeio-saas/kodemeio-sentry | REST | 10 | 2 (error triage) |
| kctl-github | kodemeio-saas/kodemeio-github | REST + `gh` CLI | 10 | 3 (cross-repo mgmt) |
| kctl-linear | kodemeio-saas/kodemeio-linear | GraphQL | 10 | 4 (sprint tracking) |
| kctl-notion | kodemeio-saas/kodemeio-notion | REST | 7 | 5 (wiki search) |

---

## 2. kctl-grafana

**Repo:** `/home/tgunawan/project/00-new-projects/kodemeio-core/kodemeio-grafana`
**API:** Grafana HTTP API (REST, Bearer token)
**Base URL:** configurable (e.g., `https://grafana.kodeme.io`)
**Auth:** `Authorization: Bearer {api_key}`

### 2.1 Structure

Create `cli/` directory inside existing kodemeio-grafana repo (alongside existing `scripts/`, `docker-compose.yml`, etc.).

```
kodemeio-grafana/
├── cli/                          # NEW
│   ├── pyproject.toml
│   ├── src/kctl_grafana/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── cli.py
│   │   ├── core/
│   │   │   ├── callbacks.py
│   │   │   ├── client.py        # GrafanaClient(APIClient)
│   │   │   ├── config.py        # SERVICE_KEY = "grafana"
│   │   │   └── exceptions.py
│   │   └── commands/
│   │       ├── config_cmd.py
│   │       ├── health.py
│   │       ├── dashboard.py
│   │       ├── datasource.py
│   │       ├── alert.py
│   │       ├── folder.py
│   │       ├── annotation.py
│   │       ├── user.py
│   │       ├── backup.py
│   │       ├── status.py
│   │       └── selftest.py
│   └── tests/
├── scripts/                      # EXISTING (unchanged)
├── docker-compose.yml            # EXISTING (unchanged)
└── CLAUDE.md                     # UPDATE
```

### 2.2 Client

```python
class GrafanaClient(APIClient):
    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"
    API_PREFIX = "/api"
```

### 2.3 Commands

#### `health` — API connectivity check
- `kctl-grafana health` — Check API reachability, version, org info
- `kctl-grafana health check` — Detailed health (API + all datasources)

#### `dashboard` — Dashboard management
- `kctl-grafana dashboard list` — List all dashboards (with folder, tags, starred)
- `kctl-grafana dashboard show <uid>` — Show dashboard metadata + panel summary
- `kctl-grafana dashboard export <uid>` — Export dashboard JSON to file
- `kctl-grafana dashboard import <file>` — Import dashboard from JSON file
- `kctl-grafana dashboard search <query>` — Search dashboards by name/tag
- `kctl-grafana dashboard star <uid>` — Star/unstar a dashboard

#### `datasource` — Data source management
- `kctl-grafana datasource list` — List all datasources with type and status
- `kctl-grafana datasource test [name]` — Test datasource connectivity (all if no name)
- `kctl-grafana datasource show <name>` — Show datasource config details
- `kctl-grafana datasource add <name> --type <type> --url <url>` — Add new datasource

#### `alert` — Alert management
- `kctl-grafana alert list` — List alert rules with current state (firing/ok/pending)
- `kctl-grafana alert show <uid>` — Show alert rule details and history
- `kctl-grafana alert silence <uid> --duration <duration>` — Silence an alert
- `kctl-grafana alert contacts` — List notification contact points

#### `folder` — Folder organization
- `kctl-grafana folder list` — List all folders
- `kctl-grafana folder create <name>` — Create folder
- `kctl-grafana folder delete <uid>` — Delete folder

#### `annotation` — Deploy/event markers
- `kctl-grafana annotation add <text> --tags <tags>` — Add annotation (for deploy markers)
- `kctl-grafana annotation list --from <time> --to <time>` — List recent annotations

#### `user` — User management
- `kctl-grafana user list` — List org users
- `kctl-grafana user add <email> --role <role>` — Add user to org

#### `backup` — Backup/restore
- `kctl-grafana backup create [--output <dir>]` — Export all dashboards + datasources
- `kctl-grafana backup restore <dir>` — Import from backup directory

#### `status` — Quick overview
- `kctl-grafana status` — Dashboard count, datasource health, active alerts, version

#### `selftest` — Self-test
- `kctl-grafana selftest` — Run diagnostic checks (API, datasources, folders)

### 2.4 ServiceConfig

```python
class ServiceConfig(BaseModel):
    url: str = ""                    # e.g., https://grafana.kodeme.io
    api_key: str = ""                # Grafana API token
    org_id: int = 1                  # Organization ID
```

---

## 3. kctl-sentry

**Repo:** `/home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-sentry`
**API:** Sentry REST API (Bearer token)
**Base URL:** configurable (e.g., `https://sentry.io` or self-hosted)
**Auth:** `Authorization: Bearer {auth_token}`

### 3.1 Client

```python
class SentryClient(APIClient):
    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"
    API_PREFIX = "/api/0"
```

### 3.2 Commands

#### `health` — API connectivity
- `kctl-sentry health` — Check API, org info, rate limits

#### `issues` — Error triage (daily use)
- `kctl-sentry issues list [--project <name>] [--status unresolved]` — Recent errors
- `kctl-sentry issues show <id>` — Error details, stack trace, affected users
- `kctl-sentry issues resolve <id> [--release <version>]` — Mark as fixed
- `kctl-sentry issues ignore <id> [--duration <time>]` — Suppress noise
- `kctl-sentry issues bulk-resolve --project <name> --before <date>` — Batch resolve old errors
- `kctl-sentry issues assign <id> --to <user>` — Assign to team member

#### `projects` — Project management
- `kctl-sentry projects list` — All projects with issue counts
- `kctl-sentry projects show <slug>` — Project details
- `kctl-sentry projects dsn <slug>` — Get DSN key for SDK configuration
- `kctl-sentry projects create <name> --team <team>` — New project

#### `releases` — Release tracking
- `kctl-sentry releases list [--project <name>]` — Recent releases
- `kctl-sentry releases create <version> --project <name>` — Tag a release
- `kctl-sentry releases show <version>` — Release details + associated issues
- `kctl-sentry releases associate <version> --commits <repo>@<from>..<to>` — Link commits

#### `alerts` — Alert rules
- `kctl-sentry alerts list [--project <name>]` — Alert rules
- `kctl-sentry alerts show <id>` — Alert details + trigger history
- `kctl-sentry alerts create --project <name> --metric <metric> --threshold <n>` — New alert

#### `stats` — Statistics
- `kctl-sentry stats events [--project <name>] [--period 24h]` — Event volume
- `kctl-sentry stats errors [--project <name>]` — Error rate trends

#### `teams` — Team management
- `kctl-sentry teams list` — List teams
- `kctl-sentry teams show <slug>` — Team members + projects

#### `environments` — Environment info
- `kctl-sentry environments list --project <name>` — List environments (prod, staging, dev)

#### `dashboard` — Quick overview
- `kctl-sentry dashboard` — Unresolved issues across projects, recent releases, alert status

### 3.3 ServiceConfig

```python
class ServiceConfig(BaseModel):
    url: str = "https://sentry.io"   # Base URL (self-hosted or cloud)
    auth_token: str = ""             # Auth token
    organization: str = ""           # Org slug (e.g., "kodemeio")
    default_project: str = ""        # Default project slug
```

---

## 4. kctl-github

**Repo:** `/home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-github`
**API:** GitHub REST API + `gh` CLI for some operations
**Base URL:** `https://api.github.com`
**Auth:** `Authorization: Bearer {token}` (Personal Access Token)

### 4.1 Design Principle

kctl-github is a **cross-repo management tool** for the 21 kodemeio-* repositories. Single-repo operations use `gh` CLI internally. The value-add is **aggregation and batch operations**.

### 4.2 Client

```python
class GitHubClient(APIClient):
    BASE_URL = "https://api.github.com"
    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"
```

Plus a helper for `gh` CLI subprocess calls:

```python
def gh_run(args: list[str]) -> str:
    """Run gh CLI command and return stdout."""
    result = run(["gh", *args])
    return result.stdout
```

### 4.3 Commands

#### `health` — API connectivity + rate limits
- `kctl-github health` — API status, rate limit remaining, token scopes

#### `repos` — Cross-repo overview
- `kctl-github repos list` — All kodemeio-* repos with visibility, default branch, last push
- `kctl-github repos status` — Aggregated: open PRs, failing CI, stale branches per repo
- `kctl-github repos show <name>` — Single repo details (size, languages, contributors)

#### `ci` — CI/CD monitoring
- `kctl-github ci status` — Latest workflow run status across ALL repos (pass/fail/running)
- `kctl-github ci show <repo>` — Workflow runs for a specific repo
- `kctl-github ci stats [--period 7d]` — CI statistics: success rate, avg duration, failure trends, most-failing workflows
- `kctl-github ci rerun <repo> [--workflow <name>]` — Re-trigger failed workflow
- `kctl-github ci bulk-status` — Table of all repos x workflows with pass/fail matrix

#### `prs` — Cross-repo PR management
- `kctl-github prs list` — Open PRs across all kodemeio-* repos
- `kctl-github prs show <repo> <number>` — PR details (delegates to `gh pr view`)
- `kctl-github prs stale [--days 14]` — PRs with no activity

#### `secrets` — Cross-repo secret management
- `kctl-github secrets list <repo>` — List action secrets for a repo
- `kctl-github secrets audit` — Check which repos have which secrets (matrix view)
- `kctl-github secrets set <name> --repos <repo1,repo2,...>` — Set secret across multiple repos
- `kctl-github secrets rotate <name>` — Update a secret across all repos that have it

#### `labels` — Cross-repo label standardization
- `kctl-github labels list <repo>` — Labels for a repo
- `kctl-github labels sync --source <repo>` — Copy labels from source repo to all others
- `kctl-github labels diff` — Show label differences across repos

#### `stats` — Repository statistics
- `kctl-github stats overview` — Total repos, total stars, total issues, total PRs
- `kctl-github stats activity [--period 30d]` — Commit activity, PR merge rate, issue velocity
- `kctl-github stats languages` — Language breakdown across all repos
- `kctl-github stats contributors` — Contributor activity

#### `billing` — Usage and billing
- `kctl-github billing actions` — Actions minutes used (this billing cycle)
- `kctl-github billing storage` — Git LFS + Packages storage usage
- `kctl-github billing packages` — Packages data transfer
- `kctl-github billing overview` — Combined billing summary + spending limits

#### `dashboard` — Quick overview
- `kctl-github dashboard` — Repos count, open PRs, failing CI, rate limits, billing summary

### 4.4 ServiceConfig

```python
class ServiceConfig(BaseModel):
    token: str = ""                  # GitHub PAT
    organization: str = "tgunawandev"  # Org/user
    repo_prefix: str = "kodemeio-"   # Filter repos by prefix
```

---

## 5. kctl-linear

**Repo:** `/home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-linear`
**API:** Linear GraphQL API
**Base URL:** `https://api.linear.app/graphql`
**Auth:** `Authorization: {api_key}` (no Bearer prefix)

### 5.1 Client

Linear uses GraphQL, not REST. The client does NOT subclass APIClient. Instead, it uses httpx directly with a `query()` method:

```python
class LinearClient:
    """GraphQL client for Linear API."""

    def __init__(self, api_key: str, timeout: float = 30.0):
        self._client = httpx.Client(
            base_url="https://api.linear.app",
            headers={"Authorization": api_key, "Content-Type": "application/json"},
            timeout=timeout,
        )

    def query(self, graphql: str, variables: dict | None = None) -> dict:
        response = self._client.post("/graphql", json={"query": graphql, "variables": variables or {}})
        data = response.json()
        if "errors" in data:
            raise APIError(detail=data["errors"][0]["message"])
        return data["data"]
```

### 5.2 Commands

#### `health` — API connectivity
- `kctl-linear health` — Check API, current user info

#### `issues` — Issue management (daily use)
- `kctl-linear issues list [--team <name>] [--state <state>] [--assignee me]` — Filter issues
- `kctl-linear issues show <id>` — Issue details, comments, history
- `kctl-linear issues create --title <title> --team <team> [--priority <1-4>] [--assignee <user>]` — New issue
- `kctl-linear issues update <id> [--state <state>] [--assignee <user>] [--priority <n>]` — Update issue
- `kctl-linear issues comment <id> --body <text>` — Add comment
- `kctl-linear issues search <query>` — Full-text search

#### `cycles` — Sprint management
- `kctl-linear cycles current [--team <name>]` — Current active cycle with progress
- `kctl-linear cycles list [--team <name>]` — Past and upcoming cycles
- `kctl-linear cycles show <id>` — Cycle details: scope, completed, remaining
- `kctl-linear cycles stats [--team <name>]` — Velocity trends

#### `projects` — Project tracking
- `kctl-linear projects list` — Active projects with progress %
- `kctl-linear projects show <id>` — Project details, milestones, member issues

#### `teams` — Team info
- `kctl-linear teams list` — All teams with member counts
- `kctl-linear teams show <name>` — Team members, workflow states, labels

#### `labels` — Label management
- `kctl-linear labels list [--team <name>]` — All labels
- `kctl-linear labels create <name> --color <hex>` — New label

#### `users` — User info
- `kctl-linear users list` — Workspace members
- `kctl-linear users me` — Current authenticated user

#### `dashboard` — Quick overview
- `kctl-linear dashboard` — My issues, current cycle progress, active projects

### 5.3 ServiceConfig

```python
class ServiceConfig(BaseModel):
    api_key: str = ""                # Linear API key
    default_team: str = ""           # Default team name/key
```

---

## 6. kctl-notion

**Repo:** `/home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-notion`
**API:** Notion REST API v1
**Base URL:** `https://api.notion.com/v1`
**Auth:** `Authorization: Bearer {token}` (internal integration token)

### 6.1 Client

```python
class NotionClient(APIClient):
    BASE_URL = "https://api.notion.com/v1"
    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"

    def _build_auth_header(self) -> dict[str, str]:
        headers = super()._build_auth_header()
        headers["Notion-Version"] = "2022-06-28"  # Required API version header
        return headers
```

### 6.2 Commands

#### `health` — API connectivity
- `kctl-notion health` — Check API, list accessible pages count

#### `search` — Global search
- `kctl-notion search <query> [--type page|database]` — Search across workspace

#### `pages` — Page management
- `kctl-notion pages list [--parent <id>]` — List pages (recently edited)
- `kctl-notion pages show <id>` — Page title, properties, content preview
- `kctl-notion pages create --parent <id> --title <title>` — New page
- `kctl-notion pages update <id> --title <title>` — Update page properties

#### `databases` — Database management
- `kctl-notion databases list` — List all databases
- `kctl-notion databases show <id>` — Database schema (properties, types)
- `kctl-notion databases query <id> [--filter <json>] [--sort <property>]` — Query rows
- `kctl-notion databases export <id> [--format csv|json]` — Export database to file

#### `blocks` — Content blocks
- `kctl-notion blocks list <page_id>` — List blocks in a page
- `kctl-notion blocks append <page_id> --text <content>` — Add paragraph to page

#### `users` — Workspace users
- `kctl-notion users list` — List workspace members
- `kctl-notion users me` — Current bot/integration user

### 6.3 ServiceConfig

```python
class ServiceConfig(BaseModel):
    token: str = ""                  # Internal integration token
```

---

## 7. Shared Patterns

All 5 CLIs follow these conventions from kctl-lib:

### Global Options
`--json`, `--quiet/-q`, `--format/-f` (pretty/json/csv/yaml), `--no-header`, `--profile/-p`, `--version/-V`

### Config Subcommands
All 9: init, add, use, show, validate, remove, set, profiles, current

### Entry Point
`cli:_run` with `handle_cli_error()`

### Output
- Tables for list commands (via `Output.table()`)
- Detail panels for show commands (via `Output.detail()`)
- JSON output when `--json` flag is set
- Success/error messages via `Output.success()`/`Output.error()`

### Dashboard Command
Each CLI has a `dashboard` command that gives a quick overview of the most important metrics for that service.

### Health Command
Each CLI has a `health` command that verifies API connectivity and reports version/org info.

### Testing
- Smoke tests (--help, --version)
- Config/client unit tests
- Command tests using pytest-httpx mocks

---

## 8. Implementation Order

1. **kctl-grafana** — Has existing shell scripts for reference. Daily monitoring use.
2. **kctl-sentry** — Error triage is critical. Clean REST API.
3. **kctl-github** — Cross-repo management. Mix of API + `gh` CLI.
4. **kctl-linear** — GraphQL client. Sprint tracking.
5. **kctl-notion** — Wiki access. Lowest frequency.

Each CLI is an independent sub-project: spec → plan → implement → review → push.

---

## 9. Out of Scope

- Building web UIs or dashboards
- Webhooks or event listeners
- Real-time streaming (SSE/WebSocket)
- Data migration between services
- Wrapping every API endpoint — only daily-use operations
- Authentication flows (OAuth) — all use pre-configured tokens
