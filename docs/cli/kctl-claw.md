# kctl-claw

Command reference for `kctl-claw` (37 groups, ~160 commands).

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

### `kctl-claw agents`

Manage OpenClaw agents.

| Command | Description |
|---------|-------------|
| `agents compare-models <name>` | Compare model performance for a given agent. |
| `agents get <name>` | Get detailed agent info. |
| `agents list` | List all configured agents. |
| `agents replay <conversation_id>` | Quick replay — replay a conversation and diff the output. |
| `agents set-model <name> <model>` | Change an agent's primary model. |
| `agents set-profile <name> <profile>` | Change an agent's tool profile. |
| `agents set-thinking <name> <mode>` | Change an agent's thinking mode. |
| `agents stats` | Show per-agent stats: message count, token usage. |
| `agents test <name> <prompt>` | Quick test — send a prompt to an agent and show the response. |
| `agents workspace <name>` | Show agent workspace structure. |

### `kctl-claw agents-test`

Test agent behavior: prompts, replay, regression, benchmarks.

| Command | Description |
|---------|-------------|
| `agents-test benchmark <agent> <prompt> [--models]` | Compare quality, cost, and latency across multiple models for an agent. |
| `agents-test compare <prompt> [--model_a] [--model_b]` | Side-by-side model comparison for a given prompt. |
| `agents-test regression <test_file>` | Run a YAML regression test suite (prompts + expected patterns). |
| `agents-test replay <conversation_id>` | Replay a conversation and diff the output against the original. |
| `agents-test run <agent> <prompt>` | Send a test prompt to an agent and capture the response. |

### `kctl-claw ai`

AI usage and cost analytics.

| Command | Description |
|---------|-------------|
| `ai cost` | Show cost projection (daily/weekly/monthly). |
| `ai models` | Show model breakdown (requests, tokens, latency per model). |
| `ai top-consumers` | Show top token consumers (by agent, cron job, skill). |
| `ai usage` | Show AI usage summary (tokens, cost, by model). |

### `kctl-claw al`

Alias: agents list

### `kctl-claw backup`

Backup and restore OpenClaw volumes.

| Command | Description |
|---------|-------------|
| `backup create` | Create a timestamped backup of Docker volumes. |
| `backup list` | List available backups with size and date. |
| `backup restore <backup>` | Restore volumes from a backup (destructive — requires confirmation). |

### `kctl-claw bc`

Alias: backup create

### `kctl-claw cl`

Alias: cron list

### `kctl-claw config`

Manage OpenClaw configuration files.

| Command | Description |
|---------|-------------|
| `config add <name> [--project_root] [--gateway_url]` | Add a new config profile. |
| `config current` | Show active profile and resolved context. |
| `config init [--profile_name] [--gateway_url] [--gateway_token]` | Initialize profile in ~/.config/kodemeio/config.yaml. |
| `config profiles` | List all config profiles. |
| `config reload` | Reload config by restarting the gateway container. |
| `config remove <name>` | Remove a config profile. |
| `config set <key> <value>` | Set a single config value in the active profile. |
| `config show <file>` | Pretty-print a config file. |
| `config test` | Verify configuration is valid. |
| `config use <name>` | Switch active config profile. |
| `config validate` | Validate all JSON config files against expected schema. |

### `kctl-claw config-drift`

Detect config drift between local and deployed container.

| Command | Description |
|---------|-------------|
| `config-drift check` | Compare local config/ vs deployed container config (summary). |
| `config-drift diff` | Show detailed diff between local and deployed container config. |
| `config-drift restore <snapshot_name>` | Restore local openclaw.json from a snapshot. |
| `config-drift snapshot` | Save deployed container config as a local baseline snapshot. |

### `kctl-claw cron`

Manage cron jobs.

| Command | Description |
|---------|-------------|
| `cron disable <job_id>` | Disable a cron job. |
| `cron dry-run <job_id>` | Quick alias — execute job in dry-run (info-only) mode. |
| `cron enable <job_id>` | Enable a disabled cron job. |
| `cron failures [--count]` | Show recent cron job failures with error details. |
| `cron get <job_id>` | Show cron job details. |
| `cron history <job_id> [--count]` | Show execution history for a cron job. |
| `cron list` | List all cron jobs. |
| `cron next <job_id> [--count]` | Show next scheduled runs for a cron job. |
| `cron set-model <job_id> <model>` | Change a cron job's model. |
| `cron set-schedule <job_id> <cron_expr>` | Update a cron job's schedule. |

### `kctl-claw cron-debug`

Debug cron jobs: dry-run, simulate, history, failures.

| Command | Description |
|---------|-------------|
| `cron-debug dry-run <job>` | Execute a cron job without side effects (info/dry-run mode). |
| `cron-debug failures [--count]` | Show recent cron job failures with error details. |
| `cron-debug history <job> [--count]` | Show execution history for a cron job with status and duration. |
| `cron-debug output <job>` | Show output of the last cron job execution. |
| `cron-debug simulate <job> [--from_date] [--to_date]` | Show execution times for a cron job over a date range. |

