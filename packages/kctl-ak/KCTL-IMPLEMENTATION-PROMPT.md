# kctl-* CLI Implementation Prompt

Copy ONE of the prompts below into a new Claude Code session in the target service repo.

---

## Odoo (kctl-odoo)

```
Build kctl-odoo CLI for managing Odoo 18 ERP. Follow the exact architecture of the reference
implementation at /home/tgunawan/project/00-new-projects/kodemeio-core/kodemeio-authentik/cli/

Read ALL files in that reference CLI first — especially core/config.py (SERVICE_KEY pattern,
service-scoped profiles in ~/.config/kodemeio/config.yaml), cli.py (Typer app structure),
core/client.py (httpx), core/output.py (Rich), commands/config_cmd.py (config add/use/remove/
migrate/profiles/current/test/show/set).

SERVICE_KEY = "odoo". Instances: erp.kodeme.io (kodemeio), multiple odoo-*.abcfood.app (abcfood).
API: Odoo JSON-RPC at /jsonrpc. Auth: API key via /web/session/authenticate.
ServiceConfig fields: url, api_key, database.

Commands needed:
- users list|get|create|update|activate|deactivate
- modules list|install|upgrade|uninstall|search
- databases list|backup|restore|duplicate
- config list|get|set (ir.config_parameter)
- cron list|enable|disable|run (ir.cron)
- health, dashboard
- shell <model> <method> [args] (execute ORM calls)
- export <model> [--domain FILTER] [--format csv|json]
- import <model> <file>
- maintenance update-list
- config init|add|use|remove|migrate|profiles|current|test|show|set

Place CLI at ./cli/ in the odoo repo. Install via uv tool install ./cli.
Create Claude skill at cli/skills/odoo-admin/SKILL.md.
Test against live instance, commit and push.
```

---

## Mailcow (kctl-mailcow)

```
Build kctl-mailcow CLI for managing Mailcow mail server. Follow the exact architecture of the
reference implementation at /home/tgunawan/project/00-new-projects/kodemeio-core/kodemeio-authentik/cli/

Read ALL files in that reference CLI first — especially core/config.py (SERVICE_KEY pattern,
service-scoped profiles in ~/.config/kodemeio/config.yaml), cli.py, core/client.py, core/output.py,
commands/config_cmd.py.

SERVICE_KEY = "mailcow". Instances: mail.kodeme.io (kodemeio), mail.abcfood.app (abcfood).
API: REST at /api/v1/. Auth: X-API-Key header.
ServiceConfig fields: url, api_key.

Commands needed:
- domains list|get|add|update|delete
- mailboxes list|get|add|update|delete [--domain DOMAIN]
- aliases list|get|add|update|delete
- dkim list|get|generate [--domain]
- queue list|flush|delete
- logs list [--type dovecot|postfix|sogo]
- ratelimits get|set
- quarantine list|release|delete
- status, health, dashboard
- sync-jobs list|add|delete
- fwdhost list|add|delete
- config init|add|use|remove|migrate|profiles|current|test|show|set

Place CLI at ./cli/ in the mailcow repo. Install via uv tool install ./cli.
Create Claude skill at cli/skills/mailcow-admin/SKILL.md.
Test against live instance, commit and push.
```

---

## Outline (kctl-outline)

```
Build kctl-outline CLI for managing Outline wiki. Follow the exact architecture of the reference
implementation at /home/tgunawan/project/00-new-projects/kodemeio-core/kodemeio-authentik/cli/

Read ALL files in that reference CLI first — especially core/config.py (SERVICE_KEY pattern,
service-scoped profiles in ~/.config/kodemeio/config.yaml), cli.py, core/client.py, core/output.py,
commands/config_cmd.py.

SERVICE_KEY = "outline". Instances: outline.kodeme.io (kodemeio).
API: REST at /api/ — all POST requests to /api/{resource}.{action}. Auth: Bearer token.
Pagination: offset+limit. Response: {"data":[...], "pagination":{"total":N}}.
ServiceConfig fields: url, token.

Commands needed:
- documents list|get|create|update|delete|search|export|move|archive
- collections list|get|create|update|delete|export
- users list|get|invite|update|activate|deactivate
- groups list|get|create|update|delete|add-user|remove-user
- shares list|create|revoke
- comments list|create|delete
- events list (activity feed)
- search <query> [--collection ID]
- health, dashboard
- config init|add|use|remove|migrate|profiles|current|test|show|set

Place CLI at ./cli/ in the outline repo. Install via uv tool install ./cli.
Create Claude skill at cli/skills/outline-admin/SKILL.md.
Test against live instance, commit and push.
```

