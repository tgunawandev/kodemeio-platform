# Accurate-Sync Integration into `deploys/` Tooling

**Date:** 2026-04-16
**Author:** Tri Gunawan (+ Claude)
**Status:** Design — not yet implemented
**Scope:** `kodemeio-dokploy/deploys/` — add first-class support for `kodemeio-accurate-sync` so tenants can declare it with one flag and the generator emits the right env file.

---

## Section 1 — Current state

- `deploys/generate.py` reads `tenants/<slug>.yaml` + `bases/<type>.yaml`, walks a set of hard-coded generators (`gen_odoo`, `gen_react_pwa`, `gen_nextjs_corporate`, `gen_nextjs_careers`, `gen_notify`), and writes pairs of files to `instances/production/{tenant}-{stack}-{app}.yaml` + `env/production/.env.{tenant}-{stack}-{app}` (or `.example` when the target already contains secrets).
- Naming convention is strict and already followed by every service: `{tenant}-{stack}-{app}` for filenames, instance name, env file. DNS follows `{tenant}-{app}.{domain}`.
- Odoo env files (Odoo itself + Notify + React-with-OIDC) are treated as "secret envs" — `is_secret_env()` prevents the generator from overwriting them; it writes a `.example` sibling instead so secrets set in Dokploy/prod are never clobbered.
- `kodemeio-accurate-sync` ships `compose/accurate-sync.yml` in the `kodemeio-accurate` repo; the Dokploy project for the TPP instance (`IHh846SmVHrBMdgFTpMGF`) already points at that compose file, and the 9 env vars (`PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`, `ODOO_URL`, `ODOO_DB_FILTER`, `ODOO_ADMIN_PASSWD`, `ACCURATE_TENANTS`) are set manually in the Dokploy UI today.
- Nothing in `deploys/` currently knows about accurate-sync — no base, no tenant field, no generator — so onboarding a second tenant (mac) would mean re-typing the 9 vars in Dokploy by hand and risking drift from the `tpp-odoo-erp` password/host values.

---

## Section 2 — Proposed architecture

### Diagram

```
tenants/tpp.yaml                         bases/accurate-sync.yaml
  accurate_sync:                              kind: base
    enabled: true                             type: accurate-sync
    odoo_ref: erp       ────────┐             source:
    tenants: [tpp]              │               type: github
                                │               owner: tgunawandev
                                │               repo: kodemeio-accurate
                                ▼               branch: main
                        generate.py               compose_path: compose/accurate-sync.yml
                        gen_accurate_sync()     env_defaults:
                                │                 PGPORT: "5432"
                                │                 IMAGE_TAG: "latest"
                                │
              ┌─────────────────┴─────────────────┐
              ▼                                   ▼
  instances/production/                 env/production/
    tpp-accurate-sync.yaml                .env.tpp-accurate-sync.example
                                          (secrets for PGPASSWORD +
                                           ODOO_ADMIN_PASSWD come from
                                           .env.tpp-odoo-erp at generate
                                           time — copied into .example only
                                           when that source file exists
                                           and the `--enrich-from-env` flag
                                           is passed; otherwise emitted as
                                           CHANGE_ME per existing convention)
```

### Key decisions

1. **New base:** `bases/accurate-sync.yaml` — reusable template declaring the github source, compose path, healthcheck, and env defaults. Mirrors the shape of `bases/odoo.yaml` and `bases/fastapi.yaml`.

2. **Tenant manifest addition:** a new optional top-level `accurate_sync:` block in `tenants/<slug>.yaml`:

   ```yaml
   accurate_sync:
     enabled: true
     odoo_ref: erp            # which odoo[] entry to pull PG + admin creds from
     tenants: [tpp]           # comma-separated slugs for ACCURATE_TENANTS
     # Optional:
     # server: tpp-prod-03    # defaults to the referenced odoo entry's server
     # image_tag: latest
   ```

   `odoo_ref` is the `short:` key of the odoo entry (here `erp` — matches `tpp-odoo-erp`). The generator looks it up in the same tenant's `odoo:` list to inherit DB name, db host, deploy profile, and to locate the matching `.env.{tenant}-odoo-{short}` secrets file.

