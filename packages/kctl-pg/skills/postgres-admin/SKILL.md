---
name: postgres-admin
description: >
  PostgreSQL server administration for kodemeio infrastructure via kctl-pg CLI. MUST use before ANY kctl-pg command or PostgreSQL admin task. Triggers on: "kctl-pg", "database backup", "create database", "postgres role", "db health", "pg stats", "database size", "restore database", "postgres user", "connection pool", or ANY PostgreSQL administration task. Even if the user just says "check db health" or "create a new database" — use this skill.
version: 1.0.0
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# PostgreSQL Administration for Kodemeio

## System Overview

- **PostgreSQL 16.12** at `db.kodeme.io` (Hetzner private network `10.0.0.3`)
- **PostGIS 3.5** (Alpine-based custom Docker image)
- **PgBouncer** for transaction-level connection pooling (port 6432)
- **postgres-exporter** for Prometheus metrics (port 9187)
- **Deployed**: Dokploy on `dokploy.kodeme.io` with `dokploy-network`
- **SSH access**: `root@db.kodeme.io` (public IP: 49.13.14.79)
- **Connection**: SSH tunnel -> Docker port mapping -> PostgreSQL container

## Production Databases

| Database | Owner | Size | Purpose |
|---|---|---|---|
| authentik | authentik | 87 MB | Identity provider (auth.kodeme.io) |
| zulip | zulip | 58 MB | Team chat (zulip.kodeme.io) |
| glitchtip | glitchtip | 53 MB | Error tracking (glitchtip.kodeme.io) |
| hmdm | hmdm | 50 MB | Mobile device management |
| outline | outline | 49 MB | Wiki/docs (outline.kodeme.io) |
| gatus | gatus | 48 MB | Uptime monitoring (gatus.kodeme.io) |
| plane | plane | 23 MB | Project management (plane.kodeme.io) |
| postgres | postgres | 16 MB | Default/admin database |

## Production Roles

| Role | Flags | Purpose |
|---|---|---|
| postgres | SLCRP | Superuser (admin) |
| app | L | Generic application user |
| authentik | L | Authentik service (conn limit: 50) |
| zulip | L | Zulip service |
| outline | L | Outline service |
| gatus | L | Gatus service |
| glitchtip | L | GlitchTip service |
| hmdm | L | Headwind MDM service |
| plane | L | Plane service |
| pgbouncer | L | PgBouncer auth user |
| replicator | LP | Streaming replication |

Flags: S=superuser, L=login, C=createdb, R=createrole, P=replication

## CLI Tool: kctl-pg

The CLI is installed in the project at `cli/` and available via the venv:

```bash
# Run from the kodemeio-postgres-16 project root:
cd cli && uv run kctl-pg <command>

# Or if installed globally:
kctl-pg <command>
```

Configuration is stored at `~/.config/kodemeio/config.yaml` under `profiles.<name>.postgres`.

### Global Options

```bash
kctl-pg [--json] [--quiet] [--profile NAME] [--host HOST] [--port PORT] [--user USER] [--password PASS] <command>
```

### Database Management

```bash
kctl-pg db list                                         # List all databases with size/owner/connections
kctl-pg db create <name> [--owner USER] [--encoding]    # Create database
kctl-pg db drop <name> [--force]                        # Drop database (terminates connections first)
kctl-pg db size                                         # Show all database sizes with total
kctl-pg db info <name>                                  # Detailed info (encoding, collation, tables, connections)
```

### User/Role Management

