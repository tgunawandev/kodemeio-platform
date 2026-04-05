# kctl-notion

Notion workspace management CLI — part of the kodemeio-platform toolchain.

## Installation

```bash
uv tool install kctl-notion
# or in development:
cd packages/kctl-notion && uv tool install --editable .
```

## Quick Start

```bash
# Configure credentials
kctl-notion config init
kctl-notion config show

# Search across workspace
kctl-notion search "sprint planning"

# Work with pages
kctl-notion pages list
kctl-notion pages show <page-id>
kctl-notion pages create --title "My Page" --parent <parent-id>

# Query a database
kctl-notion databases list
kctl-notion databases query <db-id>
```

## Command Groups

| Group       | Commands                        | Description                        |
|-------------|---------------------------------|------------------------------------|
| `config`    | init, add, use, show, validate, remove, set, profiles, current | Profile management |
| `health`    | health                          | API connectivity check             |
| `search`    | search                          | Full-text search across workspace  |
| `pages`     | list, show, create, update      | Page management                    |
| `databases` | list, show, query, export       | Database management                |
| `blocks`    | list, append                    | Content block management           |
| `users`     | list, me                        | Workspace user management          |

## Configuration

Config lives in `~/.config/kodemeio/config.yaml` under the `notion` service key.

```bash
kctl-notion config init          # Interactive setup (API key + workspace)
kctl-notion config add staging   # Add a second profile
kctl-notion config use staging   # Switch active profile
```

Required fields: `api_key`, `workspace_id` (optional for most commands).

## Global Options

`--json`, `--format pretty|json|csv|yaml`, `--quiet/-q`, `--no-header`, `--profile/-p`, `--version/-V`

## Development

```bash
cd packages/kctl-notion
uv sync --all-extras
uv run pytest tests/ -v
uv run mypy src/
uv run ruff check src/
```
