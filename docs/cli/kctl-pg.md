# kctl-pg

Command reference for `kctl-pg` (23 groups, ~129 commands).

> Auto-generated on 2026-04-02. Do not edit manually.
> Regenerate with: `uv run python scripts/generate-cli-docs.py`

## Global Options

| Flag | Description |
|------|-------------|
| `--json` | JSON output |
| `--quiet`, `-q` | Suppress info messages |
| `--format`, `-f` | Output format: pretty/json/csv/yaml |
| `--no-header` | Omit headers in CSV output |
| `--profile`, `-p` | Config profile name |
| `--version`, `-V` | Show version |

## Commands

### `kctl-pg activity`

Monitor connections and activity.

| Command | Description |
|---------|-------------|
| `activity kill <pid> [--force]` | Cancel or terminate a backend process. |
| `activity list [--database] [--state]` | List active connections. |
| `activity locks [--database]` | Show lock contention (blocked queries waiting for locks). |

### `kctl-pg automation`

Automation: maintenance plans, alerts, reports, baselines.

| Command | Description |
|---------|-------------|
| `automation alerts` | Show current metric values against recommended alert thresholds. |
| `automation baseline [--database]` | Capture current performance baseline for future comparison. |
| `automation plan [--database]` | Generate recommended vacuum/analyze/reindex schedule based on table stats. |
| `automation report [--database] [--period]` | Generate a health report: sizes, slow queries, connections, maintenance. |

### `kctl-pg backup`

Backup and restore databases via SSH.

| Command | Description |
|---------|-------------|
| `backup dump <database> [--output] [--format_]` | Dump a database via SSH + pg_dump. |
| `backup list` | List recent backups on the remote server. |
| `backup restore <database> <input_file> [--create] [--clean]` | Restore a database from a dump file via SSH. |

### `kctl-pg config`

Manage CLI configuration and profiles.

| Command | Description |
|---------|-------------|
| `config add <name> [--host] [--port] [--user] [--password] [--ssh_host] [--ssh_port] [--ssh_user] [--ssh_key] [--databases] [--set_default]` | Add or update a profile's PostgreSQL connection. |
| `config current` | Show the active profile and connection status. |
| `config init [--host] [--port] [--user] [--password] [--ssh_host] [--ssh_port] [--ssh_user] [--ssh_key] [--name]` | Initialize CLI configuration (interactive if no flags given). |
| `config profiles` | List all profiles with PostgreSQL connection status. |
| `config remove <name> [--force] [--service_only]` | Remove a profile or just its PostgreSQL config. |
| `config set <key> <value> [--profile_arg]` | Set a configuration value for the current service. |
| `config show` | Show full configuration (passwords masked). |
| `config test` | Test PostgreSQL connection with current configuration. |
| `config use <name>` | Switch the default profile. |

### `kctl-pg dashboard`

System overview dashboard.

### `kctl-pg db`

Manage databases.

| Command | Description |
|---------|-------------|
| `db copy <source> <target> [--owner]` | Copy a database using CREATE DATABASE .. |
| `db create <name> [--owner] [--encoding]` | Create a new database. |
| `db drop <name> [--force]` | Drop a database. |
| `db info <name>` | Show detailed info about a database. |
| `db list` | List all databases with size and owner. |
| `db owner <database> <new_owner>` | Change the owner of a database. |
| `db rename <old_name> <new_name> [--force]` | Rename a database (terminates active connections first). |
| `db size` | Show database sizes sorted by size. |

### `kctl-pg dr`

Disaster recovery: backup verification, failover testing, capacity forecasting.

| Command | Description |
|---------|-------------|
| `dr capacity-forecast [--database] [--months] [--disk_gb]` | Project storage growth based on table sizes and transaction rates. |
| `dr rpo-rto` | Calculate actual RPO/RTO from backup status and replication state. |
| `dr test-failover [--dry_run]` | Check replica promotion readiness and replication slot health. |
| `dr verify-backup <backup_file> [--database]` | Restore backup to a temp database, run integrity checks, then drop it. |

### `kctl-pg extensions`

Manage PostgreSQL extensions.

| Command | Description |
|---------|-------------|
| `extensions install <name> [--database] [--schema]` | Install an extension. |
| `extensions list [--database] [--available]` | List installed or available extensions. |
| `extensions uninstall <name> [--database] [--cascade] [--force]` | Uninstall an extension. |

### `kctl-pg health`

Check PostgreSQL server health.

### `kctl-pg indexes`

Index inspection and management.

