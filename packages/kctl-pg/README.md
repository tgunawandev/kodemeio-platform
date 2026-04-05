# kctl-pg

Kodemeio PostgreSQL CLI -- manage PostgreSQL servers via SSH tunnel.

## Installation

```bash
uv tool install ./packages/kctl-pg
```

To upgrade after code changes:

```bash
uv tool install --force --reinstall ./packages/kctl-pg
```

## Quick Start

```bash
# Configure a profile (interactive)
kctl-pg config init

# Verify connection
kctl-pg health

# Dashboard overview
kctl-pg dashboard

# List databases
kctl-pg db list

# List users
kctl-pg users list

# Check active connections
kctl-pg activity list

# Run a raw SQL query
kctl-pg query "SELECT version()"

# Dump a database backup
kctl-pg backup dump --database mydb

# Show slow queries
kctl-pg performance slow-queries

# Full health report
kctl-pg pipeline report
```

## Command Groups

| Group          | Commands                                                                                                                                    | Description                                               |
|----------------|---------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------|
| `activity`     | `list`, `kill`, `locks`                                                                                                                     | Active connections, long-running queries, lock waits      |
| `automation`   | `plan`, `alerts`, `report`, `baseline`                                                                                                      | Automated maintenance planning and alert rules            |
| `backup`       | `dump`, `restore`, `list`                                                                                                                   | Database backup and restore via pg_dump / pg_restore      |
| `config`       | `init`, `add`, `use`, `show`, `validate`, `remove`, `set`, `profiles`, `current`                                                           | CLI configuration and profile management                  |
| `dashboard`    | `dashboard`                                                                                                                                 | Single-screen server overview (size, connections, health) |
| `db`           | `list`, `create`, `drop`, `size`, `info`, `rename`, `copy`, `owner`                                                                        | Database CRUD and metadata                                |
| `dr`           | `verify-backup`, `test-failover`, `capacity-forecast`, `rpo-rto`                                                                           | Disaster recovery checks, RPO/RTO status, capacity        |
| `extensions`   | `list`, `install`, `uninstall`                                                                                                              | PostgreSQL extension management                           |
| `health`       | `health`                                                                                                                                    | Quick server health check (connections, replication, etc) |
| `indexes`      | `list`, `bloat`, `duplicate`, `invalid`, `missing`, `create-concurrently`, `reindex-concurrently`                                          | Index analysis, bloat detection, and safe concurrent ops  |
| `lint`         | `schema`, `indexes`, `permissions`, `all`                                                                                                   | Static analysis for schema, index, and permission issues  |
| `maintenance`  | `vacuum`, `analyze`, `reindex`, `autovacuum`, `freeze`, `cluster`, `checkpoint`, `frozen-xid`                                              | Table maintenance, vacuum, freeze, and statistics         |
| `performance`  | `overview`, `slow-queries`, `cache`, `settings`, `explain`, `temp-files`, `progress`                                                       | Query performance, cache hit ratios, and EXPLAIN plans    |
| `pg-config`    | `show`, `get`, `set`, `reset`, `reload`, `diff`                                                                                            | PostgreSQL server configuration (postgresql.conf)         |
| `pgbouncer`    | `status`, `pools`, `clients`, `servers`, `databases`, `stats`, `reload`, `pause`, `resume`                                                 | PgBouncer connection pooler management                    |
| `pipeline`     | `gate`, `report`                                                                                                                            | CI/CD pipeline gates and full health reports              |
| `query`        | `query`                                                                                                                                     | Execute raw SQL queries                                   |
| `replication`  | `status`, `lag`, `slots`, `create-slot`, `drop-slot`, `publications`, `subscriptions`, `promote`, `senders`, `receiver`                    | Streaming and logical replication management              |
| `schemas`      | `list`, `create`, `drop`, `size`                                                                                                            | Schema management and sizing                              |
| `security`     | `ssl`, `hba-rules`, `privileges`, `rls`, `rls-policies`, `superuser-audit`, `password-check`                                               | SSL, pg_hba.conf, row-level security, and auditing        |
| `stats`        | `tables`, `indexes`, `bgwriter`, `replication`, `wal`, `io`, `database`                                                                    | pg_stat_* statistics views                                |
| `tables`       | `list`, `describe`, `size`, `partitions`, `constraints`, `triggers`, `dependencies`, `toast`, `sequences`                                  | Table inspection, sizing, and metadata                    |
| `users`        | `list`, `create`, `drop`, `password`, `get`, `grant`, `revoke`, `alter`, `grant-db`, `grant-schema`, `grant-table`, `default-privileges`   | User and role management                                  |

