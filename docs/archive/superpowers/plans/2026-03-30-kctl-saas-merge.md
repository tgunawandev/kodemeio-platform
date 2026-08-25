# kctl-* SaaS CLI Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge 6 kctl-* CLIs from kodemeio-saas into kodemeio-platform/packages/ as uv workspace members, renaming kctl-1password to kctl-op with refactored internals.

**Architecture:** Copy 5 CLIs as-is into packages/, update pyproject.toml for workspace kctl-lib source. Rename and refactor kctl-1password → kctl-op by absorbing the kodemeio_1password library into kctl_op/core/. Each CLI becomes a workspace member under `packages/*`.

**Tech Stack:** Python 3.12+, uv workspace, Typer, kctl-lib, Hatchling, Ruff, mypy

---

## File Structure

### Source (kodemeio-saas)
```
kodemeio-saas/
├── kodemeio-github/cli/         → packages/kctl-github/
├── kodemeio-linear/cli/         → packages/kctl-linear/
├── kodemeio-notion/cli/         → packages/kctl-notion/
├── kodemeio-sentry/cli/         → packages/kctl-sentry/
├── kodemeio-telegram/cli/       → packages/kctl-telegram/
└── kodemeio-1password/
    ├── cli/                     → packages/kctl-op/ (renamed)
    └── src/kodemeio_1password/  → absorbed into kctl_op/core/
```

### Target (kodemeio-platform)
```
kodemeio-platform/packages/
├── kctl-lib/     # existing, unchanged
├── kctl-rustdesk/   # existing, unchanged
├── kctl-github/     # new
├── kctl-linear/     # new
├── kctl-notion/     # new
├── kctl-sentry/     # new
├── kctl-telegram/   # new
└── kctl-op/         # new (renamed from kctl-1password)
```

---

### Task 1: Copy kctl-github into workspace

**Files:**
- Create: `packages/kctl-github/` (entire directory from kodemeio-saas)
- Modify: `packages/kctl-github/pyproject.toml` (add workspace source)

- [ ] **Step 1: Copy CLI directory**

```bash
cp -r /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-github/cli/ /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-github/
```

- [ ] **Step 2: Remove .venv if copied**

```bash
rm -rf /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-github/.venv
```

- [ ] **Step 3: Update pyproject.toml to use workspace kctl-lib**

Replace the existing pyproject.toml with the workspace-aware version. The key change is adding `[tool.uv.sources]` and ensuring the dependency list matches the kctl-rustdesk reference pattern:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "kctl-github"
version = "0.1.0"
description = "Kodemeio GitHub CLI — cross-repo GitHub management"
requires-python = ">=3.12"
dependencies = [
    "kctl-lib>=0.3.0",
    "typer>=0.15.0",
    "rich>=13.9.0",
    "pydantic>=2.10.0",
    "pyyaml>=6.0.2",
    "httpx>=0.28.0",
]

[project.scripts]
kctl-github = "kctl_github.cli:_run"

[tool.uv.sources]
kctl-lib = { workspace = true }

[project.entry-points."kctl_github.plugins"]

[tool.hatch.build.targets.wheel]
packages = ["src/kctl_github"]

[tool.ruff]
target-version = "py312"
line-length = 120

[tool.mypy]
python_version = "3.12"
strict = true
```

- [ ] **Step 4: Verify workspace recognizes the package**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform && uv sync --all-extras
```

Expected: Success, kctl-github appears in workspace members.

- [ ] **Step 5: Run existing tests**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform && uv run --package kctl-github pytest packages/kctl-github/tests/ -v
```

Expected: All tests pass.

- [ ] **Step 6: Verify CLI entry point**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform && uv run kctl-github --version
```

Expected: `kctl-github, version 0.1.0`

