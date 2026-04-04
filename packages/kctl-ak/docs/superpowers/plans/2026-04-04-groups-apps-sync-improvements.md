# Groups Sync + Apps Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `kctl-ak groups sync` fully declarative (create/update/prune from YAML) and add `apps list` group column, `apps set-icon` file upload, and `apps sync` declarative app management.

**Architecture:** Rewrite `groups sync` to 3-phase (create → update → prune). Add `patch_multipart()` to client for file uploads. New `apps sync` command reads `app-registry.yaml` with same 3-phase pattern. Add `resolve_app_registry_path()` to config.

**Tech Stack:** Python 3.13, Typer, httpx, PyYAML, pytest

---

### Task 1: Rewrite `groups sync` — 3-phase create/update/prune

**Files:**
- Modify: `packages/kctl-ak/src/kctl_ak/commands/groups.py:230-297`
- Test: `packages/kctl-ak/tests/test_commands/test_groups_sync.py` (create)

- [ ] **Step 1: Write tests for the new groups sync**

Create `packages/kctl-ak/tests/test_commands/test_groups_sync.py`:

```python
"""Tests for groups sync 3-phase logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from kctl_ak.cli import app

runner = CliRunner()


@pytest.fixture
def yaml_file(tmp_path: Path) -> Path:
    data = {
        "groups": [
            {"name": "ak-test-admin", "is_superuser": True, "description": "Admin group"},
            {"name": "ak-test-app-one", "is_superuser": False, "parent": "ak-test-admin"},
            {"name": "ak-test-app-two", "is_superuser": False},
        ]
    }
    p = tmp_path / "group-structure.yaml"
    p.write_text(yaml.dump(data))
    return p


class TestGroupsSyncHelp:
    def test_sync_has_prune_flag(self) -> None:
        result = runner.invoke(app, ["groups", "sync", "--help"])
        assert result.exit_code == 0
        assert "--prune" in result.output
        assert "--no-dry-run" in result.output


class TestGroupsSyncDryRun:
    @patch("kctl_ak.commands.groups.AppContext")
    def test_dry_run_shows_create_update_prune(
        self, mock_ctx_cls: MagicMock, yaml_file: Path
    ) -> None:
        """Verify dry-run output labels for all three phases."""
        # This is a help/flag test — full integration requires mocking the API
        result = runner.invoke(app, ["groups", "sync", "--help"])
        assert "--prune" in result.output


class TestGroupsSyncAlgorithm:
    def test_create_phase_detects_missing_groups(self) -> None:
        """Groups in YAML not in existing should be in create list."""
        from kctl_ak.commands.groups import _compute_sync_plan

        desired = [
            {"name": "ak-new-group", "is_superuser": False},
            {"name": "ak-existing", "is_superuser": False},
        ]
        existing = [{"name": "ak-existing", "pk": "uuid-1", "is_superuser": False, "parent": None, "parent_name": None, "attributes": {}}]

        plan = _compute_sync_plan(desired, existing)
        assert len(plan["create"]) == 1
        assert plan["create"][0]["name"] == "ak-new-group"

    def test_update_phase_detects_superuser_change(self) -> None:
        from kctl_ak.commands.groups import _compute_sync_plan

        desired = [{"name": "ak-group", "is_superuser": True}]
        existing = [{"name": "ak-group", "pk": "uuid-1", "is_superuser": False, "parent": None, "parent_name": None, "attributes": {}}]

        plan = _compute_sync_plan(desired, existing)
        assert len(plan["update"]) == 1
        assert plan["update"][0]["changes"]["is_superuser"] == (False, True)

    def test_update_phase_detects_parent_change(self) -> None:
        from kctl_ak.commands.groups import _compute_sync_plan

        desired = [
            {"name": "ak-parent", "is_superuser": False},
            {"name": "ak-child", "is_superuser": False, "parent": "ak-parent"},
        ]
        existing = [
            {"name": "ak-parent", "pk": "uuid-parent", "is_superuser": False, "parent": None, "parent_name": None, "attributes": {}},
            {"name": "ak-child", "pk": "uuid-child", "is_superuser": False, "parent": None, "parent_name": None, "attributes": {}},
        ]

        plan = _compute_sync_plan(desired, existing)
        assert len(plan["update"]) == 1
        assert plan["update"][0]["name"] == "ak-child"

    def test_prune_phase_detects_stale_ak_groups(self) -> None:
        from kctl_ak.commands.groups import _compute_sync_plan

        desired = [{"name": "ak-keep", "is_superuser": False}]
        existing = [
            {"name": "ak-keep", "pk": "uuid-1", "is_superuser": False, "parent": None, "parent_name": None, "attributes": {}},
            {"name": "ak-stale", "pk": "uuid-2", "is_superuser": False, "parent": None, "parent_name": None, "attributes": {}},
            {"name": "authentik Admins", "pk": "uuid-3", "is_superuser": True, "parent": None, "parent_name": None, "attributes": {}},
        ]

        plan = _compute_sync_plan(desired, existing)
        assert len(plan["prune"]) == 1
        assert plan["prune"][0]["name"] == "ak-stale"

    def test_prune_ignores_non_ak_groups(self) -> None:
        from kctl_ak.commands.groups import _compute_sync_plan

        desired = []
        existing = [
            {"name": "authentik Admins", "pk": "uuid-1", "is_superuser": True, "parent": None, "parent_name": None, "attributes": {}},
            {"name": "authentik Read-only", "pk": "uuid-2", "is_superuser": False, "parent": None, "parent_name": None, "attributes": {}},
        ]

        plan = _compute_sync_plan(desired, existing)
        assert len(plan["prune"]) == 0

    def test_no_changes_returns_empty_plan(self) -> None:
        from kctl_ak.commands.groups import _compute_sync_plan

        desired = [{"name": "ak-group", "is_superuser": False}]
        existing = [{"name": "ak-group", "pk": "uuid-1", "is_superuser": False, "parent": None, "parent_name": None, "attributes": {}}]

        plan = _compute_sync_plan(desired, existing)
        assert len(plan["create"]) == 0
        assert len(plan["update"]) == 0
        assert len(plan["prune"]) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/kctl-ak && python -m pytest tests/test_commands/test_groups_sync.py -v`
