# kctl-odoo

Command reference for `kctl-odoo` (101 groups, ~729 commands).

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

### `kctl-odoo accounting`

Accounting: invoices, journal entries, payments, aging reports.

| Command | Description |
|---------|-------------|
| `accounting aged-payable [--limit]` | AP aging report. |
| `accounting aged-receivable [--limit]` | AR aging report. |
| `accounting audit-trail [--invoice] [--days] [--limit]` | Audit trail for accounting entries — who posted/modified what. |
| `accounting bank-status` | Bank account balances and reconciliation status. |
| `accounting batch-post [--move_type] [--limit] [--force]` | Post all draft invoices/bills of a given type. |
| `accounting cancel-invoice <ids> [--force]` | Cancel posted invoices/bills (reverse to draft). |
| `accounting close-period [--period_end]` | Period/year-end accounting close validation. |
| `accounting create-entry <journal_name> <lines_str> [--ref] [--date] [--dry_run] [--force]` | Create a manual journal entry. |
| `accounting create-invoice <partner_name> <product_name> [--qty] [--price] [--inv_type] [--dry_run] [--force]` | Create a customer or vendor invoice. |
| `accounting get-invoice <number>` | Get invoice detail by number or ID. |
| `accounting gl-detail <account_code> [--date_from] [--date_to] [--limit]` | General ledger detail for a specific account. |
| `accounting gl-export <account_code> [--date_from] [--date_to] [--output] [--fmt]` | Export general ledger detail to CSV file. |
| `accounting invoices [--state] [--inv_type] [--partner] [--date_from] [--date_to] [--limit]` | List invoices. |
| `accounting journal-entries [--journal] [--date_from] [--date_to] [--ref] [--partner] [--limit]` | List journal entries. |
| `accounting lock-period <date> [--tax_only] [--force]` | Set accounting lock date. |
| `accounting overdue [--days] [--limit]` | List overdue invoices (customer and vendor). |
| `accounting post-invoice <ids> [--force]` | Post one or more draft invoices/bills. |
| `accounting register-payment <invoice_number> [--amount] [--journal_name] [--force]` | Register payment for an invoice. |
| `accounting revalue-currency [--date] [--dry_run]` | Multi-currency revaluation check. |
| `accounting summary [--period]` | Accounting dashboard — invoices, receivables, payables, aging. |
| `accounting trial-balance [--date_from] [--date_to] [--limit]` | Trial balance report. |
| `accounting unreconciled [--account] [--limit]` | Show unreconciled journal items. |

### `kctl-odoo addons`

Addon analysis, health scoring, and bundle coverage audits.

| Command | Description |
|---------|-------------|
| `addons coverage [--addon_paths] [--dir_path]` | Show bundle coverage: how many disk addons are in at least one bundle. |
| `addons deps-graph [--module] [--format_] [--addon_paths]` | Show dependency graph from manifest depends keys. |
| `addons drift <profile> [--dir_path] [--addon_paths]` | Compare profile YAML vs live Odoo installed modules. |
| `addons drift-snapshot <profile> <snapshot_file> [--dir_path] [--addon_paths]` | Compare profile YAML vs a snapshot JSON file (offline). |
| `addons duplicates [--addon_paths]` | Find addon names that appear in multiple source directories. |
| `addons health <name> [--addon_paths]` | Show health score for a single addon. |
| `addons health-summary [--source] [--addon_paths]` | Aggregate health scores across addons, sorted worst-first. |
| `addons matrix [--dir_path] [--addon_paths] [--source]` | Show addon x profile matrix. |
| `addons missing [--addon_paths] [--dir_path]` | Find modules in bundles that are not on disk. |
| `addons orphans [--addon_paths] [--dir_path]` | Find addons on disk not referenced in any bundle. |
| `addons report [--addon_paths] [--dir_path] [--output_file]` | Full audit: orphans + missing + duplicates + health + coverage. |
| `addons scan [--addon_paths]` | List all addons discovered on disk. |

### `kctl-odoo approvals`

Approval center: pending requests, approve, reject, delegate.

| Command | Description |
|---------|-------------|
| `approvals approve <model> <res_id> [--comment] [--force]` | Approve a tier validation for a record. |
| `approvals delegate <model> <res_id> <to_user>` | Delegate an approval to another user. |
| `approvals escalated [--limit]` | List tier reviews that are past their review deadline. |
| `approvals history [--user] [--limit]` | List validated or rejected tier reviews (approval history). |
| `approvals pending [--review_type] [--user] [--limit]` | List pending tier review requests. |
| `approvals reject <model> <res_id> [--reason] [--force]` | Reject a tier validation for a record. |
| `approvals sla-status` | Show SLA statistics for approvals. |
| `approvals summary` | Show summary of pending approvals and SLA violations. |

### `kctl-odoo assets`

Fixed assets: depreciation, disposal, tracking.

| Command | Description |
|---------|-------------|
| `assets depreciation-schedule <asset_id>` | Show depreciation schedule for an asset. |
| `assets get <asset_id>` | Show asset detail. |
| `assets list [--state] [--limit]` | List fixed assets. |
| `assets post-depreciation [--dep_date] [--dry_run]` | Trigger depreciation posting for pending lines. |
| `assets summary` | Asset statistics — counts and values by state. |

### `kctl-odoo audit`

Audit trail: view and manage auditlog records.

| Command | Description |
|---------|-------------|
| `audit cleanup [--days] [--dry_run] [--force]` | Delete old audit log entries. |
| `audit detail <log_id>` | Show detail of an audit log entry including field changes. |
| `audit list [--model] [--user] [--days] [--limit]` | List audit log entries. |
| `audit rules` | List auditlog rules (which models are tracked). |

### `kctl-odoo auto-maintain`

Automated maintenance: cleanup, retry, auto-fix.

| Command | Description |
|---------|-------------|
| `auto-maintain report [--days]` | Show current maintenance stats. |
| `auto-maintain run [--dry_run]` | Full maintenance pass. |
| `auto-maintain schedule` | Show instructions for scheduling auto-maintain via system cron. |

### `kctl-odoo automation`

Server actions and automated rules.

| Command | Description |
|---------|-------------|
| `automation actions [--model] [--limit]` | List ir.actions.server records. |
| `automation disable <rule_id>` | Disable an automation rule (set active=False). |
| `automation enable <rule_id>` | Enable an automation rule (set active=True). |
| `automation history <rule_id> [--limit]` | Show execution history for an automation rule. |
| `automation rules [--model] [--limit]` | List base.automation records (automated rules). |
| `automation run <action_id> [--record_ids]` | Execute an ir.actions.server action. |

### `kctl-odoo backup`

Database backup and restore operations.

| Command | Description |
|---------|-------------|
| `backup create [--database] [--fmt] [--output]` | Create a database backup. |
| `backup dr-status [--rpo_hours]` | Disaster recovery readiness report. |
| `backup list` | List databases with availability info. |
| `backup restore <backup_file> [--database] [--copy] [--force]` | Restore a database from a backup file. |
| `backup schedule` | Show backup-related scheduled actions from ir.cron. |

### `kctl-odoo bank`

Bank reconciliation: statements, matching, import.

| Command | Description |
|---------|-------------|
| `bank import-guide` | Show instructions for importing bank statements. |
| `bank import-statement <file_path> [--journal] [--dry_run]` | Import bank statement lines from a CSV file. |
| `bank journals` | List bank and cash journals. |
| `bank status` | Bank reconciliation overview. |
| `bank suspense` | Show suspense account balance. |
| `bank unmatched [--journal] [--limit]` | List unreconciled bank statement lines. |

### `kctl-odoo bi`

Alias: bundles install <name>

### `kctl-odoo bl`

Alias: bundles list

### `kctl-odoo budget`

Budget planning and variance analysis.

| Command | Description |
|---------|-------------|
| `budget list [--state] [--limit]` | List budgets. |
| `budget summary [--period]` | Overall budget utilization summary. |
| `budget variance <budget_id>` | Show budget vs actual variance per budget line. |

### `kctl-odoo bundles`

Manage module bundles (YAML-based installation groups).

