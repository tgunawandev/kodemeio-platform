#!/usr/bin/env bash
# Acceptance smoke tests for dokploy-traefik + *.local.kodeme.io.
# Exit code: 0 = all green, 1 = any failure.

set -uo pipefail

PASS=0
FAIL=0

check() {
  local name=$1 result=$2 note=${3:-}
  if [ "$result" = "0" ]; then
    printf "PASS  %s %s\n" "$name" "$note"
    PASS=$((PASS + 1))
  else
    printf "FAIL  %s %s\n" "$name" "$note"
    FAIL=$((FAIL + 1))
  fi
}

# 1. dokploy-traefik swarm service is 1/1
docker service ls --filter name=dokploy_dokploy-traefik --format '{{.Replicas}}' | grep -qx '1/1'
check "dokploy-traefik service 1/1" $?

# 2. Traefik container is healthy
CID=$(docker ps -q --filter label=com.docker.swarm.service.name=dokploy_dokploy-traefik | head -1)
if [ -n "$CID" ]; then
  HEALTH=$(docker inspect "$CID" --format '{{.State.Health.Status}}' 2>/dev/null)
  [ "$HEALTH" = "healthy" ]
  check "traefik container healthy" $? "($HEALTH)"
else
  check "traefik container exists" 1 "(no container)"
fi

# 3. Cert valid for > 30 days — fetch via TLS handshake (no sudo required).
END_DATE=$(echo | openssl s_client -connect dbgate.local.kodeme.io:443 -servername dbgate.local.kodeme.io 2>/dev/null \
  | openssl x509 -noout -enddate 2>/dev/null | awk -F= '{print $2}')
if [ -n "$END_DATE" ]; then
  END_TS=$(date -d "$END_DATE" +%s 2>/dev/null || echo 0)
  NOW_TS=$(date +%s)
  DAYS_LEFT=$(( (END_TS - NOW_TS) / 86400 ))
  [ "$DAYS_LEFT" -gt 30 ]
  check "cert valid >30d" $? "(actual=${DAYS_LEFT}d)"
else
  check "cert readable via TLS" 1
fi

# 4. Systemd timer enabled
systemctl is-enabled dokploy-cert-renew.timer >/dev/null 2>&1
check "dokploy-cert-renew.timer enabled" $?

# 5. Cert-renew service has run successfully at least once
LAST_EXIT=$(systemctl show -p ExecMainStatus dokploy-cert-renew.service 2>/dev/null | cut -d= -f2)
[ "$LAST_EXIT" = "0" ]
check "cert-renew last run exited 0" $? "(status=$LAST_EXIT)"

# 6. Unknown *.local.kodeme.io host → Traefik 404 with valid cert
STATUS=$(curl -sI --max-time 5 https://does-not-exist-$(date +%s).local.kodeme.io/ 2>/dev/null | head -1 | awk '{print $2}')
[ "$STATUS" = "404" ]
check "wildcard unknown host → 404" $? "(HTTP $STATUS)"

# 7. DBGate responds 200 over HTTPS with wildcard cert
STATUS=$(curl -sI --max-time 5 https://dbgate.local.kodeme.io/ 2>/dev/null | head -1 | awk '{print $2}')
[ "$STATUS" = "200" ] || [ "$STATUS" = "302" ]
check "dbgate.local.kodeme.io → 200/302" $? "(HTTP $STATUS)"

# 8. Cert CN is *.local.kodeme.io
CN=$(echo | openssl s_client -connect dbgate.local.kodeme.io:443 -servername dbgate.local.kodeme.io 2>/dev/null | openssl x509 -noout -subject 2>/dev/null | sed 's/.*CN = //')
[ "$CN" = "*.local.kodeme.io" ]
check "cert CN = *.local.kodeme.io" $? "(got '$CN')"

echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
