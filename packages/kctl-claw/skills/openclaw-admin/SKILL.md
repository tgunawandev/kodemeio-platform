---
name: openclaw-admin
description: >
  OpenClaw AI gateway administration for kodemeio infrastructure.
  Covers agent management, cron jobs, MCP servers, skills, memory, trading,
  AI cost analytics, deployment, backup/restore, security audit, and Telegram
  bot management. Use when working with kctl-claw CLI or managing OpenClaw.
version: 1.0.0
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# OpenClaw Administration for Kodemeio

## Quick Commands

Most frequent operations at a glance:

| Command | Description |
|---------|-------------|
| `kctl-claw st` | Status overview (alias) |
| `kctl-claw hl` | Health check (alias) |
| `kctl-claw al` | List agents (alias) |
| `kctl-claw cl` | List cron jobs (alias) |
| `kctl-claw ml` | List MCP servers (alias) |
| `kctl-claw lt` | Tail logs (alias) |
| `kctl-claw bc` | Create backup (alias) |
| `kctl-claw du` | Deploy up (alias) |
| `kctl-claw status overview` | Full status dashboard |
| `kctl-claw health check` | Deep health check |
| `kctl-claw config validate` | Validate config files |
| `kctl-claw agents list` | List all agents with status |
| `kctl-claw cron list` | List all 27 cron jobs |
| `kctl-claw mcp list` | List 23 MCP servers |
| `kctl-claw security audit` | Run 15-point security audit |
| `kctl-claw backup create` | Create volume backup |
| `kctl-claw deploy up` | Start gateway |
| `kctl-claw ai usage` | AI cost & usage stats |
| `kctl-claw trading status` | Trading bot status |
| `kctl-claw memory stats` | Memory graph statistics |

## Architecture

OpenClaw is an AI Agent Gateway running in Docker on Dokploy.

- **Gateway**: Port 18789, Traefik reverse proxy → openclaw.kodeme.io
- **Version**: 2026.3.24 (pinned in docker-compose.prod.yml)
- **Agents**: 5 autonomous bots (4 company operators + 1 team assistant)
  - KodemeioDevBot — Opus 4.6, CEO/CTO/Sales/Finance/DevOps for kodeme.io
  - KontenosDevBot — Sonnet 4, Content/Social/Products for kontenos.com
  - JournaltxDevBot — Sonnet 4, Trading/Risk/Portfolio for journaltx.com
  - KidneuroDevBot — Sonnet 4, Healthcare/Product for kidneuro.io
  - KodemeioTeam — Sonnet 4, Team read-only assistant (no write ops)
- **MCP Servers**: 23 total (17 custom + 10 external npm)
- **Cron Jobs**: 27 autonomous jobs (Opus for strategy, Sonnet for content, Flash for routine)
- **Tool Profiles**: 6 profiles limiting per-turn MCP exposure
- **Volumes**: `openclaw-data` (config+auth), `openclaw-workspace` (agent memory+workspace)
- **Config**: `config/openclaw.json` (main), `config/config.json` (MCP registry), `config/cron/jobs.json`
- **Entry point**: `docker-compose.prod.yml` on dokploy.kodeme.io

## Status & Health

| Command | Description |
|---------|-------------|
| `kctl-claw status overview` | Full dashboard: gateway, agents, cron, MCP, memory |
| `kctl-claw status agents` | Agent status summary |
| `kctl-claw status cron` | Cron job status summary |
| `kctl-claw status mcp` | MCP server connectivity summary |
| `kctl-claw health check` | Deep check: gateway API, Docker, configs, MCP reachability |
| `kctl-claw health watch` | Continuous health monitoring (Ctrl+C to stop) |
| `kctl-claw health --json` | Machine-readable health output |

## Agent Management

| Command | Description |
|---------|-------------|
| `kctl-claw agents list` | List all agents with name, model, profile, status |
| `kctl-claw agents get <name>` | Full agent config details |
| `kctl-claw agents set-model <name> <model>` | Change agent model (e.g. claude-opus-4-6) |
| `kctl-claw agents set-profile <name> <profile>` | Change tool profile |
| `kctl-claw agents enable <name>` | Enable a disabled agent |
| `kctl-claw agents disable <name>` | Disable an agent |
| `kctl-claw agents sessions <name>` | List active sessions for agent |
| `kctl-claw agents reload` | Trigger agent config hot-reload |

Agent names: `kodemeiodev`, `kontenosdev`, `journaltxdev`, `kidneurodev`, `kodeimeoteam`

## Cron Management

| Command | Description |
|---------|-------------|
| `kctl-claw cron list` | List all 27 cron jobs with schedule, agent, status |
| `kctl-claw cron get <job-id>` | Job details: schedule, agent, model, last run |
| `kctl-claw cron enable <job-id>` | Enable a disabled job |
| `kctl-claw cron disable <job-id>` | Disable a job |
| `kctl-claw cron trigger <job-id>` | Trigger immediate execution |
| `kctl-claw cron history <job-id>` | Recent execution history |
| `kctl-claw cron set-schedule <job-id> <cron-expr>` | Change cron schedule |