| Command | Description |
|---------|-------------|
| `bundles add-module <bundle> <module> [--group] [--dir_path]` | Add a module to a group in an existing bundle. |
| `bundles compare-profiles <profiles> [--dir_path] [--show_modules]` | Compare features between deployment profiles. |
| `bundles create <name> [--description] [--requires] [--dir_path]` | Create a new grouped-format bundle YAML file. |
| `bundles create-profile <name> [--description] [--bundles_list] [--extends] [--dir_path]` | Create a new deployment profile YAML file. |
| `bundles diff <bundle_a> <bundle_b> [--dir_path]` | Diff two bundles showing modules unique to each and shared. |
| `bundles find-module <module> [--dir_path]` | Find which bundle(s) and group(s) contain a specific module. |
| `bundles graph [--dir_path] [--fmt]` | Show bundle dependency graph derived from 'requires' chains. |
| `bundles groups <name> [--dir_path]` | List groups in a bundle with module counts. |
| `bundles install <name> [--groups] [--dir_path] [--dry_run]` | Install missing bundle modules on the remote Odoo instance. |
| `bundles list [--dir_path]` | List all available bundles. |
| `bundles list-profiles [--dir_path]` | List all deployment profiles with bundle and module counts. |
| `bundles modules <name> [--groups] [--dir_path]` | Resolve bundle to a comma-separated module list (CI/CD compatible). |
| `bundles profile-install <name> [--dir_path] [--dry_run]` | Install all missing profile modules on the remote Odoo instance. |
| `bundles profile-status <name> [--dir_path]` | Compare all profile modules against the remote Odoo instance. |
| `bundles profile-validate [--dir_path]` | Validate all profiles: check bundles exist, resolve correctly, extends references valid. |
| `bundles remove-module <bundle> <module> [--dir_path]` | Remove a module from a bundle (searches all groups). |
| `bundles show <name> [--dir_path]` | Show bundle details: groups, dependencies, and modules. |
| `bundles show-profile <name> [--dir_path]` | Show profile details: bundles, resolved modules, and foundation overlap. |
| `bundles status <name> [--groups] [--dir_path]` | Compare bundle modules against the remote Odoo instance. |
| `bundles validate [--dir_path]` | Validate ALL bundle YAMLs: circular deps, duplicate modules, resolution errors. |

### `kctl-odoo clean`

Stale data cleanup, transient purge, and auto-fix operations.

| Command | Description |
|---------|-------------|
| `clean auto-fix [--dry_run]` | Safe auto-fix for common maintenance issues. |
| `clean transients [--days]` | Delete old transient model records (wizards). |

### `kctl-odoo companies`

Manage Odoo companies.

| Command | Description |
|---------|-------------|
| `companies create <name> [--email] [--currency] [--parent]` | Create a new company. |
| `companies get <identifier>` | Get company details. |
| `companies list [--limit]` | List companies. |
| `companies switch <user_id> <company_id>` | Switch a user's current company. |
| `companies update <identifier> [--name] [--email] [--phone] [--website]` | Update a company. |
| `companies users <identifier> [--limit]` | List users belonging to a company. |

### `kctl-odoo compliance`

Regulatory compliance: licenses, certifications, vendor checks.

| Command | Description |
|---------|-------------|
| `compliance certifications [--product] [--limit]` | List product certifications. |
| `compliance expiring [--days]` | List all licenses and certifications expiring within N days. |
| `compliance licenses [--expiring_days] [--limit]` | List company licenses and their expiry status. |
| `compliance stats` | Compliance statistics: licenses and certifications by status. |
| `compliance vendor-check <partner> [--limit]` | List compliance checklists for a vendor/partner. |

### `kctl-odoo config`

Manage CLI configuration and profiles.

| Command | Description |
|---------|-------------|
| `config add <name> [--url] [--database] [--username] [--api_key] [--set_default]` | Add or update a profile's Odoo connection. |
| `config current` | Show the active profile and connection status. |
| `config doctor` | Diagnose all configured profiles. |
| `config init [--url] [--database] [--username] [--api_key] [--name]` | Initialize CLI configuration (interactive if no flags given). |
| `config list` | List all profiles with Odoo connection status. |
| `config migrate` | Migrate config from flat format to service-scoped format. |
| `config profiles` | Manage deployment profiles (bundle sets for different company types). |
| `config quick <name> <url> <database> <api_key> [--username] [--set_default]` | Create a profile in one line (no prompts). |
| `config remove <name> [--force] [--service_only]` | Remove a profile or just its Odoo config. |
| `config set <key> <value> [--profile_arg]` | Set a configuration value for the current service. |
| `config show` | Show full configuration (API keys masked). |
| `config test` | Test API connection with current configuration. |
| `config use <name>` | Switch the default profile. |

### `kctl-odoo crm`

CRM: leads, opportunities, pipeline management.

| Command | Description |
|---------|-------------|
| `crm activities [--user] [--overdue] [--limit]` | List CRM-related activities. |
| `crm convert <lead_id> [--force]` | Convert a lead to an opportunity. |
| `crm create-lead <name> [--partner] [--email] [--phone] [--user] [--team]` | Create a new CRM lead. |
| `crm get <lead_id>` | Show full lead or opportunity detail. |
| `crm leads [--stage] [--user] [--limit]` | List CRM leads. |
| `crm lost <lead_id> [--reason] [--force]` | Mark an opportunity as lost. |
| `crm opportunities [--stage] [--user] [--limit]` | List CRM opportunities. |
| `crm pipeline` | Show pipeline summary: opportunities by stage with counts and expected revenue. |
| `crm won <lead_id> [--force]` | Mark an opportunity as won. |

### `kctl-odoo cron`

Manage scheduled actions (ir.cron).

| Command | Description |
|---------|-------------|
| `cron create <name> [--model] [--code] [--interval] [--interval_type] [--active]` | Create a new scheduled action (ir.cron). |
| `cron diagnose` | Check for failed or stuck cron jobs with detailed analysis. |
| `cron disable <identifier>` | Disable a scheduled action. |
| `cron enable <identifier>` | Enable a scheduled action. |
| `cron history <identifier> [--limit]` | Show execution history (trigger records) for a scheduled action. |
| `cron list [--active_only] [--limit]` | List scheduled actions. |
| `cron run <identifier>` | Run a scheduled action immediately. |
| `cron status [--limit]` | Show active scheduled actions with overdue detection. |

### `kctl-odoo currency`

Currency management and exchange rate automation.

| Command | Description |
|---------|-------------|
| `currency add <code>` | Activate a currency by code. |
| `currency check-stale [--days]` | Flag currencies with outdated exchange rates. |
| `currency rates [--code] [--days] [--limit]` | List recent exchange rates. |
| `currency update [--force]` | Trigger currency rate update via Odoo cron. |

### `kctl-odoo dashboard`

Instance dashboard and overview.

| Command | Description |
|---------|-------------|
| `dashboard digest` | Morning coffee command — key business metrics at a glance. |
| `dashboard exec-summary` | Executive summary — all key metrics in one view. |
| `dashboard failed-emails [--limit]` | Emails that failed to send. |
| `dashboard gross-margin [--date_from] [--date_to] [--limit]` | Gross margin report — revenue vs COGS per product. |
| `dashboard info [--watch] [--interval]` | Show comprehensive Odoo instance overview. |
| `dashboard kpi` | Business KPI scorecard with pass/warn/fail thresholds. |
| `dashboard pending-approvals [--limit]` | Records awaiting approval across modules. |

### `kctl-odoo data-quality`

Data quality: duplicates, completeness, orphans.

| Command | Description |
|---------|-------------|
| `data-quality completeness <model> [--fields] [--limit]` | Check field completeness (fill rates) for a model. |
| `data-quality duplicates <model> [--field] [--limit]` | Find duplicate records grouped by a field. |
| `data-quality orphans [--model]` | Check for common orphan record patterns. |
| `data-quality report [--category]` | Combined data quality scorecard. |
| `data-quality validate <model> [--rules]` | Run basic data validation rules on a model. |

### `kctl-odoo databases`

Manage Odoo databases.

| Command | Description |
|---------|-------------|
| `databases create <name> [--lang]` | Create a new database. |
| `databases drop <name> [--force]` | Drop a database (irreversible). |
| `databases duplicate <source> <target>` | Duplicate a database. |
| `databases exists <name>` | Check if a database exists. |
| `databases languages` | List available languages for database creation. |
| `databases list` | List available databases. |
| `databases rename <old_name> <new_name>` | Rename a database. |

### `kctl-odoo dd`

Alias: dashboard digest

### `kctl-odoo delivery`

Delivery & logistics: tracking, performance, returns.

| Command | Description |
|---------|-------------|
| `delivery carriers` | List configured delivery carriers. |
| `delivery list [--state] [--carrier] [--date_from] [--limit]` | List outgoing deliveries. |
| `delivery pending [--days]` | List deliveries pending beyond threshold days. |
| `delivery performance [--days]` | On-time delivery performance report. |
| `delivery returns [--limit]` | List return pickings (origin contains 'Return'). |
| `delivery tracking <name>` | Show delivery tracking detail by reference. |

### `kctl-odoo deploy`

Deployment status and verification.

| Command | Description |
|---------|-------------|
| `deploy changelog [--days]` | Show recently installed or upgraded modules. |
| `deploy env [--redact]` | Show key system parameters (environment configuration). |
| `deploy status` | Show deployment status overview. |
| `deploy verify <profile_name> [--install_dir]` | Verify that a remote instance matches a deployment profile. |

### `kctl-odoo dev`

Development tools for Odoo.

