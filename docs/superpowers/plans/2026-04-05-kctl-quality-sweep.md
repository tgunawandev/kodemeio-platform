# kctl-* CLI Quality Sweep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring all 22 kctl-* CLIs to 9+/10 quality rating via 7 horizontal sweeps.

**Architecture:** Each sweep applies one improvement layer across all CLIs in parallel. Sweeps are sequential (2 depends on 1, 3 depends on 2, etc.). Within each sweep, all CLIs are independent and can be dispatched as parallel subagents.

**Tech Stack:** Python 3.12+, Typer, pytest, kctl-lib v0.4.0, Playwright (E2E only)

**Spec:** `docs/superpowers/specs/2026-04-05-kctl-quality-sweep-design.md`

---

## Task 0: Delete kctl-gatus

**Files:**
- Delete: `packages/kctl-gatus/` (entire directory)
- Modify: `CLAUDE.md` (remove gatus references)
- Delete: `docs/cli/kctl-gatus.md`
- Modify: `monitoring/README.md` (remove gatus references)
- Modify: any runbook referencing kctl-gatus

- [ ] **Step 1: Remove the package directory**

```bash
rm -rf packages/kctl-gatus/
```

- [ ] **Step 2: Remove from CLAUDE.md**

Remove `kctl-gatus` from:
- Workspace Members table (line with "**kctl-gatus** — Gatus health monitoring")
- Key Paths table (line with `packages/kctl-gatus/`)
- Any other mention

- [ ] **Step 3: Remove docs/cli/kctl-gatus.md**

```bash
rm docs/cli/kctl-gatus.md
```

- [ ] **Step 4: Clean up monitoring/README.md**

Remove paragraphs/sections referencing kctl-gatus. Replace with note that health monitoring is handled by kctl-grafana.

- [ ] **Step 5: Grep for remaining references**

```bash
grep -r "kctl-gatus\|kctl_gatus\|gatus-admin" --include="*.md" --include="*.py" --include="*.yaml" --include="*.yml" .
```

Remove any remaining references found.

- [ ] **Step 6: Verify workspace still resolves**

```bash
uv sync --all-packages 2>&1 | head -20
```

Expected: No errors about kctl-gatus.

- [ ] **Step 7: Commit**

```bash
git add -A packages/kctl-gatus/ CLAUDE.md docs/cli/kctl-gatus.md monitoring/README.md
git commit -m "chore: delete kctl-gatus CLI (overlaps with kctl-grafana + kctl-dokploy)"
```

---

## Sweep 1: README + SKILL.md

Each CLI below gets its own parallel task. The pattern is identical — only the CLI name, command count, and command groups differ.

### Task 1.1: README Template (apply to each CLI)

For each CLI listed below, create or rewrite `packages/kctl-XX/README.md` following this template. Scale sections based on command count.

**Files per CLI:**
- Create/Modify: `packages/kctl-XX/README.md`

**Template for small CLIs (<30 commands):**

```markdown
# kctl-XX

Kodemeio [Service Name] CLI — [one-line description].

## Installation

```bash
uv tool install kctl-XX
```

## Quick Start

```bash
# Configure
kctl-XX config init

# Common operations
kctl-XX [group] [command]
kctl-XX health check
kctl-XX dashboard
```

## Command Groups

| Group | Commands | Description |
|-------|----------|-------------|
| `config` | init, add, use, show, validate, remove, set, profiles, current | Profile management |
| ... | ... | ... |

## Configuration

Uses shared config at `~/.config/kodemeio/config.yaml` with `[service_key]` profile scoping.

```bash
kctl-XX config init        # Interactive setup
kctl-XX config show        # Show current config
kctl-XX config profiles    # List all profiles
```

## Development

```bash
cd packages/kctl-XX
uv sync --all-extras
uv run pytest tests/ -v
uv run ruff check src/
uv run mypy src/
```
```

**Additional sections for medium CLIs (30-100 commands):** Add Command Aliases, Global Options (`--json`, `--quiet`, `--format`, `--profile`, `--version`), Shell Completions.

**Additional sections for large CLIs (100+ commands):** Add Plugins, Architecture overview, E2E Testing (if applicable), Version Highlights.

**CLIs and their sizes:**

| CLI | Commands | Size category | README action |
|-----|----------|--------------|---------------|
| kctl-ak | 186 | Large | Rewrite (93L, needs expansion) |
| kctl-api | 231 | Large | Rewrite (73L, needs expansion) |
| kctl-cf | 195 | Large | Rewrite (3L stub) |
| kctl-claude | 31 | Medium | Polish (40L, adequate) |
| kctl-claw | 151 | Large | Polish (135L, good) |
| kctl-dokploy | 279 | Large | Rewrite (3L stub) |
| kctl-github | 37 | Medium | Rewrite (17L) |
| kctl-glitchtip | 50 | Medium | Create (missing) |
| kctl-grafana | 33 | Medium | Rewrite (3L stub) |
| kctl-hz | 139 | Large | Rewrite (49L, needs expansion) |
| kctl-linear | 29 | Small | Rewrite (17L) |
| kctl-mailcow | 107 | Large | Create (missing) |
| kctl-notion | 23 | Small | Rewrite (17L) |
| kctl-odoo | 733 | Large | Keep (227L, gold standard) |
| kctl-op | 22 | Small | Polish (40L, adequate) |
| kctl-pg | 127 | Large | Rewrite (0L empty) |
| kctl-react | 175 | Large | Polish (89L, needs expansion) |
| kctl-redis | 61 | Medium | Create (missing) |
| kctl-rmm | 66 | Medium | Polish (42L, adequate) |
| kctl-rustdesk | 36 | Medium | Polish (40L, adequate) |
| kctl-sentry | 35 | Medium | Rewrite (17L) |
| kctl-telegram | 27 | Small | Polish (30L, needs expansion) |
| kctl-waha | 28 | Small | Polish (30L, needs expansion) |

