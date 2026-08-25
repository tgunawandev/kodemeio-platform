# kctl-op

Command reference for `kctl-op` (11 groups, ~26 commands).

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

### `kctl-op backup`

Backup management for .env files.

| Command | Description |
|---------|-------------|
| `backup clean [--keep] [--force]` | Clean old backups, keeping the N most recent per file. |
| `backup list [--project]` | List available backups. |
| `backup restore <project> <environment> [--timestamp] [--force]` | Restore a .env file from backup. |

### `kctl-op config`

Manage CLI configuration and profiles.

| Command | Description |
|---------|-------------|
| `config add <name> [--vault] [--token] [--scan_root]` | Add a new profile. |
| `config current` | Show current active profile. |
| `config init [--vault] [--token] [--name] [--scan_root]` | Initialize CLI configuration (interactive if no flags given). |
| `config migrate` | Migrate legacy configuration to service-scoped format. |
| `config profiles` | List all profiles. |
| `config remove <name> [--force]` | Remove a profile's 1Password configuration. |
| `config set <key> <value>` | Set a configuration value in the current profile. |
| `config show` | Show full configuration (tokens masked). |
| `config test` | Test current profile's 1Password connection. |
| `config use <name>` | Set the default profile. |

### `kctl-op diff`

Show differences between local and 1Password.

### `kctl-op discover`

Discover .env files.

### `kctl-op health`

Health checks and diagnostics.

| Command | Description |
|---------|-------------|
| `health dashboard` | Overview: projects, files, sync status, last sync times. |

### `kctl-op list`

List all items in the 1Password vault.

### `kctl-op projects`

Project discovery and status.

| Command | Description |
|---------|-------------|
| `projects envs <project>` | List all .env files for a project. |
| `projects list` | List all projects found across scan roots. |
| `projects status <project>` | Show sync status for all environments in a project. |

### `kctl-op pull`

Pull .env files from 1Password.

### `kctl-op push`

Push .env files to 1Password.

### `kctl-op status`

Check sync status.

### `kctl-op vault`

Vault management operations.

| Command | Description |
|---------|-------------|
| `vault create [--name] [--description]` | Create a new 1Password vault. |
| `vault info` | Show vault details. |
| `vault items` | List all items in the vault with metadata. |