3. **Secret sharing:** `gen_accurate_sync()` derives `PGHOST`, `PGPORT`, `PGUSER`, `PGDATABASE`, `ODOO_URL`, `ODOO_DB_FILTER` from the sibling Odoo generator outputs (identical logic — no duplication of hardcoded values). `PGPASSWORD` and `ODOO_ADMIN_PASSWD` are the only two true secrets; they are **not** written in the generated file (emitted as `CHANGE_ME` in the `.example`). Operators have two supported paths to populate them:

   - **Recommended:** Dokploy env var resolution — the compose file references `${PGPASSWORD}` / `${ODOO_ADMIN_PASSWD}` and Dokploy pulls them from the project-level env file or shared env group. This matches how TPP is wired today.
   - **Optional helper:** add a small `scripts/sync-env-from-odoo.sh <tenant>-accurate-sync <tenant>-odoo-<short>` in `deploys/` that reads `PGPASSWORD` / `ODOO_ADMIN_PASSWD` from the Odoo secret env file and merges them into the accurate-sync one. Only run locally when operators explicitly want a single env file; never auto-run from `generate.py` (honors the existing "generator never writes secrets" invariant).

4. **Where the compose file lives — pick:** **Option (b): Dokploy points at `kodemeio-accurate` repo's `compose/accurate-sync.yml`; `deploys/` only generates the instance YAML (metadata + env_overrides) and the env file (`.example`).**

   **Reasoning:**
   - The compose file already exists in `kodemeio-accurate` and is the natural home for it (same repo the image is built from via GHCR). Duplicating the compose under `compose/odoo.*.yml` or `compose/accurate-sync.yml` in kodemeio-odoo would create a drift surface: image changes in kodemeio-accurate would require a second commit in kodemeio-odoo to update the compose.
   - Every other generator in `deploys/` uses `source_overrides.compose_path` to point Dokploy at a compose file in a different repo (notify already does this: `owner: tgunawandev, repo: kodemeio-react, compose_path: apps/api/notify/docker-compose.yml`). This fits the same pattern.
   - The generated `instances/production/tpp-accurate-sync.yaml` is just the Dokploy binding contract (source + server + env file reference + env_overrides); it is NOT the compose itself. That stays self-contained and reproducible while the compose stays in the service's home repo.

---

## Section 3 — File changes (detailed plan)

### 3.1 New: `deploys/bases/accurate-sync.yaml`

```yaml
# Naming convention for instances:
#   File:     {tenant}-accurate-sync.yaml
#   Instance: {tenant}-accurate-sync
#   Env file: .env.{tenant}-accurate-sync
#
# Deployed alongside the tenant's Odoo ERP instance. Pulls PG + Odoo admin
# credentials from the referenced Odoo entry (tenants/*.yaml → accurate_sync.odoo_ref).

kind: base
type: accurate-sync

source:
  type: github
  owner: tgunawandev
  repo: kodemeio-accurate
  branch: main
  compose_path: compose/accurate-sync.yml

server: kodeme-service
project: kod

healthcheck:
  test: ["CMD", "accurate-sync", "tenants"]
  port: 0                  # container-level command, no HTTP surface
  timeout: 30
  interval: 300
  start_period: 30

env_defaults:
  PGPORT: "5432"
  IMAGE_TAG: "latest"
  TZ: "Asia/Jakarta"
```

### 3.2 Modified: `deploys/tenants/tpp.yaml`

Append:

```yaml
accurate_sync:
  enabled: true
  odoo_ref: erp            # maps to the odoo[] entry with short: erp
  tenants: [tpp]           # ACCURATE_TENANTS comma-joined at render
  # server: (defaults to the tpp-odoo-erp server, tpp-prod-03)
```

A future `tenants/mac.yaml` turning this on is the same 5-line block plus `tenants: [mac]`.

### 3.3 Modified: `deploys/generate.py`

Add `gen_accurate_sync()` and wire into `generate_tenant()`.

