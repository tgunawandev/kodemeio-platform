---
name: outline-admin
description: >
  Outline wiki/knowledge-base administration via kctl-outline CLI.
  MUST use for ANY kctl-outline operation — documents, collections, users, groups,
  shares, comments, events, health checks, AND markdown sync between repos and
  one or more Outline instances.
  Triggers on: "kctl-outline", "outline", "wiki", "knowledge base", "create document",
  "collection", "share document", "outline.kodeme.io", "outline.idtpp.com",
  "sync docs", "outline sync", "doc sync", ".outline-sync.yaml".
---

# outline-admin — kctl-outline CLI Reference

## Overview

**CLI:** `kctl-outline`
**Workspace:** `kodemeio-platform/packages/kctl-outline/`
**Install:** `cd packages/kctl-outline && uv sync --extra dev`
**Standalone install:** `uv tool install kctl-outline` (when published to PyPI)

## Global Options

| Flag | Description |
|------|-------------|
| `--json` | JSON output |
| `--quiet`, `-q` | Suppress info messages |
| `--profile`, `-p` | Profile name (default from `~/.config/kodemeio/config.yaml`) |
| `--url` | Override API URL (e.g., `https://outline.idtpp.com`) |
| `--token` | Override API token |
| `--version`, `-V` | Show version |

## Profiles

Configure once per Outline instance:

```bash
kctl-outline config init                                                # interactive
kctl-outline config add kod --url https://outline.kodeme.io --token <T>
kctl-outline config add tpp --url https://outline.idtpp.com --token <T>
kctl-outline config use kod                                             # default
kctl-outline config current                                             # show active
```

## Command Groups

| Group | Purpose |
|---|---|
| `config` | Profile management (init, add, use, show, profiles, current, test) |
| `documents` | Create / list / update / delete / move documents |
| `collections` | Manage collections |
| `users` | User management |
| `groups` | Group management |
| `shares` | Public share links |
| `comments`, `events`, `revisions` | Read-only metadata |
| `templates`, `stars`, `tokens` | Misc admin |
| `search` | Search across documents |
| `health` | Health checks and diagnostics |
| `dashboard` | System overview |
| **`sync`** | **Markdown sync between git repos and Outline (primary integration)** |

## Sync subcommand — primary use case

`kctl-outline sync` is the integration point with `kodemeio-docs`. It supports multi-mapping `.outline-sync.yaml` v2 configs with three direction modes:

- **`push`** — git is the source of truth. Markdown files are pushed to Outline.
- **`pull`** — Outline is the source of truth. Documents are pulled into the repo. Reconciles deletions: docs removed in Outline are also removed from disk.
- **`mixed`** — per-file `.ssot` markers (containing `git` or `outline`) decide direction.

### Commands

```bash
# Dry-run (default) against the kod instance
kctl-outline sync run /path/to/kodemeio-docs --config .outline-sync.kod.yaml

# Apply
kctl-outline sync run /path/to/kodemeio-docs --config .outline-sync.kod.yaml --no-dry-run

# Filter to one direction (push only, skip pull mappings)
kctl-outline sync run . --config .outline-sync.kod.yaml --mode push --no-dry-run

# Same syntax against the TPP instance
kctl-outline sync run /path/to/kodemeio-docs --config .outline-sync.tpp.yaml --no-dry-run

# Inspect tracked state
kctl-outline sync status

# What would change on next push?
kctl-outline sync diff /path/to/kodemeio-docs

# Bootstrap a config stub
kctl-outline sync init /path/to/repo --collection 'My Docs'

# Wipe state (does NOT delete from Outline)
kctl-outline sync reset --force
```

### Profile-aware client routing

When a sync config declares `profile: tpp`, `sync run` builds a fresh client using **that profile's URL+token**, regardless of the active CLI profile. So the same machine can push to both `outline.kodeme.io` and `outline.idtpp.com` without `--profile` switching:

```bash
kctl-outline sync run . --config .outline-sync.kod.yaml --no-dry-run    # → outline.kodeme.io
kctl-outline sync run . --config .outline-sync.tpp.yaml --no-dry-run    # → outline.idtpp.com
```

### .outline-sync.yaml v2 schema

```yaml
instance: outline.kodeme.io       # human-readable, optional
profile: kod                      # selects the kctl-outline profile

mappings:
  - src: shared/                  # path relative to the config file
    collection: "Shared — Engineering"
    mode: push                    # push | pull | mixed
    subpath: ""                   # optional: nest under a doc title
    include:                      # optional gitignore-style globs
      - "01-*/**"
      - "02-*/**"
    exclude:                      # optional
      - "**/draft/**"

  - src: shared/06-business-processes
    collection: "Shared — Business"
    mode: pull                    # nightly cron pulls + reconciles deletions

  - src: tenants/kod
    collection: "Kod — Internal"
    mode: mixed                   # per-file .ssot markers
```

### .ssot markers

Each leaf directory may contain a `.ssot` file with exactly one line: `git` or `outline`. In `mixed` mode the planner skips push actions for files under `outline`-marked directories (and vice versa). The kodemeio-docs pre-commit hook (`scripts/check_ssot.py`) enforces the same rule on commits.

## Live URLs

| Profile | URL | Audience |
|---|---|---|
| `kod` | https://outline.kodeme.io | Kodemeio staff, MAC, Provetics, Terakidz |
| `tpp` | https://outline.idtpp.com | TPP Group customer-facing |

## Tests

```bash
cd packages/kctl-outline
uv run --extra dev pytest tests/ -v
# Expected: 32 tests passing
```

## See also

- Spec: `kodemeio-docs/superpowers/specs/2026-04-10-docs-outline-restructure-design.md`
- Plans: `kodemeio-docs/superpowers/plans/2026-04-10-{docs-restructure,kctl-outline-sync-enhancements,outline-tpp-instance}.md`
- Configs in use: `kodemeio-docs/.outline-sync.{kod,tpp}.yaml`
- Push CI: `kodemeio-docs/.github/workflows/outline-sync-push.yml`
- Nightly pull cron: `kodemeio-docs/scripts/cron/outline-sync-pull.sh`
