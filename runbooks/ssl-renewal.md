# TLS Certificate Issues

> Last verified: 2026-04-03 | Owner: Platform team

Traefik handles TLS termination for all services using Let's Encrypt ACME. Certificates are auto-renewed ~30 days before expiry. Manual intervention is rarely needed but this runbook covers the cases where it is.

Traefik runs as part of Dokploy's own stack — **never stop or remove the `traefik` container directly.**

## Symptoms

- Browser shows "Your connection is not private" / `NET::ERR_CERT_AUTHORITY_INVALID`
- `curl` returns `SSL certificate problem: certificate has expired`
- `curl` returns `SSL certificate problem: unable to get local issuer certificate`
- `curl -I https://<domain>` fails but `curl -I http://<domain>` works
- Service is up but HTTPS connections refused
- Traefik dashboard shows certificate resolver errors
- Gatus SSL check is failing

## Diagnosis

```bash
# Step 1: Check certificate expiry and issuer for affected domains
kctl-cf ssl check --domain kodeme.io
kctl-cf ssl check --domain auth.kodeme.io
kctl-cf ssl check --domain odoo.kodeme.io

# Step 2: Check Traefik logs for ACME errors
kctl-dokploy services logs -s traefik --tail 100 | grep -i "acme\|certificate\|tls\|error"

# Step 3: Check Traefik dashboard (if accessible)
# https://traefik.kodeme.io — look at Certificates section

# Step 4: Verify DNS is resolving correctly (bad DNS blocks ACME HTTP-01 challenge)
kctl-cf dns list --domain kodeme.io
# Confirm A record points to 49.13.14.79

# Step 5: Check if Let's Encrypt rate limit is hit
# LE rate limit: 50 certs per domain per week
# Error in Traefik logs: "too many certificates already issued"
```

If DNS records are missing or pointing to the wrong IP, fix DNS first before attempting cert renewal — ACME HTTP-01 challenges will fail otherwise.

## Recovery Steps

### Scenario A: Certificate Expired / Not Renewing

Traefik auto-renews but the renewal may have silently failed. The fix is usually a Traefik restart.

```bash
# 1. Restart Traefik to trigger renewal attempt
# Use Dokploy to restart — never use docker restart directly on Traefik
kctl-dokploy services restart -s traefik

# 2. Watch Traefik logs for the ACME renewal
kctl-dokploy services logs -s traefik --tail 50 --follow
# Look for: "Obtain certificate" or "Certificate obtained successfully"

# 3. Wait up to 2 minutes, then verify
kctl-cf ssl check --domain <affected-domain>
```

### Scenario B: ACME Storage Corrupted

Symptoms: Traefik logs show JSON parse errors for `acme.json`, or cert requests fail immediately on restart.

```bash
# 1. Stop Traefik (via Dokploy only — do not docker stop traefik)
kctl-dokploy services stop -s traefik

# 2. Locate and back up the ACME storage file
# SSH to kodeme-service
# File is typically at: /var/lib/dokploy/traefik/acme.json
cp /var/lib/dokploy/traefik/acme.json /var/lib/dokploy/traefik/acme.json.bak-$(date +%Y%m%d)

# 3. Clear the corrupted ACME storage
echo '{}' > /var/lib/dokploy/traefik/acme.json
chmod 600 /var/lib/dokploy/traefik/acme.json

# 4. Start Traefik — it will request fresh certificates for all configured domains
kctl-dokploy services start -s traefik

# 5. Monitor renewal progress (may take 2-5 minutes for all certs)
kctl-dokploy services logs -s traefik --tail 100 --follow
```

Note: Clearing `acme.json` will cause a brief period of self-signed certs while Let's Encrypt issues new ones. There is no persistent downtime but browsers will show warnings for ~2-5 minutes.

### Scenario C: DNS Not Propagated (new domain or DNS change)

Traefik uses HTTP-01 ACME challenge. The domain must resolve to the server's public IP before the challenge can succeed.

```bash
# 1. Verify the DNS record exists and points to the right IP
kctl-cf dns list --domain <domain>
# Should show: A record → 49.13.14.79

# 2. If the record is missing, add it
kctl-cf dns create --domain <domain> --type A --name @ --value 49.13.14.79

# 3. Wait for DNS propagation (Cloudflare is near-instant; external resolvers up to 60s)
# Test from outside: dig +short <domain> @8.8.8.8

# 4. Restart Traefik to retry ACME challenge
kctl-dokploy services restart -s traefik
```

### Scenario D: Let's Encrypt Rate Limit Hit

Symptom in Traefik logs: `too many certificates already issued for registered domain`.

LE rate limits: 50 certificates per domain per week, 5 duplicate certificates per week.

```bash
# 1. Check LE rate limit status
# https://crt.sh/?q=<domain> — see recent certs issued

# 2. Wait out the rate limit window (resets weekly on Tuesday ~00:00 UTC)

# 3. Temporary workaround: use LE staging to verify config works
# Set Traefik ACME CA server to staging in Dokploy environment:
kctl-dokploy env set -s traefik TRAEFIK_CERTIFICATESRESOLVERS_LE_ACME_CASERVER=https://acme-staging-v02.api.letsencrypt.org/directory

# 4. After rate limit resets, switch back to production CA
kctl-dokploy env set -s traefik TRAEFIK_CERTIFICATESRESOLVERS_LE_ACME_CASERVER=https://acme-v02.api.letsencrypt.org/directory
kctl-dokploy services restart -s traefik
```

## Verification

```bash
# Check certificate validity for primary domains
kctl-cf ssl check --domain kodeme.io
kctl-cf ssl check --domain auth.kodeme.io
kctl-cf ssl check --domain odoo.kodeme.io
kctl-cf ssl check --domain grafana.kodeme.io

# Verify from curl
curl -sI https://kodeme.io | head -5
# Should return HTTP/2 200 with no SSL errors

# Check Grafana SSL monitors
kctl-grafana dashboard list
# All SSL checks should be green
```

## Escalation

- If Traefik itself won't start after clearing ACME storage: check Dokploy status at `dokploy.kodeme.io` — Dokploy manages Traefik's compose stack
- If Let's Encrypt is unreachable (LE outage): check https://letsencrypt.status.io/
- Cloudflare proxying issues (orange cloud vs grey cloud): ensure the A records for ACME domains are grey-cloud (DNS only, not proxied) if HTTP-01 challenges are failing
