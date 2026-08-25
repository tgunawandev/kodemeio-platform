# Dokploy Local Domains — Design

**Date:** 2026-04-18
**Status:** Draft (awaiting user approval)
**Owner:** @tgunawandev
**Scope:** `kodemeio-platform/deploys` + local Dokploy on this workstation

## 1. Problem

Local Dokploy deployments (e.g., `kod-infra-dbgate`) are currently reachable only via `http://localhost:<port>`, which:

- Requires per-service port juggling and collides with `kodemeio-platform`'s convention of publishing nothing except via Traefik.
- Breaks PWA testing locally (Service Workers, `secure` cookies, WebCrypto need HTTPS origin).
- Diverges from the production deploy model (Traefik labels + Dokploy-managed domain), so compose files in git need a second variant for local.

We want local deployments to behave **exactly like production**: same `docker-compose.prod.yml`, same Traefik labels, a clean HTTPS URL per service, reachable from the workstation and from a phone on the same Wi-Fi.

## 2. Goals / non-goals

**Goals**
- `https://<service>.local.kodeme.io` reachable with a trusted cert from the workstation and any device on the same LAN.
- Zero per-service cert work (single wildcard cert covers all).
- Convention encoded in `deploys/instances/local/*.yaml`: a declarative `domain.host` field is the single source of truth.
- Reconciled idempotently by `kctl-dokploy deploy apply-local <manifest>` — same mental model as production.
- Does not change how production deploys work; reuses the same compose files and label patterns.

**Non-goals**
- Offline-only operation. Cert renewal needs internet every ~60 days.
- Remote-access to local services from outside the LAN.
- Per-tenant sub-wildcards (`*.<tenant>.local.kodeme.io`). Can be added later.
- Auto-detecting LAN IP changes via a daemon. Documented manual step for now.

## 3. Chosen approach — context and decisions

| Decision | Choice | Alternatives considered | Why |
|---|---|---|---|
| Reverse proxy | Dokploy's own Traefik (reclaim :80/:443) | Piggyback on `jwilder/nginx-proxy`; run a separate Traefik on 8080/8443 | Production uses Dokploy's Traefik; matching it keeps compose files identical. Nginx-proxy is dormant Frappe infra with no active users. |
| TLD | `*.local.kodeme.io` (subzone of `kodeme.io`) | `.local` with mkcert; `.test` | User already manages `kodeme.io` in Cloudflare. Real LE cert + no per-device CA install. Works for phone PWA testing without trusting a custom CA on iOS/Android. |
| Cert issuance | Let's Encrypt DNS-01 via Cloudflare, using `lego` | mkcert; Traefik's built-in LE resolver with HTTP-01 | DNS-01 is the only option for wildcards and for issuing against an IP (`127.0.0.1` / RFC1918). `lego` is the official LE client, simpler to script than Traefik's internal resolver for a single wildcard. |
| Scope of change | "Standard pattern for all future local deploys" (Q2 option B) | DBGate-only; backfill existing composes | Pays for itself after the second service. Not worth rewiring `postgres-15-dev` / `tpp-infra-postgres` which are internal DB services with no web UI. |

## 4. Architecture

```
Dev laptop / phone on Wi-Fi
           │
           ▼
  public DNS: *.local.kodeme.io (Cloudflare, A → <workstation LAN IP>)
           │
           ▼
     <LAN IP>:443 (dokploy-traefik swarm service)
           │
           ├─ TLS terminated with wildcard *.local.kodeme.io cert
           │       (issued via Cloudflare DNS-01, renewed by systemd timer)
           │
           ▼
  match Host header → swarm/docker provider routes to compose service
           │
           ▼
  service container on dokploy-network  (Traefik labels from docker-compose.prod.yml)
```

## 5. Components

### 5.1 `dokploy-traefik` swarm service