- [ ] **Step 1: For each CLI, read existing README (if any) and command groups from source**

```bash
# List command groups for a CLI
grep "app.add_typer\|app.command" packages/kctl-XX/src/kctl_XX/cli.py
```

- [ ] **Step 2: Write README following template + size category**

- [ ] **Step 3: Verify README renders correctly**

```bash
head -5 packages/kctl-XX/README.md  # sanity check
```

- [ ] **Step 4: Commit per CLI**

```bash
git add packages/kctl-XX/README.md
git commit -m "docs(kctl-XX): add comprehensive README"
```

### Task 1.2: SKILL.md Generation (12 CLIs)

**Files per CLI:**
- Create: `packages/kctl-XX/skills/XX-admin/SKILL.md`

12 CLIs missing SKILL.md: **api, claude, github, grafana, linear, mailcow, notion, op, redis, rmm, rustdesk, sentry**.

Each CLI that already has `skill generate` wired up can auto-generate. For CLIs without the skill command, follow the kctl-claude pattern.

- [ ] **Step 1: For each CLI, check if skill command exists**

```bash
grep -r "skill_cmd\|skill_generator" packages/kctl-XX/src/
```

- [ ] **Step 2A: If skill command exists, run it**

```bash
cd packages/kctl-XX && uv run kctl-XX skill generate
```

- [ ] **Step 2B: If skill command does NOT exist, wire it up first**

Create `packages/kctl-XX/src/kctl_XX/commands/skill_cmd.py`:

```python
"""Skill generation command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from kctl_XX import __version__
from kctl_XX.core.callbacks import AppContext

app = typer.Typer(help="Skill file management.", no_args_is_help=True)


@app.command()
def generate(
    ctx: typer.Context,
    output: Annotated[str, typer.Option("--output", "-o", help="Output directory")] = "",
    install: Annotated[bool, typer.Option("--install", help="Install to ~/.claude/skills/")] = False,
    check: Annotated[bool, typer.Option("--check", help="Check if SKILL.md is stale")] = False,
) -> None:
    """Auto-generate SKILL.md from CLI command registry."""
    actx: AppContext = ctx.obj
    out = actx.output
    from kctl_lib.skill_generator import check_stale, generate_skill

    from kctl_XX.cli import app as cli_app

    skill_name = "XX-admin"
    description = "DESCRIPTION via kctl-XX CLI"

    if output:
        output_dir = Path(output)
    elif install:
        output_dir = Path.home() / ".claude" / "skills" / skill_name
    else:
        cli_root = Path(__file__).resolve().parents[3]
        output_dir = cli_root / "skills" / skill_name

    if check:
        skill_file = output_dir / "SKILL.md"
        is_stale, reason = check_stale(cli_app, skill_file)
        if is_stale:
            out.warn(f"SKILL.md is stale: {reason}")
            raise typer.Exit(1)
        out.success(f"SKILL.md is up to date: {reason}")
        return

    extra = output_dir / "SKILL.extra.md"
    generate_skill(
        cli_app,
        "kctl-XX",
        skill_name,
        description,
        output_dir=output_dir,
        extra_file=extra if extra.exists() else None,
    )
    out.success(f"Generated {output_dir / 'SKILL.md'}")
```

Then register in `cli.py`:

```python
from kctl_XX.commands.skill_cmd import app as skill_app
app.add_typer(skill_app, name="skill", hidden=True)
```

- [ ] **Step 3: Run skill generate**

```bash
cd packages/kctl-XX && uv run kctl-XX skill generate
```

- [ ] **Step 4: Review generated SKILL.md for accuracy**

- [ ] **Step 5: Commit**

```bash
git add packages/kctl-XX/skills/ packages/kctl-XX/src/kctl_XX/commands/skill_cmd.py packages/kctl-XX/src/kctl_XX/cli.py
git commit -m "docs(kctl-XX): add SKILL.md via skill generator"
```

---

## Sweep 2: Test Infrastructure (conftest.py + fixtures)

### Task 2.1: Create conftest.py for 5 CLIs Missing It

**CLIs:** ak, claude, mailcow, telegram, waha

**Files per CLI:**
- Create: `packages/kctl-XX/tests/conftest.py`

- [ ] **Step 1: Create conftest.py following this template**

For **API-based CLIs** (ak, mailcow, telegram, waha):

