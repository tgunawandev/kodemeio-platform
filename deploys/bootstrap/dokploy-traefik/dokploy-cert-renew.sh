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

# lego's wildcard filename varies: _.local.kodeme.io.crt or similar. Resolve at runtime.
SRC_CRT=$(ls -1 "$LEGO_DIR"/certificates/*local.kodeme.io.crt | grep -v '\.issuer\.crt$' | head -1)
SRC_KEY="${SRC_CRT%.crt}.key"

install -D -m 0644 "$SRC_CRT" "$LEGO_DIR/local.kodeme.io/fullchain.pem"
install -D -m 0600 "$SRC_KEY" "$LEGO_DIR/local.kodeme.io/privkey.pem"

# Force Traefik to re-read certs (file watcher normally handles this; belt-and-suspenders).
if docker service ls --format '{{.Name}}' 2>/dev/null | grep -qx 'dokploy_dokploy-traefik'; then
  docker service update --force dokploy_dokploy-traefik >/dev/null
fi

echo "Cert rotated: $(date -Iseconds)"
