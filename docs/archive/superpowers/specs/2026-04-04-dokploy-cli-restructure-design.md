# kctl-dokploy CLI Restructure — Design Spec

**Goal:** Restructure kctl-dokploy from 37 flat top-level groups to ~20 groups, mirroring the Dokploy UI by making compose sub-resources (backups, domains, env, etc.) into subcommands of `compose`.

**Problem:** User has to remember 8+ different top-level groups to manage a single compose service. The CLI doesn't match the Dokploy UI tabs, making it confusing and error-prone.

## Before → After

### Groups ABSORBED into `compose` (10 groups → compose sub-commands)

| Current Top-Level | New Location | Reason |
|---|---|---|
| `backups` | `compose backups` | Backups tab in compose UI |
| `domains` | `compose domains` | Domains tab |
| `env` | `compose env` | Environment tab |
| `schedules` | `compose schedules` | Schedules tab |
| `patches` | `compose patches` | Patches tab |
| `mounts` | `compose mounts` | Part of compose config |
| `volume-backups` | `compose volume-backups` | Volume Backups tab |
| `ports` | `compose ports` | Part of compose config |
| `security` | `compose security` | Part of compose config |
| `redirects` | `compose redirects` | Part of compose config |

### Groups MERGED (5 groups eliminated)

| Current | Merged Into | Reason |
|---|---|---|
| `deployments` | `compose deployments` | Deployments are compose-specific |
| `pipeline` | REMOVED | Duplicates `compose redeploy` + `deploy apply` |
| `status` | `dashboard` | Only has 1 command (`health`) |
| `maintenance` | `diagnose` | Similar purpose (health/cleanup) |
| `bulk` | `compose bulk` | Operates on compose services |

### Groups MOVED (2 groups rehomed)

| Current | New Location | Reason |
|---|---|---|
| `monitoring` | `servers monitoring` | Server-level metrics |
| `environments` | `projects environments` | Project-level config |
| `cluster` | `servers cluster` | Server-level cluster mgmt |

### Groups KEPT as top-level (17 groups)

```
config, projects, applications, compose, servers, databases,
registry, users, git, notifications, certificates, settings,
docker, dashboard, diagnose, deploy, report, audit, template, setup
```

## Implementation Strategy

### Phase 1: Register sub-apps on compose (no code moves)

In `cli.py`, instead of:
```python
app.add_typer(backups_app, name="backups")
```

Do:
```python
compose_app.add_typer(backups_app, name="backups")
```

This is a **one-file change** in `cli.py` — move 10 `add_typer` registrations from `app` to `compose_app`.

### Phase 2: Merge eliminated groups

- Move `deployments` commands into compose (or register as compose sub-app)
- Move `maintenance` commands into `diagnose`
- Move `monitoring` commands into `servers`
- Move `status.health` into `dashboard`
- Move `bulk` commands into compose
- Move `environments` into projects
- Move `cluster` into servers
- Remove `pipeline` (duplicate)

### Phase 3: Update skill, docs, tests

- Update dokploy-admin skill
- Update CLAUDE.md
- Update deploy pipeline references
- Update test imports

## Usage After Restructure

```bash
# Manage a compose service (mirrors UI tabs)
kctl-dokploy compose list
kctl-dokploy compose get <id>
kctl-dokploy compose env <id> list
kctl-dokploy compose env <id> push .env
kctl-dokploy compose domains <id> list
kctl-dokploy compose domains <id> create --host example.com --port 80
kctl-dokploy compose backups <id> list
kctl-dokploy compose backups <id> create --destination <s3> --database mydb
kctl-dokploy compose backups <id> run <backup-id>
kctl-dokploy compose schedules <id> list
kctl-dokploy compose deployments <id> list
kctl-dokploy compose logs <id>

# Top-level stays clean
kctl-dokploy deploy apply -f manifest.yaml
kctl-dokploy projects list
kctl-dokploy servers list
kctl-dokploy dashboard show
kctl-dokploy diagnose run
```

## Backward Compatibility

Keep old top-level groups as **hidden aliases** for 1 version cycle:
```python
# Hidden — still works but doesn't show in --help
app.add_typer(backups_app, name="backups", hidden=True)
```

This way existing scripts don't break immediately.
