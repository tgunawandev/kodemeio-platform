# kctl-rustdesk

Kodemeio RustDesk CLI — manage RustDesk server infrastructure.

## Installation

```bash
uv tool install .
```

## Quick Start

```bash
kctl-rustdesk config init
kctl-rustdesk health
kctl-rustdesk dashboard
kctl-rustdesk peers list
```

## Commands

| Group | Description |
|-------|-------------|
| `config` | Profile and connection management |
| `audit` | Audit log inspection |
| `backup` | Server backup operations |
| `dashboard` | Server overview and statistics |
| `health` | Health checks |
| `maintenance` | Server maintenance tasks |
| `peers` | Peer/device management |
| `setup` | Initial server setup |
| `users` | User management |

## Development

```bash
uv run pytest tests/ -v
uv run ruff check src/
uv run mypy src/
```