| Command | Description |
|---------|-------------|
| `indexes bloat [--database] [--top]` | Estimate index bloat using actual vs expected size ratios. |
| `indexes create-concurrently <table> <columns> [--database] [--name] [--unique] [--schema]` | Create an index concurrently (non-blocking). |
| `indexes duplicate [--database]` | Find duplicate or overlapping indexes (same table, same leading columns). |
| `indexes invalid [--database]` | Find invalid indexes (e.g., from failed REINDEX CONCURRENTLY). |
| `indexes list [--database] [--table]` | List indexes with size, type, uniqueness, and partial predicate. |
| `indexes missing [--database] [--min_size]` | Find tables with high sequential scan counts suggesting missing indexes. |
| `indexes reindex-concurrently <target> [--database] [--is_table]` | Reindex an index or table concurrently (non-blocking). |

### `kctl-pg lint`

Schema and configuration quality checks.

| Command | Description |
|---------|-------------|
| `lint all [--database] [--strict] [--min_scans]` | Run all lint checks. |
| `lint indexes [--database] [--min_scans]` | Detect unused, duplicate, bloated, and missing FK indexes. |
| `lint permissions [--database]` | Find excessive privileges, public schema grants, superuser misuse, missing RLS. |
| `lint schema [--database]` | Check naming conventions, missing PKs, column types, and NOT NULL gaps. |

### `kctl-pg maintenance`

Database maintenance operations.

| Command | Description |
|---------|-------------|
| `maintenance analyze <database> [--table] [--verbose]` | Update planner statistics (ANALYZE) on a database or table. |
| `maintenance autovacuum [--database]` | Show autovacuum settings and last vacuum/analyze times per table. |
| `maintenance checkpoint [--force]` | Force a WAL checkpoint. |
| `maintenance cluster <database> <table> <index> [--force]` | Physically reorder a table by an index (requires exclusive lock). |
| `maintenance freeze <database> [--table]` | Run VACUUM FREEZE to aggressively freeze old row versions. |
| `maintenance frozen-xid [--database] [--top]` | Show transaction ID freeze status (XID age) per database and per table. |
| `maintenance reindex <database> [--table] [--index] [--system]` | Rebuild indexes on a database, table, or specific index. |
| `maintenance vacuum <database> [--table] [--full] [--analyze] [--verbose]` | Run VACUUM on a database or table. |

### `kctl-pg performance`

Performance monitoring and diagnostics.

| Command | Description |
|---------|-------------|
| `performance cache [--database]` | Show buffer cache hit ratio per database. |
| `performance explain <sql> [--database] [--analyze_opt] [--buffers]` | Show query execution plan (EXPLAIN). |
| `performance overview [--database]` | Show performance overview: cache hits, transactions, connections, DB sizes. |
| `performance progress` | Show progress of running maintenance operations (vacuum, analyze, create index, etc.). |
| `performance settings [--filter]` | Show PostgreSQL configuration parameters. |
| `performance slow-queries [--database] [--min_duration] [--limit]` | Show slowest queries from pg_stat_statements. |
| `performance temp-files [--database]` | Show temporary file usage per database. |

### `kctl-pg pg-config`

Manage PostgreSQL configuration (pg_settings).

| Command | Description |
|---------|-------------|
| `pg-config diff` | Show settings that differ from their default (boot) values. |
| `pg-config get <name>` | Get details of a specific PostgreSQL setting. |
| `pg-config reload` | Reload PostgreSQL configuration (pg_reload_conf). |
| `pg-config reset <name>` | Reset a PostgreSQL configuration parameter to default (ALTER SYSTEM RESET + reload). |
| `pg-config set <name> <value>` | Set a PostgreSQL configuration parameter (ALTER SYSTEM + reload). |
| `pg-config show [--filter]` | Show PostgreSQL settings (optionally filtered by name pattern). |

### `kctl-pg pgbouncer`

PgBouncer management (admin console).

| Command | Description |
|---------|-------------|
| `pgbouncer clients` | Show PgBouncer client connections. |
| `pgbouncer databases` | Show PgBouncer database configurations. |
| `pgbouncer pause [--database] [--force]` | Pause PgBouncer database (or all databases). |
| `pgbouncer pools` | Show PgBouncer connection pools. |
| `pgbouncer reload [--force]` | Reload PgBouncer configuration. |
| `pgbouncer resume [--database]` | Resume PgBouncer database (or all databases). |
| `pgbouncer servers` | Show PgBouncer server (backend) connections. |
| `pgbouncer stats` | Show PgBouncer statistics. |
| `pgbouncer status` | Show PgBouncer version and pool summary. |

### `kctl-pg pipeline`

Pipeline orchestration: quality gates, combined health reports.

| Command | Description |
|---------|-------------|
| `pipeline gate [--database] [--strict] [--min_scans]` | Run quality gate: lint + alerts + DR checks. |
| `pipeline report [--database] [--fmt]` | Comprehensive health report combining all checks. |