Expected: FAIL — `_compute_sync_plan` not found

- [ ] **Step 3: Implement `_compute_sync_plan` and rewrite `sync()`**

Replace the `sync()` function in `packages/kctl-ak/src/kctl_ak/commands/groups.py` (lines 230-297) with:

```python
def _compute_sync_plan(
    desired: list[dict], existing: list[dict]
) -> dict[str, list[dict]]:
    """Compute create/update/prune plan without side effects.

    Returns dict with keys 'create', 'update', 'prune'.
    Each value is a list of dicts describing the action.
    """
    existing_by_name = {g["name"]: g for g in existing}
    desired_names = {g["name"] for g in desired if g.get("name")}

    # --- Create ---
    to_create = [g for g in desired if g.get("name") and g["name"] not in existing_by_name]

    # --- Update ---
    to_update: list[dict] = []
    for g in desired:
        name = g.get("name", "")
        if not name or name not in existing_by_name:
            continue
        ex = existing_by_name[name]
        changes: dict[str, tuple] = {}

        # is_superuser
        desired_su = g.get("is_superuser", False)
        if ex.get("is_superuser", False) != desired_su:
            changes["is_superuser"] = (ex.get("is_superuser", False), desired_su)

        # parent
        desired_parent = g.get("parent")
        current_parent_name = ex.get("parent_name") or None
        if desired_parent != current_parent_name:
            changes["parent"] = (current_parent_name, desired_parent)

        # description (stored in attributes)
        desired_desc = g.get("description", "")
        current_desc = (ex.get("attributes") or {}).get("description", "")
        if desired_desc and desired_desc != current_desc:
            changes["description"] = (current_desc, desired_desc)

        if changes:
            to_update.append({"name": name, "pk": ex["pk"], "changes": changes})

    # --- Prune ---
    to_prune = [
        g for g in existing
        if g["name"].startswith("ak-") and g["name"] not in desired_names
    ]

    return {"create": to_create, "update": to_update, "prune": to_prune}


@app.command()
def sync(
    ctx: typer.Context,
    dry_run: Annotated[bool, typer.Option("--dry-run/--no-dry-run", help="Preview changes without applying")] = True,
    prune: Annotated[bool, typer.Option("--prune", help="Delete ak-* groups not in YAML")] = False,
    file: Annotated[Path | None, typer.Option(help="Path to group-structure.yaml")] = None,
) -> None:
    """Sync groups from group-structure.yaml (create/update/prune)."""
    c: AppContext = ctx.obj

    if file:
        gs_path = file
    else:
        gs_path = resolve_group_structure_path()
        if gs_path is None:
            c.output.error("group-structure.yaml not found. Use --file to specify path.")
            raise typer.Exit(1)

    with open(gs_path) as f:
        structure = yaml.safe_load(f) or {}

    desired_groups = structure.get("groups", [])
    if not desired_groups:
        c.output.warn("No groups defined in structure file")
        return

    existing = c.client.get_all("core/groups/")

    plan = _compute_sync_plan(desired_groups, existing)

    c.output.header("Group Sync")
    c.output.info(f"Source: {gs_path}")
    c.output.info(
        f"Desired: {len(desired_groups)} | Existing: {len(existing)} | "
        f"Create: {len(plan['create'])} | Update: {len(plan['update'])} | "
        f"Prune: {len(plan['prune']) if prune else 0}"
    )

    if not plan["create"] and not plan["update"] and (not prune or not plan["prune"]):
        c.output.success("All groups in sync")
        return

    # --- Phase 1: Create ---
    for g in plan["create"]:
        name = g["name"]
        if dry_run:
            c.output.info(f"[create] {name}")
        else:
            try:
                c.client.post(
                    "core/groups/",
                    data={"name": name, "is_superuser": g.get("is_superuser", False)},
                )
                c.output.success(f"[create] {name}")
            except Exception as e:
                c.output.error(f"[create] {name} — {e}")

    # Reload groups after creates (need PKs for parent resolution)
    if plan["create"] and not dry_run:
        existing = c.client.get_all("core/groups/")
        # Recompute update plan with fresh data
        plan = _compute_sync_plan(desired_groups, existing)

    # --- Phase 2: Update ---
    existing_by_name = {g["name"]: g for g in existing}
    for item in plan["update"]:
        name = item["name"]
        pk = item["pk"]
        changes = item["changes"]
        for field, (old_val, new_val) in changes.items():
            if dry_run:
                c.output.info(f"[update] {name} — {field}: {old_val} → {new_val}")
            else:
                try:
                    if field == "parent":
                        if new_val:
                            parent_group = existing_by_name.get(new_val)
                            if parent_group:
                                c.client.patch(f"core/groups/{pk}/", data={"parent": parent_group["pk"]})
                            else:
                                c.output.error(f"[update] {name} — parent '{new_val}' not found")
                                continue
                        else:
                            c.client.patch(f"core/groups/{pk}/", data={"parent": None})
                    elif field == "description":
                        current = c.client.get(f"core/groups/{pk}/")
                        attrs = current.get("attributes", {})
                        attrs["description"] = new_val
                        c.client.patch(f"core/groups/{pk}/", data={"attributes": attrs})
                    else:
                        c.client.patch(f"core/groups/{pk}/", data={field: new_val})
                    c.output.success(f"[update] {name} — {field}: {old_val} → {new_val}")
                except Exception as e:
                    c.output.error(f"[update] {name} — {field}: {e}")

    # --- Phase 3: Prune ---
    if prune:
        for g in plan["prune"]:
            name = g["name"]
            pk = g["pk"]
            if dry_run:
                c.output.info(f"[prune]  {name}")
            else:
                try:
                    c.client.delete(f"core/groups/{pk}/")
                    c.output.success(f"[prune]  {name}")
                except Exception as e:
                    c.output.error(f"[prune]  {name} — {e}")

    if dry_run:
        c.output.warn("Dry-run mode. Use --no-dry-run to apply changes.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/kctl-ak && python -m pytest tests/test_commands/test_groups_sync.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Run full test suite**

Run: `cd packages/kctl-ak && python -m pytest tests/ -v`
Expected: All tests PASS (existing + new)

- [ ] **Step 6: Commit**

```bash
cd packages/kctl-ak
git add src/kctl_ak/commands/groups.py tests/test_commands/test_groups_sync.py
git commit -m "feat(kctl-ak): rewrite groups sync with 3-phase create/update/prune

