# Rename kctl-cf → kctl-cf Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the `kctl-cf` package to `kctl-cf` (distribution name) / `kctl_cf` (Python import name) while preserving all functionality.

**Architecture:** Pure rename — directory `packages/kctl-cf` → `packages/kctl-cf`, Python package `kctl_cf` → `kctl_cf`, CLI command `kctl-cf` → `kctl-cf`. All internal imports, pyproject.toml, docs, cross-package references, and skill files updated accordingly.

**Tech Stack:** Python 3.12, Typer, Hatchling, uv workspace

---

## File Map

### Renamed/Moved
| From | To |
|------|-----|
| `packages/kctl-cf/` | `packages/kctl-cf/` |
| `packages/kctl-cf/src/kctl_cf/` | `packages/kctl-cf/src/kctl_cf/` |

### Modified In-Place (after move)
| File | Change |
|------|--------|
| `packages/kctl-cf/pyproject.toml` | name, script entry, plugin entry, wheel packages |
| `packages/kctl-cf/src/kctl_cf/cli.py` | Typer app name + 32 `kctl_cf` imports |
| `packages/kctl-cf/src/kctl_cf/__main__.py` | 2 imports |
| `packages/kctl-cf/src/kctl_cf/core/callbacks.py` | 2 imports |
| `packages/kctl-cf/src/kctl_cf/core/plugins.py` | 3 imports + entry point namespace string |
| `packages/kctl-cf/src/kctl_cf/core/utils.py` | 1 import |
| `packages/kctl-cf/src/kctl_cf/commands/*.py` | 2-4 imports each (24 files) |
| `packages/kctl-cf/tests/conftest.py` | 1 import |
| `packages/kctl-cf/tests/test_commands.py` | 74 occurrences |
| `packages/kctl-cf/tests/test_output.py` | 1 import |
| `packages/kctl-cf/tests/test_smoke.py` | check if references exist |
| `packages/kctl-cf/README.md` | CLI name references |
| `packages/kctl-cf/skills/cloudflare-admin/SKILL.md` | All `kctl-cf` command references |
| `CLAUDE.md` | 2 references |
| `README.md` | 1 reference |
| `packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py` | 3 subprocess references |
| `packages/kctl-dokploy/tests/core/test_deployer.py` | 1 reference |
| `templates/deploy-manifest/deploy.yaml.example` | 1 comment |

### Regenerated
| File | Change |
|------|--------|
| `uv.lock` | Regenerated via `uv lock` after rename |

### Documentation (non-blocking, update for accuracy)
| File | Change |
|------|--------|
| `docs/superpowers/specs/2026-03-31-deployment-manifest-design.md` | References |
| `docs/superpowers/specs/2026-03-29-kctl-standardization-design.md` | References |
| `docs/superpowers/plans/2026-03-31-deployment-manifest.md` | References |
| `docs/superpowers/plans/2026-03-29-kctl-standardization-phase2.md` | References |

---

### Task 1: Rename directory and Python package

**Files:**
- Move: `packages/kctl-cf/` → `packages/kctl-cf/`
- Move: `packages/kctl-cf/src/kctl_cf/` → `packages/kctl-cf/src/kctl_cf/`

- [ ] **Step 1: Rename the top-level package directory**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
git mv packages/kctl-cf packages/kctl-cf
```

- [ ] **Step 2: Rename the Python source package directory**

```bash
git mv packages/kctl-cf/src/kctl_cf packages/kctl-cf/src/kctl_cf
```

- [ ] **Step 3: Commit the directory renames**

```bash
git add packages/kctl-cf/
git commit -m "refactor(kctl-cf): rename directories kctl-cf → kctl-cf"
```

---

### Task 2: Update pyproject.toml

**Files:**
- Modify: `packages/kctl-cf/pyproject.toml`

- [ ] **Step 1: Update package name, script entry, plugin entry, and wheel config**

Change these 4 lines in `packages/kctl-cf/pyproject.toml`:

```toml
# Line 6: name
name = "kctl-cf"

