---
name: 1password-admin
description: >
  1Password secret management via kctl-op CLI (12 groups, ~27 commands).
  MUST use for ANY kctl-op operation.
  Triggers on: "backup", "check", "clean", "config", "current", "dashboard", "diff", "discover", "envs", "generate", "health", "info", "init", "items", "kctl-op", "list", "migrate", "profile", "profiles", "projects", "pull", "push", "remove", "restore", "skill", "status", "test", "vault".
  Auto-generated: 2026-04-05
  registry_hash: d1005426c491
---

# 1password-admin — kctl-op CLI Reference

> Auto-generated from `kctl-op` command registry. Do not edit manually.
> To regenerate: `kctl-op skill generate`
> To add custom content: edit `SKILL.extra.md` in the same directory.

## Overview

**CLI:** `kctl-op`
**Command groups:** 12
**Total commands:** ~27
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

### `kctl-op skill`

Claude Code skill management.

| Command | Description |
|---------|-------------|
| `skill generate [--output] [--install] [--check]` | Auto-generate SKILL.md from CLI command registry. |

**Examples:**
```bash
kctl-op skill generate
kctl-op skill generate --install
kctl-op skill generate --check
```

### `kctl-op status`

Check sync status.

### `kctl-op vault`

Vault management operations.

| Command | Description |
|---------|-------------|
| `vault create [--name] [--description]` | Create a new 1Password vault. |
| `vault info` | Show vault details. |
| `vault items` | List all items in the vault with metadata. |

## Configuration

Shared config: `~/.config/kodemeio/config.yaml`

```bash
kctl-op config init       # Interactive setup
kctl-op config show       # Show current config
kctl-op config profiles   # List profiles
kctl-op config current    # Show active profile
kctl-op config validate   # Verify config
```