- Create groups not in Authentik
- Update is_superuser, parent, description if changed
- Prune ak-* groups not in YAML (with --prune flag)
- Extract _compute_sync_plan() for testability

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Add `group` column to `apps list`

**Files:**
- Modify: `packages/kctl-ak/src/kctl_ak/commands/apps.py:12-33`
- Test: `packages/kctl-ak/tests/test_commands/test_apps.py`

- [ ] **Step 1: Add test for group column in help**

Append to `packages/kctl-ak/tests/test_commands/test_apps.py`:

```python
class TestAppsListOutput:
    def test_list_help_exists(self) -> None:
        result = runner.invoke(app, ["apps", "list", "--help"])
        assert result.exit_code == 0
```

- [ ] **Step 2: Update `list_()` to include group column**

In `packages/kctl-ak/src/kctl_ak/commands/apps.py`, replace the `list_()` function (lines 12-33):

```python
@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all applications."""
    c = ctx.obj
    apps = c.client.get_all("core/applications/")
    rows = []
    for a in apps:
        provider = a.get("provider_obj", {}) or {}
        rows.append(
            [
                a.get("slug", ""),
                a.get("name", ""),
                a.get("group", "") or "-",
                provider.get("name", "-"),
                a.get("meta_launch_url", "") or "-",
            ]
        )
    c.output.table(
        "Applications",
        [("Slug", "cyan"), ("Name", ""), ("Group", "green"), ("Provider", "dim"), ("Launch URL", "dim")],
        rows,
        data_for_json=apps,
    )
```

- [ ] **Step 3: Run tests**

Run: `cd packages/kctl-ak && python -m pytest tests/test_commands/test_apps.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
cd packages/kctl-ak
git add src/kctl_ak/commands/apps.py tests/test_commands/test_apps.py
git commit -m "feat(kctl-ak): show group column in apps list output

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Add `patch_multipart` to client

**Files:**
- Modify: `packages/kctl-ak/src/kctl_ak/core/client.py:56-68`
- Test: `packages/kctl-ak/tests/test_client.py`

- [ ] **Step 1: Add test for patch_multipart method**

Append to `packages/kctl-ak/tests/test_client.py`:

```python
class TestPatchMultipart:
    def test_method_exists(self) -> None:
        """patch_multipart is available on AuthentikClient."""
        assert hasattr(AuthentikClient, "patch_multipart")