---

## Plane (kctl-plane)

```
Build kctl-plane CLI for managing Plane project management. Follow the exact architecture of the
reference implementation at /home/tgunawan/project/00-new-projects/kodemeio-core/kodemeio-authentik/cli/

Read ALL files in that reference CLI first — especially core/config.py (SERVICE_KEY pattern,
service-scoped profiles in ~/.config/kodemeio/config.yaml), cli.py, core/client.py, core/output.py,
commands/config_cmd.py.

SERVICE_KEY = "plane". Instances: plane.kodeme.io (kodemeio), plane.abcfood.app (abcfood).
API: REST at /api/v1/. Auth: X-API-Key header. Nested: workspace > project > issue.
ServiceConfig fields: url, api_key, workspace.

Commands needed:
- workspaces list|get|create|update
- projects list|get|create|update|delete [--workspace SLUG]
- issues list|get|create|update|delete|assign|label|move [--project ID]
- cycles list|get|create|update|delete
- modules list|get|create|update|delete
- members list|add|remove [--project|--workspace]
- labels list|create|delete
- states list|create|update|delete
- health, dashboard
- export <project> [--format csv|json]
- config init|add|use|remove|migrate|profiles|current|test|show|set

Place CLI at ./cli/ in the plane repo. Install via uv tool install ./cli.
Create Claude skill at cli/skills/plane-admin/SKILL.md.
Test against live instance, commit and push.
```

---

## Zulip (kctl-zulip)

```
Build kctl-zulip CLI for managing Zulip chat. Follow the exact architecture of the reference
implementation at /home/tgunawan/project/00-new-projects/kodemeio-core/kodemeio-authentik/cli/

Read ALL files in that reference CLI first — especially core/config.py (SERVICE_KEY pattern,
service-scoped profiles in ~/.config/kodemeio/config.yaml), cli.py, core/client.py, core/output.py,
commands/config_cmd.py.

SERVICE_KEY = "zulip". Instances: zulip.kodeme.io (kodemeio).
API: REST at /api/v1/. Auth: HTTP Basic (email:api_key) or Bearer token.
ServiceConfig fields: url, email, api_key.

Commands needed:
- users list|get|create|update|deactivate|reactivate
- streams list|get|create|update|delete|subscribe|unsubscribe
- messages list|send|update|delete [--stream NAME] [--topic TOPIC]
- topics list [--stream NAME]
- groups list|get|create|update|delete|add-member|remove-member
- realm settings|get|update (server settings)
- invitations list|create|revoke
- emoji list|upload|delete
- health, dashboard
- announce <message> --stream <stream> --topic <topic>
- config init|add|use|remove|migrate|profiles|current|test|show|set

Place CLI at ./cli/ in the zulip repo. Install via uv tool install ./cli.
Create Claude skill at cli/skills/zulip-admin/SKILL.md.
Test against live instance, commit and push.
```

---

## PostgreSQL (kctl-pg)

```
Build kctl-pg CLI for managing PostgreSQL servers remotely over SSH tunnel.
This is DIFFERENT from other kctl-* CLIs — it does NOT use a REST API.
It connects to PostgreSQL via SSH tunnel + psycopg3 (SQL driver).

Follow the architecture of the reference implementation at:
/home/tgunawan/project/00-new-projects/kodemeio-core/kodemeio-authentik/cli/

Read ALL files in that reference CLI — especially core/config.py (SERVICE_KEY pattern,
service-scoped profiles in ~/.config/kodemeio/config.yaml), cli.py (Typer app),
core/output.py (Rich output), commands/config_cmd.py (config add/use/remove/profiles).

IMPORTANT DIFFERENCES from kctl-ak:
1. No httpx — use psycopg3 (psycopg[binary]>=3.2.0) for database connections
2. Add sshtunnel>=0.4.0 for SSH tunnel management
3. core/client.py should be a PostgresClient (not AuthentikClient) that:
   - Opens SSH tunnel via sshtunnel.SSHTunnelForwarder
   - Connects psycopg3 through the tunnel (localhost:local_bind_port)
   - Manages connection lifecycle (context manager)
   - Has methods: execute(sql, params), fetchall(sql, params), fetchone(sql, params)
4. Some commands (backup, restore, logs) run shell commands over SSH via paramiko or subprocess

SERVICE_KEY = "postgres".

Instances:
- kodemeio: PostgreSQL 16 at 10.0.0.3 (Hetzner private network)
  - SSH via 49.13.14.79 (public IP of PG server)
  - Databases: authentik, odoo, odoo_tpm, odoo_dms, and more
- abcfood: PostgreSQL at their server (separate SSH host)

ServiceConfig fields: host, port, user, password, ssh_host, ssh_port, ssh_user, ssh_key, databases (list).

Config section in ~/.config/kodemeio/config.yaml:
```yaml
profiles:
  kodemeio:
    postgres:
      host: 10.0.0.3
      port: 5432
      user: postgres
      password: ${PG_PASSWORD}
      ssh_host: 49.13.14.79
      ssh_port: 22
      ssh_user: root
      ssh_key: ~/.ssh/id_ed25519
      databases:
        - authentik
        - odoo
  abcfood:
    postgres:
      host: 10.0.0.3
      port: 5432
      user: postgres
      password: ${PG_PASSWORD_ABCFOOD}
      ssh_host: <abcfood-server-ip>
      ssh_port: 22
      ssh_user: root
      ssh_key: ~/.ssh/id_ed25519