```python
"""Shared test fixtures for kctl-XX."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from kctl_XX.cli import app
from kctl_XX.core.callbacks import AppContext
from kctl_XX.core.client import XXClient


@pytest.fixture
def runner():
    """Typer CLI test runner."""
    from typer.testing import CliRunner
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    """Mock API client."""
    client = MagicMock(spec=XXClient)
    client.base_url = "https://XX.kodeme.io"
    return client


@pytest.fixture
def mock_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect config to tmp_path."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    monkeypatch.setattr("kctl_XX.core.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("kctl_XX.core.config.CONFIG_FILE", config_file)
    return config_file


@pytest.fixture
def mock_output():
    """Output instance for testing."""
    from kctl_lib.testing import mock_output
    return mock_output()


@pytest.fixture
def mock_context(mock_client: MagicMock, mock_output) -> AppContext:
    """AppContext with mocked client."""
    ctx = AppContext(quiet=True)
    ctx._client = mock_client
    ctx._output = mock_output
    return ctx


@pytest.fixture
def cli_app():
    """Return the Typer app for testing."""
    return app
```

For **kctl-claude** (subprocess-based, no API client):

```python
"""Shared test fixtures for kctl-claude."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from kctl_claude.cli import app
from kctl_claude.core.callbacks import AppContext


@pytest.fixture
def runner():
    """Typer CLI test runner."""
    from typer.testing import CliRunner
    return CliRunner()


@pytest.fixture
def mock_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect config to tmp_path."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    monkeypatch.setattr("kctl_claude.core.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("kctl_claude.core.config.CONFIG_FILE", config_file)
    return config_file


@pytest.fixture
def mock_output():
    """Output instance for testing."""
    from kctl_lib.testing import mock_output
    return mock_output()


@pytest.fixture
def mock_context(mock_output) -> AppContext:
    """AppContext with mocked dependencies."""
    ctx = AppContext(quiet=True)
    ctx._output = mock_output
    return ctx


@pytest.fixture
def mock_subprocess(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock subprocess.run for testing CLI wrappers."""
    mock = MagicMock()
    mock.return_value.returncode = 0
    mock.return_value.stdout = ""
    mock.return_value.stderr = ""
    monkeypatch.setattr("subprocess.run", mock)
    return mock


@pytest.fixture
def cli_app():
    """Return the Typer app for testing."""
    return app
```

- [ ] **Step 2: Verify conftest loads correctly**

```bash
cd packages/kctl-XX && uv run pytest tests/ --collect-only 2>&1 | head -10
```

Expected: No import errors.

- [ ] **Step 3: Commit**

```bash
git add packages/kctl-XX/tests/conftest.py
git commit -m "test(kctl-XX): add conftest.py with standard fixtures"
```

### Task 2.2: Audit and Upgrade Existing conftest.py (16 CLIs)

**CLIs:** api, cf, claw, dokploy, github, glitchtip, grafana, hz, linear, notion, odoo, op, pg, react, redis, rmm, rustdesk, sentry

For each CLI, check its existing `tests/conftest.py` and ensure it has these 5 standard fixtures:

1. `runner` — CliRunner
2. `mock_client` — MagicMock of the CLI's client class
3. `mock_config` — tmp_path config redirect
4. `mock_output` — Output in json mode
5. `mock_context` — AppContext with mocked dependencies

Plus type-specific fixtures:
- SSH CLIs (pg, redis): add `mock_ssh_tunnel`, `mock_ssh_run`
- Docker CLIs (react, dokploy): add `mock_docker_manager`
- GraphQL CLIs (linear): add `mock_graphql_client`

- [ ] **Step 1: Read existing conftest.py**

```bash
cat packages/kctl-XX/tests/conftest.py
```

- [ ] **Step 2: Add any missing standard fixtures from the templates above**

- [ ] **Step 3: Add type-specific fixtures if applicable**

For SSH CLIs (pg, redis):

```python
@pytest.fixture
def mock_ssh_run(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock kctl_lib.ssh.ssh_run."""
    from kctl_lib.ssh import SSHResult
    mock = MagicMock()
    mock.return_value = SSHResult(stdout="", stderr="", returncode=0)
    monkeypatch.setattr("kctl_lib.ssh.ssh_run", mock)
    return mock


@pytest.fixture
def mock_ssh_tunnel(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock SSHTunnel context manager."""
    mock = MagicMock()
    mock.__enter__ = MagicMock(return_value=("localhost", 15432))
    mock.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr("kctl_lib.ssh_tunnel.SSHTunnel", MagicMock(return_value=mock))
    return mock
```

For Docker CLIs (react, dokploy):

```python
@pytest.fixture
def mock_docker_manager(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock DockerManager."""
    from kctl_lib.docker import DockerManager
    mock = MagicMock(spec=DockerManager)
    return mock
```

- [ ] **Step 4: Verify tests still pass**

```bash
cd packages/kctl-XX && uv run pytest tests/ -v 2>&1 | tail -5
```

- [ ] **Step 5: Commit**

```bash
git add packages/kctl-XX/tests/conftest.py
git commit -m "test(kctl-XX): standardize conftest.py fixtures"
```