- [ ] **Step 7: Lint check**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform && uv run --package kctl-github ruff check packages/kctl-github/src/ packages/kctl-github/tests/
```

Expected: No errors (or fix any that arise).

- [ ] **Step 8: Commit**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
git add packages/kctl-github/
git commit -m "feat(kctl-github): merge CLI from kodemeio-saas into workspace

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Copy kctl-linear into workspace

**Files:**
- Create: `packages/kctl-linear/` (entire directory from kodemeio-saas)
- Modify: `packages/kctl-linear/pyproject.toml` (add workspace source)

- [ ] **Step 1: Copy CLI directory**

```bash
cp -r /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-linear/cli/ /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-linear/
```

- [ ] **Step 2: Remove .venv if copied**

```bash
rm -rf /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-linear/.venv
```

- [ ] **Step 3: Update pyproject.toml to use workspace kctl-lib**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "kctl-linear"
version = "0.1.0"
description = "Kodemeio Linear CLI — project and sprint tracking"
requires-python = ">=3.12"
dependencies = [
    "kctl-lib>=0.4.0",
    "typer>=0.15.0",
    "rich>=13.9.0",
    "pydantic>=2.10.0",
    "pyyaml>=6.0.2",
    "httpx>=0.28.0",
]

[project.scripts]
kctl-linear = "kctl_linear.cli:_run"

[tool.uv.sources]
kctl-lib = { workspace = true }

[project.entry-points."kctl_linear.plugins"]

[tool.hatch.build.targets.wheel]
packages = ["src/kctl_linear"]

[tool.ruff]
target-version = "py312"
line-length = 120

[tool.mypy]
python_version = "3.12"
strict = true
```

- [ ] **Step 4: Sync workspace and run tests**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
uv sync --all-extras
uv run --package kctl-linear pytest packages/kctl-linear/tests/ -v
```

Expected: All tests pass.

- [ ] **Step 5: Verify CLI entry point**

```bash
uv run kctl-linear --version
```

Expected: `kctl-linear, version 0.1.0`

- [ ] **Step 6: Lint check**

```bash
uv run --package kctl-linear ruff check packages/kctl-linear/src/ packages/kctl-linear/tests/
```

- [ ] **Step 7: Commit**

```bash
git add packages/kctl-linear/
git commit -m "feat(kctl-linear): merge CLI from kodemeio-saas into workspace

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Copy kctl-notion into workspace

**Files:**
- Create: `packages/kctl-notion/` (entire directory from kodemeio-saas)
- Modify: `packages/kctl-notion/pyproject.toml` (add workspace source)

- [ ] **Step 1: Copy CLI directory**

```bash
cp -r /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-notion/cli/ /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-notion/
```

- [ ] **Step 2: Remove .venv if copied**

```bash
rm -rf /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-notion/.venv
```

- [ ] **Step 3: Update pyproject.toml to use workspace kctl-lib**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "kctl-notion"
version = "0.1.0"
description = "Kodemeio Notion CLI — wiki and database management"
requires-python = ">=3.12"
dependencies = [
    "kctl-lib>=0.4.0",
    "typer>=0.15.0",
    "rich>=13.9.0",
    "pydantic>=2.10.0",
    "pyyaml>=6.0.2",
    "httpx>=0.28.0",
]

[project.scripts]
kctl-notion = "kctl_notion.cli:_run"

[tool.uv.sources]
kctl-lib = { workspace = true }

[project.entry-points."kctl_notion.plugins"]

[tool.hatch.build.targets.wheel]
packages = ["src/kctl_notion"]

[tool.ruff]
target-version = "py312"
line-length = 120

[tool.mypy]
python_version = "3.12"
strict = true
```

- [ ] **Step 4: Sync workspace and run tests**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
uv sync --all-extras
uv run --package kctl-notion pytest packages/kctl-notion/tests/ -v
```

- [ ] **Step 5: Verify CLI entry point**

```bash
uv run kctl-notion --version
```

- [ ] **Step 6: Lint check**

```bash
uv run --package kctl-notion ruff check packages/kctl-notion/src/ packages/kctl-notion/tests/
```

- [ ] **Step 7: Commit**