| Command | Description |
|---------|-------------|
| `dev audit [--module] [--all_modules] [--min_score] [--output]` | Comprehensive module audit with scored report card. |
| `dev audit-api [--module]` | Audit FastAPI router code for common performance issues. |
| `dev audit-blocking [--module]` | Find blocking operations inside HTTP controllers. |
| `dev audit-compute [--module]` | Find computed fields without store=True. |
| `dev audit-fix <module> [--dry_run] [--categories]` | Auto-fix safe audit issues for a module. |
| `dev audit-logic [--module]` | Audit Odoo business logic for common errors. |
| `dev audit-ou [--module]` | Audit Operating Unit (multi-branch) isolation gaps. |
| `dev audit-prompt <module> [--output]` | Generate an AI agent prompt from audit results for human-in-loop fixes. |
| `dev audit-ui <module>` | Comprehensive Odoo UI / XML static audit. |
| `dev audit-views [--module]` | Audit XML views for performance — field count, deprecated patterns. |
| `dev check-conventions [--module]` | Check Kodemeio coding conventions across private modules. |
| `dev check-log-level` | Check if debug logging is enabled (production risk). |
| `dev check-translations <module> [--lang]` | Validate PO file placeholder consistency. |
| `dev clear-field-cache` | Clear cached model field definitions. |
| `dev cloc [--module]` | Show lines of code information for installed modules. |
| `dev coverage-report` | Show test coverage summary across all private modules. |
| `dev deps-reverse <module>` | Show what modules depend on this module (reverse dependencies). |
| `dev deps-tree <module>` | Show dependency tree for a module. |
| `dev export-translations <module> [--lang] [--fmt] [--output]` | Export translations for a module using the base.language.export wizard. |
| `dev find-overrides <model>` | List all modules that inherit/extend a model. |
| `dev generate-cmd <model> [--group_name] [--output]` | Auto-generate a CLI command file from live Odoo model introspection. |
| `dev import-translations <file> [--lang] [--overwrite]` | Import translations from a PO or CSV file. |
| `dev languages` | List installed and available languages. |
| `dev model-fields <model> [--stored_only] [--format_]` | Show model fields with types — useful for building CLI commands. |
| `dev model-info <model_name>` | Show detailed field information for an Odoo model. |
| `dev module-health <module>` | Comprehensive health check for a single private module. |
| `dev profile` | Show CPU and memory stats of the running Odoo process via JSON-RPC. |
| `dev regenerate-assets [--force]` | Regenerate web assets by clearing asset attachments. |
| `dev release-check <module>` | Pre-release validation for a module before version bump. |
| `dev routes` | List HTTP routes and JSON-RPC endpoints registered in Odoo. |
| `dev unused-xml-ids [--module] [--limit]` | Find XML IDs defined but potentially unreferenced. |
| `dev watch <module> [--service] [--interval]` | Watch Python/XML files and auto-upgrade module on change. |

### `kctl-odoo dev-mode`

Enable/disable dev mode for FastAPI apps.

| Command | Description |
|---------|-------------|
| `dev-mode disable <app_name>` | Disable dev mode for an app. |
| `dev-mode enable <app_name>` | Enable dev mode for an app. |
| `dev-mode status [--app_name]` | Show dev mode status for one or all apps. |

### `kctl-odoo di`

Alias: dashboard info

### `kctl-odoo diff`

Compare Odoo instances across profiles.

| Command | Description |
|---------|-------------|
| `diff config <profile_a> <profile_b> [--key]` | Compare ir.config_parameter values between two instances. |
| `diff modules <profile_a> <profile_b>` | Compare installed modules between two Odoo instances. |
| `diff users <profile_a> <profile_b>` | Compare user lists between two Odoo instances. |

### `kctl-odoo doctor`

Troubleshooting, diagnostics & health checks.

| Command | Description |
|---------|-------------|
| `doctor check [--watch] [--interval]` | Check Odoo instance health. |
| `doctor check-config` | Validate Odoo instance configuration against best practices. |
| `doctor check-xml-ids [--limit]` | Check for potentially broken XML IDs (ir.model.data with missing references). |
| `doctor fix-stuck <module> [--force]` | Reset a stuck module to installed/uninstalled state. |
| `doctor mail-diagnostics` | Check mail server configuration and queue status. |
| `doctor module-conflicts` | Find modules with overlapping model inheritance that may conflict. |
| `doctor recent-changes [--days] [--limit]` | Show recently changed modules. |
| `doctor report [--output] [--quick] [--section_filter]` | Instance diagnostics and health reporting. |
| `doctor stuck-modules` | Find modules stuck in transitional states. |
| `doctor unused-modules [--limit]` | Find installed modules with zero records in their custom models. |
| `doctor version-info` | Show Odoo version, database, CLI version, and module statistics. |

### `kctl-odoo dunning`

AR collection: dunning cases, follow-up, escalation.

| Command | Description |
|---------|-------------|
| `dunning cases [--level] [--limit]` | List dunning cases. |
| `dunning levels` | List dunning levels with delay days and actions. |
| `dunning run [--dry_run]` | Trigger dunning evaluation: create or escalate overdue cases. |
| `dunning stats` | Dunning statistics: cases by level and total overdue amount. |

### `kctl-odoo e2e`

E2E browser testing via Playwright.

| Command | Description |
|---------|-------------|
| `e2e discover [--dry_run]` | Discover Odoo menus and generate page test registry. |
| `e2e install` | Install Playwright browsers and dependencies. |
| `e2e list [--scenario]` | List all discovered E2E tests. |
| `e2e report` | Open Playwright HTML test report. |
| `e2e screenshots [--module] [--output]` | Capture screenshots of all accessible Odoo menu pages. |
| `e2e test [--scenario] [--headed] [--ui] [--debug] [--screenshots] [--video] [--mobile] [--smoke] [--module] [--grep]` | Run Playwright E2E tests against an Odoo instance. |

### `kctl-odoo events`

Events: event management and registrations.

| Command | Description |
|---------|-------------|
| `events cancel-registration <registration_id>` | Cancel an event registration. |
| `events confirm-registration <registration_id>` | Confirm an event registration. |
| `events get <event_id>` | Get event detail with registration count. |
| `events list [--upcoming] [--limit]` | List events. |
| `events registrations <event_id> [--state] [--limit]` | List registrations for an event. |
| `events stats <event_id>` | Registration statistics for an event: total, confirmed, draft, cancelled, revenue. |
| `events upcoming [--days]` | List events starting within N days. |

### `kctl-odoo export`

Export model data.

| Command | Description |
|---------|-------------|
| `export records <model> [--domain] [--fields] [--fmt] [--limit] [--output] [--with_id]` | Export records from a model. |

### `kctl-odoo fastapi`

Test FastAPI addon endpoints directly (not JSON-RPC).

| Command | Description |
|---------|-------------|
| `fastapi audit <app_name>` | Audit a FastAPI app's OpenAPI spec for quality and completeness. |
| `fastapi audit-live <app_name> [--quick]` | Live audit of a running FastAPI app — tests actual HTTP responses. |
| `fastapi audit-standards [--module] [--fix_hint]` | Cross-check FastAPI/PWA backends against standardized patterns. |
| `fastapi bench <app_name> <endpoint> [--count] [--token]` | Benchmark response time for a FastAPI endpoint. |
| `fastapi endpoints <app_name>` | List FastAPI endpoints from OpenAPI schema. |
| `fastapi health <app_name>` | Check if a FastAPI app router is responding. |
| `fastapi openapi <app_name> [--output]` | Extract OpenAPI spec from a FastAPI addon and save or display it. |
| `fastapi routes <app_name> [--tag]` | List all FastAPI routes for a module from its OpenAPI spec. |
| `fastapi test <app_name> <path> [--method] [--body] [--token]` | Call a FastAPI endpoint directly. |
| `fastapi validate <app_name>` | Validate OpenAPI spec completeness: schemas, operation IDs, response codes. |

### `kctl-odoo fleet`

Fleet management: vehicles, contracts, services.

| Command | Description |
|---------|-------------|
| `fleet contracts [--expiring_days] [--limit]` | List fleet contracts, optionally filtered by expiry window. |
| `fleet costs [--vehicle] [--period]` | Summarize fleet costs grouped by vehicle. |
| `fleet expiring [--days]` | Show contracts and insurances expiring within N days. |
| `fleet get-vehicle <vehicle_id>` | Get vehicle detail by ID. |
| `fleet log-odometer <vehicle> <value>` | Log an odometer reading for a vehicle. |
| `fleet services [--vehicle] [--limit]` | List fleet service logs. |
| `fleet summary` | Fleet dashboard: vehicle count, expiring contracts, services due. |
| `fleet vehicles [--state] [--driver] [--limit]` | List fleet vehicles. |

### `kctl-odoo forms`

Form requests: types, submissions, approval.

| Command | Description |
|---------|-------------|
| `forms approve <request_id> [--force]` | Approve a form request. |
| `forms get <request_id>` | Show form request detail with lines and attachments. |
| `forms pending [--form_type] [--limit]` | List pending/draft form requests awaiting action. |
| `forms reject <request_id> [--reason] [--force]` | Reject a form request. |
| `forms types` | List available form types. |

### `kctl-odoo hc`

Alias: troubleshoot check

### `kctl-odoo helpdesk`

Helpdesk: tickets, teams, SLA tracking.