```python
def gen_accurate_sync(
    tenant: dict,
    accurate_cfg: dict,
    odoo_entry: dict,
    env_name: str = "production",
    server: str = "",
    dns_prefix: str = "",
    db_prefix: str = "",
) -> tuple[str, str, str, str]:
    """Generate accurate-sync instance YAML + env.example content.

    Returns (yaml_filename, yaml_content, env_example_filename, env_example_content).
    Always emits a *.example — secrets must be populated out-of-band (Dokploy UI
    or the optional scripts/sync-env-from-odoo.sh helper).
    """
    code = tenant["code"]
    display = tenant.get("short_name", tenant["name"])
    domain = tenant["domain"]
    short = odoo_entry["short"]
    db_name = f"{db_prefix}{code}_odoo_{short}"
    odoo_host = f"{dns_prefix}{code}-odoo-{short}.{domain}"
    accurate_tenants = ",".join(accurate_cfg.get("tenants", [code]))
    image_tag = accurate_cfg.get("image_tag", "latest")

    yaml_filename = f"{code}-accurate-sync.yaml"
    env_example_filename = f".env.{code}-accurate-sync.example"

    instance: dict = {
        "kind": "instance",
        "extends": "../../bases/accurate-sync.yaml",
        "instance": {
            "name": f"{code}-accurate-sync",
            "description": f"{display} — Accurate Online sync worker",
        },
        "project": code,
        "environment": env_name,
    }
    if server:
        instance["server"] = server
    instance.update(
        {
            "env_file": f"../../env/{env_name}/.env.{code}-accurate-sync",
            "env_overrides": {
                "COMPOSE_PROJECT_NAME": f"{code}-accurate-sync",
                "TENANT": code,
                "PGDATABASE": db_name,
                "PGUSER": "odoo",
                "ODOO_URL": f"https://{odoo_host}",
                "ODOO_DB_FILTER": f"^{db_name}$",
                "ACCURATE_TENANTS": accurate_tenants,
                "IMAGE_TAG": image_tag,
            },
        }
    )

    env_example = (
        f"# =============================================================================\n"
        f"# {display} Accurate-Sync — {env_name.title()} Environment\n"
        f"# =============================================================================\n"
        f"# Reads PG credentials + Odoo admin password.\n"
        f"# Secrets (PGPASSWORD, ODOO_ADMIN_PASSWD) must match the sibling\n"
        f"# .env.{code}-odoo-{short} file. Populate via Dokploy UI or run\n"
        f"# scripts/sync-env-from-odoo.sh {code}-accurate-sync {code}-odoo-{short}\n"
        f"# =============================================================================\n"
        f"\n"
        f"COMPOSE_PROJECT_NAME={code}-accurate-sync\n"
        f"TENANT={code}\n"
        f"\n"
        f"# DATABASE — must match .env.{code}-odoo-{short}\n"
        f"PGHOST=10.0.0.3\n"
        f"PGPORT=5432\n"
        f"PGUSER=odoo\n"
        f"PGPASSWORD=CHANGE_ME\n"
        f"PGDATABASE={db_name}\n"
        f"\n"
        f"# ODOO — URL of the sibling Odoo instance, admin password for RPC calls\n"
        f"ODOO_URL=https://{odoo_host}\n"
        f"ODOO_DB_FILTER=^{db_name}$\n"
        f"ODOO_ADMIN_PASSWD=CHANGE_ME\n"
        f"\n"
        f"# TENANT LIST — comma-separated slugs from accurate_company table\n"
        f"ACCURATE_TENANTS={accurate_tenants}\n"
        f"\n"
        f"# IMAGE\n"
        f"IMAGE_TAG={image_tag}\n"
        f"TZ=Asia/Jakarta\n"
    )

    return yaml_filename, yaml_dump(instance), env_example_filename, env_example
```

Wiring inside `generate_tenant()` (just after the odoo+react loop, before the next.js/notify blocks):

```python
# --- Accurate-sync ---
accurate_cfg = raw.get("accurate_sync")
if accurate_cfg and accurate_cfg.get("enabled"):
    ref_short = accurate_cfg["odoo_ref"]
    try:
        odoo_entry = next(e for e in raw.get("odoo", []) if e["short"] == ref_short)
    except StopIteration:
        raise ValueError(
            f"accurate_sync.odoo_ref={ref_short!r} does not match any odoo[] "
            f"entry in tenants/{code}.yaml"
        )
    acc_server = accurate_cfg.get("server", server)
    y_name, y_content, e_name, e_content = gen_accurate_sync(
        t, accurate_cfg, odoo_entry, env_name, acc_server, dns_prefix, db_prefix
    )
    files.append((inst_dir / y_name, header + y_content))
    files.append((env_dir / e_name, e_content))
```

Also extend `is_secret_env()`:

```python
def is_secret_env(path: Path) -> bool:
    name = path.name
    return name.startswith(".env.") and (
        "-odoo-" in name
        or "-hono-notify" in name
        or "-react-" in name
        or "-accurate-sync" in name      # NEW
    )
```

### 3.4 Generated: `deploys/instances/production/tpp-accurate-sync.yaml`

```yaml
# GENERATED FROM tenants/tpp.yaml — DO NOT EDIT
kind: instance
extends: ../../bases/accurate-sync.yaml
instance:
  name: tpp-accurate-sync
  description: Pakerti — Accurate Online sync worker
project: tpp
environment: production
server: tpp-prod-03
env_file: ../../env/production/.env.tpp-accurate-sync
env_overrides:
  COMPOSE_PROJECT_NAME: tpp-accurate-sync
  TENANT: tpp
  PGDATABASE: tpp_odoo_erp
  PGUSER: odoo
  ODOO_URL: https://tpp-odoo-erp.idtpp.com
  ODOO_DB_FILTER: ^tpp_odoo_erp$
  ACCURATE_TENANTS: tpp
  IMAGE_TAG: latest
```

### 3.5 Generated: `deploys/env/production/.env.tpp-accurate-sync.example`

```
# =============================================================================
# Pakerti Accurate-Sync — Production Environment
# =============================================================================
# Reads PG credentials + Odoo admin password.
# Secrets (PGPASSWORD, ODOO_ADMIN_PASSWD) must match the sibling
# .env.tpp-odoo-erp file. Populate via Dokploy UI or run
# scripts/sync-env-from-odoo.sh tpp-accurate-sync tpp-odoo-erp
# =============================================================================

COMPOSE_PROJECT_NAME=tpp-accurate-sync
TENANT=tpp

# DATABASE — must match .env.tpp-odoo-erp
PGHOST=10.0.0.3
PGPORT=5432
PGUSER=odoo
PGPASSWORD=CHANGE_ME
PGDATABASE=tpp_odoo_erp

# ODOO — URL of the sibling Odoo instance, admin password for RPC calls
ODOO_URL=https://tpp-odoo-erp.idtpp.com
ODOO_DB_FILTER=^tpp_odoo_erp$
ODOO_ADMIN_PASSWD=CHANGE_ME

# TENANT LIST — comma-separated slugs from accurate_company table
ACCURATE_TENANTS=tpp

# IMAGE
IMAGE_TAG=latest
TZ=Asia/Jakarta
```

(If `.env.tpp-accurate-sync` already exists with real secrets — e.g. after an operator populated it — `is_secret_env()` prevents clobbering; the generator writes `.example` instead, matching existing Odoo behavior.)

### 3.6 Optional: `deploys/scripts/sync-env-from-odoo.sh`

```bash
#!/usr/bin/env bash
# Copy PGPASSWORD and ODOO_ADMIN_PASSWD from a source env file into a target
# env file, creating the target from its .example if missing.
#
#   ./scripts/sync-env-from-odoo.sh tpp-accurate-sync tpp-odoo-erp
set -euo pipefail
TARGET=$1   # e.g. tpp-accurate-sync
SOURCE=$2   # e.g. tpp-odoo-erp
ENV_DIR="$(dirname "$0")/../env/production"
SRC="$ENV_DIR/.env.$SOURCE"
DST="$ENV_DIR/.env.$TARGET"
EX="$ENV_DIR/.env.$TARGET.example"
[[ -f "$SRC" ]] || { echo "Missing source: $SRC"; exit 1; }
[[ -f "$DST" ]] || cp "$EX" "$DST"
for KEY in PGPASSWORD ODOO_ADMIN_PASSWD; do
  VAL=$(grep -E "^${KEY}=" "$SRC" | head -1 | cut -d= -f2-)
  [[ -n "$VAL" ]] || { echo "Source missing $KEY"; exit 1; }
  if grep -qE "^${KEY}=" "$DST"; then
    sed -i "s|^${KEY}=.*|${KEY}=${VAL}|" "$DST"
  else
    printf '%s=%s\n' "$KEY" "$VAL" >> "$DST"
  fi
done
echo "Synced $KEY(s) $SOURCE → $TARGET"
```

Optional because the recommended flow is to rely on Dokploy project-level env resolution. Include only if operators prefer a single `.env.{tenant}-accurate-sync` file.

---