# Line 30: console script
[project.scripts]
kctl-cf = "kctl_cf.cli:_run"

# Line 35: plugin entry point namespace
[project.entry-points."kctl_cf.plugins"]

# Line 38: wheel packages
packages = ["src/kctl_cf"]
```

- [ ] **Step 2: Verify pyproject.toml is valid**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
python -c "import tomllib; tomllib.load(open('packages/kctl-cf/pyproject.toml','rb')); print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add packages/kctl-cf/pyproject.toml
git commit -m "refactor(kctl-cf): update pyproject.toml for kctl-cf rename"
```

---

### Task 3: Find-and-replace all Python imports

**Files:**
- Modify: All `.py` files under `packages/kctl-cf/src/kctl_cf/` (30 files, 175 occurrences)
- Modify: All `.py` files under `packages/kctl-cf/tests/` (3 files)

- [ ] **Step 1: Replace all `kctl_cf` with `kctl_cf` in source files**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
find packages/kctl-cf/src/kctl_cf -name '*.py' -exec sed -i 's/kctl_cf/kctl_cf/g' {} +
```

- [ ] **Step 2: Replace all `kctl_cf` with `kctl_cf` in test files**

```bash
find packages/kctl-cf/tests -name '*.py' -exec sed -i 's/kctl_cf/kctl_cf/g' {} +
```

- [ ] **Step 3: Update Typer app name in cli.py**

In `packages/kctl-cf/src/kctl_cf/cli.py`, change the Typer name:

```python
# Change: name="kctl-cf"
# To:     name="kctl-cf"
```

Also replace any `"kctl-cf"` string literals (help text, error messages) with `"kctl-cf"`.

- [ ] **Step 4: Update plugin entry point string in core/plugins.py**

In `packages/kctl-cf/src/kctl_cf/core/plugins.py`, if there's a hardcoded entry point namespace string:

```python
# Change: "kctl_cf.plugins"
# To:     "kctl_cf.plugins"
```

- [ ] **Step 5: Verify no remaining references to old name**

```bash
grep -r "kctl_cf" packages/kctl-cf/ || echo "Clean!"
grep -r "kctl-cf" packages/kctl-cf/src/ packages/kctl-cf/tests/ || echo "Clean!"
```

Expected: `Clean!` for both (SKILL.md and README.md may still have references — handled in Task 5)

- [ ] **Step 6: Commit**

```bash
git add packages/kctl-cf/
git commit -m "refactor(kctl-cf): rename all Python imports kctl_cf → kctl_cf"
```

---

### Task 4: Update cross-package references

**Files:**
- Modify: `packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py` (lines 143, 151)
- Modify: `packages/kctl-dokploy/tests/core/test_deployer.py` (line 226)
- Modify: `templates/deploy-manifest/deploy.yaml.example` (line 35)

- [ ] **Step 1: Update deployer.py subprocess calls**

In `packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py`, replace all `"kctl-cf"` strings with `"kctl-cf"`:

```python
# Line 143: change ["kctl-cf", "records", "list", ...] → ["kctl-cf", "records", "list", ...]
# Line 151: change "kctl-cf" → "kctl-cf"
```

- [ ] **Step 2: Update deployer test**

In `packages/kctl-dokploy/tests/core/test_deployer.py`, replace `kctl-cf` references with `kctl-cf`.

- [ ] **Step 3: Update deploy template**

In `templates/deploy-manifest/deploy.yaml.example`, change comment:
```yaml
# DNS Records (via kctl-cf)
```

- [ ] **Step 4: Commit**

```bash
git add packages/kctl-dokploy/ templates/
git commit -m "refactor(kctl-cf): update cross-package references kctl-cf → kctl-cf"
```

---

### Task 5: Update documentation

**Files:**
- Modify: `CLAUDE.md` (lines 38, 71)
- Modify: `README.md` (line 60)
- Modify: `packages/kctl-cf/README.md`
- Modify: `packages/kctl-cf/skills/cloudflare-admin/SKILL.md`
- Modify: `docs/superpowers/specs/2026-03-31-deployment-manifest-design.md`
- Modify: `docs/superpowers/specs/2026-03-29-kctl-standardization-design.md`
- Modify: `docs/superpowers/plans/2026-03-31-deployment-manifest.md`
- Modify: `docs/superpowers/plans/2026-03-29-kctl-standardization-phase2.md`

- [ ] **Step 1: Update CLAUDE.md**

```markdown
# Line 38: change "kctl-cf" → "kctl-cf"
- **kctl-cf** — Cloudflare DNS/CDN/WAF (27 groups)

