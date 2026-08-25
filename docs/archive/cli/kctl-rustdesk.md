# kctl-rustdesk

Command reference for `kctl-rustdesk` (9 groups, ~35 commands).

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

### `kctl-rustdesk audit`

Audit logs and connection history.

| Command | Description |
|---------|-------------|
| `audit active` | Show currently active sessions. |
| `audit connections [--today] [--limit]` | Show connection history. |
| `audit logins [--failed] [--limit]` | Show login history. |
| `audit stats` | Show connection statistics. |

### `kctl-rustdesk backup`

Backup and restore RustDesk server data.

| Command | Description |
|---------|-------------|
| `backup clean [--days]` | Remove old backups. |
| `backup create` | Create a backup of keys and database. |
| `backup list` | List available backups. |
| `backup restore <backup_file>` | Restore from a backup file. |

### `kctl-rustdesk config`

Manage CLI configuration and profiles.

| Command | Description |
|---------|-------------|
| `config init [--host] [--ssh_user] [--compose_file] [--env_file] [--project_name] [--domain] [--name]` | Initialize CLI configuration with a new profile. |
| `config profiles` | List all profiles. |
| `config show` | Show current configuration. |
| `config test` | Test connection to the RustDesk server. |
| `config use <name>` | Set the default profile. |

### `kctl-rustdesk dashboard`

System overview dashboard.

| Command | Description |
|---------|-------------|
| `dashboard show [--compact]` | Show system overview dashboard. |

### `kctl-rustdesk health`

Health checks for RustDesk server.

| Command | Description |
|---------|-------------|
| `health check [--as_json]` | Run health checks on RustDesk server. |

### `kctl-rustdesk maintenance`

Maintenance and operational tasks.

| Command | Description |
|---------|-------------|
| `maintenance cleanup` | Clean up unused Docker resources. |
| `maintenance db-optimize` | Optimize the SQLite database (VACUUM + ANALYZE). |
| `maintenance db-stats` | Show database statistics. |
| `maintenance logs [--service] [--lines]` | View container logs. |
| `maintenance status` | Show container status and resource usage. |
| `maintenance version` | Show version information. |

### `kctl-rustdesk peers`

Manage RustDesk peers (devices).

| Command | Description |
|---------|-------------|
| `peers count` | Count total peers. |
| `peers export` | Export all peers as JSON. |
| `peers get <peer_id>` | Get details for a specific peer. |
| `peers list [--online]` | List all registered peers. |
| `peers search <term>` | Search peers by ID, UUID, or note. |

### `kctl-rustdesk setup`

Server setup and configuration.

| Command | Description |
|---------|-------------|
| `setup client-config` | Generate RustDesk client configuration string. |
| `setup firewall` | Show required firewall rules. |
| `setup get-key` | Display the server's public key. |
| `setup status` | Show setup status checklist. |

### `kctl-rustdesk users`

Manage RustDesk users.

| Command | Description |
|---------|-------------|
| `users count` | Count users. |
| `users export` | Export all users as JSON. |
| `users get <username>` | Get details for a specific user. |
| `users groups` | List user groups. |
| `users list [--active]` | List all users. |