### `kctl-pg query`

Execute SQL queries.

### `kctl-pg replication`

Replication management (status, lag, slots, publications, subscriptions).

| Command | Description |
|---------|-------------|
| `replication create-slot <name> [--logical] [--plugin] [--physical]` | Create a replication slot (physical or logical). |
| `replication drop-slot <name> [--force]` | Drop a replication slot. |
| `replication lag` | Show replication lag for connected replicas (bytes and estimated seconds). |
| `replication promote [--force]` | Promote standby to primary (pg_promote). |
| `replication publications [--database]` | Show publications and their tables. |
| `replication receiver` | Show WAL receiver status (only on standby servers). |
| `replication senders` | Show detailed WAL sender information for all connected replicas. |
| `replication slots` | Show replication slots: name, type, active status, retained WAL. |
| `replication status` | Show replication status: primary/standby role and connected replicas. |
| `replication subscriptions [--database]` | Show subscriptions and their status. |

### `kctl-pg schemas`

Manage schemas.

| Command | Description |
|---------|-------------|
| `schemas create <name> [--database] [--owner]` | Create a new schema. |
| `schemas drop <name> [--database] [--cascade] [--force]` | Drop a schema. |
| `schemas list [--database]` | List all schemas with sizes. |
| `schemas size [--database]` | Show per-schema size breakdown. |

### `kctl-pg security`

Security management (SSL, HBA, privileges, RLS, auditing).

| Command | Description |
|---------|-------------|
| `security hba-rules` | Show pg_hba.conf rules (PostgreSQL 15+). |
| `security password-check` | Check for password security issues: missing passwords, weak hashing, unnecessary passwords. |
| `security privileges <role> [--database]` | Show privileges for a specific role (tables, routines, database-level). |
| `security rls [--database]` | Show tables with Row-Level Security (RLS) enabled. |
| `security rls-policies [--database] [--table]` | Show RLS policies (name, table, command, roles, expressions). |
| `security ssl` | Show SSL connection status for all active connections. |
| `security superuser-audit` | Audit superuser roles and their recent activity. |

### `kctl-pg stats`

PostgreSQL statistics views (tables, indexes, WAL, I/O).

| Command | Description |
|---------|-------------|
| `stats bgwriter` | Show background writer statistics. |
| `stats database [--name]` | Show database-level statistics from pg_stat_database. |
| `stats indexes [--database]` | Show index statistics from pg_stat_user_indexes. |
| `stats io` | Show I/O statistics (PostgreSQL 16+). |
| `stats replication` | Show replication status from pg_stat_replication. |
| `stats tables [--database]` | Show table statistics from pg_stat_user_tables. |
| `stats wal` | Show WAL statistics (PostgreSQL 14+). |

### `kctl-pg tables`

Table inspection and management.

| Command | Description |
|---------|-------------|
| `tables constraints <table> [--database] [--schema]` | Show all constraints on a table (PK, FK, UNIQUE, CHECK). |
| `tables dependencies <table> [--database] [--schema]` | Show foreign key references to and from a table. |
| `tables describe <table> [--database] [--schema]` | Show table structure: columns, types, constraints, defaults. |
| `tables list [--database] [--schema]` | List tables with sizes in a database. |
| `tables partitions <table> [--database] [--schema]` | Show partition children and their bounds. |
| `tables sequences [--database] [--near_max]` | Show sequences with current value and percentage used. |
| `tables size [--database] [--top]` | Show table sizes with breakdown (table, toast, indexes). |
| `tables toast <table> [--database] [--schema]` | Show TOAST table statistics for a table. |
| `tables triggers <table> [--database] [--schema]` | Show triggers on a table with event, function, and enabled status. |

### `kctl-pg users`

Manage PostgreSQL roles and users.

| Command | Description |
|---------|-------------|
| `users alter <name> <set_param> <value>` | Set a configuration parameter for a role. |
| `users create <name> [--password] [--login] [--createdb] [--superuser]` | Create a new role/user. |
| `users default-privileges <role> <grant_to> [--privileges] [--database] [--schema]` | Set default privileges for tables created by a role. |
| `users drop <name> [--force]` | Drop a role/user. |
| `users get <name>` | Show detailed role info. |
| `users grant <role> <to>` | Grant a role to another role. |
| `users grant-db <role> <database> [--privileges]` | Grant privileges on a database to a role. |
| `users grant-schema <role> <schema> [--database] [--privileges]` | Grant privileges on a schema to a role. |
| `users grant-table <role> <table> [--database] [--privileges]` | Grant privileges on a table to a role. |
| `users list` | List all roles/users. |
| `users password <name> [--new_password]` | Set or reset a role's password. |
| `users revoke <role> <from_>` | Revoke a role from another role. |
