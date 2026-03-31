# kctl-ak

Kodemeio Authentik CLI -- manage your Authentik identity provider from the command line.

## Install

```bash
uv pip install -e .
```

## Quick Start

```bash
kctl-ak config init
kctl-ak health
kctl-ak users list
kctl-ak users provision user@kodeme.io basic-user
```

## Command Groups (24)

| Group | Description |
|-------|-------------|
| `users` | User management, provisioning, bulk invite/import |
| `groups` | Group management, hierarchy, sync from YAML |
| `apps` | Application management, audit, orphaned detection |
| `providers` | OAuth2, LDAP, SAML, Proxy provider management |
| `flows` | Authentication flow management |
| `audit` | Event log, login tracking, suspicious event detection |
| `sessions` | Authenticated session management |
| `tokens` | API token management, rotation |
| `blueprints` | Blueprint management |
| `maintenance` | System maintenance and administration |
| `setup` | Setup wizards (OAuth2, Proxy, admin, recovery) |
| `health` | Health checks and diagnostics |
| `dashboard` | System overview with security view |
| `config` | CLI configuration and profiles |
| `mail` | Email operations via SMTP |
| `policies` | Policy management and testing |
| `stages` | Stage management (prompt, password, identification, etc.) |
| `property-mappings` | Property mapping management (OAuth2, SAML, LDAP, SCIM) |
| `certificates` | Certificate and key pair management |
| `outposts` | Outpost instance and service connection management |
| `brands` | Brand/tenant management |
| `notifications` | Notification rules and transports |
| `system` | System settings, impersonation, token defaults, event retention |

## Role-Based Provisioning

```bash
kctl-ak users roles                    # List available roles
kctl-ak users roles --verify           # Check groups exist in Authentik
kctl-ak users provision user@example.com basic-user devops
```

| Role | Description |
|------|-------------|
| `admin` | Full IT admin (all apps + superuser) |
| `basic-user` | Standard employee (Mattermost) |
| `office-user` | Office worker (Mattermost + Grafana) |
| `erp-user` | ERP access (Mattermost + Odoo) |
| `devops` | DevOps engineer (Grafana admin + N8N + monitoring) |
| `mattermost-user` | Chat only |

## Group Sync

```bash
kctl-ak groups sync --dry-run          # Preview from group-structure.yaml
kctl-ak groups sync --no-dry-run       # Create missing groups
```

## Security

```bash
kctl-ak dashboard --security           # Security-focused overview
kctl-ak audit suspicious               # Failed logins, privilege changes
kctl-ak system impersonation off       # Disable impersonation
```

## Development

```bash
uv sync --all-extras
uv run pytest tests/ -v                # 166 tests
uv run ruff check src/
uv run mypy src/
```

## Dependencies

- Python >= 3.12
- `kctl-lib >= 0.4.0` (shared CLI infrastructure)
- Typer + Rich + Pydantic 2 + httpx
