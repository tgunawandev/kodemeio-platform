# kctl-mm Design

**Date:** 2026-04-13
**Status:** Approved — ready for implementation plan
**Target instance:** `mm.idtpp.com` (Mattermost Team Edition 10.5, deployed via `kodemeio-mattermost`)

## 1. Purpose

Create `kctl-mm`, a Typer-based Python CLI in the `kodemeio-platform` workspace for managing Mattermost. It replaces the existing `scripts/mm-cli.sh` bash CLI in `kodemeio-mattermost` with a first-class kctl-* tool that uses `kctl-lib>=0.4.0` for output, config, profiles, SSH, API client, doctor, self-update, completions, and skill generation.

## 2. Architecture

Hybrid transport:

- **`MattermostClient`** — subclasses `kctl_lib.api_client.APIClient`. Calls Mattermost REST v4 at `https://mm.idtpp.com/api/v4`, bearer-token auth from profile.
- **`MMExec`** — wraps `kctl_lib.ssh.ssh_run` to execute `docker compose -f <compose_path> exec -T <service> mmctl --local --format json <args>` on the Dokploy host. Used for ops where REST is missing or inconvenient (permissions, plugin install from file, config reload, maintenance, bulk import/export, integrations).

Each command module decides per-operation whether to call REST or mmctl.

## 3. Package Layout

```
packages/kctl-mm/
├── pyproject.toml           # hatchling; deps: kctl-lib>=0.4.0, typer, httpx, pydantic, rich, pyyaml
├── README.md                # ≥40 lines
├── src/kctl_mm/
│   ├── __main__.py          # entry point: kctl-mm
│   ├── app.py               # Typer app, global callback
│   ├── context.py           # AppContext(AppContextBase) — lazy client/exec/output
│   ├── core/
│   │   ├── client.py        # MattermostClient(APIClient)
│   │   ├── exec.py          # MMExec
│   │   ├── config.py        # re-export
│   │   ├── output.py        # re-export
│   │   └── exceptions.py    # re-export + MMAPIError mapping
│   └── commands/
│       ├── config_cmd.py    # init/add/use/show/validate/remove/set/profiles/current
│       ├── doctor.py        # REST ping + SSH reach + mmctl version + auth
│       ├── self_update.py
│       ├── completions.py
│       ├── skill_cmd.py
│       ├── status.py        # host: service health (SSH docker ps)
│       ├── logs.py          # host: tail logs
│       ├── deploy.py        # host: up/down/restart/rebuild/pull
│       ├── health.py        # REST /system/ping + components
│       ├── dashboard.py     # summary/full/watch/json/activity
│       ├── users.py
│       ├── teams.py
│       ├── channels.py
│       ├── permissions.py
│       ├── posts.py
│       ├── config.py
│       ├── maintenance.py
│       ├── webhooks.py
│       ├── bots.py
│       ├── plugins.py
│       ├── integrations.py
│       ├── jobs.py
│       ├── audit.py
│       └── import_export.py
└── tests/
    ├── conftest.py
    └── test_<group>.py
```

Entry point: `kctl-mm = "kctl_mm.__main__:app"`.

Total command groups: **27** (18 domain + 5 standard + status/logs/deploy/dashboard).

## 4. Config Schema

Stored at `~/.config/kodemeio/config.yaml` under service key `"mattermost"`, default profile `default`:

```yaml
mattermost:
  current: default
  profiles:
    default:
      url: https://mm.idtpp.com
      token: ${MM_TOKEN}             # personal access token (env-expanded)
      team: kodemeio                 # optional default team slug
      ssh_host: kod-prod-02
      ssh_user: root
      compose_path: /etc/dokploy/compose/kod-mattermost/code/docker-compose.prod.yml
      compose_service: mattermost
      timeout: 30
```

`config init` prompts interactively and verifies both transports (REST `GET /api/v4/users/me` + `ssh <host> docker compose -f <path> ps`). `config show` masks secrets (first4****last4).

## 5. Transport Decision Matrix

| Group | REST | mmctl |
|---|---|---|
| users, teams, channels, posts, webhooks, bots, jobs, health, dashboard | primary | fallback for admin-only ops |
| permissions, maintenance, plugins, integrations, import-export, audit |  | primary |
| config | get/show | set/reload/test-email |
| status, logs, deploy |  | SSH docker compose |

mmctl invocation:
```
ssh {ssh_user}@{ssh_host} "docker compose -f {compose_path} exec -T {compose_service} mmctl --local --format json {args}"
```

`--local` uses the unix admin socket (no auth). JSON parsed into the standard Output pipeline.

## 6. CLI Conventions

Global options (via kctl-lib callback): `--json`, `--quiet/-q`, `--format/-f` (pretty/json/csv/yaml), `--no-header`, `--profile/-p`, `--version/-V`.

Standard subcommands (per Quality Sweep 2026-04-06): `config init`, `doctor`, `self-update`, `completions`, `skill generate`.

Command naming follows `docs/cli-standards.md`: `scaffold` for codegen, `doctor` for diagnostics, `clean` for cleanup.

## 7. Error Handling

- `MattermostClient` maps HTTP status codes: 401→`AuthenticationError`, 404→`NotFoundError`, 4xx→`APIError`, 5xx→`APIError` with `APIClient` retry/backoff.
- `MMExec` non-zero exit → `CommandError` with stderr; SSH connect failure → `ConnectionError`.
- All exceptions bubble to Typer callback which prints via `ctx.output.error()` and exits with standard kctl codes.

## 8. Testing

- pytest + `kctl_lib.testing` helpers.
- `conftest.py` exposes the 5 standard fixtures: `runner`, `mock_client`, `mock_config`, `mock_output`, `mock_context`, plus a kctl-mm-specific `mock_exec` returning `SSHResult`.
- One test file per command group; happy path + at least one error path each.
- No live Mattermost required. No Playwright/E2E.
- Lint: `ruff check`; types: `mypy --strict`.

## 9. Quality Baseline

- README ≥40 lines with commands table and quick start
- `skills/mattermost-admin/SKILL.md` generated via `kctl-mm skill generate`
- CI coverage via existing workspace matrix in `.github/workflows/ci.yml`
- Registered in root workspace `pyproject.toml` `[tool.uv.workspace]` members
- Added to `CLAUDE.md` package list

## 10. Out of Scope (v0.1)

- Multi-profile tenant layout (kctl-lib profile framework makes this trivial to add later)
- Playwright E2E tests
- Replacing `scripts/mm-cli.sh` in `kodemeio-mattermost` (will be deprecated in a follow-up once kctl-mm reaches parity)

## 11. Success Criteria

- `kctl-mm --help` shows all 27 groups
- `kctl-mm config init` configures `mm.idtpp.com` and passes `kctl-mm doctor`
- All 18 domain groups from `mm-cli.sh` have kctl-mm equivalents
- `uv run pytest packages/kctl-mm/tests/ -v` passes with ≥80% coverage on command modules
- `uv run ruff check packages/kctl-mm/src/` and `uv run mypy packages/kctl-mm/src/` are clean
- `kctl-mm skill generate` produces a valid SKILL.md
