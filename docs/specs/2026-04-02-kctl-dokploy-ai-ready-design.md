# kctl-dokploy AI-Ready Improvements — Design Specification

**Date:** 2026-04-02
**Status:** Approved
**Author:** Claude + tgunawan

---

## 1. Problem Statement

An AI agent (Claude) spent 30+ minutes failing to deploy a Next.js app via `kctl-dokploy` due to:
- **ID truncation** — all IDs in table output are sliced to 12 chars, causing 404 on subsequent commands
- **githubId confusion** — Dokploy has two different GitHub IDs; the CLI passes the wrong one
- **No atomic deploy** — deploying a GitHub-sourced compose requires 5+ chained commands, each with hidden pitfalls
- **No verification** — after deployment completes, no way to verify the site actually works

These issues make kctl-dokploy **unusable by AI agents** for the most common operation: deploying a service from GitHub.

## 2. Changes

### 2.1 Bug Fixes (8 files)

#### Fix 1: Remove ALL `[:12]` ID truncation

Files with `[:12]` slicing on IDs:

| File | Line(s) | Variable |
|---|---|---|
| `commands/compose.py` | 41, 415 | `cid` |
| `commands/applications.py` | 34, 260 | `aid` |
| `commands/deployments.py` | 36, 230, 253, 281 | `did` |
| `commands/servers.py` | 23 | `sid` |
| `commands/domains.py` | 81 | `did` |
| `commands/git.py` | 23 | `gid` |

**Change:** Remove `[:12]` from all. Full IDs in tables are fine — Rich auto-truncates with `…` when the terminal is narrow.

#### Fix 2: Fix `githubId` vs `gitProviderId`

The Dokploy API has TWO different IDs:
- `gitProviderId` — the provider record ID (from `/gitProvider.getAll`)
- `github.githubId` — the nested GitHub App installation ID (the FK that compose.githubId references)

**Changes:**

1. `commands/git.py` `list` command — add a column `GitHub ID` showing `g.get("github", {}).get("githubId", "")` so AI agents can see the correct ID to use for compose linking.

2. `commands/git.py` — add a new `resolve` command:
```python
@app.command()
def resolve(ctx, provider_id: str):
    """Resolve a git provider to its GitHub App ID (for compose linking)."""
    # GET /gitProvider.getAll, find by gitProviderId
    # Return github.githubId
```

3. `commands/compose.py` `update` — when `--github-id` is provided, validate it's a valid `github.githubId` (not a `gitProviderId`). If the user passes a `gitProviderId`, auto-resolve it to the inner `githubId`.

4. `core/deployer.py` `_find_github_id()` — already correct (returns inner ID). Add a comment explaining the distinction.

#### Fix 3: Server ID validation in `compose create`

In `commands/compose.py` `create`:
- If `--server` is provided, resolve the server name/ID via `servers list` first
- If resolution fails, error immediately with "Server not found: <name>"
- Don't pass `serverId` if it's empty/None

#### Fix 4: Deploy pipeline error handling

In `core/deployer.py`:
- `phase_compose()` — parse compose creation response with `--json` output, not fragile text splitting
- After compose creation, immediately verify the compose exists by calling `compose get`
- After `githubId` linkage, verify it's set by re-fetching the compose
- Add clear phase-level error messages: "Phase 4 (Compose) failed: [reason]"

### 2.2 New Command: `quickdeploy`

New file: `commands/quickdeploy.py`

```
kctl-dokploy quickdeploy \
  --name terakidz-web \
  --project kidneuro-service \
  --repo tgunawandev/kodemeio-react \
  --branch main \
  --compose-path compose/docker-compose.terakidz.yml \
  --domain terakidz.com \
  --port 3006 \
  --service terakidz-web \
  [--https] \
  [--wait] \
  [--timeout 300]
```

#### Workflow (7 steps)

```
Step 1: RESOLVE — project name → environment ID
  - Call projects get <name>
  - Extract first environment ID
  - Fail: "Project not found: <name>"

Step 2: GITHUB — find GitHub provider → resolve inner githubId
  - Call /gitProvider.getAll
  - Find first GitHub-type provider
  - Extract github.githubId (the inner ID)
  - Fail: "No GitHub provider configured in Dokploy"

Step 3: COMPOSE — create or update compose service
  - Check if compose with --name already exists in the environment
  - If exists: update source-type, repo, branch, compose-path, githubId
  - If not: create new compose, then update with GitHub details
  - Verify compose is created by re-fetching
  - Fail: "Failed to create/update compose: [API error]"

Step 4: DOMAIN — add domain if --domain provided
  - Check if domain already exists on this compose
  - If exists: skip (idempotent)
  - If not: create domain with host, port, service, https, cert
  - Fail: "Failed to add domain: [API error]"

Step 5: DEPLOY — trigger deployment
  - Call compose redeploy
  - Fail: "Failed to trigger deployment"

Step 6: WAIT — poll deployment status
  - Every 10s, check deployments list --compose <id> --limit 1
  - Status "running" → continue polling
  - Status "done" → proceed to step 7
  - Status "error" → fetch deployment logs, report error, exit 1
  - Timeout (default 300s) → report timeout, exit 1

Step 7: VERIFY — health check (if --wait)
  - Poll https://<domain> every 5s
  - 200 → success, report URL
  - Non-200 after 60s → warn but don't fail (Traefik propagation delay)
```