---

## Sweep 3: Test Coverage to 35%+

### Task 3.1: Write Tests (per CLI)

For each CLI below that is under 35% test LOC ratio, write tests targeting the most important commands.

**Testing pattern for API-based CLIs:**

```python
"""Tests for kctl_XX.commands.GROUPNAME."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_XX.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestGroupNameList:
    """Tests for `kctl-XX groupname list`."""

    def test_list_success(self, runner: CliRunner, mock_client: MagicMock) -> None:
        """List returns formatted table."""
        mock_client.get.return_value = {
            "results": [
                {"id": 1, "name": "test-item"},
                {"id": 2, "name": "other-item"},
            ]
        }
        with patch("kctl_XX.commands.groupname.get_client", return_value=mock_client):
            result = runner.invoke(app, ["groupname", "list", "--json"])
        assert result.exit_code == 0

    def test_list_empty(self, runner: CliRunner, mock_client: MagicMock) -> None:
        """List with no results shows empty message."""
        mock_client.get.return_value = {"results": []}
        with patch("kctl_XX.commands.groupname.get_client", return_value=mock_client):
            result = runner.invoke(app, ["groupname", "list", "--json"])
        assert result.exit_code == 0

    def test_list_auth_error(self, runner: CliRunner, mock_client: MagicMock) -> None:
        """List with bad auth shows error."""
        from kctl_lib.exceptions import AuthenticationError
        mock_client.get.side_effect = AuthenticationError("Invalid token")
        with patch("kctl_XX.commands.groupname.get_client", return_value=mock_client):
            result = runner.invoke(app, ["groupname", "list"])
        assert result.exit_code != 0


class TestGroupNameShow:
    """Tests for `kctl-XX groupname show`."""

    def test_show_success(self, runner: CliRunner, mock_client: MagicMock) -> None:
        """Show returns detail view."""
        mock_client.get.return_value = {"id": 1, "name": "test-item", "status": "active"}
        with patch("kctl_XX.commands.groupname.get_client", return_value=mock_client):
            result = runner.invoke(app, ["groupname", "show", "1", "--json"])
        assert result.exit_code == 0

    def test_show_not_found(self, runner: CliRunner, mock_client: MagicMock) -> None:
        """Show with bad ID returns error."""
        from kctl_lib.exceptions import NotFoundError
        mock_client.get.side_effect = NotFoundError("Not found")
        with patch("kctl_XX.commands.groupname.get_client", return_value=mock_client):
            result = runner.invoke(app, ["groupname", "show", "999"])
        assert result.exit_code != 0
```

**Testing pattern for SSH-based CLIs (pg, redis):**

```python
"""Tests for kctl_XX.commands.GROUPNAME."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from kctl_XX.cli import app


class TestQueryExecution:
    """Tests for query-based commands."""

    def test_query_success(self, runner: CliRunner, mock_ssh_run: MagicMock) -> None:
        """Command executes query via SSH and formats output."""
        from kctl_lib.ssh import SSHResult
        mock_ssh_run.return_value = SSHResult(
            stdout="name|size\nmy_db|1024 MB\n",
            stderr="",
            returncode=0,
        )
        result = runner.invoke(app, ["databases", "list", "--json"])
        assert result.exit_code == 0

    def test_query_connection_error(self, runner: CliRunner, mock_ssh_run: MagicMock) -> None:
        """SSH connection failure shows error."""
        from kctl_lib.exceptions import ConnectionError
        mock_ssh_run.side_effect = ConnectionError("SSH timeout")
        result = runner.invoke(app, ["databases", "list"])
        assert result.exit_code != 0
```

**Testing pattern for config commands (all CLIs):**

```python
"""Tests for config commands."""

from __future__ import annotations

import yaml
from typer.testing import CliRunner

from kctl_XX.cli import app


class TestConfigInit:
    """Tests for `kctl-XX config init`."""

    def test_init_creates_config(self, runner: CliRunner, mock_config, tmp_path) -> None:
        """Config init creates config file."""
        result = runner.invoke(app, ["config", "init"], input="https://service.kodeme.io\nmy-token\n")
        assert result.exit_code == 0

    def test_init_idempotent(self, runner: CliRunner, mock_config, tmp_path) -> None:
        """Config init twice doesn't crash."""
        runner.invoke(app, ["config", "init"], input="https://service.kodeme.io\nmy-token\n")
        result = runner.invoke(app, ["config", "init"], input="https://service.kodeme.io\nmy-token\n")
        assert result.exit_code == 0
```

**CLIs needing tests and their priority command groups:**

