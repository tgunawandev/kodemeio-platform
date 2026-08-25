# MAC Staging Runbook

Operations guide for the MAC Odoo staging environment.

**Last Updated:** 2026-04-10
**Related spec:** [archived design](../archive/superpowers/specs/2026-04-10-mac-staging-clone-design.md)
**Related plan:** [archived implementation plan](../archive/superpowers/plans/2026-04-10-mac-staging-clone.md)

---

## Overview

| Item | Value |
|---|---|
| **ERP URL** | https://stg-mac-odoo-erp.idtpp.com |
| **HRMS URL** | https://stg-mac-odoo-hrms.idtpp.com |
| **Compose host** | `tpp-prod-02` (46.224.93.123) — reused, not dedicated |
| **PostgreSQL host** | `tpp-prod-01` (shared with production) |
| **ERP database** | `stg_mac_odoo_erp` |
| **HRMS database** | `stg_mac_odoo_hrms` |
| **Dokploy ERP compose** | `mac-odoo-erp-stg` |
| **Dokploy HRMS compose** | `mac-odoo-hrms-stg` |
| **Staging admin password** | 1Password: `op://kodemeio/mac-odoo/staging-admin-password` |

Staging is a clone of production refreshed on demand. After each refresh, a neutralization step disables outgoing mail, payment providers, and webhooks so staging can never accidentally contact real customers or vendors.

---

## Refresh From Production

Full refresh takes ~5 minutes end to end. Run:

```bash
cd /path/to/kodemeio-dokploy
export KCTL_DOKPLOY_PROFILE=your-staging-profile
./ops/scripts/refresh-mac-staging.sh
```

The script:

1. Dumps production databases (`mac_odoo_erp`, `mac_odoo_hrms`) to `~/backups/mac-stg-clone/`
2. Drops and recreates staging databases
3. Restores prod dumps into staging
4. Pre-sets `web.base.url` so links are correct on first boot
5. Redeploys Dokploy compose services
6. Waits 90 seconds for containers
7. Runs `kctl-odoo staging neutralize-staging` on both instances
8. Smoke-tests both HTTPS endpoints
9. Keeps the 5 most recent backup pairs, prunes older

**Prerequisites:**
- SSH key at `~/.ssh/id_ed25519` for `tpp-prod-01` and `tpp-prod-02`
- `kctl-pg`, `kctl-dokploy`, `kctl-odoo`, `kctl-op` on PATH
- 1Password authenticated via `op account`
- `KCTL_DOKPLOY_PROFILE` set to the staging-capable Dokploy profile

---

## Day-to-Day Operations

### Check staging health

```bash
curl -I https://stg-mac-odoo-erp.idtpp.com/web/login
curl -I https://stg-mac-odoo-hrms.idtpp.com/web/login
```

Expected: HTTP 200 or 303.

### View logs

Resolve the exact Dokploy compose IDs before lifecycle operations:

```bash
export ERP_COMPOSE_ID=$(kctl-dokploy -p "$KCTL_DOKPLOY_PROFILE" --quiet --json compose search --name mac-odoo-erp-stg | jq -er '[.[] | select(.name == "mac-odoo-erp-stg")] | if length == 1 then .[0].composeId else error("expected one exact match") end')
export HRMS_COMPOSE_ID=$(kctl-dokploy -p "$KCTL_DOKPLOY_PROFILE" --quiet --json compose search --name mac-odoo-hrms-stg | jq -er '[.[] | select(.name == "mac-odoo-hrms-stg")] | if length == 1 then .[0].composeId else error("expected one exact match") end')
kctl-dokploy -p "$KCTL_DOKPLOY_PROFILE" compose service-logs "$ERP_COMPOSE_ID" --tail 100
kctl-dokploy -p "$KCTL_DOKPLOY_PROFILE" compose service-logs "$HRMS_COMPOSE_ID" --tail 100
```

### Restart staging

```bash
kctl-dokploy -p "$KCTL_DOKPLOY_PROFILE" compose redeploy "$ERP_COMPOSE_ID"
kctl-dokploy -p "$KCTL_DOKPLOY_PROFILE" compose redeploy "$HRMS_COMPOSE_ID"
```

### Re-apply neutralization manually

If someone re-enabled a mail server or payment provider by mistake:

```bash
export STG_ADMIN_PASSWORD=$(kctl-op read "op://kodemeio/mac-odoo/staging-admin-password")
kctl-odoo -p mac-erp-stg staging neutralize-staging
kctl-odoo -p mac-hrms-stg staging neutralize-staging
```

### Dry-run neutralization (see what would change)

```bash
kctl-odoo -p mac-erp-stg staging neutralize-staging --dry-run
kctl-odoo -p mac-hrms-stg staging neutralize-staging --dry-run
```

### Log in

- **URL:** https://stg-mac-odoo-erp.idtpp.com (or `-hrms`)
- **User:** admin
- **Password:** from 1Password `op://kodemeio/mac-odoo/staging-admin-password`

The company name is prefixed with `[STG]` after neutralization, so you can visually confirm you're on staging.

---

## Troubleshooting

