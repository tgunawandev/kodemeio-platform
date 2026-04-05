---
name: grafana-admin
description: >
  Grafana monitoring platform administration via kctl-grafana CLI (12 groups, ~33 commands).
  MUST use for ANY kctl-grafana operation.
  Triggers on: "alert", "annotation", "backup", "check", "config", "contacts", "dashboard", "datasource", "deploy", "detailed", "export", "folder", "generate", "health", "import", "init", "kctl-grafana", "overview", "profile", "remove", "restore", "search", "selftest", "silence", "skill", "star", "status", "test", "user".
  Auto-generated: 2026-04-05
  registry_hash: bf42f2813358
---

# grafana-admin — kctl-grafana CLI Reference

> Auto-generated from `kctl-grafana` command registry. Do not edit manually.
> To regenerate: `kctl-grafana skill generate`
> To add custom content: edit `SKILL.extra.md` in the same directory.

## Overview

**CLI:** `kctl-grafana`
**Command groups:** 12
**Total commands:** ~33
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

### `kctl-grafana alert`

Alert rule management.

| Command | Description |
|---------|-------------|
| `alert contacts` | List notification contact points. |
| `alert list` | List alert rules with current state. |
| `alert show <uid>` | Show alert rule details. |
| `alert silence <uid> [--duration] [--comment]` | Silence an alert rule for a given duration. |

### `kctl-grafana annotation`

Annotation management (deploy markers, events).

| Command | Description |
|---------|-------------|
| `annotation add <text> [--tags] [--dashboard_uid]` | Add an annotation (useful for deploy markers). |
| `annotation list [--from_time] [--to_time] [--tags] [--limit]` | List recent annotations. |

### `kctl-grafana backup`

Backup and restore dashboards and datasources.

| Command | Description |
|---------|-------------|
| `backup create [--output_dir]` | Export all dashboards and datasources to a backup directory. |
| `backup restore <backup_dir> [--skip_datasources] [--skip_dashboards]` | Restore dashboards and datasources from a backup directory. |

### `kctl-grafana config`

Manage CLI configuration and profiles.

| Command | Description |
|---------|-------------|
| `config export` | Export current configuration as YAML. |
| `config init [--url] [--api_key] [--org_id] [--name]` | Initialize CLI configuration. |
| `config remove <name> [--force]` | Remove a profile. |
| `config show` | Show configuration (keys masked). |
| `config test` | Test API connection. |
| `config use <name>` | Switch default profile. |

### `kctl-grafana dashboard`

Dashboard management.

| Command | Description |
|---------|-------------|
| `dashboard export <uid> [--output_file]` | Export dashboard JSON to file. |
| `dashboard import <file_path> [--folder_uid] [--overwrite]` | Import dashboard from JSON file. |
| `dashboard list` | List all dashboards. |
| `dashboard search <query>` | Search dashboards by name or tag. |
| `dashboard show <uid>` | Show dashboard metadata and panel summary. |
| `dashboard star <uid> [--unstar]` | Star or unstar a dashboard. |

### `kctl-grafana datasource`

Datasource management.

| Command | Description |
|---------|-------------|
| `datasource list` | List all datasources with type and status. |
| `datasource show <name>` | Show datasource configuration details. |
| `datasource test [--name]` | Test datasource connectivity. |

### `kctl-grafana folder`

Folder organization.

| Command | Description |
|---------|-------------|
| `folder create <title> [--uid]` | Create a new folder. |
| `folder delete <uid> [--force]` | Delete a folder and all its dashboards. |
| `folder list` | List all folders. |

### `kctl-grafana health`

Health checks for Grafana API.

| Command | Description |
|---------|-------------|
| `health check` | Check Grafana API connectivity, version, and org info. |
| `health detailed` | Detailed health check including all datasources. |

### `kctl-grafana selftest`

Self-test diagnostics.

| Command | Description |
|---------|-------------|
| `selftest run` | Run diagnostic checks for kctl-grafana. |

### `kctl-grafana skill`

Claude Code skill management.

| Command | Description |
|---------|-------------|
| `skill generate [--output] [--install] [--check]` | Auto-generate SKILL.md from CLI command registry. |

**Examples:**
```bash
kctl-grafana skill generate
kctl-grafana skill generate --install
kctl-grafana skill generate --check
```

### `kctl-grafana status`

Quick status overview.

| Command | Description |
|---------|-------------|
| `status overview` | Show Grafana status overview: dashboard count, datasource health, active alerts, version. |

### `kctl-grafana user`

Organization user management.

| Command | Description |
|---------|-------------|
| `user add <email> [--role]` | Add a user to the organization. |
| `user list` | List organization users. |

## Configuration

Shared config: `~/.config/kodemeio/config.yaml`

```bash
kctl-grafana config init       # Interactive setup
kctl-grafana config show       # Show current config
kctl-grafana config profiles   # List profiles
kctl-grafana config current    # Show active profile
kctl-grafana config validate   # Verify config
```