| CLI | Delta LOC | Priority command groups to test |
|-----|-----------|-------------------------------|
| pg | +3,047 | databases, users, backup, activity, bloat, vacuum |
| api | +3,065 | apps, deploy, auth, cache, ai, background-job |
| ak | +1,505 | providers, applications, flows, users, groups |
| mailcow | +1,364 | domains, mailboxes, aliases, dkim, transport |
| cf | +1,055 | dns, zones, firewall, cache, ssl, analytics |
| hz | +788 | servers, networks, firewalls, volumes, ssh-keys |
| redis | +702 | keys, clients, memory, backup, pub-sub |
| waha | +629 | sessions, messages, groups, webhook, health |
| telegram | +625 | bots, groups, messages, chatwoot, health |
| rmm | +503 | agents, alerts, checks, scripts, tasks |
| react | +446 | apps, build, deploy, audit, a11y, i18n |
| linear | +434 | issues, projects, cycles, users, teams |
| sentry | +400 | errors, projects, alerts, releases, deploy |
| github | +372 | repos, actions, ci, contributors, audit |
| dokploy | +368 | deploy, compose, domains, env, backup |
| claw | +350 | agents, profiles, models, alerts, audit |
| glitchtip | +233 | projects, issues, uptime, alerts, teams |
| op | +210 | envs, secrets, vaults, backup, generate |
| rustdesk | +62 | peers, users, health, audit, backup |

- [ ] **Step 1: For each CLI, identify the top 3-5 command groups by usage frequency**

- [ ] **Step 2: Write test file per command group following patterns above**

Create `packages/kctl-XX/tests/test_GROUPNAME.py` for each group.

- [ ] **Step 3: Run tests to verify they pass**

```bash
cd packages/kctl-XX && uv run pytest tests/ -v
```

- [ ] **Step 4: Check coverage ratio**

```bash
find packages/kctl-XX/src -name "*.py" -exec cat {} + | wc -l  # source LOC
find packages/kctl-XX/tests -name "*.py" -exec cat {} + | wc -l  # test LOC
# test LOC / source LOC should be >= 0.35
```

- [ ] **Step 5: Commit**

```bash
git add packages/kctl-XX/tests/
git commit -m "test(kctl-XX): increase test coverage to 35%+"
```

---

## Sweep 4: kctl-lib Integration

Three sub-sweeps, each parallelizable across all 22 CLIs.

### Task 4.1: Add `self-update` Command (20 CLIs)

**Skip:** kctl-claude (already has it), kctl-lib (shared library, not a CLI)

**Files per CLI:**
- Modify: `packages/kctl-XX/src/kctl_XX/cli.py`

- [ ] **Step 1: Add update command to cli.py**

Add this block after the existing commands in `cli.py`, before the `_run()` function:

```python
@app.command("update")
def update_cmd(ctx: typer.Context) -> None:
    """Check for updates and upgrade kctl-XX."""
    actx: AppContext = ctx.obj
    out = actx.output

    from kctl_lib.self_update import check_update
    from kctl_lib.self_update import update as do_update

    latest = check_update("kctl-XX", __version__)
    if latest:
        out.info(f"Updating to {latest}...")
        do_update("kctl-XX")
        out.success(f"Updated to {latest}")
    else:
        out.success("Already up to date")
```

- [ ] **Step 2: Write test**

Create or append to `packages/kctl-XX/tests/test_update.py`:

```python
"""Tests for self-update command."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from kctl_XX.cli import app


def test_update_already_latest(runner_or_default: CliRunner = None) -> None:
    runner = runner_or_default or CliRunner()
    with patch("kctl_lib.self_update.check_update", return_value=None):
        result = runner.invoke(app, ["update"])
    assert result.exit_code == 0
    assert "up to date" in result.stdout.lower()


def test_update_new_version_available() -> None:
    runner = CliRunner()
    with (
        patch("kctl_lib.self_update.check_update", return_value="0.5.0"),
        patch("kctl_lib.self_update.update") as mock_update,
    ):
        result = runner.invoke(app, ["update"])
    assert result.exit_code == 0
    mock_update.assert_called_once_with("kctl-XX")
```

- [ ] **Step 3: Run test**

```bash
cd packages/kctl-XX && uv run pytest tests/test_update.py -v
```

- [ ] **Step 4: Commit**

```bash
git add packages/kctl-XX/src/kctl_XX/cli.py packages/kctl-XX/tests/test_update.py
git commit -m "feat(kctl-XX): add self-update command"
```

### Task 4.2: Add `doctor` Command (20 CLIs)

**Skip:** kctl-claude (already has it), kctl-lib

**Files per CLI:**
- Create: `packages/kctl-XX/src/kctl_XX/commands/doctor_cmd.py`
- Modify: `packages/kctl-XX/src/kctl_XX/cli.py` (register command)

- [ ] **Step 1: Create doctor_cmd.py**

For **API-based CLIs** (ak, api, cf, claw, dokploy, github, glitchtip, grafana, hz, mailcow, notion, rmm, rustdesk, sentry, telegram, waha):

