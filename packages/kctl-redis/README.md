# kctl-redis

Kodemeio Redis CLI — manage Redis servers via SSH tunnel.

## Installation

```bash
uv tool install kctl-redis
# or within the workspace
uv sync --all-packages
```

## Quick Start

```bash
# Initialize a profile
kctl-redis config init --profile production

# Test the connection
kctl-redis config validate

# Check health
kctl-redis health ping

# Live dashboard
kctl-redis dashboard overview

# Scan keys
kctl-redis keys scan --pattern "session:*"

# Run a raw command
kctl-redis query run GET mykey
```

## Command Groups

| Group | Description | Commands |
|-------|-------------|----------|
| `config` | Profile management (init, add, use, show, validate, remove, set, profiles, current) | 9 |
| `health` | Ping, latency check, info summary | 3 |
| `dashboard` | Live server overview | 1 |
| `query` | Execute raw Redis commands | 1 |
| `keys` | Scan, get, set, delete, TTL, type, rename | 7 |
| `db` | List databases, flush, select, move keys | 4 |
| `memory` | Memory stats, usage by key, doctor, purge | 4 |
| `clients` | List clients, kill, info | 3 |
| `server` | Get/set config, save config, reset stats | 4 |
| `persistence` | RDB status, AOF status, BGSAVE, BGREWRITEAOF | 4 |
| `replication` | Replication info, promote replica, reset | 3 |
| `pubsub` | List channels, subscribers, numsub | 3 |
| `streams` | Stream info, read, trim, delete, groups | 5 |
| `performance` | Slow log, latency history, command stats, monitor | 4 |
| `backup` | Dump RDB via SSH, restore, list backups | 3 |
| `maintenance` | Memory purge, defrag check, flush expired | 3 |

**Total: 61 commands**

## Global Options

```
--json              Output as JSON
--quiet / -q        Suppress info messages
--profile / -p      Config profile name
--host / -H         Redis host override
--port              Redis port override
--user / -U         Redis username override
--password          Redis password override
--db                Redis database number override
--version / -V      Show version
```

## Configuration

Config is stored in `~/.config/kodemeio/config.yaml` under the `redis` service key.

```yaml
profiles:
  production:
    redis:
      host: 10.0.0.5          # Redis host (internal, accessed via SSH tunnel)
      port: 6379
      username: default
      password: ${REDIS_PASSWORD}
      db: 0
      ssh_host: 49.13.14.79   # Jump host IP
      ssh_port: 22
      ssh_user: root
      ssh_key: ~/.ssh/id_ed25519
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `KCTL_REDIS_HOST` | Redis host |
| `KCTL_REDIS_PORT` | Redis port |
| `KCTL_REDIS_USERNAME` | Redis username |
| `KCTL_REDIS_PASSWORD` | Redis password |
| `KCTL_REDIS_SSH_HOST` | SSH tunnel host |
| `KCTL_REDIS_DB` | Redis database number |
| `REDIS_HOST` / `REDIS_PORT` | Standard Redis env vars (lower priority) |

Resolution order (highest to lowest): CLI flags > `KCTL_REDIS_*` env vars > `REDIS_*` env vars > config file profile.

### Profile Management

```bash
kctl-redis config init --profile production
kctl-redis config add --profile staging --host 10.0.0.6 --ssh-host 1.2.3.4
kctl-redis config use production
kctl-redis config show
kctl-redis config profiles
```

## Development

```bash
cd packages/kctl-redis
uv sync --all-extras
uv run pytest tests/ -v
uv run ruff check src/
uv run mypy src/
```
