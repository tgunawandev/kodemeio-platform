# kctl-odoo

Kodemeio Odoo CLI -- manage Odoo 18 ERP instances via JSON-RPC and Docker Compose.

## Installation

```bash
uv tool install ./cli
```

To upgrade after code changes:

```bash
uv tool install --force --reinstall ./cli
```

## Quick Start

```bash
# Configure connection (interactive)
kctl-odoo config init

# Verify connectivity
kctl-odoo config test

# Dashboard overview
kctl-odoo dashboard info

# List installed modules
kctl-odoo modules list --state installed

# Health check
kctl-odoo troubleshoot check
```

## Fast debugging — log tailing

`kctl-odoo logs tail` is a unified streaming command for local + remote Odoo
with structured filters. It auto-detects the transport from the current
profile URL:

- **local** (`localhost` / `127.0.0.1`) → streams `docker compose logs -f` in
  the project directory.
- **remote** → streams `docker logs -f` over SSH via `kctl-dokploy compose
  service-logs --follow`. Requires `--compose-id` (find with `kctl-dokploy
  compose list`).

```bash
# Local dev — stream everything
kctl-odoo logs tail

# Local dev — only warnings and above from the account.move module
kctl-odoo logs tail --level WARNING --module account.move

# Remote prod — stream tpp-odoo-erp
kctl-odoo -p idtpp-tpp-odoo-erp logs tail \
    --dokploy-profile idtpp \
    --compose-id Qki8U2u4Ltstq0_6zW7UE

# Narrow by worker PID or request id in the message
kctl-odoo logs tail --worker 12 --grep "traceback"
```

Filter flags compose as AND: `--level`, `--module`, `--request`, `--worker`,
`--grep`.

**Full traceback capture.** Filters apply per *log record*, not per line. When
a record's timestamped header matches, all of its continuation lines
(`Traceback (most recent call last):`, `File "..."`, `^^^`, exception
message) are emitted too — stack traces survive `--level ERROR` or any
other filter. `--grep` can also match a continuation line directly (e.g.
`--grep "fields.py"` to find tracebacks involving a specific file); when
it does, the rest of that record's block is included.

Other `logs` subcommands:

- `logs follow` — legacy local-only streamer (kept for back-compat).
- `logs errors --days N` — finite query against Odoo's `ir.logging` model.
- `logs search <pattern>` — finite ilike search against `ir.logging`.

## Command Groups

| Group            | Description                                          |
|------------------|------------------------------------------------------|
| `accounting`     | Accounting transactional operations (invoices, payments, entries) |
| `backup`         | Database backup and restore operations               |
| `bundles`        | Module bundle management (install/list YAML bundles)  |
| `cleanup`        | Stale data cleanup operations                         |
| `companies`      | Company and multi-company management                  |
| `config`         | CLI configuration (profiles, init, test)              |
| `cron`           | Scheduled action (ir.cron) management                 |
| `dashboard`      | Instance overview and statistics                      |
| `databases`      | Database CRUD operations                              |
| `deploy`         | Deployment and release management                     |
| `dev`            | Developer tools (scaffold, aggregate, link-addons)    |
| `diff`           | Compare module states across databases/snapshots      |
| `export`         | Data export (CSV, JSON, XML)                          |
| `generate`       | Code generation (module scaffold, models, views)      |
| `history`        | Operation history tracking                            |
| `hr`             | HR operations (employees, leaves, payslips, expenses) |
| `import`         | Data import from files                                |
| `integration`    | External integration management                       |
| `inventory`      | Inventory operations (stock, transfers, adjustments)  |
| `jobs`           | Background job / queue_job management                 |
| `local`          | Docker Compose lifecycle (up, down, restart, logs)    |
| `logs`           | Container log streaming and filtering                 |
| `mail`           | Mail server and outgoing email management             |
| `maintenance`    | Database maintenance (vacuum, reindex, cleanup)       |
| `master-data`    | Master data configuration and seeding                 |
| `migrate`        | Data migration tools and utilities                    |
| `modules`        | Module install, upgrade, list, and info               |
| `partners`       | Partner (res.partner) queries and bulk ops            |
| `performance`    | Performance profiling and slow-query analysis         |
| `profiles`       | Installation profile management                       |
| `purchasing`     | Purchasing operations (POs, receipts, vendor bills)   |
| `repl`           | Interactive Python REPL with Odoo connection          |
| `report`         | Report template and PDF management                    |
| `sales`          | Sales operations (SOs, deliveries, CRM pipeline)      |
| `security`       | Access rights, record rules, and audit                |
| `server`         | Server configuration, system parameters, and tuning   |
| `sessions`       | User session inspection and cleanup                   |
| `shell`          | Interactive Odoo shell (inside container)             |
| `storage`        | Attachment and filestore management                   |
| `tax`            | Indonesian tax operations (PPN/PPh summaries, faktur) |
| `tenants`        | Multi-tenant / SaaS instance management               |
| `test`           | Test runner with result parsing and summary           |
| `troubleshoot`   | Diagnostic commands, health checks, and connectivity  |
| `users`          | User CRUD, password reset, role management            |
| `workers`        | Worker process inspection and scaling                 |