```

PostgresClient pattern:
```python
from sshtunnel import SSHTunnelForwarder
import psycopg

class PostgresClient:
    def __init__(self, config: ServiceConfig):
        self._tunnel = SSHTunnelForwarder(
            (config.ssh_host, config.ssh_port),
            ssh_username=config.ssh_user,
            ssh_pkey=config.ssh_key,
            remote_bind_address=(config.host, config.port),
        )
        self._tunnel.start()
        self._conn = psycopg.connect(
            host="localhost",
            port=self._tunnel.local_bind_port,
            user=config.user,
            password=config.password,
            dbname="postgres",  # default, switch per command
        )

    def execute(self, sql, params=None): ...
    def fetchall(self, sql, params=None): ...
    def fetchone(self, sql, params=None): ...
    def close(self): self._conn.close(); self._tunnel.stop()
```

Commands needed:

Database operations:
- databases list                         # List all DBs with sizes (pg_database)
- databases create <name> [--owner USER] # CREATE DATABASE
- databases drop <name> [--force]        # DROP DATABASE (with confirmation)
- databases size                         # All database sizes sorted
- databases backup <name> [--output FILE] # pg_dump via SSH (subprocess over SSH)
- databases restore <name> <file>        # pg_restore via SSH
- databases duplicate <source> <target>  # CREATE DATABASE target TEMPLATE source

User/role management:
- users list                             # List roles (pg_roles)
- users create <name> [--password PASS] [--superuser] [--createdb]
- users drop <name> [--force]
- users grant <user> <database> [--privileges all|readonly|readwrite]
- users revoke <user> <database>
- users password <name> [password]       # ALTER ROLE SET PASSWORD

Monitoring:
- health                                 # Uptime, version, connections, replication, DB status
- dashboard                              # Full overview: DBs, sizes, connections, locks, replication
- queries active                         # pg_stat_activity (non-idle)
- queries slow [--min-ms 1000]           # Queries running longer than threshold
- queries kill <pid>                     # pg_terminate_backend(pid)
- locks                                  # pg_locks with blocker info
- connections                            # Connection count per database/user/state
- replication                            # pg_stat_replication (if replicas exist)

Table operations:
- tables list <db>                       # Tables with sizes, row estimates, last vacuum/analyze
- tables bloat <db>                      # Table and index bloat estimates
- tables stats <db> <table>              # Detailed pg_stat_user_tables for one table
- tables indexes <db> [table]            # Index usage stats (pg_stat_user_indexes)
- tables unused-indexes <db>             # Indexes with idx_scan = 0

Maintenance:
- vacuum <db> [table] [--full] [--analyze]  # VACUUM [FULL] [ANALYZE]
- reindex <db> [table]                      # REINDEX
- analyze <db> [table]                      # ANALYZE

Configuration:
- config show                            # Key PostgreSQL settings (shared_buffers, max_connections, etc.)
- config get <setting>                   # Single setting value
- config reload                          # SELECT pg_reload_conf()

Logs:
- logs [--lines N] [--follow]            # Tail PG logs via SSH (cat/tail on log file)

Extensions:
- extensions list <db>                   # List installed extensions
- extensions install <db> <ext>          # CREATE EXTENSION
- extensions drop <db> <ext>             # DROP EXTENSION

Config management (standard kctl pattern):
- config init|add|use|remove|migrate|profiles|current|test|show|set

Dependencies (pyproject.toml):
```toml
dependencies = [
    "typer>=0.15.0",
    "rich>=13.9.0",
    "pydantic>=2.10.0",
    "pyyaml>=6.0.2",
    "psycopg[binary]>=3.2.0",
    "sshtunnel>=0.4.0",
]
```

NOTE: Do NOT include httpx — this CLI uses SQL, not REST API.

Key SQL queries to use:
- Database list: SELECT datname, pg_database_size(datname), ... FROM pg_database WHERE datistemplate = false
- Active queries: SELECT pid, usename, datname, state, query, now()-query_start as duration FROM pg_stat_activity WHERE state != 'idle'
- Table sizes: SELECT schemaname, tablename, pg_total_relation_size(schemaname||'.'||tablename) FROM pg_stat_user_tables
- Connections: SELECT datname, usename, state, count(*) FROM pg_stat_activity GROUP BY 1,2,3
- Locks: SELECT ... FROM pg_locks JOIN pg_stat_activity ...
- Bloat: Use pgstattuple or estimate via dead_tuple_count from pg_stat_user_tables
- Config: SELECT name, setting, unit, context FROM pg_settings WHERE name IN (...)

For backup/restore, use subprocess to run commands over SSH:
  ssh root@<ssh_host> "pg_dump -Fc -h <host> -U <user> <dbname>" > backup.dump
  cat backup.dump | ssh root@<ssh_host> "pg_restore -h <host> -U <user> -d <dbname>"

Place CLI at ./cli/ in the kodemeio-postgres-16 repo. Install via uv tool install ./cli.
Create Claude skill at cli/skills/postgres-admin/SKILL.md.
Test against live instance (kodemeio profile), commit and push.
```

