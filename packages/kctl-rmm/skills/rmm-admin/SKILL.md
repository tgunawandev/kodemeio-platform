---
name: rmm-admin
description: >
  Tactical RMM remote monitoring via kctl-rmm CLI (19 groups, ~68 commands).
  MUST use for ANY kctl-rmm operation.
  Triggers on: "agents", "alerts", "check", "check-printer", "checks", "clients", "config", "connect", "current", "dashboard", "deploy", "dismiss", "drivers", "generate", "health", "history", "init", "install", "install-pos58", "kctl-rmm", "linux", "logs", "maintenance", "mesh", "migrate", "offline", "patches", "ping", "profile", "profiles", "reboot", "remote", "remove", "restart", "results", "rustdesk", "scan", "scripts", "search", "services", "setup", "sites", "skill", "software", "start", "stop", "summary", "takecontrol", "tasks", "terminal", "test", "transfer", "uninstall", "winupdates".
  Auto-generated: 2026-04-05
  registry_hash: caa7b6286d08
---

# rmm-admin — kctl-rmm CLI Reference

> Auto-generated from `kctl-rmm` command registry. Do not edit manually.
> To regenerate: `kctl-rmm skill generate`
> To add custom content: edit `SKILL.extra.md` in the same directory.

## Overview

**CLI:** `kctl-rmm`
**Command groups:** 19
**Total commands:** ~68
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

### `kctl-rmm agents`

Manage Tactical RMM agents.

| Command | Description |
|---------|-------------|
| `agents get <agent_id>` | Get agent details. |
| `agents list [--detail] [--client] [--site]` | List all agents. |
| `agents offline` | List agents that are offline/unreachable. |
| `agents ping <agent_id>` | Ping an agent to check connectivity. |
| `agents reboot <agent_id> [--force]` | Reboot a remote machine. |
| `agents summary` | Agent count summary by client/site, online/offline. |
| `agents update <agent_id>` | Trigger agent update. |

### `kctl-rmm alerts`

Manage alerts.

| Command | Description |
|---------|-------------|
| `alerts dismiss <alert_id>` | Dismiss an alert. |
| `alerts list [--severity]` | List active alerts. |

### `kctl-rmm checks`

Manage automated checks.

| Command | Description |
|---------|-------------|
| `checks create <agent> <check_type> [--name] [--threshold] [--alert_severity]` | Create an automated check on an agent. |
| `checks delete <check_id> [--force]` | Delete an automated check. |
| `checks list [--agent]` | List automated checks. |
| `checks results <check_id>` | Show results/history for a check. |
| `checks run <check_id>` | Manually run a check. |

### `kctl-rmm clients`

Manage clients and sites.

| Command | Description |
|---------|-------------|
| `clients get <client_id>` | Get client details with sites. |
| `clients list` | List all clients. |
| `clients sites [--client_filter]` | List all sites. |

### `kctl-rmm config`

Manage CLI configuration and profiles.

| Command | Description |
|---------|-------------|
| `config add <name> [--url] [--api_key] [--mesh_url] [--set_default]` | Add or update a profile's RMM connection. |
| `config current` | Show the active profile and connection status. |
| `config init [--url] [--api_key] [--mesh_url] [--name]` | Initialize CLI configuration (interactive if no flags given). |
| `config migrate` | Migrate config from flat format to service-scoped format. |
| `config profiles` | List all profiles with RMM connection status. |
| `config remove <name> [--force] [--service_only]` | Remove a profile or just its RMM config. |
| `config set <key> <value> [--profile_arg]` | Set a configuration value for the current service. |
| `config show` | Show full configuration (API keys masked). |
| `config test` | Test API connection with current configuration. |
| `config use <name>` | Switch the default profile. |

### `kctl-rmm dashboard`

System overview dashboard.

### `kctl-rmm drivers`

Driver management (POS58 thermal printer).

| Command | Description |
|---------|-------------|
| `drivers check-printer <agent_id> [--timeout]` | Check printer/USB info on an agent (script 135). |
| `drivers install-pos58 <agent_id> [--timeout]` | Install POS58 thermal printer driver on an agent (script 136). |

### `kctl-rmm health`

Health checks and diagnostics.

### `kctl-rmm linux`

Linux agent management (install/update/uninstall via LinuxRMM-Script).

