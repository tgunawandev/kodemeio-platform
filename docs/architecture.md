# Kodemeio Platform Architecture

## CLI Ecosystem

5 CLI tools sharing `kctl-common`:

| CLI | Repo | Target | Groups |
|-----|------|--------|--------|
| kctl-next | kodemeio-next | Next.js monorepo (4 apps) | 24 |
| kctl-odoo | kodemeio-odoo | Odoo 18 ERP (96 modules) | 53 |
| kctl-react | kodemeio-react | React PWA monorepo (11 apps) | 17 |
| kctl-api | kodemeio-fastapi | FastAPI platform | 32 |
| kctl-claw | kodemeio-openclaw | AI agent gateway | 16 |

## Shared Config

All CLIs share `~/.config/kodemeio/config.yaml` with service-scoped profiles:

```yaml
default_profile: default
profiles:
  default:
    next:  { project_root: /path/to/kodemeio-next }
    odoo:  { url: https://erp.kodeme.io, database: kodemeio }
    react: { project_root: /path/to/kodemeio-react }
    api:   { url: https://api.kodeme.io }
    claw:  { project_root: /path/to/kodemeio-openclaw }
```

## Dependency Flow

```
kctl-common (PyPI)
  ├── kctl-next
  ├── kctl-odoo
  ├── kctl-react
  ├── kctl-api
  └── kctl-claw
```
