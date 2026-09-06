# CLAUDE.md — kodemeio-dokploy

This repository owns Dokploy deployment desired state, infrastructure,
monitoring, and operational runbooks. CLI implementation belongs in
`kodemeio-skills`.

## Key paths

| Path | Purpose |
|---|---|
| `deploys/bases/` | Reusable deployment bases |
| `deploys/instances/` | Local, staging, and production desired state |
| `deploys/env/` | Ignored values and committed sanitized examples |
| `deploys/tenants/` | Generator inputs |
| `deploys/bootstrap/` | Dokploy/Traefik bootstrap |
| `infra/` | Terraform root and local modules |
| `ops/monitoring/` | Monitoring configuration |
| `ops/runbooks/` | Incident and recovery procedures |
| `ops/scripts/` | Operational utilities |
| `docs/archive/` | Historical, non-authoritative material |

## The front door — `./dokploy.sh`

Everything that touches a Dokploy instance goes through it. It resolves the
platform to a profile, refuses unconfirmed writes, and forwards anything it does
not own to `kctl-dokploy` verbatim, so a CLI command that shipped this morning is
reachable here this afternoon with no registration.

```bash
./dokploy.sh                                  # usage, generated from dokploy.yaml + bin/dokploy/
./dokploy.sh kodemeio applications list       # resolved: kctl-dokploy -p kodemeio ...
./dokploy.sh health kodemeio                  # a repo tool from bin/dokploy/
./dokploy.sh commands tree                    # passthrough, verbatim
```

| platform | profile | control plane |
|---|---|---|
| `kodemeio` | `kodemeio` | https://dokploy.kodeme.io |
| `idtpp` | `idtpp` | https://dokploy.idtpp.com |
| `abcfood` | `abcfood` | https://dokploy-hz.abcfood.app |
| `local` | `local` | http://localhost:3000 — the only unguarded target |

**`--dry-run` prints the resolved command and runs nothing.** Cheapest possible
first move, and safe against production.

🔴 **`--yes` is the DOOR's confirmation, not the CLI's.** 95 write verbs are
guarded; the door reads the flag then strips it, because `kctl-dokploy` owns no
`--yes` of its own and forwarding one makes it exit on `No such option`.
`--kctl-yes` forces a real one through.

🔴 **`--dry-run` here is the door's, not `kctl-dokploy`'s.** This CLI has a real
`--dry-run` that previews against the live API; reach it with `--kctl-dry-run`.

The guard table in `dokploy.yaml` is **derived**, not hand-written — re-derive it
after a CLI upgrade and check it with:

```bash
../kodemeio-skills/scripts/frontdoor-guards verify dokploy.yaml
```

`dokploy.sh` and `bin/dokploy/*` are **vendored byte-identical** from
`kodemeio-skills/templates/frontdoor/`. Never edit them in place — edit the
template and run `scripts/frontdoor-sync --write`. `--check` fails on drift.
`dokploy.yaml` is the only per-repo file. Full standard:
`kodemeio-skills/docs/frontdoor.md`.

## Commands

```bash
uv sync
just test
just lint
just fmt-check
terraform -chdir=infra init -backend=false
terraform -chdir=infra validate

./dokploy.sh <platform> doctor ai-summary
./dokploy.sh <platform> deploy validate -f <manifest>
./dokploy.sh <platform> deploy apply -f <manifest> --dry-run   # preview
./dokploy.sh <platform> deploy apply -f <manifest> --yes       # commit
```

## Rules

Three of these used to be prose asking a human to remember something. They are
now enforced by `./dokploy.sh`, and are kept here to say what enforces them —
**a rule a machine can check should never be only a sentence in a document.**

| Rule | Enforced by |
|---|---|
| Always pass an explicit profile | the door resolves it from `<platform>`, and **rejects** a stray `-p` as conflicting |
| Preview live-facing operations before applying | `--dry-run`, plus 95 guarded verbs that refuse without `--yes` |
| Read-only validation, status and doctor are safe | those verbs are deliberately absent from the guard table — over-guarding a read is as much a bug as under-guarding a write |

Still prose, because no mechanism checks them yet:

- Never commit real env files, credentials, Terraform state, or dumps.
- Do not modify files in `docs/archive/` to describe current behavior.
- Do not add `kctl-*` source or package scaffolding here.
- Standard HTTP services use the external `dokploy-network` and Traefik.
- **Never stop or remove `dokploy` or `traefik`.** ⚠️ The door cannot refuse
  this yet — `docker restart` and `docker prune` are guarded, but nothing knows
  those two container names are special. A `PreToolUse` deny hook is the fix, the
  way `kodemeio-odoo/bin/hooks/require-18-0-branch.py` denies a commit off the
  wrong branch. Until then this is on you.
- Deploys are asynchronous; verify completion and health (`./dokploy.sh health <platform>`).
- Preserve ignored files under `deploys/env/` during repository moves.

See `README.md` and `docs/architecture.md` for the current system boundary.