#### Options

| Option | Required | Default | Description |
|---|---|---|---|
| `--name` / `-n` | Yes | — | Compose service name |
| `--project` / `-p` | Yes | — | Project name (not ID) |
| `--repo` / `-r` | Yes | — | GitHub repo (owner/repo format) |
| `--branch` / `-b` | No | `main` | Git branch |
| `--compose-path` / `-c` | Yes | — | Path to docker-compose.yml in repo |
| `--domain` / `-d` | No | — | Domain to configure |
| `--port` | No | 80 | Container port for domain routing |
| `--service` / `-s` | No | — | Docker Compose service name for domain |
| `--https` | No | False | Enable HTTPS with Let's Encrypt |
| `--wait` | No | False | Wait for deployment + health check |
| `--timeout` | No | 300 | Max seconds to wait for deployment |
| `--dry-run` | No | False | Show plan without executing |

#### Output

Success:
```
✓ Step 1/7: Project 'kidneuro-service' → env msI18ISal5GeMlGLIXpwb
✓ Step 2/7: GitHub provider → githubId ZieFEXD90Ai1X6U6wj0ur
✓ Step 3/7: Compose 'terakidz-web' created (uWvTvQKuXKPMsfQndoQxJ)
✓ Step 4/7: Domain terakidz.com:3006 added
✓ Step 5/7: Deployment triggered
✓ Step 6/7: Deployment done (2m 34s)
✓ Step 7/7: Health check passed — https://terakidz.com

OK Deployment complete: terakidz-web → https://terakidz.com
```

Error:
```
✓ Step 1/7: Project 'kidneuro-service' → env msI18ISal5GeMlGLIXpwb
✓ Step 2/7: GitHub provider → githubId ZieFEXD90Ai1X6U6wj0ur
✓ Step 3/7: Compose 'terakidz-web' created (uWvTvQKuXKPMsfQndoQxJ)
✓ Step 4/7: Domain terakidz.com:3006 added
✓ Step 5/7: Deployment triggered
✗ Step 6/7: Deployment FAILED after 3m 12s

Build Error:
  COPY packages/api-client/package.json — not found
  
Suggestion: Check Dockerfile references missing packages in the monorepo.
```

### 2.3 SKILL.md Update

Add to the `dokploy-admin` skill file:

```markdown
## AI Quick Deploy (Recommended for AI Agents)

Deploy any GitHub-sourced service in ONE command:

```bash
kctl-dokploy quickdeploy \
  --name <service-name> \
  --project <project-name> \
  --repo <owner/repo> \
  --branch main \
  --compose-path <path/to/docker-compose.yml> \
  --domain <host> \
  --port <container-port> \
  --service <compose-service-name> \
  --https --wait
```

### Examples

Next.js site:
```bash
kctl-dokploy quickdeploy -n terakidz-web -p kidneuro-service \
  -r tgunawandev/kodemeio-react -c compose/docker-compose.terakidz.yml \
  -d terakidz.com --port 3006 -s terakidz-web --https --wait
```

FastAPI service:
```bash
kctl-dokploy quickdeploy -n api-tms -p kidneuro-service \
  -r tgunawandev/kodemeio-odoo -c compose/fastapi.prod.api-tms.yml \
  -d api.terakidz.com --port 8015 -s api-tms --https --wait
```

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Deploy status "error" | Build failure | `kctl-dokploy deployments logs <id>` |
| 404 from domain | Traefik routing | Redeploy: `kctl-dokploy compose redeploy <id>` |
| 521 from Cloudflare | SSL mode mismatch | Set CF SSL to "flexible" if Dokploy domain is HTTP |
| "No GitHub provider" | GitHub App not installed | Install via Dokploy UI → Settings → Git |
```

## 3. Files Changed

| File | Change |
|---|---|
| `commands/git.py` | Remove `[:12]`, add `GitHub ID` column, add `resolve` command |
| `commands/compose.py` | Remove `[:12]`, auto-resolve `githubId`, validate server |
| `commands/applications.py` | Remove `[:12]` |
| `commands/deployments.py` | Remove `[:12]` (4 locations) |
| `commands/servers.py` | Remove `[:12]` |
| `commands/domains.py` | Remove `[:12]` |
| `commands/quickdeploy.py` | NEW — entire quick deploy command |
| `core/deployer.py` | Fix error handling, add comments on githubId |
| `cli.py` | Register `quickdeploy` command group |
| SKILL.md (dokploy-admin) | Add AI Quick Deploy section + troubleshooting |

## 4. Testing

- Unit tests for `quickdeploy` command (mock API calls)
- Integration test: dry-run mode with mock Dokploy API
- Verify ID truncation fix doesn't break existing table formatting
