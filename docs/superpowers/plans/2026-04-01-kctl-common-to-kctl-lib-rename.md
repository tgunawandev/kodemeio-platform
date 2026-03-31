# Rename kctl-lib → kctl-lib Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the shared library from `kctl-lib` to `kctl-lib` — package name, Python module, directory, all imports, dependencies, CI/CD, docs, and templates.

**Architecture:** This is a mechanical rename across the entire monorepo. The PyPI package name changes from `kctl-lib` to `kctl-lib`, the Python import changes from `kctl_lib` to `kctl_lib`, and the directory moves from `packages/kctl-lib/` to `packages/kctl-lib/`. Version bumps to `0.4.0` since this is a breaking change for any external consumers.

**Tech Stack:** Python 3.12+, uv workspace, Hatchling build, GitHub Actions CI/CD

---

## Impact Summary

| What | Count |
|------|-------|
| Directory rename | 1 (`packages/kctl-lib/` → `packages/kctl-lib/`) |
| Python module rename | 1 (`src/kctl_lib/` → `src/kctl_lib/`) |
| Dependent `pyproject.toml` files | 22 |
| Python files with imports | ~216 |
| CI/CD workflow files | 2 |
| Copier template files | ~6 |
| Documentation files | ~7 |

---

### Task 1: Rename the core package directory and module

**Files:**
- Rename: `packages/kctl-lib/` → `packages/kctl-lib/`
- Rename: `packages/kctl-lib/src/kctl_lib/` → `packages/kctl-lib/src/kctl_lib/`
- Modify: `packages/kctl-lib/pyproject.toml`
- Modify: `packages/kctl-lib/src/kctl_lib/__init__.py`

- [ ] **Step 1: Rename the package directory**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
git mv packages/kctl-lib packages/kctl-lib
```

- [ ] **Step 2: Rename the Python module directory**

```bash
git mv packages/kctl-lib/src/kctl_lib packages/kctl-lib/src/kctl_lib
```

- [ ] **Step 3: Update pyproject.toml package name and version**

In `packages/kctl-lib/pyproject.toml`, change:
```toml
name = "kctl-lib"
version = "0.3.1"
description = "Shared core library for kctl-* CLI tools"
```
To:
```toml
name = "kctl-lib"
version = "0.4.0"
description = "Shared core library for kctl-* CLI tools"
```

- [ ] **Step 4: Update __init__.py version and all self-imports**

In `packages/kctl-lib/src/kctl_lib/__init__.py`, change:
- `__version__ = "0.3.1"` → `__version__ = "0.4.0"`
- All `from kctl_lib.` → `from kctl_lib.`
- Docstring: `"""kctl-lib:` → `"""kctl-lib:`

- [ ] **Step 5: Update all internal imports within kctl-lib**

Replace all `from kctl_lib` and `import kctl_lib` with `from kctl_lib` and `import kctl_lib` in every `.py` file under `packages/kctl-lib/src/kctl_lib/` and `packages/kctl-lib/tests/`:

```bash
find packages/kctl-lib/ -name '*.py' -exec sed -i 's/from kctl_lib/from kctl_lib/g; s/import kctl_lib/import kctl_lib/g' {} +
```

- [ ] **Step 6: Verify kctl-lib tests pass**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
uv sync --all-extras --all-packages
uv run pytest packages/kctl-lib/tests/ -v --tb=short
```

Expected: All 247 tests pass.

- [ ] **Step 7: Commit**

```bash
git add packages/kctl-lib/
git commit -m "refactor: rename kctl-lib to kctl-lib (core package)

Rename directory, Python module, bump version to 0.4.0.
All 247 internal tests updated."
```

---

### Task 2: Update all 22 dependent CLIs — pyproject.toml files

Each of the 22 CLI packages has two references in `pyproject.toml`:
1. `"kctl-lib>=0.4.0"` in `[project.dependencies]`
2. `kctl-lib = { workspace = true }` in `[tool.uv.sources]`