## SSH Tunnel Architecture

kctl-pg does **not** connect directly to PostgreSQL. All connections are established through an SSH tunnel to avoid exposing the PostgreSQL port on the network.

```
kctl-pg CLI
    |
    | SSH (port 22)
    v
Remote Server (ssh_host)
    |
    | localhost tunnel -> 5432
    v
PostgreSQL (host:port, internal network only)
```

The tunnel is opened automatically when any command needs a database connection and closed when the command completes. This is handled transparently by `PostgresClient` using `SSHTunnel` from `kctl-lib`.

For Dokploy-managed servers, the `host` in the config refers to the PostgreSQL host as seen **from the SSH server** (e.g. `10.0.0.2` for internal Hetzner network addresses), not from your local machine.

## Global Options

These options are available on every command:

```
--json            Output as JSON (machine-readable)
--quiet, -q       Suppress informational messages
--profile, -p     Use a named config profile
--host, -H        PostgreSQL host override
--port            PostgreSQL port override
--user, -U        PostgreSQL user override
--password        PostgreSQL password override
--version, -V     Show version and exit
```

## Configuration

### Config File Format

kctl-pg shares the platform-wide config at `~/.config/kodemeio/config.yaml`. PostgreSQL settings are scoped under the `postgres` service key:

```yaml
default_profile: production

profiles:
  production:
    postgres:
      host: 10.0.0.2           # Internal PG host (as seen from SSH server)
      port: 5432
      user: postgres
      password: ${PG_PASSWORD}  # Env var expansion supported
      ssh_host: 49.13.14.79    # Public SSH host
      ssh_port: 22
      ssh_user: root
      ssh_key: ~/.ssh/id_ed25519
      databases:
        - authentik
        - odoo_production
  staging:
    postgres:
      host: 10.0.0.3
      port: 5432
      user: postgres
      password: ${PG_PASSWORD_STG}
      ssh_host: staging.example.com
      ssh_port: 22
      ssh_user: root
      ssh_key: ~/.ssh/id_ed25519
```

### Profile Management

```bash
# Interactive setup wizard
kctl-pg config init

# Add a named profile
kctl-pg config add production \
  --host 10.0.0.2 \
  --ssh-host 49.13.14.79 \
  --user postgres

# Switch the default profile
kctl-pg config use production

# Show current profile config (secrets masked)
kctl-pg config show

# List all profiles
kctl-pg config profiles

# Validate current config
kctl-pg config validate
```

### Environment Variables

CLI flags take precedence over env vars, which take precedence over the config file.

| Variable            | Description                                   |
|---------------------|-----------------------------------------------|
| `KCTL_PG_HOST`      | PostgreSQL host override                      |
| `KCTL_PG_PORT`      | PostgreSQL port override                      |
| `KCTL_PG_USER`      | PostgreSQL user override                      |
| `KCTL_PG_PASSWORD`  | PostgreSQL password override                  |
| `KCTL_PG_SSH_HOST`  | SSH host override                             |
| `KCTL_PG_PROFILE`   | Active profile name override                  |
| `PGHOST`            | Standard libpq host (lower priority)          |
| `PGPORT`            | Standard libpq port (lower priority)          |
| `PGUSER`            | Standard libpq user (lower priority)          |
| `PGPASSWORD`        | Standard libpq password (lower priority)      |

### Connection Resolution Priority

1. CLI flags (`--host`, `--user`, `--password`, etc.)
2. `KCTL_PG_*` environment variables
3. Standard `PG*` environment variables (`PGHOST`, `PGUSER`, etc.)
4. Config file profile

## Common DBA Workflows

### Database Provisioning

```bash
# Create a role first
kctl-pg users create myuser --password secret --login

# Create a database with owner
kctl-pg db create mydb --owner myuser

# Grant full access on the database
kctl-pg users grant-db myuser mydb

# Grant usage on public schema
kctl-pg users grant-schema myuser public --database mydb
```

### Backup and Restore

```bash
# Dump a database
kctl-pg backup dump --database mydb --file mydb.dump

# List available backups
kctl-pg backup list

# Restore a backup
kctl-pg backup restore --file mydb.dump --database mydb_restore
```

