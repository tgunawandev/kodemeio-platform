"""Atomic GitHub → Dokploy deployment in one command."""

from __future__ import annotations

import time
from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext
from kctl_dokploy.core.validators import (
    validate_project_exists,
    find_github_app_id,
    disable_autodeploy,
    validate_service_name,
)

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
    service: Annotated[
        str | None, typer.Option("--service", "-s", help="Docker Compose service name for domain")
    ] = None,
    https: Annotated[bool, typer.Option("--https/--no-https", help="Enable HTTPS")] = False,
    wait: Annotated[bool, typer.Option("--wait/--no-wait", help="Wait for deploy + health check")] = False,
    timeout: Annotated[int, typer.Option(help="Max seconds to wait")] = 300,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without executing")] = False,
) -> None:
    """Deploy a GitHub-sourced service to Dokploy in one atomic command.

    Uses a 2-deploy flow when a domain is configured:
      1st deploy: build container + Dokploy discovers services
      2nd deploy: apply Traefik labels after domain is linked to discovered service

    Without --domain, only a single deploy is needed.
    """
    c: AppContext = ctx.obj

    # Parse owner/repo
    if "/" not in repo:
        c.output.error("--repo must be in owner/repo format (e.g. tgunawandev/kodemeio-react)")
        raise typer.Exit(1)
    owner, repo_name = repo.split("/", 1)

    # Step count depends on whether domain is provided
    # With domain: 8 steps (2 deploys + domain between them + health check)
    # Without domain: 5 steps (1 deploy + wait)
    if domain:
        steps_total = 8
    else:
        steps_total = 5

    # --- Step 1/N: Resolve project (Gate 2) ---
    _step(c, 1, steps_total, "Resolving project...")
    if dry_run:
        env_id = "dry-run-env-id"
        _ok(c, 1, steps_total, f"[dry-run] Project '{project}'")
    else:
        ok, msg, pid, env_id = validate_project_exists(c.client, project)
        if not ok:
            _fail(c, 1, steps_total, msg)
            raise typer.Exit(1)
        _ok(c, 1, steps_total, msg)

    # --- Step 2/N: Find GitHub provider (Gate 3) ---
    _step(c, 2, steps_total, "Finding GitHub provider...")
    if dry_run:
        github_id = "dry-run-github-id"
        _ok(c, 2, steps_total, "[dry-run] GitHub provider")
    else:
        ok, msg, github_id = find_github_app_id(c.client)
        if not ok:
            _fail(c, 2, steps_total, msg)
            raise typer.Exit(1)
        _ok(c, 2, steps_total, msg)

    # --- Step 3/N: Create or update compose (link GitHub source) ---
    _step(c, 3, steps_total, "Setting up compose service...")
    compose_id = _setup_compose(c, env_id, name, owner, repo_name, branch, compose_path, github_id, dry_run)
    if not compose_id:
        _fail(c, 3, steps_total, "Failed to create/update compose service")
        raise typer.Exit(1)
    _ok(c, 3, steps_total, f"Compose '{name}' ready ({compose_id})")

    # Gate 4: Disable autodeploy
    if not dry_run and compose_id:
        ok, msg = disable_autodeploy(c.client, compose_id)
        if not ok:
            c.output.warn(f"  Autodeploy: {msg}")

    if domain:
        # === 2-DEPLOY FLOW (with domain) ===

        # --- Step 4/8: First deploy (build + discover services) ---
        _step(c, 4, steps_total, "First deploy (build + service discovery)...")
        if dry_run:
            _ok(c, 4, steps_total, "[dry-run] Would trigger first deploy")
        else:
            try:
                c.client.post("/compose.deploy", json={"composeId": compose_id})
                _ok(c, 4, steps_total, "First deployment triggered")
            except Exception as e:
                _fail(c, 4, steps_total, f"First deploy failed: {e}")
                raise typer.Exit(1)

        # --- Step 5/8: Wait for first deploy to complete ---
        _step(c, 5, steps_total, "Waiting for first deploy to complete...")
        if dry_run:
            _ok(c, 5, steps_total, "[dry-run] Would wait for first deploy")
        else:
            status, elapsed, error = _wait_for_deployment(c, compose_id, timeout)
            if status == "done":
                _ok(c, 5, steps_total, f"First deploy done ({elapsed}s) — services discovered")
            elif status == "error":
                _fail(c, 5, steps_total, f"First deploy FAILED after {elapsed}s")
                if error:
                    c.output.error(f"Build error: {error[:500]}")
                raise typer.Exit(1)
            else:
                _fail(c, 5, steps_total, f"First deploy timeout after {timeout}s (status: {status})")
                raise typer.Exit(1)

        # --- Step 6/8: Add domain (NOW Dokploy can link to discovered service) ---
        # Gate 5: Validate service name before domain creation
        if domain and not dry_run:
            svc = service or name
            ok, msg = validate_service_name(c.client, compose_id, svc)
            if not ok:
                _fail(c, 6, steps_total, msg)
                raise typer.Exit(1)
            c.output.info(f"  {msg}")

        _step(c, 6, steps_total, f"Adding domain {domain} → service '{service or name}'...")
        _setup_domain(c, compose_id, domain, port, service or name, https, dry_run)
        if dry_run:
            _ok(c, 6, steps_total, f"[dry-run] Would add domain {domain}:{port}")
        else:
            _ok(c, 6, steps_total, f"Domain {domain}:{port} → {service or name}")

        # --- Step 7/8: Second deploy (apply Traefik labels) ---
        _step(c, 7, steps_total, "Second deploy (apply Traefik labels)...")
        if dry_run:
            _ok(c, 7, steps_total, "[dry-run] Would trigger second deploy")
        else:
            try:
                c.client.post("/compose.deploy", json={"composeId": compose_id})
                _ok(c, 7, steps_total, "Second deployment triggered")
            except Exception as e:
                _fail(c, 7, steps_total, f"Second deploy failed: {e}")
                raise typer.Exit(1)

            # Wait for second deploy
            status, elapsed, error = _wait_for_deployment(c, compose_id, timeout)
            if status == "done":
                c.output.success(f"  Second deploy done ({elapsed}s) — Traefik labels applied")
            elif status == "error":
                _fail(c, 7, steps_total, f"Second deploy FAILED after {elapsed}s")
                if error:
                    c.output.error(f"Build error: {error[:500]}")
                raise typer.Exit(1)
            else:
                _fail(c, 7, steps_total, f"Second deploy timeout after {timeout}s (status: {status})")
                raise typer.Exit(1)

        # --- Step 8/8: Health check ---
        if wait:
            scheme = "https" if https else "http"
            _step(c, 8, steps_total, f"Health checking {scheme}://{domain}...")
            if dry_run:
                _ok(c, 8, steps_total, "[dry-run] Would verify health")
            else:
                healthy = _health_check(c, f"{scheme}://{domain}", 60)
                if healthy:
                    _ok(c, 8, steps_total, f"Health check passed — {scheme}://{domain}")
                else:
                    c.output.warn("Health check did not pass within 60s. Site may need Traefik propagation time.")
                    c.output.info(f"Try: curl -sL {scheme}://{domain}")
        else:
            _ok(c, 8, steps_total, "Health check skipped (use --wait to enable)")

    else:
        # === SINGLE-DEPLOY FLOW (no domain) ===

        # --- Step 4/5: Deploy ---
        _step(c, 4, steps_total, "Triggering deployment...")
        if dry_run:
            _ok(c, 4, steps_total, "[dry-run] Would deploy")
        else:
            try:
                c.client.post("/compose.deploy", json={"composeId": compose_id})
                _ok(c, 4, steps_total, "Deployment triggered")
            except Exception as e:
                _fail(c, 4, steps_total, f"Deploy failed: {e}")
                raise typer.Exit(1)

        # --- Step 5/5: Wait for deployment ---
        _step(c, 5, steps_total, "Waiting for deployment...")
        if dry_run:
            _ok(c, 5, steps_total, "[dry-run] Would wait")
        else:
            status, elapsed, error = _wait_for_deployment(c, compose_id, timeout)
            if status == "done":
                _ok(c, 5, steps_total, f"Deployment done ({elapsed}s)")
            elif status == "error":
                _fail(c, 5, steps_total, f"Deployment FAILED after {elapsed}s")
                if error:
                    c.output.error(f"Build error: {error[:500]}")
                raise typer.Exit(1)
            else:
                _fail(c, 5, steps_total, f"Deployment timeout after {timeout}s (status: {status})")
                raise typer.Exit(1)

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
    c: AppContext,
    env_id: str,
    name: str,
    owner: str,
    repo: str,
    branch: str,
    compose_path: str,
    github_id: str,
    dry_run: bool,
) -> str:
    if dry_run:
        return "dry-run-compose-id"

    # Check if compose already exists
    existing_id = _find_existing_compose(c, env_id, name)

    if existing_id:
        # Update existing
        c.client.post(
            "/compose.update",
            json={
                "composeId": existing_id,
                "sourceType": "github",
                "repository": repo,
                "owner": owner,
                "branch": branch,
                "composePath": compose_path,
                "githubId": github_id,
            },
        )
        return existing_id
    else:
        # Create new
        result = c.client.post(
            "/compose.create",
            json={
                "name": name,
                "environmentId": env_id,
            },
        )
        compose_id = result.get("composeId", "") if isinstance(result, dict) else ""
        if not compose_id:
            return ""

        # Link GitHub source
        c.client.post(
            "/compose.update",
            json={
                "composeId": compose_id,
                "sourceType": "github",
                "repository": repo,
                "owner": owner,
                "branch": branch,
                "composePath": compose_path,
                "githubId": github_id,
            },
        )
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
    c: AppContext,
    compose_id: str,
    host: str,
    port: int,
    service_name: str,
    https: bool,
    dry_run: bool,
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
            deployments = c.client.get("/deployment.allByCompose", params={"composeId": compose_id})
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