```python
"""Doctor diagnostic checks for kctl-XX."""

from __future__ import annotations

from dataclasses import dataclass

import typer

from kctl_lib.doctor_base import CheckResult, DoctorCheck, PythonVersionCheck, UvCheck, GitCheck, run_doctor
from kctl_XX.core.callbacks import AppContext


@dataclass
class APIConnectivityCheck:
    """Check that the configured API endpoint is reachable."""

    name: str = "API Connectivity"

    def run(self) -> CheckResult:
        try:
            from kctl_XX.core.config import load_config

            cfg = load_config()
            url = cfg.get("url", "")
            if not url:
                return CheckResult(
                    name=self.name,
                    status="fail",
                    message="No URL configured",
                    fix_command="kctl-XX config init",
                )
            import httpx

            resp = httpx.get(f"{url}/", timeout=5)
            return CheckResult(
                name=self.name,
                status="ok",
                message=f"{url} reachable (HTTP {resp.status_code})",
            )
        except Exception as e:
            return CheckResult(
                name=self.name,
                status="fail",
                message=str(e),
                fix_command="kctl-XX config show",
            )


@dataclass
class AuthCheck:
    """Check that authentication credentials are valid."""

    name: str = "Authentication"

    def run(self) -> CheckResult:
        try:
            from kctl_XX.core.config import load_config

            cfg = load_config()
            token = cfg.get("api_key", "") or cfg.get("token", "")
            if not token:
                return CheckResult(
                    name=self.name,
                    status="fail",
                    message="No API key/token configured",
                    fix_command="kctl-XX config init",
                )
            return CheckResult(
                name=self.name,
                status="ok",
                message="Token configured (validity not checked)",
            )
        except Exception as e:
            return CheckResult(
                name=self.name,
                status="fail",
                message=str(e),
            )


app = typer.Typer(help="Run diagnostic checks.", no_args_is_help=False)


@app.callback(invoke_without_command=True)
def doctor(ctx: typer.Context) -> None:
    """Run all diagnostic checks."""
    if ctx.invoked_subcommand is not None:
        return
    actx: AppContext = ctx.obj
    out = actx.output

    checks: list[DoctorCheck] = [
        PythonVersionCheck(),
        UvCheck(),
        GitCheck(),
        APIConnectivityCheck(),
        AuthCheck(),
    ]

    all_passed = run_doctor(checks, out)  # type: ignore[arg-type]
    if not all_passed:
        raise typer.Exit(code=1)
```

For **SSH-based CLIs** (pg, redis), replace `APIConnectivityCheck` with:

```python
@dataclass
class SSHConnectivityCheck:
    """Check that SSH connection to database host works."""

    name: str = "SSH Connectivity"

    def run(self) -> CheckResult:
        try:
            from kctl_XX.core.config import load_config

            cfg = load_config()
            host = cfg.get("ssh_host", "")
            if not host:
                return CheckResult(
                    name=self.name,
                    status="fail",
                    message="No SSH host configured",
                    fix_command="kctl-XX config init",
                )
            from kctl_lib.ssh import ssh_run

            result = ssh_run(host, "echo ok")
            if result.returncode == 0:
                return CheckResult(name=self.name, status="ok", message=f"SSH to {host} working")
            return CheckResult(name=self.name, status="fail", message=f"SSH failed: {result.stderr}")
        except Exception as e:
            return CheckResult(name=self.name, status="fail", message=str(e))
```

For **subprocess-based CLIs** (op), replace with:

```python
@dataclass
class OpBinaryCheck:
    """Check that 1Password CLI (op) is installed."""

    name: str = "1Password CLI"

    def run(self) -> CheckResult:
        import shutil

        if shutil.which("op"):
            return CheckResult(name=self.name, status="ok", message="op binary found in PATH")
        return CheckResult(
            name=self.name,
            status="fail",
            message="op not found",
            fix_command="https://developer.1password.com/docs/cli/get-started/",
        )
```

- [ ] **Step 2: Register in cli.py**

Add to imports and registration:

```python
from kctl_XX.commands.doctor_cmd import app as doctor_app
app.add_typer(doctor_app, name="doctor")
```

- [ ] **Step 3: Write test**

Create `packages/kctl-XX/tests/test_doctor.py`:

```python
"""Tests for doctor command."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from kctl_XX.cli import app


def test_doctor_all_pass() -> None:
    runner = CliRunner()
    with patch("kctl_XX.commands.doctor_cmd.APIConnectivityCheck.run") as mock_api, \
         patch("kctl_XX.commands.doctor_cmd.AuthCheck.run") as mock_auth:
        from kctl_lib.doctor_base import CheckResult
        mock_api.return_value = CheckResult(name="API", status="ok", message="OK")
        mock_auth.return_value = CheckResult(name="Auth", status="ok", message="OK")
        result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0


def test_doctor_fail_exits_1() -> None:
    runner = CliRunner()
    with patch("kctl_XX.commands.doctor_cmd.APIConnectivityCheck.run") as mock_api, \
         patch("kctl_XX.commands.doctor_cmd.AuthCheck.run") as mock_auth:
        from kctl_lib.doctor_base import CheckResult
        mock_api.return_value = CheckResult(name="API", status="fail", message="unreachable")
        mock_auth.return_value = CheckResult(name="Auth", status="ok", message="OK")
        result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
```

- [ ] **Step 4: Run test**

```bash
cd packages/kctl-XX && uv run pytest tests/test_doctor.py -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/kctl-XX/src/kctl_XX/commands/doctor_cmd.py packages/kctl-XX/src/kctl_XX/cli.py packages/kctl-XX/tests/test_doctor.py
git commit -m "feat(kctl-XX): add doctor diagnostic command"
```