| Command | Description |
|---------|-------------|
| `linux install [--mesh_agent_url] [--auth_key] [--client_name] [--site_name] [--client_id] [--site_id] [--agent_type] [--ssh_host] [--ssh_port] [--dry_run]` | Install Tactical RMM agent on a Linux machine. |
| `linux status <ssh_host> [--ssh_port]` | Check Linux agent status on a remote host via SSH. |
| `linux uninstall [--mesh_fqdn] [--mesh_id] [--ssh_host] [--ssh_port] [--dry_run]` | Uninstall the Tactical RMM agent from a Linux machine. |
| `linux update [--ssh_host] [--ssh_port] [--dry_run]` | Update the Tactical RMM agent on a Linux machine. |

### `kctl-rmm maintenance`

RMM stack maintenance (docker services).

| Command | Description |
|---------|-------------|
| `maintenance logs <service> [--lines]` | Show log command for a service. |
| `maintenance restart <service>` | Show restart command for a service. |
| `maintenance status` | Show expected RMM service list and API health. |

### `kctl-rmm patches`

Manage Windows patches and updates.

| Command | Description |
|---------|-------------|
| `patches install <agent_id> [--all_patches] [--kb]` | Install patches on an agent. |
| `patches list <agent_id>` | List pending patches for an agent. |
| `patches scan <agent_id>` | Trigger a patch scan on an agent. |

### `kctl-rmm remote`

Remote access (Take Control, terminal, MeshCentral).

| Command | Description |
|---------|-------------|
| `remote mesh` | Open MeshCentral dashboard in browser. |
| `remote rmm` | Open Tactical RMM dashboard in browser. |
| `remote takecontrol <agent>` | Take Control of agent (opens TRMM remote desktop). |
| `remote terminal <agent>` | Open terminal for agent via MeshCentral. |

### `kctl-rmm rustdesk`

RustDesk remote access (connect, deploy, manage).

| Command | Description |
|---------|-------------|
| `rustdesk connect <agent>` | Open RustDesk remote session to agent. |
| `rustdesk deploy [--agent_id] [--all_agents] [--client_filter] [--timeout]` | Deploy RustDesk client to agent(s) via TRMM script. |
| `rustdesk list [--client_filter] [--installed_only]` | List agents with their RustDesk IDs. |
| `rustdesk setup` | One-time setup: create TRMM custom fields and upload RustDesk scripts. |
| `rustdesk status <agent_id> [--timeout]` | Check RustDesk status on an agent (runs check script). |
| `rustdesk transfer <agent>` | Open RustDesk file transfer session to agent. |

### `kctl-rmm scripts`

Manage and execute scripts.

| Command | Description |
|---------|-------------|
| `scripts create <name> [--shell] [--file] [--description] [--timeout]` | Upload a new script. |
| `scripts get <script_id>` | Get script details. |
| `scripts history [--agent]` | View script execution history. |
| `scripts list` | List all scripts. |
| `scripts run <script_id> [--agent] [--all_agents] [--client_filter] [--timeout]` | Run a script on agent(s). |

### `kctl-rmm services`

Manage Windows services on remote agents.

| Command | Description |
|---------|-------------|
| `services list <agent_id>` | List Windows services on an agent. |
| `services restart <agent_id> <service_name>` | Restart a Windows service. |
| `services start <agent_id> <service_name>` | Start a Windows service. |
| `services stop <agent_id> <service_name>` | Stop a Windows service. |

### `kctl-rmm skill`

Claude Code skill management.

| Command | Description |
|---------|-------------|
| `skill generate [--output] [--install] [--check]` | Auto-generate SKILL.md from CLI command registry. |

**Examples:**
```bash
kctl-rmm skill generate
kctl-rmm skill generate --install
kctl-rmm skill generate --check
```

### `kctl-rmm software`

Software inventory management.

| Command | Description |
|---------|-------------|
| `software list <agent_id>` | List installed software on an agent. |
| `software search <name> [--agent_id]` | Search for software across agents. |

### `kctl-rmm tasks`

Manage automated tasks.

| Command | Description |
|---------|-------------|
| `tasks list [--agent]` | List automated tasks. |
| `tasks run <task_id>` | Trigger a task manually. |

### `kctl-rmm winupdates`

Manage Windows Updates on agents.

| Command | Description |
|---------|-------------|
| `winupdates install <agent_id> [--kb] [--all_updates] [--reboot]` | Install Windows updates on an agent. |
| `winupdates list <agent_id>` | List Windows updates for an agent. |
| `winupdates scan <agent_id>` | Trigger a Windows Update scan on an agent. |

## Configuration

Shared config: `~/.config/kodemeio/config.yaml`

```bash
kctl-rmm config init       # Interactive setup
kctl-rmm config show       # Show current config
kctl-rmm config profiles   # List profiles
kctl-rmm config current    # Show active profile
kctl-rmm config validate   # Verify config
```