## Command Aliases

Hidden short aliases are available for common workflows:

| Alias | Expands to               |
|-------|--------------------------|
| `mi`  | `modules install <name>` |
| `mu`  | `modules upgrade <name>` |
| `ml`  | `modules list`           |
| `hc`  | `troubleshoot check`     |
| `di`  | `dashboard info`         |
| `bl`  | `bundles list`           |
| `bi`  | `bundles install <name>` |
| `pl`  | `profiles list`          |
| `pi`  | `profiles install <name>`|
| `tr`  | `test run <module>`      |

Example:

```bash
kctl-odoo mi sale_management       # same as: kctl-odoo modules install sale_management
kctl-odoo tr base_management       # same as: kctl-odoo test run base_management
```

## Global Options

```
--json            Output as JSON (machine-readable)
--quiet, -q       Suppress informational messages
--profile, -p     Use a named config profile
--url             Odoo URL override
--api-key         API key override
--database, -d    Database override
--username, -u    Username override
--version, -V     Show version and exit
```

## Configuration

### Profiles

kctl-odoo supports named profiles for managing multiple Odoo instances:

```bash
# Create profiles
kctl-odoo config add production --url https://erp.kodeme.io --database kodemeio --api-key $KEY
kctl-odoo config add staging --url https://staging.kodeme.io --database staging --api-key $KEY

# Switch default profile
kctl-odoo config use production

# Use per-command
kctl-odoo --profile staging modules list

# List all profiles
kctl-odoo config list
```

### Config File

Configuration is stored in `~/.config/kctl-odoo/config.toml` (XDG-compliant).

## Shell Completions

```bash
# Install for your shell
kctl-odoo --install-completion bash
kctl-odoo --install-completion zsh
kctl-odoo --install-completion fish
```

See [docs/completions.md](docs/completions.md) for manual installation and troubleshooting.

## Plugin Development

kctl-odoo supports extending the CLI via Python entry points. Create a package that
registers a Typer app under the `kctl_odoo.plugins` entry point group:

```toml
# In your plugin's pyproject.toml
[project.entry-points."kctl_odoo.plugins"]
my_plugin = "my_plugin.cli:app"
```

The plugin's `app` (a `typer.Typer` instance) will be registered as a command group
automatically on startup.

## New in This Version

- **SQLite history tracking** — All CLI operations are recorded locally. Use `kctl-odoo history` to query past commands, timings, and outcomes.
- **Runner abstraction** — Subprocess management extracted into a reusable `Runner` class in `core/`, replacing ad-hoc `subprocess.run` calls.
- **Command group consolidation** — Reduced from 58 to 53 groups. `biz` group eliminated; 22 business commands redistributed to `sales`, `purchasing`, `inventory`, `hr`, `accounting`, `dashboard`. `maintenance update-list` moved to `modules scan`. `maintenance accounting-close` / `inventory-close` moved to `accounting close-period` / `inventory close-period`. `maintenance run-autovacuum` renamed to `maintenance autovacuum`.
- **Verb-first command names** — 52 commands renamed to verb-first pattern (e.g., `invoice-get` → `get-invoice`, `order-confirm` → `confirm-order`). 11 duplicate commands removed.

## Development

### Running Tests

```bash
cd cli
uv run pytest tests/ -v
```

### Linting and Formatting

```bash
cd cli
uv run ruff check src/
uv run ruff format src/
```

### Type Checking

```bash
cd cli
uv run mypy src/kctl_odoo/
```

### Project Structure

```
cli/
  src/kctl_odoo/
    cli.py              Main app + command registration
    __init__.py         Version
    core/
      callbacks.py      Global option handling (AppContext)
      client.py         JSON-RPC client for remote Odoo
      local.py          Docker Compose client for local dev
      config.py         Profile/config management
      exceptions.py     Custom exception hierarchy
      output.py         Output formatting (table, JSON, plain)
    commands/
      aliases.py        Short command aliases
      modules.py        Module management
      testing.py        Test runner with result parsing
      ...               (50+ command modules)
  tests/                pytest test suite
  pyproject.toml        Package metadata and tool config
  README.md             This file
  docs/                 Additional documentation
```
