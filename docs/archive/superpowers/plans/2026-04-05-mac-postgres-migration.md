# MAC PostgreSQL Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy a dedicated PostgreSQL 16 instance on `mac-prod-01`, migrate `mac_odoo_dist` and `mac_odoo_hrms` databases from `kod-infra-postgres` (kod-prod-01, 49.13.116.191), and update MAC Odoo services to use the new local postgres.

**Architecture:** Same `kodemeio-postgres-16` compose (postgres + pgbouncer + init + exporter) deployed as `mac-infra-postgres` on `mac-prod-01`. Data migrated via `pg_dump | pg_restore` over SSH. MAC Odoo env vars updated to point to the new local postgres IP.

**Tech Stack:** PostgreSQL 16, Docker Compose, kctl-pg, kctl-dokploy

**Servers:**
- Source: `kod-prod-01` (49.13.116.191) — current postgres host
- Target: `mac-prod-01` (91.98.80.207) — new dedicated postgres

**Databases to migrate:**
- `mac_odoo_dist` (distribution — SFA, WMS, BIA)
- `mac_odoo_hrms` (HR — employees, attendance, payroll)

---

## Pre-Migration Checklist

Before starting, verify:
- [ ] `mac-prod-01` SSH access works: `ssh root@91.98.80.207`
- [ ] `kod-prod-01` SSH access works: `ssh root@49.13.116.191`
- [ ] Both servers have Docker running
- [ ] `mac-prod-01` has enough disk space for postgres data
- [ ] Current MAC Odoo services are stopped or in maintenance mode

---

### Task 1: Create mac-infra-postgres deploy manifest

**Files:**
- Create: `deploys/instances/production/mac-infra-postgres.yaml`
- Create: `deploys/env/production/.env.mac-infra-postgres`

- [ ] **Step 1: Create the instance manifest**

Create `deploys/instances/production/mac-infra-postgres.yaml`:

```yaml
kind: instance
extends: ../../bases/infra.yaml

instance:
  name: mac-infra-postgres
  description: "MAC dedicated PostgreSQL 16 database"

project: mac
environment: production
server: mac-prod-01

source_overrides:
  repo: kodemeio-postgres-16

env_file: ../../env/production/.env.mac-infra-postgres
```

- [ ] **Step 2: Create the env file**

Copy the structure from kod-infra-postgres but with MAC-specific values. Create `deploys/env/production/.env.mac-infra-postgres`:

```bash
# Pull current kod-postgres env as reference
kctl-dokploy compose env pull CiiIwoTTjXnwSRG5vGHCT /tmp/kod-postgres-env.txt

# Create mac-postgres env with new password
cat > deploys/env/production/.env.mac-infra-postgres << 'ENVEOF'
# =============================================================================
# MAC PostgreSQL 16 — Production (mac-prod-01)
# =============================================================================

# PostgreSQL
POSTGRES_PASSWORD=<GENERATE_NEW_SECURE_PASSWORD>
POSTGRES_USER=postgres
PGDATA=/var/lib/postgresql/data

# Init script creates the odoo role
ODOO_DB_PASSWORD=<GENERATE_NEW_SECURE_PASSWORD>

# PgBouncer
PGBOUNCER_AUTH_TYPE=scram-sha-256
PGBOUNCER_DEFAULT_POOL_SIZE=20
PGBOUNCER_MAX_CLIENT_CONN=200
PGBOUNCER_POOL_MODE=transaction

# Exporter
POSTGRES_EXPORTER_DATA_SOURCE_NAME=postgresql://postgres:${POSTGRES_PASSWORD}@postgres:5432/postgres?sslmode=disable

# Resources
TZ=Asia/Jakarta
ENVEOF
```

**IMPORTANT:** Generate new secure passwords — do NOT reuse kod-postgres passwords.

- [ ] **Step 3: Commit manifest**

```bash
git add deploys/instances/production/mac-infra-postgres.yaml
git commit -m "feat(deploys): add mac-infra-postgres manifest for dedicated MAC database"
```

---

### Task 2: Deploy mac-infra-postgres on mac-prod-01

- [ ] **Step 1: Deploy the postgres instance**

```bash
kctl-dokploy deploy apply -f deploys/instances/production/mac-infra-postgres.yaml
```

- [ ] **Step 2: Verify postgres is running**

```bash
# Check compose status
kctl-dokploy compose list | grep mac-infra-postgres

# Check containers are healthy
ssh root@91.98.80.207 "docker ps | grep postgres"
```

- [ ] **Step 3: Verify postgres is accessible**

```bash
# Test connection from mac-prod-01
ssh root@91.98.80.207 "docker exec -it \$(docker ps -q -f name=postgres-1) psql -U postgres -c 'SELECT version();'"
```

