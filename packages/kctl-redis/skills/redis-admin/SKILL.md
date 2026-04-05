---
name: redis-admin
description: >
  Redis server administration via kctl-redis CLI (17 groups, ~62 commands).
  MUST use for ANY kctl-redis operation.
  Triggers on: "aof-status", "backup", "bgrewriteaof", "bgsave", "big-keys", "channels", "check", "clients", "config", "config-get", "config-rewrite", "config-set", "consumers", "current", "dashboard", "db", "defrag", "dump", "eviction", "exec", "flush", "fragmentation", "generate", "groups", "health", "hit-ratio", "info", "init", "kctl-redis", "keys", "kill", "latency", "maintenance", "memory", "memory-purge", "memory-usage", "monitor", "numsub", "ops-sec", "pending", "performance", "persistence", "ping", "profile", "profiles", "promote", "publish", "pubsub", "query", "rdb-status", "remove", "rename", "replication", "restore", "scan", "server", "size", "skill", "slowlog", "stats", "streams", "swap", "test", "trim", "type".
  Auto-generated: 2026-04-05
  registry_hash: fba5f3211d47
---

# redis-admin — kctl-redis CLI Reference

> Auto-generated from `kctl-redis` command registry. Do not edit manually.
> To regenerate: `kctl-redis skill generate`
> To add custom content: edit `SKILL.extra.md` in the same directory.

## Overview

**CLI:** `kctl-redis`
**Command groups:** 17
**Total commands:** ~62
**Install:** `cd cli && uv tool install --editable .`

## Global Options

| Flag | Description |
|------|-------------|
| `--json` | JSON output |
| `--quiet`, `-q` | Suppress info messages |
| `--format`, `-f` | Output format: pretty/json/csv/yaml |
| `--no-header` | Omit CSV header row |
| `--profile`, `-p` | Config profile name |
| `--version`, `-V` | Show version |

## Command Reference

### `kctl-redis backup`

Redis backup operations via SSH.

| Command | Description |
|---------|-------------|
| `backup dump [--output_path]` | Trigger BGSAVE and download the RDB file. |
| `backup list [--remote_dir]` | List backup files on the remote server. |
| `backup restore <file_path>` | Upload an RDB file to the server. |

### `kctl-redis clients`

Redis client management.

| Command | Description |
|---------|-------------|
| `clients info` | Show client connection info. |
| `clients kill <client_id>` | Kill a client connection by ID. |
| `clients list` | List connected clients. |

### `kctl-redis config`

Manage kctl-redis configuration profiles.

| Command | Description |
|---------|-------------|
| `config add <profile> [--host] [--port] [--username] [--password] [--db] [--ssh_host] [--ssh_port] [--ssh_user] [--ssh_key]` | Add or update a profile. |
| `config current` | Show the active profile name. |
| `config init [--profile] [--host] [--port] [--username] [--password] [--db] [--ssh_host] [--ssh_port] [--ssh_user] [--ssh_key]` | Initialize kctl-redis configuration. |
| `config profiles` | List all profiles. |
| `config remove <profile> [--force]` | Remove a profile. |
| `config set <key> <value>` | Set a configuration value. |
| `config show` | Show current configuration (passwords masked). |
| `config test` | Test Redis connection. |
| `config use <profile>` | Switch the default profile. |

### `kctl-redis dashboard`

Redis system overview.

### `kctl-redis db`

Redis database operations.

| Command | Description |
|---------|-------------|
| `db flush [--force] [--async_mode]` | Flush current database (delete all keys). |
| `db list` | List databases with key counts. |
| `db size` | Show key count for current database. |
| `db swap <db1> <db2>` | Swap two databases. |

### `kctl-redis health`

Redis health checks.

| Command | Description |
|---------|-------------|
| `health check [--memory_warn] [--memory_crit] [--clients_warn]` | Run health threshold checks. |
| `health info` | Show Redis server info summary. |
| `health ping` | Ping Redis and measure latency. |

### `kctl-redis keys`

Redis key management.