| Command | Description |
|---------|-------------|
| `helpdesk assign <ticket_id> <user>` | Assign a helpdesk ticket to a user. |
| `helpdesk close <ticket_id> [--force]` | Close a helpdesk ticket (move to last stage). |
| `helpdesk create-ticket <subject> [--partner] [--team] [--priority]` | Create a new helpdesk ticket. |
| `helpdesk get-ticket <ticket_id>` | Get helpdesk ticket detail with messages. |
| `helpdesk sla-breaches [--limit]` | List tickets that have breached their SLA deadline. |
| `helpdesk summary` | Helpdesk dashboard: ticket counts by stage and SLA breaches. |
| `helpdesk team-load` | Show ticket count per helpdesk team. |
| `helpdesk tickets [--stage] [--team] [--assigned] [--limit]` | List helpdesk tickets. |

### `kctl-odoo history`

View local operation history (module ops, backups, health checks, deployments).

| Command | Description |
|---------|-------------|
| `history backups [--database] [--limit]` | Show backup operation history. |
| `history clear [--force]` | Clear all operation history. |
| `history deployments [--database] [--limit]` | Show deployment history. |
| `history health [--database] [--limit]` | Show health check history. |
| `history modules [--database] [--limit]` | Show module install/update operation history. |

### `kctl-odoo hr`

HR: employees, departments, attendance, leaves, payroll, expenses.

| Command | Description |
|---------|-------------|
| `hr approve-expense <sheet_id> [--force]` | Approve an expense sheet (hr.expense.sheet). |
| `hr approve-leave <leave_id> [--force]` | Approve a leave request by ID. |
| `hr attendance-report [--date_from] [--date_to] [--employee] [--limit]` | Attendance report for a date range. |
| `hr attendance-today [--limit]` | Who's checked in today (hr.attendance). |
| `hr birthdays [--days] [--limit]` | Upcoming employee birthdays. |
| `hr confirm-payslip [--month] [--ids] [--force]` | Confirm (set to done) draft/verify payslips. |
| `hr contracts [--state] [--limit]` | Contract status (hr.contract). |
| `hr create-expense <employee> <product> <amount> [--description] [--dry_run] [--force]` | Create an expense record (hr.expense). |
| `hr departments [--limit]` | Department list (hr.department). |
| `hr employees [--department] [--active] [--limit]` | Employee directory (hr.employee). |
| `hr expense-summary [--period]` | Expense dashboard — sheets by state, total amounts. |
| `hr expenses [--state] [--employee] [--limit]` | List expense sheets (hr.expense.sheet). |
| `hr generate-payslip <month> [--employee] [--force]` | Generate payslips for a period. |
| `hr get-employee <identifier>` | Get employee details by name or ID. |
| `hr get-payslip <payslip_id>` | Get payslip detail by ID. |
| `hr import-attendance <file> [--dry_run]` | Import attendance records from CSV. |
| `hr leave-balance [--employee] [--leave_type] [--limit]` | Leave balances (hr.leave.allocation). |
| `hr leave-summary [--department]` | Leave summary by department — approved leaves count and total days. |
| `hr leaves [--state] [--employee] [--limit]` | List leave requests (hr.leave). |
| `hr payslips [--state] [--employee] [--limit]` | List payslips (hr.payslip). |
| `hr refuse-leave <leave_id> [--force]` | Refuse a leave request by ID. |
| `hr reimburse-expense <sheet_id> [--journal] [--force]` | Register reimbursement for an approved expense sheet. |
| `hr request-leave <employee> <leave_type> <date_from> <date_to> [--reason] [--dry_run] [--force]` | Create a leave request (hr.leave). |
| `hr submit-expense <sheet_id> [--force]` | Submit an expense report for approval. |
| `hr summary` | HR dashboard — employees and leave requests. |

### `kctl-odoo import`

Import data into Odoo models.

| Command | Description |
|---------|-------------|
| `import guide` | Show the recommended data import order and CSV formats. |
| `import inventory <file> [--dry_run]` | Import inventory levels (stock quantities). |
| `import opening-balances <file> [--journal] [--date] [--ref] [--dry_run]` | Import opening balances as a journal entry. |
| `import records <model> <file> [--dry_run] [--batch_size]` | Import records into a model from CSV or JSON. |
| `import template <model> [--format] [--required_only] [--output]` | Generate an import template file for a model. |
| `import validate <model> <file>` | Validate an import file against a model without importing. |

### `kctl-odoo integration`

Integration & connectivity operations.

| Command | Description |
|---------|-------------|
| `integration oauth [--limit]` | List OAuth providers. |
| `integration send-bus <channel> <message>` | Send a message to the Odoo bus channel. |
| `integration test-smtp [--server_id]` | Test SMTP connection for outgoing mail servers. |
| `integration webhooks [--limit]` | List webhook-type automated actions. |

### `kctl-odoo inventory`

Inventory: stock levels, transfers, adjustments, lots, scrap.

| Command | Description |
|---------|-------------|
| `inventory adjust <product> <qty> [--location] [--force]` | Quick inventory adjustment for a single product. |
| `inventory adjustments <product_name> <location_name> <qty> [--reason] [--dry_run] [--force]` | Create an inventory adjustment (Odoo 18 stock.quant method). |
| `inventory close-period [--period_end]` | Period-end inventory validation. |
| `inventory create-transfer <from_wh> <to_wh> <product_name> <qty> [--dry_run] [--force]` | Create an internal stock transfer between warehouses. |
| `inventory locations [--warehouse] [--limit]` | List stock locations. |
| `inventory lots [--product] [--expired] [--limit]` | List stock lots / serial numbers. |
| `inventory low-stock [--threshold] [--limit]` | Products with stock below threshold. |
| `inventory manufacturing` | Manufacturing dashboard — production orders by state. |
| `inventory product-stock <product>` | Detailed stock for one product across all internal locations. |
| `inventory reorder-rules [--triggered] [--limit]` | List reorder rules (stock.warehouse.orderpoint). |
| `inventory scrap <product_name> <qty> [--reason] [--force]` | Create and validate a scrap order. |
| `inventory stock-levels [--warehouse] [--limit]` | Show stock levels per product (internal locations). |
| `inventory stock-moves [--product] [--date_from] [--limit]` | List stock moves (detailed movement history). |
| `inventory stuck [--days] [--limit]` | Transfers stuck in waiting/ready state beyond threshold. |
| `inventory summary [--warehouse]` | Inventory dashboard — stock levels, pending transfers. |
| `inventory transfers [--state] [--picking_type] [--date_from] [--partner] [--limit]` | List stock transfers (pickings). |
| `inventory turnover [--days] [--limit]` | Inventory turnover analysis — fast vs slow moving products. |
| `inventory validate-transfer <name> [--force]` | Validate (confirm) a stock transfer. |
| `inventory valuation [--limit]` | Show inventory valuation — stock value per product. |
| `inventory warehouses` | List warehouses. |

### `kctl-odoo jobs`

Manage OCA queue jobs (requires queue_job module).

| Command | Description |
|---------|-------------|
| `jobs cancel <ids>` | Cancel queue jobs by setting state to cancelled. |
| `jobs cleanup [--days] [--force]` | Delete old completed and cancelled queue jobs. |
| `jobs failed [--limit]` | Show failed queue jobs with error details. |
| `jobs list [--state] [--limit]` | List queue jobs. |
| `jobs retry <ids>` | Requeue failed jobs by setting state to pending. |
| `jobs retry-all [--force]` | Requeue all failed jobs. |
| `jobs stats [--watch] [--interval]` | Show queue job statistics by state. |

### `kctl-odoo kpi`

KPI reports via MIS Builder framework.

| Command | Description |
|---------|-------------|
| `kpi instances [--limit]` | List MIS report instances (configured reports with date ranges). |
| `kpi list` | List MIS report templates. |
| `kpi run <instance_id>` | Compute and display a MIS report instance result. |

### `kctl-odoo lint`

Lint and validate Odoo modules against best practices.

| Command | Description |
|---------|-------------|
| `lint all [--strict] [--summary_only]` | Lint ALL private modules and show a summary report. |
| `lint full [--strict]` | Run all linters: module checks, XML, manifests, security, N+1, ruff. |
| `lint manifests [--name] [--strict]` | Batch manifest linting using manifest_cmd conventions. |
| `lint module <name> [--strict]` | Lint a single private module against Odoo 18 best practices. |
| `lint ruff [--name] [--fix]` | Run ruff linter on private module Python code. |
| `lint security [--name]` | Check every model has a corresponding ir.model.access.csv row. |
| `lint summary` | Quick lint summary showing CLEAN/WARN/FAIL per module. |
| `lint xml [--name]` | XML-specific lint: deprecated attributes, encoding declarations, indentation. |

### `kctl-odoo local`

Local Docker Compose development environment.

