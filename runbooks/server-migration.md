# Hetzner Server Migration

> Last verified: 2026-04-03 | Owner: Platform team

Procedure for migrating the Kodemeio platform to a new Hetzner server. This is needed for hardware replacement, region migration, or scaling up. Plan for 2-4 hours of maintenance window.

Current server: **kodeme-service** (49.13.14.79, CX31, 16GB RAM, Nuremberg)
Private network: **10.0.0.0/16** (PostgreSQL at 10.0.0.3)

## Planning Checklist

Before starting:

- [ ] New server provisioned and accessible
- [ ] Maintenance window scheduled and communicated to customers
- [ ] All databases backed up within last hour
- [ ] DNS TTLs reduced to 60s at least 24 hours before migration (for fast cutover)
- [ ] New server specs confirmed to meet requirements (minimum 16GB RAM for full stack)
- [ ] S3 backup credentials available for restore

## Phase 1: Provision New Server

```bash
# 1. Create the new server on Hetzner
kctl-hz servers create \
  --name kodeme-service-new \
  --type cx31 \
  --image ubuntu-24.04 \
  --location nbg1 \
  --ssh-key <your-key-name>

# 2. Wait for server to be running
kctl-hz servers status --name kodeme-service-new

# 3. Note the new server's public IP
kctl-hz servers show --name kodeme-service-new | grep -i ip

# 4. Attach to the same private network (required for PostgreSQL private IP routing)
kctl-hz networks attach --network kodeme-private --server kodeme-service-new

# 5. Assign a static private IP (must be different from 10.0.0.3)
# Configure in Hetzner console or via kctl-hz if supported

# 6. Add firewall rules
kctl-hz firewalls apply --name kodeme-firewall --server kodeme-service-new
```

## Phase 2: Install Base Stack

SSH to the new server for the initial setup:

```bash
# On new server: install Docker
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker

# Install Dokploy
curl -sSL https://dokploy.com/install.sh | sh
# Follow prompts — configure same admin credentials

# Wait for Dokploy to start
sleep 30
curl -sf http://localhost:3000/health
```

Back on your workstation, configure kctl-dokploy to target the new server:

```bash
# Add new server as a kctl-dokploy profile
kctl-dokploy config add \
  --profile new-server \
  --url https://dokploy-new.kodeme.io \
  --token <api-token>

# Verify connection
kctl-dokploy health --profile new-server
```

## Phase 3: Data Sync

```bash
# 1. Final database backup on old server (do this just before cutover)
kctl-pg backup create --all-databases
kctl-pg backup list  # confirm all databases backed up

# 2. Sync Docker volumes to new server
# SSH to old server, then rsync volumes to new server
# Volumes are typically at /var/lib/docker/volumes/
rsync -avz --progress \
  /var/lib/docker/volumes/ \
  root@<new-server-ip>:/var/lib/docker/volumes/

# 3. Sync Dokploy configuration
rsync -avz --progress \
  /var/lib/dokploy/ \
  root@<new-server-ip>:/var/lib/dokploy/

# 4. Sync any persistent data directories
rsync -avz --progress \
  /opt/kodemeio/ \
  root@<new-server-ip>:/opt/kodemeio/
```

## Phase 4: Deploy Services on New Server

```bash
# Deploy the infra foundation layer first, in dependency order

# 1. PostgreSQL
kctl-dokploy deploy apply \
  -f deploys/instances/kodeme.io-infra-postgres.yaml \
  --profile new-server

kctl-pg health --profile new-server

# 2. Authentik (depends on PostgreSQL)
kctl-dokploy deploy apply \
  -f deploys/instances/kodeme.io-infra-authentik.yaml \
  --profile new-server

kctl-ak health --profile new-server

# 3. Core monitoring services
kctl-dokploy deploy apply -f deploys/instances/kodeme.io-infra-glitchtip.yaml --profile new-server

# 4. Remaining infrastructure
kctl-dokploy deploy apply -f deploys/instances/kodeme.io-infra-mailcow.yaml --profile new-server
kctl-dokploy deploy apply -f deploys/instances/kodeme.io-infra-waha.yaml --profile new-server
kctl-dokploy deploy apply -f deploys/instances/kodeme.io-infra-rustdesk.yaml --profile new-server
kctl-dokploy deploy apply -f deploys/instances/kodeme.io-infra-rmm.yaml --profile new-server

# 5. Business applications
kctl-dokploy deploy apply -f deploys/instances/kodeme.io-odoo-full.yaml --profile new-server
kctl-dokploy deploy apply -f deploys/instances/kodeme.io-odoo-hrms.yaml --profile new-server
kctl-dokploy deploy apply -f deploys/instances/mandiriagro.com-odoo-hrms.yaml --profile new-server
kctl-dokploy deploy apply -f deploys/instances/mandiriagro.com-odoo-trading.yaml --profile new-server
kctl-dokploy deploy apply -f deploys/instances/pakerti.com-odoo-hrms.yaml --profile new-server
kctl-dokploy deploy apply -f deploys/instances/pakerti.com-odoo-trading.yaml --profile new-server

# 6. Batch deploy remaining instances
kctl-dokploy deploy apply-all -d deploys/instances/ --profile new-server
```