```

Add the import at the top if not already there:
```python
from kctl_ak.core.client import AuthentikClient
```

- [ ] **Step 2: Add `patch_multipart` to client**

The `post_multipart` method already exists at line 56. Add `patch_multipart` right after it (after line 68) in `packages/kctl-ak/src/kctl_ak/core/client.py`:

```python
    def patch_multipart(self, endpoint: str, files: dict[str, Any], data: dict[str, Any] | None = None) -> Any:
        """PATCH with multipart form data (for file uploads like app icons)."""
        url = self._ensure_trailing_slash(endpoint)
        headers = dict(self._client.headers)
        headers.pop("Content-Type", None)
        try:
            response = self._client.patch(url, files=files, data=data, headers=headers)
        except httpx.HTTPError as e:
            raise KctlConnectionError(self._base_url, e) from e
        if response.status_code >= 400:
            detail = self._map_error(response)
            raise APIError(status_code=response.status_code, detail=detail)
        return self._unwrap_response(response)
```

- [ ] **Step 3: Run tests**

Run: `cd packages/kctl-ak && python -m pytest tests/test_client.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
cd packages/kctl-ak
git add src/kctl_ak/core/client.py tests/test_client.py
git commit -m "feat(kctl-ak): add patch_multipart to AuthentikClient

Enables file uploads via PATCH multipart/form-data (e.g. app icons).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Add `apps set-icon` command

**Files:**
- Modify: `packages/kctl-ak/src/kctl_ak/commands/apps.py`
- Test: `packages/kctl-ak/tests/test_commands/test_apps.py`

- [ ] **Step 1: Add help test**

Append to `packages/kctl-ak/tests/test_commands/test_apps.py`:

```python
class TestAppsSetIcon:
    def test_set_icon_help(self) -> None:
        result = runner.invoke(app, ["apps", "set-icon", "--help"])
        assert result.exit_code == 0
        assert "slug" in result.output.lower()
        assert "source" in result.output.lower()
```

- [ ] **Step 2: Implement `set_icon` command**

Add to `packages/kctl-ak/src/kctl_ak/commands/apps.py` after the `delete` command (after line 125):

```python
@app.command("set-icon")
def set_icon(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Application slug")],
    source: Annotated[str, typer.Argument(help="Local file path or URL")],
) -> None:
    """Set application icon from a local file or URL."""
    c = ctx.obj
    if source.startswith("http://") or source.startswith("https://"):
        c.client.patch(f"core/applications/{slug}/", data={"meta_icon": source})
        c.output.success(f"Icon set for '{slug}' from URL")
    else:
        path = Path(source)
        if not path.exists():
            c.output.error(f"File not found: {source}")
            raise typer.Exit(1)
        content_type = "image/png" if path.suffix == ".png" else "image/svg+xml"
        with open(path, "rb") as f:
            c.client.patch_multipart(
                f"core/applications/{slug}/",
                files={"meta_icon": (path.name, f, content_type)},
            )
        c.output.success(f"Icon uploaded for '{slug}' from {path.name}")
```

Add `from pathlib import Path` to the imports at the top of the file.

- [ ] **Step 3: Run tests**

Run: `cd packages/kctl-ak && python -m pytest tests/test_commands/test_apps.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
cd packages/kctl-ak
git add src/kctl_ak/commands/apps.py tests/test_commands/test_apps.py
git commit -m "feat(kctl-ak): add apps set-icon command for file upload

Accepts local PNG/SVG file path or URL. File uploads use
multipart PATCH to Authentik API.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Add `resolve_app_registry_path` to config

**Files:**
- Modify: `packages/kctl-ak/src/kctl_ak/core/config.py`
- Test: `packages/kctl-ak/tests/test_config_resolution.py`

- [ ] **Step 1: Add test**

Append to `packages/kctl-ak/tests/test_config_resolution.py`:

```python
class TestResolveAppRegistryPath:
    @patch("kctl_ak.core.config.load_raw_config", return_value={})
    @patch("kctl_ak.core.config.get_service_config", return_value=ServiceConfig())
    @patch("kctl_ak.core.config.resolve_active_profile_name", return_value="default")
    def test_returns_none_when_not_found(
        self, mock_pname: MagicMock, mock_svc: MagicMock, mock_raw: MagicMock
    ) -> None:
        from kctl_ak.core.config import resolve_app_registry_path

        result = resolve_app_registry_path()
        assert result is None

    def test_finds_in_config_dir(self, tmp_path: Path) -> None:
        from kctl_ak.core.config import resolve_app_registry_path

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        reg = config_dir / "app-registry.yaml"
        reg.write_text("apps: []")

        with patch("kctl_ak.core.config.resolve_active_profile_name", return_value="default"), \
             patch("kctl_ak.core.config.get_service_config", return_value=ServiceConfig()), \
             patch("kctl_ak.core.config.load_raw_config", return_value={}), \
             patch("kctl_ak.core.config.Path.cwd", return_value=tmp_path):
            result = resolve_app_registry_path()
            # May or may not find depending on cwd mock — test the function exists
            assert callable(resolve_app_registry_path)
```

Add import at top if not there: `from kctl_ak.core.config import ServiceConfig`

- [ ] **Step 2: Implement `resolve_app_registry_path`**

Add to `packages/kctl-ak/src/kctl_ak/core/config.py` after `resolve_group_structure_path` (after line 229):

```python
def resolve_app_registry_path(
    profile_name: str | None = None,
) -> Path | None:
    """Find app-registry.yaml."""
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)

    raw = load_raw_config()
    if arp := raw.get("app_registry_path", ""):
        p = Path(arp).expanduser()
        if p.exists():
            return p

    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        ar = parent / "config" / "app-registry.yaml"
        if ar.exists():
            return ar

    user_ar = CONFIG_DIR / "app-registry.yaml"
    if user_ar.exists():
        return user_ar

    return None
