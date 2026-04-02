# kctl-github

Command reference for `kctl-github` (10 groups, ~38 commands).

> Auto-generated on 2026-04-02. Do not edit manually.
> Regenerate with: `uv run python scripts/generate-cli-docs.py`

## Global Options

| Flag | Description |
|------|-------------|
| `--json` | JSON output |
| `--quiet`, `-q` | Suppress info messages |
| `--format`, `-f` | Output format: pretty/json/csv/yaml |
| `--no-header` | Omit headers in CSV output |
| `--profile`, `-p` | Config profile name |
| `--version`, `-V` | Show version |

## Commands

### `kctl-github billing`

GitHub Actions billing and usage.

| Command | Description |
|---------|-------------|
| `billing actions` | Actions minutes used this billing cycle. |
| `billing overview` | Combined billing summary. |
| `billing packages` | Packages data transfer. |
| `billing storage` | Git LFS + Packages storage usage. |

### `kctl-github ci`

CI/CD monitoring across kodemeio-* repositories.

| Command | Description |
|---------|-------------|
| `ci bulk-status` | Table of all repos x workflows with pass/fail matrix. |
| `ci rerun <repo> [--workflow]` | Re-trigger the latest failed workflow run. |
| `ci show <repo> [--limit]` | Show workflow runs for a specific repo. |
| `ci stats [--period]` | CI statistics: success rate, avg duration, failure trends. |
| `ci status` | Latest workflow run status across ALL repos (pass/fail/running). |

### `kctl-github config`

Profile and configuration management.

| Command | Description |
|---------|-------------|
| `config add <name>` | Add a new config profile. |
| `config current` | Show active profile and resolved context. |
| `config init` | Interactive config setup. |
| `config profiles` | List all config profiles. |
| `config remove <name>` | Remove a config profile. |
| `config set <key> <value>` | Set a single config value. |
| `config show` | Show current configuration. |
| `config test` | Test API connection with current configuration. |
| `config use <name>` | Switch active config profile. |
| `config validate` | Validate current config completeness. |

### `kctl-github dashboard`

Quick overview dashboard.

### `kctl-github health`

API connectivity and rate limits.

### `kctl-github labels`

Cross-repo label management.

| Command | Description |
|---------|-------------|
| `labels diff` | Show label differences across repos. |
| `labels list <repo>` | List labels for a repo. |
| `labels sync <source>` | Copy labels from source repo to all other kodemeio-* repos. |

### `kctl-github prs`

Cross-repo PR management.

| Command | Description |
|---------|-------------|
| `prs list` | Open PRs across all kodemeio-* repos. |
| `prs show <repo> <number>` | Show PR details (delegates to gh pr view). |
| `prs stale [--days]` | Find PRs with no activity for N days. |

### `kctl-github repos`

Cross-repo overview for kodemeio-* repositories.

| Command | Description |
|---------|-------------|
| `repos list` | List all kodemeio-* repos with visibility, default branch, last push. |
| `repos show <name>` | Show single repo details (size, languages, contributors). |
| `repos status` | Aggregated status: open PRs, failing CI, stale branches per repo. |

### `kctl-github secrets`

Cross-repo Actions secret management.

| Command | Description |
|---------|-------------|
| `secrets audit` | Check which repos have which secrets (matrix view). |
| `secrets list <repo>` | List Actions secrets for a repo. |
| `secrets rotate <name>` | Update a secret across all repos that have it. |
| `secrets set <name> <repos>` | Set a secret across multiple repos (prompts for value). |

### `kctl-github stats`

Repository statistics across kodemeio-* repos.

| Command | Description |
|---------|-------------|
| `stats activity [--period]` | Commit activity, PR merge rate, issue velocity. |
| `stats contributors` | Contributor activity across all repos. |
| `stats languages` | Language breakdown across all repos. |
| `stats overview` | Total repos, total stars, total issues, total PRs. |