**Files (22 pyproject.toml files):**
- Modify: `packages/kctl-ak/pyproject.toml`
- Modify: `packages/kctl-api/pyproject.toml`
- Modify: `packages/kctl-claude/pyproject.toml`
- Modify: `packages/kctl-claw/pyproject.toml`
- Modify: `packages/kctl-cf/pyproject.toml`
- Modify: `packages/kctl-dokploy/pyproject.toml`
- Modify: `packages/kctl-gatus/pyproject.toml`
- Modify: `packages/kctl-github/pyproject.toml`
- Modify: `packages/kctl-glitchtip/pyproject.toml`
- Modify: `packages/kctl-grafana/pyproject.toml`
- Modify: `packages/kctl-hetzner/pyproject.toml`
- Modify: `packages/kctl-linear/pyproject.toml`
- Modify: `packages/kctl-notion/pyproject.toml`
- Modify: `packages/kctl-odoo/pyproject.toml`
- Modify: `packages/kctl-op/pyproject.toml`
- Modify: `packages/kctl-pg/pyproject.toml`
- Modify: `packages/kctl-react/pyproject.toml`
- Modify: `packages/kctl-rustdesk/pyproject.toml`
- Modify: `packages/kctl-sentry/pyproject.toml`
- Modify: `packages/kctl-telegram/pyproject.toml`
- Modify: `packages/kctl-waha/pyproject.toml`

- [ ] **Step 1: Batch replace in all dependent pyproject.toml files**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform

# Update dependency name (handles both >=0.3.0 and >=0.3.1 variants)
find packages/ -name 'pyproject.toml' -not -path 'packages/kctl-lib/*' \
  -exec sed -i 's/"kctl-lib>="/"kctl-lib>=/g' {} +

# Update version floor to 0.4.0
find packages/ -name 'pyproject.toml' -not -path 'packages/kctl-lib/*' \
  -exec sed -i 's/"kctl-lib>=0\.3\.[0-9]*"/"kctl-lib>=0.4.0"/g' {} +

# Update uv workspace source
find packages/ -name 'pyproject.toml' -not -path 'packages/kctl-lib/*' \
  -exec sed -i 's/kctl-lib = { workspace = true }/kctl-lib = { workspace = true }/g' {} +
```

- [ ] **Step 2: Verify changes look correct**

```bash
grep -r 'kctl-lib' packages/*/pyproject.toml
# Expected: no output (all references replaced)

grep -r 'kctl-lib' packages/*/pyproject.toml | head -10
# Expected: shows kctl-lib>=0.4.0 and workspace = true entries
```

- [ ] **Step 3: Commit**

```bash
git add packages/*/pyproject.toml
git commit -m "refactor: update all 22 CLIs to depend on kctl-lib>=0.4.0

Replace kctl-lib references in all pyproject.toml files."
```

---

### Task 3: Update all Python imports across 22 CLI packages

All `from kctl_lib` and `import kctl_lib` statements in every CLI's `src/` and `tests/` directories must change to `kctl_lib`.

**Files:** ~216 Python files across `packages/kctl-*/src/` and `packages/kctl-*/tests/`

- [ ] **Step 1: Batch replace all imports**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform

# Replace in all Python files under packages/ (excluding kctl-lib which was already done in Task 1)
find packages/ -name '*.py' -not -path 'packages/kctl-lib/*' \
  -exec sed -i 's/from kctl_lib/from kctl_lib/g; s/import kctl_lib/import kctl_lib/g' {} +
```

- [ ] **Step 2: Also replace any string references (e.g., in docstrings, comments)**

```bash
# Check for remaining string references
grep -r 'kctl_lib' packages/ --include='*.py' -l
# Expected: no output

grep -r 'kctl-lib' packages/ --include='*.py' -l
# Expected: no output (or only in comments that are fine to keep)
```

- [ ] **Step 3: Resync workspace and run a quick sanity check**

```bash
uv sync --all-extras --all-packages
uv run python -c "from kctl_lib import KctlError; print('Import OK')"
```

Expected: `Import OK`

