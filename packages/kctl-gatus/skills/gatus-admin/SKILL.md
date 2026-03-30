---
name: gatus-admin
description: >
  Gatus health monitoring administration via kctl-gatus CLI. MUST use for ANY uptime monitoring, health check configuration, or alert management. Triggers on: "kctl-gatus", "gatus", "uptime monitor", "health endpoint", "alert channel", "response time", "health check status", "monitoring dashboard", or ANY health monitoring task.
version: 1.0.0
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# Gatus Administration

## Managed Instances

kctl-gatus supports multiple Gatus instances via profiles:

| Profile | URL | Use |
|---|---|---|
| `kodemeio` | https://gatus.kodeme.io | Kodemeio infrastructure monitoring |

```bash
# Target a specific instance
kctl-gatus -p kodemeio endpoints list
kctl-gatus -p kodemeio health check

# Switch default profile
kctl-gatus config use kodemeio
```

Config: `~/.config/kodemeio/config.yaml`

## CLI Tool: kctl-gatus

Installed globally via `uv tool install ./cli`. Run `kctl-gatus` from anywhere.

### Global Options

```bash
kctl-gatus [--json] [--quiet] [--profile NAME] [--url URL] [--api-key KEY] <command>
```

- `--profile / -p`: target a specific Gatus instance
- `--url`: override Gatus base URL
- `--api-key`: override API key
- `--json`: output as JSON (for scripting/piping)
- `--quiet / -q`: suppress info messages

## Multi-Instance Management

```bash
kctl-gatus config init                                            # Interactive setup
kctl-gatus config add <name> --url <url> [--api-key KEY]          # Add/update profile
kctl-gatus config use <name>                                      # Switch default
kctl-gatus config remove <name> [--service-only] [--force]        # Remove profile
kctl-gatus config profiles                                        # List all with status
kctl-gatus config current                                         # Show active + connection
kctl-gatus config show                                            # Full config (masked)
kctl-gatus config set <key> <value>                               # Edit config (url, api_key, default_profile)
kctl-gatus config test                                            # Test connection
kctl-gatus config migrate                                         # Migrate flat -> scoped format
```

Each profile can have its own: url, api_key. API key is optional (Gatus may not require auth).

## Endpoint Management

```bash
kctl-gatus endpoints list                                         # All endpoints with status
kctl-gatus endpoints get <key>                                    # Detailed status for one endpoint
kctl-gatus endpoints uptime <key> [--duration 7d|30d|1y]          # Uptime data
kctl-gatus endpoints response-time <key> [--duration 7d|30d|1y]   # Response time data
kctl-gatus endpoints search <query>                               # Search by name/group/key
```

Endpoint keys follow the format: `group_endpoint-name` (e.g. `auto-dokploy_my-service`).

## Results & History

```bash
kctl-gatus results list <key> [--limit N]                         # Recent check results
kctl-gatus results summary                                        # Overall up/down/unknown counts by group
```

## Alert Management

```bash
kctl-gatus alerts test [CHANNEL] [--telegram-token T] [--telegram-chat-id ID] [--mattermost-webhook URL] [--smtp-host H] [--smtp-port P]
kctl-gatus alerts history                                         # Recent failed checks (alert triggers)
```

### Alert Channels
- `telegram` -- requires `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
- `mattermost` -- requires `MATTERMOST_WEBHOOK_URL`
- `smtp` -- requires `SMTP_HOST` (connectivity test only)
- `all` -- test all channels (default)

Environment variables can be used instead of CLI flags.

## Discovery Sidecar

Manages the auto-discovery sidecar that detects Dokploy-deployed services.

```bash
kctl-gatus discovery status                                       # Sidecar health + endpoint counts
kctl-gatus discovery config                                       # Show endpoint groups and discovered services
kctl-gatus discovery trigger [--container NAME] [--compose-file F] # Restart sidecar for re-discovery
kctl-gatus discovery endpoints                                    # List only auto-discovered endpoints (group: auto-dokploy)
```

### Discovery Architecture
- The sidecar queries the Dokploy API to discover all active domains
- Auto-discovered endpoints appear in the `auto-dokploy` group
- Core (manually configured) endpoints have other group names
- Re-discovery runs every `DISCOVERY_INTERVAL` seconds (default 300)
- Use `discovery trigger` to force an immediate re-discovery

## Health Check

```bash
kctl-gatus health check                                           # API health + endpoint summary
kctl-gatus health dashboard                                       # Rich table: all endpoints with uptime and response times
```

Exit codes for `health check`:
- `0` -- healthy, all endpoints up
- `1` -- Gatus API unhealthy
- `2` -- some endpoints are down

## Dashboard

```bash
kctl-gatus dashboard overview                                     # Comprehensive view: groups, worst performers, down endpoints
```

Shows: total endpoints, up/down/unknown counts, group breakdown with up/total ratios, worst performers ranked by success rate, and currently down endpoints.

## API Structure

Gatus exposes a read-only REST API (no authentication required by default):

```
GET /api/v1/endpoints/statuses                  # All endpoint statuses with results
GET /api/v1/endpoints/{key}/statuses            # Single endpoint status
GET /api/v1/endpoints/{key}/uptimes/{duration}  # Uptime data (7d, 30d, 1y)
GET /api/v1/endpoints/{key}/response-times/{duration}  # Response time data
GET /api/v1/endpoints/statuses?page=N           # Paginated results
GET /health                                     # Health probe (200 = OK)
```

## Troubleshooting

### Cannot connect to Gatus
1. `kctl-gatus config test` -- verify URL and connectivity
2. `kctl-gatus health check` -- check API health
3. Verify Gatus is running: `docker compose -f docker-compose.prod.yml --env-file .env.prod ps`

### No endpoints showing
1. `kctl-gatus discovery status` -- check if discovery sidecar is active
2. `kctl-gatus discovery trigger` -- force a re-discovery run
3. Check Gatus config: the sidecar writes to `/config/config.yaml`

### Endpoints showing as DOWN
1. `kctl-gatus endpoints get <key>` -- check condition results
2. `kctl-gatus results list <key>` -- review recent check history
3. `kctl-gatus alerts history` -- see all failed checks

### Auto-discovery not finding services
1. `kctl-gatus discovery config` -- see current endpoint groups
2. Check `gatus-init/config.yml` for pattern matching rules
3. Check `gatus-init/exclude.yml` for exclusion patterns
4. Verify Dokploy API credentials in `.env.prod`

### Alert channels not working
1. `kctl-gatus alerts test telegram` -- test individual channel
2. `kctl-gatus alerts test all` -- test all channels
3. Check environment variables: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `MATTERMOST_WEBHOOK_URL`

### Working with multiple instances
1. `kctl-gatus config profiles` -- see all instances
2. `kctl-gatus -p <name> <command>` -- target specific instance
3. `kctl-gatus config use <name>` -- switch default
