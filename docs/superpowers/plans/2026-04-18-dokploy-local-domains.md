# Dokploy Local Domains Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable `https://<service>.local.kodeme.io` for every local Dokploy deployment, reachable from the workstation and from phones on the same Wi-Fi, using a real Let's Encrypt wildcard cert (DNS-01 via Cloudflare) served by Dokploy's own Traefik. Encode the pattern declaratively in `deploys/instances/local/*.yaml` via a new `kctl-dokploy deploy apply-local` command.

**Architecture:** Retire the dormant `fm_global-*` Frappe stack to free :80/:443 → issue a single wildcard `*.local.kodeme.io` via `lego` with a systemd timer for renewal → run `dokploy-traefik` as a swarm service consuming that cert via a file-provider fragment → build a Python reconciler in `kctl-dokploy` that reads the existing `DeployManifest` (Pydantic, in `core/manifest.py`) and converges Cloudflare DNS + Dokploy compose/domain/env state. No changes to production compose files or production Dokploy behavior.

**Tech Stack:** Python 3.12 (Typer + Pydantic v2 for `kctl-dokploy`), `lego` (Go binary, Let's Encrypt client), Traefik v3.2 (swarm mode), systemd (timers), `kctl-cf` (existing Cloudflare CLI), Bash (bootstrap shell scripts), pytest + pytest-httpx (existing test harness in `packages/kctl-dokploy/tests/`).

**Spec:** `docs/superpowers/specs/2026-04-18-dokploy-local-domains-design.md`

---

## File Structure

**New files (in `kodemeio-platform` repo):**

| Path | Purpose |
|---|---|
| `deploys/bootstrap/dokploy-traefik/docker-compose.yml` | The `dokploy-traefik` swarm-mode stack file |
| `deploys/bootstrap/dokploy-traefik/dynamic/wildcard-local.yml` | Traefik file-provider fragment registering the wildcard cert as default |
| `deploys/bootstrap/dokploy-traefik/lego.env.example` | Template for the Cloudflare token env (real file is `/etc/dokploy/traefik/lego.env`, NEVER in git) |
| `deploys/bootstrap/dokploy-traefik/dokploy-cert-renew.sh` | Wrapper script called by systemd; runs `lego`, publishes stable cert paths, force-updates Traefik |
| `deploys/bootstrap/dokploy-traefik/dokploy-cert-renew.service` | systemd one-shot service unit |
| `deploys/bootstrap/dokploy-traefik/dokploy-cert-renew.timer` | systemd timer (daily) |
| `deploys/bootstrap/dokploy-traefik/README.md` | Runbook: one-time install + troubleshooting |
| `deploys/tests/local-domains-smoke.sh` | Post-deploy smoke tests (cert validity, wildcard coverage, Traefik health) |
| `packages/kctl-dokploy/src/kctl_dokploy/core/lan_ip.py` | Detect the workstation's current LAN IP (used by the reconciler) |
| `packages/kctl-dokploy/src/kctl_dokploy/core/local_reconciler.py` | The reconciler: given a manifest, converge CF DNS + Dokploy compose/domain/env |
| `packages/kctl-dokploy/tests/core/test_lan_ip.py` | Unit tests for `lan_ip.py` |
| `packages/kctl-dokploy/tests/core/test_local_reconciler.py` | Unit tests for `local_reconciler.py` (all external calls mocked) |

**Modified files:**

| Path | Change |
|---|---|
| `packages/kctl-dokploy/src/kctl_dokploy/commands/deploy.py` | Add `apply_local` Typer command that wires manifest → `LocalReconciler.apply()` |
| `deploys/instances/local/kod-infra-dbgate.yaml` | `domain.host: dbgate.local.kodeme.io`, `compose_path: ./docker-compose.prod.yml` |
| `deploys/env/local/.env.kod-infra-dbgate` | `DOMAIN=dbgate.local.kodeme.io`, remove `DBGATE_PORT` |

**Files on the workstation (not in git — installed by Phase 1):**

- `/etc/dokploy/traefik/lego.env` (0600, root) — real CF token
- `/etc/dokploy/traefik/dynamic/wildcard-local.yml` (copy of the template)
- `/etc/dokploy/traefik/dynamic/certs/certificates/_.local.kodeme.io.crt` (written by `lego`)
- `/etc/dokploy/traefik/dynamic/certs/certificates/_.local.kodeme.io.key` (written by `lego`)
- `/etc/dokploy/traefik/dynamic/certs/local.kodeme.io/fullchain.pem` (published by wrapper; read by Traefik)
- `/etc/dokploy/traefik/dynamic/certs/local.kodeme.io/privkey.pem` (published by wrapper; read by Traefik)
- `/usr/local/bin/dokploy-cert-renew.sh` (copy of the script, 0755)
- `/etc/systemd/system/dokploy-cert-renew.service` (copy)
- `/etc/systemd/system/dokploy-cert-renew.timer` (copy)

---

## Phase Ordering

- **Phase 1 — Free the ports.** Gracefully stop the dormant Frappe nginx-proxy. No rollback risk — bring it back with one command if needed.
- **Phase 2 — Cert issuance.** Mint Cloudflare token, create wildcard DNS records, install `lego`, bootstrap the cert, install the renewal timer. At the end: a valid `fullchain.pem` / `privkey.pem` on disk.
- **Phase 3 — Traefik stack.** Write the `wildcard-local.yml` fragment, deploy `dokploy-traefik` swarm service, smoke-test with an unknown `.local.kodeme.io` host.
- **Phase 4 — Reconciler code (TDD).** Build `lan_ip.py` + `local_reconciler.py` + CLI wiring. All external calls mocked in tests.
- **Phase 5 — Rewire DBGate.** Update its manifest + env, run `apply-local`, verify green padlock in a real browser.
- **Phase 6 — Acceptance tests + proof-of-reuse.** Smoke-test script, commit a second local service to prove the pattern is reusable with zero extra setup.

---

## Phase 1 — Retire Frappe stack, free :80 / :443

### Task 1: Confirm Frappe stack is inactive, then stop it

**Files:** none (ops)

- [ ] **Step 1: Verify no active traffic**

Run:
```bash
docker logs --since 7d fm_global-nginx-proxy 2>&1 | grep -cE ' 200 | 301 | 302 ' || true
```

Expected: `0` (no 2xx/3xx in the last week). If > 0, **stop this task and escalate** — something is actually using the proxy.

- [ ] **Step 2: Verify ports are held by the proxy (and only the proxy)**

Run:
```bash
sudo ss -ltnp '( sport = :80 or sport = :443 )'
```

Expected: only `docker-proxy` processes traced back to `fm_global-nginx-proxy` via `docker inspect`. If other listeners appear, **stop and escalate**.

- [ ] **Step 3: Stop the Frappe stack (both containers), leave the DB volume intact**

Run:
```bash
docker compose -f /home/tgunawan/frappe/services/docker-compose.yml down
```

Expected: `fm_global-nginx-proxy` and `fm_global-db` containers removed. Volumes (`./mariadb/data`, `./nginx-proxy/certs`, etc.) remain on disk.

- [ ] **Step 4: Verify :80 and :443 are free**

Run:
```bash
ss -ltn '( sport = :80 or sport = :443 )'
```

Expected: empty output.

- [ ] **Step 5: Commit — none**

This step has no file changes. Move to Task 2. Rollback (if ever needed): `docker compose -f /home/tgunawan/frappe/services/docker-compose.yml up -d`.

---

## Phase 2 — Cert issuance

### Task 2: Mint a scoped Cloudflare API token

**Files:** none (manual + `/etc/dokploy/traefik/lego.env`)

- [ ] **Step 1: Mint the token via Cloudflare dashboard**

Open https://dash.cloudflare.com/profile/api-tokens → **Create Token** → **Custom token** with:
- Name: `dokploy-local-cert-renew`
- Permissions:
  - `Zone` → `Zone` → `Read`
  - `Zone` → `DNS` → `Edit`
- Zone Resources: Include → Specific zone → `kodeme.io`
- TTL: no expiry (or annual per ops policy)

Save the token. It is shown **once**.

- [ ] **Step 2: Stash it on disk (root-only, never git)**

Run:
```bash
sudo install -d -m 0700 -o root -g root /etc/dokploy/traefik
sudo tee /etc/dokploy/traefik/lego.env >/dev/null <<'EOF'
CF_DNS_API_TOKEN=<paste-token-here>
EOF
sudo chmod 0600 /etc/dokploy/traefik/lego.env
sudo chown root:root /etc/dokploy/traefik/lego.env
```

- [ ] **Step 3: Verify file perms**

Run: `sudo stat -c '%a %U:%G %n' /etc/dokploy/traefik/lego.env`
Expected: `600 root:root /etc/dokploy/traefik/lego.env`

- [ ] **Step 4: Commit — none**

No git changes. The secret is not committed.

---

### Task 3: Create Cloudflare wildcard DNS records

**Files:** none (live DNS state)

- [ ] **Step 1: Resolve the current LAN IP**

Run:
```bash
LAN_IP=$(ip -4 -o route get 1 | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}')
echo "LAN_IP=$LAN_IP"
```

Expected: a non-loopback IPv4 (e.g., `192.168.1.5`). Write it down.

- [ ] **Step 2: Inspect `kctl-cf` DNS command syntax**

Run: `kctl-cf dns create --help`
Expected: shows flags like `--zone`, `--type`, `--name`, `--content`, `--proxied`, `--ttl`. (If the flag names differ, adjust Step 3 accordingly.)

- [ ] **Step 3: Create wildcard + apex A records**

Run (substituting the real IP and the profile your `kodeme.io` zone lives under):
```bash
kctl-cf -p kodemeio dns create --zone kodeme.io --type A --name '*.local' --content "$LAN_IP" --proxied=false --ttl 60
kctl-cf -p kodemeio dns create --zone kodeme.io --type A --name 'local'   --content "$LAN_IP" --proxied=false --ttl 60
```

Expected: two 200 OK responses from the Cloudflare API.

- [ ] **Step 4: Verify public resolution**

Run:
```bash
dig +short '@1.1.1.1' nothing.local.kodeme.io A
dig +short '@1.1.1.1' local.kodeme.io A
```

Expected: both return the `$LAN_IP`. (DNS may take ≤ 60s to propagate from Cloudflare; retry once.)

- [ ] **Step 5: Commit — none**

No git changes.

---

### Task 4: Install the `lego` binary

**Files:** none (system binary)

- [ ] **Step 1: Install `lego`**

Run:
```bash
sudo apt-get install -y golang-go  # if not already present
LEGO_VERSION=v4.19.2
curl -sSL "https://github.com/go-acme/lego/releases/download/${LEGO_VERSION}/lego_${LEGO_VERSION}_linux_amd64.tar.gz" | sudo tar -xz -C /usr/local/bin lego
sudo chmod 0755 /usr/local/bin/lego
```

- [ ] **Step 2: Verify**

Run: `lego --version`
Expected: `lego version 4.19.2`.

- [ ] **Step 3: Commit — none**

Binary is system-installed, not tracked in git.

---

### Task 5: Author the cert-renew wrapper script

**Files:**
- Create: `deploys/bootstrap/dokploy-traefik/dokploy-cert-renew.sh`

- [ ] **Step 1: Write the script**

Create `deploys/bootstrap/dokploy-traefik/dokploy-cert-renew.sh`:

```bash
#!/usr/bin/env bash
# Dokploy local-domains cert renewal wrapper.
# Idempotent: runs `lego run` on first invocation, `lego renew --days 30` after.
# Called by dokploy-cert-renew.service (systemd).

set -euo pipefail
umask 077

LEGO_DIR=/etc/dokploy/traefik/dynamic/certs
EMAIL=tri.gunawan@live.com
DOMAINS=(--domains '*.local.kodeme.io' --domains 'local.kodeme.io')

# shellcheck disable=SC1091
source /etc/dokploy/traefik/lego.env   # exports CF_DNS_API_TOKEN
export CF_DNS_API_TOKEN

mkdir -p "$LEGO_DIR/certificates" "$LEGO_DIR/local.kodeme.io"

if ls "$LEGO_DIR"/certificates/*local.kodeme.io.crt 2>/dev/null | grep -qv '\.issuer\.crt$'; then
  /usr/local/bin/lego --accept-tos --email "$EMAIL" --dns cloudflare \
        --path "$LEGO_DIR" "${DOMAINS[@]}" renew --days 30
else
  /usr/local/bin/lego --accept-tos --email "$EMAIL" --dns cloudflare \
        --path "$LEGO_DIR" "${DOMAINS[@]}" run
fi

SRC_CRT=$(ls -1 "$LEGO_DIR"/certificates/*local.kodeme.io.crt | grep -v '\.issuer\.crt$' | head -1)
SRC_KEY="${SRC_CRT%.crt}.key"

install -D -m 0644 "$SRC_CRT" "$LEGO_DIR/local.kodeme.io/fullchain.pem"
install -D -m 0600 "$SRC_KEY" "$LEGO_DIR/local.kodeme.io/privkey.pem"

# Force Traefik to re-read certs (file watcher normally does this; belt-and-suspenders).
if docker service ls --format '{{.Name}}' | grep -qx dokploy-traefik; then
  docker service update --force dokploy-traefik >/dev/null
fi

echo "Cert rotated: $(date -Iseconds)"
```

- [ ] **Step 2: Shell-syntax check**

Run: `bash -n deploys/bootstrap/dokploy-traefik/dokploy-cert-renew.sh`
Expected: no output (success). Any output = syntax error — fix.

- [ ] **Step 3: Install to system**

Run:
```bash
sudo install -m 0755 -o root -g root \
  deploys/bootstrap/dokploy-traefik/dokploy-cert-renew.sh \
  /usr/local/bin/dokploy-cert-renew.sh
```

- [ ] **Step 4: Commit**

```bash
git add deploys/bootstrap/dokploy-traefik/dokploy-cert-renew.sh
git commit -m "feat(deploys): add dokploy-traefik cert renewal wrapper"
```

---

### Task 6: Bootstrap the initial cert (first `lego run`)

**Files:** none (runs the script manually once)

- [ ] **Step 1: Dry-run the script with `set -x` to see what lego does**

Run:
```bash
sudo bash -x /usr/local/bin/dokploy-cert-renew.sh 2>&1 | tee /tmp/lego-bootstrap.log | tail -50
```

Expected: `lego` completes with "Server responded with a certificate", final line shows `Cert rotated: ...`. (If it fails on DNS-01 propagation, retry — Cloudflare can need 30–60s.)

- [ ] **Step 2: Verify cert files on disk**

Run:
```bash
sudo ls -la /etc/dokploy/traefik/dynamic/certs/local.kodeme.io/
sudo openssl x509 -in /etc/dokploy/traefik/dynamic/certs/local.kodeme.io/fullchain.pem -noout -subject -issuer -enddate
```

Expected:
- Two files: `fullchain.pem` (0644), `privkey.pem` (0600).
- `subject=CN = *.local.kodeme.io`
- `issuer=...Let's Encrypt...`
- `notAfter=<~90 days from now>`

- [ ] **Step 3: Commit — none**

Cert files live under `/etc/` only, not in git.

---

### Task 7: Install systemd service + timer

**Files:**
- Create: `deploys/bootstrap/dokploy-traefik/dokploy-cert-renew.service`
- Create: `deploys/bootstrap/dokploy-traefik/dokploy-cert-renew.timer`

- [ ] **Step 1: Write the service unit**

Create `deploys/bootstrap/dokploy-traefik/dokploy-cert-renew.service`:

```ini
[Unit]
Description=Dokploy local-domains cert renewal
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/dokploy-cert-renew.sh
# Don't spam logs on retry; systemd will mark failure and the timer retries next day.
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Write the timer unit**

Create `deploys/bootstrap/dokploy-traefik/dokploy-cert-renew.timer`:

```ini
[Unit]
Description=Daily check: renew *.local.kodeme.io cert if < 30 days to expiry
Requires=dokploy-cert-renew.service

[Timer]
OnCalendar=*-*-* 03:00:00
RandomizedDelaySec=1h
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 3: Install both units**

Run:
```bash
sudo install -m 0644 -o root -g root \
  deploys/bootstrap/dokploy-traefik/dokploy-cert-renew.{service,timer} \
  /etc/systemd/system/
sudo systemctl daemon-reload
```

- [ ] **Step 4: Enable (but do NOT start) the timer**

Run:
```bash
sudo systemctl enable dokploy-cert-renew.timer
sudo systemctl start  dokploy-cert-renew.timer
sudo systemctl list-timers dokploy-cert-renew.timer
```

Expected: timer listed with `NEXT` a.m. 03:00, `UNIT=dokploy-cert-renew.timer`.

- [ ] **Step 5: Dry-run the service (idempotent — should just do a `renew` that's a no-op)**

Run:
```bash
sudo systemctl start dokploy-cert-renew.service
sudo journalctl -u dokploy-cert-renew.service -n 20 --no-pager
```

Expected: log line `Cert rotated: <date>` or `lego: Certificates for the domains is not due for renewal, not renewing`. Exit code 0.

- [ ] **Step 6: Commit**

```bash
git add deploys/bootstrap/dokploy-traefik/dokploy-cert-renew.{service,timer}
git commit -m "feat(deploys): add systemd units for dokploy-traefik cert renewal"
```

---

## Phase 3 — Deploy `dokploy-traefik` swarm service

### Task 8: Write the Traefik wildcard cert fragment

**Files:**
- Create: `deploys/bootstrap/dokploy-traefik/dynamic/wildcard-local.yml`

- [ ] **Step 1: Write the fragment**

Create `deploys/bootstrap/dokploy-traefik/dynamic/wildcard-local.yml`:

```yaml
# Traefik file-provider fragment.
# Registers the *.local.kodeme.io wildcard as the DEFAULT certificate —
# any route without an explicit cert resolver uses it.
# Paths are inside the Traefik container; host /etc/dokploy/traefik is
# bind-mounted at /etc/traefik (read-only) by deploys/bootstrap/dokploy-traefik/docker-compose.yml.
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

- [ ] **Step 2: Install to the live dynamic dir**

Run:
```bash
sudo install -m 0644 \
  deploys/bootstrap/dokploy-traefik/dynamic/wildcard-local.yml \
  /etc/dokploy/traefik/dynamic/wildcard-local.yml
```

- [ ] **Step 3: Commit**

```bash
git add deploys/bootstrap/dokploy-traefik/dynamic/wildcard-local.yml
git commit -m "feat(deploys): add Traefik wildcard-local.yml (serves *.local.kodeme.io)"
```

---

### Task 9: Write the `dokploy-traefik` swarm compose file

**Files:**
- Create: `deploys/bootstrap/dokploy-traefik/docker-compose.yml`

- [ ] **Step 1: Write the compose file**

Create `deploys/bootstrap/dokploy-traefik/docker-compose.yml`:

```yaml
# Dokploy Traefik — reclaims :80/:443 for local Dokploy routing.
# Deploy with:
#   docker stack deploy -c deploys/bootstrap/dokploy-traefik/docker-compose.yml dokploy
# (Running inside the existing `dokploy` stack so it joins dokploy-network.)

version: "3.9"

services:
  dokploy-traefik:
    image: traefik:v3.2
    networks:
      - dokploy-network
    ports:
      - target: 80
        published: 80
        mode: host
      - target: 443
        published: 443
        mode: host
    volumes:
      - /etc/dokploy/traefik:/etc/traefik:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints:
          - node.role == manager
      restart_policy:
        condition: any
      update_config:
        order: start-first
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://127.0.0.1:8080/ping", "||", "exit", "1"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 15s

networks:
  dokploy-network:
    external: true
```

- [ ] **Step 2: Deploy the stack**

Run:
```bash
docker stack deploy -c deploys/bootstrap/dokploy-traefik/docker-compose.yml dokploy
```

Expected: `Creating service dokploy_dokploy-traefik` (or `Updating` if a prior attempt left state). Name in `docker service ls`: `dokploy_dokploy-traefik`.

- [ ] **Step 3: Verify the service is running**

Run:
```bash
until [ "$(docker service ls --filter name=dokploy_dokploy-traefik --format '{{.Replicas}}')" = "1/1" ]; do sleep 2; done && echo OK
```

Expected: prints `OK` within ~30s.

- [ ] **Step 4: Verify :80 and :443 are now held by Traefik**

Run: `sudo ss -ltnp '( sport = :80 or sport = :443 )'`
Expected: listeners traced (via Docker) to `traefik` container.

- [ ] **Step 5: Commit**

```bash
git add deploys/bootstrap/dokploy-traefik/docker-compose.yml
git commit -m "feat(deploys): add dokploy-traefik swarm stack (:80/:443)"
```

---

### Task 10: Smoke-test the wildcard via an unknown host

**Files:** none (verification)

- [ ] **Step 1: Hit an unconfigured host**

Run:
```bash
curl -vk --resolve "nothing.local.kodeme.io:443:127.0.0.1" https://nothing.local.kodeme.io/ 2>&1 | grep -E '^\* |^< HTTP' | head
```

Expected:
- TLS handshake succeeds.
- Server cert is issued by Let's Encrypt with CN `*.local.kodeme.io` (`* subject: CN=*.local.kodeme.io`).
- HTTP status `404 Not Found` (Traefik default — no route matches, but TLS was terminated OK).

- [ ] **Step 2: Confirm via real DNS (tests the Cloudflare record too)**

Run: `curl -sIk https://nothing.local.kodeme.io/ | head -1`
Expected: `HTTP/2 404` (or `HTTP/1.1 404 Not Found`). No `curl` cert warning.

- [ ] **Step 3: Commit — none**

---

### Task 11: Write the bootstrap runbook

**Files:**
- Create: `deploys/bootstrap/dokploy-traefik/README.md`

- [ ] **Step 1: Write the runbook**

Create `deploys/bootstrap/dokploy-traefik/README.md`:

````markdown
# dokploy-traefik — local domains bootstrap

One-time setup to enable `https://<service>.local.kodeme.io` on this workstation.
Follow the spec: `docs/superpowers/specs/2026-04-18-dokploy-local-domains-design.md`.

## Prerequisites

- Ports 80 and 443 free on the host. If the `fm_global-nginx-proxy` container is
  holding them: `docker compose -f /home/tgunawan/frappe/services/docker-compose.yml down`.
- Cloudflare zone `kodeme.io` accessible to your `kctl-cf` profile.
- A scoped Cloudflare API token with `Zone.DNS:Edit` + `Zone:Read` on `kodeme.io`.

## Install (run once)

```bash
# 1. Stash the CF token (never committed)
sudo install -d -m 0700 /etc/dokploy/traefik
echo 'CF_DNS_API_TOKEN=<paste-token>' | sudo tee /etc/dokploy/traefik/lego.env
sudo chmod 0600 /etc/dokploy/traefik/lego.env

# 2. Create wildcard DNS records (LAN IP → A records)
LAN_IP=$(ip -4 -o route get 1 | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}')
kctl-cf -p kodemeio dns create --zone kodeme.io --type A --name '*.local' --content "$LAN_IP" --proxied=false --ttl 60
kctl-cf -p kodemeio dns create --zone kodeme.io --type A --name 'local'   --content "$LAN_IP" --proxied=false --ttl 60

# 3. Install lego
LEGO_VERSION=v4.19.2
curl -sSL "https://github.com/go-acme/lego/releases/download/${LEGO_VERSION}/lego_${LEGO_VERSION}_linux_amd64.tar.gz" \
  | sudo tar -xz -C /usr/local/bin lego
sudo chmod 0755 /usr/local/bin/lego

# 4. Install renewal wrapper + systemd units
sudo install -m 0755 dokploy-cert-renew.sh /usr/local/bin/
sudo install -m 0644 dokploy-cert-renew.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dokploy-cert-renew.timer

# 5. Bootstrap the cert (first issuance)
sudo systemctl start dokploy-cert-renew.service
sudo journalctl -u dokploy-cert-renew.service -n 20 --no-pager   # expect "Cert rotated"

# 6. Drop Traefik dynamic config
sudo install -m 0644 dynamic/wildcard-local.yml /etc/dokploy/traefik/dynamic/

# 7. Deploy the Traefik swarm service
docker stack deploy -c docker-compose.yml dokploy
```

## Verify

```bash
# Port ownership
sudo ss -ltnp '( sport = :80 or sport = :443 )'   # Traefik container

# Cert
sudo openssl x509 -in /etc/dokploy/traefik/dynamic/certs/local.kodeme.io/fullchain.pem -noout -subject -enddate

# Unknown host → Traefik 404 with valid cert
curl -sIk https://nothing.local.kodeme.io/ | head -1   # HTTP/2 404
```

## Rotate the CF token

1. Mint new token in Cloudflare dashboard.
2. `sudo sed -i "s/^CF_DNS_API_TOKEN=.*/CF_DNS_API_TOKEN=<new-token>/" /etc/dokploy/traefik/lego.env`
3. Revoke the old token on Cloudflare.

## LAN IP changed

```bash
NEW_IP=$(ip -4 -o route get 1 | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}')
kctl-cf -p kodemeio dns update --zone kodeme.io --name '*.local.kodeme.io' --content "$NEW_IP"
kctl-cf -p kodemeio dns update --zone kodeme.io --name 'local.kodeme.io'   --content "$NEW_IP"
```

(Or just run `kctl-dokploy deploy apply-local <any-local-manifest>` — it reconciles DNS automatically.)

## Rollback

```bash
# Stop Traefik
docker service rm dokploy_dokploy-traefik

# Bring Frappe nginx-proxy back (if truly needed)
docker compose -f /home/tgunawan/frappe/services/docker-compose.yml up -d
```
````

- [ ] **Step 2: Commit**

```bash
git add deploys/bootstrap/dokploy-traefik/README.md
git commit -m "docs(deploys): add dokploy-traefik bootstrap runbook"
```

---

## Phase 4 — Reconciler (TDD)

### Task 12: `lan_ip.py` — detect current LAN IP

**Files:**
- Create: `packages/kctl-dokploy/src/kctl_dokploy/core/lan_ip.py`
- Create: `packages/kctl-dokploy/tests/core/test_lan_ip.py`

- [ ] **Step 1: Write the failing test**

Create `packages/kctl-dokploy/tests/core/test_lan_ip.py`:

```python
"""Unit tests for lan_ip module."""

from __future__ import annotations

from ipaddress import IPv4Address
from unittest.mock import patch

import pytest

from kctl_dokploy.core.lan_ip import current_lan_ipv4, is_private_ipv4


def test_is_private_ipv4_accepts_rfc1918() -> None:
    assert is_private_ipv4("192.168.1.5") is True
    assert is_private_ipv4("10.0.0.4") is True
    assert is_private_ipv4("172.16.5.7") is True


def test_is_private_ipv4_rejects_public_and_loopback() -> None:
    assert is_private_ipv4("8.8.8.8") is False
    assert is_private_ipv4("127.0.0.1") is False
    assert is_private_ipv4("169.254.1.1") is False   # link-local


def test_current_lan_ipv4_parses_ip_route_get() -> None:
    # Simulates: `ip -4 -o route get 1.1.1.1` output
    fake_out = "1.1.1.1 via 192.168.1.1 dev wlp0s20f3 src 192.168.1.5 uid 1000 \n   cache\n"
    with patch("kctl_dokploy.core.lan_ip._run_ip_route", return_value=fake_out):
        assert current_lan_ipv4() == IPv4Address("192.168.1.5")


def test_current_lan_ipv4_raises_when_no_src() -> None:
    with patch("kctl_dokploy.core.lan_ip._run_ip_route", return_value="no route"):
        with pytest.raises(RuntimeError, match="Could not determine LAN IP"):
            current_lan_ipv4()
```

- [ ] **Step 2: Run — verify it fails with ImportError**

Run:
```bash
cd packages/kctl-dokploy
uv run pytest tests/core/test_lan_ip.py -v
```

Expected: `ModuleNotFoundError: No module named 'kctl_dokploy.core.lan_ip'`.

- [ ] **Step 3: Implement the minimal module**

Create `packages/kctl-dokploy/src/kctl_dokploy/core/lan_ip.py`:

```python
"""Determine the workstation's current LAN IPv4.

Used by the local-domains reconciler to compare declared vs live Cloudflare
A records for `*.local.kodeme.io`.
"""

from __future__ import annotations

import ipaddress
import re
import subprocess
from ipaddress import IPv4Address

__all__ = ["current_lan_ipv4", "is_private_ipv4"]

_SRC_RE = re.compile(r"\bsrc\s+(\d+\.\d+\.\d+\.\d+)\b")


def is_private_ipv4(addr: str) -> bool:
    """Return True if `addr` is in RFC1918 space (10/8, 172.16/12, 192.168/16)."""
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return isinstance(ip, IPv4Address) and ip.is_private and not ip.is_loopback and not ip.is_link_local


def _run_ip_route() -> str:
    """Return stdout of `ip -4 -o route get 1.1.1.1`."""
    return subprocess.run(
        ["ip", "-4", "-o", "route", "get", "1.1.1.1"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def current_lan_ipv4() -> IPv4Address:
    """Return the workstation's outbound-facing IPv4 (the `src` address in the default route)."""
    out = _run_ip_route()
    m = _SRC_RE.search(out)
    if not m:
        raise RuntimeError(f"Could not determine LAN IP from `ip route get` output: {out!r}")
    return IPv4Address(m.group(1))
```

- [ ] **Step 4: Run — verify it passes**

Run: `uv run pytest tests/core/test_lan_ip.py -v`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/core/lan_ip.py \
        packages/kctl-dokploy/tests/core/test_lan_ip.py
git commit -m "feat(kctl-dokploy): add lan_ip module for LAN IPv4 detection"
```

---

### Task 13: `LocalReconciler` — DNS reconcile (first behavior)

**Files:**
- Create: `packages/kctl-dokploy/src/kctl_dokploy/core/local_reconciler.py`
- Create: `packages/kctl-dokploy/tests/core/test_local_reconciler.py`

- [ ] **Step 1: Write the failing test (DNS drift detection + update)**

Create `packages/kctl-dokploy/tests/core/test_local_reconciler.py`:

```python
"""Unit tests for LocalReconciler.

All external calls (Cloudflare, Dokploy API, filesystem) are mocked.
Tests only exercise pure logic + wiring.
"""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address
from unittest.mock import MagicMock

import pytest

from kctl_dokploy.core.local_reconciler import (
    LocalReconciler,
    ReconcileResult,
)


@dataclass
class _StubDnsAdapter:
    """In-memory DNS: name -> content."""

    records: dict[str, str]

    def get(self, zone: str, name: str) -> str | None:
        return self.records.get(name)

    def update(self, zone: str, name: str, content: str) -> None:
        self.records[name] = content


def test_reconcile_dns_no_drift_is_noop() -> None:
    dns = _StubDnsAdapter(
        records={"*.local.kodeme.io": "192.168.1.5", "local.kodeme.io": "192.168.1.5"}
    )
    r = LocalReconciler(
        dns=dns,
        dokploy=MagicMock(),
        lan_ip_getter=lambda: IPv4Address("192.168.1.5"),
        zone="kodeme.io",
    )
    result = r.reconcile_dns()
    assert result.changed is False
    assert "*.local.kodeme.io" in result.inspected
    assert dns.records["*.local.kodeme.io"] == "192.168.1.5"


def test_reconcile_dns_drift_triggers_update() -> None:
    dns = _StubDnsAdapter(
        records={"*.local.kodeme.io": "192.168.1.10", "local.kodeme.io": "192.168.1.10"}
    )
    r = LocalReconciler(
        dns=dns,
        dokploy=MagicMock(),
        lan_ip_getter=lambda: IPv4Address("192.168.1.5"),
        zone="kodeme.io",
    )
    result = r.reconcile_dns()
    assert result.changed is True
    assert dns.records["*.local.kodeme.io"] == "192.168.1.5"
    assert dns.records["local.kodeme.io"] == "192.168.1.5"


def test_reconcile_dns_raises_when_lan_ip_is_public() -> None:
    r = LocalReconciler(
        dns=_StubDnsAdapter(records={}),
        dokploy=MagicMock(),
        lan_ip_getter=lambda: IPv4Address("8.8.8.8"),
        zone="kodeme.io",
    )
    with pytest.raises(ValueError, match="not RFC1918"):
        r.reconcile_dns()
```

- [ ] **Step 2: Run — verify it fails**

Run: `uv run pytest tests/core/test_local_reconciler.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement minimal `LocalReconciler` with only `reconcile_dns`**

Create `packages/kctl-dokploy/src/kctl_dokploy/core/local_reconciler.py`:

```python
"""Reconciler for `kctl-dokploy deploy apply-local`.

Given a DeployManifest targeting local infra, converge:
  1. Cloudflare wildcard A records (*.local.kodeme.io, local.kodeme.io) → workstation LAN IP.
  2. Dokploy project, environment, compose service (via existing deploy_ops).
  3. Dokploy env file push.
  4. Dokploy domain attachment.

External dependencies are injected for testability (DNS adapter, Dokploy client,
LAN IP getter).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from ipaddress import IPv4Address
from typing import Callable, Protocol

from kctl_dokploy.core.lan_ip import is_private_ipv4


class DnsAdapter(Protocol):
    def get(self, zone: str, name: str) -> str | None: ...
    def update(self, zone: str, name: str, content: str) -> None: ...


@dataclass
class ReconcileResult:
    """Outcome of a reconcile step — used to decide whether to trigger a redeploy."""

    changed: bool = False
    inspected: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)


@dataclass
class LocalReconciler:
    dns: DnsAdapter
    dokploy: object   # Dokploy HTTP client; broadened in later tasks.
    lan_ip_getter: Callable[[], IPv4Address]
    zone: str = "kodeme.io"

    WILDCARD_NAME = "*.local.kodeme.io"
    APEX_NAME = "local.kodeme.io"

    def reconcile_dns(self) -> ReconcileResult:
        """Ensure Cloudflare wildcard + apex A records match the current LAN IP."""
        result = ReconcileResult()
        lan_ip = self.lan_ip_getter()
        if not is_private_ipv4(str(lan_ip)):
            raise ValueError(f"Current LAN IP {lan_ip} is not RFC1918; refusing to publish.")

        for name in (self.WILDCARD_NAME, self.APEX_NAME):
            result.inspected.append(name)
            live = self.dns.get(self.zone, name)
            if live != str(lan_ip):
                self.dns.update(self.zone, name, str(lan_ip))
                result.changed = True
                result.messages.append(f"{name}: {live!r} → {lan_ip}")

        return result
```

- [ ] **Step 4: Run — verify it passes**

Run: `uv run pytest tests/core/test_local_reconciler.py -v`
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/core/local_reconciler.py \
        packages/kctl-dokploy/tests/core/test_local_reconciler.py
git commit -m "feat(kctl-dokploy): LocalReconciler with DNS reconcile step"
```

---

### Task 14: `LocalReconciler.reconcile_domain` — Dokploy domain attachment

**Files:**
- Modify: `packages/kctl-dokploy/src/kctl_dokploy/core/local_reconciler.py` (add method)
- Modify: `packages/kctl-dokploy/tests/core/test_local_reconciler.py` (add tests)

- [ ] **Step 1: Write the failing test**

Append to `packages/kctl-dokploy/tests/core/test_local_reconciler.py`:

```python
from dataclasses import dataclass as _dc


@_dc
class _StubDokployDomains:
    """In-memory domain store: compose_id -> list[dict]."""

    store: dict[str, list[dict]]
    created: list[dict]

    def list_for_compose(self, compose_id: str) -> list[dict]:
        return list(self.store.get(compose_id, []))

    def create(self, compose_id: str, **spec: object) -> None:
        self.store.setdefault(compose_id, []).append({"composeId": compose_id, **spec})
        self.created.append({"composeId": compose_id, **spec})

    def update(self, domain_id: str, **spec: object) -> None:  # pragma: no cover - unused in this task
        raise NotImplementedError


def test_reconcile_domain_creates_missing_domain() -> None:
    domains = _StubDokployDomains(store={}, created=[])
    r = LocalReconciler(
        dns=_StubDnsAdapter(records={}),
        dokploy=MagicMock(domains=domains),
        lan_ip_getter=lambda: IPv4Address("192.168.1.5"),
        zone="kodeme.io",
    )
    result = r.reconcile_domain(
        compose_id="cmp_abc",
        host="dbgate.local.kodeme.io",
        port=3000,
        service="dbgate",
    )
    assert result.changed is True
    assert domains.created == [
        {
            "composeId": "cmp_abc",
            "host": "dbgate.local.kodeme.io",
            "port": 3000,
            "service_name": "dbgate",
            "https": True,
            "cert_type": "none",
        }
    ]


def test_reconcile_domain_noop_when_exact_match_exists() -> None:
    domains = _StubDokployDomains(
        store={
            "cmp_abc": [
                {
                    "composeId": "cmp_abc",
                    "host": "dbgate.local.kodeme.io",
                    "port": 3000,
                    "service_name": "dbgate",
                    "https": True,
                    "cert_type": "none",
                }
            ]
        },
        created=[],
    )
    r = LocalReconciler(
        dns=_StubDnsAdapter(records={}),
        dokploy=MagicMock(domains=domains),
        lan_ip_getter=lambda: IPv4Address("192.168.1.5"),
        zone="kodeme.io",
    )
    result = r.reconcile_domain(
        compose_id="cmp_abc",
        host="dbgate.local.kodeme.io",
        port=3000,
        service="dbgate",
    )
    assert result.changed is False
    assert domains.created == []


def test_reconcile_domain_rejects_non_local_host() -> None:
    r = LocalReconciler(
        dns=_StubDnsAdapter(records={}),
        dokploy=MagicMock(),
        lan_ip_getter=lambda: IPv4Address("192.168.1.5"),
        zone="kodeme.io",
    )
    with pytest.raises(ValueError, match="must end with .local.kodeme.io"):
        r.reconcile_domain(
            compose_id="cmp_abc",
            host="dbgate.kodeme.io",   # missing ".local"
            port=3000,
            service="dbgate",
        )
```

- [ ] **Step 2: Run — verify new tests fail**

Run: `uv run pytest tests/core/test_local_reconciler.py -v`
Expected: 3 existing tests pass + 3 new tests fail with `AttributeError: 'LocalReconciler' object has no attribute 'reconcile_domain'`.

- [ ] **Step 3: Implement `reconcile_domain`**

Append to `packages/kctl-dokploy/src/kctl_dokploy/core/local_reconciler.py`:

```python
    _LOCAL_SUFFIX = ".local.kodeme.io"

    def reconcile_domain(
        self,
        compose_id: str,
        host: str,
        port: int,
        service: str,
    ) -> ReconcileResult:
        """Ensure a Dokploy domain with the given spec is attached to the compose service.

        Uses cert_type='none' so Traefik falls back to the default cert store
        (populated by wildcard-local.yml → our *.local.kodeme.io cert).
        """
        if not host.endswith(self._LOCAL_SUFFIX):
            raise ValueError(f"host {host!r} must end with {self._LOCAL_SUFFIX}")

        spec = dict(
            host=host,
            port=port,
            service_name=service,
            https=True,
            cert_type="none",
        )
        existing = self.dokploy.domains.list_for_compose(compose_id)  # type: ignore[attr-defined]
        for d in existing:
            if all(d.get(k) == v for k, v in spec.items()):
                return ReconcileResult(changed=False, inspected=[host])

        self.dokploy.domains.create(compose_id=compose_id, **spec)  # type: ignore[attr-defined]
        return ReconcileResult(changed=True, inspected=[host], messages=[f"domain created: {host}"])
```

- [ ] **Step 4: Run — verify all tests pass**

Run: `uv run pytest tests/core/test_local_reconciler.py -v`
Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/core/local_reconciler.py \
        packages/kctl-dokploy/tests/core/test_local_reconciler.py
git commit -m "feat(kctl-dokploy): LocalReconciler.reconcile_domain attaches Dokploy domain"
```

---

### Task 15: `LocalReconciler.apply` — end-to-end manifest application

**Files:**
- Modify: `packages/kctl-dokploy/src/kctl_dokploy/core/local_reconciler.py`
- Modify: `packages/kctl-dokploy/tests/core/test_local_reconciler.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/kctl-dokploy/tests/core/test_local_reconciler.py`:

```python
from pathlib import Path

from kctl_dokploy.core.manifest import DeployManifest


def _load_dbgate_manifest(tmp_path: Path) -> DeployManifest:
    p = tmp_path / "kod-infra-dbgate.yaml"
    p.write_text(
        """
kind: instance
project: application
environment: local
server: vbox-ubuntu-server
instance:
  name: kod-infra-dbgate
  description: DBGate
source_overrides:
  type: github
  owner: tgunawandev
  repo: kodemeio-dbgate
  branch: main
  compose_path: ./docker-compose.prod.yml
domain:
  host: dbgate.local.kodeme.io
  port: 3000
  service: dbgate
  https: true
env_file: ../../env/local/.env.kod-infra-dbgate
""".strip()
    )
    return DeployManifest.from_yaml(p)


def test_apply_dispatches_dns_compose_env_and_domain(tmp_path: Path) -> None:
    manifest = _load_dbgate_manifest(tmp_path)

    dns = _StubDnsAdapter(records={"*.local.kodeme.io": "192.168.1.5", "local.kodeme.io": "192.168.1.5"})
    domains = _StubDokployDomains(store={}, created=[])
    dokploy = MagicMock()
    dokploy.domains = domains
    # Stub out compose ensure/env push — they return a dict with {"changed": bool, "compose_id": str}
    dokploy.ensure_compose.return_value = {"changed": True, "compose_id": "cmp_dbgate"}
    dokploy.push_env.return_value = {"changed": False}

    r = LocalReconciler(
        dns=dns,
        dokploy=dokploy,
        lan_ip_getter=lambda: IPv4Address("192.168.1.5"),
        zone="kodeme.io",
    )
    outcome = r.apply(manifest)

    # Ordering: DNS, then compose, then env, then domain
    assert dokploy.ensure_compose.call_count == 1
    assert dokploy.push_env.call_count == 1
    # Domain was created (none existed before)
    assert len(domains.created) == 1
    # Overall changed because compose + domain changed
    assert outcome.changed is True
```

- [ ] **Step 2: Run — verify it fails**

Run: `uv run pytest tests/core/test_local_reconciler.py::test_apply_dispatches_dns_compose_env_and_domain -v`
Expected: `AttributeError: 'LocalReconciler' object has no attribute 'apply'`.

- [ ] **Step 3: Implement `apply`**

Append to `packages/kctl-dokploy/src/kctl_dokploy/core/local_reconciler.py`:

```python
    def apply(self, manifest: "DeployManifest") -> ReconcileResult:   # noqa: F821
        """Converge all resources declared by `manifest`.

        Steps (in order):
          1. reconcile_dns — wildcard CF records point to current LAN IP.
          2. ensure_compose — project + environment + compose service exist with manifest's source config.
          3. push_env — env_file content mirrored to the compose service.
          4. reconcile_domain — Dokploy domain attached with cert_type=none.
        """
        from kctl_dokploy.core.manifest import DeployManifest as _DM  # local import to avoid cycles

        assert isinstance(manifest, _DM), f"expected DeployManifest, got {type(manifest).__name__}"
        if manifest.environment != "local":
            raise ValueError(f"apply() refuses non-local manifest (environment={manifest.environment!r})")

        overall = ReconcileResult()

        dns_r = self.reconcile_dns()
        overall.changed |= dns_r.changed
        overall.messages.extend(dns_r.messages)

        compose = self.dokploy.ensure_compose(manifest)          # type: ignore[attr-defined]
        overall.changed |= bool(compose.get("changed"))
        compose_id: str = compose["compose_id"]

        env = self.dokploy.push_env(compose_id, manifest.env_file)   # type: ignore[attr-defined]
        overall.changed |= bool(env.get("changed"))

        if manifest.domain is not None:
            dom_r = self.reconcile_domain(
                compose_id=compose_id,
                host=manifest.domain.host,
                port=manifest.domain.port,
                service=manifest.domain.service,
            )
            overall.changed |= dom_r.changed
            overall.messages.extend(dom_r.messages)

        return overall
```

**Note:** `DeployManifest.from_yaml` may not exist yet in `core/manifest.py`. If the test in Step 1 fails with `AttributeError: type object 'DeployManifest' has no attribute 'from_yaml'`, add a thin `@classmethod from_yaml(cls, path: Path)` that reads the file with PyYAML and validates via `cls.model_validate(data)`. Do this minimally; extensive manifest loading is not in scope for this plan — inspect `core/manifest.py` first to see how existing `deploy apply` loads manifests and reuse that entry point instead if it exists.

- [ ] **Step 4: Run — verify all tests pass**

Run: `uv run pytest tests/core/test_local_reconciler.py -v`
Expected: `7 passed`.

- [ ] **Step 5: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/core/local_reconciler.py \
        packages/kctl-dokploy/tests/core/test_local_reconciler.py
git commit -m "feat(kctl-dokploy): LocalReconciler.apply — end-to-end manifest reconcile"
```

---

### Task 16: Cloudflare DNS adapter (thin wrapper over `kctl-cf`)

**Files:**
- Modify: `packages/kctl-dokploy/src/kctl_dokploy/core/local_reconciler.py` (add adapter class)
- Modify: `packages/kctl-dokploy/tests/core/test_local_reconciler.py` (add subprocess-based integration test behind a marker)

- [ ] **Step 1: Write the failing test (mocks `subprocess.run`)**

Append to `packages/kctl-dokploy/tests/core/test_local_reconciler.py`:

```python
from unittest.mock import patch, MagicMock as _MM
import json as _json

from kctl_dokploy.core.local_reconciler import KctlCfDnsAdapter


def test_kctlcf_adapter_get_returns_content() -> None:
    # Simulate `kctl-cf --json dns get --zone kodeme.io --name '*.local.kodeme.io'` → JSON
    fake_proc = _MM(returncode=0, stdout=_json.dumps({"name": "*.local.kodeme.io", "content": "192.168.1.5"}))
    with patch("kctl_dokploy.core.local_reconciler.subprocess.run", return_value=fake_proc):
        adapter = KctlCfDnsAdapter(profile="kodemeio")
        assert adapter.get("kodeme.io", "*.local.kodeme.io") == "192.168.1.5"


def test_kctlcf_adapter_get_returns_none_when_absent() -> None:
    fake_proc = _MM(returncode=1, stdout="", stderr="Record not found")
    with patch("kctl_dokploy.core.local_reconciler.subprocess.run", return_value=fake_proc):
        adapter = KctlCfDnsAdapter(profile="kodemeio")
        assert adapter.get("kodeme.io", "*.local.kodeme.io") is None


def test_kctlcf_adapter_update_invokes_kctl_cf_dns_update() -> None:
    fake_proc = _MM(returncode=0, stdout="OK", stderr="")
    with patch("kctl_dokploy.core.local_reconciler.subprocess.run", return_value=fake_proc) as run_mock:
        adapter = KctlCfDnsAdapter(profile="kodemeio")
        adapter.update("kodeme.io", "*.local.kodeme.io", "192.168.1.6")
        args = run_mock.call_args.args[0]
        assert args[:4] == ["kctl-cf", "-p", "kodemeio", "dns"]
        assert "update" in args
        assert "--content" in args and "192.168.1.6" in args
```

- [ ] **Step 2: Run — verify it fails**

Run: `uv run pytest tests/core/test_local_reconciler.py -v -k kctlcf`
Expected: `ImportError: cannot import name 'KctlCfDnsAdapter'`.

- [ ] **Step 3: Implement the adapter**

Append to `packages/kctl-dokploy/src/kctl_dokploy/core/local_reconciler.py`:

```python
import json
import subprocess


@dataclass
class KctlCfDnsAdapter:
    """DnsAdapter backed by the `kctl-cf` CLI (shells out)."""

    profile: str = "kodemeio"
    zone_fallback: str = "kodeme.io"

    def get(self, zone: str, name: str) -> str | None:
        proc = subprocess.run(
            ["kctl-cf", "-p", self.profile, "--json", "dns", "get",
             "--zone", zone, "--name", name],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return None
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return None
        return str(data.get("content")) if data.get("content") else None

    def update(self, zone: str, name: str, content: str) -> None:
        subprocess.run(
            ["kctl-cf", "-p", self.profile, "dns", "update",
             "--zone", zone, "--name", name, "--content", content],
            check=True,
            capture_output=True,
            text=True,
        )
```

- [ ] **Step 4: Run — verify passes**

Run: `uv run pytest tests/core/test_local_reconciler.py -v`
Expected: `10 passed`.

**Note on `kctl-cf` flag fidelity:** If `kctl-cf dns get/update` flag names differ from what's used here (e.g., `--name` is called `--record-name`), correct both the implementation and the assertions in lockstep. Run `kctl-cf dns get --help` once during development to confirm.

- [ ] **Step 5: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/core/local_reconciler.py \
        packages/kctl-dokploy/tests/core/test_local_reconciler.py
git commit -m "feat(kctl-dokploy): KctlCfDnsAdapter shells out to kctl-cf for DNS ops"
```

---

### Task 17: Dokploy ops adapter (thin wrapper around existing `kctl-dokploy` internals)

**Files:**
- Modify: `packages/kctl-dokploy/src/kctl_dokploy/core/local_reconciler.py`
- Modify: `packages/kctl-dokploy/tests/core/test_local_reconciler.py`

**Design note:** Inspect `core/deploy_ops.py` first. The existing `deploy apply` flow already has helpers for creating/updating compose services + pushing env files. This task adds a thin `LocalDokployAdapter` that calls those helpers and exposes `ensure_compose(manifest)`, `push_env(compose_id, env_file_path)`, and a `domains` attribute with `list_for_compose/create/update`. Reuse, don't reimplement.

- [ ] **Step 1: Write the failing test**

Append to `packages/kctl-dokploy/tests/core/test_local_reconciler.py`:

```python
def test_local_dokploy_adapter_delegates_to_deploy_ops(tmp_path: Path) -> None:
    from kctl_dokploy.core.local_reconciler import LocalDokployAdapter

    env_file = tmp_path / ".env"
    env_file.write_text("FOO=bar\n")

    mock_client = MagicMock()
    with patch("kctl_dokploy.core.local_reconciler.deploy_ops") as ops:
        ops.ensure_project_and_env.return_value = {"environment_id": "env_x"}
        ops.ensure_compose_service.return_value = {"changed": True, "compose_id": "cmp_x"}
        ops.push_env_file.return_value = {"changed": False, "count": 1}

        adapter = LocalDokployAdapter(client=mock_client)

        manifest = MagicMock(
            project="application",
            environment="local",
            instance=MagicMock(name="kod-infra-dbgate"),
            source_overrides=MagicMock(),
            server="vbox-ubuntu-server",
        )
        result = adapter.ensure_compose(manifest)
        assert result == {"changed": True, "compose_id": "cmp_x"}
        ops.ensure_project_and_env.assert_called_once()
        ops.ensure_compose_service.assert_called_once()

        env_result = adapter.push_env("cmp_x", env_file)
        assert env_result == {"changed": False, "count": 1}
        ops.push_env_file.assert_called_once_with(mock_client, "cmp_x", env_file, force=True)
```

- [ ] **Step 2: Run — verify it fails**

Run: `uv run pytest tests/core/test_local_reconciler.py -v -k local_dokploy_adapter`
Expected: `ImportError: cannot import name 'LocalDokployAdapter'`.

- [ ] **Step 3: Implement the adapter**

Before writing code, inspect the real function names:
```bash
grep -n "^def \|^class " packages/kctl-dokploy/src/kctl_dokploy/core/deploy_ops.py | head -20
```

If function names differ (e.g., `ensure_project_and_env` doesn't exist), adjust the adapter and tests together. Document any rename here in a `# XXX(local-domains): was {old_name} in Task 17` comment so it's traceable.

Append to `packages/kctl-dokploy/src/kctl_dokploy/core/local_reconciler.py`:

```python
from kctl_dokploy.core import deploy_ops


class _DomainsAdapter:
    """Sub-adapter exposed at `adapter.domains.*`."""

    def __init__(self, client: object) -> None:
        self._client = client

    def list_for_compose(self, compose_id: str) -> list[dict]:
        return deploy_ops.list_domains_for_compose(self._client, compose_id)   # type: ignore[attr-defined]

    def create(self, *, compose_id: str, **spec: object) -> None:
        deploy_ops.create_domain(self._client, compose_id=compose_id, **spec)   # type: ignore[attr-defined]

    def update(self, domain_id: str, **spec: object) -> None:
        deploy_ops.update_domain(self._client, domain_id=domain_id, **spec)   # type: ignore[attr-defined]


@dataclass
class LocalDokployAdapter:
    """Dokploy side of the reconciler — wraps existing deploy_ops helpers."""

    client: object

    def __post_init__(self) -> None:
        self.domains = _DomainsAdapter(self.client)

    def ensure_compose(self, manifest: "DeployManifest") -> dict:   # noqa: F821
        env_info = deploy_ops.ensure_project_and_env(self.client, manifest)
        return deploy_ops.ensure_compose_service(self.client, manifest, env_info)

    def push_env(self, compose_id: str, env_file_path) -> dict:   # noqa: ANN001
        return deploy_ops.push_env_file(self.client, compose_id, env_file_path, force=True)
```

If `deploy_ops` doesn't expose these exact functions, add them **inside `deploy_ops`** (they already exist in the production `deploy apply` flow, just possibly as private helpers; promote to module-level if needed) rather than duplicating logic in the adapter.

- [ ] **Step 4: Run — verify passes**

Run: `uv run pytest tests/core/test_local_reconciler.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/core/local_reconciler.py \
        packages/kctl-dokploy/tests/core/test_local_reconciler.py
# If deploy_ops.py was modified:
# git add packages/kctl-dokploy/src/kctl_dokploy/core/deploy_ops.py
git commit -m "feat(kctl-dokploy): LocalDokployAdapter bridges reconciler to deploy_ops"
```

---

### Task 18: Wire `deploy apply-local` CLI command

**Files:**
- Modify: `packages/kctl-dokploy/src/kctl_dokploy/commands/deploy.py`

- [ ] **Step 1: Add the command to `deploy.py`**

After the existing `apply` command in `packages/kctl-dokploy/src/kctl_dokploy/commands/deploy.py`, append:

```python
@app.command(name="apply-local")
def apply_local(
    ctx: typer.Context,
    file: Path = typer.Option(..., "-f", "--file", help="Local instance manifest (deploys/instances/local/*.yaml)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would change without applying"),
) -> None:
    """Apply a local-only instance manifest.

    Converges:
      1. Cloudflare wildcard DNS records → current LAN IP
      2. Dokploy project/env/compose exists with manifest's source config
      3. env_file pushed
      4. Dokploy domain attached with cert_type=none
    """
    from kctl_dokploy.core.lan_ip import current_lan_ipv4
    from kctl_dokploy.core.local_reconciler import (
        KctlCfDnsAdapter,
        LocalDokployAdapter,
        LocalReconciler,
    )

    c: AppContext = ctx.obj
    manifest = _load(file, c)

    if manifest.environment != "local":
        c.output.error(f"{file}: environment={manifest.environment!r}, expected 'local'")
        raise typer.Exit(code=2)

    if manifest.domain is None or not manifest.domain.host.endswith(".local.kodeme.io"):
        c.output.error(f"{file}: domain.host must end with '.local.kodeme.io'")
        raise typer.Exit(code=2)

    reconciler = LocalReconciler(
        dns=KctlCfDnsAdapter(profile=c.profile or "kodemeio"),
        dokploy=LocalDokployAdapter(client=c.client),
        lan_ip_getter=current_lan_ipv4,
        zone="kodeme.io",
    )

    if dry_run:
        c.output.info("dry-run: only DNS reconcile is safe to preview; skipping compose/env/domain")
        dns_r = reconciler.reconcile_dns()
        for m in dns_r.messages:
            c.output.info(m)
        c.output.success(f"DNS changed={dns_r.changed}")
        return

    outcome = reconciler.apply(manifest)
    for m in outcome.messages:
        c.output.info(m)
    c.output.success(f"apply-local complete. changed={outcome.changed}")
```

- [ ] **Step 2: Smoke-test the CLI help**

Run: `uv run kctl-dokploy deploy apply-local --help`
Expected: help text showing `-f/--file` and `--dry-run` flags.

- [ ] **Step 3: Dry-run against a stubbed manifest**

Create a throwaway test manifest:
```bash
cat > /tmp/test-local.yaml <<'EOF'
kind: instance
project: application
environment: local
server: vbox-ubuntu-server
instance:
  name: kod-infra-test
  description: throwaway
source_overrides:
  type: github
  owner: tgunawandev
  repo: kodemeio-dbgate
  branch: main
  compose_path: ./docker-compose.yml
domain:
  host: test.local.kodeme.io
  port: 3000
  service: dbgate
  https: true
env_file: /dev/null
EOF
kctl-dokploy -p local deploy apply-local -f /tmp/test-local.yaml --dry-run
```

Expected: "DNS changed=False" (your wildcard records already match your LAN IP from Phase 2). No Dokploy mutations.

- [ ] **Step 4: Reject a non-local manifest**

Run:
```bash
kctl-dokploy -p local deploy apply-local -f deploys/instances/production/kod-infra-authentik.yaml
```

Expected: error "environment='production', expected 'local'", exit code 2. No side effects.

- [ ] **Step 5: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/commands/deploy.py
git commit -m "feat(kctl-dokploy): add 'deploy apply-local' CLI command"
```

---

## Phase 5 — Rewire DBGate

### Task 19: Update DBGate local manifest + env

**Files:**
- Modify: `deploys/instances/local/kod-infra-dbgate.yaml`
- Modify: `deploys/env/local/.env.kod-infra-dbgate`

- [ ] **Step 1: Update the instance manifest**

Edit `deploys/instances/local/kod-infra-dbgate.yaml` to match:

```yaml
kind: instance
extends: ../../bases/infra.yaml

instance:
  name: kod-infra-dbgate
  description: "DBGate — local (HTTPS via dokploy-traefik + *.local.kodeme.io)"

project: application
environment: local
server: vbox-ubuntu-server

source_overrides:
  type: github
  owner: tgunawandev
  repo: kodemeio-dbgate
  branch: main
  compose_path: ./docker-compose.prod.yml

domain:
  host: dbgate.local.kodeme.io
  port: 3000
  service: dbgate
  https: true

env_file: ../../env/local/.env.kod-infra-dbgate
```

Key changes vs prior: `compose_path` switched from `./docker-compose.yml` to `./docker-compose.prod.yml` (so Traefik labels from prod compose are in play), `domain.host` switched from `localhost`, `domain.port` from 3001 to 3000 (internal container port, no host publish anymore).

- [ ] **Step 2: Update the env file**

Edit `deploys/env/local/.env.kod-infra-dbgate`:
- Set `DOMAIN=dbgate.local.kodeme.io`
- Delete `DBGATE_PORT=3001` (no host publish under prod compose)
- Keep `DBGATE_LOGIN`, `DBGATE_PASSWORD`, `DBGATE_TAG`, `WEB_ROOT`, `CONNECTIONS`, resource limits, `TZ`
- Keep the `TENANT`, `COMPOSE_PROJECT_NAME`, and prod-compose required vars unchanged

- [ ] **Step 3: Validate the manifest parses**

Run:
```bash
kctl-dokploy -p local deploy validate -f deploys/instances/local/kod-infra-dbgate.yaml
```

Expected: `OK: manifest valid`.

- [ ] **Step 4: Commit**

```bash
git add deploys/instances/local/kod-infra-dbgate.yaml deploys/env/local/.env.kod-infra-dbgate
git commit -m "feat(deploys): rewire kod-infra-dbgate to https://dbgate.local.kodeme.io"
```

---

### Task 20: Run `apply-local` on DBGate

**Files:** none (mutates live Dokploy + Cloudflare)

- [ ] **Step 1: Dry-run first**

Run:
```bash
kctl-dokploy -p local deploy apply-local -f deploys/instances/local/kod-infra-dbgate.yaml --dry-run
```

Expected: DNS changed=False. No errors.

- [ ] **Step 2: Apply for real**

Run:
```bash
kctl-dokploy -p local deploy apply-local -f deploys/instances/local/kod-infra-dbgate.yaml
```

Expected log lines (order):
- DNS reconcile: no changes.
- ensure_compose: updates existing compose `BoDZXpCikjbQh2hufIhOJ` with new `compose_path` → changed=True.
- push_env: new `.env.kod-infra-dbgate` uploaded.
- reconcile_domain: domain `dbgate.local.kodeme.io` created (cert_type=none).
- `apply-local complete. changed=True`.

- [ ] **Step 3: Wait for the container to come up**

Run:
```bash
until docker ps --filter 'name=dbgate' --format '{{.Status}}' | grep -q 'healthy'; do sleep 3; done && echo HEALTHY
```

Expected: prints `HEALTHY` within ~90s.

- [ ] **Step 4: Verify HTTPS reachability**

Run:
```bash
curl -sI https://dbgate.local.kodeme.io/ | head -1
openssl s_client -connect dbgate.local.kodeme.io:443 -servername dbgate.local.kodeme.io </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -enddate
```

Expected:
- `HTTP/2 200` or `HTTP/1.1 200 OK`.
- `subject=CN = *.local.kodeme.io`, `notAfter=<~90d out>`.
- No `curl` cert warnings, no `-k`.

- [ ] **Step 5: Verify in a real browser**

Open `https://dbgate.local.kodeme.io` in Chrome/Firefox. Expect a green padlock, DBGate login screen.

- [ ] **Step 6: Commit — none**

State change only.

---

## Phase 6 — Acceptance tests + proof-of-reuse

### Task 21: Smoke test script

**Files:**
- Create: `deploys/tests/local-domains-smoke.sh`

- [ ] **Step 1: Write the script**

Create `deploys/tests/local-domains-smoke.sh`:

```bash
#!/usr/bin/env bash
# Acceptance smoke tests for dokploy-traefik + *.local.kodeme.io.
# Exit code: 0 = all green, 1 = any failure.

set -euo pipefail

PASS=0
FAIL=0

check() {
  local name=$1 result=$2
  if [ "$result" = "0" ]; then
    echo "PASS  $name"
    PASS=$((PASS + 1))
  else
    echo "FAIL  $name"
    FAIL=$((FAIL + 1))
  fi
}

# 1. Traefik service is 1/1
docker service ls --filter name=dokploy_dokploy-traefik --format '{{.Replicas}}' | grep -qx '1/1' && rc=0 || rc=1
check "dokploy-traefik service 1/1" $rc

# 2. Traefik /ping healthy on :80 (inside container via a quick exec)
CID=$(docker ps -q -f name=dokploy_dokploy-traefik | head -1)
if [ -n "$CID" ]; then
  docker exec "$CID" wget -qO- http://127.0.0.1:8080/ping >/dev/null && rc=0 || rc=1
else
  rc=1
fi
check "traefik /ping 200" $rc

# 3. Cert valid for >30 days
DAYS_LEFT=$(sudo openssl x509 -in /etc/dokploy/traefik/dynamic/certs/local.kodeme.io/fullchain.pem \
  -noout -enddate | awk -F= '{print $2}' \
  | xargs -I{} date -d {} +%s \
  | awk -v now="$(date +%s)" '{print int(($1 - now) / 86400)}')
[ "$DAYS_LEFT" -gt 30 ] && rc=0 || rc=1
check "cert valid >30d (actual=${DAYS_LEFT}d)" $rc

# 4. Systemd timer enabled
systemctl is-enabled dokploy-cert-renew.timer >/dev/null 2>&1 && rc=0 || rc=1
check "dokploy-cert-renew.timer enabled" $rc

# 5. Last cert renewal succeeded within 30 days
LAST=$(systemctl show -p ExecMainExitTimestampMonotonic dokploy-cert-renew.service | cut -d= -f2)
[ -n "$LAST" ] && [ "$LAST" != "0" ] && rc=0 || rc=1
check "cert-renew service has run at least once" $rc

# 6. Unknown *.local.kodeme.io host returns Traefik 404 with valid cert
BODY=$(curl -sI https://this-does-not-exist.local.kodeme.io/ 2>&1 | head -1)
echo "$BODY" | grep -qE '404' && rc=0 || rc=1
check "wildcard unknown host → 404 no cert error" $rc

# 7. DBGate responds 200
BODY=$(curl -sI https://dbgate.local.kodeme.io/ | head -1)
echo "$BODY" | grep -qE '200|302' && rc=0 || rc=1
check "dbgate.local.kodeme.io → 200/302" $rc

echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
```

- [ ] **Step 2: Make executable + run**

Run:
```bash
chmod +x deploys/tests/local-domains-smoke.sh
bash deploys/tests/local-domains-smoke.sh
```

Expected: `summary: 7 passed, 0 failed`, exit 0.

- [ ] **Step 3: Commit**

```bash
git add deploys/tests/local-domains-smoke.sh
git commit -m "test(deploys): add local-domains smoke test script"
```

---

### Task 22: Proof of reuse — add a second local service

**Files:**
- Create: `deploys/instances/local/kod-infra-gatus.yaml` (or another small web service of choice)
- Create: `deploys/env/local/.env.kod-infra-gatus`

**Intent:** Prove that adding a new local service costs zero ops work beyond the manifest + env. If the pattern holds, no Cloudflare touch, no systemd touch, no Traefik touch — just `apply-local`.

Suggested target: `gatus` (lightweight health dashboard, single container, already in production at `gatus.kodeme.io`). If gatus is inconvenient, substitute any existing production local service the reader prefers — the verification is the same.

- [ ] **Step 1: Mirror the production gatus manifest for local**

Create `deploys/instances/local/kod-infra-gatus.yaml` by copying from production and adjusting:
- `environment: local`
- `server: vbox-ubuntu-server`
- `domain.host: gatus.local.kodeme.io`
- `source_overrides.compose_path`: keep production compose path if it uses only Traefik labels (no host-port publish); otherwise set to a local-specific variant.
- `env_file: ../../env/local/.env.kod-infra-gatus`

- [ ] **Step 2: Create a local env file with safe test values**

Create `deploys/env/local/.env.kod-infra-gatus`. Set `DOMAIN=gatus.local.kodeme.io`. Use throwaway/test creds for any DB/SMTP/webhook values. Do NOT reuse production secrets.

- [ ] **Step 3: Validate + apply**

Run:
```bash
kctl-dokploy -p local deploy validate -f deploys/instances/local/kod-infra-gatus.yaml
kctl-dokploy -p local deploy apply-local -f deploys/instances/local/kod-infra-gatus.yaml
```

Expected: validation passes; apply-local runs cleanly; `changed=True` (fresh service).

- [ ] **Step 4: Verify**

Run:
```bash
until docker ps --filter 'name=gatus' --format '{{.Status}}' | grep -q 'Up'; do sleep 3; done
curl -sI https://gatus.local.kodeme.io/ | head -1
```

Expected: container up; `HTTP/2 200`. Green padlock in browser.

- [ ] **Step 5: Re-run the smoke test — now with two services**

Append a line to `deploys/tests/local-domains-smoke.sh` after the DBGate check (or parameterize: accept a list of expected hosts via env var). For this plan, hardcode one extra line mirroring check #7 for `gatus.local.kodeme.io`.

Re-run the smoke test. Expected: `summary: 8 passed, 0 failed`.

- [ ] **Step 6: Commit**

```bash
git add deploys/instances/local/kod-infra-gatus.yaml \
        deploys/env/local/.env.kod-infra-gatus \
        deploys/tests/local-domains-smoke.sh
git commit -m "test(deploys): add gatus local instance as proof-of-reuse"
```

---

## Final verification

- [ ] **Step 1: All tests green**

Run:
```bash
cd packages/kctl-dokploy && uv run pytest -q
cd ../.. && bash deploys/tests/local-domains-smoke.sh
```

Expected: Python unit tests pass; smoke test reports `summary: 8 passed, 0 failed`.

- [ ] **Step 2: Mobile PWA sanity check**

On a phone on the same Wi-Fi, open `https://dbgate.local.kodeme.io`. Expected: green padlock, page loads, no cert trust prompt.

- [ ] **Step 3: Cert auto-renew dry-run**

Force a renewal as if the cert were about to expire:
```bash
sudo /usr/local/bin/lego --accept-tos --email tri.gunawan@live.com --dns cloudflare \
  --path /etc/dokploy/traefik/dynamic/certs \
  --domains '*.local.kodeme.io' --domains 'local.kodeme.io' renew --days 9999
sudo /usr/local/bin/dokploy-cert-renew.sh   # re-publishes stable names, forces Traefik update
```

Expected: new cert issued (within LE rate limits), Traefik hot-reloads, `curl https://dbgate.local.kodeme.io` still green, no downtime visible.

- [ ] **Step 4: Push**

```bash
git push
```

- [ ] **Step 5: Mark plan complete**

Update the plan file's status to `Implemented YYYY-MM-DD`.

---

## Plan Self-Review

**Spec coverage check** — matrix of spec § → implementing task:

| Spec section | Implementing task(s) |
|---|---|
| §4 Architecture | Phases 1–3 (ports, certs, Traefik) |
| §5.1 dokploy-traefik swarm service | Task 9 |
| §5.1 wildcard-local.yml | Task 8 |
| §5.2 lego + systemd timer | Tasks 4, 5, 6, 7 |
| §5.3 Cloudflare DNS records | Tasks 2, 3 |
| §5.4 Manifest schema (no new field needed) | Task 19 (usage only — schema is pre-existing) |
| §5.5 Reconciler algorithm | Tasks 12–18 |
| §6 Failure modes / rollback | Runbook in Task 11 |
| §7.1 One-time migration | Tasks 1–11 |
| §7.2 Rewire DBGate | Tasks 19, 20 |
| §7.3 Acceptance tests | Task 21 |
| §7.4 Second consumer | Task 22 |
| §8 Out of scope (future) | Not implemented — captured in spec §8 |
| §9 Affected files | Covered in this plan's "File Structure" |
| §10 Open questions | Defaulted by brainstorming skill: LE email=`tri.gunawan@live.com`, CF token name=`dokploy-local-cert-renew`, apply-local is read-only |

**Placeholder scan:** no `TBD`, `TODO`, `implement later` or similar. Every code step contains the actual code. Commands have expected output. File paths are absolute or explicitly repo-root-relative.

**Type consistency:** `DnsAdapter` protocol (Task 13) is implemented by `KctlCfDnsAdapter` (Task 16) — verified method signatures match (`get(zone, name) -> str | None`, `update(zone, name, content) -> None`). `LocalDokployAdapter.domains` (Task 17) implements the contract used in `reconcile_domain` (Task 14) — `list_for_compose`, `create(compose_id, **spec)`, `update(domain_id, **spec)`. `ReconcileResult.changed: bool` is set in all three reconcile steps (DNS, compose, env, domain) and OR-merged in `apply` — consistent. `LocalReconciler.apply` expects `manifest.domain.host/port/service` — matches `DomainConfig` fields used in existing production manifests.

**Fix applied during review:** Task 15's `test_apply_dispatches_dns_compose_env_and_domain` uses `DeployManifest.from_yaml`. A note was added in that task warning the engineer to inspect `core/manifest.py` for the existing loader and reuse it rather than adding a new classmethod. Similarly Task 17 warns to inspect `core/deploy_ops.py` for real helper names before mocking them in tests — this avoids the "test passes but prod is broken" trap.

**Scope:** Single subsystem (local domains for Dokploy). No decomposition needed. Builds working, shippable software at the end of Phase 5 (Task 20 has DBGate live on HTTPS); Phase 6 is acceptance + proof.