---

## Tactical RMM (kctl-rmm)

```
Build kctl-rmm CLI for managing Tactical RMM + MeshCentral remote monitoring platform.
Follow the exact architecture of the reference implementation at:
/home/tgunawan/project/00-new-projects/kodemeio-core/kodemeio-authentik/cli/

Read ALL files in that reference CLI first — especially core/config.py (SERVICE_KEY pattern,
service-scoped profiles in ~/.config/kodemeio/config.yaml), cli.py, core/client.py, core/output.py,
commands/config_cmd.py.

Also read the target project's CLAUDE.md for API details and architecture:
/home/tgunawan/project/00-new-projects/kodemeio-core/kodemeio-rmm/CLAUDE.md

SERVICE_KEY = "rmm". Instance: api-rmm.kodeme.io (kodemeio).
API: Tactical RMM REST API v3 at /api/v3/. Auth: X-API-KEY header.
Frontend: rmm.kodeme.io. MeshCentral: mesh.kodeme.io.
ServiceConfig fields: url, api_key, mesh_url.

Config section in ~/.config/kodemeio/config.yaml:
```yaml
profiles:
  kodemeio:
    rmm:
      url: https://api-rmm.kodeme.io
      api_key: <trmm-service-api-key>
      mesh_url: https://mesh.kodeme.io
