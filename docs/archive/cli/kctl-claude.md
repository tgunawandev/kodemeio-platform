# kctl-claude

Command reference for `kctl-claude` (11 groups, ~32 commands).

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

### `kctl-claude api`

SDK REST API operations.

| Command | Description |
|---------|-------------|
| `api health` | Check SDK API health. |
| `api task <prompt> [--workspace] [--bare]` | Send a task to Claude Code via SDK API. |

### `kctl-claude backup`

Backup and restore Claude Code runtime.

| Command | Description |
|---------|-------------|
| `backup create` | Backup container runtime volume. |
| `backup restore <backup_dir>` | Restore runtime from backup. |

### `kctl-claude completions`

Generate or install shell completions.

### `kctl-claude config`

Manage CLI configuration and profiles.

| Command | Description |
|---------|-------------|
| `config add <name> [--config_dir] [--backup_dir] [--set_default]` | Add or update a profile's Claude configuration. |
| `config current` | Show the active profile and its Claude configuration. |
| `config init [--config_dir] [--backup_dir] [--name]` | Initialize CLI configuration (interactive if no flags given). |
| `config profiles` | List all profiles. |
| `config remove <name> [--force] [--service_only]` | Remove a profile or just its Claude config. |
| `config set <key> <value> [--profile_arg]` | Set a configuration value for the current service. |
| `config show` | Show full configuration. |
| `config test` | Verify configuration is valid. |
| `config use <name>` | Switch the default profile. |
| `config validate` | Validate the current configuration. |

### `kctl-claude doctor`

Diagnostics and health checks.

### `kctl-claude env`

Environment file management.

| Command | Description |
|---------|-------------|
| `env check` | Validate .env file. |
| `env deploy` | Deploy .env to Hetzner server. |
| `env generate` | Interactive .env generator. |

### `kctl-claude setup`

Setup Claude Code on local, VPS, or Docker.

| Command | Description |
|---------|-------------|
| `setup compare` | Compare setup modes side-by-side. |
| `setup docker` | Show Docker deployment commands. |
| `setup init` | Run session initialization (git, SSH, tmux, kctl tools). |
| `setup local` | Setup local development environment (laptop). |
| `setup vps [--check] [--skip_repos]` | Setup VPS/bare-metal server (requires sudo). |

### `kctl-claude status`

Status dashboard and health checks.

| Command | Description |
|---------|-------------|
| `status health` | Quick health check (exit code 0=ok, 1=issues). |
| `status updates` | Check for Claude Code updates and show changelog link. |

### `kctl-claude sync`

Sync config between local ~/.claude and repo.

| Command | Description |
|---------|-------------|
| `sync diff` | Preview what push would change (dry-run). |
| `sync pull` | Sync repo config -> local (update local environment). |
| `sync push` | Sync local config -> repo (for Docker deployment). |
| `sync secrets` | Deploy kctl credentials to Hetzner. |

### `kctl-claude update`

Check for updates and upgrade kctl-claude.

### `kctl-claude verify`

Verify Claude Code config completeness.