```bash
git add packages/kctl-notion/
git commit -m "feat(kctl-notion): merge CLI from kodemeio-saas into workspace

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Copy kctl-sentry into workspace

**Files:**
- Create: `packages/kctl-sentry/` (entire directory from kodemeio-saas)
- Modify: `packages/kctl-sentry/pyproject.toml` (add workspace source)

- [ ] **Step 1: Copy CLI directory**

```bash
cp -r /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-sentry/cli/ /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-sentry/
```

- [ ] **Step 2: Remove .venv if copied**

```bash
rm -rf /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-sentry/.venv
```

- [ ] **Step 3: Update pyproject.toml to use workspace kctl-lib**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "kctl-sentry"
version = "0.1.0"
description = "Kodemeio Sentry CLI — error tracking management"
requires-python = ">=3.12"
dependencies = [
    "kctl-lib>=0.4.0",
    "typer>=0.15.0",
    "rich>=13.9.0",
    "pydantic>=2.10.0",
    "pyyaml>=6.0.2",
    "httpx>=0.28.0",
]

[project.scripts]
kctl-sentry = "kctl_sentry.cli:_run"

[tool.uv.sources]
kctl-lib = { workspace = true }

[project.entry-points."kctl_sentry.plugins"]

[tool.hatch.build.targets.wheel]
packages = ["src/kctl_sentry"]

[tool.ruff]
target-version = "py312"
line-length = 120

[tool.mypy]
python_version = "3.12"
strict = true
```

- [ ] **Step 4: Sync workspace and run tests**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
uv sync --all-extras
uv run --package kctl-sentry pytest packages/kctl-sentry/tests/ -v
```

- [ ] **Step 5: Verify CLI entry point**

```bash
uv run kctl-sentry --version
```

- [ ] **Step 6: Lint check**

```bash
uv run --package kctl-sentry ruff check packages/kctl-sentry/src/ packages/kctl-sentry/tests/
```

- [ ] **Step 7: Commit**

```bash
git add packages/kctl-sentry/
git commit -m "feat(kctl-sentry): merge CLI from kodemeio-saas into workspace

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Copy kctl-telegram into workspace

**Files:**
- Create: `packages/kctl-telegram/` (entire directory from kodemeio-saas)
- Modify: `packages/kctl-telegram/pyproject.toml` (add workspace source)

Note: kctl-telegram has a `core/output.py` file (custom output overrides) but no `core/plugins.py`. Verify the structure after copy.

- [ ] **Step 1: Copy CLI directory**

```bash
cp -r /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-telegram/cli/ /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-telegram/
```

- [ ] **Step 2: Remove .venv if copied**

```bash
rm -rf /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-telegram/.venv
```

- [ ] **Step 3: Update pyproject.toml to use workspace kctl-lib**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "kctl-telegram"
version = "0.1.0"
description = "Kodemeio Telegram CLI — bot platform management"
requires-python = ">=3.12"
dependencies = [
    "kctl-lib>=0.3.0",
    "typer>=0.15.0",
    "rich>=13.9.0",
    "pydantic>=2.10.0",
    "pyyaml>=6.0.2",
    "httpx>=0.28.0",
]

[project.scripts]
kctl-telegram = "kctl_telegram.cli:_run"

[tool.uv.sources]
kctl-lib = { workspace = true }

[project.entry-points."kctl_telegram.plugins"]

[tool.hatch.build.targets.wheel]
packages = ["src/kctl_telegram"]

[tool.ruff]
target-version = "py312"
line-length = 120

[tool.mypy]
python_version = "3.12"
strict = true
```

- [ ] **Step 4: Sync workspace and run tests**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
uv sync --all-extras
uv run --package kctl-telegram pytest packages/kctl-telegram/tests/ -v
```

- [ ] **Step 5: Verify CLI entry point**

```bash
uv run kctl-telegram --version
```

- [ ] **Step 6: Lint check**

```bash
uv run --package kctl-telegram ruff check packages/kctl-telegram/src/
```

- [ ] **Step 7: Commit**

