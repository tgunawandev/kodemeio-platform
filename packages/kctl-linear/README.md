# kctl-linear

Linear project and sprint tracking CLI. Uses the Linear GraphQL API.

## Installation

```bash
uv tool install kctl-linear
# or editable install for development
uv tool install --editable packages/kctl-linear
```

## Quick Start

```bash
# Configure
kctl-linear config init
kctl-linear config show

# Common workflows
kctl-linear dashboard                    # Overview: issues, cycles, projects
kctl-linear issues list                  # List all issues
kctl-linear issues search "bug login"    # Search issues by keyword
kctl-linear issues create               # Create a new issue
kctl-linear cycles current              # Active sprint details
kctl-linear projects list               # List all projects
```

## Command Groups

| Group       | Subcommands                          | Description                        |
|-------------|--------------------------------------|------------------------------------|
| `config`    | init, add, use, show, validate, ...  | Profile and API key management     |
| `dashboard` | (root)                               | Summary view of issues and sprints |
| `issues`    | list, show, create, update, comment, search | Issue lifecycle management  |
| `cycles`    | list, show, current, stats           | Sprint / cycle tracking            |
| `projects`  | list, show                           | Project listing and details        |
| `teams`     | list, show                           | Team membership and info           |
| `labels`    | list, create                         | Issue label management             |
| `users`     | list, me                             | Workspace user listing             |
| `health`    | check                                | API connectivity check             |

## Configuration

Config is stored in `~/.config/kodemeio/config.yaml` under the `linear` key.

```bash
kctl-linear config init          # Interactive setup (API key, workspace)
kctl-linear config add myprofile # Add a named profile
kctl-linear config use myprofile # Switch active profile
kctl-linear config show          # Display current config (secrets masked)
```

Required fields: `api_key`, `team_id` (optional default team).

## Global Options

`--json`, `--format/-f` (pretty/json/csv/yaml), `--quiet/-q`, `--profile/-p`, `--no-header`, `--version/-V`

## Development

```bash
cd packages/kctl-linear
uv sync --all-extras
uv run pytest tests/ -v
uv run mypy src/
uv run ruff check src/
```