# Line 71: change path and name
| `packages/kctl-cf/` | Cloudflare DNS/CDN/WAF CLI |
```

- [ ] **Step 2: Update root README.md**

```markdown
# Line 60:
| kctl-cf | kodemeio-cloudflare | Cloudflare DNS/CDN/WAF | 27 |
```

- [ ] **Step 3: Update package README.md**

Replace all `kctl-cf` with `kctl-cf` in `packages/kctl-cf/README.md`.

- [ ] **Step 4: Update SKILL.md**

Replace all `kctl-cf` with `kctl-cf` in `packages/kctl-cf/skills/cloudflare-admin/SKILL.md`. This includes:
- All command examples (`kctl-cf zones list`, `kctl-cf records create`, etc.)
- Installation instructions
- Trigger keywords

- [ ] **Step 5: Update docs/superpowers/ references**

In the 4 docs files, replace `kctl-cf` → `kctl-cf` and `kctl_cf` → `kctl_cf`:

```bash
sed -i 's/kctl-cf/kctl-cf/g; s/kctl_cf/kctl_cf/g' \
  docs/superpowers/specs/2026-03-31-deployment-manifest-design.md \
  docs/superpowers/specs/2026-03-29-kctl-standardization-design.md \
  docs/superpowers/plans/2026-03-31-deployment-manifest.md \
  docs/superpowers/plans/2026-03-29-kctl-standardization-phase2.md
```

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md README.md packages/kctl-cf/README.md packages/kctl-cf/skills/ docs/superpowers/
git commit -m "docs(kctl-cf): update all documentation references kctl-cf → kctl-cf"
```

---

### Task 6: Regenerate lockfile and verify

**Files:**
- Regenerate: `uv.lock`

- [ ] **Step 1: Regenerate the uv lockfile**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
uv lock
```

Expected: Lockfile regenerated with `kctl-cf` replacing `kctl-cf`.

- [ ] **Step 2: Install the package in dev mode**

```bash
uv sync --all-extras --all-packages
```

Expected: All packages install without errors.

- [ ] **Step 3: Verify the CLI entry point works**

```bash
uv run kctl-cf --version
```

Expected: Prints version `0.2.0`.

- [ ] **Step 4: Run the test suite**

```bash
uv run pytest packages/kctl-cf/tests/ -v
```

Expected: All tests pass.

- [ ] **Step 5: Run linting**

```bash
uv run ruff check packages/kctl-cf/src/
```

Expected: No errors.

- [ ] **Step 6: Final grep — no stale references anywhere**

```bash
grep -r "kctl.cloudflare" packages/kctl-cf/src/ packages/kctl-cf/tests/ packages/kctl-cf/pyproject.toml packages/kctl-dokploy/src/ CLAUDE.md README.md templates/ || echo "All clean!"
```

Expected: `All clean!`

- [ ] **Step 7: Commit lockfile**

```bash
git add uv.lock
git commit -m "chore(kctl-cf): regenerate uv.lock after rename"
```

---

## Summary of Changes

| Category | Count |
|----------|-------|
| Directories renamed | 2 (package dir + src dir) |
| Python imports updated | ~175 occurrences across 35 files |
| pyproject.toml fields | 4 (name, script, plugins, wheel) |
| Cross-package refs | 3 files (deployer, deployer test, template) |
| Documentation files | 8 (CLAUDE.md, README.md, package README, SKILL.md, 4 docs/) |
| Generated files | 1 (uv.lock) |