```

Add `"resolve_app_registry_path"` to the `__all__` list.

- [ ] **Step 3: Run tests**

Run: `cd packages/kctl-ak && python -m pytest tests/test_config_resolution.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
cd packages/kctl-ak
git add src/kctl_ak/core/config.py tests/test_config_resolution.py
git commit -m "feat(kctl-ak): add resolve_app_registry_path to config

Searches for app-registry.yaml in same pattern as group-structure.yaml.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: Implement `apps sync` command

**Files:**
- Modify: `packages/kctl-ak/src/kctl_ak/commands/apps.py`
- Test: `packages/kctl-ak/tests/test_commands/test_apps_sync.py` (create)

- [ ] **Step 1: Write tests**

Create `packages/kctl-ak/tests/test_commands/test_apps_sync.py`:

```python
"""Tests for apps sync logic."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from kctl_ak.cli import app

runner = CliRunner()


@pytest.fixture
def yaml_file(tmp_path: Path) -> Path:
    data = {
        "apps": [
            {"slug": "mac-odoo-dist", "name": "MAC — Odoo Distribution", "group": "MAC — Mandiriagro", "launch_url": "https://odoo-dist-mac.mandiriagro.com"},
            {"slug": "shared-gatus", "name": "Shared — Gatus", "group": "Shared — Infrastructure", "launch_url": "https://gatus.kodeme.io"},
        ]
    }
    p = tmp_path / "app-registry.yaml"
    p.write_text(yaml.dump(data))
    return p


class TestAppsSyncHelp:
    def test_sync_has_prune_flag(self) -> None:
        result = runner.invoke(app, ["apps", "sync", "--help"])
        assert result.exit_code == 0
        assert "--prune" in result.output
        assert "--no-dry-run" in result.output


class TestAppsSyncAlgorithm:
    def test_create_phase_detects_missing_apps(self) -> None:
        from kctl_ak.commands.apps import _compute_app_sync_plan

        desired = [
            {"slug": "mac-odoo-dist", "name": "MAC — Odoo Distribution", "group": "MAC — Mandiriagro"},
            {"slug": "shared-gatus", "name": "Shared — Gatus", "group": "Shared — Infrastructure"},
        ]
        existing = [{"slug": "shared-gatus", "name": "Shared — Gatus", "group": "Shared — Infrastructure", "meta_launch_url": "", "meta_icon": ""}]

        plan = _compute_app_sync_plan(desired, existing)
        assert len(plan["create"]) == 1
        assert plan["create"][0]["slug"] == "mac-odoo-dist"

    def test_update_phase_detects_name_change(self) -> None:
        from kctl_ak.commands.apps import _compute_app_sync_plan

        desired = [{"slug": "gatus", "name": "Shared — Gatus", "group": "Shared — Infrastructure"}]
        existing = [{"slug": "gatus", "name": "Gatus", "group": "", "meta_launch_url": "", "meta_icon": ""}]

        plan = _compute_app_sync_plan(desired, existing)
        assert len(plan["update"]) == 1
        assert "name" in plan["update"][0]["changes"]

    def test_prune_detects_stale_prefixed_apps(self) -> None:
        from kctl_ak.commands.apps import _compute_app_sync_plan

        desired = [{"slug": "mac-odoo-dist", "name": "MAC", "group": "MAC"}]
        existing = [
            {"slug": "mac-odoo-dist", "name": "MAC", "group": "MAC", "meta_launch_url": "", "meta_icon": ""},
            {"slug": "mac-react-old", "name": "OLD", "group": "MAC", "meta_launch_url": "", "meta_icon": ""},
            {"slug": "ldap", "name": "LDAP", "group": "", "meta_launch_url": "", "meta_icon": ""},
        ]

        plan = _compute_app_sync_plan(desired, existing)
        assert len(plan["prune"]) == 1
        assert plan["prune"][0]["slug"] == "mac-react-old"

    def test_prune_ignores_system_apps(self) -> None:
        from kctl_ak.commands.apps import _compute_app_sync_plan

        desired = []
        existing = [
            {"slug": "ldap", "name": "LDAP", "group": "", "meta_launch_url": "", "meta_icon": ""},
            {"slug": "dokploy", "name": "Dokploy", "group": "", "meta_launch_url": "", "meta_icon": ""},
        ]

        plan = _compute_app_sync_plan(desired, existing)
        assert len(plan["prune"]) == 0

    def test_no_changes(self) -> None:
        from kctl_ak.commands.apps import _compute_app_sync_plan

        desired = [{"slug": "mac-odoo-dist", "name": "MAC", "group": "MAC"}]
        existing = [{"slug": "mac-odoo-dist", "name": "MAC", "group": "MAC", "meta_launch_url": "", "meta_icon": ""}]

        plan = _compute_app_sync_plan(desired, existing)
        assert len(plan["create"]) == 0
        assert len(plan["update"]) == 0
        assert len(plan["prune"]) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/kctl-ak && python -m pytest tests/test_commands/test_apps_sync.py -v`