- [ ] **Step 4: Run kctl-lib tests to confirm nothing broke**

```bash
uv run pytest packages/kctl-lib/tests/ -v --tb=short
```

Expected: All 247 tests pass.

- [ ] **Step 5: Run a sampling of CLI tests**

```bash
# Test a few representative CLIs
uv run pytest packages/kctl-ak/tests/ -v --tb=short 2>&1 | tail -5
uv run pytest packages/kctl-op/tests/ -v --tb=short 2>&1 | tail -5
uv run pytest packages/kctl-dokploy/tests/ -v --tb=short 2>&1 | tail -5
```

Expected: Tests pass for each sampled CLI.

- [ ] **Step 6: Commit**

```bash
git add packages/
git commit -m "refactor: replace all kctl_lib imports with kctl_lib

Updated ~216 Python files across 22 CLI packages."
```

---

### Task 4: Update CI/CD workflows

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/publish.yml`

- [ ] **Step 1: Update ci.yml**

Replace all occurrences of `packages/kctl-lib` with `packages/kctl-lib` and `kctl-lib` with `kctl-lib`:

```bash
sed -i 's|packages/kctl-lib|packages/kctl-lib|g; s|kctl-lib|kctl-lib|g' \
  .github/workflows/ci.yml
```

- [ ] **Step 2: Update publish.yml**

```bash
sed -i 's|packages/kctl-lib|packages/kctl-lib|g; s|kctl-lib|kctl-lib|g' \
  .github/workflows/publish.yml