- Image: `traefik:v3.2`.
- **Static config**: `/etc/dokploy/traefik/traefik.yml` — **unchanged** from the file already present on disk; it already defines `web:80`, `websecure:443`, swarm + docker providers, `letsencrypt` resolver (kept for any future public-domain services, not used for `*.local.kodeme.io`).
- **Dynamic config**: `/etc/dokploy/traefik/dynamic/` — existing file watcher. We add **one new file**:

  ```yaml
  # /etc/dokploy/traefik/dynamic/wildcard-local.yml
  # Paths are inside the Traefik container; host dir /etc/dokploy/traefik is
  # bind-mounted at /etc/traefik (see Volumes below).
  tls:
    certificates:
      - certFile: /etc/traefik/dynamic/certs/local.kodeme.io/fullchain.pem
        keyFile:  /etc/traefik/dynamic/certs/local.kodeme.io/privkey.pem
        stores:   [default]
    stores:
      default:
        defaultCertificate:
          certFile: /etc/traefik/dynamic/certs/local.kodeme.io/fullchain.pem
          keyFile:  /etc/traefik/dynamic/certs/local.kodeme.io/privkey.pem
  ```

  Setting the wildcard as the *default certificate* means any route that doesn't explicitly specify a cert resolver (i.e., every `*.local.kodeme.io` route) gets it automatically.

- **Volumes**:
  - `/etc/dokploy/traefik:/etc/traefik:ro` (static + dynamic config and certs; Traefik only reads — `lego` writes to the host dir directly, outside the container).
  - `/var/run/docker.sock:/var/run/docker.sock:ro`.
- **Networks**: joins `dokploy-network` (overlay).
- **Ports**: host-published `80:80` + `443:443`.
- **Run as**: docker swarm service (`docker service create` or a compose manifest under Dokploy itself). Following Dokploy's own pattern for `dokploy` / `dokploy-postgres` / `dokploy-redis`.

### 5.2 Cert issuance — `lego` + systemd timer

**Why `lego`, not Traefik's built-in resolver:** Traefik's ACME integration writes a single `acme.json` blob per-domain; works but is less portable and harder to debug/rotate. `lego` drops a conventional `{fullchain,privkey}.pem` pair into a directory, which we hand to Traefik via file provider.

**Files on disk**:

```
/etc/dokploy/traefik/
  traefik.yml                             # unchanged
  lego.env                                # 0600, root; CF_DNS_API_TOKEN=...
  dynamic/
    wildcard-local.yml                    # (new, 5.1)
    certs/                                # lego --path root
      certificates/                       # lego raw output: _.local.kodeme.io.crt/.key + archive
      local.kodeme.io/                    # wrapper-published stable names
        fullchain.pem                     # read by Traefik
        privkey.pem                       # read by Traefik

/usr/local/bin/
  dokploy-cert-renew.sh                   # wrapper calling lego + reload Traefik

/etc/systemd/system/
  dokploy-cert-renew.service              # oneshot unit
  dokploy-cert-renew.timer                # daily @ 03:00
```

**Wrapper script** (`dokploy-cert-renew.sh`, simplified):

```bash
#!/usr/bin/env bash
set -euo pipefail
umask 077

LEGO_DIR=/etc/dokploy/traefik/dynamic/certs
DOMAINS=(--domains '*.local.kodeme.io' --domains 'local.kodeme.io')
EMAIL=tri.gunawan@live.com

# shellcheck disable=SC1091
source /etc/dokploy/traefik/lego.env   # CF_DNS_API_TOKEN

# lego writes certificates into $LEGO_DIR/certificates/ — exact file name varies
# slightly across lego versions for wildcards (commonly `_.local.kodeme.io.crt`
# but may be `*.local.kodeme.io.crt` or URL-encoded). Resolve at runtime so the
# wrapper is version-tolerant.
if ls "$LEGO_DIR"/certificates/*local.kodeme.io.crt >/dev/null 2>&1; then
  lego --accept-tos --email "$EMAIL" --dns cloudflare \
       --path "$LEGO_DIR" "${DOMAINS[@]}" renew --days 30
else
  lego --accept-tos --email "$EMAIL" --dns cloudflare \
       --path "$LEGO_DIR" "${DOMAINS[@]}" run
fi

SRC_CRT=$(ls -1 "$LEGO_DIR"/certificates/*local.kodeme.io.crt | grep -v '.issuer.crt' | head -1)
SRC_KEY=${SRC_CRT%.crt}.key

# Publish the stable names Traefik reads (wildcard-local.yml references these).
install -D -m 0644 "$SRC_CRT" "$LEGO_DIR/local.kodeme.io/fullchain.pem"
install -D -m 0600 "$SRC_KEY" "$LEGO_DIR/local.kodeme.io/privkey.pem"

# Traefik's file provider watches this dir; no reload needed, but force-update the service
# to guarantee in-memory state matches disk.
docker service update --force dokploy-traefik >/dev/null
```