- [ ] **Step 4: Create the odoo role and databases**

```bash
# SSH into mac-prod-01, exec into postgres container
ssh root@91.98.80.207

# Find the postgres container
docker exec -it $(docker ps -q -f name=postgres-1 -f ancestor=postgres) bash

# Inside the container:
psql -U postgres <<SQL
-- Create odoo role (if init script didn't)
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'odoo') THEN
    CREATE ROLE odoo WITH LOGIN PASSWORD '<ODOO_DB_PASSWORD>';
  END IF;
END
\$\$;

-- Create databases
CREATE DATABASE mac_odoo_dist OWNER odoo;
CREATE DATABASE mac_odoo_hrms OWNER odoo;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE mac_odoo_dist TO odoo;
GRANT ALL PRIVILEGES ON DATABASE mac_odoo_hrms TO odoo;
SQL

exit  # exit container
exit  # exit SSH
```

---

### Task 3: Stop MAC Odoo services (maintenance window)

**This is the start of the maintenance window. MAC Odoo will be offline until Task 6.**

- [ ] **Step 1: Announce maintenance**

Notify users that MAC Odoo (mac-odoo-dist.mandiriagro.com, mac-odoo-hrms.mandiriagro.com) will be offline.

- [ ] **Step 2: Stop MAC Odoo compose services**

```bash
kctl-dokploy compose stop b253C2PRLLbwgC-3Zxb0q    # mac-odoo-dist
kctl-dokploy compose stop OEK_dJRQZZMo9HKbQrQ0z    # mac-odoo-hrms
```

- [ ] **Step 3: Verify services are stopped**

```bash
kctl-dokploy compose list | grep mac-odoo
```

Expected: Status shows `idle` for both.

---

### Task 4: Dump databases from kod-postgres

- [ ] **Step 1: Dump mac_odoo_dist**

```bash
# SSH into kod-prod-01 and dump
ssh root@49.13.116.191 "docker exec \$(docker ps -q -f name=postgres-1 -f ancestor=postgres) pg_dump -U postgres -Fc -Z3 mac_odoo_dist > /tmp/mac_odoo_dist.dump"

# Verify dump size
ssh root@49.13.116.191 "ls -lh /tmp/mac_odoo_dist.dump"
```

- [ ] **Step 2: Dump mac_odoo_hrms**

```bash
ssh root@49.13.116.191 "docker exec \$(docker ps -q -f name=postgres-1 -f ancestor=postgres) pg_dump -U postgres -Fc -Z3 mac_odoo_hrms > /tmp/mac_odoo_hrms.dump"

ssh root@49.13.116.191 "ls -lh /tmp/mac_odoo_hrms.dump"
```

- [ ] **Step 3: Transfer dumps to mac-prod-01**

```bash
# SCP from kod-prod-01 to mac-prod-01
ssh root@49.13.116.191 "scp /tmp/mac_odoo_dist.dump root@91.98.80.207:/tmp/"
ssh root@49.13.116.191 "scp /tmp/mac_odoo_hrms.dump root@91.98.80.207:/tmp/"

# Verify on mac-prod-01
ssh root@91.98.80.207 "ls -lh /tmp/mac_odoo_*.dump"
```

---

### Task 5: Restore databases on mac-postgres

- [ ] **Step 1: Copy dumps into postgres container**

```bash
ssh root@91.98.80.207 "docker cp /tmp/mac_odoo_dist.dump \$(docker ps -q -f name=postgres-1 -f ancestor=postgres):/tmp/"
ssh root@91.98.80.207 "docker cp /tmp/mac_odoo_hrms.dump \$(docker ps -q -f name=postgres-1 -f ancestor=postgres):/tmp/"
```

- [ ] **Step 2: Restore mac_odoo_dist**

```bash
ssh root@91.98.80.207 "docker exec \$(docker ps -q -f name=postgres-1 -f ancestor=postgres) pg_restore -U postgres -d mac_odoo_dist --no-owner --role=odoo /tmp/mac_odoo_dist.dump"
```

- [ ] **Step 3: Restore mac_odoo_hrms**

```bash
ssh root@91.98.80.207 "docker exec \$(docker ps -q -f name=postgres-1 -f ancestor=postgres) pg_restore -U postgres -d mac_odoo_hrms --no-owner --role=odoo /tmp/mac_odoo_hrms.dump"
```

- [ ] **Step 4: Verify data**

```bash
ssh root@91.98.80.207 "docker exec \$(docker ps -q -f name=postgres-1 -f ancestor=postgres) psql -U odoo -d mac_odoo_dist -c 'SELECT count(*) FROM res_partner;'"
ssh root@91.98.80.207 "docker exec \$(docker ps -q -f name=postgres-1 -f ancestor=postgres) psql -U odoo -d mac_odoo_hrms -c 'SELECT count(*) FROM hr_employee;'"
```