```bash
git add packages/kctl-telegram/
git commit -m "feat(kctl-telegram): merge CLI from kodemeio-saas into workspace

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: Create kctl-op package structure (rename from kctl-1password)

**Files:**
- Create: `packages/kctl-op/pyproject.toml`
- Create: `packages/kctl-op/src/kctl_op/__init__.py`
- Create: `packages/kctl-op/src/kctl_op/__main__.py`

This task sets up the package skeleton. The next tasks fill in the code.

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-op/src/kctl_op/{commands,core}
mkdir -p /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-op/tests
```

- [ ] **Step 2: Create pyproject.toml**

Write to `packages/kctl-op/pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "kctl-op"
version = "0.1.0"
description = "Kodemeio 1Password CLI — secret management and .env sync"
requires-python = ">=3.12"
dependencies = [
    "kctl-lib>=0.3.0",
    "typer>=0.15.0",
    "rich>=13.9.0",
    "pydantic>=2.10.0",
    "pyyaml>=6.0.2",
    "python-dotenv>=1.0.0",
]

[project.scripts]
kctl-op = "kctl_op.cli:_run"

[tool.uv.sources]
kctl-lib = { workspace = true }

[project.entry-points."kctl_op.plugins"]

[tool.hatch.build.targets.wheel]
packages = ["src/kctl_op"]

[tool.ruff]
target-version = "py312"
line-length = 120

[tool.mypy]
python_version = "3.12"
strict = true
```

- [ ] **Step 3: Create __init__.py**

Write to `packages/kctl-op/src/kctl_op/__init__.py`:

```python
__version__ = "0.1.0"
```

- [ ] **Step 4: Create __main__.py**

Write to `packages/kctl-op/src/kctl_op/__main__.py`:

```python
from kctl_op.cli import _run

_run()
```

- [ ] **Step 5: Create empty __init__.py files**

```bash
touch /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-op/src/kctl_op/commands/__init__.py
touch /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-op/src/kctl_op/core/__init__.py
touch /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-op/tests/__init__.py
```

- [ ] **Step 6: Commit skeleton**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
git add packages/kctl-op/
git commit -m "feat(kctl-op): scaffold package skeleton (renamed from kctl-1password)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: Absorb kodemeio_1password library into kctl_op/core/

**Files:**
- Create: `packages/kctl-op/src/kctl_op/core/diff.py` (from `kodemeio_1password/diff.py`)
- Create: `packages/kctl-op/src/kctl_op/core/discovery.py` (from `kodemeio_1password/discovery.py`)
- Create: `packages/kctl-op/src/kctl_op/core/op_client.py` (from `kodemeio_1password/onepassword.py`)
- Create: `packages/kctl-op/src/kctl_op/core/parser.py` (from `kodemeio_1password/parser.py`)
- Create: `packages/kctl-op/src/kctl_op/core/sync.py` (from `kodemeio_1password/sync.py`)

The library's `config.py` will be merged into the CLI's `core/config.py` in the next task.

- [ ] **Step 1: Copy diff.py**

```bash
cp /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-1password/src/kodemeio_1password/diff.py \
   /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-op/src/kctl_op/core/diff.py
```

No import changes needed — diff.py has no internal cross-imports.

- [ ] **Step 2: Copy parser.py**

```bash
cp /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-1password/src/kodemeio_1password/parser.py \
   /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-op/src/kctl_op/core/parser.py
```

No import changes needed — parser.py has no internal cross-imports.

- [ ] **Step 3: Copy discovery.py and fix imports**

```bash
cp /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-1password/src/kodemeio_1password/discovery.py \
   /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-op/src/kctl_op/core/discovery.py
```

Then update imports in `packages/kctl-op/src/kctl_op/core/discovery.py`:
- Replace `from kodemeio_1password.config import get_config, Config` with `from kctl_op.core.op_config import get_config, Config`

Note: The library's config module will be placed at `core/op_config.py` to avoid conflict with the CLI's `core/config.py`.

- [ ] **Step 4: Copy onepassword.py as op_client.py**

```bash
cp /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-1password/src/kodemeio_1password/onepassword.py \
   /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-op/src/kctl_op/core/op_client.py
```

No import changes needed — onepassword.py has no internal cross-imports.

- [ ] **Step 5: Copy sync.py and fix imports**