### Task 4.3: Add `completions` Command (21 CLIs)

**Skip:** kctl-claude (already has it)

**Files per CLI:**
- Modify: `packages/kctl-XX/src/kctl_XX/cli.py`

- [ ] **Step 1: Add completions command to cli.py**

Add this block in `cli.py`:

```python
@app.command()
def completions(
    shell: Annotated[str, typer.Argument(help="Shell type: zsh, bash, fish")] = "zsh",
    install: Annotated[bool, typer.Option("--install", help="Install completions")] = False,
) -> None:
    """Generate or install shell completions."""
    from kctl_lib.completions import get_completion_script, install_completions

    if install:
        path = install_completions("kctl-XX", shell)
        if path:
            typer.echo(f"Completions installed to {path}")
        else:
            typer.echo(f"Could not install completions for {shell}", err=True)
            raise typer.Exit(code=1)
    else:
        script = get_completion_script("kctl-XX", shell)
        typer.echo(script)
```

- [ ] **Step 2: Write test**

Create or append to `packages/kctl-XX/tests/test_completions.py`:

```python
"""Tests for completions command."""

from __future__ import annotations

from unittest.mock import patch
from pathlib import Path

from typer.testing import CliRunner

from kctl_XX.cli import app


def test_completions_generate() -> None:
    runner = CliRunner()
    with patch("kctl_lib.completions.get_completion_script", return_value="# completion script"):
        result = runner.invoke(app, ["completions", "zsh"])
    assert result.exit_code == 0
    assert "completion script" in result.stdout


def test_completions_install(tmp_path: Path) -> None:
    runner = CliRunner()
    target = tmp_path / "_kctl-XX"
    with patch("kctl_lib.completions.install_completions", return_value=target):
        result = runner.invoke(app, ["completions", "zsh", "--install"])
    assert result.exit_code == 0
    assert "installed" in result.stdout.lower()
```

- [ ] **Step 3: Run test**

```bash
cd packages/kctl-XX && uv run pytest tests/test_completions.py -v
```

- [ ] **Step 4: Commit**

```bash
git add packages/kctl-XX/src/kctl_XX/cli.py packages/kctl-XX/tests/test_completions.py
git commit -m "feat(kctl-XX): add shell completions command"
```

---

## Sweep 5: Error Handling Standardization

### Task 5.1: Standardize Exception Usage (per CLI)

**Files per CLI:**
- Modify: `packages/kctl-XX/src/kctl_XX/core/client.py` (or equivalent API client)
- Modify: command files that catch raw exceptions

- [ ] **Step 1: Audit current exception handling**

```bash
grep -rn "except Exception\|except httpx\|except requests\|except KeyError" packages/kctl-XX/src/
```

- [ ] **Step 2: Replace raw exception catches with kctl-lib exceptions**

In the CLI's client module, ensure HTTP status mapping:

```python
from kctl_lib.exceptions import (
    APIError,
    AuthenticationError,
    ConnectionError,
    NotFoundError,
    ValidationError,
)

def _handle_response(self, response: httpx.Response) -> dict:
    """Map HTTP status to kctl-lib exceptions."""
    if response.status_code in (401, 403):
        raise AuthenticationError(f"Authentication failed: {response.status_code}")
    if response.status_code == 404:
        raise NotFoundError(f"Resource not found: {response.url}")
    if response.status_code == 422:
        raise ValidationError(f"Validation error: {response.text}")
    if response.status_code >= 500:
        raise APIError(f"Server error {response.status_code}: {response.text}")
    response.raise_for_status()
    return response.json()
```

**Note:** If the CLI uses `APIClient` from kctl-lib, this mapping is already built in. Check if the CLI overrides or bypasses it.

- [ ] **Step 3: Ensure handle_cli_error() is used in _run()**

Verify `cli.py` has:

```python
def _run() -> None:
    try:
        app()
    except KctlError as e:
        from kctl_lib import handle_cli_error
        handle_cli_error(e)
```

- [ ] **Step 4: Add input validation for CLI boundaries**

For CLIs that accept user input that gets passed to SQL, DNS, or API paths:

```python
import re
from kctl_lib.exceptions import ValidationError

def _validate_name(name: str, pattern: str = r"^[a-zA-Z0-9_-]+$") -> str:
    if not re.match(pattern, name):
        raise ValidationError(f"Invalid name: {name!r} (must match {pattern})")
    return name
```

Apply to:
- **kctl-pg:** database names, user names
- **kctl-cf:** domain names (use `r"^[a-zA-Z0-9.-]+$"`)
- **kctl-hz:** server names
- **All CLIs:** profile names in config commands

- [ ] **Step 5: Run existing tests to verify no regressions**

```bash
cd packages/kctl-XX && uv run pytest tests/ -v
```

- [ ] **Step 6: Commit**

```bash
git add packages/kctl-XX/src/
git commit -m "fix(kctl-XX): standardize error handling with kctl-lib exceptions"
```

---

## Sweep 6: E2E Tests (4 CLIs)

kctl-odoo already has E2E. Add to: dokploy, react, pg, ak.

### Task 6.1: E2E for kctl-dokploy