Expected: Row counts match the source databases.

- [ ] **Step 5: Clean up dumps**

```bash
ssh root@91.98.80.207 "rm /tmp/mac_odoo_*.dump"
ssh root@49.13.116.191 "rm /tmp/mac_odoo_*.dump"
```

---

### Task 6: Update MAC Odoo env vars and restart

- [ ] **Step 1: Find mac-postgres internal IP**

The postgres container on `mac-prod-01` is on `dokploy-network`. Find its IP:

```bash
ssh root@91.98.80.207 "docker inspect \$(docker ps -q -f name=postgres-1 -f ancestor=postgres) --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'"
```

Or use the Docker service name (preferred — resolves via Docker DNS):
The service name will be something like `mac-infra-postgres-postgres-1`. For stability, use the dokploy-network internal IP or the compose service name.

- [ ] **Step 2: Update mac-odoo-dist env**

Update `deploys/env/production/.env.mac-odoo-dist` — change PGHOST to the new postgres:

```bash
# Old value:
# PGHOST=10.0.0.3   (kod-postgres internal IP)

# New value — use mac-prod-01's postgres internal IP or Docker service name
sed -i 's/PGHOST=10.0.0.3/PGHOST=<MAC_POSTGRES_IP>/' deploys/env/production/.env.mac-odoo-dist
```

Also update `PGPASSWORD` to match the new mac-postgres odoo role password.

- [ ] **Step 3: Update mac-odoo-hrms env**

Same change for `deploys/env/production/.env.mac-odoo-hrms`:

```bash
sed -i 's/PGHOST=10.0.0.3/PGHOST=<MAC_POSTGRES_IP>/' deploys/env/production/.env.mac-odoo-hrms
```

Update `PGPASSWORD` too.

- [ ] **Step 4: Push updated env vars to Dokploy**

```bash
kctl-dokploy compose env push b253C2PRLLbwgC-3Zxb0q deploys/env/production/.env.mac-odoo-dist
kctl-dokploy compose env push OEK_dJRQZZMo9HKbQrQ0z deploys/env/production/.env.mac-odoo-hrms
```

- [ ] **Step 5: Restart MAC Odoo services**

```bash
kctl-dokploy compose start b253C2PRLLbwgC-3Zxb0q    # mac-odoo-dist
kctl-dokploy compose start OEK_dJRQZZMo9HKbQrQ0z    # mac-odoo-hrms
```

- [ ] **Step 6: Verify Odoo is working**

```bash
# Health check
curl -s -o /dev/null -w "%{http_code}" https://mac-odoo-dist.mandiriagro.com/web/login
curl -s -o /dev/null -w "%{http_code}" https://mac-odoo-hrms.mandiriagro.com/web/login
```

Expected: `200` for both.

**End of maintenance window.**

---

### Task 7: Verify and clean up

- [ ] **Step 1: Test MAC apps end-to-end**

Verify all MAC React PWA apps can still reach their Odoo backend:
- mac-sfa.mandiriagro.com
- mac-wms.mandiriagro.com
- mac-bia.mandiriagro.com
- mac-hrm.mandiriagro.com

- [ ] **Step 2: Drop old databases from kod-postgres (after 48h soak)**

After confirming everything works for 48 hours:

```bash
ssh root@49.13.116.191 "docker exec \$(docker ps -q -f name=postgres-1 -f ancestor=postgres) psql -U postgres -c 'DROP DATABASE mac_odoo_dist;'"
ssh root@49.13.116.191 "docker exec \$(docker ps -q -f name=postgres-1 -f ancestor=postgres) psql -U postgres -c 'DROP DATABASE mac_odoo_hrms;'"
```

- [ ] **Step 3: Update CLAUDE.md**

Add mac-infra-postgres to the server layout documentation.

---

## Rollback Plan

If anything goes wrong during migration:

1. **Odoo won't start on new postgres:** Revert PGHOST in env files back to `10.0.0.3`, push env, restart. MAC Odoo reconnects to kod-postgres with original data.

2. **Data corruption during restore:** Re-dump from kod-postgres (data is untouched there), re-restore.

3. **Network issues between services:** All MAC services run on `mac-prod-01` on `dokploy-network` — no cross-server networking needed.

## Timeline Estimate

| Phase | Duration |
|-------|----------|
| Task 1-2: Deploy postgres | ~15 min |
| Task 3: Stop Odoo | ~2 min |
| Task 4: Dump databases | ~5-30 min (depends on data size) |
| Task 5: Restore databases | ~5-30 min |
| Task 6: Update env + restart | ~5 min |
| Task 7: Verify | ~10 min |
| **Total maintenance window** | **Tasks 3-6: ~20-70 min** |