```bash
cp /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-1password/src/kodemeio_1password/sync.py \
   /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-op/src/kctl_op/core/sync.py
```

Then update imports in `packages/kctl-op/src/kctl_op/core/sync.py`:
- Replace `from kodemeio_1password.diff import compute_diff, DiffResult` with `from kctl_op.core.diff import compute_diff, DiffResult`
- Replace `from kodemeio_1password.onepassword import ...` with `from kctl_op.core.op_client import ...`
- Replace `from kodemeio_1password.parser import ...` with `from kctl_op.core.parser import ...`
- Replace `from kodemeio_1password.config import get_config` with `from kctl_op.core.op_config import get_config`
- Replace `from kodemeio_1password.discovery import ...` with `from kctl_op.core.discovery import ...`

- [ ] **Step 6: Copy library config.py as op_config.py**

```bash
cp /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-1password/src/kodemeio_1password/config.py \
   /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-op/src/kctl_op/core/op_config.py
```

No import changes needed — config.py has no internal cross-imports.

- [ ] **Step 7: Verify no remaining kodemeio_1password imports**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
grep -r "kodemeio_1password" packages/kctl-op/
```

Expected: No matches. If any remain, fix them.

- [ ] **Step 8: Commit**

```bash
git add packages/kctl-op/src/kctl_op/core/
git commit -m "feat(kctl-op): absorb kodemeio_1password library into core/

Modules: diff, parser, discovery, op_client, sync, op_config
All imports updated from kodemeio_1password → kctl_op.core

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: Copy and rename kctl-1password CLI code into kctl-op

**Files:**
- Create: `packages/kctl-op/src/kctl_op/cli.py` (from `kctl_1password/cli.py`, renamed)
- Create: `packages/kctl-op/src/kctl_op/core/callbacks.py` (from `kctl_1password/core/callbacks.py`)
- Create: `packages/kctl-op/src/kctl_op/core/client.py` (from `kctl_1password/core/client.py`)
- Create: `packages/kctl-op/src/kctl_op/core/config.py` (from `kctl_1password/core/config.py`)
- Create: `packages/kctl-op/src/kctl_op/core/exceptions.py` (from `kctl_1password/core/exceptions.py`)
- Create: `packages/kctl-op/src/kctl_op/core/output.py` (from `kctl_1password/core/output.py`)
- Create: `packages/kctl-op/src/kctl_op/commands/*.py` (all command files)

- [ ] **Step 1: Copy all command files**

```bash
cp /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-1password/cli/src/kctl_1password/commands/*.py \
   /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-op/src/kctl_op/commands/
```

- [ ] **Step 2: Copy core CLI files (callbacks, client, config, exceptions, output)**

```bash
for f in callbacks.py client.py config.py exceptions.py output.py; do
  cp /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-1password/cli/src/kctl_1password/core/$f \
     /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-op/src/kctl_op/core/$f
done
```

Note: This will overwrite `core/config.py` — that's intentional. The CLI's config.py (with SERVICE_KEY, resolve_config) is the one we want. The library's config was saved as `op_config.py` in Task 7.

- [ ] **Step 3: Copy cli.py**

```bash
cp /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-1password/cli/src/kctl_1password/cli.py \
   /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-op/src/kctl_op/cli.py
```