```bash
kctl-pg users list                                      # List all roles with flags
kctl-pg users get <name>                                # Detailed role info (memberships, owned DBs)
kctl-pg users create <name> [--password PASS] [--login/--no-login] [--createdb] [--superuser]
kctl-pg users drop <name> [--force]                     # Drop role
kctl-pg users password <name> [--password PASS]         # Set/reset password (auto-generates if omitted)
kctl-pg users grant <role> --to <target>                # Grant role membership
kctl-pg users revoke <role> --from <target>             # Revoke role membership
kctl-pg users alter <name> --set <param> <value>        # Set session defaults per role
kctl-pg users grant-db <role> <database> --privileges connect,create,temp
kctl-pg users grant-schema <role> <schema> --privileges usage,create [--db DATABASE]
kctl-pg users grant-table <role> <table> --privileges select,insert,update,delete [--db DATABASE]
kctl-pg users default-privileges <role> [--db DATABASE] [--schema SCHEMA] --grant-to <target> --privileges select
```

### Health & Monitoring

```bash
kctl-pg health                                          # Server status, version, uptime, connections, replication
kctl-pg dashboard                                       # Overview: databases, sizes, connections, long-running queries
```

### Connection Activity

```bash
kctl-pg activity list [--db NAME] [--state STATE]       # List active connections
kctl-pg activity kill <pid> [--force]                   # Cancel or terminate backend (--force = pg_terminate)
kctl-pg activity locks [--db NAME]                      # Show lock contention (blocked queries)
```

### Ad-hoc SQL Queries

```bash
kctl-pg query "SELECT version()"                        # Execute SQL on default database
kctl-pg query --db odoo "SELECT * FROM res_users"       # Query specific database
kctl-pg query "SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database"
```

### Backup & Restore (via SSH)

```bash
kctl-pg backup dump <database> [-o output.dump] [-F c|p|d]  # pg_dump via SSH into Docker container
kctl-pg backup restore <database> -i file.dump [--create] [--clean]  # pg_restore via SSH
kctl-pg backup list                                     # List pgBackRest backups (if configured)
```

### Extension Management

```bash
kctl-pg extensions list [--db NAME]                     # List installed extensions
kctl-pg extensions list --db NAME --available           # List all available extensions
kctl-pg extensions install <name> [--db NAME] [--schema SCHEMA]
kctl-pg extensions uninstall <name> [--db NAME] [--cascade] [--force]
```

### Configuration Management

```bash
kctl-pg config init                                     # Interactive first-time setup
kctl-pg config add <profile> --host H --ssh-host SSH [--databases db1,db2]
kctl-pg config use <profile>                            # Switch default profile
kctl-pg config remove <profile> [--force] [--service-only]
kctl-pg config show                                     # Show all profiles (passwords masked)
kctl-pg config set <key> <value>                        # Set individual config value
kctl-pg config profiles                                 # List profiles with connection status
kctl-pg config current                                  # Show active profile details
kctl-pg config test                                     # Test SSH tunnel + PostgreSQL connection
```

## Connection Architecture

```
kctl-pg (local machine)
  └─ SSH tunnel (sshtunnel + paramiko)
       └─ db.kodeme.io:22 (SSH)
            └─ 127.0.0.1:5432 (Docker port mapping)
                 └─ PostgreSQL container (kodemeio-postgres-16)
```

- SQL commands (db, users, health, query, activity, extensions) use psycopg3 through the SSH tunnel
- Backup/restore commands use `subprocess` SSH + `docker exec` to run pg_dump/pg_restore inside the container

## Config File Format

```yaml
# ~/.config/kodemeio/config.yaml
default_profile: production
profiles:
  production:
    postgres:                          # SERVICE_KEY = "postgres"
      host: 127.0.0.1
      port: 5432
      user: postgres
      password: ${PG_PASSWORD}         # Supports env var expansion
      ssh_host: db.kodeme.io
      ssh_port: 22
      ssh_user: root
      ssh_key: ~/.ssh/id_ed25519
      databases:
        - authentik
        - zulip
        - outline
        - gatus
        - glitchtip
        - hmdm
    authentik:                         # Other kctl-* tools coexist
      url: https://auth.kodeme.io
      token: ${AUTHENTIK_TOKEN}
```

### Config Resolution Priority

