# kctl-dokploy AI-Ready Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix critical bugs (ID truncation, githubId confusion) and add a `quickdeploy` command so AI agents can deploy GitHub-sourced services in one atomic command.

**Architecture:** Bug fixes are simple find-and-replace across 6 command files. The `quickdeploy` command orchestrates existing CLI operations (compose create/update, domain add, deploy, verify) in a single workflow with proper error handling.

**Tech Stack:** Python 3.12, Typer, Rich, httpx (via kctl-lib APIClient)

**Spec:** `docs/specs/2026-04-02-kctl-dokploy-ai-ready-design.md`

---

## File Structure

```
packages/kctl-dokploy/src/kctl_dokploy/
  commands/
    git.py              — MODIFY: remove [:12], add GitHub ID column + resolve command
    compose.py          — MODIFY: remove [:12] (2 locations), auto-resolve githubId
    domains.py          — MODIFY: remove [:12]
    applications.py     — MODIFY: remove [:12] (2 locations)
    deployments.py      — MODIFY: remove [:12] (5 locations)
    servers.py          — MODIFY: remove [:12] (3 locations)
    quickdeploy.py      — NEW: atomic GitHub→Dokploy deploy command
  cli.py                — MODIFY: register quickdeploy command
  tests/
    test_quickdeploy.py — NEW: tests for quickdeploy
```

---

## Task 1: Remove ALL `[:12]` ID truncations

**Files:**
- Modify: `commands/compose.py` lines 41, 415
- Modify: `commands/domains.py` line 81
- Modify: `commands/applications.py` lines 34, 260
- Modify: `commands/deployments.py` lines 36, 230, 253, 281, 323
- Modify: `commands/servers.py` lines 23, 262, 287

- [ ] **Step 1: Fix compose.py**

Line 41: change `rows.append([cid[:12], name, status, project])` to `rows.append([cid, name, status, project])`

Line 415: find `[:12]` in search command and remove.

- [ ] **Step 2: Fix domains.py**

Line 81: change `did = d.get("domainId", "")[:12]` to `did = d.get("domainId", "")`

- [ ] **Step 3: Fix applications.py**

Line 34: change `rows.append([aid[:12], proj_name, name, status])` to `rows.append([aid, proj_name, name, status])`

Line 260: remove `[:12]` from search command.

- [ ] **Step 4: Fix deployments.py**

Lines 36, 230, 253, 281, 323: change all `did = d.get("deploymentId", "")[:12]` to `did = d.get("deploymentId", "")`

- [ ] **Step 5: Fix servers.py**

Lines 23, 262, 287: change all `sid = s.get("serverId", "")[:12]` to `sid = s.get("serverId", "")`

- [ ] **Step 6: Verify**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
uv tool install --force ./packages/kctl-dokploy
kctl-dokploy git list  # IDs should be full length now
kctl-dokploy compose list  # IDs should be full length
kctl-dokploy servers list  # IDs should be full length
```

- [ ] **Step 7: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/commands/
git commit -m "fix(kctl-dokploy): remove all [:12] ID truncation across 6 command files"
```

---

## Task 2: Fix githubId confusion — add resolve command + GitHub ID column

**Files:**
- Modify: `commands/git.py`

- [ ] **Step 1: Add GitHub ID column to `list` command**

In `git.py`, in the `list_` function, after `gid = g.get("gitProviderId", "")`, add:

```python
        github_inner = g.get("github", {})
        github_app_id = github_inner.get("githubId", "") if isinstance(github_inner, dict) else ""
```

Update the `rows.append` to include the inner ID:
```python
        rows.append([gid, github_app_id, name, ptype, str(org), str(created)])
```

Update the table headers to add "GitHub App ID":
```python
    c.output.table(
        "Git Providers",
        [("Provider ID", "dim"), ("GitHub App ID", "cyan"), ("Name", ""), ("Type", ""), ("Organization", ""), ("Created", "dim")],
        rows,
        data_for_json=providers,
    )
```

- [ ] **Step 2: Add `resolve` command**

Add after the `list_` function:

```python
@app.command()
def resolve(
    ctx: typer.Context,
    provider_id: Annotated[str | None, typer.Argument(help="Git provider ID (optional, uses first GitHub provider if omitted)")] = None,
) -> None:
    """Resolve a git provider to its GitHub App ID (for compose linking).

    The compose table's githubId FK references the INNER github.githubId,
    not the outer gitProviderId. This command returns the correct ID.
    """
    c: AppContext = ctx.obj
    providers = c.client.get("/gitProvider.getAll")
    if not isinstance(providers, list):
        providers = []

    for p in providers:
        if provider_id and p.get("gitProviderId") != provider_id:
            continue
        if p.get("gitProviderType", p.get("providerType")) == "github":
            github = p.get("github", {})
            if isinstance(github, dict) and github.get("githubId"):
                github_id = github["githubId"]
                c.output.success(f"GitHub App ID: {github_id}")
                if c.json_mode:
                    c.output.raw_json({"githubId": github_id, "gitProviderId": p.get("gitProviderId")})
                return

    c.output.error("No GitHub provider found" + (f" with ID {provider_id}" if provider_id else ""))
    raise typer.Exit(1)
```

- [ ] **Step 3: Verify**

```bash
uv tool install --force ./packages/kctl-dokploy
kctl-dokploy git list       # Should show both Provider ID and GitHub App ID columns
kctl-dokploy git resolve    # Should print: GitHub App ID: ZieFEXD90Ai1X6U6wj0ur
```

- [ ] **Step 4: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/commands/git.py
git commit -m "feat(kctl-dokploy): add GitHub App ID column and resolve command for compose linking"
```

---

## Task 3: Auto-resolve githubId in compose update

**Files:**
- Modify: `commands/compose.py` (update function)

- [ ] **Step 1: Add auto-resolution**

In the `update` function, after the line `if github_id is not None: payload["githubId"] = github_id`, add auto-resolution:

```python
    if github_id is not None:
        # Auto-resolve: if the ID looks like a gitProviderId (not a github.githubId),
        # resolve it to the inner ID
        resolved = _resolve_github_app_id(c, github_id)
        payload["githubId"] = resolved if resolved else github_id
```

Add the helper function before the `update` function:

```python
def _resolve_github_app_id(c: AppContext, id_or_provider_id: str) -> str | None:
    """Resolve a gitProviderId to its inner github.githubId if needed."""
    providers = c.client.get("/gitProvider.getAll")
    if not isinstance(providers, list):
        return None
    for p in providers:
        # Check if the provided ID is a gitProviderId
        if p.get("gitProviderId") == id_or_provider_id:
            github = p.get("github", {})
            if isinstance(github, dict):
                return github.get("githubId")
        # Check if it's already a github.githubId (pass through)
        github = p.get("github", {})
        if isinstance(github, dict) and github.get("githubId") == id_or_provider_id:
            return id_or_provider_id
    return None
```

- [ ] **Step 2: Verify**

```bash
uv tool install --force ./packages/kctl-dokploy
# This should now work with EITHER the provider ID or the inner GitHub ID:
kctl-dokploy compose update --id <compose-id> --github-id SeJx2A7XRZMFPFwr8sU4Y  # auto-resolves to inner ID
```

- [ ] **Step 3: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/commands/compose.py
git commit -m "fix(kctl-dokploy): auto-resolve gitProviderId to github.githubId in compose update"
```

---

## Task 4: Create `quickdeploy` command

**Files:**
- Create: `commands/quickdeploy.py`
- Modify: `cli.py`

- [ ] **Step 1: Create quickdeploy.py**