```

IMPORTANT: The API uses X-API-KEY header (not Bearer token):
```python
self._client = httpx.Client(
    base_url=base_url,
    headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
)
```

Commands needed:

Agent management:
- agents list [--detail] [--client CLIENT] [--site SITE]  # List agents (detail=false for lightweight)
- agents get <agent-id>                                     # Agent details
- agents ping <agent-id>                                    # Check agent connectivity
- agents reboot <agent-id> [--force]                        # Reboot remote machine
- agents update <agent-id>                                  # Trigger agent update
- agents offline                                            # List agents that are offline/unreachable
- agents summary                                            # Count by client/site, online/offline

Script management:
- scripts list                                              # List all scripts
- scripts get <script-id>                                   # Script details
- scripts run <script-id> --agent <agent-id> [--timeout N]  # Run script on agent (output=forget)
- scripts run <script-id> --all [--client CLIENT]           # Run on all agents or by client
- scripts history [--agent <agent-id>]                      # Script execution history
- scripts create <name> --shell bash|powershell|python --file <path>  # Upload new script

Client/Site management:
- clients list                                              # List all clients
- clients get <client-id>                                   # Client details with sites
- sites list [--client CLIENT]                              # List sites

Software inventory:
- software list <agent-id>                                  # Installed software on agent
- software search <name> [--agent <agent-id>]               # Search across agents

Patches/Updates:
- patches list <agent-id>                                   # Pending patches
- patches scan <agent-id>                                   # Trigger patch scan
- patches install <agent-id> [--all|--kb KB_ID]             # Install patches

Monitoring:
- health                                                    # API health + service status
- dashboard                                                 # Agent count, online/offline, alerts, patches pending
- alerts list [--severity info|warning|error]               # Active alerts
- alerts dismiss <alert-id>                                 # Dismiss alert

Tasks:
- tasks list [--agent <agent-id>]                           # Automated tasks
- tasks run <task-id>                                       # Trigger task manually

Services (on remote agent):
- services list <agent-id>                                  # Windows services
- services start <agent-id> <service-name>                  # Start service
- services stop <agent-id> <service-name>                   # Stop service
- services restart <agent-id> <service-name>                # Restart service

Drivers (project-specific POS58):
- drivers install-pos58 <agent-id>                          # Run script 136 on agent
- drivers check-printer <agent-id>                          # Run script 135 on agent

Docker services (via docker compose on the RMM server):
- maintenance status                                        # Check all 11 container statuses
- maintenance restart <service>                             # Restart a service (e.g. tactical-celery)
- maintenance logs <service> [--lines N]                    # Tail service logs

Config management (standard kctl pattern):
- config init|add|use|remove|migrate|profiles|current|test|show|set

Key API endpoints:
- GET  /api/v3/agents/?detail=false           → agent list (lightweight)
- GET  /api/v3/agents/?detail=true            → agent list (full details)
- GET  /api/v3/agents/<id>/                   → single agent
- GET  /api/v3/agents/<id>/ping/              → ping agent
- POST /api/v3/agents/<id>/reboot/            → reboot
- GET  /api/v3/scripts/                       → list scripts
- POST /api/v3/agents/<id>/runscript/         → run script (body: {script: id, output: "forget", timeout: 120})
- GET  /api/v3/software/<id>/                 → installed software
- GET  /api/v3/clients/                       → list clients/sites
- GET  /api/v3/agents/history/                → script execution history
- GET  /health/                               → health check

IMPORTANT: For script execution, ALWAYS use output: "forget" (fire-and-forget).
The "wait" mode is unreliable and returns 500 errors. Script ID 135 = check printer,
Script ID 136 = install POS58 driver.

Place CLI at ./cli/ in the kodemeio-rmm repo. Install via uv tool install ./cli.
Create Claude skill at cli/skills/rmm-admin/SKILL.md.
Test against live instance, commit and push.
```

---

## 1Password Secrets Management (kctl-1password)

```
Build kctl-1password CLI for managing secrets across all Kodemeio projects via 1Password.
This is DIFFERENT from other kctl-* CLIs — it does NOT use a REST API or httpx.
It wraps the 1Password CLI (op) via subprocess to sync .env files to/from a 1Password vault.

Follow the architecture of the reference implementation at:
/home/tgunawan/project/00-new-projects/kodemeio-core/kodemeio-authentik/cli/

Read ALL files in that reference CLI — especially core/config.py (SERVICE_KEY pattern,
service-scoped profiles in ~/.config/kodemeio/config.yaml), cli.py (Typer app),
core/output.py (Rich output), commands/config_cmd.py.

ALSO read the existing project (it already has a Click CLI that you should migrate to Typer):
/home/tgunawan/project/00-new-projects/kodemeio-ext/kodemeio-1password/CLAUDE.md
/home/tgunawan/project/00-new-projects/kodemeio-ext/kodemeio-1password/src/kodemeio_1password/cli.py
/home/tgunawan/project/00-new-projects/kodemeio-ext/kodemeio-1password/src/kodemeio_1password/onepassword.py
/home/tgunawan/project/00-new-projects/kodemeio-ext/kodemeio-1password/src/kodemeio_1password/sync.py
/home/tgunawan/project/00-new-projects/kodemeio-ext/kodemeio-1password/src/kodemeio_1password/discovery.py
/home/tgunawan/project/00-new-projects/kodemeio-ext/kodemeio-1password/src/kodemeio_1password/diff.py
/home/tgunawan/project/00-new-projects/kodemeio-ext/kodemeio-1password/config/default.yaml

IMPORTANT: This project already has a working CLI using Click. You should either:
A. Migrate it to Typer + Rich (matching kctl-* patterns) and rename to kctl-1password, OR
B. Build kctl-1password as a new CLI in ./cli/ that reuses the existing core modules
   (onepassword.py, sync.py, discovery.py, diff.py, parser.py, config.py)

Choose option B (build in ./cli/ reusing existing modules) to avoid breaking the existing tool.

SERVICE_KEY = "onepassword".

Config section in ~/.config/kodemeio/config.yaml:
```yaml
profiles:
  kodemeio:
    onepassword:
      vault: Kodemeio
      service_account_token: ${OP_SERVICE_ACCOUNT_TOKEN}
      scan_roots:
        - /home/tgunawan/project/00-new-projects/kodemeio-app
        - /home/tgunawan/project/00-new-projects/kodemeio-core
        - /home/tgunawan/project/00-new-projects/kodemeio-ext
  abcfood:
    onepassword:
      vault: ABCFood
      service_account_token: ${OP_SERVICE_ACCOUNT_TOKEN_ABCFOOD}
      scan_roots:
        - /home/tgunawan/project/00-new-projects/abcfood