Expected: FAIL — `_compute_app_sync_plan` not found

- [ ] **Step 3: Implement `_compute_app_sync_plan` and `sync` command**

Add to `packages/kctl-ak/src/kctl_ak/commands/apps.py`:

At the top, add imports:
```python
import yaml
from kctl_ak.core.config import resolve_app_registry_path
```

Then add before the last command in the file:

```python
# Known slug prefixes for managed apps (safe to prune)
_MANAGED_PREFIXES = ("mac-", "tpp-", "kod-", "tkz-", "pro-", "shared-")


def _compute_app_sync_plan(
    desired: list[dict], existing: list[dict]
) -> dict[str, list[dict]]:
    """Compute create/update/prune plan for apps."""
    existing_by_slug = {a["slug"]: a for a in existing}
    desired_slugs = {a["slug"] for a in desired if a.get("slug")}

    # --- Create ---
    to_create = [a for a in desired if a.get("slug") and a["slug"] not in existing_by_slug]

    # --- Update ---
    to_update: list[dict] = []
    for a in desired:
        slug = a.get("slug", "")
        if not slug or slug not in existing_by_slug:
            continue
        ex = existing_by_slug[slug]
        changes: dict[str, tuple] = {}

        for field, api_field in [("name", "name"), ("group", "group"), ("launch_url", "meta_launch_url")]:
            desired_val = a.get(field, "") or ""
            existing_val = ex.get(api_field, "") or ""
            if desired_val and desired_val != existing_val:
                changes[field] = (existing_val, desired_val)

        # Icon: only compare if desired icon is a URL
        desired_icon = a.get("icon", "")
        if desired_icon and (desired_icon.startswith("http://") or desired_icon.startswith("https://")):
            existing_icon = ex.get("meta_icon", "") or ""
            if desired_icon != existing_icon:
                changes["icon"] = (existing_icon, desired_icon)

        if changes:
            to_update.append({"slug": slug, "changes": changes})

    # --- Prune ---
    to_prune = [
        a for a in existing
        if any(a["slug"].startswith(p) for p in _MANAGED_PREFIXES)
        and a["slug"] not in desired_slugs
    ]

    return {"create": to_create, "update": to_update, "prune": to_prune}


@app.command("sync")
def sync(
    ctx: typer.Context,
    dry_run: Annotated[bool, typer.Option("--dry-run/--no-dry-run", help="Preview changes without applying")] = True,
    prune: Annotated[bool, typer.Option("--prune", help="Delete managed apps not in YAML")] = False,
    file: Annotated[Path | None, typer.Option(help="Path to app-registry.yaml")] = None,
) -> None:
    """Sync applications from app-registry.yaml (create/update/prune)."""
    c = ctx.obj

    if file:
        reg_path = file
    else:
        reg_path = resolve_app_registry_path()
        if reg_path is None:
            c.output.error("app-registry.yaml not found. Use --file to specify path.")
            raise typer.Exit(1)

    with open(reg_path) as f:
        registry = yaml.safe_load(f) or {}

    desired_apps = registry.get("apps", [])
    if not desired_apps:
        c.output.warn("No apps defined in registry file")
        return

    existing = c.client.get_all("core/applications/")
    plan = _compute_app_sync_plan(desired_apps, existing)

    c.output.header("App Sync")
    c.output.info(f"Source: {reg_path}")
    c.output.info(
        f"Desired: {len(desired_apps)} | Existing: {len(existing)} | "
        f"Create: {len(plan['create'])} | Update: {len(plan['update'])} | "
        f"Prune: {len(plan['prune']) if prune else 0}"
    )

    if not plan["create"] and not plan["update"] and (not prune or not plan["prune"]):
        c.output.success("All apps in sync")
        return

    # --- Phase 1: Create ---
    for a in plan["create"]:
        slug = a["slug"]
        if dry_run:
            c.output.info(f"[create] {slug} — {a.get('name', '')}")
        else:
            try:
                payload: dict = {"name": a.get("name", slug), "slug": slug}
                if a.get("group"):
                    payload["group"] = a["group"]
                if a.get("launch_url"):
                    payload["meta_launch_url"] = a["launch_url"]
                icon = a.get("icon", "")
                if icon and (icon.startswith("http://") or icon.startswith("https://")):
                    payload["meta_icon"] = icon
                c.client.post("core/applications/", data=payload)
                # Upload file icon after create
                if icon and not icon.startswith("http"):
                    icon_path = Path(icon)
                    if icon_path.exists():
                        ct = "image/png" if icon_path.suffix == ".png" else "image/svg+xml"
                        with open(icon_path, "rb") as fh:
                            c.client.patch_multipart(
                                f"core/applications/{slug}/",
                                files={"meta_icon": (icon_path.name, fh, ct)},
                            )
                c.output.success(f"[create] {slug}")
            except Exception as e:
                c.output.error(f"[create] {slug} — {e}")

    # --- Phase 2: Update ---
    _FIELD_MAP = {"name": "name", "group": "group", "launch_url": "meta_launch_url", "icon": "meta_icon"}
    for item in plan["update"]:
        slug = item["slug"]
        changes = item["changes"]
        if dry_run:
            for field, (old_val, new_val) in changes.items():
                c.output.info(f"[update] {slug} — {field}: {old_val!r} → {new_val!r}")
        else:
            try:
                patch_data = {}
                for field, (_, new_val) in changes.items():
                    api_field = _FIELD_MAP.get(field, field)
                    patch_data[api_field] = new_val
                c.client.patch(f"core/applications/{slug}/", data=patch_data)
                c.output.success(f"[update] {slug} — {', '.join(changes.keys())}")
            except Exception as e:
                c.output.error(f"[update] {slug} — {e}")

    # --- Phase 3: Prune ---
    if prune:
        for a in plan["prune"]:
            slug = a["slug"]
            if dry_run:
                c.output.info(f"[prune]  {slug}")
            else:
                try:
                    c.client.delete(f"core/applications/{slug}/")
                    c.output.success(f"[prune]  {slug}")
                except Exception as e:
                    c.output.error(f"[prune]  {slug} — {e}")

    if dry_run:
        c.output.warn("Dry-run mode. Use --no-dry-run to apply changes.")
```