| Command | Description |
|---------|-------------|
| `local aggregate` | Fetch OCA repositories via git-aggregator. |
| `local build [--no_cache]` | Build Docker image. |
| `local clear-assets [--database]` | Clear compiled asset bundles (CSS/JS cache). |
| `local db-create <name> [--modules]` | Create a new database via Docker. |
| `local db-drop <name> [--force]` | Drop a database via Docker (irreversible). |
| `local db-list` | List databases via Docker. |
| `local db-reset <database> [--with_demo] [--modules] [--force]` | Drop and recreate a database (irreversible). |
| `local down` | Stop all containers. |
| `local exec <command>` | Execute a command inside the Odoo container. |
| `local install [--modules] [--bundle] [--groups] [--database] [--no_demo]` | Install modules via Docker (no JSON-RPC timeout). |
| `local install-bundles [--database] [--tier] [--all_groups] [--single] [--dry_run]` | Install all bundles by tier (core -> oca -> private). |
| `local install-profiles [--profiles] [--dry_run] [--no_demo]` | Install deployment profiles (creates databases + installs bundles). |
| `local lint-js [--module] [--fix]` | Lint JavaScript files in private Odoo modules. |
| `local reload` | Restart Odoo and clear assets cache for development. |
| `local restart [--service]` | Restart container(s). |
| `local screenshots [--database] [--output] [--module] [--viewport]` | Capture screenshots of all Odoo menu pages via headless Chrome. |
| `local shell [--database] [--db]` | Open interactive Odoo shell. |
| `local status` | Show container status. |
| `local test <module> [--tags] [--database] [--clean]` | Run Odoo tests for a module. |
| `local up [--tunnel] [--debug] [--cron]` | Start the development environment (docker compose up). |
| `local update <modules> [--database] [--safe]` | Update modules via Docker. |

### `kctl-odoo logs`

Stream and analyze Odoo logs.

| Command | Description |
|---------|-------------|
| `logs errors [--days] [--limit]` | Show recent errors from ir.logging (works remotely via JSON-RPC). |
| `logs follow [--level] [--lines] [--service]` | Stream Docker container logs in real time. |
| `logs search <pattern> [--days] [--limit]` | Search ir.logging records matching a pattern. |

### `kctl-odoo mail`

Manage Odoo mail system.

| Command | Description |
|---------|-------------|
| `mail cancel <ids>` | Cancel emails by setting state to cancel. |
| `mail cleanup [--days] [--force]` | Delete old sent and cancelled emails. |
| `mail failed [--limit]` | Show failed emails with error details. |
| `mail queue [--watch] [--interval]` | Show mail queue summary by state. |
| `mail retry <ids>` | Retry failed emails by resetting state to outgoing. |
| `mail send <to> [--subject] [--body] [--dry_run]` | Send an email via Odoo mail.mail. |
| `mail status` | Comprehensive mail system health overview. |
| `mail templates [--limit]` | List email templates. |
| `mail test <server_id> [--to]` | Test SMTP server connection. |

### `kctl-odoo maintenance`

Database maintenance, health checks, and period-close validation.

| Command | Description |
|---------|-------------|
| `maintenance autovacuum` | Trigger Odoo's built-in autovacuum (ir.autovacuum). |
| `maintenance check-data [--category]` | Comprehensive data integrity checks across 7 categories. |
| `maintenance check-financial-statements [--date] [--period_start]` | Financial statement integrity checks for P&L, Balance Sheet, and Cash Flow. |
| `maintenance db-stats` | Show database size and growth indicators. |
| `maintenance health-report` | Generate a comprehensive daily health report. |
| `maintenance monthly-close [--period_end]` | Combined monthly close validation (accounting + inventory). |

### `kctl-odoo manifest`

Validate and analyze Odoo module manifests.

| Command | Description |
|---------|-------------|
| `manifest circular` | Detect circular dependencies across all private modules. |
| `manifest deps <module>` | Show dependency tree for a module (static, from __manifest__.py). |
| `manifest lint [--module]` | Kodemeio conventions: depends ordering, description present, author set. |
| `manifest report` | Full manifest health report across all private modules. |
| `manifest validate [--module]` | Check __manifest__.py: required keys, version format, installable=True. |
| `manifest versions` | Version consistency check across all private modules. |

### `kctl-odoo master-data`

Configure Odoo master data (taxes, accounts, journals, warehouses, etc.).

| Command | Description |
|---------|-------------|
| `master-data accounts [--account_type]` | List chart of accounts. |
| `master-data activate-currency <code>` | Activate a currency. |
| `master-data audit` | Audit configuration against best practices and score as percentage. |
| `master-data create-account <code> <name> [--account_type]` | Create an account in the chart of accounts. |
| `master-data create-fiscal-position <name> [--auto_apply]` | Create a fiscal position. |
| `master-data create-journal <name> <code> [--journal_type]` | Create an accounting journal. |
| `master-data create-operating-unit <name> <code>` | Create an operating unit. |
| `master-data create-payment-term <name>` | Create a payment term. |
| `master-data create-pricelist <name>` | Create a pricelist. |
| `master-data create-tax <name> <amount> [--use] [--amount_type]` | Create a tax. |
| `master-data create-warehouse <name> <code>` | Create a warehouse. |
| `master-data currencies [--all_currencies]` | List currencies. |
| `master-data fiscal-positions` | List fiscal positions. |
| `master-data journals` | List accounting journals. |
| `master-data operating-units` | List operating units. |
| `master-data payment-terms` | List payment terms. |
| `master-data pricelists` | List pricelists. |
| `master-data set-setting <key> <value>` | Set an Odoo configuration setting (ir.config_parameter). |
| `master-data settings` | Show key Odoo configuration settings. |
| `master-data taxes [--use]` | List taxes. |
| `master-data warehouses` | List warehouses. |

### `kctl-odoo mi`

Alias: modules install <names>

### `kctl-odoo migrate`

Database migration tools — audit source, validate target, compare.

| Command | Description |
|---------|-------------|
| `migrate audit-source [--source]` | Audit source data quality before migration. |
| `migrate column-diff <table> [--source] [--target]` | Compare column types for a model between source and target. |
| `migrate dry-run <model> [--source] [--target] [--limit]` | Simulate migration for a model — show type mismatches. |
| `migrate field-map <source> <target>` | Auto-detect field differences between two profiles. |
| `migrate status <source> <target>` | Show migration status: compare source and target profiles. |
| `migrate tables [--target] [--limit] [--min_records]` | Show table record counts on the target instance. |
| `migrate validate [--target]` | Post-migration validation checks on the target database. |

### `kctl-odoo ml`

Alias: modules list

### `kctl-odoo modules`

Manage Odoo modules.

| Command | Description |
|---------|-------------|
| `modules check <name>` | Check if a module is installed (exit 0 if yes, exit 1 if not). |
| `modules deps <name> [--depth]` | Show module install dependency tree. |
| `modules diff-live <profile_a> <profile_b>` | Compare installed modules between two kctl-odoo connection profiles. |
| `modules diff-snapshots <file_a> <file_b>` | Compare two snapshot JSON files. |
| `modules install <names>` | Install modules. |
| `modules list [--state] [--limit]` | List modules. |
| `modules rdeps <name> [--depth]` | Show reverse dependencies (modules that depend on this one). |
| `modules scan` | Scan for new or updated modules (update module list). |
| `modules search <query> [--limit]` | Search for modules by name or description. |
| `modules snapshot [--output] [--state]` | Export current module state to a JSON snapshot file. |
| `modules uninstall <names> [--force]` | Uninstall modules. |
| `modules upgrade <names>` | Upgrade modules. |

### `kctl-odoo monitor`

Health monitoring, alerting, and metrics export.

| Command | Description |
|---------|-------------|
| `monitor gatus-export` | Generate a Gatus endpoints YAML config for monitoring this instance. |
| `monitor glitchtip-export` | Show GlitchTip/Sentry DSN configuration for Odoo error tracking. |
| `monitor history [--days]` | Show health check history. |
| `monitor prometheus [--prefix]` | Export Prometheus-format metrics. |
| `monitor run [--strict]` | Run all health checks and report status. |
| `monitor thresholds [--set_value]` | Show or set alert thresholds. |

### `kctl-odoo mrp`

Manufacturing: production orders, BOMs, work centers.

| Command | Description |
|---------|-------------|
| `mrp bom-cost <bom_id>` | Calculate BOM cost from component standard prices. |
| `mrp bom-detail <bom_id>` | Show BOM detail with component lines. |
| `mrp boms [--product] [--limit]` | List bills of materials. |
| `mrp confirm <name> [--force]` | Confirm a draft manufacturing order. |
| `mrp costs <name>` | Show manufacturing order cost breakdown — planned vs actual. |
| `mrp create-order <product> [--qty] [--bom] [--dry_run]` | Create a manufacturing order. |
| `mrp done <name> [--force]` | Mark a manufacturing order as done. |
| `mrp finish-workorder <workorder_id> [--force]` | Finish a work order (mark as done). |
| `mrp get-order <name>` | Get manufacturing order detail by name or ID. |
| `mrp orders [--state] [--limit]` | List manufacturing orders with key fields. |
| `mrp planning [--days] [--limit]` | Upcoming manufacturing orders (confirmed or in progress) by scheduled date. |
| `mrp start-workorder <workorder_id> [--force]` | Start a work order (set to in progress). |
| `mrp stuck [--days] [--limit]` | Manufacturing orders stuck beyond threshold (confirmed/in progress, overdue). |
| `mrp summary` | Manufacturing dashboard — MOs by state count. |
| `mrp workcenters` | List work centers. |
| `mrp workorders [--state] [--workcenter] [--limit]` | List work orders. |