1. CLI flags (`--host`, `--user`, `--password`)
2. `KCTL_PG_*` env vars (`KCTL_PG_HOST`, `KCTL_PG_USER`, etc.)
3. Standard `PG*` env vars (`PGHOST`, `PGUSER`, `PGPASSWORD`)
4. Config file profile

## Service Database Provisioning

New service databases are auto-provisioned by the init container using `SERVICE_DATABASES` env var:

```bash
# Format: db1:user1:pass1,db2:user2:pass2
SERVICE_DATABASES=authentik:authentik:4bdab...,zulip:zulip:YVbm...
```

To manually add a new service database:
```bash
kctl-pg users create <service_name> --password "$PASS"
kctl-pg db create <service_name> --owner <service_name>
```

## Container Scripts (via SSH)

The Docker container embeds 24 management scripts at `/scripts/`. These can be run via SSH:

```bash
ssh root@db.kodeme.io "docker exec kodemeio-postgres-16 /scripts/health.sh"
ssh root@db.kodeme.io "docker exec kodemeio-postgres-16 /scripts/db.sh list"
ssh root@db.kodeme.io "docker exec kodemeio-postgres-16 /scripts/dashboard.sh"
```

kctl-pg replaces the need for most of these by providing a local CLI experience.

## Security Notes

- SCRAM-SHA-256 authentication (not md5)
- SSL/TLS with auto-generated RSA-4096 self-signed certs
- pgAudit extension for DDL + role change audit logging
- `audit.logged_actions` table for row-level change tracking
- Replication restricted to RFC1918 private networks
- App users have LOGIN only (no CREATEDB by default)
- PgBouncer uses `auth_query` for credential lookup

## Database Maintenance

```bash
kctl-pg maintenance vacuum <database> [--table TABLE] [--full] [--analyze] [--verbose]
kctl-pg maintenance analyze <database> [--table TABLE] [--verbose]
kctl-pg maintenance reindex <database> [--table TABLE] [--index INDEX] [--system]
kctl-pg maintenance bloat [--db DATABASE] [--top 20]
kctl-pg maintenance autovacuum-status [--db DATABASE]
kctl-pg maintenance vacuum-freeze <database> [--table TABLE]
kctl-pg maintenance cluster <database> <table> <index> [--force]
kctl-pg maintenance reindex-concurrently <database> [--table TABLE] [--index INDEX]
kctl-pg maintenance checkpoint [--force]
kctl-pg maintenance frozen-xid [--db DATABASE] [--top 20]
```

## Performance Monitoring

```bash
kctl-pg perf overview [--db DATABASE]
kctl-pg perf slow-queries [--db DATABASE] [--min-duration MS] [--limit 20]
kctl-pg perf table-stats [--db DATABASE] [--top 20]
kctl-pg perf index-usage [--db DATABASE] [--min-size BYTES]
kctl-pg perf cache [--db DATABASE]
kctl-pg perf locks [--db DATABASE]
kctl-pg perf connections [--db DATABASE]
kctl-pg perf settings [--filter PATTERN]
kctl-pg perf wal-status
kctl-pg perf explain <sql> [--db DATABASE] [--analyze] [--buffers]
kctl-pg perf xid-wraparound                             # XID age per database
kctl-pg perf temp-files [--db DATABASE]                  # Temp file usage
kctl-pg perf progress                                    # All pg_stat_progress_* views
```

## PostgreSQL Configuration

```bash
kctl-pg pg-config show [--filter PATTERN]
kctl-pg pg-config get <name>
kctl-pg pg-config set <name> <value>
kctl-pg pg-config reset <name>
kctl-pg pg-config reload
kctl-pg pg-config diff
```

## Statistics Views

```bash
kctl-pg stats tables [--db DATABASE]
kctl-pg stats indexes [--db DATABASE]
kctl-pg stats bgwriter
kctl-pg stats replication
kctl-pg stats wal
kctl-pg stats io
kctl-pg stats database [--name DB]
```

## Table Management