```

- [ ] **Step 3: Verify the changes**

```bash
grep -n 'kctl-lib\|kctl_lib' .github/workflows/*.yml
# Expected: no output
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/
git commit -m "ci: update workflows for kctl-lib → kctl-lib rename"
```

---

### Task 5: Update Copier template

**Files:**
- Modify: `templates/kctl-cli/pyproject.toml.jinja`
- Modify: `templates/kctl-cli/src/{{package_name}}/core/config.py.jinja`
- Modify: `templates/kctl-cli/src/{{package_name}}/core/plugins.py.jinja`
- Modify: `templates/kctl-cli/src/{{package_name}}/core/exceptions.py.jinja`
- Modify: `templates/kctl-cli/src/{{package_name}}/core/callbacks.py.jinja`
- Modify: `templates/kctl-cli/src/{{package_name}}/cli.py.jinja`

- [ ] **Step 1: Batch replace in all template files**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform

find templates/kctl-cli/ -type f \( -name '*.jinja' -o -name '*.j2' -o -name '*.toml' -o -name '*.py' \) \
  -exec sed -i 's/kctl-lib/kctl-lib/g; s/kctl_lib/kctl_lib/g' {} +
```

- [ ] **Step 2: Update version floor in template pyproject.toml.jinja**

Verify `templates/kctl-cli/pyproject.toml.jinja` now shows `"kctl-lib>=0.4.0"` (not `>=0.3.0`).

```bash
grep 'kctl-lib' templates/kctl-cli/pyproject.toml.jinja
```

If it still says `>=0.3.0`, manually fix:
```bash
sed -i 's/kctl-lib>=0\.3\.0/kctl-lib>=0.4.0/' templates/kctl-cli/pyproject.toml.jinja
```

- [ ] **Step 3: Verify no remaining references**

```bash
grep -r 'kctl-lib\|kctl_lib' templates/
# Expected: no output
```

- [ ] **Step 4: Commit**

```bash
git add templates/
git commit -m "refactor: update copier template for kctl-lib rename"
```

---

### Task 6: Update documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/cli-standards.md`
- Modify: `docs/architecture.md`
- Modify: `docs/superpowers/specs/2026-03-29-kctl-service-clis-design.md`
- Modify: `docs/superpowers/specs/2026-03-30-kctl-saas-merge-design.md`
- Modify: `docs/superpowers/specs/2026-03-29-kctl-standardization-design.md`
- Modify: `docs/superpowers/plans/2026-03-30-kctl-saas-merge.md`

- [ ] **Step 1: Batch replace in all markdown docs**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform

# Replace in CLAUDE.md
sed -i 's/kctl-lib/kctl-lib/g; s/kctl_lib/kctl_lib/g' CLAUDE.md

# Replace in docs/
find docs/ -name '*.md' \
  -exec sed -i 's/kctl-lib/kctl-lib/g; s/kctl_lib/kctl_lib/g' {} +
```

- [ ] **Step 2: Update version references in CLAUDE.md**

Replace `v0.3.1` references for kctl-lib to `v0.4.0`:

```bash
# In CLAUDE.md, update the version references for kctl-lib specifically
sed -i 's/kctl-lib (v0\.3\.1/kctl-lib (v0.4.0/g; s/kctl-lib v0\.3\.1/kctl-lib v0.4.0/g; s/kctl-lib>=0\.3\.1/kctl-lib>=0.4.0/g' CLAUDE.md
```

- [ ] **Step 3: Verify no remaining references**

```bash
grep -rn 'kctl-lib\|kctl_lib' CLAUDE.md docs/
# Expected: no output
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md docs/
git commit -m "docs: update all documentation for kctl-lib → kctl-lib rename"
```

---

### Task 7: Update memory files and global config references

**Files:**
- Modify: `~/.claude/rules/infrastructure.md` (mentions `kctl-lib>=0.4.0`)
- Modify: Memory files that reference `kctl-lib`

- [ ] **Step 1: Update infrastructure.md**

In `~/.claude/rules/infrastructure.md`, change:
```
- All kctl-* CLIs depend on kctl-lib>=0.4.0 from PyPI
```
To:
```
- All kctl-* CLIs depend on kctl-lib>=0.4.0 from PyPI
```

- [ ] **Step 2: Update memory files**

Update any memory `.md` files under `.claude/projects/` that reference `kctl-lib` to say `kctl-lib`.

- [ ] **Step 3: Commit (infrastructure.md only — memory files aren't committed)**

No git commit needed for memory files. Infrastructure rules:
```bash
# This is a user config file, not in the repo — just edit it directly
```

---

### Task 8: Full workspace verification

- [ ] **Step 1: Final grep for any remaining references**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform

# Check all tracked files for leftover references
grep -r 'kctl-lib' --include='*.py' --include='*.toml' --include='*.yml' --include='*.yaml' --include='*.md' --include='*.jinja' . | grep -v '.git/' | grep -v 'node_modules/'
# Expected: no output (or only this plan file itself)

grep -r 'kctl_lib' --include='*.py' --include='*.toml' --include='*.yml' --include='*.yaml' --include='*.md' --include='*.jinja' . | grep -v '.git/' | grep -v 'node_modules/'
# Expected: no output
```

- [ ] **Step 2: Full workspace sync**

```bash
uv sync --all-extras --all-packages
```

Expected: resolves successfully with `kctl-lib` as the workspace package.

- [ ] **Step 3: Run kctl-lib core tests**

```bash
uv run pytest packages/kctl-lib/tests/ -v --tb=short
```

Expected: All 247 tests pass.

- [ ] **Step 4: Run linting across all packages**

```bash
uv run ruff check packages/*/src/ --fix
```

Expected: No errors (or only pre-existing ones unrelated to rename).

- [ ] **Step 5: Run full test suite (all packages with tests)**

```bash
uv run pytest packages/kctl-lib/tests/ packages/kctl-op/tests/ packages/kctl-ak/tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All tests pass.

- [ ] **Step 6: Final commit if any fixups needed**

```bash
# Only if ruff --fix or other fixups were needed
git add -A
git commit -m "fix: post-rename cleanup and lint fixes"
```

---

## PyPI Migration Note

After merging, you'll need to:
1. **Publish `kctl-lib` v0.4.0** to PyPI (the new package name)
2. **Publish a final `kctl-lib` v0.3.2** to PyPI with a deprecation notice pointing to `kctl-lib`
3. Tag the release: `git tag v0.4.0 && git push --tags`