```python
"""Atomic GitHub → Dokploy deployment in one command."""

from __future__ import annotations

import time
from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Quick deploy a GitHub-sourced service to Dokploy.")


@app.command("run")
def run(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Compose service name")],
    project: Annotated[str, typer.Option("--project", "-p", help="Project name")],
    repo: Annotated[str, typer.Option("--repo", "-r", help="GitHub repo (owner/repo)")],
    compose_path: Annotated[str, typer.Option("--compose-path", "-c", help="Path to docker-compose.yml in repo")],
    branch: Annotated[str, typer.Option("--branch", "-b", help="Git branch")] = "main",
    domain: Annotated[str | None, typer.Option("--domain", "-d", help="Domain to configure")] = None,
    port: Annotated[int, typer.Option(help="Container port for domain")] = 80,
    service: Annotated[str | None, typer.Option("--service", "-s", help="Docker Compose service name for domain")] = None,
    https: Annotated[bool, typer.Option("--https/--no-https", help="Enable HTTPS")] = False,
    wait: Annotated[bool, typer.Option("--wait/--no-wait", help="Wait for deploy + health check")] = False,
    timeout: Annotated[int, typer.Option(help="Max seconds to wait")] = 300,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without executing")] = False,
) -> None:
    """Deploy a GitHub-sourced service to Dokploy in one atomic command.

    Handles: project resolution, GitHub provider linking, compose creation,
    domain setup, deployment, and health verification.
    """
    c: AppContext = ctx.obj

    # Parse owner/repo
    if "/" not in repo:
        c.output.error("--repo must be in owner/repo format (e.g. tgunawandev/kodemeio-react)")
        raise typer.Exit(1)
    owner, repo_name = repo.split("/", 1)

    steps_total = 7 if wait else 6

    # --- Step 1: Resolve project → environment ---
    _step(c, 1, steps_total, "Resolving project...")
    env_id = _resolve_environment(c, project, dry_run)
    if not env_id:
        _fail(c, 1, steps_total, f"Project '{project}' not found or has no environment")
        raise typer.Exit(1)
    _ok(c, 1, steps_total, f"Project '{project}' → env {env_id}")

    # --- Step 2: Find GitHub provider ---
    _step(c, 2, steps_total, "Finding GitHub provider...")
    github_id = _find_github_app_id(c, dry_run)
    if not github_id:
        _fail(c, 2, steps_total, "No GitHub provider configured. Set up GitHub App in Dokploy UI → Settings → Git.")
        raise typer.Exit(1)
    _ok(c, 2, steps_total, f"GitHub provider → githubId {github_id}")

    # --- Step 3: Create or update compose ---
    _step(c, 3, steps_total, "Setting up compose service...")
    compose_id = _setup_compose(c, env_id, name, owner, repo_name, branch, compose_path, github_id, dry_run)
    if not compose_id:
        _fail(c, 3, steps_total, "Failed to create/update compose service")
        raise typer.Exit(1)
    _ok(c, 3, steps_total, f"Compose '{name}' ready ({compose_id})")

    # --- Step 4: Add domain ---
    if domain:
        _step(c, 4, steps_total, f"Configuring domain {domain}...")
        _setup_domain(c, compose_id, domain, port, service or name, https, dry_run)
        _ok(c, 4, steps_total, f"Domain {domain}:{port} configured")
    else:
        _ok(c, 4, steps_total, "No domain (skipped)")

    # --- Step 5: Deploy ---
    _step(c, 5, steps_total, "Triggering deployment...")
    if dry_run:
        _ok(c, 5, steps_total, "[dry-run] Would deploy")
    else:
        try:
            c.client.post("/compose.deployCompose", json={"composeId": compose_id})
            _ok(c, 5, steps_total, "Deployment triggered")
        except Exception as e:
            _fail(c, 5, steps_total, f"Deploy failed: {e}")
            raise typer.Exit(1)

    # --- Step 6: Wait for deployment ---
    _step(c, 6, steps_total, "Waiting for deployment...")
    if dry_run:
        _ok(c, 6, steps_total, "[dry-run] Would wait")
    else:
        status, elapsed, error = _wait_for_deployment(c, compose_id, timeout)
        if status == "done":
            _ok(c, 6, steps_total, f"Deployment done ({elapsed}s)")
        elif status == "error":
            _fail(c, 6, steps_total, f"Deployment FAILED after {elapsed}s")
            if error:
                c.output.error(f"Build error: {error[:500]}")
            raise typer.Exit(1)
        else:
            _fail(c, 6, steps_total, f"Deployment timeout after {timeout}s (status: {status})")
            raise typer.Exit(1)

    # --- Step 7: Health check ---
    if wait and domain:
        _step(c, 7, steps_total, f"Health checking {'https' if https else 'http'}://{domain}...")
        if dry_run:
            _ok(c, 7, steps_total, "[dry-run] Would verify")
        else:
            scheme = "https" if https else "http"
            healthy = _health_check(c, f"{scheme}://{domain}", 60)
            if healthy:
                _ok(c, 7, steps_total, f"Health check passed — {scheme}://{domain}")
            else:
                c.output.warn(f"Health check did not pass within 60s. Site may need Traefik propagation time.")
                c.output.info(f"Try: curl -sL {scheme}://{domain}")

    # Final summary
    url = f"{'https' if https else 'http'}://{domain}" if domain else "(no domain)"
    c.output.success(f"Deployment complete: {name} → {url}")


# --- Helper functions ---

def _step(c: AppContext, n: int, total: int, msg: str) -> None:
    c.output.info(f"Step {n}/{total}: {msg}")


def _ok(c: AppContext, n: int, total: int, msg: str) -> None:
    c.output.success(f"Step {n}/{total}: {msg}")


def _fail(c: AppContext, n: int, total: int, msg: str) -> None:
    c.output.error(f"Step {n}/{total}: {msg}")


def _resolve_environment(c: AppContext, project_name: str, dry_run: bool) -> str:
    if dry_run:
        return "dry-run-env-id"
    projects = c.client.get("/project.all")
    if not isinstance(projects, list):
        return ""
    for p in projects:
        if p.get("name", "").lower() == project_name.lower():
            envs = p.get("environments", [])
            if envs:
                return envs[0].get("environmentId", "")
            # Fallback: check if env is nested differently
            env_id = p.get("environmentId")
            if env_id:
                return env_id
    return ""


def _find_github_app_id(c: AppContext, dry_run: bool) -> str:
    if dry_run:
        return "dry-run-github-id"
    providers = c.client.get("/gitProvider.getAll")
    if not isinstance(providers, list):
        return ""
    for p in providers:
        ptype = p.get("gitProviderType", p.get("providerType", ""))
        if ptype == "github":
            github = p.get("github", {})
            if isinstance(github, dict):
                return github.get("githubId", "")
    return ""


def _setup_compose(
    c: AppContext, env_id: str, name: str, owner: str, repo: str,
    branch: str, compose_path: str, github_id: str, dry_run: bool,
) -> str:
    if dry_run:
        return "dry-run-compose-id"

    # Check if compose already exists
    existing_id = _find_existing_compose(c, env_id, name)

    if existing_id:
        # Update existing
        c.client.post("/compose.update", json={
            "composeId": existing_id,
            "sourceType": "github",
            "repository": repo,
            "owner": owner,
            "branch": branch,
            "composePath": compose_path,
            "githubId": github_id,
        })
        return existing_id
    else:
        # Create new
        result = c.client.post("/compose.create", json={
            "name": name,
            "environmentId": env_id,
        })
        compose_id = result.get("composeId", "") if isinstance(result, dict) else ""
        if not compose_id:
            return ""

        # Link GitHub source
        c.client.post("/compose.update", json={
            "composeId": compose_id,
            "sourceType": "github",
            "repository": repo,
            "owner": owner,
            "branch": branch,
            "composePath": compose_path,
            "githubId": github_id,
        })
        return compose_id


def _find_existing_compose(c: AppContext, env_id: str, name: str) -> str:
    """Find compose by name in environment."""
    projects = c.client.get("/project.all")
    if not isinstance(projects, list):
        return ""
    for p in projects:
        for env in p.get("environments", []):
            if env.get("environmentId") == env_id:
                for comp in env.get("compose", []):
                    if comp.get("name", "").lower() == name.lower():
                        return comp.get("composeId", "")
    # Also check via compose in project root
    for p in projects:
        for comp in p.get("compose", []):
            if comp.get("name", "").lower() == name.lower():
                return comp.get("composeId", "")
    return ""


def _setup_domain(
    c: AppContext, compose_id: str, host: str, port: int,
    service_name: str, https: bool, dry_run: bool,
) -> None:
    if dry_run:
        return

    # Check if domain already exists
    existing = c.client.get("/domain.byComposeId", params={"composeId": compose_id})
    if isinstance(existing, list):
        for d in existing:
            if d.get("host") == host:
                return  # Already exists, skip

    payload: dict = {
        "host": host,
        "port": port,
        "https": https,
        "serviceName": service_name,
        "composeId": compose_id,
    }
    if https:
        payload["certificateType"] = "letsencrypt"
    c.client.post("/domain.create", json=payload)


def _wait_for_deployment(c: AppContext, compose_id: str, timeout: int) -> tuple[str, int, str]:
    """Poll deployment status. Returns (status, elapsed_seconds, error_detail)."""
    start = time.monotonic()
    last_status = "unknown"

    while (elapsed := int(time.monotonic() - start)) < timeout:
        try:
            deployments = c.client.get("/deployment.all", params={"composeId": compose_id})
            if isinstance(deployments, list) and deployments:
                # Sort by created desc, get latest
                latest = sorted(deployments, key=lambda d: d.get("createdAt", ""), reverse=True)[0]
                last_status = latest.get("status", "unknown")

                if last_status == "done":
                    return "done", elapsed, ""
                elif last_status == "error":
                    # Try to get error logs
                    did = latest.get("deploymentId", "")
                    error = ""
                    if did:
                        try:
                            logs = c.client.get("/deployment.readLog", params={"deploymentId": did})
                            if isinstance(logs, str):
                                error = logs
                        except Exception:
                            pass
                    return "error", elapsed, error
        except Exception:
            pass

        time.sleep(10)

    return last_status, timeout, ""


def _health_check(c: AppContext, url: str, timeout: int) -> bool:
    """Poll URL until 200 or timeout."""
    import httpx

    start = time.monotonic()
    while (time.monotonic() - start) < timeout:
        try:
            r = httpx.get(url, follow_redirects=True, timeout=10, verify=False)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(5)
    return False
```

