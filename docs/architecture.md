# Kodemeio Platform Architecture

## CLI Ecosystem

5 CLI tools sharing `kctl-common`:

| CLI | Repo | Target | Groups |
|-----|------|--------|--------|
| kctl-next | kodemeio-next | Next.js monorepo (4 apps) | 35 |
| kctl-odoo | kodemeio-odoo | Odoo 18 ERP (96 modules) | 70 |
| kctl-react | kodemeio-react | React PWA monorepo (11 apps) | 31 |
| kctl-api | kodemeio-fastapi | FastAPI platform | 46 |
| kctl-claw | kodemeio-openclaw | AI agent gateway | 29 |

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

## API Client Base Classes

CLIs that interact with HTTP APIs subclass `APIClient` (sync) or `AsyncAPIClient` (async) from `kctl-common`. These base classes provide authentication, retry with exponential backoff, error mapping, and debug logging.

### Class Attributes

| Attribute | Default | Purpose |
|-----------|---------|---------|
| `AUTH_HEADER` | `"Authorization"` | HTTP header name for credentials |
| `AUTH_PREFIX` | `"Bearer"` | Prefix before the credential value (empty for raw tokens) |
| `API_PREFIX` | `""` | URL path prefix appended to base URL (e.g., `/v1`) |
| `BASE_URL` | `""` | Default base URL if not passed at init |

### Override Hooks

| Method | Purpose |
|--------|---------|
| `_unwrap_response(response)` | Parse/unwrap response body. Override for envelope APIs (e.g., Cloudflare wraps results in `{"result": ...}`) |
| `_map_error(response)` | Extract human-readable error detail from error responses |
| `_is_retryable(response)` | Determine if a failed response should be retried (beyond the default 5xx check) |

### Example Subclass

```python
from kctl_common.api_client import APIClient

class CloudflareClient(APIClient):
    BASE_URL = "https://api.cloudflare.com"
    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"
    API_PREFIX = "/client/v4"

    def _unwrap_response(self, response):
        data = response.json()
        return data.get("result", data)
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
