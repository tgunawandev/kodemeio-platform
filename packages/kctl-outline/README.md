# kctl-outline

Kodemeio Outline CLI — manages Outline wiki instances and syncs markdown documentation between git repositories and one or more Outline collections.

## Install

```bash
cd packages/kctl-outline
uv sync --extra dev
uv run kctl-outline --help
```

Or via the workspace from the repo root:

```bash
uv sync
uv run --package kctl-outline kctl-outline --help
```

## Configuration

Like other `kctl-*` tools, configuration lives at `~/.config/kodemeio/config.yaml`. Each profile may declare an `outline` service block:

```yaml
profiles:
  kod:
    outline:
      url: https://outline.kodeme.io
      token: env:OUTLINE_API_TOKEN_KOD
  tpp:
    outline:
      url: https://outline.idtpp.com
      token: env:OUTLINE_API_TOKEN_TPP
```

Add a profile interactively:

```bash
kctl-outline config init
kctl-outline config add tpp --url https://outline.idtpp.com --token <TOKEN>
kctl-outline config use kod
```

## Commands

| Group | Purpose |
|---|---|
| `documents` | List, create, update, delete, move documents |
| `collections` | Manage collections |
| `users`, `groups` | User and group management |
| `shares` | Public share links |
| `comments`, `events`, `revisions` | Read-only metadata |
| `templates`, `stars`, `tokens` | Misc admin |
| `health`, `dashboard`, `doctor` | Diagnostics (`doctor` checks URL + auth config) |
| `search` | Search across documents |
| `sync` | **Sync markdown docs between repos and Outline (see below)** |

## Sync subcommand

`kctl-outline sync` is the primary integration point with `kodemeio-docs`. It supports multi-mapping configs (`.outline-sync.yaml` v2) with three direction modes:

- **`push`** — git is the source of truth. Markdown files are pushed to Outline.
- **`pull`** — Outline is the source of truth. Documents are pulled into the repo.
- **`mixed`** — per-file `.ssot` markers decide direction.

```bash
# Dry-run a sync from a repo
kctl-outline sync run /path/to/kodemeio-docs --config .outline-sync.kod.yaml

# Apply
kctl-outline sync run /path/to/kodemeio-docs --config .outline-sync.kod.yaml --no-dry-run

# Filter to a specific direction
kctl-outline sync run . --config .outline-sync.kod.yaml --mode push --no-dry-run

# Inspect tracked state
kctl-outline sync status
kctl-outline sync diff /path/to/repo
```

The full spec lives in `kodemeio-docs/superpowers/specs/2026-04-10-docs-outline-restructure-design.md`.

## Profile-aware sync routing

When a sync config declares `profile: tpp`, `kctl-outline sync run` builds a fresh client using that profile's URL and token, regardless of the active CLI profile. This means the same machine can push to both `outline.kodeme.io` and `outline.idtpp.com` without switching profiles between commands.

## Layout

```
packages/kctl-outline/
├── pyproject.toml
├── README.md
├── src/kctl_outline/
│   ├── cli.py            # Typer entry point
│   ├── commands/         # one module per Outline subresource
│   │   ├── sync.py       # the Plan A/D sync subcommand
│   │   ├── documents.py
│   │   ├── collections.py
│   │   └── …
│   └── core/
│       ├── client.py     # httpx wrapper
│       ├── config.py     # profile resolution
│       ├── sync_config.py    # SyncConfig v2 schema + v1 auto-upgrade
│       ├── sync_planner.py   # pure plan_push_mapping
│       ├── sync_pull.py      # pull direction (Outline → disk)
│       ├── sync_state.py     # MappingSyncEntry + v1→v2 migration
│       └── sync_ssot.py      # .ssot marker walker
└── tests/                # 30+ tests (pytest)
```

## Tests

```bash
cd packages/kctl-outline
uv run --extra dev pytest tests/ -v
```
