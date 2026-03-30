# kctl-react

Kodemeio React Monorepo CLI — manage 11 Vite PWAs + 14 shared packages.

Part of the kctl-\* CLI ecosystem (alongside kctl-ak, kctl-odoo, kctl-pg, etc.), built with Python + Typer + Rich.

## Install

```bash
cd cli && uv tool install .
```

## Quick Start

```bash
kctl-react dashboard          # Full monorepo overview
kctl-react apps list          # List all 11 apps
kctl-react doctor             # Comprehensive health check
kctl-react info               # Quick project info
```

## Command Groups

| Group       | Commands                                                   | Purpose                             |
| ----------- | ---------------------------------------------------------- | ----------------------------------- |
| `apps`      | `list`, `ports`, `status`, `health --watch`                | App inventory & health              |
| `dev`       | `start`, `logs`, `list`                                    | Dev server management               |
| `build`     | `[app] --analyze`, `size`                                  | Production builds + bundle analysis |
| `test`      | `[app] --coverage --watch`, `count`                        | Vitest testing                      |
| `lint`      | `[app] --fix`, `format --check`                            | ESLint + TypeScript + Prettier      |
| `codegen`   | `[app]`, `status`                                          | OpenAPI type generation             |
| `deps`      | `outdated`, `audit`, `graph`, `list`                       | Dependency management               |
| `env`       | `show`, `diff`, `validate`                                 | .env management                     |
| `scaffold`  | `page`, `hook`, `component`                                | Code scaffolding                    |
| `deploy`    | `build`, `status`, `logs`, `down --force`                  | Docker Compose deployment           |
| `packages`  | `list`, `consumers`, `size`                                | Shared package inspection           |
| `clean`     | `[app] --all`                                              | Clean build artifacts               |
| `doctor`    |                                                            | Comprehensive health check          |
| `info`      |                                                            | Quick project info                  |
| `dashboard` | `--watch --interval`                                       | Monorepo overview                   |
| `config`    | `init`, `add`, `use`, `show`, `set`, `profiles`, `current` | Profile management                  |

## Global Options

```bash
kctl-react [--json] [--quiet] [--profile NAME] [--root PATH] <command>
```

- `--json` — Machine-readable JSON output (data to stdout, status to stderr)
- `--quiet` / `-q` — Suppress info messages
- `--profile` / `-p` — Config profile name
- `--root` — Monorepo root override
- `--version` / `-V` — Show version

## Configuration

Shared config at `~/.config/kodemeio/config.yaml` (same file as kctl-ak, kctl-odoo, etc.):

```yaml
default_profile: default
profiles:
  default:
    react:
      project_root: /path/to/kodemeio-react
      api_url: https://api.kodeme.io
```

Auto-detects project root from `turbo.json` when not configured.

## Development

```bash
cd cli
uv run --extra dev pytest tests/ -v    # Run 73 tests
uv run --extra dev ruff check src/     # Lint
uv run --extra dev mypy src/           # Type check
```

## Architecture

Follows the kctl-\* ecosystem pattern:

```
cli/src/kctl_react/
├── core/           # Config, output, callbacks, runner, exceptions
├── commands/       # One file per command group (16 groups)
├── cli.py          # Main Typer app + command registration
└── py.typed        # PEP 561 marker
```
