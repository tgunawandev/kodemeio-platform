# Contributing to kodemeio-platform

## Quick Start

```bash
git clone https://github.com/tgunawandev/kodemeio-platform.git
cd kodemeio-platform
just install    # Install all packages
just check      # Lint + format + test
```

See [docs/onboarding.md](docs/onboarding.md) for detailed setup instructions.

## Development Workflow

### 1. Create a branch

```bash
git checkout -b feat/my-feature    # feat/, fix/, chore/, refactor/
```

Branch naming must match commit type prefix.

### 2. Make changes

- Edit package code in `packages/<name>/src/`
- Follow existing patterns — read a similar package first
- Run `just lint-pkg <name>` as you work

### 3. Write tests

Every change needs tests. Follow the existing test patterns:

```bash
# Run tests for your package
just test-pkg kctl-mypackage

# Run integration tests
just test-integration
```

### 4. Verify quality

```bash
just check    # Runs lint + format-check + kctl-lib tests
```

### 5. Commit

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(kctl-dokploy): add deploy rollback command
fix(kctl-pg): handle connection timeout on health check
chore(ci): add Python 3.13 to test matrix
docs: update architecture.md with new CLI packages
refactor(kctl-lib): simplify retry logic in APIClient
test(kctl-grafana): add dashboard CRUD tests
```

### 6. Push and create PR

```bash
git push -u origin feat/my-feature
gh pr create
```

## Code Standards

### Python

- Python 3.12+, strict mypy, ruff for linting
- Type hints on all functions
- `from __future__ import annotations` in every file
- Hatchling build system, uv for package management

### CLI Conventions

- All CLIs use Typer + Rich + Pydantic
- Global options: `--json`, `--quiet/-q`, `--format/-f`, `--profile/-p`, `--version/-V`
- Standard config subcommands: `init`, `add`, `use`, `show`, `validate`, `remove`, `set`, `profiles`, `current`
- See [docs/cli-standards.md](docs/cli-standards.md) for full conventions

### Test Conventions

- pytest with fixtures in `conftest.py`
- Smoke tests: `--help` for every command group
- Core tests: config, client init, exceptions
- Mock external services — never hit real APIs in tests
- Use `CliRunner` from `typer.testing` for CLI tests

### Adding a New CLI

```bash
just new-cli kctl-myservice
# Edit packages/kctl-myservice/src/ as needed
# Add tests in packages/kctl-myservice/tests/
# Run: just test-pkg kctl-myservice
```

## What NOT to Do

- Never commit `.env` files, API keys, or secrets
- Never push directly to `main` — always use PRs
- Never use `pip` — use `uv` for everything
- Never use `npm`/`yarn` — use `pnpm` for JS projects
- Never skip pre-commit hooks (`--no-verify`)
- Never use `docker run` directly — use Docker Compose via Dokploy