### `kctl-odoo ms`

Alias: modules scan

### `kctl-odoo mu`

Alias: modules upgrade <names>

### `kctl-odoo orm`

ORM profiling, N+1 detection, and query analysis.

| Command | Description |
|---------|-------------|
| `orm explain <model> <method> [--domain]` | Show timing and result info for an ORM operation on a model. |
| `orm fields-unused [--module]` | Fields declared in models but never referenced in Python code or XML views. |
| `orm fields-usage <model>` | Show which fields of a model are used in views and Python code. |
| `orm index-suggest <model>` | Suggest database indexes based on common search patterns. |
| `orm n-plus-one [--module]` | Static analysis: scan Python for N+1 ORM patterns inside for loops. |
| `orm profile [--duration]` | Capture SQL query stats for N seconds from pg_stat_statements via Odoo. |
| `orm query-log [--tail]` | Recent slow queries from pg_stat_statements (via docker compose exec). |

### `kctl-odoo partners`

Manage Odoo partners and contacts.

| Command | Description |
|---------|-------------|
| `partners create <name> [--email] [--phone] [--is_company] [--parent_id]` | Create a new partner/contact. |
| `partners delete <partner_id> [--force]` | Delete a partner/contact. |
| `partners duplicates [--limit]` | Find potential duplicate partners (same email). |
| `partners get <identifier>` | Get partner details. |
| `partners list [--company] [--person] [--customer] [--supplier] [--limit]` | List partners/contacts. |
| `partners search <query> [--limit]` | Search partners by name or email. |
| `partners stats` | Show partner statistics. |
| `partners update <identifier> [--name] [--email] [--phone] [--city]` | Update a partner/contact. |

### `kctl-odoo payment-gateways`

Payment gateways: iPaymu, Midtrans, Xendit status.

| Command | Description |
|---------|-------------|
| `payment-gateways history [--provider] [--days] [--limit]` | List recent payment transactions. |
| `payment-gateways pending [--provider] [--limit]` | List pending payment transactions. |
| `payment-gateways reconcile [--dry_run]` | Check for stale pending transactions (>24h) and suggest reconciliation. |
| `payment-gateways status` | Show all payment providers with state. |

### `kctl-odoo performance`

Performance diagnostics, profiling, and benchmarks.

| Command | Description |
|---------|-------------|
| `performance benchmark [--iterations]` | Benchmark ORM operations — measure RPC response times. |
| `performance cache` | Show cache-related system parameters. |
| `performance connections` | Show active database connection counts. |
| `performance cron-timing [--limit]` | Show cron execution timing — identify slow scheduled actions. |
| `performance indexes [--limit]` | List models and their indexed fields. |
| `performance memory` | Show Odoo server memory usage and configuration guidance. |
| `performance model-speed <model> [--limit]` | Profile a specific model — measure search, read, and count speeds. |
| `performance modules-count` | Count modules by state. |
| `performance pg` | Show how to use kctl-pg for database-level profiling. |
| `performance queue-throughput [--hours]` | Show queue job throughput — jobs processed per hour. |
| `performance stats [--watch] [--interval]` | Show database and system statistics overview. |
| `performance tables [--limit]` | Show record counts per model (largest tables first). |

### `kctl-odoo periods`

Fiscal periods and date range management.

| Command | Description |
|---------|-------------|
| `periods create-year <year> [--range_type]` | Create 12 monthly date ranges for a fiscal year. |
| `periods list [--range_type] [--limit]` | List date ranges (fiscal periods). |
| `periods types` | List date range types. |

### `kctl-odoo pi`

Alias: profiles install <name>

### `kctl-odoo pipeline`

CI/CD pipeline automation and observability.

| Command | Description |
|---------|-------------|
| `pipeline changelog <from_ref> [--to_ref] [--path_filter]` | Generate release notes from git commits and module changes. |
| `pipeline metrics [--prefix] [--warn]` | Export Prometheus-format metrics for Grafana dashboards. |
| `pipeline promote <source> <target> [--dry_run] [--sync_modules] [--sync_params] [--force]` | Compare and promote modules/config from source to target instance. |
| `pipeline rollback <profile> <backup_file> [--database] [--copy] [--skip_pre_backup] [--force]` | Restore from backup with pre/post verification. |
| `pipeline validate [--skip_lint] [--skip_test]` | Run lint + test + preflight + smoke-test as a single CI gate. |

### `kctl-odoo pl`

Alias: profiles list

### `kctl-odoo pos`

Point of Sale: sessions, orders, payments.

| Command | Description |
|---------|-------------|
| `pos cash-control <session_id>` | Show cash in/out details for a POS session. |
| `pos cashier-summary [--date_from] [--date_to]` | Revenue and order count per cashier. |
| `pos close-session <session_id> [--force]` | Close a POS session. |
| `pos config-detail <config_id>` | Show detailed POS configuration. |
| `pos configs` | List POS configurations. |
| `pos daily-report [--date]` | Daily sales summary grouped by POS configuration. |
| `pos debug-session <session_id>` | Comprehensive debug view of a POS session. |
| `pos get-order <ref>` | Get POS order detail by reference or name. |
| `pos hourly-sales [--date]` | Hourly sales breakdown for a given day. |
| `pos order-lines <order_ref>` | Show detailed order lines with products, qty, price, discount. |
| `pos orders [--session] [--date_from] [--limit]` | List POS orders. |
| `pos orphan-orders [--limit]` | Find POS orders with data integrity issues. |
| `pos payments [--date_from] [--limit]` | Payment summary grouped by payment method. |
| `pos period-report [--period]` | Sales comparison report: this period vs previous. |
| `pos reconcile <session_id>` | Verify session reconciliation — compare POS totals vs journal entries. |
| `pos refunds [--date_from] [--limit]` | List POS refund orders. |
| `pos sessions [--state] [--limit]` | List POS sessions. |
| `pos stuck-sessions [--hours]` | Find POS sessions that have been open beyond a threshold. |
| `pos summary` | Dashboard — active sessions count, today's orders count, today's revenue. |
| `pos tax-summary [--date_from] [--date_to]` | POS tax breakdown by tax rate for a period. |
| `pos top-products [--limit] [--date_from]` | Top-selling products from POS orders. |
| `pos trace-order <order_ref>` | Trace a POS order through the full accounting flow. |
| `pos validate-close <session_id>` | Pre-check if a session can be cleanly closed. |

### `kctl-odoo products`

Product management: catalog, pricing, categories.

| Command | Description |
|---------|-------------|
| `products barcode-lookup <barcode>` | Find product variant by exact barcode. |
| `products by-category [--limit]` | Count products per category. |
| `products categories [--limit]` | List product categories. |
| `products get <identifier>` | Show full product details by name or ID. |
| `products list [--category] [--product_type] [--limit]` | List product templates with key fields. |
| `products low-margin [--threshold] [--limit]` | Find products with low margin (below threshold %). |
| `products search <query> [--limit]` | Search products by name, internal code, or barcode. |
| `products update-price <identifier> [--sale_price] [--cost_price] [--force]` | Update sale price and/or cost price on a product. |

### `kctl-odoo project`

Project & task management.

| Command | Description |
|---------|-------------|
| `project list [--state] [--limit]` | List projects (project.project). |
| `project overdue [--days] [--limit]` | Tasks past their deadline. |
| `project tasks <project> [--stage] [--user] [--limit]` | List tasks for a project. |
| `project timesheets [--user] [--period] [--limit]` | Timesheet hours summary (account.analytic.line). |

### `kctl-odoo purchasing`

Purchase operations: orders, receipts, billing.

| Command | Description |
|---------|-------------|
| `purchasing approve [--ids] [--all_] [--force]` | Approve purchase orders awaiting approval. |
| `purchasing by-product [--limit] [--date_from]` | Purchase volume breakdown by product. |
| `purchasing by-vendor [--limit] [--date_from]` | Purchase volume breakdown by vendor. |
| `purchasing cancel-order <name> [--force]` | Cancel a purchase order. |
| `purchasing confirm-order <name> [--force]` | Confirm a draft purchase order. |
| `purchasing create-bill <po_name> [--force]` | Create a vendor bill from a confirmed purchase order. |
| `purchasing create-order <partner_name> <product_name> [--qty] [--price] [--dry_run] [--force]` | Create a purchase order with one line. |
| `purchasing get-order <name>` | Get purchase order detail by name or ID. |
| `purchasing orders [--state] [--partner] [--date_from] [--date_to] [--limit]` | List purchase orders with key fields. |
| `purchasing receipts [--state] [--limit]` | List incoming receipts (purchase-related stock pickings). |
| `purchasing summary [--period]` | Purchase dashboard — POs by state with totals. |
| `purchasing trend [--period]` | Purchase trend — compare this period vs previous. |
| `purchasing validate-receipt <name> [--force]` | Validate an incoming receipt picking. |

### `kctl-odoo quality`

Quality control: checks, inspections, alerts.

