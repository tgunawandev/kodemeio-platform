# dokploy-traefik — local domains bootstrap

One-time setup to enable `https://<service>.local.kodeme.io` on this workstation.
Spec: [archived local-domains design](../../../docs/archive/superpowers/specs/2026-04-18-dokploy-local-domains-design.md).

## Prerequisites

- Ports 80 and 443 free. If held by another container, stop it first.
- Cloudflare zone `kodeme.io` accessible via `kctl-cf -p kodemeio`.
- Docker engine 24.x+ in Swarm mode.

## Install (run once, in this order)

```bash
# 1. Reuse the kctl-cf kodemeio profile's CF token (already has Zone.DNS:Edit)
sudo install -d -m 0700 -o root -g root /etc/dokploy/traefik
python3 -c "import yaml; print('CF_DNS_API_TOKEN=' + yaml.safe_load(open('/home/tgunawan/.config/kodemeio/config.yaml'))['profiles']['kodemeio']['cloudflare']['api_token'])" \
  | sudo tee /etc/dokploy/traefik/lego.env >/dev/null
sudo chmod 0600 /etc/dokploy/traefik/lego.env

# 2. Create wildcard + apex A records → LAN IP
LAN_IP=$(ip -4 -o route get 1 | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}')
kctl-cf -p kodemeio records create --zone kodeme.io --type A --name '*.local' --content "$LAN_IP" --ttl 60 --no-proxied
kctl-cf -p kodemeio records create --zone kodeme.io --type A --name 'local'   --content "$LAN_IP" --ttl 60 --no-proxied

# 3. Install lego
LEGO_VERSION=v4.19.2
curl -sSL "https://github.com/go-acme/lego/releases/download/${LEGO_VERSION}/lego_${LEGO_VERSION}_linux_amd64.tar.gz" \
  | sudo tar -xz -C /usr/local/bin lego
sudo chmod 0755 /usr/local/bin/lego

# 4. Install renewal wrapper + systemd units
sudo install -m 0755 dokploy-cert-renew.sh /usr/local/bin/
sudo install -m 0644 dokploy-cert-renew.service dokploy-cert-renew.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dokploy-cert-renew.timer

# 5. Bootstrap the cert (first issuance, ~60s)
sudo systemctl start dokploy-cert-renew.service
sudo journalctl -u dokploy-cert-renew.service -n 10 --no-pager   # expect "Cert rotated"

# 6. Drop Traefik dynamic config
sudo install -m 0644 dynamic/wildcard-local.yml /etc/dokploy/traefik/dynamic/

# 7. Deploy the Traefik swarm stack
docker stack deploy -c docker-compose.yml dokploy
```

## Verify

```bash
# Port ownership
sudo ss -ltnp 'sport = :80 or sport = :443'   # Traefik container via docker-proxy

# Cert
sudo openssl x509 -in /etc/dokploy/traefik/dynamic/certs/local.kodeme.io/fullchain.pem \
  -noout -subject -enddate
# subject=CN = *.local.kodeme.io ; notAfter ≈ +90 days

# Unknown host → Traefik 404 with valid cert, no -k needed
curl -sI https://nothing.local.kodeme.io/ | head -1   # HTTP/2 404
```

## Rotate the Cloudflare token

If the `kodemeio` profile token changes:

```bash
python3 -c "import yaml; print('CF_DNS_API_TOKEN=' + yaml.safe_load(open('/home/tgunawan/.config/kodemeio/config.yaml'))['profiles']['kodemeio']['cloudflare']['api_token'])" \
  | sudo tee /etc/dokploy/traefik/lego.env >/dev/null
sudo chmod 0600 /etc/dokploy/traefik/lego.env
sudo systemctl start dokploy-cert-renew.service   # verify next renewal works
```

## LAN IP changed

```bash
NEW_IP=$(ip -4 -o route get 1 | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}')
# kctl-cf records update: look up ID first, then update by ID
for name in '*.local.kodeme.io' 'local.kodeme.io'; do
  REC=$(kctl-cf -p kodemeio --json records list --zone kodeme.io --type A \
    | python3 -c "import json,sys; [print(r['id']) for r in json.load(sys.stdin) if r['name']=='$name']")
  kctl-cf -p kodemeio records update "$REC" --zone kodeme.io --content "$NEW_IP"
done
```

Or: run `kctl-dokploy -p <profile> deploy apply-local <any-local-manifest>` — its DNS reconcile step detects drift.

## Gotchas / caveats (seen during first bootstrap)

- **Docker engine 29.x rejects Traefik's default API v1.24.** Fix: `DOCKER_API_VERSION=1.47` env on the Traefik service (already in `docker-compose.yml`).
- **SERVFAIL during lego's propagation check.** Fix: lego queries CF's authoritative NS directly via `--dns.resolvers rory.ns.cloudflare.com:53 --dns.resolvers desiree.ns.cloudflare.com:53` (already in `dokploy-cert-renew.sh`).
- **Stale `_acme-challenge.local.kodeme.io` TXT records** from a crashed previous attempt cause CF error 81058 "identical record already exists". Clean them up first: `kctl-cf -p kodemeio records list --zone kodeme.io --type TXT` → identify → `records delete <id> --zone kodeme.io --force`.
- **Static config path references.** `/etc/dokploy/traefik/traefik.yml` uses absolute paths like `/etc/dokploy/traefik/dynamic/...`. The compose must bind-mount **at the same path** inside the container, not a different path like `/etc/traefik/`, or file-provider paths won't resolve.
- **`host-mode port already in use`** during swarm service updates. On a single-node setup, `order: start-first` (the default) can briefly fail as both tasks fight for :80/:443. Either wait it out (resolves within ~60s) or switch update config to `order: stop-first`.

## Rollback

```bash
# Stop Traefik (does NOT delete the cert or dynamic config)
docker service rm dokploy_dokploy-traefik

# Bring back a prior :80/:443 holder (example: the old Frappe nginx-proxy)
docker compose -f /home/tgunawan/frappe/services/docker-compose.yml up -d

# Disable auto-renewal (cert stays on disk, timer is the only auto-action)
sudo systemctl disable --now dokploy-cert-renew.timer
```
