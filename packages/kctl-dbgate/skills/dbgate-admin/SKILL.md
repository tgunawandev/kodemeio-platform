---
name: dbgate-admin
description: >
  DBGate web-based database management administration via kctl-dbgate CLI.
  MUST use for ANY kctl-dbgate operation — database connections, health checks,
  config, doctor diagnostics.
  Triggers on: "kctl-dbgate", "dbgate", "database gate", "dbgate.kodeme.io",
  "dbgate connection", "add connection", "list connections".
---

# dbgate-admin — kctl-dbgate CLI Reference

## Overview

**CLI:** `kctl-dbgate`
**Workspace:** `kodemeio-platform/packages/kctl-dbgate/`
**Install:** `cd packages/kctl-dbgate && uv sync --extra dev`

DBGate is a web-based database management UI (MySQL, PostgreSQL, MongoDB,
SQLite, SQL Server). `kctl-dbgate` manages connections registered with a
running DBGate instance and provides health + config tooling.

## Command Groups

| Group          | Purpose                                                |
|----------------|--------------------------------------------------------|
| `config`       | Profile init, add, use, show, validate                 |
| `connections`  | Register + list database connections in DBGate         |
| `health`       | DBGate instance health check                           |
| `doctor`       | Diagnostic checks (URL, credentials, connectivity)     |

## Quick Start

```bash
# One-time configuration
kctl-dbgate config init
kctl-dbgate doctor          # verify URL + credentials

# List/add database connections
kctl-dbgate connections list
kctl-dbgate connections add --name "prod-postgres" --engine postgres --host ...
```

## Global Options

Standard kctl-* globals: `--json`, `--quiet/-q`, `--format/-f` (pretty/json/csv/yaml),
`--no-header`, `--profile/-p`, `--version/-V`.

Service-specific overrides (dbgate-only): `--url`, `--login`, `--password`.

## Config

Profile config lives in `~/.config/kodemeio/config.yaml` under the `dbgate`
service key (scoped per-profile):

```yaml
profiles:
  default:
    dbgate:
      url: https://dbgate.kodeme.io
      login: admin
      password: ${DBGATE_PASSWORD}
```

See `packages/kctl-dbgate/README.md` for full command reference.