| Command | Description |
|---------|-------------|
| `keys delete <key> [--force]` | Delete a key. |
| `keys get <key>` | Get value of a key (auto-detects type). |
| `keys memory-usage <key>` | Show memory usage of a key. |
| `keys rename <old_key> <new_key>` | Rename a key. |
| `keys scan [--pattern] [--count] [--key_type] [--limit]` | Scan keys matching a pattern. |
| `keys ttl <key> [--precise]` | Show time-to-live for a key. |
| `keys type <key>` | Show key type and encoding. |

### `kctl-redis maintenance`

Redis maintenance operations.

| Command | Description |
|---------|-------------|
| `maintenance config-rewrite` | Persist runtime configuration to redis.conf. |
| `maintenance defrag` | Check and enable active defragmentation. |
| `maintenance memory-purge` | Release memory back to the OS. |

### `kctl-redis memory`

Redis memory analysis.

| Command | Description |
|---------|-------------|
| `memory big-keys [--count] [--limit]` | Find largest keys by memory usage. |
| `memory eviction` | Show eviction policy and stats. |
| `memory fragmentation` | Show memory fragmentation and recommendation. |
| `memory stats` | Show memory statistics. |

### `kctl-redis performance`

Redis performance monitoring.

| Command | Description |
|---------|-------------|
| `performance hit-ratio` | Show keyspace hit ratio. |
| `performance latency` | Show latency monitoring data. |
| `performance ops-sec` | Show current operations per second. |
| `performance slowlog [--count]` | Show slow log entries. |

### `kctl-redis persistence`

Redis persistence management.

| Command | Description |
|---------|-------------|
| `persistence aof-status` | Show AOF persistence status. |
| `persistence bgrewriteaof` | Trigger AOF rewrite. |
| `persistence bgsave` | Trigger a background RDB save. |
| `persistence rdb-status` | Show RDB persistence status. |

### `kctl-redis pubsub`

Redis Pub/Sub operations.

| Command | Description |
|---------|-------------|
| `pubsub channels [--pattern]` | List active Pub/Sub channels. |
| `pubsub numsub <channel_names>` | Show subscriber counts for channels. |
| `pubsub publish <channel> <message>` | Publish a message to a channel. |

### `kctl-redis query`

Execute raw Redis commands.

| Command | Description |
|---------|-------------|
| `query exec <command>` | Execute a raw Redis command. |

### `kctl-redis replication`

Redis replication management.

| Command | Description |
|---------|-------------|
| `replication info` | Show replication info. |
| `replication lag` | Show replication lag for replicas. |
| `replication promote` | Promote this replica to master (REPLICAOF NO ONE). |

### `kctl-redis server`

Redis server management.

| Command | Description |
|---------|-------------|
| `server acl [--user]` | List ACL users or show user details. |
| `server config-get [--pattern]` | Get Redis configuration parameters. |
| `server config-set <parameter> <value>` | Set a Redis configuration parameter at runtime. |
| `server info [--section]` | Show Redis INFO output. |

### `kctl-redis skill`

Claude Code skill management.

| Command | Description |
|---------|-------------|
| `skill generate [--output] [--install] [--check]` | Auto-generate SKILL.md from CLI command registry. |

**Examples:**
```bash
kctl-redis skill generate
kctl-redis skill generate --install
kctl-redis skill generate --check
```

### `kctl-redis streams`

Redis Streams operations.

| Command | Description |
|---------|-------------|
| `streams consumers <key> <group>` | Show consumers in a group. |
| `streams groups <key>` | Show consumer groups for a stream. |
| `streams info <key>` | Show stream information. |
| `streams pending <key> <group> [--count]` | Show pending messages for a consumer group. |
| `streams trim <key> [--maxlen] [--minid] [--approximate]` | Trim a stream. |

## Configuration

Shared config: `~/.config/kodemeio/config.yaml`

```bash
kctl-redis config init       # Interactive setup
kctl-redis config show       # Show current config
kctl-redis config profiles   # List profiles
kctl-redis config current    # Show active profile
kctl-redis config validate   # Verify config
```
