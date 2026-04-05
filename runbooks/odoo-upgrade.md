# Odoo Deployment and Upgrade

> Last verified: 2026-04-03 | Owner: Platform team

Covers deploying a new Odoo image, applying module updates, and rolling back. This applies to all 6 Odoo instances:

| Instance | Manifest | URL |
|----------|----------|-----|
| kodeme.io full | `kodeme.io-odoo-full.yaml` | odoo.kodeme.io |
| kodeme.io HRMS | `kodeme.io-odoo-hrms.yaml` | odoo-hrms.kodeme.io |
| mandiriagro.com HRMS | `mandiriagro.com-odoo-hrms.yaml` | odoo.mandiriagro.com |
| mandiriagro.com trading | `mandiriagro.com-odoo-trading.yaml` | odoo-trading.mandiriagro.com |
| pakerti.com HRMS | `pakerti.com-odoo-hrms.yaml` | odoo.pakerti.com |
| pakerti.com trading | `pakerti.com-odoo-trading.yaml` | odoo-trading.pakerti.com |

Source image: `kodemeio-odoo` repo → `compose/odoo.prod.yml` (4 containers: init → web + cron + gevent).

## Pre-Deploy Checklist

Work through this before touching production. Skip nothing at 3am — mistakes here mean restoring from backup.

```bash
# 1. Back up the target database NOW, before any changes
kctl-pg backup create --database <db-name>
kctl-pg backup list  # confirm backup appears

# 2. Note the current image tag (you'll need this for rollback)
kctl-dokploy services show -s <service-name> | grep -i image

# 3. List currently installed modules (to verify post-deploy)
kctl-odoo modules list --installed

# 4. Verify the new image is available in registry
kctl-dokploy registry list | grep kodemeio-odoo

# 5. If staging exists: deploy to staging first and verify
kctl-dokploy deploy apply -f deploys/instances/<staging-manifest>.yaml
kctl-odoo health --profile staging
```

If there is no staging environment, do a dry-run to confirm the manifest is valid:

```bash
kctl-dokploy deploy apply -f deploys/instances/kodeme.io-odoo-full.yaml --dry-run
```

## Deploy Steps

### Full Pipeline Deploy (standard path)

```bash
# 1. Run the full 11-phase deploy pipeline
kctl-dokploy deploy apply -f deploys/instances/kodeme.io-odoo-full.yaml

# The pipeline runs:
# Phase 1:  DNS check (kctl-cf)
# Phase 2:  Database ensure (kctl-pg)
# Phase 3:  Registry access (kctl-dokploy)
# Phase 4:  Compose service create/update (kctl-dokploy)
# Phase 5:  Environment vars push (kctl-dokploy)
# Phase 6:  Traefik domain routing (kctl-dokploy)
# Phase 7:  Trigger redeploy (kctl-dokploy)
# Phase 8:  Wait for healthcheck pass (kctl-dokploy)
# Phase 9:  Configure backup destination (kctl-dokploy)
# Phase 10: Setup cron schedules (kctl-dokploy)
# Phase 11: Install Odoo bundles/profiles (kctl-odoo)
```

### Staged Deploy (when troubleshooting)

```bash
# Stage 1: DNS + DB + Compose + Env + Domain
kctl-dokploy deploy setup -f deploys/instances/kodeme.io-odoo-full.yaml

# Stage 2: Deploy + wait for healthcheck
kctl-dokploy deploy run -f deploys/instances/kodeme.io-odoo-full.yaml

# Stage 3: Backup config + schedules + post-deploy hooks
kctl-dokploy deploy post -f deploys/instances/kodeme.io-odoo-full.yaml
```

### Image-Only Update (no config changes)

```bash
# 1. Update the image tag in the manifest
# Edit deploys/instances/kodeme.io-odoo-full.yaml — change image.tag

# 2. Push the env/compose update and redeploy
kctl-dokploy deploy run -f deploys/instances/kodeme.io-odoo-full.yaml
```

## Post-Deploy Steps

```bash
# 1. Verify the service is healthy
kctl-dokploy services status -s kodemeio-odoo-full

# 2. Update all installed modules (critical after image changes)
kctl-odoo modules update --all

# 3. Check for failed module updates
kctl-odoo modules list --state failed

# 4. Verify healthcheck endpoint responds
kctl-odoo health

# 5. Run a smoke test — check Odoo web UI is functional
kctl-odoo e2e test login

# 6. Check no critical errors in logs
kctl-dokploy services logs -s kodemeio-odoo-full --tail 50 | grep -i "error\|critical\|traceback"

# 7. Verify OIDC login still works (Authentik integration)
# Open the app in a browser and test SSO login

# 8. Confirm backup schedule is active
kctl-dokploy services show -s kodemeio-odoo-full | grep -i backup
```

## Module Management

```bash
# Install a new module
kctl-odoo modules install --module <module_name>

# Update specific modules
kctl-odoo modules update --module sale,account,stock

# Update all modules (safe after image upgrade)
kctl-odoo modules update --all

# Check module status
kctl-odoo modules list --state installed
kctl-odoo modules list --state failed

# Uninstall a module
kctl-odoo modules uninstall --module <module_name>
```

## Rollback

If the deployment fails or introduces a regression, roll back to the previous image tag.

```bash
# 1. Note the previous image tag (from pre-deploy step or git history)
# git log deploys/instances/kodeme.io-odoo-full.yaml

# 2. Edit the manifest to restore the previous tag
# deploys/instances/kodeme.io-odoo-full.yaml — revert image.tag

# 3. Redeploy with the old image
kctl-dokploy deploy run -f deploys/instances/kodeme.io-odoo-full.yaml

# 4. If database schema was changed by the new version, restore from backup
kctl-pg backup list
kctl-pg backup restore --backup-id <pre-deploy-backup-id>

# 5. Restart Odoo after database restore
kctl-dokploy services restart -s kodemeio-odoo-full

# 6. Verify rollback
kctl-odoo health
kctl-odoo modules list --installed
```

Database restores are destructive — all data written after the backup is lost. Confirm with stakeholders before restoring.

## Verification

```bash
# Full health check
kctl-odoo health

# Login test (requires kctl-odoo E2E Playwright setup)
kctl-odoo e2e test login

# Check all menus load without errors
kctl-odoo e2e test --smoke

# Confirm service shows healthy in Grafana
kctl-grafana dashboard list
```

## Escalation

- Module install failures with `odoo.exceptions.ValidationError`: check module dependencies — install missing modules first
- Image pull failures: check registry credentials with `kctl-dokploy registry list`
- Database migration errors: do not retry — take a backup immediately and investigate logs before attempting again
- If a customer reports data loss after deployment: stop all writes, take a backup, then investigate — do not overwrite anything