### `kctl-claw deploy`

Deploy and manage the OpenClaw gateway container.

| Command | Description |
|---------|-------------|
| `deploy canary <bot>` | Deploy to a single bot first (canary deployment). |
| `deploy diff` | Show config diff between local and deployed container config. |
| `deploy down` | Stop and remove gateway services (requires confirmation). |
| `deploy pull` | Pull the latest gateway image. |
| `deploy restart` | Restart the gateway service. |
| `deploy rollback` | Rollback to the previous deployment (restore latest backup config). |
| `deploy status` | Show container status. |
| `deploy up [--build]` | Build and start the gateway. |

### `kctl-claw docker`

Docker container management for OpenClaw services.

| Command | Description |
|---------|-------------|
| `docker logs [--service] [--tail]` | Show container logs for a service. |
| `docker ps` | List running containers for the OpenClaw project. |
| `docker resource-usage` | Show CPU and memory resource usage for OpenClaw containers. |
| `docker restart [--service]` | Restart a specific Docker service or all services. |
| `docker run-cmd <service> <cmd>` | Execute a command in a running container (safe: uses parameterized args). |

### `kctl-claw doctor`

Environment validation: check, fix, and report.

| Command | Description |
|---------|-------------|
| `doctor check` | Check Docker, Node.js, gateway health, MCP servers, and Telegram webhooks. |
| `doctor fix` | Auto-fix environment issues: rebuild container, sync config. |
| `doctor report` | Generate a full diagnostic report. |

### `kctl-claw du`

Alias: deploy up

### `kctl-claw env`

Manage environment variables (.env.prod vs .env.example).

| Command | Description |
|---------|-------------|
| `env check` | Compare .env.prod vs .env.example and show missing vars. |
| `env diff` | Show vars in .env.example that are missing or differ from .env.prod. |
| `env list` | List all env vars from .env.prod with redacted values. |

### `kctl-claw health`

Deep health checks for gateway, configs, and Docker.

| Command | Description |
|---------|-------------|
| `health check` | Full health check: config validation, Docker status, gateway ping. |
| `health gateway` | Check gateway health: uptime, version, active connections. |

### `kctl-claw hl`

Alias: health check

### `kctl-claw lint`

Lint configs, MCP servers, skills, and cron expressions.

| Command | Description |
|---------|-------------|
| `lint config` | Validate openclaw.json schema structure. |
| `lint cron` | Check cron expressions, agent references, and model references. |
| `lint mcp` | Validate MCP server configs in config.json. |
| `lint skills` | Validate skill markdown files for required frontmatter and structure. |

### `kctl-claw logs`

View OpenClaw gateway logs.

| Command | Description |
|---------|-------------|
| `logs errors [--lines]` | Show recent error-level log lines. |
| `logs search <pattern> [--lines]` | Search logs for a pattern. |
| `logs tail [--lines] [--follow]` | Tail gateway logs. |

### `kctl-claw lt`

Alias: logs tail

### `kctl-claw mcp`

Manage MCP server registry and tool profiles.

| Command | Description |
|---------|-------------|
| `mcp add-to-profile <server> <profile>` | Add an MCP server to a tool profile. |
| `mcp debug <server>` | Start an MCP server with JSON-RPC logging enabled. |
| `mcp get <server>` | Show MCP server config detail. |
| `mcp latency` | Show per-tool latency report from the gateway. |
| `mcp list` | List all MCP servers. |
| `mcp profiles` | Show tool profile assignments. |
| `mcp remove-from-profile <server> <profile>` | Remove an MCP server from a tool profile. |
| `mcp restart <server>` | Restart a specific MCP server via the gateway. |
| `mcp test-tool <server> <tool_name>` | Quick alias for mcp-test tool — invoke a tool and show the result. |
| `mcp tools <server>` | Show tools for an MCP server (placeholder — needs running container for full introspection). |

### `kctl-claw mcp-test`

Test MCP servers and tools.

| Command | Description |
|---------|-------------|
| `mcp-test all` | Test all tools in all MCP servers. |
| `mcp-test bench <server> <tool_name> [--iterations]` | Benchmark latency for an MCP tool invocation. |
| `mcp-test protocol <server> [--duration]` | Capture JSON-RPC messages for a server (protocol trace). |
| `mcp-test server <server_name>` | Health check all tools registered for a server. |
| `mcp-test tool <server> <tool_name> [--params]` | Invoke an MCP tool and validate the response. |

### `kctl-claw memory`

Manage agent memory and knowledge graph.

| Command | Description |
|---------|-------------|
| `memory age-report` | Report memory entries by age buckets. |
| `memory clear <agent>` | Clear an agent's memory (requires confirmation). |
| `memory dedupe` | Find similar or duplicate memory entries. |
| `memory export` | Export memory to JSON file (placeholder — requires running gateway). |
| `memory list` | List memory files from the workspace directory. |
| `memory prune` | Remove old memory entries (placeholder — requires running gateway). |
| `memory relevance` | Score memory entries by recency and estimated reference count. |
| `memory search <query>` | Search knowledge graph (BM25+vector). |
| `memory stats` | Show memory stats (file count, sizes) from workspace directory. |
| `memory validate` | Check MEMORY.md format in the workspace. |