**Files:**
- Create: `packages/kctl-dokploy/e2e/playwright.config.ts`
- Create: `packages/kctl-dokploy/e2e/fixtures/auth.ts`
- Create: `packages/kctl-dokploy/e2e/fixtures/helpers.ts`
- Create: `packages/kctl-dokploy/e2e/tests/global-setup.ts`
- Create: `packages/kctl-dokploy/e2e/tests/smoke/compose-list.spec.ts`
- Create: `packages/kctl-dokploy/e2e/tests/scenarios/deploy-dryrun.spec.ts`

- [ ] **Step 1: Initialize Playwright**

```bash
cd packages/kctl-dokploy && npm init -y && npm i -D @playwright/test && npx playwright install chromium
```

- [ ] **Step 2: Create playwright.config.ts**

```typescript
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  retries: 1,
  use: {
    baseURL: process.env.DOKPLOY_URL || 'https://dokploy.kodeme.io',
  },
  projects: [
    { name: 'setup', testMatch: /global-setup\.ts/ },
    { name: 'smoke', testMatch: /smoke\/.*\.spec\.ts/, dependencies: ['setup'] },
    { name: 'scenarios', testMatch: /scenarios\/.*\.spec\.ts/, dependencies: ['setup'] },
  ],
});
```

- [ ] **Step 3: Create auth fixture**

`e2e/fixtures/auth.ts`:

```typescript
import { test as base } from '@playwright/test';

export const test = base.extend<{ apiToken: string; baseUrl: string }>({
  apiToken: async ({}, use) => {
    const token = process.env.DOKPLOY_TOKEN;
    if (!token) throw new Error('DOKPLOY_TOKEN env var required');
    await use(token);
  },
  baseUrl: async ({}, use) => {
    const url = process.env.DOKPLOY_URL || 'https://dokploy.kodeme.io';
    await use(url);
  },
});

export { expect } from '@playwright/test';
```

- [ ] **Step 4: Create smoke test**

`e2e/tests/smoke/compose-list.spec.ts`:

```typescript
import { test, expect } from '../../fixtures/auth';

test.describe('Compose List', () => {
  test('can list compose services via API', async ({ request, apiToken, baseUrl }) => {
    const response = await request.get(`${baseUrl}/api/compose.all`, {
      headers: { Authorization: `Bearer ${apiToken}` },
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(Array.isArray(data)).toBeTruthy();
  });
});
```

- [ ] **Step 5: Run E2E against staging**

```bash
cd packages/kctl-dokploy/e2e && DOKPLOY_URL=https://dokploy.kodeme.io DOKPLOY_TOKEN=$TOKEN npx playwright test --project=smoke
```

- [ ] **Step 6: Commit**

```bash
git add packages/kctl-dokploy/e2e/
git commit -m "test(kctl-dokploy): add Playwright E2E smoke tests"
```

### Task 6.2: E2E for kctl-pg

Same structure as 6.1 but targeting PostgreSQL operations:

**Files:**
- Create: `packages/kctl-pg/e2e/` (same structure)
- Smoke tests: `databases list`, `users list`, `activity`
- Scenario tests: create test DB → verify → drop

Connection via active kctl-pg profile pointing to staging PostgreSQL.

### Task 6.3: E2E for kctl-ak

Same structure targeting Authentik:

**Files:**
- Create: `packages/kctl-ak/e2e/` (same structure)
- Smoke tests: `providers list`, `applications list`, `flows list`
- Scenario tests: create test provider → verify → delete

Connection via active kctl-ak profile pointing to staging Authentik.

### Task 6.4: E2E for kctl-react

Same structure targeting React monorepo operations:

**Files:**
- Create: `packages/kctl-react/e2e/` (same structure)
- Smoke tests: `apps list`, `apps status`
- Scenario tests: `build` a test app, verify output

Note: kctl-react E2E tests run locally against the kodemeio-react repo clone, not against a remote service.

---

## Final Verification

After all sweeps complete:

- [ ] **Run full test suite**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
uv run pytest packages/*/tests/ -v --tb=short 2>&1 | tail -30
```

- [ ] **Run linter**

```bash
uv run ruff check packages/*/src/
```

- [ ] **Run type checker**

```bash
for pkg in packages/kctl-*/; do
  echo "=== $(basename $pkg) ==="
  cd "$pkg" && uv run mypy src/ 2>&1 | tail -3 && cd ../..
done
```

- [ ] **Verify all READMEs exist and meet minimum length**

```bash
for pkg in packages/kctl-*/; do
  name=$(basename $pkg)
  lines=$(wc -l < "$pkg/README.md" 2>/dev/null || echo 0)
  echo "$name: $lines lines"
done
```

- [ ] **Verify all SKILL.md exist**

```bash
for pkg in packages/kctl-*/; do
  name=$(basename $pkg)
  if [ -f "$pkg/skills/"*/SKILL.md ]; then echo "$name: OK"; else echo "$name: MISSING"; fi
done
```

- [ ] **Final commit**

```bash
git add -A
git commit -m "chore: complete kctl quality sweep — all CLIs at 9+/10"
```
