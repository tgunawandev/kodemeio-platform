# kctl-* CLI Standards

## Command Naming

| Concern | Canonical Name |
|---------|---------------|
| Code generation | `scaffold` |
| Diagnostics | `doctor` |
| Cleanup | `clean` |
| Dashboard | `dashboard` |
| Skill docs generation | `skill generate` |

## Global Options (required in every CLI)

| Flag | Short | Purpose |
|------|-------|---------|
| `--json` | `-j` | JSON output shorthand |
| `--quiet` | `-q` | Suppress info messages |
| `--format` | `-f` | Output format: pretty/json/csv/yaml |
| `--no-header` | — | Omit CSV header row |
| `--profile` | `-p` | Config profile name |
| `--version` | `-V` | Show version |

## Standard `config` Subcommands

Every CLI must implement: `init`, `add`, `use`, `show`, `validate`, `remove`, `set`, `profiles`, `current`.

## Error Handling

Use `handle_cli_error()` from kctl-common in `_run()`.

## History

Use `HistoryStore` from kctl-common. DB at `~/.local/share/kodemeio/{cli-name}/history.db`.