| Command | Description |
|---------|-------------|
| `quality alerts [--limit]` | List quality checks/inspections in failed state. |
| `quality checks [--state] [--limit]` | List quality checks or inspections. |
| `quality stats` | Quality statistics: count by state (pass/fail/pending). |

### `kctl-odoo record-rules`

Debug and audit Odoo record rules and access control.

| Command | Description |
|---------|-------------|
| `record-rules audit` | Audit: models without record rules, overly permissive rules. |
| `record-rules explain <model> <user_id>` | Show the full record rule chain for a model and user. |
| `record-rules simulate <model> <user_id> <record_id>` | Evaluate record rules for a given user and record combination. |
| `record-rules test <model> [--limit]` | Test record rules against sample data by checking which records are visible. |

### `kctl-odoo repl`

Interactive ORM exploration.

| Command | Description |
|---------|-------------|
| `repl repl [--load_models]` | Start an interactive ORM REPL session. |

### `kctl-odoo report`

Manage Odoo reports and generate diagnostic reports.

| Command | Description |
|---------|-------------|
| `report batch-download [--category] [--date_from] [--date_to] [--output_dir]` | Bulk export multiple reports to files. |
| `report catalog` | Show all report types with template count and status. |
| `report download <type_code> [--date_from] [--date_to] [--as_of_date] [--fmt] [--output] [--force]` | Generate a report and export it in one step. |
| `report export <instance_id> [--fmt] [--output]` | Export a report instance to XLSX or PDF file. |
| `report generate <report_type> [--output] [--quick]` | Generate a focused diagnostic report by domain. |
| `report instances [--type_code] [--limit]` | List generated report instances from report_management. |
| `report list [--model] [--limit]` | List available reports. |
| `report render <report_name> <record_ids> [--fmt] [--output]` | Render a report for given record IDs and save to file. |
| `report run <type_code> [--date_from] [--date_to] [--as_of_date] [--company] [--dry_run] [--force]` | Generate a report using the report_management framework. |
| `report schedule <type_code> [--cron] [--email_to]` | Schedule a report to run periodically. |
| `report templates [--model] [--limit]` | List QWeb report templates. |
| `report types [--category] [--limit]` | List report types from the report_management registry. |
| `report validate [--type_code] [--date_from] [--date_to]` | Validate report quality — check reports generate with data. |
| `report view <instance_id>` | View a report instance's metadata and data summary. |

### `kctl-odoo sales`

Sales operations: orders, deliveries, invoicing.

| Command | Description |
|---------|-------------|
| `sales by-customer [--limit] [--date_from] [--date_to]` | Sales revenue breakdown by customer. |
| `sales by-product [--limit] [--date_from] [--date_to]` | Sales revenue breakdown by product. |
| `sales by-salesperson [--date_from] [--date_to]` | Sales revenue breakdown by salesperson. |
| `sales cancel-order <name> [--force]` | Cancel a sale order (set to cancelled state). |
| `sales confirm-order <name> [--force]` | Confirm a draft sale order. |
| `sales create-order <partner_name> <product_name> [--qty] [--price] [--dry_run] [--force]` | Create a sale order with one line. |
| `sales crm-pipeline [--team]` | CRM pipeline — opportunities by stage with expected revenue. |
| `sales deliveries [--state] [--limit]` | List outgoing deliveries (sale-related stock pickings). |
| `sales get-order <name>` | Get sale order detail by name or ID. |
| `sales orders [--state] [--partner] [--date_from] [--date_to] [--limit]` | List sale orders with key fields. |
| `sales overdue [--order_type] [--days] [--limit]` | List overdue/expired quotations or purchase orders. |
| `sales summary [--period] [--team]` | Sales dashboard — orders by state with totals. |
| `sales trend [--period]` | Sales trend — compare this period vs previous. |
| `sales validate-delivery <name> [--force]` | Validate an outgoing delivery picking. |

### `kctl-odoo scaffold`

Generate Odoo module boilerplate (scaffold).

| Command | Description |
|---------|-------------|
| `scaffold bridge <module_a> <module_b> [--dest] [--overwrite]` | Generate a bridge module skeleton with auto_install=True. |
| `scaffold controller <module_dir> <name> [--overwrite]` | Generate an HTTP controller skeleton. |
| `scaffold crud-api <module> <model> [--dest] [--overwrite]` | Generate FastAPI CRUD router + Pydantic schema + test for a model. |
| `scaffold migration <module_dir> <version> [--stage] [--overwrite]` | Generate a pre/post migration script for a version upgrade. |
| `scaffold model <module_dir> <model_name> [--inherit] [--fields]` | Add a model to an existing module. |
| `scaffold module <name> [--dest] [--depends] [--author] [--category] [--fastapi] [--version]` | Create a new Odoo 18 module with standard directory structure. |
| `scaffold report <module_dir> <name> [--model] [--overwrite]` | Generate a QWeb report template with ir.actions.report record. |
| `scaffold router <module_dir> <name> [--crud]` | Add a FastAPI router to an existing module. |
| `scaffold schema <module_dir> <name>` | Add a Pydantic schema file to an existing module. |
| `scaffold security <module_dir> [--group] [--overwrite]` | Generate ir.model.access.csv rows for all models declared in the module. |
| `scaffold test <module_dir> <name> [--model] [--router]` | Add a test file to an existing module. |
| `scaffold view <module_dir> <model> [--view_type] [--overwrite]` | Generate an XML view file for a model. |
| `scaffold wizard <module_dir> <name> [--overwrite]` | Generate a transient model (wizard) with view and action. |

### `kctl-odoo security`

Security & audit operations.

| Command | Description |
|---------|-------------|
| `security access-rights [--model] [--limit]` | List access control rules (ir.model.access). |
| `security add-to-group <user_login> <group_ref>` | Add a user to a security group. |
| `security admins` | List users in the Administration / Settings group (base.group_system). |
| `security audit` | Comprehensive security audit across groups, ACLs, record rules, and users. |
| `security bulk-grant <group_ref> <users>` | Add multiple users to a security group. |
| `security bulk-revoke <group_ref> <users>` | Remove multiple users from a security group. |
| `security check-permissions <user>` | Show a user's groups and effective permissions. |
| `security compliance` | Security compliance scorecard (9-point check). |
| `security diff-users <user_a> <user_b>` | Compare permissions between two users. |
| `security group-users <group> [--limit]` | List all users in a specific security group. |
| `security groups [--limit]` | List security groups with user counts. |
| `security quick-audit [--days] [--limit]` | Show recent login activity from res.users.log. |
| `security record-rules [--model] [--limit]` | List record-level access rules (ir.rule). |
| `security remove-from-group <user_login> <group_ref> [--force]` | Remove a user from a security group. |
| `security sudo-audit [--module]` | Find sudo() calls in private module Python code. |
| `security superusers` | List internal (non-portal) active users with admin status. |

### `kctl-odoo self-test`

CLI self-test and smoke test.

### `kctl-odoo sequences`

Manage IR sequences (numbering).

| Command | Description |
|---------|-------------|
| `sequences get <code>` | Get detailed info for a sequence by code. |
| `sequences list [--model] [--limit]` | List IR sequences. |
| `sequences preview <code> [--count]` | Preview next N sequence numbers without consuming them. |
| `sequences reset <code> <number> [--force]` | Reset a sequence counter to a specific number. |

### `kctl-odoo server`

Manage Odoo server configuration (mail servers, defaults, system parameters).

| Command | Description |
|---------|-------------|
| `server add-mail-incoming <name> <host> <port> <server_type> [--user] [--password] [--ssl]` | Add a new incoming mail server (IMAP/POP3). |
| `server add-mail-outgoing <name> <host> <port> [--user] [--password] [--encryption]` | Add a new outgoing SMTP mail server. |
| `server defaults [--model]` | List default values configured in the system. |
| `server delete-default <default_id> [--force]` | Delete a default value record. |
| `server get-param <key>` | Get a system parameter value. |
| `server mail-incoming` | List incoming mail servers (IMAP/POP3). |
| `server mail-outgoing` | List outgoing SMTP mail servers. |
| `server params [--search] [--limit]` | List system parameters. |
| `server params-export [--output] [--search]` | Export system parameters to YAML or JSON file. |
| `server params-import <file_path> [--dry_run] [--force]` | Import system parameters from YAML or JSON file. |
| `server set-default <model> <field> <value> [--company_id]` | Set a default value for a model field. |
| `server set-param <key> <value>` | Set a system parameter value (creates if not exists). |
| `server sync-base-url [--all_dbs]` | Update web.base.url to match the CLI profile URL. |
| `server test-mail-outgoing <server_id>` | Test an outgoing SMTP server connection. |

### `kctl-odoo sessions`

Manage user sessions and login activity.

| Command | Description |
|---------|-------------|
| `sessions active [--hours] [--limit]` | Show recent login activity. |
| `sessions kick <login> [--force]` | Invalidate user sessions by forcing a password change token. |
| `sessions list [--days] [--limit]` | List user login sessions with activity summary. |
| `sessions stats` | Show session statistics. |

