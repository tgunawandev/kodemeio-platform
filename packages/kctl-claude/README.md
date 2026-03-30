# kctl-claude

Kodemeio Claude Code CLI — manage local and remote Claude Code environments.

## Installation

```bash
uv tool install .
```

## Quick Start

```bash
kctl-claude config init
kctl-claude status
kctl-claude doctor
kctl-claude env list
```

## Commands

| Group | Description |
|-------|-------------|
| `config` | Profile and connection management |
| `api` | Claude API key and SDK management |
| `backup` | Configuration backup and restore |
| `doctor` | Diagnostic checks |
| `env` | Environment and settings management |
| `setup` | Initial setup and onboarding |
| `status` | Environment status overview |
| `sync` | Config sync across machines |
| `verify` | Installation and config verification |

## Development

```bash
uv run pytest tests/ -v
uv run ruff check src/
uv run mypy src/
```
