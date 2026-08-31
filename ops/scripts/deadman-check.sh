#!/usr/bin/env bash
# Dokploy schedule dead-man check -- runs from HOST CRON on tpp-prod-01.
#
# Deliberately NOT a Dokploy schedule, and deliberately not on tpp-prod-04
# where the toolbox lives. A scheduler cannot report its own death, and if
# Dokploy itself is down the watchdog still has to page. Same reasoning that
# kept the Ofelia and xyOps watchdogs off the machines they watched.
#
# Alerts when:
#   - credentials are missing or empty (itself an alert condition, never a
#     reason to go quiet)
#   - the toolbox container is not running -- the single failure that
#     silently kills every scheduled job at once
#   - Dokploy is unreachable, or reports no schedules at all
#   - an ENABLED schedule has never run
#   - an ENABLED schedule's most recent run is not "done"
#   - an ENABLED schedule has no run inside its own interval plus grace
#
# DISABLED schedules are skipped and reported as notes in the log, never by
# email. A watchdog that pages for jobs nobody expects to run is one people
# learn to ignore.
#
# This checks EVERY enabled schedule in the estate, not only the migrated
# ones: 16 pre-existing schedules failed 100% of the time for five months
# precisely because nothing was watching them.
#
# Install: /opt/kodemeio/deadman-check.sh, chmod 755
# Cron:    15 8 * * *   TZ=Asia/Jakarta   (08:15 WIB, after the 07:00 report)
# Creds:   /opt/kodemeio/reports-smtp.env (mode 600) -- SMTP_PASS, ALERT_TO
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SMTP_ENV="${SMTP_ENV:-/opt/kodemeio/reports-smtp.env}"
KCTL_PROFILE="${KCTL_PROFILE:-idtpp}"
TOOLBOX_HOST="${TOOLBOX_HOST:-178.104.169.250}"
PYTHON="${PYTHON:-python3}"
PROBLEMS=""
NOTES=""

add_problem() { PROBLEMS="${PROBLEMS}"$'\n'"$1"; }
add_note()    { NOTES="${NOTES}"$'\n'"$1"; }

# --- Credentials -----------------------------------------------------------
# A missing file is itself an alert condition: record it, still try to mail,
# still exit non-zero. Never go quiet because the config is wrong.
if [[ -r "$SMTP_ENV" ]]; then
    set -a
    # shellcheck disable=SC1090
    . "$SMTP_ENV"
    set +a
else
    add_problem "CREDENTIALS MISSING: ${SMTP_ENV} is not readable."
fi
ALERT_TO="${ALERT_TO:-trigunawan.note@gmail.com}"
export ALERT_TO

# --- 1. Toolbox container alive? ------------------------------------------
# The one failure a schedule-history check cannot see: if the container is
# gone, every job simply stops, and the last recorded run still says "done".
if ! ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=no \
        "root@${TOOLBOX_HOST}" \
        'docker ps --format "{{.Names}}" | grep -q -- "-kctl-1"' 2>/dev/null; then
    add_problem "TOOLBOX DOWN: no running *-kctl-1 container on ${TOOLBOX_HOST}. Every scheduled job is dead."
fi

# --- 2. Every enabled schedule is fresh and succeeding ---------------------
STATUS_JSON="$("$PYTHON" "${HERE}/schedule-status.py" --profile "$KCTL_PROFILE" --json 2>/dev/null)"
if [[ -z "$STATUS_JSON" || "$STATUS_JSON" == "[]" ]]; then
    add_problem "DOKPLOY UNREACHABLE OR EMPTY: no schedules returned for profile ${KCTL_PROFILE}."
else
    REPORT="$(SCHEDULES="$STATUS_JSON" "$PYTHON" "${HERE}/deadman_report.py")"
    while IFS= read -r line; do
        [[ -n "$line" ]] && add_problem "$line"
    done < <("$PYTHON" -c 'import json,sys; [print(p) for p in json.load(sys.stdin)["problems"]]' <<<"$REPORT")
    while IFS= read -r line; do
        [[ -n "$line" ]] && add_note "$line"
    done < <("$PYTHON" -c 'import json,sys; [print(n) for n in json.load(sys.stdin)["notes"]]' <<<"$REPORT")
fi

# --- Report ----------------------------------------------------------------
[[ -n "$NOTES" ]] && printf '%s\n' "${NOTES# }"

if [[ -z "$PROBLEMS" ]]; then
    echo "$(date '+%F %T') OK"
    exit 0
fi

BODY="Dokploy schedule DEAD-MAN CHECK -- PROBLEMS DETECTED
Host: $(hostname)   Time: $(TZ=Asia/Jakarta date '+%F %T %Z')
${PROBLEMS}

--
Investigate:
  python3 ${HERE}/schedule-status.py --profile ${KCTL_PROFILE}
  ssh root@${TOOLBOX_HOST} 'docker ps | grep kctl'
  ssh root@${TOOLBOX_HOST} 'ls -t /etc/dokploy/schedules/*/*.log | head'
"
echo "$(date '+%F %T') ALERT" >&2
printf '%s\n' "$BODY" >&2

if [[ -z "${SMTP_PASS:-}" ]]; then
    echo "FATAL: SMTP_PASS unavailable -- cannot send the alert mail either." >&2
    exit 1
fi

BODY="$BODY" SUBJECT="[ALERT] Dokploy schedules are UNHEALTHY" \
    "$PYTHON" "${HERE}/deadman_mail.py" \
    || echo "FATAL: alert mail FAILED -- this problem is now silent." >&2
exit 1