### Performance Investigation

```bash
# Full performance overview
kctl-pg performance overview --database mydb

# Slow queries (top 20 by total time)
kctl-pg performance slow-queries --database mydb --limit 20

# Cache hit ratio
kctl-pg performance cache --database mydb

# EXPLAIN a query
kctl-pg performance explain "SELECT * FROM orders WHERE status = 'pending'" --database mydb

# Operations currently in progress
kctl-pg performance progress
```

### Index Maintenance

```bash
# Find bloated indexes
kctl-pg indexes bloat --database mydb

# Find duplicate indexes
kctl-pg indexes duplicate --database mydb

# Find invalid indexes (failed CONCURRENTLY build)
kctl-pg indexes invalid --database mydb

# Rebuild a specific index without locking writes
kctl-pg indexes reindex-concurrently --index my_index --database mydb
```

### Security Audit

```bash
# Check SSL configuration
kctl-pg security ssl

# Review pg_hba.conf rules
kctl-pg security hba-rules

# Superuser audit
kctl-pg security superuser-audit

# Password hash methods in use
kctl-pg security password-check
```

### Replication Monitoring

```bash
# Replication status
kctl-pg replication status

# Replication lag per replica
kctl-pg replication lag

# List replication slots
kctl-pg replication slots

# WAL senders
kctl-pg replication senders
```

### CI/CD Pipeline Integration

```bash
# Gate: fail if replication lag > threshold, cache hit < 95%, connections > 80%
kctl-pg pipeline gate --database mydb

# Generate a full Markdown health report
kctl-pg pipeline report --database mydb --output report.md
```

### Server Configuration Tuning

```bash
# Show all non-default settings
kctl-pg pg-config show --changed-only

# Get a specific parameter
kctl-pg pg-config get shared_buffers

# Set a parameter (requires superuser)
kctl-pg pg-config set work_mem 64MB

# Reload config without restart
kctl-pg pg-config reload

# Diff current settings against defaults
kctl-pg pg-config diff
```

## Development

### Running Tests

```bash
cd packages/kctl-pg
uv run pytest tests/ -v
```

### Linting and Formatting

```bash
cd packages/kctl-pg
uv run ruff check src/
uv run ruff format src/
```

### Type Checking

```bash
cd packages/kctl-pg
uv run mypy src/kctl_pg/
```

### Project Structure

```
packages/kctl-pg/
  src/kctl_pg/
    cli.py              Main Typer app + command group registration
    __init__.py         Version
    core/
      callbacks.py      AppContext (subclasses AppContextBase from kctl-lib)
      client.py         PostgresClient (psycopg + SSHTunnel)
      config.py         Profile and connection resolution (SERVICE_KEY = "postgres")
      exceptions.py     KctlError subclasses
    commands/
      activity.py       list, kill, locks
      automation.py     plan, alerts, report, baseline
      backup.py         dump, restore, list
      config_cmd.py     init, add, use, show, validate, remove, set, profiles, current
      dashboard.py      single-screen server overview
      db.py             list, create, drop, size, info, rename, copy, owner
      dr.py             verify-backup, test-failover, capacity-forecast, rpo-rto
      extensions.py     list, install, uninstall
      health.py         health
      indexes.py        list, bloat, duplicate, invalid, missing, create-concurrently, reindex-concurrently
      lint.py           schema, indexes, permissions, all
      maintenance.py    vacuum, analyze, reindex, autovacuum, freeze, cluster, checkpoint, frozen-xid
      performance.py    overview, slow-queries, cache, settings, explain, temp-files, progress
      pg_config.py      show, get, set, reset, reload, diff
      pgbouncer.py      status, pools, clients, servers, databases, stats, reload, pause, resume
      pipeline.py       gate, report
      query.py          raw SQL execution
      replication.py    status, lag, slots, create-slot, drop-slot, publications, subscriptions, promote, senders, receiver
      schemas.py        list, create, drop, size
      security.py       ssl, hba-rules, privileges, rls, rls-policies, superuser-audit, password-check
      stats.py          tables, indexes, bgwriter, replication, wal, io, database
      tables.py         list, describe, size, partitions, constraints, triggers, dependencies, toast, sequences
      users.py          list, create, drop, password, get, grant, revoke, alter, grant-db, grant-schema, grant-table, default-privileges
  tests/                pytest test suite
  pyproject.toml        Package metadata and tool config
  README.md             This file
```