Important: Never disable `system-health-check` or `daily-self-reflection` without explicit user request.

## MCP Servers

| Command | Description |
|---------|-------------|
| `kctl-claw mcp list` | List all 23 MCP servers with type and status |
| `kctl-claw mcp get <server-id>` | Server details: command, env vars, tools |
| `kctl-claw mcp test <server-id>` | Test connectivity / spawn server |
| `kctl-claw mcp profiles` | List tool profiles and their server assignments |
| `kctl-claw mcp profile-get <profile>` | Profile details: servers, denied tools |
| `kctl-claw mcp assign <server-id> <profile>` | Add server to profile |
| `kctl-claw mcp remove <server-id> <profile>` | Remove server from profile |

Profiles: `default`, `content`, `trading`, `kidneuro`, `team`, `all`

## Skill Management

| Command | Description |
|---------|-------------|
| `kctl-claw skills list` | List all 15 skills with agent assignments |
| `kctl-claw skills get <name>` | Skill details: command, description, agents |
| `kctl-claw skills create <name>` | Scaffold new skill from template |
| `kctl-claw skills delete <name>` | Remove skill |
| `kctl-claw skills assign <name> <agent>` | Assign skill to agent |
| `kctl-claw skills unassign <name> <agent>` | Remove skill from agent |
| `kctl-claw skills reload` | Hot-reload skills (requires `--live`) |

## Memory & Knowledge

| Command | Description |
|---------|-------------|
| `kctl-claw memory stats` | Memory graph stats: nodes, edges, topics |
| `kctl-claw memory search <query>` | BM25+vector hybrid search |
| `kctl-claw memory export` | Export memory graph to JSON |
| `kctl-claw memory prune --older-than <days>` | Prune entries older than N days |
| `kctl-claw memory clear <agent>` | Clear all memory for an agent (destructive) |

Memory prune requires an explicit age threshold — no default bulk delete.
Always backup before `memory clear`.

## Deployment

| Command | Description |
|---------|-------------|
| `kctl-claw deploy up` | Start gateway (`docker compose up -d`) |
| `kctl-claw deploy down` | Stop gateway |
| `kctl-claw deploy restart` | Restart gateway container |
| `kctl-claw deploy pull` | Pull latest image |
| `kctl-claw deploy verify` | Verify image hash and version |
| `kctl-claw deploy status` | Container status and uptime |
| `kctl-claw deploy logs` | Recent deploy logs |

Run `kctl-claw security audit` and `kctl-claw backup create` before deploying to production.
Use `--live` only when immediate config effect is required.

## Backup & Restore

| Command | Description |
|---------|-------------|
| `kctl-claw backup create` | Create timestamped backup of both volumes |
| `kctl-claw backup list` | List available backups with size and date |
| `kctl-claw backup restore <backup-id>` | Restore volumes from backup |
| `kctl-claw backup prune --keep <n>` | Delete old backups, keep latest N |
| `kctl-claw backup verify <backup-id>` | Verify backup integrity |

Always run `kctl-claw backup create` before: memory clear, restore, deploy, config reload with destructive changes.

## Trading Operations

| Command | Description |
|---------|-------------|
| `kctl-claw trading status` | Trading bot status: active, paused, positions |
| `kctl-claw trading portfolio` | Portfolio summary: assets, P&L, allocation |
| `kctl-claw trading kill-switch` | Emergency stop all trading (requires confirmation) |
| `kctl-claw trading risk-limits` | Show current risk limits |
| `kctl-claw trading set-risk <key> <value>` | Update a risk limit parameter |
| `kctl-claw trading history` | Recent trade history |

For trading kill switch: always confirm with user before executing.

## AI Cost Analytics

| Command | Description |
|---------|-------------|
| `kctl-claw ai usage` | Usage summary: tokens, requests, cost today/month |
| `kctl-claw ai projection` | Monthly cost projection based on current rate |
| `kctl-claw ai breakdown` | Cost breakdown by model (Opus/Sonnet/Flash) |
| `kctl-claw ai budget` | Budget status and alerts |
| `kctl-claw ai by-agent` | Usage breakdown per agent |
| `kctl-claw ai by-cron` | Usage breakdown per cron job |

## Security

| Command | Description |
|---------|-------------|
| `kctl-claw security audit` | Run 15-point security checklist |
| `kctl-claw security credentials` | List credentials (redacted values) |
| `kctl-claw security allowlist` | Show Telegram user allowlist |
| `kctl-claw security allowlist-add <user-id>` | Add user to Telegram allowlist |
| `kctl-claw security allowlist-remove <user-id>` | Remove user from allowlist |
| `kctl-claw security sandbox-status` | Show agent sandbox configuration |

Always show redacted values for env vars and credentials — never expose secrets.
Security audit must pass before any production deployment.

## Telegram Bots