```

ServiceConfig fields: vault, service_account_token, scan_roots (list).

IMPORTANT DIFFERENCES from kctl-ak:
1. No httpx — uses subprocess to call `op` (1Password CLI binary)
2. Auth via OP_SERVICE_ACCOUNT_TOKEN env var (not Bearer token)
3. core/client.py should be a OnePasswordClient that wraps `op` CLI subprocess calls:
   - op vault get, op item list, op item get, op item create, op item delete, op whoami
4. Reuse existing modules from src/kodemeio_1password/ (discovery, parser, diff, sync)

Commands needed:

Discovery & Status:
- discover                                    # Find all .env files across scan_roots
- status                                      # Check 1Password connection, vault access, sync state
- list                                        # List all items in the vault

Sync Operations:
- push [--all] [-p PROJECT] [-e ENV] [--dry-run] [--force]    # Push .env to 1Password
- pull [--all] [-p PROJECT] [-e ENV] [--dry-run] [--force] [--no-backup]  # Pull from 1Password
- diff <project> <environment> [--show-values]                 # Show local vs remote differences
- diff --all                                                   # Show all diffs

Vault Management:
- vault info                                  # Show vault details
- vault create [name]                         # Create vault (setup)
- vault items                                 # List all items with metadata

Project Operations:
- projects list                               # List projects found across scan_roots
- projects status <project>                   # Sync status for all envs in a project
- projects envs <project>                     # List env files for a project

Backup:
- backup list [project]                       # List backups
- backup restore <project> <env> [timestamp]  # Restore from backup
- backup clean [--keep N]                     # Clean old backups

Health & Diagnostics:
- health                                      # Check: op CLI installed, authenticated, vault accessible
- dashboard                                   # Overview: projects, files, sync status, last sync times

Config management (standard kctl pattern):
- config init|add|use|remove|migrate|profiles|current|test|show|set

Dependencies (pyproject.toml):
```toml
dependencies = [
    "typer>=0.15.0",
    "rich>=13.9.0",
    "pydantic>=2.10.0",
    "pyyaml>=6.0.2",
    "python-dotenv>=1.0.0",
]
```

NOTE: Do NOT include httpx. This CLI uses subprocess to call `op` binary.
The `op` CLI must be installed separately (bin/install-op-cli).

Key implementation details:
- Each .env file becomes a Secure Note in 1Password
- Item title format: {project}/{environment} (e.g., kodemeio-authentik/production)
- Tags: project:{name}, env:{environment}
- Fields: each env var → password-type field in 1Password
- Metadata in notes: source path, sync time, SHA256 hash, field count
- Backups at: ~/.kodemeio-1password/backups/{project}/{env}/
- NEVER show secret values by default — require explicit --show-values flag

Place CLI at ./cli/ in the kodemeio-1password repo. Install via uv tool install ./cli.
Create Claude skill at cli/skills/1password-admin/SKILL.md.
Test with: kctl-1password health, kctl-1password discover, kctl-1password status.
Commit and push.
```

---

## Headwind MDM (kctl-mdm)