## Section 4 — Deployment steps for a new tenant

```
1. Edit tenants/<slug>.yaml — append:
     accurate_sync:
       enabled: true
       odoo_ref: erp
       tenants: [<slug>]

2. Run: python deploys/generate.py --tenant <slug>
   Expected output:
     WROTE: instances/production/<slug>-accurate-sync.yaml
     WROTE: env/production/.env.<slug>-accurate-sync.example

3. Review diff, commit to the 18.0 branch of kodemeio-dokploy.

4. Create Dokploy project binding (one-time per tenant):
     kctl-dokploy compose create \
       --name <slug>-accurate-sync \
       --project <slug> \
       --source-provider github \
       --source-repo tgunawandev/kodemeio-accurate \
       --source-branch main \
       --compose-path compose/accurate-sync.yml \
       --env-file env/production/.env.<slug>-accurate-sync

5. Populate secrets (either path works):
   a) Dokploy UI — set PGPASSWORD + ODOO_ADMIN_PASSWD to match the
      matching .env.<slug>-odoo-<short> values, OR
   b) Locally run scripts/sync-env-from-odoo.sh <slug>-accurate-sync
      <slug>-odoo-<short>, then kctl-dokploy compose sync-env.

6. Deploy: kctl-dokploy compose deploy --name <slug>-accurate-sync
```

---

## Section 5 — Backwards compatibility

- Existing Dokploy project `IHh846SmVHrBMdgFTpMGF` (TPP accurate-sync) keeps its current name, server binding, and env vars — no rename, no recreate. The generator produces a fresh `instances/production/tpp-accurate-sync.yaml` that matches the live config, so re-running `python generate.py --tenant tpp` is a no-op writeback after secret values are sync'd.
- `is_secret_env()` gains `"-accurate-sync"` so an existing `.env.tpp-accurate-sync` (if operators chose to create one via the helper script) is never overwritten; only `.env.tpp-accurate-sync.example` is rewritten on subsequent generates. Matches existing Odoo/Notify/React-OIDC behavior.
- The new `accurate_sync:` tenant key is optional. Tenants without it (`kod.yaml`, `mac.yaml` as of today) emit exactly the same files they did before — verified by `python generate.py --dry-run --diff`.
- No changes to `bases/odoo.yaml`, `bases/fastapi.yaml`, `bases/react-pwa.yaml`, `bases/nextjs.yaml`, `bases/infra.yaml`, or any existing generator function. Purely additive.

---

## Section 6 — Testing plan

1. **Dry-run generate (before any tenant change) — regression check:**
   ```bash
   python deploys/generate.py --dry-run
   ```
   Expected: `Would write: 0` (all existing instance + env files unchanged).

2. **Add `accurate_sync:` block to `tenants/tpp.yaml`, dry-run again:**
   ```bash
   python deploys/generate.py --tenant tpp --dry-run
   ```
   Expected: `WOULD WRITE: instances/production/tpp-accurate-sync.yaml` and `WOULD WRITE: env/production/.env.tpp-accurate-sync.example`; zero changes to other files.

3. **Full generate, assert env file contents:**
   ```bash
   python deploys/generate.py --tenant tpp
   grep -c '^PGHOST=' env/production/.env.tpp-accurate-sync.example       # 1
   grep -c '^PGPORT=' env/production/.env.tpp-accurate-sync.example       # 1
   grep -c '^PGUSER=' env/production/.env.tpp-accurate-sync.example       # 1
   grep -c '^PGPASSWORD=' env/production/.env.tpp-accurate-sync.example   # 1
   grep -c '^PGDATABASE=' env/production/.env.tpp-accurate-sync.example   # 1
   grep -c '^ODOO_URL=' env/production/.env.tpp-accurate-sync.example     # 1
   grep -c '^ODOO_DB_FILTER=' env/production/.env.tpp-accurate-sync.example # 1
   grep -c '^ODOO_ADMIN_PASSWD=' env/production/.env.tpp-accurate-sync.example # 1
   grep -c '^ACCURATE_TENANTS=' env/production/.env.tpp-accurate-sync.example # 1
   ```
   Expected: each grep returns 1 (all 9 required vars present).

4. **Regression: no other env/instance file changed:**
   ```bash
   git status deploys/env/production/ deploys/instances/production/
   ```
   Expected: only the two new files listed; no other `.env.*` or `*.yaml` modified.