- [ ] **Step 4: Rename all kctl_1password imports to kctl_op across all files**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
find packages/kctl-op/src/kctl_op/ -name "*.py" -exec sed -i 's/kctl_1password/kctl_op/g' {} +
```

- [ ] **Step 5: Rename kodemeio_1password imports in command files**

Some command files (like `diff_cmd.py`) import from `kodemeio_1password`. Fix these:

```bash
find packages/kctl-op/src/kctl_op/ -name "*.py" -exec sed -i 's/from kodemeio_1password\.diff/from kctl_op.core.diff/g' {} +
find packages/kctl-op/src/kctl_op/ -name "*.py" -exec sed -i 's/from kodemeio_1password\.onepassword/from kctl_op.core.op_client/g' {} +
find packages/kctl-op/src/kctl_op/ -name "*.py" -exec sed -i 's/from kodemeio_1password\.parser/from kctl_op.core.parser/g' {} +
find packages/kctl-op/src/kctl_op/ -name "*.py" -exec sed -i 's/from kodemeio_1password\.sync/from kctl_op.core.sync/g' {} +
find packages/kctl-op/src/kctl_op/ -name "*.py" -exec sed -i 's/from kodemeio_1password\.discovery/from kctl_op.core.discovery/g' {} +
find packages/kctl-op/src/kctl_op/ -name "*.py" -exec sed -i 's/from kodemeio_1password\.config/from kctl_op.core.op_config/g' {} +
find packages/kctl-op/src/kctl_op/ -name "*.py" -exec sed -i 's/from kodemeio_1password/from kctl_op.core/g' {} +
```

- [ ] **Step 6: Update SERVICE_KEY in core/config.py**

In `packages/kctl-op/src/kctl_op/core/config.py`, change:

```python
# OLD
SERVICE_KEY = "onepassword"
# NEW
SERVICE_KEY = "op"
```

- [ ] **Step 7: Update CLI app name in cli.py**

In `packages/kctl-op/src/kctl_op/cli.py`, change:

```python
# OLD
app = typer.Typer(name="kctl-1password", ...)
# NEW
app = typer.Typer(name="kctl-op", ...)
```

Also update any help text that references "1password" or "1Password" to "op" / "1Password (op)".

- [ ] **Step 8: Update env var prefix references**

Search and replace environment variable prefix references:

```bash
find packages/kctl-op/src/kctl_op/ -name "*.py" -exec sed -i 's/KCTL_1PASSWORD_/KCTL_OP_/g' {} +
```

- [ ] **Step 9: Verify no remaining old references**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
grep -rn "kctl_1password\|kctl-1password\|kodemeio_1password\|KCTL_1PASSWORD" packages/kctl-op/
```

Expected: No matches. Fix any remaining references.

- [ ] **Step 10: Commit**

