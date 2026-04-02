"""Compose service management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Manage Dokploy compose services.")


@app.command("list")
def list_(
    ctx: typer.Context,
    project_id: Annotated[str | None, typer.Option("--project", "-p", help="Filter by project ID")] = None,
) -> None:
    """List compose services, optionally filtered by project."""
    c: AppContext = ctx.obj
    if project_id:
        services = c.client.get("/compose.all", params={"projectId": project_id})
    else:
        projects = c.client.get("/project.all")
        if not isinstance(projects, list):
            projects = []
        services = []
        for p in projects:
            for comp in p.get("compose", []):
                comp["_projectName"] = p.get("name", "")
                services.append(comp)
    if not isinstance(services, list):
        services = []
    rows = []
    json_data = []
    for s in services:
        cid = s.get("composeId", "")
        name = s.get("name", "")
        status = s.get("composeStatus", "unknown")
        project = s.get("_projectName", s.get("projectName", ""))
        rows.append([cid, name, status, project])
        json_data.append(
            {
                "composeId": cid,
                "name": name,
                "status": status,
                "project": project,
            }
        )
    c.output.table(
        "Compose Services",
        [("ID", "dim"), ("Name", "cyan"), ("Status", ""), ("Project", "green")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def get(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
) -> None:
    """Get details for a compose service."""
    c: AppContext = ctx.obj
    data = c.client.get("/compose.one", params={"composeId": compose_id})
    if not isinstance(data, dict):
        c.output.error(f"Compose service '{compose_id}' not found")
        raise typer.Exit(1)
    name = data.get("name", "unknown")
    status = data.get("composeStatus", "unknown")
    source_type = data.get("sourceType", "unknown")
    updated = data.get("updatedAt", data.get("createdAt", "-"))
    sections = [
        (
            "Compose Service",
            [
                ("ID", data.get("composeId", "")),
                ("Name", name),
                ("Status", status),
                ("Source Type", source_type),
                ("Updated", updated),
            ],
        ),
    ]
    domains = data.get("domains", [])
    if domains:
        domain_kvs = [(d.get("host", ""), str(d.get("port", ""))) for d in domains]
        sections.append(("Domains", domain_kvs))
    c.output.detail(f"Compose: {name}", sections, data_for_json=data)


@app.command()
def create(
    ctx: typer.Context,
    environment_id: Annotated[str, typer.Argument(help="Environment ID (from kctl-dokploy projects get)")],
    name: Annotated[str, typer.Option("--name", "-n", help="Compose service name")],
    description: Annotated[str | None, typer.Option("--description", "-d", help="Description")] = None,
    server_id: Annotated[str | None, typer.Option("--server", help="Server ID")] = None,
    compose_file: Annotated[str | None, typer.Option("--file", "-f", help="Path to docker-compose file")] = None,
) -> None:
    """Create a new compose service in a project environment."""
    c: AppContext = ctx.obj
    payload: dict = {"name": name, "environmentId": environment_id}
    if description:
        payload["description"] = description
    if server_id:
        payload["serverId"] = server_id
    if compose_file:
        import pathlib

        payload["composeFile"] = pathlib.Path(compose_file).read_text()
    result = c.client.post("/compose.create", json=payload)
    cid = result.get("composeId", "") if isinstance(result, dict) else ""
    c.output.success(f"Compose '{name}' created: {cid}")
    if c.json_mode:
        c.output.raw_json(result)


def _resolve_github_app_id(c: AppContext, id_or_provider_id: str) -> str | None:
    """Resolve a gitProviderId to its inner github.githubId if needed.

    Dokploy has two IDs:
    - gitProviderId: the provider record
    - github.githubId: the GitHub App installation ID (FK in compose table)

    This function accepts either and returns the github.githubId.
    """
    try:
        providers = c.client.get("/gitProvider.getAll")
    except Exception:
        return None
    if not isinstance(providers, list):
        return None
    for p in providers:
        github = p.get("github", {})
        if not isinstance(github, dict):
            continue
        inner_id = github.get("githubId", "")
        # If the provided ID IS already the inner github.githubId, return it
        if inner_id == id_or_provider_id:
            return id_or_provider_id
        # If the provided ID is the outer gitProviderId, resolve to inner
        if p.get("gitProviderId") == id_or_provider_id:
            return inner_id if inner_id else None
    return None


@app.command()
def update(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Option("--id", "-i", help="Compose service ID")],
    env_content: Annotated[str | None, typer.Option("--env", help="Environment variables content")] = None,
    compose_file: Annotated[str | None, typer.Option("--compose-file", help="Path to docker-compose file")] = None,
    source_type: Annotated[
        str | None, typer.Option("--source-type", help="Source type: raw, github, gitlab, git")
    ] = None,
    repository: Annotated[str | None, typer.Option("--repo", help="GitHub repository name")] = None,
    owner: Annotated[str | None, typer.Option("--owner", help="GitHub owner/org (e.g. tgunawandev)")] = None,
    branch: Annotated[str | None, typer.Option("--branch", help="Git branch")] = None,
    compose_path: Annotated[str | None, typer.Option("--compose-path", help="Path to compose file in repo")] = None,
    github_id: Annotated[str | None, typer.Option("--github-id", help="Dokploy GitHub provider ID")] = None,
) -> None:
    """Update a compose service configuration."""
    c: AppContext = ctx.obj
    payload: dict = {"composeId": compose_id}
    if env_content is not None:
        payload["env"] = env_content
    if compose_file is not None:
        import pathlib

        path = pathlib.Path(compose_file)
        if not path.exists():
            c.output.error(f"File not found: {compose_file}")
            raise typer.Exit(1)
        payload["composeFile"] = path.read_text()
        payload["sourceType"] = "raw"
    if source_type is not None:
        payload["sourceType"] = source_type
    if repository is not None:
        payload["repository"] = repository
    if owner is not None:
        payload["owner"] = owner
    if branch is not None:
        payload["branch"] = branch
    if compose_path is not None:
        payload["composePath"] = compose_path
    if github_id is not None:
        payload["githubId"] = github_id
    if len(payload) == 1:
        c.output.error("No update options provided. Use --env, --compose-file, or --source-type.")
        raise typer.Exit(1)
    result = c.client.post("/compose.update", json=payload)
    c.output.success(f"Compose '{compose_id}' updated")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def delete(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete a compose service (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete compose '{compose_id}'? This cannot be undone.", abort=True)
    result = c.client.post("/compose.delete", json={"composeId": compose_id})
    c.output.success(f"Compose '{compose_id}' deleted")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def stop(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Stop a running compose service."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Stop compose '{compose_id}'?", abort=True)
    result = c.client.post("/compose.stop", json={"composeId": compose_id})
    c.output.success(f"Compose '{compose_id}' stopped")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def start(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
) -> None:
    """Start (deploy) a compose service."""
    c: AppContext = ctx.obj
    c.output.info(f"Starting compose '{compose_id}'...")
    result = c.client.post("/compose.deploy", json={"composeId": compose_id})
    c.output.success(f"Compose '{compose_id}' deployment triggered")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def redeploy(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
) -> None:
    """Stop and redeploy a compose service."""
    c: AppContext = ctx.obj
    out = c.output
    out.info(f"Redeploying compose '{compose_id}'...")
    try:
        c.client.post("/compose.stop", json={"composeId": compose_id})
        out.info("Stopped. Triggering deployment...")
    except Exception:
        out.warn("Stop failed or service was not running; proceeding with deploy")
    result = c.client.post("/compose.deploy", json={"composeId": compose_id})
    out.success(f"Compose '{compose_id}' redeployed")
    if c.json_mode:
        out.raw_json(result)


@app.command()
def logs(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
    lines: Annotated[int | None, typer.Option("--lines", "-n", help="Number of log lines")] = None,
) -> None:
    """Show logs for a compose service (fetches from deployment history)."""
    c: AppContext = ctx.obj
    # Get recent deployments and show the latest log
    deployments = c.client.get("/deployment.allByCompose", params={"composeId": compose_id})
    log_text = ""
    if isinstance(deployments, list) and deployments:
        # Sort newest first
        sorted_deps = sorted(deployments, key=lambda d: d.get("createdAt", ""), reverse=True)
        latest = sorted_deps[0]
        log_text = latest.get("logPath", latest.get("log", latest.get("logs", "")))
        if not log_text:
            log_text = f"Deployment: {latest.get('status', 'unknown')} at {latest.get('createdAt', '-')}"
    if c.json_mode:
        c.output.raw_json({"composeId": compose_id, "logs": log_text})
    else:
        c.output.header(f"Logs: {compose_id}")
        c.output.text(str(log_text))


@app.command("service-logs")
def service_logs(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
    service: Annotated[str, typer.Option("--service", "-s", help="Service name (e.g. 'odoo-init')")] = "",
    tail: Annotated[int, typer.Option("--tail", "-n", help="Number of lines from end")] = 200,
) -> None:
    """Show Docker container runtime logs for a compose service.

    Fetches actual container stdout/stderr (not Dokploy build logs).
    Works for services on both the main server and remote servers.
    """
    import subprocess

    c: AppContext = ctx.obj

    # Get compose details to find appName and serverId
    compose_data = c.client.get("/compose.one", params={"composeId": compose_id})
    if not isinstance(compose_data, dict):
        c.output.error(f"Compose '{compose_id}' not found")
        raise typer.Exit(1)

    app_name = compose_data.get("appName", "")
    server_id = compose_data.get("serverId")

    if not app_name:
        c.output.error("Compose has no appName — cannot resolve container names")
        raise typer.Exit(1)

    # Get containers for this compose
    params: dict[str, str] = {}
    if server_id:
        params["serverId"] = server_id
    containers = c.client.get("/docker.getContainers", params=params)
    if not isinstance(containers, list):
        containers = []

    # Filter containers matching this compose appName
    matching = [ct for ct in containers if app_name in ct.get("name", "")]

    # Further filter by service name if specified
    if service:
        matching = [ct for ct in matching if service in ct.get("name", "")]

    if not matching:
        # Show available containers for this compose
        all_compose_containers = [ct for ct in containers if app_name in ct.get("name", "")]
        if all_compose_containers:
            c.output.warn(f"Service '{service}' not found. Available containers:")
            for ct in all_compose_containers:
                c.output.text(f"  {ct.get('name', '')} ({ct.get('state', '')})")
        else:
            c.output.error(f"No containers found for compose '{app_name}'")
        raise typer.Exit(1)

    # Resolve server IP for SSH (remote servers) or use local docker
    server_ip = ""
    if server_id:
        server_data = compose_data.get("server", {})
        if isinstance(server_data, dict):
            server_ip = server_data.get("ipAddress", "")
        if not server_ip:
            # Fetch server details
            try:
                srv = c.client.get("/server.one", params={"serverId": server_id})
                if isinstance(srv, dict):
                    server_ip = srv.get("ipAddress", "")
            except Exception:
                pass

    for ct in matching:
        container_name = ct.get("name", "")
        state = ct.get("state", "")
        status = ct.get("status", "")
        c.output.header(f"{container_name} ({state}, {status})")

        if server_ip:
            # Remote server — use SSH
            cmd = [
                "ssh",
                "-o",
                "ConnectTimeout=10",
                "-o",
                "StrictHostKeyChecking=accept-new",
                f"root@{server_ip}",
                f"docker logs --tail {tail} {container_name} 2>&1",
            ]
        else:
            # Local server
            cmd = ["docker", "logs", "--tail", str(tail), container_name]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            log_output = proc.stdout or proc.stderr
            if log_output:
                if c.json_mode:
                    c.output.raw_json({"container": container_name, "logs": log_output})
                else:
                    c.output.text(log_output)
            else:
                c.output.warn("No logs available")
        except subprocess.TimeoutExpired:
            c.output.error(f"Timeout fetching logs from {container_name}")
        except Exception as exc:
            c.output.error(f"Failed to fetch logs: {exc}")


@app.command("cancel")
def cancel(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
) -> None:
    """Cancel a running deployment for a compose service."""
    c: AppContext = ctx.obj
    c.output.info(f"Cancelling deployment for compose '{compose_id}'...")
    result = c.client.post("/compose.cancelDeployment", json={"composeId": compose_id})
    c.output.success(f"Deployment cancelled for compose '{compose_id}'")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("services")
def services(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
) -> None:
    """List services defined in a compose service."""
    c: AppContext = ctx.obj
    data = c.client.get("/compose.loadServices", params={"composeId": compose_id})
    if not isinstance(data, list):
        data = []
    rows = []
    for svc in data:
        name = svc if isinstance(svc, str) else svc.get("name", svc.get("serviceName", str(svc)))
        rows.append([str(name)])
    c.output.table(
        f"Services in {compose_id}",
        [("Service Name", "cyan")],
        rows,
        data_for_json=data,
    )


@app.command("search")
def search(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Search query")],
) -> None:
    """Search compose services by name."""
    c: AppContext = ctx.obj
    data = c.client.get("/compose.search", params={"name": name})
    if not isinstance(data, list):
        data = []
    rows = []
    for s in data:
        cid = s.get("composeId", "")
        sname = s.get("name", "")
        status = s.get("composeStatus", "unknown")
        rows.append([cid, sname, status])
    c.output.table(
        f"Search Results: '{name}'",
        [("ID", "dim"), ("Name", "cyan"), ("Status", "")],
        rows,
        data_for_json=data,
    )


@app.command("kill-build")
def kill_build(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Kill a running build for a compose service (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Kill build for compose '{compose_id}'?", abort=True)
    result = c.client.post("/compose.killBuild", json={"composeId": compose_id})
    c.output.success(f"Build killed for compose '{compose_id}'")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("clear-deployments")
def clear_deployments(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Clear all deployment history for a compose service (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Clear all deployments for compose '{compose_id}'? This cannot be undone.", abort=True)
    result = c.client.post("/compose.clearDeployments", json={"composeId": compose_id})
    c.output.success(f"Deployments cleared for compose '{compose_id}'")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("move")
def move(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
    environment: Annotated[str, typer.Option("--environment", "-e", help="Target environment ID")],
) -> None:
    """Move a compose service to a different environment."""
    c: AppContext = ctx.obj
    result = c.client.post("/compose.move", json={"composeId": compose_id, "environmentId": environment})
    c.output.success(f"Compose '{compose_id}' moved to environment '{environment}'")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("import")
def import_compose(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
    file: Annotated[str, typer.Option("--file", "-f", help="Path to compose file to import")],
) -> None:
    """Import a docker-compose file into a compose service."""
    import pathlib

    c: AppContext = ctx.obj
    path = pathlib.Path(file)
    if not path.exists():
        c.output.error(f"File not found: {file}")
        raise typer.Exit(1)
    content = path.read_text()
    result = c.client.post("/compose.import", json={"composeId": compose_id, "composeFile": content})
    c.output.success(f"Compose file imported into '{compose_id}'")
    if c.json_mode:
        c.output.raw_json(result)