- [ ] **Step 2: Register in cli.py**

Read `cli.py`, find the command registration block, and add:

```python
from kctl_dokploy.commands.quickdeploy import app as quickdeploy_app
app.add_typer(quickdeploy_app, name="quickdeploy")
```

- [ ] **Step 3: Reinstall and verify**

```bash
uv tool install --force ./packages/kctl-dokploy
kctl-dokploy quickdeploy run --help  # Should show all options
kctl-dokploy quickdeploy run --name test --project kidneuro-service \
  --repo tgunawandev/kodemeio-react --compose-path compose/docker-compose.terakidz.yml \
  --domain terakidz.com --port 3006 --service terakidz-web --dry-run
```

- [ ] **Step 4: Commit**

```bash
git add packages/kctl-dokploy/src/kctl_dokploy/commands/quickdeploy.py \
       packages/kctl-dokploy/src/kctl_dokploy/cli.py
git commit -m "feat(kctl-dokploy): add quickdeploy command for atomic GitHub→Dokploy deployments"
```

---

## Task 5: Update dokploy-admin SKILL.md

**Files:**
- Modify: `/home/tgunawan/.claude/skills/dokploy-admin/SKILL.md`

- [ ] **Step 1: Add Quick Deploy section**

Add after the "## Deployment Workflow" section:

```markdown
## AI Quick Deploy (Recommended)

Deploy any GitHub-sourced service in ONE command:

```bash
kctl-dokploy quickdeploy run \
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

Next.js marketing site:
```bash
kctl-dokploy quickdeploy run -n terakidz-web -p kidneuro-service \
  -r tgunawandev/kodemeio-react -c compose/docker-compose.terakidz.yml \
  -d terakidz.com --port 3006 -s terakidz-web --https --wait
```

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Deploy status "error" | Build failure | `kctl-dokploy deployments logs <id>` |
| 404 from domain | Traefik not routing | Redeploy: `kctl-dokploy compose redeploy <id>` |
| 521 from Cloudflare | SSL mode mismatch | Set CF SSL to "flexible" or use `--no-https` |
| "No GitHub provider" | App not installed | Setup in Dokploy UI → Settings → Git |

### Important: GitHub Provider IDs

Dokploy has TWO different GitHub IDs:
- `gitProviderId` — the provider record (shown in `git list`)
- `github.githubId` — the GitHub App installation ID (needed by compose)

Use `kctl-dokploy git resolve` to get the correct ID for compose linking.
The `quickdeploy` command handles this automatically.
```

- [ ] **Step 2: Commit**

```bash
git add /home/tgunawan/.claude/skills/dokploy-admin/SKILL.md
git commit -m "docs(kctl-dokploy): add AI Quick Deploy section to SKILL.md"
```

---

## Task 6: Deploy terakidz.com using quickdeploy

**Verify the fix by actually deploying terakidz.com:**

- [ ] **Step 1: Clean up old compose**

```bash
kctl-dokploy compose delete uWvTvQKuXKPMsfQndoQxJ --force
```

- [ ] **Step 2: Deploy with quickdeploy**

```bash
kctl-dokploy quickdeploy run \
  --name terakidz-web \
  --project kidneuro-service \
  --repo tgunawandev/kodemeio-react \
  --branch main \
  --compose-path compose/docker-compose.terakidz.yml \
  --domain terakidz.com \
  --port 3006 \
  --service terakidz-web \
  --wait
```

Expected: All 7 steps pass, site live at https://terakidz.com

- [ ] **Step 3: Verify site**

```bash
curl -sL https://terakidz.com | grep -o "<title>[^<]*</title>"
```

Expected: Contains "Terakidz" or "Platform Terapi"

---

## Summary

| Task | Component | Description |
|---|---|---|
| 1 | Bug fix | Remove ALL `[:12]` ID truncations (13 locations, 6 files) |
| 2 | Feature | Add GitHub App ID column + `git resolve` command |
| 3 | Bug fix | Auto-resolve githubId in `compose update` |
| 4 | Feature | New `quickdeploy` command (atomic deploy workflow) |
| 5 | Docs | Update SKILL.md with AI Quick Deploy section |
| 6 | Verify | Deploy terakidz.com using the new command |