**Timer** (`dokploy-cert-renew.timer`): `OnCalendar=*-*-* 03:00:00`, `Persistent=true`, `RandomizedDelaySec=1h`.

Bootstrap = first manual run: `systemctl start dokploy-cert-renew.service`.

### 5.3 DNS — single wildcard record

- Cloudflare zone `kodeme.io`.
- Records to create (once):
  - `*.local.kodeme.io` — A, `<workstation LAN IP>`, **proxied = OFF** (Cloudflare cannot proxy to RFC1918 IPs, and we don't want them to anyway).
  - `local.kodeme.io` — A, `<workstation LAN IP>`, **proxied = OFF** (for bare apex, if ever needed).
- Creation via `kctl-cf dns create` — documented in the runbook.

**LAN IP drift:** On DHCP, the workstation's LAN IP may change. The reconciler (5.5) will compare the declared/current IP at `apply-local` time and call `kctl-cf dns update` if they differ. Users on a static LAN IP or MAC reservation won't hit this.

**TTL:** 60s on these records — fast failover if the IP changes.

### 5.4 Manifest schema

**No schema change needed.** The existing `deploys/instances/*.yaml` already supports:

```yaml
domain:
  host: <hostname>
  port: <internal container port>
  service: <compose service name>
  https: true
  cert: letsencrypt      # production; for local this key is ignored
```

**New convention (validated by the reconciler, not enforced by schema):**
- In `deploys/instances/local/*.yaml`, `domain.host` **must** end with `.local.kodeme.io`.
- The same compose file (`docker-compose.prod.yml`) is used for local and production. Env var `DOMAIN` differentiates.

Example diff for DBGate:

```diff
  # deploys/instances/local/kod-infra-dbgate.yaml
  domain:
-   host: localhost
-   port: 3001
+   host: dbgate.local.kodeme.io
+   port: 3000
    service: dbgate
-   https: false
+   https: true
  source_overrides:
    type: github
    owner: tgunawandev
    repo: kodemeio-dbgate
    branch: main
-   compose_path: ./docker-compose.yml
+   compose_path: ./docker-compose.prod.yml
```

And in `deploys/env/local/.env.kod-infra-dbgate`:

```diff
- DOMAIN=localhost
- DBGATE_PORT=3001
+ DOMAIN=dbgate.local.kodeme.io
```

### 5.5 Reconciler — `kctl-dokploy deploy apply-local`

Implemented in `kodemeio-platform/packages/kctl-dokploy/` as a new command under the existing `deploy` group.

**Inputs:** path to an instance manifest in `deploys/instances/local/`.

**Algorithm (idempotent):**

1. **Parse** the manifest; resolve `project`, `environment`, `domain`, `source_overrides`, `env_file`.
2. **Ensure DNS**: compute current LAN IP of this machine (first non-loopback IPv4 on the default route). Compare against the Cloudflare `*.local.kodeme.io` A record via `kctl-cf dns get`. If drift, `kctl-cf dns update`.
3. **Ensure project + environment** exist in Dokploy — same logic as production `deploy apply`.
4. **Ensure compose service** exists with the declared `source_overrides`. If it exists with different source config, update it.
5. **Push env** from the `env_file` via `kctl-dokploy env push --force`.
6. **Ensure Dokploy domain** attached:
   - `kctl-dokploy domains get <compose_id>` → compare.
   - If missing or differs, `kctl-dokploy domains create/update` with `host=domain.host`, `port=domain.port`, `service_name=domain.service`, `https=true`, `cert_type=none`.
   - **`cert_type=none` semantics:** instructs Dokploy to emit Traefik router labels **without** a `tls.certresolver` directive. Traefik then falls back to the default cert store set in `wildcard-local.yml` (§5.1) — our wildcard. If future routes need public Let's Encrypt (non-`.local.kodeme.io`), use `cert_type=letsencrypt` — the two coexist cleanly.
7. **Trigger redeploy only if any of steps 4, 5, or 6 changed something** (track a dirty flag).
8. **Verify**: `curl -sI https://<host>/` returns non-5xx within 60s, else print diagnostic and exit non-zero.

**Out of scope for the reconciler** (by design):
- It does **not** issue or renew certs — that's the systemd timer.
- It does **not** install or manage Traefik — one-time bootstrap (§7).
- It does **not** touch production deploys. A separate code path / flag.

## 6. Failure modes + rollback

| Failure | Detection | Recovery |
|---|---|---|
| LE rate limit (5 dupe certs/week per domain) | `lego` exits non-zero; `systemctl status dokploy-cert-renew` red | We issue **one** wildcard covering every hostname; the limit is not a concern at normal cadence. Weekly cap is 5, we renew every ~60 days. |
| Cloudflare API token expired/revoked | `lego` fails DNS-01 challenge | Mint new scoped token (`Zone.DNS:Edit` + `Zone:Read` on `kodeme.io`), update `/etc/dokploy/traefik/lego.env`, re-run service. |
| Workstation LAN IP changed | Old IP in DNS, `curl` times out, or mobile device can't reach | `kctl-dokploy deploy apply-local <any manifest>` — its DNS reconcile step detects + fixes. Or manual `kctl-cf dns update`. |
| Cert file corrupted / truncated | Traefik logs TLS error, browser cert error | Re-issue: `systemctl start dokploy-cert-renew.service` (LE weekly rate limit is 5 per identical SAN set; plenty of headroom). If rate-limited, restore from the nightly `/etc/dokploy/traefik` backup (see §9 — covered by existing kodemeio ops backups, or adds a new one). |
| Traefik dynamic-config syntax error | Traefik logs config rejection, 502 on existing routes | File watcher doesn't hot-unload prior good state; revert `wildcard-local.yml` from git (the file will be committed). |
| Frappe stack removal regret | — | `docker compose -f /home/tgunawan/frappe/services/docker-compose.yml up -d`. The compose dir is **not** deleted by this plan; only `down`. |
| Offline dev, cert still valid | DNS resolution works via local cache; new services still get cert from wildcard | No action. |
| Offline dev, cert expired | Browser cert error | Short-term workaround: `127.0.0.1 foo.local.kodeme.io` in `/etc/hosts` + accept cert warning; long-term: reconnect and run timer. |
| DBGate port 3001 dependency gone (reclaim by something else) | — | Port no longer published; no action needed. Traffic flows through Traefik:443 exclusively. |

## 7. Migration / test plan

### 7.1 One-time migration

Run in order:

1. Retire Frappe stack:
   ```bash
   docker compose -f /home/tgunawan/frappe/services/docker-compose.yml down
   ss -ltn | grep -E ':80 |:443 '   # expect: empty
   ```
2. Create `/etc/dokploy/traefik/lego.env` (0600, root) with `CF_DNS_API_TOKEN=<scoped token>`.
3. Create Cloudflare records via `kctl-cf`:
   ```bash
   LAN_IP=$(ip -4 -o route get 1 | awk '{print $7; exit}')
   kctl-cf dns create --zone kodeme.io --type A --name '*.local' --content "$LAN_IP" --proxied=false --ttl 60
   kctl-cf dns create --zone kodeme.io --type A --name 'local'   --content "$LAN_IP" --proxied=false --ttl 60
   ```
4. Install `lego` (`go install` or package manager), install the wrapper script + systemd units, bootstrap the cert:
   ```bash
   sudo install -m 0755 dokploy-cert-renew.sh /usr/local/bin/
   sudo install -m 0644 dokploy-cert-renew.{service,timer} /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now dokploy-cert-renew.timer
   sudo systemctl start dokploy-cert-renew.service   # one-shot bootstrap
   ```
5. Deploy `dokploy-traefik` as a swarm service (compose + `docker stack deploy`). Verify: `docker service ls | grep dokploy-traefik` → 1/1 replicas.
6. Write `wildcard-local.yml` into `/etc/dokploy/traefik/dynamic/`.
7. **Smoke test:**
   ```bash
   curl -vk https://nothing.local.kodeme.io   # expect Traefik 404 + valid *.local.kodeme.io cert in TLS handshake
   ```

### 7.2 Rewire DBGate (first real consumer)

1. Update `deploys/instances/local/kod-infra-dbgate.yaml` (diff in §5.4).
2. Update `deploys/env/local/.env.kod-infra-dbgate`: set `DOMAIN=dbgate.local.kodeme.io`, drop `DBGATE_PORT`.
3. `kctl-dokploy deploy apply-local deploys/instances/local/kod-infra-dbgate.yaml`.
4. Verify:
   ```bash
   curl -sI https://dbgate.local.kodeme.io/ | head -1   # HTTP/2 200
   openssl s_client -connect dbgate.local.kodeme.io:443 -servername dbgate.local.kodeme.io </dev/null 2>/dev/null | openssl x509 -noout -subject -enddate
   # subject=CN = *.local.kodeme.io ; notAfter in ~90d
   ```
5. Load the URL in a browser — expect green padlock, DBGate login screen.

### 7.3 Acceptance tests (automated where possible)

These are added as a checked-in script `kodemeio-platform/deploys/tests/local-domains-smoke.sh`:

- Cert validity > 30 days.
- Wildcard covers a second hostname (temporarily add a route and curl it).
- Traefik healthcheck responds on `/ping`.
- `dokploy-cert-renew.service` reports success in the last 30 days.

### 7.4 Second consumer (proof of reuse)

As proof that Approach-2's "standard pattern" is real, add a second local instance under `deploys/instances/local/` (proposed: a local-only `kod-infra-portainer` or similar small web service), run `apply-local`, and confirm zero additional per-service setup beyond the manifest.

## 8. Out of scope (captured for later)

- **LAN IP auto-reconcile on boot**: systemd-networkd dispatcher hook that calls `kctl-dokploy deploy apply-local --dns-only` when the default route changes.
- **mkcert offline fallback**: for air-gapped work; trivial to add a second cert file in `wildcard-local.yml`.
- **Per-tenant sub-wildcards**: `*.kod.local.kodeme.io`, `*.tpp.local.kodeme.io` — issue as additional SANs on the same LE cert.
- **HTTP→HTTPS redirect middleware**: already in Dokploy's Traefik static config; verify post-migration.

## 9. Affected repos / files

| Path | Change |
|---|---|
| `kodemeio-platform/packages/kctl-dokploy/src/kctl_dokploy/commands/deploy.py` | New subcommand `apply-local` (or flag on existing `apply`). |
| `kodemeio-platform/deploys/instances/local/kod-infra-dbgate.yaml` | Update `domain.host`, `compose_path`. |
| `kodemeio-platform/deploys/env/local/.env.kod-infra-dbgate` | `DOMAIN=dbgate.local.kodeme.io`, drop `DBGATE_PORT`. |
| `kodemeio-platform/deploys/tests/local-domains-smoke.sh` | New acceptance tests. |
| `kodemeio-platform/deploys/bootstrap/dokploy-traefik/` | New: compose file + dynamic config template + systemd units + wrapper script. |
| `kodemeio-platform/docs/superpowers/specs/2026-04-18-dokploy-local-domains-design.md` | This spec. |
| `/etc/dokploy/traefik/lego.env` | New, NOT in git (contains secret). |
| `/etc/dokploy/traefik/dynamic/wildcard-local.yml` | New, rendered from template on bootstrap. |
| `/usr/local/bin/dokploy-cert-renew.sh` | New. |
| `/etc/systemd/system/dokploy-cert-renew.{service,timer}` | New. |

No changes to production deploys, production compose files, or the `kodemeio-dbgate` repo.

## 10. Open questions (for user review)

1. Is `tri.gunawan@live.com` the right LE contact email, or a shared ops alias?
2. Confirm the Cloudflare scoped API token name convention — is there an existing one we can reuse, or do we mint a new one (`dokploy-local-cert-renew`)?
3. Should `apply-local` auto-commit the manifest changes it makes (e.g., a recorded LAN IP), or stay purely read-on-disk?
