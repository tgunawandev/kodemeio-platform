# kctl-accurate

General-purpose CLI for the Accurate Online API. Part of the Kodemeio kctl-* family.

> **v0.1.0a1 (alpha)** — Phase 1 walking skeleton: config + auth + doctor only.
> Module commands (customers, invoices, etc.) ship in 0.1.0 (Phase 2).
> Extract / Indo commands ship in 0.2.0 (Phase 3).

## Install

```bash
uv tool install kctl-accurate
# or, from the kodemeio-platform monorepo:
uv sync --all-packages
```

## Quickstart

```bash
# Interactive: prompts for token, secret, db_id; verifies; saves.
kctl-accurate config init

# Verify creds against the live API
kctl-accurate config test

# Show current token info
kctl-accurate auth token-info

# Diagnose
kctl-accurate doctor
```

## Profiles

Multi-tenant via the kctl-* shared config at `~/.config/kodemeio/config.yaml`:

```yaml
profiles:
  tpp:
    accurate:
      api_token: aut.xxxxx
      signature_secret: ${KCTL_ACCURATE_TPP_SECRET}   # env-var indirection works
      db_id: 12345
      host: https://public.accurate.id
      db_alias: PT TPP Indonesia
```

Use a profile per command: `kctl-accurate -p tpp auth token-info`.

## Global flags

| flag | purpose |
|---|---|
| `-p, --profile NAME` | Override active profile |
| `--api-token TOKEN` | Override profile's api_token |
| `--signature-secret S` | Override profile's signature_secret |
| `--db-id N` | Override profile's db_id |
| `--host URL` | Override profile's host |
| `--json` | JSON output |
| `-q, --quiet` | Suppress progress/info |
| `-V, --version` | Print version + exit |

## Exit codes

| code | meaning |
|---|---|
| 0 | success |
| 1 | command-level failure |
| 2 | config error (missing creds, bad profile) |
| 3 | network/API error (5xx, host unreachable) |
| 4 | auth error (401/403, signature/token) |
| 5 | rate-limit exhaustion (429 after retries) |

> Note: kctl-lib 0.4.0's `handle_cli_error` currently exits 1 for all KctlError subclasses. The differentiated exit codes above are the *intent* carried by the subclass — they will activate when kctl-lib adds per-subclass exit-code routing or when per-command `_run()` overrides are added.

## Related

- [`kodemeio-accurate`](https://pypi.org/project/kodemeio-accurate/) — the Python SDK powering this CLI
- `accurate-sync` — the migration writer (Accurate → Odoo); separate tool, separate scope