## Phase 5: Verification on New Server (Pre-Cutover)

Before touching DNS, confirm the new server is fully functional using direct IP access or a test domain.

```bash
# Health check all services on new server
kctl-dokploy services list --profile new-server
kctl-pg health --profile new-server
kctl-ak health --profile new-server
kctl-odoo health --profile new-server

# Test Odoo login
kctl-odoo e2e test login --profile new-server

# Check all healthchecks pass
kctl-grafana dashboard list --profile new-server
```

## Phase 6: DNS Cutover

This is the point of no return for downtime. Do this when all services on the new server are verified.

```bash
# 1. Update all A records to new server IP
NEW_IP=<new-server-ip>

kctl-cf dns update --domain kodeme.io --name @ --value $NEW_IP
kctl-cf dns update --domain kodeme.io --name "*" --value $NEW_IP
kctl-cf dns update --domain mandiriagro.com --name @ --value $NEW_IP
kctl-cf dns update --domain mandiriagro.com --name "*" --value $NEW_IP
kctl-cf dns update --domain pakerti.com --name @ --value $NEW_IP
kctl-cf dns update --domain pakerti.com --name "*" --value $NEW_IP
kctl-cf dns update --domain terakidz.com --name @ --value $NEW_IP
kctl-cf dns update --domain terakidz.com --name "*" --value $NEW_IP
kctl-cf dns update --domain trigunawan.com --name @ --value $NEW_IP
kctl-cf dns update --domain trigunawan.com --name "*" --value $NEW_IP
kctl-cf dns update --domain kidneuro.io --name @ --value $NEW_IP
kctl-cf dns update --domain kidneuro.io --name "*" --value $NEW_IP

# 2. Verify DNS is resolving to new IP
kctl-cf dns list --domain kodeme.io

# 3. Update kctl-dokploy default profile to point to new server
kctl-dokploy config use new-server
```

## Phase 7: Post-Cutover Verification

```bash
# 1. Wait for DNS TTL to propagate (60s if TTL was reduced beforehand)
sleep 60

# 2. Verify all public URLs resolve correctly
kctl-cf ssl check --domain kodeme.io
kctl-cf ssl check --domain auth.kodeme.io
kctl-cf ssl check --domain odoo.kodeme.io

# 3. Check all services via Grafana
kctl-grafana dashboard list

# 4. Confirm no errors in app logs
kctl-dokploy services logs -s kodemeio-odoo-full --tail 50
```

## Phase 8: Decommission Old Server

Only do this after 24 hours of stable operation on the new server.

```bash
# 1. Stop all services on old server (optional — they'll stop receiving traffic)
# SSH to old server if needed

# 2. Delete old server
kctl-hz servers delete --name kodeme-service

# 3. Release old floating IP if applicable
kctl-hz floating-ips delete --ip 49.13.14.79

# 4. Update any hardcoded IP references in documentation
```

## Rollback

If the new server has critical issues after DNS cutover, revert DNS to the old server IP:

```bash
# Revert all DNS records to old server IP
OLD_IP=49.13.14.79

kctl-cf dns update --domain kodeme.io --name @ --value $OLD_IP
# ... repeat for all domains

# Switch kctl-dokploy profile back
kctl-dokploy config use default
```

## Escalation

- Hetzner server provisioning issues: Hetzner Cloud console at console.hetzner.cloud
- Private network routing issues: Hetzner support — private network configuration requires their intervention for IP assignment
- If PostgreSQL data is not intact on new server: restore from S3 backup using `kctl-pg backup restore --from-latest`