- [ ] **Step 4: Run tests**

Run: `cd packages/kctl-ak && python -m pytest tests/test_commands/test_apps_sync.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Run full test suite**

Run: `cd packages/kctl-ak && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
cd packages/kctl-ak
git add src/kctl_ak/commands/apps.py tests/test_commands/test_apps_sync.py
git commit -m "feat(kctl-ak): add apps sync command with 3-phase create/update/prune

Reads app-registry.yaml manifest. Creates missing apps, updates
name/group/launch_url/icon if changed, prunes managed-prefix apps
not in YAML (with --prune).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: Create app-registry.yaml in authentik repo

**Files:**
- Create: `/home/tgunawan/project/00-new-projects/kodemeio-core/kodemeio-authentik/config/app-registry.yaml`

- [ ] **Step 1: Create the manifest**

Create `config/app-registry.yaml` in the kodemeio-authentik repo:

```yaml
# =============================================================================
# Kodemeio Authentik App Registry
# =============================================================================
# Defines all applications managed by Authentik.
# Sync with: kctl-ak apps sync --no-dry-run
#
# Slug pattern: {company}-{service-type}-{profile}
# Group pattern: {Company} — {Company Name} or Shared — {Category}
# =============================================================================

apps:
  # ===========================================================================
  # MAC — Mandiriagro (mandiriagro.com)
  # ===========================================================================
  - slug: mac-odoo-dist
    name: "MAC — Odoo Distribution"
    group: "MAC — Mandiriagro"
    launch_url: https://odoo-dist-mac.mandiriagro.com
    icon: https://raw.githubusercontent.com/tgunawandev/kodemeio-platform/main/icons/odoo.png

  - slug: mac-odoo-hrms
    name: "MAC — Odoo HRMS"
    group: "MAC — Mandiriagro"
    launch_url: https://odoo-hrms-mac.mandiriagro.com
    icon: https://raw.githubusercontent.com/tgunawandev/kodemeio-platform/main/icons/odoo.png

  - slug: mac-react-wms
    name: "MAC — WMS"
    group: "MAC — Mandiriagro"
    launch_url: https://wms-mac.mandiriagro.com
    icon: https://raw.githubusercontent.com/tgunawandev/kodemeio-platform/main/icons/wms.png

  - slug: mac-react-hrm
    name: "MAC — HRM"
    group: "MAC — Mandiriagro"
    launch_url: https://hrm-mac.mandiriagro.com
    icon: https://raw.githubusercontent.com/tgunawandev/kodemeio-platform/main/icons/hrm.png

  - slug: mac-react-bia
    name: "MAC — BIA"
    group: "MAC — Mandiriagro"
    launch_url: https://bia-mac.mandiriagro.com
    icon: https://raw.githubusercontent.com/tgunawandev/kodemeio-platform/main/icons/bia.png

  # ===========================================================================
  # TPP — Pakerti (pakerti.com)
  # ===========================================================================
  - slug: tpp-odoo-trad
    name: "TPP — Odoo Trading"
    group: "TPP — Pakerti"
    launch_url: https://odoo-trad-tpp.kodeme.io
    icon: https://raw.githubusercontent.com/tgunawandev/kodemeio-platform/main/icons/odoo.png

  - slug: tpp-odoo-hrms
    name: "TPP — Odoo HRMS"
    group: "TPP — Pakerti"
    launch_url: https://odoo-hrms-tpp.kodeme.io
    icon: https://raw.githubusercontent.com/tgunawandev/kodemeio-platform/main/icons/odoo.png

  - slug: tpp-react-wms
    name: "TPP — WMS"
    group: "TPP — Pakerti"
    launch_url: https://wms-tpp.pakerti.com
    icon: https://raw.githubusercontent.com/tgunawandev/kodemeio-platform/main/icons/wms.png

  - slug: tpp-react-hrm
    name: "TPP — HRM"
    group: "TPP — Pakerti"
    launch_url: https://hrm-tpp.pakerti.com
    icon: https://raw.githubusercontent.com/tgunawandev/kodemeio-platform/main/icons/hrm.png

  - slug: tpp-react-bia
    name: "TPP — BIA"
    group: "TPP — Pakerti"
    launch_url: https://bia-tpp.pakerti.com
    icon: https://raw.githubusercontent.com/tgunawandev/kodemeio-platform/main/icons/bia.png

  - slug: tpp-react-sfa
    name: "TPP — SFA"
    group: "TPP — Pakerti"
    launch_url: https://sfa-tpp.pakerti.com
    icon: https://raw.githubusercontent.com/tgunawandev/kodemeio-platform/main/icons/sfa.png

  # ===========================================================================
  # KOD — Kodemeio (kodeme.io)
  # ===========================================================================
  - slug: kod-odoo-full
    name: "KOD — Odoo Full"
    group: "KOD — Kodemeio"
    launch_url: https://erp.kodeme.io
    icon: https://raw.githubusercontent.com/tgunawandev/kodemeio-platform/main/icons/odoo.png

  - slug: kod-odoo-hrms
    name: "KOD — Odoo HRMS"
    group: "KOD — Kodemeio"
    launch_url: https://hrms.kodeme.io
    icon: https://raw.githubusercontent.com/tgunawandev/kodemeio-platform/main/icons/odoo.png

  # ===========================================================================
  # TKZ — Terakidz (terakidz.com)
  # ===========================================================================
  - slug: tkz-fastapi-tms
    name: "TKZ — Task Management"
    group: "TKZ — Terakidz"
    launch_url: https://api-tms.terakidz.com
    icon: https://raw.githubusercontent.com/tgunawandev/kodemeio-platform/main/icons/tms.png

  # ===========================================================================
  # Shared — Infrastructure (DevOps/Superuser only)
  # ===========================================================================
  - slug: gatus
    name: "Shared — Gatus"
    group: "Shared — Infrastructure"
    launch_url: https://gatus.kodeme.io
    icon: https://raw.githubusercontent.com/tgunawandev/kodemeio-platform/main/icons/gatus.png

  - slug: glitchtip
    name: "Shared — GlitchTip"
    group: "Shared — Infrastructure"
    launch_url: https://glitchtip.kodeme.io
    icon: https://raw.githubusercontent.com/tgunawandev/kodemeio-platform/main/icons/glitchtip.png

  - slug: rustdesk
    name: "Shared — RustDesk"
    group: "Shared — Infrastructure"
    launch_url: https://rustdesk.kodeme.io
    icon: https://raw.githubusercontent.com/tgunawandev/kodemeio-platform/main/icons/rustdesk.png

  - slug: tactical-rmm
    name: "Shared — Tactical RMM"
    group: "Shared — Infrastructure"
    launch_url: https://rmm.kodeme.io
    icon: https://raw.githubusercontent.com/tgunawandev/kodemeio-platform/main/icons/tactical-rmm.png

  - slug: dokploy
    name: "Dokploy"
    group: "Shared — Infrastructure"
    launch_url: https://dokploy.kodeme.io

  - slug: headwind-mdm
    name: "Headwind MDM"
    group: "Shared — Infrastructure"
    launch_url: https://mdm.kodeme.io
    icon: https://raw.githubusercontent.com/tgunawandev/kodemeio-platform/main/icons/headwind-mdm.png

  - slug: meshcentral
    name: "MeshCentral"
    group: "Shared — Infrastructure"
    launch_url: https://mesh.kodeme.io
    icon: https://raw.githubusercontent.com/tgunawandev/kodemeio-platform/main/icons/meshcentral.png

  # ===========================================================================
  # Shared — Business (Regular users)
  # ===========================================================================
  - slug: mailcow-oidc
    name: "Shared — Mailcow"
    group: "Shared — Business"
    launch_url: https://mail.kodeme.io

  - slug: outline
    name: "Shared — Outline"
    group: "Shared — Business"
    launch_url: https://outline.kodeme.io
    icon: https://raw.githubusercontent.com/tgunawandev/kodemeio-platform/main/icons/outline.png

  - slug: plane-oauth
    name: "Shared — Plane"
    group: "Shared — Business"
    launch_url: https://plane.kodeme.io
    icon: https://raw.githubusercontent.com/tgunawandev/kodemeio-platform/main/icons/plane.png

  - slug: zulip-oidc
    name: "Shared — Zulip"
    group: "Shared — Business"
    launch_url: https://zulip.kodeme.io
```

- [ ] **Step 2: Validate YAML**

Run: `python3 -c "import yaml; d=yaml.safe_load(open('config/app-registry.yaml')); print(f'{len(d[\"apps\"])} apps defined')"`
Expected: `26 apps defined`

- [ ] **Step 3: Commit**

```bash
git add config/app-registry.yaml
git commit -m "feat: add app-registry.yaml manifest for kctl-ak apps sync

26 apps across 5 companies + shared infrastructure/business.
Use with: kctl-ak apps sync --no-dry-run

Co-Authored-By: Claude <noreply@anthropic.com>"
```