5. **Negative test — missing odoo_ref:**
   ```yaml
   accurate_sync:
     enabled: true
     odoo_ref: doesnotexist
   ```
   Expected: `ValueError: accurate_sync.odoo_ref='doesnotexist' does not match any odoo[] entry in tenants/tpp.yaml`.

6. **Second tenant (mac) — 5-line add, verify isolation:**
   Add `accurate_sync:` block to `tenants/mac.yaml`, run `python deploys/generate.py --tenant mac`. Expected: only `mac-accurate-sync.yaml` + `.env.mac-accurate-sync.example` written; no tpp files touched.

7. **Secret protection — simulate an existing secret env file:**
   ```bash
   cp env/production/.env.tpp-accurate-sync.example env/production/.env.tpp-accurate-sync
   # edit to change PGPASSWORD to something real
   python deploys/generate.py --tenant tpp
   # Expected: "SKIP (secrets): .env.tpp-accurate-sync → wrote .example instead"
   # and the real file is untouched.
   ```

---

## Section 7 — Implementation tasks

Each task is ≤ 90 min and produces a reviewable diff.

1. **[30 min] Add `bases/accurate-sync.yaml`** — copy the skeleton from Section 3.1. Verify `yaml.safe_load` parses cleanly. No generator wiring yet.

2. **[45 min] Add `gen_accurate_sync()` function to `generate.py`** — paste the function from Section 3.3. Add unit-level smoke test: call with a minimal tenant dict + odoo_entry, assert output contains all 9 required vars and the `extends: ../../bases/accurate-sync.yaml` line.

3. **[30 min] Wire `gen_accurate_sync()` into `generate_tenant()`** — insert the block after the odoo+react loop. Include the `odoo_ref` lookup with the explicit `ValueError` for missing refs.

4. **[15 min] Extend `is_secret_env()`** — add `"-accurate-sync"` predicate. No other caller changes required.

5. **[30 min] Add `accurate_sync:` block to `tenants/tpp.yaml`** — reference the existing `odoo_ref: erp` entry, `tenants: [tpp]`. Run `python generate.py --tenant tpp`, commit the two generated files.

6. **[45 min] Sync the generated instance YAML with Dokploy's live TPP binding** — compare `instances/production/tpp-accurate-sync.yaml` against the live Dokploy config for `IHh846SmVHrBMdgFTpMGF`. Reconcile any drift (expected: none for `env_overrides`; server may differ if TPP accurate-sync is currently on a non-default host — update either the tenant YAML or the Dokploy binding). No rename of the live project.

7. **[30 min] Run the full testing plan from Section 6** — dry-run baseline, full generate, grep assertions, negative test. Record output in the implementation PR.

8. **[60 min — optional]** Add `deploys/scripts/sync-env-from-odoo.sh` with the content from Section 3.6. Mark executable, document in `deploys/README.md` alongside the existing `generate.py` usage section.

9. **[30 min] Document the new tenant flag** — update `deploys/README.md` (and/or root `deploys/docs/README.md` if it exists) with the 5-line recipe from Section 4 and a pointer to this design doc.

10. **[15 min — when ready]** Repeat task #5 for `tenants/mac.yaml` once MAC's Accurate connection is provisioned. Verifies the multi-tenant onboarding claim from Section 4.

**Total estimate: 5–6 hours of focused work.**

---

## Appendix — Why not Option (a)?

Option (a) would copy `compose/accurate-sync.yml` into `kodemeio-odoo/compose/` or bake the compose content into `instances/production/tpp-accurate-sync.yaml` itself so Dokploy could pull it from kodemeio-dokploy.

Rejected because:
- **Drift surface.** The image and the compose file evolve together in `kodemeio-accurate`. Splitting them across two repos means any image change (env var addition, volume mount, healthcheck tweak) needs a matching commit in kodemeio-dokploy, and the two can get out of sync silently.
- **Precedent.** `tpp-hono-notify` already uses option (b) (compose lives in `kodemeio-react/apps/api/notify/docker-compose.yml`, Dokploy source pointer in the generated instance YAML). Matching the same pattern keeps the mental model consistent.
- **Reviewability.** PRs to `kodemeio-accurate` already get Claude/human review on the compose file. Keeping it in one place avoids reviewer confusion about which copy is authoritative.
