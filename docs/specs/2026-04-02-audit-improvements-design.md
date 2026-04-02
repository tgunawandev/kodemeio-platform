# Audit System Improvements — Design Specification

**Date:** 2026-04-02
**Status:** Approved

---

## Problem

All audit commands (diagnose, report, audit, setup, maintenance) show 0 services/domains because they iterate `p.get("compose", [])` at project root instead of `p.get("environments", [])...compose`. Additionally, security/SSL audits don't check real-world conditions (autodeploy, domain HTTPS, backup status).

## Solution: 3 Tasks

### Task 1: Shared `collect_all_services()` helper

New file: `core/helpers.py`

```python
def collect_all_services(client) -> dict:
    """Returns {
        projects: [{name, projectId, env_count}],
        composes: [{composeId, name, status, project, domains, backups, githubId, autoDeploy}],
        applications: [{applicationId, name, status, project}],
        domains: [{host, port, https, cert, serviceName, domainType, project}],
        summary: {projects, composes, applications, domains, servers}
    }"""
```

Single source of truth. Iterates both `p.get("compose", [])` AND `p.get("environments", [])...compose`.

### Task 2: Fix all audit commands to use helper

Files: `diagnose.py`, `report.py`, `audit.py`, `setup.py`, `maintenance.py`

Replace inline project iteration with `collect_all_services()`.

### Task 3: Enhanced audit checks

| Command | New checks |
|---|---|
| `audit security` | autodeploy enabled, HTTP-only domains, missing domainType:compose |
| `audit ssl` | domain HTTPS status from collected domains (not Dokploy cert API) |
| `audit config` | githubId set, backup configured per compose, domainType validation |
| `report summary` | Accurate counts from environments[] |
| `diagnose` | Fix deployment check API, per-service health status |
| `setup check` | Accurate service/domain counts |

## Files Changed

| File | Change |
|---|---|
| `core/helpers.py` | NEW — shared collection helper |
| `commands/diagnose.py` | MODIFY — use helper, fix deployment API |
| `commands/report.py` | MODIFY — use helper for accurate counts |
| `commands/audit.py` | MODIFY — use helper, add real security checks |
| `commands/setup.py` | MODIFY — use helper for pre-flight |
| `commands/maintenance.py` | MODIFY — use helper for integrity/orphans |