### `kctl-claw ml`

Alias: mcp list

### `kctl-claw monitor`

Production monitoring: gateway, agents, MCP servers, alerts.

| Command | Description |
|---------|-------------|
| `monitor agents` | Check per-agent availability via the gateway. |
| `monitor alerts` | Alert on gateway, agent, or MCP failures. |
| `monitor gateway` | Check gateway health and display status. |
| `monitor mcp-health` | Check MCP server health (reads registry + pings gateway endpoint). |

### `kctl-claw pipeline`

CI/CD pipeline: validate, deploy, status, history.

| Command | Description |
|---------|-------------|
| `pipeline deploy` | Run the full deployment pipeline: validate -> build -> up. |
| `pipeline history` | Show deployment history from gateway API. |
| `pipeline status` | Show current deployment status. |
| `pipeline validate` | Validate all configs before deployment. |

### `kctl-claw prompts`

Manage system prompts: list, view, diff, test, history, optimize.

| Command | Description |
|---------|-------------|
| `prompts diff <name> [--base]` | Diff a prompt file between git refs. |
| `prompts get <name>` | View prompt content. |
| `prompts history <name>` | Show git log of changes to a prompt file. |
| `prompts list` | List all system prompts (agents, skills, workspace). |
| `prompts optimize <name>` | Token count analysis and optimization suggestions for a prompt. |
| `prompts test <name> <input_text>` | Test a prompt via the gateway with given input. |

### `kctl-claw security`

Security audit and credential management.

| Command | Description |
|---------|-------------|
| `security allowlist` | Show the Telegram allowlist (DMs and groups). |
| `security audit` | Run the 15-point security audit script. |
| `security credentials` | Check .env.prod for empty or placeholder values. |
| `security sandbox` | Show agent sandbox settings. |

### `kctl-claw skill`

Claude Code skill management.

| Command | Description |
|---------|-------------|
| `skill generate [--output] [--install]` | Auto-generate SKILL.md from CLI command registry. |

### `kctl-claw skills`

Manage OpenClaw skills.

| Command | Description |
|---------|-------------|
| `skills create <name>` | Create a new skill directory with SKILL.md template. |
| `skills delete <name> [--yes]` | Delete a skill directory. |
| `skills get <name>` | Read and print SKILL.md content. |
| `skills list` | List all skills. |

### `kctl-claw skills-test`

Test, lint, and validate OpenClaw skills.

| Command | Description |
|---------|-------------|
| `skills-test bench <skill>` | Measure skill execution time via the gateway. |
| `skills-test lint <skill>` | Validate skill markdown: required frontmatter fields and sections. |
| `skills-test run <skill> [--input_text]` | Execute a skill with test input via the gateway. |
| `skills-test validate` | Validate all skills: file refs, tool refs, frontmatter. |

### `kctl-claw st`

Alias: status overview

### `kctl-claw status`

Quick status dashboard.

### `kctl-claw telegram`

Manage Telegram bot configuration.

| Command | Description |
|---------|-------------|
| `telegram allowlist` | Show Telegram DM and group allowlists. |
| `telegram bindings` | Show bot-agent channel bindings. |
| `telegram bots` | List configured Telegram bots (name, token env var, bound agent). |
| `telegram recent <bot> [--count]` | Show recent messages for a bot. |
| `telegram simulate <bot> <message>` | Simulate a user message to a bot and show the agent response. |
| `telegram test-send <bot> <message>` | Send a test message via a configured bot. |
| `telegram webhook-status <bot>` | Check webhook delivery status for a bot. |

### `kctl-claw test`

Run unit, integration, and smoke tests.

| Command | Description |
|---------|-------------|
| `test integration` | Test MCP server communication (requires running container). |
| `test smoke` | Gateway health + agent response smoke test. |
| `test unit` | Run MCP server unit tests if test files exist. |

### `kctl-claw trading`

Trading bot operations (JournaltxDevBot).

| Command | Description |
|---------|-------------|
| `trading backtest <strategy> [--period]` | Run a historical backtest for a strategy. |
| `trading compare <strategy_a> <strategy_b>` | Compare performance of two strategies. |
| `trading history [--count]` | Show trade history. |
| `trading kill-switch` | Emergency stop all trading bots (requires confirmation). |
| `trading portfolio` | Show portfolio overview (positions, P&L, balances). |
| `trading risk-limits` | Show risk limits configuration. |
| `trading simulate <strategy>` | Start paper trading simulation for a strategy. |
| `trading status` | Show trading bot status (Freqtrade, QuantConnect, Hummingbot). |
| `trading strategies` | Show strategy performance summary. |