### `kctl-odoo setup`

Implementation setup wizard and go-live tools.

| Command | Description |
|---------|-------------|
| `setup audit` | Deep audit of master data, configuration, and business readiness. |
| `setup check-db` | Test PostgreSQL connectivity using configured .env values. |
| `setup checklist [--category]` | Run the implementation checklist against the Odoo instance. |
| `setup init` | Interactive setup wizard -- prompts for .env values and writes .env file. |
| `setup preflight [--profile] [--dir_path]` | Pre-flight check before go-live. |
| `setup quickstart` | Show the recommended setup steps for a new Odoo implementation. |
| `setup smoke-test` | Smoke-test key HTTP endpoints on the Odoo instance. |

### `kctl-odoo shell`

Execute ORM method calls.

| Command | Description |
|---------|-------------|
| `shell call <model> <method> [--args] [--kwargs]` | Execute an ORM method on a model. |

### `kctl-odoo skill`

Claude Code skill management.

| Command | Description |
|---------|-------------|
| `skill generate [--output] [--install] [--check]` | Auto-generate SKILL.md from CLI command registry. |

### `kctl-odoo statements`

Customer/vendor account statements.

| Command | Description |
|---------|-------------|
| `statements aging` | Show aged receivable summary by aging bucket. |
| `statements generate [--partner] [--stmt_type] [--stmt_date]` | Instructions for generating partner statements via Odoo wizard. |
| `statements overdue [--limit]` | List partners with overdue balances (unpaid past due date). |
| `statements partner <partner_name> [--date_from] [--output]` | Show account statement for a specific partner. |

### `kctl-odoo storage`

Storage monitoring & cleanup operations.

| Command | Description |
|---------|-------------|
| `storage attachments [--model] [--top]` | List attachments sorted by size (largest first). |
| `storage cleanup-attachments [--days] [--force]` | Remove orphan attachments older than N days. |
| `storage cleanup-logs [--days] [--force]` | Remove old ir.logging records older than N days. |
| `storage cleanup-mail [--days] [--force]` | Remove sent/cancelled mail.mail records older than N days. |
| `storage cleanup-sessions [--force]` | Purge expired sessions via ir.http (if available). |
| `storage download <attachment_id> [--output]` | Download an attachment by ID. |
| `storage filestore-stats` | Show attachment storage statistics. |
| `storage integrity-check` | Verify attachment references are valid. |
| `storage large-attachments [--min_size] [--limit]` | Find oversized attachments (default: > 1MB). |
| `storage migrate-to-db [--limit] [--dry_run]` | Migrate filestore attachments to database storage. |
| `storage migrate-to-fs [--limit] [--dry_run]` | Migrate database attachments to filestore storage. |
| `storage overview` | Comprehensive storage overview with cleanup recommendations. |

### `kctl-odoo support`

Internal support: tickets, SLA, knowledge base.

| Command | Description |
|---------|-------------|
| `support close <ticket_id> [--force]` | Close a support ticket (set status to resolved). |
| `support create <subject> [--category] [--priority]` | Create a new support ticket. |
| `support sla-status` | Count tickets by SLA compliance (within/breached). |
| `support tickets [--status] [--limit]` | List support tickets. |

### `kctl-odoo tax`

Tax reporting and compliance (Indonesian PPN/PPh).

| Command | Description |
|---------|-------------|
| `tax accounts` | List all tax-related GL accounts. |
| `tax coretax-status` | Check Coretax DJP integration status. |
| `tax faktur [--state] [--limit]` | List Faktur Pajak records (tax_management module). |
| `tax invoices [--invoice_type] [--limit]` | List posted invoices that have tax lines. |
| `tax pph-summary [--date_from] [--date_to]` | PPh withholding summary — grouped by PPh account. |
| `tax pph21-summary [--month]` | PPh 21 employee income tax summary. |
| `tax ppn-summary [--date_from] [--date_to]` | PPN (VAT) summary — output PPN, input PPN, and net amount. |
| `tax report [--period]` | Monthly tax summary combining PPN + PPh. |
| `tax tax-invoices-export [--invoice_type] [--date_from] [--date_to] [--output]` | Export tax invoices to CSV for Coretax/e-Faktur filing. |
| `tax withholdings [--pph_type] [--date_from] [--limit]` | List withholding tax entries from PPh accounts. |

### `kctl-odoo tenants`

SaaS tenant/multi-database operations.

| Command | Description |
|---------|-------------|
| `tenants backup <name> [--output] [--fmt]` | Backup a tenant database. |
| `tenants create <name> [--template] [--modules]` | Create a new tenant database. |
| `tenants delete <name> [--force]` | Delete a tenant database. |
| `tenants info <name>` | Show information about a tenant database. |
| `tenants list` | List all tenant databases. |
| `tenants reactivate <name>` | Reactivate a suspended tenant by re-enabling cron jobs. |
| `tenants suspend <name> [--force]` | Suspend a tenant by disabling all cron jobs. |

### `kctl-odoo test`

Run and manage Odoo tests.

| Command | Description |
|---------|-------------|
| `test coverage <module> [--database]` | Run tests with coverage measurement for a module. |
| `test list <module> [--directory]` | List test files and classes for a module. |
| `test profile <name> [--dir_path] [--stop_on_fail] [--tags] [--database]` | Run tests for all testable modules in a deployment profile. |
| `test run <module> [--tags] [--database] [--clean] [--summary]` | Run Odoo tests for a module. |

### `kctl-odoo tr`

Alias: test run <module>

### `kctl-odoo traceback`

Parse, analyze, and suggest fixes for Odoo tracebacks.

| Command | Description |
|---------|-------------|
| `traceback analyze <logfile>` | Pattern-match common errors in a log file and suggest fixes. |
| `traceback parse <logfile>` | Extract module, model, method, error type from Odoo tracebacks. |
| `traceback recent [--count] [--service]` | Show last N tracebacks from Docker logs. |
| `traceback suggest <error_text>` | Given an error message, suggest cause and fix. |

### `kctl-odoo translations`

Manage PO translation files for Odoo modules.

| Command | Description |
|---------|-------------|
| `translations coverage [--module]` | Show translation coverage per module per language. |
| `translations export-all [--lang] [--output_dir]` | Batch export PO files for all installed private modules via Odoo. |
| `translations import-all [--lang] [--overwrite]` | Batch import PO files for all private modules from i18n/ directories. |
| `translations missing [--module] [--lang]` | Show untranslated strings in PO files. |
| `translations validate [--module]` | Validate PO syntax and format string consistency. |

### `kctl-odoo users`

Manage Odoo users.

| Command | Description |
|---------|-------------|
| `users activate <identifier>` | Activate a user. |
| `users create <login> [--name] [--email] [--password]` | Create a new user. |
| `users create-apikey <login> [--name]` | Generate a new API key for a user. |
| `users deactivate <identifier>` | Deactivate a user. |
| `users get <identifier>` | Get user details. |
| `users groups <login>` | Show all groups assigned to a user. |
| `users list [--limit] [--active_only]` | List Odoo users. |
| `users list-apikeys <login>` | List API keys for a user. |
| `users reset-password <login>` | Send a password reset email to a user. |
| `users revoke-apikey <key_id> [--force]` | Revoke (delete) an API key by record ID. |
| `users set-password <login> <password> [--force]` | Set a user's password directly. |
| `users update <identifier> [--name] [--email] [--lang] [--tz]` | Update an existing user. |

### `kctl-odoo views`

XML view validation and xpath analysis.

| Command | Description |
|---------|-------------|
| `views duplicates` | Find duplicate view IDs (record id=) across all private modules. |
| `views inheritance <view_id>` | Show the inheritance chain for a view from ir.ui.view. |
| `views parse <file>` | Parse a single XML file and show the element tree structure. |
| `views render <template>` | Show QWeb template structure from running Odoo. |
| `views validate [--module]` | Parse all XML view files, check syntax, deprecated patterns (states=, tree vs list). |
| `views xpath-test <view_id> <xpath>` | Test an XPath expression against a view definition in running Odoo. |

### `kctl-odoo website`

Website & eCommerce: pages, products, publishing.

| Command | Description |
|---------|-------------|
| `website menus` | List website menu items in tree structure. |
| `website orders [--state] [--limit]` | List eCommerce orders (sale orders placed via website). |
| `website pages [--published] [--limit]` | List website pages. |
| `website products [--published] [--limit]` | List eCommerce products. |
| `website publish <model> <ids>` | Publish records by setting website_published=True. |
| `website redirects [--limit]` | List URL redirects configured on the website. |
| `website summary` | Dashboard — page count, published product count, eCommerce order count. |
| `website unpublish <model> <ids>` | Unpublish records by setting website_published=False. |
| `website visitors [--days]` | Visitor stats for the last N days. |

### `kctl-odoo workers`

Monitor Odoo worker and server status.

| Command | Description |
|---------|-------------|
| `workers info` | Show server configuration parameters (workers, limits, etc.). |
| `workers longpoll` | Check longpolling/websocket status via bus.bus model. |
| `workers status` | Check if Odoo is responding and show server version info. |
