# kctl-op

Kodemeio 1Password CLI — secret management and .env sync.

## Installation

```bash
uv tool install .
```

## Quick Start

```bash
kctl-op config init
kctl-op health
kctl-op vault list
kctl-op sync pull
```

## Commands

| Group | Description |
|-------|-------------|
| `config` | Profile and connection management |
| `health` | 1Password CLI connectivity checks |
| `vault` | Vault listing and management |
| `projects` | Project-scoped secret management |
| `sync` | Push/pull .env files to/from 1Password |
| `diff` | Compare local .env with vault secrets |
| `discover` | Discover .env files in project directories |
| `backup` | Vault backup operations |
| `status` | Secret sync status overview |

## Development

```bash
uv run pytest tests/ -v
uv run ruff check src/
uv run mypy src/
```