```bash
kctl-pg tables list [--db DATABASE] [--schema SCHEMA]
kctl-pg tables describe <table> [--db DATABASE]
kctl-pg tables size [--db DATABASE] [--top 20]
kctl-pg tables partitions <table> [--db DATABASE]
kctl-pg tables constraints <table> [--db DATABASE]
kctl-pg tables triggers <table> [--db DATABASE]
kctl-pg tables dependencies <table> [--db DATABASE]
kctl-pg tables toast <table> [--db DATABASE]
kctl-pg tables sequences [--db DATABASE] [--near-max]
```

## Index Management

```bash
kctl-pg indexes list [--db DATABASE] [--table TABLE]
kctl-pg indexes bloat [--db DATABASE] [--top 20]
kctl-pg indexes duplicate [--db DATABASE]
kctl-pg indexes invalid [--db DATABASE]
kctl-pg indexes missing [--db DATABASE] [--min-size "10 MB"]
kctl-pg indexes create-concurrently <table> <columns> [--db DATABASE] [--name NAME] [--unique]
kctl-pg indexes reindex-concurrently <target> [--db DATABASE] [--table]
```

## Replication Management

```bash
kctl-pg replication status
kctl-pg replication lag
kctl-pg replication slots
kctl-pg replication slot-create <name> [--logical --plugin pgoutput] [--physical]
kctl-pg replication slot-drop <name> [--force]
kctl-pg replication publications [--db DATABASE]
kctl-pg replication subscriptions [--db DATABASE]
kctl-pg replication promote [--force]
kctl-pg replication wal-senders
kctl-pg replication wal-receiver
```

## Security Management

```bash
kctl-pg security ssl-status
kctl-pg security hba-rules
kctl-pg security privileges <role> [--db DATABASE]
kctl-pg security rls-status [--db DATABASE]
kctl-pg security rls-policies [--db DATABASE] [--table TABLE]
kctl-pg security superuser-audit
kctl-pg security password-check
```

## Schema Management

```bash
kctl-pg schemas list [--db DATABASE]
kctl-pg schemas create <name> [--db DATABASE] [--owner ROLE]
kctl-pg schemas drop <name> [--db DATABASE] [--cascade] [--force]
kctl-pg schemas size [--db DATABASE]
```

## PgBouncer Management

```bash
kctl-pg pgbouncer status
kctl-pg pgbouncer pools
kctl-pg pgbouncer clients
kctl-pg pgbouncer servers
kctl-pg pgbouncer databases
kctl-pg pgbouncer stats
kctl-pg pgbouncer reload [--force]
kctl-pg pgbouncer pause [--db DATABASE] [--force]
kctl-pg pgbouncer resume [--db DATABASE]
```

## Troubleshooting

### Cannot connect via kctl-pg
1. Check SSH key: `ssh -i ~/.ssh/id_ed25519 root@db.kodeme.io "echo ok"`
2. Check config: `kctl-pg config current`
3. Test connection: `kctl-pg config test`

### Database connection refused
1. Check Docker container is running: `ssh root@db.kodeme.io "docker ps | grep postgres"`
2. Check port mapping: PostgreSQL must map 5432 to host
3. Try `kctl-pg health` to see if server responds

### High connection count
1. `kctl-pg activity list` -- see who is connected
2. `kctl-pg activity list --state idle` -- find idle connections
3. `kctl-pg activity kill <pid>` -- cancel runaway queries
4. Check PgBouncer pool settings if connections exceed `max_connections`

### Lock contention / slow queries
1. `kctl-pg activity locks` -- show blocked queries
2. `kctl-pg dashboard` -- shows long-running queries (>5s)
3. `kctl-pg activity kill <blocking_pid> --force` -- terminate blocking backend

### Backup failures
1. Ensure Docker container name is discoverable: `ssh root@db.kodeme.io "docker ps --format '{{.Names}}' | grep postgres"`
2. Check disk space on remote server
3. For large databases, increase timeout in backup command