| Command | Description |
|---------|-------------|
| `kctl-claw telegram list` | List all 5 bots with username and status |
| `kctl-claw telegram get <bot>` | Bot details: token (redacted), agent binding |
| `kctl-claw telegram bindings` | Show agent ↔ bot bindings |
| `kctl-claw telegram test <bot>` | Test bot connectivity via Telegram API |
| `kctl-claw telegram allowlist` | Show allowed user IDs |
| `kctl-claw telegram send <bot> <user-id> <message>` | Send test message |

Bots: `KodemeioDevBot`, `KontenosDevBot`, `JournaltxDevBot`, `KidneuroDevBot`, `KodemeioTeamBot`

## Environment Vars

| Command | Description |
|---------|-------------|
| `kctl-claw env check` | Validate .env.prod against .env.example template |
| `kctl-claw env diff` | Show keys present in example but missing from prod |
| `kctl-claw env list` | List all env var keys (values redacted) |
| `kctl-claw env template` | Regenerate .env.example from current .env.prod (redacted) |

Never output actual secret values. Always display redacted placeholders.

## Logs

| Command | Description |
|---------|-------------|
| `kctl-claw logs tail` | Tail gateway logs (like `docker compose logs -f`) |
| `kctl-claw logs tail --lines <n>` | Last N lines then follow |
| `kctl-claw logs search <pattern>` | Search logs for pattern |
| `kctl-claw logs agent <name>` | Filter logs for a specific agent |
| `kctl-claw logs errors` | Show only ERROR/FATAL log lines |
| `kctl-claw logs since <datetime>` | Logs since a specific time |

## Aliases

Short commands for fast terminal use (hidden from `--help`):

| Alias | Expands To |
|-------|-----------|
| `kctl-claw st` | `kctl-claw status overview` |
| `kctl-claw hl` | `kctl-claw health check` |
| `kctl-claw cl` | `kctl-claw cron list` |
| `kctl-claw al` | `kctl-claw agents list` |
| `kctl-claw ml` | `kctl-claw mcp list` |
| `kctl-claw lt` | `kctl-claw logs tail` |
| `kctl-claw bc` | `kctl-claw backup create` |
| `kctl-claw du` | `kctl-claw deploy up` |

All global options (`--json`, `--format`, `--profile`, `--quiet`, `--live`) are forwarded by aliases.

## Output Formats

| Flag | Description | Use Case |
|------|-------------|----------|
| `--json` | JSON output | Scripting, CI/CD pipelines |
| `--format csv` | CSV table output | Spreadsheet import |
| `--format yaml` | YAML output | Config review |
| `--format pretty` | Rich tables (default) | Human reading |
| `--quiet` / `-q` | Suppress info messages | Scripting |
| `--no-header` | Omit table header row | Scripting |

Example for scripting:
```bash
kctl-claw --json agents list | jq '.[].name'
kctl-claw --format csv cron list > cron-jobs.csv
kctl-claw --quiet backup create && echo "Backup OK"
```

## Troubleshooting

| Symptom | Likely Cause | Resolution |
|---------|-------------|------------|
| `Gateway connection refused` | Container not running | `kctl-claw deploy up` |
| `Config validation failed` | Malformed JSON in config | `kctl-claw config validate` + fix errors |
| `MCP server unreachable` | Wrong path or env vars | `kctl-claw mcp test <server-id>` |
| `Cron not firing` | Job disabled or wrong schedule | `kctl-claw cron get <job-id>` |
| `Agent not responding` | Token exhausted or model error | `kctl-claw logs agent <name>` |
| `Backup restore fails` | Volume busy or wrong backup-id | `kctl-claw deploy down` then restore |
| `Trading bot stuck` | Risk limit hit | `kctl-claw trading status` + check limits |
| `High AI costs` | Opus used for routine tasks | `kctl-claw ai breakdown` + tune cron models |
| `Telegram bot offline` | Webhook conflict or invalid token | `kctl-claw telegram test <bot>` |
| `Memory search empty` | No entries or wrong agent scope | `kctl-claw memory stats` |

For persistent issues, check `kctl-claw logs errors` and `kctl-claw health check --json`.

## Rules

Enforcement rules for safe OpenClaw operations:

1. **Validate before reload**: Always run `kctl-claw config validate` before `kctl-claw config reload`
2. **Backup before destructive ops**: Always run `kctl-claw backup create` before memory clear, restore, or deploy with destructive config changes
3. **Protect system cron jobs**: Never disable `system-health-check` or `daily-self-reflection` without explicit user request
4. **Live flag intent**: Use `--live` only when the user wants immediate effect — default to config-only changes
5. **Trading kill switch**: Always confirm with the user before executing `kctl-claw trading kill-switch`
6. **Security first**: Security audit must pass (`kctl-claw security audit`) before any production deployment
7. **Memory prune threshold**: Memory prune requires an explicit `--older-than <days>` argument — no default bulk delete
8. **No secret exposure**: Always show redacted values for env vars and credentials — never output actual secrets