| Problem | Likely Cause | Fix |
|---|---|---|
| HTTP 502 Bad Gateway | Container not ready after redeploy | Wait 60s and retry. Check logs. |
| HTTP 503 | Traefik can't reach container | Resolve the compose ID as above, then inspect `compose service-logs` |
| "Database does not exist" error | Staging DB wasn't restored | Re-run `./ops/scripts/refresh-mac-staging.sh` |
| Emails going out from staging | Neutralization not applied | Run `kctl-odoo -p mac-erp-stg staging neutralize-staging` |
| Payment provider sending real charges | Neutralization not applied | Same as above |
| Login fails with correct password | Wrong admin password in 1Password | Check `op://kodemeio/mac-odoo/staging-admin-password` — may need to update after refresh |
| Company name missing `[STG]` prefix | Neutralization not applied | Run neutralize command |
| Smoke test passes but login shows prod data | Normal — staging is cloned from prod | Verify `[STG]` prefix in company name |
| `stg_mac_odoo_*` database shows `mac_odoo_erp` content | Wrong dump restored | Re-run refresh script |
| `SENTRY_DSN` errors in logs | Env file has Sentry configured | Set `SENTRY_DSN=` (empty) in `.env.mac-odoo-erp` staging |

---

## Rollback

If staging is broken beyond repair and you just want a clean slate:

```bash
# Stop staging containers
kctl-dokploy -p "$KCTL_DOKPLOY_PROFILE" compose stop "$ERP_COMPOSE_ID"
kctl-dokploy -p "$KCTL_DOKPLOY_PROFILE" compose stop "$HRMS_COMPOSE_ID"

# Drop the databases
kctl-pg db drop stg_mac_odoo_erp --force
kctl-pg db drop stg_mac_odoo_hrms --force

# Re-run the refresh script (recreates DBs + redeploys)
./ops/scripts/refresh-mac-staging.sh
```

**Production is never at risk.** All operations use `stg_*` database names and `*-stg` compose service names. Nothing in this runbook touches production.

---

## Common Use Cases

### Before a training session

Refresh staging so trainees see current production data:

```bash
./ops/scripts/refresh-mac-staging.sh
```

Allow ~5 minutes. Verify with a login check before training starts.

### After a schema change in development

Test a module update against production-like data without risking prod:

```bash
# Refresh staging from latest prod
./ops/scripts/refresh-mac-staging.sh

# Test the module update
kctl-odoo -p mac-erp-stg modules upgrade your_module

# If it breaks, just re-refresh
./ops/scripts/refresh-mac-staging.sh
```

### Validating a bug report

Reproduce a bug against a clone of production:

1. Refresh staging
2. Log in as admin
3. Follow the reporter's steps
4. If reproduced, investigate in staging — no risk to prod users

### Practicing a risky operation (data import, mass update)

1. Refresh staging
2. Run the risky operation on staging
3. Verify the result
4. If good, run it on production with confidence
5. If bad, re-refresh staging and try a different approach

---

## Staging vs Production

| Aspect | Production | Staging |
|---|---|---|
| URL | `mac-odoo-erp.idtpp.com` | `stg-mac-odoo-erp.idtpp.com` |
| Company name | `CV Mandiri Agro Cemerlang` | `[STG] CV Mandiri Agro Cemerlang` |
| Outgoing email | Enabled (mailcow) | **Disabled** by neutralization |
| Payment providers | Enabled | **Disabled** by neutralization |
| Webhook endpoints | Enabled | **Disabled** by neutralization |
| Admin password | Separate prod password | Separate staging password (1Password) |
| Database | `mac_odoo_erp` | `stg_mac_odoo_erp` |
| Refresh cadence | Never | On demand via script |
| Workers | 4 | 2 (smaller workload) |
| Restart cost | High (real users) | Low (no real users) |

---

## Limitations

- **No email testing in staging.** Mail servers are disabled. To test email templates, use Odoo's "Send test" feature against a personal inbox by temporarily enabling a single mail server, then run `neutralize-staging` afterwards to lock it back down.
- **No payment gateway testing.** Providers are disabled. To test payments, temporarily re-enable a specific provider in test/sandbox mode, then neutralize again.
- **Shared Authentik OAuth client.** Staging uses the same OAuth credentials as prod. A dedicated staging OAuth client is tracked as a v2 improvement in the design spec.
- **No visual "STAGING" banner.** The `[STG]` prefix in company name is the only visual indicator. A red banner CSS override is a v2 improvement.
- **No automatic refresh schedule.** Refresh is manual for v1. A weekly auto-refresh cron is a v2 improvement.

---

## Related Documentation

- **Spec:** [archived design](../archive/superpowers/specs/2026-04-10-mac-staging-clone-design.md) — design decisions and rationale
- **Plan:** [archived implementation plan](../archive/superpowers/plans/2026-04-10-mac-staging-clone.md) — step-by-step implementation
- **Script:** [`ops/scripts/refresh-mac-staging.sh`](../../ops/scripts/refresh-mac-staging.sh) — automated refresh
- **CLI command:** `kctl-odoo staging neutralize-staging --help`
- **Tenant config:** [`deploys/tenants/mac.yaml`](../../deploys/tenants/mac.yaml)
- **Staging instance configs:** [`deploys/instances/staging/mac-odoo-*.yaml`](../../deploys/instances/staging/)
