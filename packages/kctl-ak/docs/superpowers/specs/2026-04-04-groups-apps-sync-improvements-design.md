# Groups Sync Overhaul + Apps Improvements — Design Spec

## Goal

Enhance `kctl-ak` so that all operations we did manually during the multi-company
reorganization (creating/updating/pruning groups, setting icons, syncing app metadata)
can be done declaratively from YAML manifests via `kctl-ak groups sync` and a new
`kctl-ak apps sync` command.

## Spec 1: `groups sync` Overhaul

### Current Behavior (broken)

- Creates groups that don't exist, silently skips existing ones
- Ignores `parent` field from YAML
- Ignores `description` field (stored in Authentik group attributes)
- No way to remove groups deleted from YAML
- `--no-dry-run` flag already fixed

### New Behavior

**Command:** `kctl-ak groups sync [--no-dry-run] [--prune] [--file PATH]`

Three phases, always in this order:

**Phase 1 — Create:** Groups in YAML not in Authentik. Created without parents first.

**Phase 2 — Update:** Groups that exist but differ. Checked fields:
- `is_superuser` — compared directly
- `parent` — resolved by name, compared to current parent
- `description` — stored in `attributes.description` on the Authentik group

**Phase 3 — Prune (only with `--prune`):** Delete groups in Authentik that:
- Have the `ak-` name prefix (protects system groups like `authentik Admins`)
- Are NOT present in the YAML manifest

Parent resolution runs after all creates complete, so a child can reference
a parent defined later in the YAML file.

### Dry-run Output Format

```
────── Group Sync ──────
INFO Source: config/group-structure.yaml
INFO Desired: 34 | Existing: 32 | To create: 2 | To update: 3 | To prune: 6

[create] ak-shared-infra
[create] ak-shared-biz
[update] ak-shared-app-grafana — parent: (none) → ak-shared-infra
[update] ak-shared-app-mailcow — parent: (none) → ak-shared-biz
[update] ak-platform-admin — is_superuser: false → true
[prune]  ak-app-mattermost-all
[prune]  ak-app-odoo-all

WARN Dry-run mode. Use --no-dry-run to apply changes.
```

### Implementation Details

File: `packages/kctl-ak/src/kctl_ak/commands/groups.py` — modify `sync()` function.

**Algorithm:**
1. Load YAML, load all existing groups from API
2. Build lookup: `existing_by_name = {g["name"]: g for g in existing}`
3. **Create pass:** for each YAML group not in `existing_by_name`, create it (no parent yet)
4. Reload all groups (to get PKs of newly created ones)
5. **Update pass:** for each YAML group, compare `is_superuser`, `parent`, `description` with existing. Patch if different.
6. **Prune pass** (if `--prune`): for each existing group starting with `ak-`, if name not in YAML desired set, delete it.

**Parent resolution:** Resolve parent name → PK using the refreshed group list after creates.

**Description storage:** Authentik groups don't have a native `description` field. Store in `attributes.description` via PATCH `{"attributes": {"description": "..."}}`.

## Spec 2: Apps Improvements

### 2a. `apps list` — Show `group` Column

Add `Group` column to the `apps list` table between `Name` and `Provider`.

File: `packages/kctl-ak/src/kctl_ak/commands/apps.py` — modify `list_()`.

Fetch `group` field from API response (already returned, just not displayed).

### 2b. `apps set-icon` — File Upload

**Command:** `kctl-ak apps set-icon <slug> <source>`

`<source>` can be:
- Local file path (`.png`, `.svg`) — uploaded via multipart form PATCH
- URL (`https://...`) — set via JSON PATCH on `meta_icon` field

File: `packages/kctl-ak/src/kctl_ak/commands/apps.py` — new `set_icon()` command.

**Multipart upload:** Authentik API accepts `PATCH /api/v3/core/applications/<slug>/`
with `Content-Type: multipart/form-data` and a `meta_icon` file field. The kctl-ak
client currently only sends JSON. Add a `patch_multipart()` method to
`AuthentikClient` that sends `files=` instead of `json=`.

### 2c. `apps sync` — Declarative App Management

**Command:** `kctl-ak apps sync [--no-dry-run] [--prune] [--file PATH]`

**New manifest file:** `config/app-registry.yaml`

```yaml
apps:
  # --- MAC (Mandiriagro) ---
  - slug: mac-odoo-dist
    name: "MAC — Odoo Distribution"
    group: "MAC — Mandiriagro"
    launch_url: https://odoo-dist-mac.mandiriagro.com
    icon: icons/odoo.png

  - slug: mac-react-wms
    name: "MAC — WMS"
    group: "MAC — Mandiriagro"
    launch_url: https://wms-mac.mandiriagro.com
    icon: icons/wms.png

  # --- Shared Infrastructure ---
  - slug: shared-gatus
    name: "Shared — Gatus"
    group: "Shared — Infrastructure"
    launch_url: https://gatus.kodeme.io
    icon: icons/gatus.png
```

**Three phases (same pattern as groups sync):**

**Phase 1 — Create:** Apps in YAML not in Authentik. Created with `name`, `slug`,
`meta_launch_url`, `group`.

**Phase 2 — Update:** Apps that exist but fields differ. Compared fields:
- `name`
- `group`
- `meta_launch_url`
- `meta_icon` (only if `icon` is a URL; file icons require separate upload)

For file-based icons: after create/update, upload icon if `icon` field is a local
path and the file exists. Uses the `patch_multipart()` method from 2b.

**Phase 3 — Prune (with `--prune`):** Delete apps whose slugs match any known prefix
(`mac-`, `tpp-`, `kod-`, `tkz-`, `pro-`, `shared-`) but aren't in the YAML. Protects
system apps (`ldap`, `dokploy`, etc.).

**No provider creation.** Providers are a separate concern handled by `setup oauth2`
/ `setup proxy`. Apps sync only manages the application object metadata.

### Config Resolution

`app-registry.yaml` searched in same paths as `group-structure.yaml`:
1. `--file` flag
2. `./config/app-registry.yaml` (project root)
3. `~/.config/kodemeio/app-registry.yaml`

Add `resolve_app_registry_path()` to `core/config.py` following the existing
`resolve_group_structure_path()` pattern.

## Files Changed

| File | Change |
|------|--------|
| `commands/groups.py` | Rewrite `sync()` — 3-phase create/update/prune |
| `commands/apps.py` | Add `group` to `list_()`, new `set_icon()`, new `sync()` |
| `core/client.py` | Add `patch_multipart()` method |
| `core/config.py` | Add `resolve_app_registry_path()` |
| `config/app-registry.yaml` | New file (in kodemeio-authentik repo) |
| Tests | `test_groups_sync.py`, `test_apps_sync.py`, `test_apps_set_icon.py` |

## Out of Scope

- Provider creation/linking (handled by `setup oauth2`/`setup proxy`)
- Policy binding management
- Bulk user provisioning to new groups
- Icon generation (done externally, sync just uploads)
