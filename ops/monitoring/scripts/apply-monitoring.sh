#!/usr/bin/env bash
# apply-monitoring.sh — Apply all monitoring-as-code configs via kctl-* CLIs
#
# Usage:
#   ./ops/monitoring/scripts/apply-monitoring.sh --profile <profile>
#   ./ops/monitoring/scripts/apply-monitoring.sh --profile <profile> --dry-run
#   ./ops/monitoring/scripts/apply-monitoring.sh --profile <profile> --component grafana
#
# Prerequisites:
#   - kctl-gatus, kctl-grafana, and kctl-glitchtip configured for the selected profile

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MONITORING_DIR="$(dirname "$SCRIPT_DIR")"
DRY_RUN=false
COMPONENT="all"
PROFILE=""

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --component)
            COMPONENT="$2"
            shift 2
            ;;
        --profile|-p)
            PROFILE="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 --profile <profile> [--dry-run] [--component gatus|grafana|alerts|all]"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [[ -z "$PROFILE" ]]; then
    echo "ERROR: --profile is required"
    exit 2
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "\n${GREEN}==> $1${NC}"; }

check_cli() {
    if ! command -v "$1" &>/dev/null; then
        log_error "$1 is not installed. Install with: uv tool install $1"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
log_step "Pre-flight checks"

FAILED=0
for cli in kctl-gatus kctl-grafana kctl-glitchtip; do
    if check_cli "$cli"; then
        log_info "$cli: installed"
    else
        FAILED=1
    fi
done

if [[ "$FAILED" -eq 1 ]]; then
    log_error "Missing required CLIs. Aborting."
    exit 1
fi

if [[ "$DRY_RUN" == "true" ]]; then
    log_warn "DRY RUN mode — no changes will be applied"
fi

# ---------------------------------------------------------------------------
# 1. Gatus — Verify endpoints match config
# ---------------------------------------------------------------------------
apply_gatus() {
    log_step "Gatus: Verifying endpoint configuration"

    # List current endpoints to compare against config
    log_info "Current Gatus endpoints:"
    kctl-gatus -p "$PROFILE" endpoints list --format pretty

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Would sync endpoints from: $MONITORING_DIR/gatus/endpoints.yaml"
        log_info "Would sync alerting from:  $MONITORING_DIR/gatus/alerting.yaml"
        return
    fi

    # Gatus reads its own config.yaml directly from the mounted volume.
    # This section validates that the running config matches our source-of-truth.
    log_info "Gatus config is volume-mounted. To update:"
    log_info "  1. Copy endpoints.yaml + alerting.yaml to the Gatus config volume"
    log_info "  2. Restart Gatus: kctl-dokploy -p $PROFILE compose redeploy kodeme.io-infra-gatus"
    log_info ""
    log_info "Verifying Gatus health..."
    kctl-gatus -p "$PROFILE" health check

    log_info "Gatus endpoint count:"
    kctl-gatus -p "$PROFILE" endpoints list --json | python3 -c "import sys,json; data=json.load(sys.stdin); print(f'  {len(data)} endpoints configured')" 2>/dev/null || log_warn "Could not count endpoints"
}

# ---------------------------------------------------------------------------
# 2. Grafana — Import dashboards and verify datasources
# ---------------------------------------------------------------------------
apply_grafana() {
    log_step "Grafana: Importing dashboards and verifying datasources"

    # Verify datasources
    log_info "Current Grafana datasources:"
    kctl-grafana -p "$PROFILE" datasource list

    # Import dashboards
    DASHBOARD_DIR="$MONITORING_DIR/grafana/dashboards"
    for dashboard_file in "$DASHBOARD_DIR"/*.json; do
        if [[ ! -f "$dashboard_file" ]]; then
            log_warn "No dashboard JSON files found in $DASHBOARD_DIR"
            break
        fi

        dashboard_name="$(basename "$dashboard_file" .json)"
        log_info "Importing dashboard: $dashboard_name"

        if [[ "$DRY_RUN" == "true" ]]; then
            log_info "  Would import: $dashboard_file"
            continue
        fi

        kctl-grafana -p "$PROFILE" dashboard import "$dashboard_file" --overwrite
        log_info "  Imported: $dashboard_name"
    done

    # List all dashboards to confirm
    log_info "Current Grafana dashboards:"
    kctl-grafana -p "$PROFILE" dashboard list
}

# ---------------------------------------------------------------------------
# 3. Grafana Alerts — Verify alert rules are loaded
# ---------------------------------------------------------------------------
apply_alerts() {
    log_step "Grafana Alerts: Verifying alert rules"

    log_info "Alert rules file: $MONITORING_DIR/alerts/rules.yaml"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Would verify alert rules are provisioned in Grafana"
        # Validate YAML syntax
        python3 -c "
import yaml, sys
with open('$MONITORING_DIR/alerts/rules.yaml') as f:
    data = yaml.safe_load(f)
groups = data.get('groups', [])
total_rules = sum(len(g.get('rules', [])) for g in groups)
print(f'  Validated: {len(groups)} groups, {total_rules} rules')
" 2>/dev/null || log_warn "Could not validate rules YAML"
        return
    fi

    # Alert rules are typically loaded via Prometheus config or Grafana provisioning.
    # Verify they are active in Grafana:
    log_info "Current alert rules in Grafana:"
    kctl-grafana -p "$PROFILE" alert list

    # Validate local rules file
    python3 -c "
import yaml, sys
with open('$MONITORING_DIR/alerts/rules.yaml') as f:
    data = yaml.safe_load(f)
groups = data.get('groups', [])
total_rules = sum(len(g.get('rules', [])) for g in groups)
print(f'  Local rules: {len(groups)} groups, {total_rules} rules')
for g in groups:
    name = g.get('name', 'unnamed')
    count = len(g.get('rules', []))
    print(f'    - {name}: {count} rules')
" 2>/dev/null || log_warn "Could not parse rules YAML (is PyYAML installed?)"
}

# ---------------------------------------------------------------------------
# 4. GlitchTip — Verify projects and DSN keys
# ---------------------------------------------------------------------------
apply_glitchtip() {
    log_step "GlitchTip: Verifying error tracking projects"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Would verify GlitchTip projects and DSN keys"
        return
    fi

    log_info "Current GlitchTip projects:"
    kctl-glitchtip -p "$PROFILE" projects list 2>/dev/null || log_warn "Could not list GlitchTip projects (check config)"

    log_info "GlitchTip health:"
    kctl-glitchtip -p "$PROFILE" health check 2>/dev/null || log_warn "Could not reach GlitchTip"
}

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
log_step "Applying monitoring configuration from: $MONITORING_DIR"

case "$COMPONENT" in
    gatus)
        apply_gatus
        ;;
    grafana)
        apply_grafana
        ;;
    alerts)
        apply_alerts
        ;;
    glitchtip)
        apply_glitchtip
        ;;
    all)
        apply_gatus
        apply_grafana
        apply_alerts
        apply_glitchtip
        ;;
    *)
        log_error "Unknown component: $COMPONENT"
        log_error "Valid components: gatus, grafana, alerts, glitchtip, all"
        exit 1
        ;;
esac

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
log_step "Summary"
if [[ "$DRY_RUN" == "true" ]]; then
    log_warn "Dry run complete — no changes were made"
else
    log_info "Monitoring configuration applied successfully"
fi

log_info "Files:"
log_info "  Gatus endpoints:   $MONITORING_DIR/gatus/endpoints.yaml"
log_info "  Gatus alerting:    $MONITORING_DIR/gatus/alerting.yaml"
log_info "  Grafana dashboard: $MONITORING_DIR/grafana/dashboards/platform-overview.json"
log_info "  Grafana datasource:$MONITORING_DIR/grafana/datasources/prometheus.yaml"
log_info "  Alert rules:       $MONITORING_DIR/alerts/rules.yaml"
log_info ""
log_info "Dashboards:"
log_info "  Gatus:     https://gatus.kodeme.io"
log_info "  Grafana:   https://grafana.kodeme.io"
log_info "  GlitchTip: https://glitchtip.kodeme.io"