```bash
git add packages/kctl-op/
git commit -m "feat(kctl-op): copy CLI commands and core, rename all references

- kctl_1password → kctl_op
- kodemeio_1password → kctl_op.core
- SERVICE_KEY: onepassword → op
- Env prefix: KCTL_1PASSWORD_ → KCTL_OP_

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 9: Copy and update kctl-op tests

**Files:**
- Create: `packages/kctl-op/tests/` (from kctl-1password CLI tests + library tests)

- [ ] **Step 1: Copy CLI tests**

```bash
cp /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-1password/cli/tests/*.py \
   /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-op/tests/
```

- [ ] **Step 2: Copy library tests**

```bash
cp /home/tgunawan/project/00-new-projects/kodemeio-saas/kodemeio-1password/tests/*.py \
   /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/packages/kctl-op/tests/
```

Note: If there are filename conflicts (e.g., both have `conftest.py`), merge them manually — the CLI's conftest.py takes priority, add any library-specific fixtures into it.

- [ ] **Step 3: Rename all imports in test files**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
find packages/kctl-op/tests/ -name "*.py" -exec sed -i 's/kctl_1password/kctl_op/g' {} +
find packages/kctl-op/tests/ -name "*.py" -exec sed -i 's/kodemeio_1password\.diff/kctl_op.core.diff/g' {} +
find packages/kctl-op/tests/ -name "*.py" -exec sed -i 's/kodemeio_1password\.onepassword/kctl_op.core.op_client/g' {} +
find packages/kctl-op/tests/ -name "*.py" -exec sed -i 's/kodemeio_1password\.parser/kctl_op.core.parser/g' {} +
find packages/kctl-op/tests/ -name "*.py" -exec sed -i 's/kodemeio_1password\.sync/kctl_op.core.sync/g' {} +
find packages/kctl-op/tests/ -name "*.py" -exec sed -i 's/kodemeio_1password\.discovery/kctl_op.core.discovery/g' {} +
find packages/kctl-op/tests/ -name "*.py" -exec sed -i 's/kodemeio_1password\.config/kctl_op.core.op_config/g' {} +
find packages/kctl-op/tests/ -name "*.py" -exec sed -i 's/kodemeio_1password/kctl_op/g' {} +
```

- [ ] **Step 4: Verify no remaining old references in tests**

```bash
grep -rn "kctl_1password\|kodemeio_1password\|KCTL_1PASSWORD" packages/kctl-op/tests/
```

Expected: No matches.

- [ ] **Step 5: Sync workspace and run tests**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
uv sync --all-extras
uv run --package kctl-op pytest packages/kctl-op/tests/ -v
```

Expected: All tests pass.

- [ ] **Step 6: Verify CLI entry point**

```bash
uv run kctl-op --version
```

Expected: `kctl-op, version 0.1.0`

- [ ] **Step 7: Lint check**

```bash
uv run --package kctl-op ruff check packages/kctl-op/src/ packages/kctl-op/tests/
```

Fix any lint errors.

- [ ] **Step 8: Commit**

```bash
git add packages/kctl-op/tests/
git commit -m "feat(kctl-op): add tests from CLI and library, all imports updated

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 10: Update uv.lock and final workspace validation

**Files:**
- Modify: `uv.lock` (auto-generated by uv sync)

- [ ] **Step 1: Full workspace sync**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
uv sync --all-extras
```

Expected: All 8 workspace members resolve (kctl-lib, kctl-rustdesk, kctl-github, kctl-linear, kctl-notion, kctl-sentry, kctl-telegram, kctl-op).

- [ ] **Step 2: Verify all CLI entry points**

```bash
uv run kctl-github --version
uv run kctl-linear --version
uv run kctl-notion --version
uv run kctl-sentry --version
uv run kctl-telegram --version
uv run kctl-op --version
```

Expected: Each prints `kctl-{name}, version 0.1.0`.

- [ ] **Step 3: Run all tests across workspace**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
for pkg in kctl-github kctl-linear kctl-notion kctl-sentry kctl-telegram kctl-op; do
  echo "=== Testing $pkg ==="
  uv run --package $pkg pytest packages/$pkg/tests/ -v
done
```

Expected: All tests pass for all 6 CLIs.

- [ ] **Step 4: Run kctl-lib tests (ensure no regression)**

```bash
uv run --package kctl-lib pytest packages/kctl-lib/tests/ -v
```

Expected: All 238 tests pass.

- [ ] **Step 5: Lint all new packages**

```bash
for pkg in kctl-github kctl-linear kctl-notion kctl-sentry kctl-telegram kctl-op; do
  echo "=== Linting $pkg ==="
  uv run --package $pkg ruff check packages/$pkg/src/
done
```

Expected: No lint errors.

- [ ] **Step 6: Commit uv.lock**

```bash
git add uv.lock
git commit -m "chore: update uv.lock with 6 new workspace members

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 11: Update documentation

**Files:**
- Modify: `CLAUDE.md` (update CLI listing)
- Modify: `README.md` (update package table)

- [ ] **Step 1: Update CLAUDE.md**

In the `### kodemeio-saas (7 CLIs)` section, update entries to reflect:
- `kctl-1password` → `kctl-op` (renamed)
- Add note that these 6 CLIs now live in kodemeio-platform workspace

Add a new subsection:

```markdown
### kodemeio-platform workspace members
- **kctl-lib** — Shared CLI infrastructure (v0.3.1)
- **kctl-rustdesk** — RustDesk server management (9 groups)
- **kctl-op** — 1Password secret management (9 groups) — *renamed from kctl-1password*
- **kctl-github** — Cross-repo GitHub management (10 groups)
- **kctl-linear** — Linear project/sprint tracking (9 groups)
- **kctl-notion** — Notion wiki/database management (7 groups)
- **kctl-sentry** — Sentry error tracking (10 groups)
- **kctl-telegram** — Telegram bot platform (7 groups)
```

- [ ] **Step 2: Update README.md**

Add the new packages to the package table in README.md.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: update CLI listings for merged saas packages and kctl-op rename

Co-Authored-By: Claude <noreply@anthropic.com>"
```
