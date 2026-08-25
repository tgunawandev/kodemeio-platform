# Authentik SSO Recovery

> Last verified: 2026-04-03 | Owner: Platform team

Authentik is a Layer 0 dependency for all services using OIDC login. When it fails, users cannot log in to Odoo, Grafana, GlitchTip, Dokploy, or any other SSO-protected service. Apps with `VITE_AUTH_MODE=native` (React PWAs) can bypass SSO — see the workaround section.

URL: `https://auth.kodeme.io` | Deploy manifest: `deploys/instances/kodeme.io-infra-authentik.yaml`

## Symptoms

- All OIDC-protected services redirect to auth.kodeme.io and show an error
- `502 Bad Gateway` on `auth.kodeme.io`
- Login redirect loops (client receives redirect but Authentik never responds)
- Grafana/Dokploy show "Failed to authenticate" after callback
- `kctl-ak health` returns connection refused or timeout
- Odoo showing "OAuth2 error" on login

## Diagnosis

```bash
# Step 1: Check Authentik health
kctl-ak health

# Step 2: Check recent failed logins — helps distinguish config vs infrastructure issue
kctl-ak audit logins --failed --limit 20

# Step 3: Check container logs for Python tracebacks or DB errors
kctl-dokploy services logs -s kodemeio-authentik --tail 100

# Step 4: Check Authentik worker separately (handles flows/policies)
kctl-dokploy services logs -s kodemeio-authentik-worker --tail 50

# Step 5: Verify PostgreSQL is reachable from Authentik
# If kctl-pg health fails, fix PostgreSQL first — see db-recovery.md
kctl-pg health

# Step 6: Check Redis (session cache) if available
kctl-dokploy services status -s kodemeio-redis
```

If logs show `django.db.utils.OperationalError` or `could not connect to server`, PostgreSQL is the root cause — go to [db-recovery.md](db-recovery.md) first.

## Recovery Steps

### Scenario A: Container Crashed

```bash
# 1. Restart Authentik server and worker
kctl-dokploy services restart -s kodemeio-authentik
kctl-dokploy services restart -s kodemeio-authentik-worker

# 2. Wait for healthcheck (Authentik can take 30-60s to boot)
kctl-dokploy services status -s kodemeio-authentik --watch

# 3. Verify health
kctl-ak health
```

### Scenario B: OIDC Provider Misconfiguration

Symptom: Authentik is up (`kctl-ak health` passes) but specific app logins fail.

```bash
# 1. List all OIDC providers
kctl-ak providers list

# 2. Check provider details for the failing app
kctl-ak providers show --name <provider-name>

# 3. List applications and their bindings
kctl-ak applications list

# 4. Check outpost status (proxy/LDAP outposts must be healthy)
kctl-ak outposts list
kctl-ak outposts status --name <outpost-name>

# 5. Restart outpost if unhealthy
kctl-dokploy services restart -s kodemeio-authentik-outpost
```

If the OIDC client secret was rotated in the app but not in Authentik (or vice versa), update the client secret:

```bash
# Show current provider config
kctl-ak providers show --name <provider-name>

# Update client secret (match what's in the app's OIDC_CLIENT_SECRET env var)
kctl-ak providers update --name <provider-name> --client-secret <new-secret>
```

### Scenario C: Authentik Migration Failure (after upgrade)

Symptoms in logs: `django.db.utils.ProgrammingError`, `column does not exist`, `relation does not exist`.

```bash
# 1. Run pending migrations manually
kctl-dokploy services exec -s kodemeio-authentik -- ak migrate

# 2. Restart after migration
kctl-dokploy services restart -s kodemeio-authentik
kctl-dokploy services restart -s kodemeio-authentik-worker

# 3. Verify
kctl-ak health
```

### Scenario D: Full Rebuild

Use only if Authentik state is unrecoverable. All OIDC client configurations will need to be re-applied from the manifest.

```bash
# 1. Rebuild from manifest
kctl-dokploy deploy apply -f deploys/instances/kodeme.io-infra-authentik.yaml

# 2. Wait for healthy state
kctl-ak health

# 3. Verify all providers are present
kctl-ak providers list
kctl-ak applications list
```

## SSO Bypass Workaround

While Authentik is down, services with native auth can still be accessed:

**React PWAs** — Apps configured with `VITE_AUTH_MODE=native` support direct username/password login. Check the app's env vars:

```bash
kctl-dokploy env show -s <react-app-service> | grep AUTH_MODE
```

**Odoo** — Odoo has its own internal auth. Users with local Odoo accounts (not OIDC-only) can log in at the `/web/login` path directly. Admin users are always local.

**Dokploy** — Has its own auth at `dokploy.kodeme.io`. Not dependent on Authentik.

**Grafana** — If configured with local admin account, accessible at `grafana.kodeme.io/login` with username/password.

Communicate the bypass to affected users via Telegram while fixing SSO:

```bash
kctl-telegram send --chat ops "SSO is temporarily down. Direct login available at <app-url>/login. Working on fix."
```

## Verification

```bash
# 1. Authentik API is healthy
kctl-ak health

# 2. No recent failed logins (or failure rate returned to baseline)
kctl-ak audit logins --failed --limit 10

# 3. Test an actual OIDC flow
# Open a browser, visit a protected app, click "Login with SSO"
# Confirm redirect to auth.kodeme.io works and returns you to the app

# 4. All outposts healthy
kctl-ak outposts list

# 5. Grafana shows auth.kodeme.io as green
kctl-grafana dashboard list
```

## Escalation

- If PostgreSQL recovery is also needed: start with [db-recovery.md](db-recovery.md)
- If OIDC provider configs are lost after rebuild: check `deploys/instances/kodeme.io-infra-authentik.yaml` for declarative provider definitions
- For Authentik bugs (not infrastructure): check https://github.com/goauthentik/authentik/issues before escalating
