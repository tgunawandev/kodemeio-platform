# PostgreSQL Recovery

> Last verified: 2026-04-03 | Owner: Platform team

PostgreSQL 16 is a Layer 0 dependency. When it goes down, **every Odoo instance, Authentik, GlitchTip, Grafana, and Mailcow** will fail simultaneously. Start here if you see a cascade of 500s across multiple services.

Host: `10.0.0.3` (private network) | Deploy manifest: `deploys/instances/kodeme.io-infra-postgres.yaml`

## Symptoms

- Multiple services returning 500 errors at the same time
- `FATAL: connection refused` or `could not connect to server` in app logs
- Odoo showing "Internal Server Error" on every page load
- Authentik login page failing to load
- GlitchTip/Grafana dashboards unreachable

## Diagnosis

```bash
# Step 1: Confirm PostgreSQL is the root cause
kctl-pg health

# Step 2: Check connection counts (saturation?)
kctl-pg stats connections

# Step 3: Check the container status on the host
# SSH to kodeme-service first if kctl-pg is unresponsive
kctl-dokploy services logs -s kodemeio-postgres --tail 100

# Step 4: Check Dokploy service status
kctl-dokploy services list --filter kodemeio-postgres

# Step 5: Check disk space (full disk kills Postgres immediately)
kctl-dokploy services exec -s kodemeio-postgres -- df -h /var/lib/postgresql/data
```

If `kctl-pg health` times out and logs show `No space left on device`, go to **Scenario C** (disk full) before anything else.

## Recovery Steps

### Scenario A: Container Crashed (most common)

Container stopped but data is intact.

```bash
# 1. Restart the container
kctl-dokploy services restart -s kodemeio-postgres

# 2. Wait for healthcheck to pass (up to 60s)
kctl-dokploy services status -s kodemeio-postgres --watch

# 3. Verify connectivity
kctl-pg health
kctl-pg stats connections
```

If restart loops or container exits immediately, check logs for `PANIC` — that indicates data corruption, go to Scenario B.

### Scenario B: Data Corruption / WAL Errors

Symptoms in logs: `PANIC`, `invalid page in block`, `could not read block`, `WAL file missing`.

```bash
# 1. Stop the service to prevent further writes
kctl-dokploy services stop -s kodemeio-postgres

# 2. Check available backups
kctl-pg backup list

# 3. Restore from latest backup
kctl-pg backup restore --from-latest

# 4. If you need a specific point-in-time restore
kctl-pg backup list --verbose
kctl-pg backup restore --backup-id <id>

# 5. Start Postgres after restore
kctl-dokploy services start -s kodemeio-postgres

# 6. Verify each database recovered
kctl-pg health
kctl-pg databases list
```

Data loss window equals time since last backup. Backups run on the schedule configured in the deploy manifest — check `deploys/instances/kodeme.io-infra-postgres.yaml` for the cron.

### Scenario C: Disk Full

```bash
# 1. Check disk usage breakdown
kctl-dokploy services exec -s kodemeio-postgres -- du -sh /var/lib/postgresql/data/*

# 2. Check for bloated WAL files
kctl-dokploy services exec -s kodemeio-postgres -- ls -lh /var/lib/postgresql/data/pg_wal/

# 3. On the host: check overall disk
# SSH to kodeme-service
df -h /
du -sh /var/lib/docker/volumes/* | sort -rh | head -10

# 4. Extend Hetzner volume if needed
kctl-hz volumes resize --name postgres-data --size <new-gb>

# 5. Once space is available, restart Postgres
kctl-dokploy services restart -s kodemeio-postgres
```

### Scenario D: Full Rebuild from Scratch

Use only if data is unrecoverable and you have a backup to restore from.

```bash
# 1. Stop all dependent services first to prevent split-brain
kctl-dokploy services stop -s kodemeio-authentik
kctl-dokploy services stop -s kodemeio-odoo-full
# ... stop other Odoo instances as needed

# 2. Remove and rebuild Postgres
kctl-dokploy deploy apply -f deploys/instances/kodeme.io-infra-postgres.yaml

# 3. Wait for Postgres to be healthy
kctl-pg health

# 4. Restore databases
kctl-pg backup restore --from-latest

# 5. Restart dependent services in dependency order
kctl-dokploy services start -s kodemeio-authentik
# Wait for Authentik to be healthy before starting Odoo
kctl-ak health
kctl-dokploy services start -s kodemeio-odoo-full
```

## Verification

```bash
# 1. Postgres itself is healthy
kctl-pg health

# 2. Connection counts are normal (should be well under max_connections)
kctl-pg stats connections

# 3. All databases present
kctl-pg databases list

# 4. Odoo instances can authenticate users
# Open odoo.kodeme.io and attempt login

# 5. Authentik login works
# Open auth.kodeme.io — login page should load

# 6. Grafana shows green for all services
kctl-grafana dashboard list
```

## Post-Recovery

```bash
# Check for any Odoo instances that need a restart after DB recovery
kctl-dokploy services list --filter odoo
kctl-dokploy services restart -s kodemeio-odoo-full   # if still in error state

# Check replication lag if using streaming replication
kctl-pg stats replication

# Notify team that recovery is complete
kctl-telegram send --chat ops "DB recovery complete. All services verified healthy."
```

## Escalation

- If WAL corruption is widespread and backup restore fails: engage Hetzner support for volume snapshot restore
- If backup is older than acceptable RPO: notify stakeholders before proceeding
- Max acceptable downtime before customer communication: **30 minutes** for Odoo production