```
Build kctl-mdm CLI for managing Headwind MDM (Android device management).
Follow the exact architecture of the reference implementation at:
/home/tgunawan/project/00-new-projects/kodemeio-core/kodemeio-authentik/cli/

Read ALL files in that reference CLI first — especially core/config.py (SERVICE_KEY pattern,
service-scoped profiles in ~/.config/kodemeio/config.yaml), cli.py, core/client.py, core/output.py,
commands/config_cmd.py.

Also read the target project for context:
/home/tgunawan/project/00-new-projects/kodemeio-core/kodemeio-headwind/docker-compose.prod.yml
/home/tgunawan/project/00-new-projects/kodemeio-core/kodemeio-headwind/.env.example

SERVICE_KEY = "mdm". Instance: mdm.kodeme.io (kodemeio).
API: Headwind MDM REST API at /api/. Auth: admin login → session token.
MQTT push notifications on port 31000 (devices connect directly).
ServiceConfig fields: url, username, password.

IMPORTANT: Headwind MDM API auth works differently — you must first POST to /api/login
with username/password to get a session/token, then use that for subsequent requests.
The client.py should handle login + session management automatically.

Config section in ~/.config/kodemeio/config.yaml:
```yaml
profiles:
  kodemeio:
    mdm:
      url: https://mdm.kodeme.io
      username: admin
      password: ${HMDM_ADMIN_PASSWORD}
```

Client pattern for HMDM auth:
```python
class HmdmClient:
    def __init__(self, url, username, password):
        self._client = httpx.Client(base_url=url)
        # Login to get session
        resp = self._client.post("/api/login", json={
            "login": username, "password": password
        })
        token = resp.json().get("token", "")
        self._client.headers["Authorization"] = f"Bearer {token}"
```

Commands needed:

Device management:
- devices list [--status online|offline] [--group GROUP]  # List enrolled devices
- devices get <id>                                         # Device details (model, OS, last seen, apps)
- devices search <term>                                    # Search by name, number, IMEI
- devices remove <id> [--force]                            # Remove from management
- devices lock <id>                                        # Lock device screen
- devices unlock <id>                                      # Unlock device
- devices reboot <id>                                      # Reboot device
- devices wipe <id> [--force]                              # Factory reset (dangerous!)
- devices locate <id>                                      # Get GPS location
- devices command <id> <command>                           # Send custom command
- devices enroll                                           # Generate enrollment URL/QR code
- devices online                                           # List currently online devices
- devices offline                                          # List offline/unreachable devices

Application management:
- apps list                                                # List all applications
- apps get <id>                                            # App details (versions, assignments)
- apps upload <apk_file>                                   # Upload new APK
- apps assign <app-id> --to <group|device>                 # Assign app to group/device
- apps remove <id> [--force]                               # Remove application
- apps push-install <app-id> --to <device-id>              # Force install on device
- apps versions <app-id>                                   # List app versions

Configuration management:
- configs list                                             # List device configurations
- configs get <id>                                         # Configuration details
- configs create <name>                                    # Create new configuration
- configs assign <config-id> --to <group|device>           # Assign config
- configs clone <id> <new-name>                            # Duplicate configuration

Group management:
- groups list                                              # List device groups
- groups get <id>                                          # Group details with devices
- groups create <name>                                     # Create group
- groups delete <id> [--force]                             # Delete group
- groups add-device <group-id> <device-id>                 # Add device to group
- groups remove-device <group-id> <device-id>              # Remove device from group

Admin user management:
- users list                                               # List admin users
- users create <login> [--name NAME] [--password PASS]     # Create admin
- users delete <id> [--force]                              # Delete admin

Monitoring:
- health                                                   # API health + device stats
- dashboard                                                # Overview: devices, apps, groups, online/offline counts
- audit [--days N]                                         # Recent admin actions (if API supports)

RustDesk integration:
- rustdesk status                                          # RustDesk deployment status across devices
- rustdesk enroll <device-id>                              # Push RustDesk APK to device

Config management (standard kctl pattern):
- config init|add|use|remove|migrate|profiles|current|test|show|set

Key API endpoints (Headwind MDM 5.38.1):
- POST /api/login                      → authenticate, get token
- GET  /api/devices                    → list devices
- GET  /api/devices/{id}               → device details
- POST /api/devices/{id}/command       → send command to device
- GET  /api/applications               → list applications
- POST /api/applications               → create/upload application
- GET  /api/configurations             → list configurations
- POST /api/configurations             → create configuration
- GET  /api/groups                     → list device groups
- GET  /api/users                      → list admin users

IMPORTANT: Check the actual API documentation at https://h-mdm.com/docs/
for the correct endpoint paths — they may differ slightly per version.
Use context7 MCP to fetch latest Headwind MDM API docs if available.

Place CLI at ./cli/ in the kodemeio-headwind repo. Install via uv tool install ./cli.
Create Claude skill at cli/skills/mdm-admin/SKILL.md.
Test against live instance, commit and push.
```

---

## GlitchTip (kctl-glitchtip)

```
Build kctl-glitchtip CLI for managing GlitchTip error tracking platform.
Follow the exact architecture of the reference implementation at:
/home/tgunawan/project/00-new-projects/kodemeio-core/kodemeio-authentik/cli/

Read ALL files in that reference CLI first — especially core/config.py (SERVICE_KEY pattern,
service-scoped profiles in ~/.config/kodemeio/config.yaml), cli.py, core/client.py, core/output.py,
commands/config_cmd.py.

Also read the target project for context (it has existing shell scripts to reference):
/home/tgunawan/project/00-new-projects/kodemeio-core/kodemeio-glitchtip/Makefile
/home/tgunawan/project/00-new-projects/kodemeio-core/kodemeio-glitchtip/scripts/glitchtip-cli.sh
/home/tgunawan/project/00-new-projects/kodemeio-core/kodemeio-glitchtip/.env.example

SERVICE_KEY = "glitchtip". Instance: glitchtip.kodeme.io (kodemeio).
API: Sentry-compatible REST API at /api/0/. Auth: Bearer token (API token from GlitchTip UI).
ServiceConfig fields: url, token.

Config section in ~/.config/kodemeio/config.yaml:
```yaml
profiles:
  kodemeio:
    glitchtip:
      url: https://glitchtip.kodeme.io
      token: <glitchtip-api-token>
```

IMPORTANT: GlitchTip uses Sentry-compatible API. Auth header is:
```python
self._client = httpx.Client(
    base_url=base_url + "/api/0",
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
)
```

Commands needed:

Project management:
- projects list                                    # List all projects with DSNs
- projects get <org-slug> <project-slug>           # Project details
- projects create <name> --team <team-slug>        # Create project (returns DSN)
- projects delete <org-slug> <project-slug> [--force]
- projects dsn <org-slug> <project-slug>           # Show DSN keys for a project
- projects dsn-create <org-slug> <project-slug>    # Create new DSN key
- projects stats <org-slug> <project-slug>         # Event statistics

Issue/Error management:
- issues list [--project PROJECT] [--status unresolved|resolved|ignored]  # List issues
- issues get <issue-id>                            # Issue details with events
- issues resolve <issue-id>                        # Mark as resolved
- issues ignore <issue-id>                         # Mark as ignored
- issues delete <issue-id> [--force]               # Delete issue
- issues bulk-resolve --project <project>          # Resolve all issues in project

Team management:
- teams list                                       # List teams
- teams get <team-slug>                            # Team details with members
- teams create <name>                              # Create team
- teams delete <team-slug> [--force]
- teams add-member <team-slug> <email>             # Add member
- teams remove-member <team-slug> <email>

Organization:
- orgs list                                        # List organizations
- orgs get <org-slug>                              # Organization details

Event management:
- events list <org-slug> <project-slug> [--limit N]  # Recent events
- events cleanup [--days N]                          # Clean old events (default: 90 days)

Monitoring:
- health                                           # API health + container status
- dashboard                                        # Overview: projects, issues, events, teams
- celery-status                                    # Celery worker status
- redis-info                                       # Redis stats

User management:
- users list                                       # List users
- users create <email> [--superuser]               # Create user

Notifications:
- test-webhook <url>                               # Send test alert to webhook
- test-email [--to EMAIL]                          # Send test email

Config management (standard kctl pattern):
- config init|add|use|remove|migrate|profiles|current|test|show|set

Key API endpoints (Sentry-compatible at /api/0/):
- GET  /api/0/projects/                                    → list projects
- GET  /api/0/projects/{org}/{project}/                    → project details
- POST /api/0/teams/{org}/{team}/projects/                 → create project
- GET  /api/0/projects/{org}/{project}/keys/               → DSN keys
- GET  /api/0/projects/{org}/{project}/issues/             → list issues
- PUT  /api/0/projects/{org}/{project}/issues/             → bulk update issues
- GET  /api/0/issues/{id}/                                 → issue details
- PUT  /api/0/issues/{id}/                                 → update issue (resolve/ignore)
- GET  /api/0/projects/{org}/{project}/events/             → list events
- GET  /api/0/teams/                                       → list teams
- GET  /api/0/organizations/                               → list organizations
- GET  /api/0/organizations/{org}/members/                 → list members

Place CLI at ./cli/ in the kodemeio-glitchtip repo. Install via uv tool install ./cli.
Create Claude skill at cli/skills/glitchtip-admin/SKILL.md.
Test against live instance, commit and push.
```
