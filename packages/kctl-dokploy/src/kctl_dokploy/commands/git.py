"""Git repository/provider management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Manage Git providers and repositories.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all configured Git providers."""
    c: AppContext = ctx.obj
    providers = c.client.get("/gitProvider.getAll")
    if not isinstance(providers, list):
        providers = []
    rows = []
    for g in providers:
        gid = g.get("gitProviderId", "")
        github_inner = g.get("github", {})
        github_app_id = github_inner.get("githubId", "") if isinstance(github_inner, dict) else ""
        name = g.get("name", g.get("gitProviderType", ""))
        ptype = g.get("gitProviderType", g.get("providerType", "unknown"))
        org = g.get("organizationName", g.get("organization", "-"))
        created = g.get("createdAt", "-")
        rows.append([gid, github_app_id, name, ptype, str(org), str(created)])
    c.output.table(
        "Git Providers",
        [
            ("Provider ID", "dim"),
            ("GitHub App ID", "cyan"),
            ("Name", ""),
            ("Type", ""),
            ("Organization", ""),
            ("Created", "dim"),
        ],
        rows,
        data_for_json=providers,
    )


@app.command()
def resolve(
    ctx: typer.Context,
    provider_id: Annotated[
        str | None, typer.Argument(help="Git provider ID (optional, uses first GitHub provider if omitted)")
    ] = None,
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
        ptype = p.get("gitProviderType", p.get("providerType", ""))
        if ptype == "github":
            github = p.get("github", {})
            if isinstance(github, dict) and github.get("githubId"):
                github_id = github["githubId"]
                c.output.success(f"GitHub App ID: {github_id}")
                if c.json_mode:
                    c.output.raw_json({"githubId": github_id, "gitProviderId": p.get("gitProviderId")})
                return

    c.output.error("No GitHub provider found" + (f" with ID {provider_id}" if provider_id else ""))
    raise typer.Exit(1)


@app.command()
def get(
    ctx: typer.Context,
    provider_id: Annotated[str, typer.Argument(help="Git provider ID")],
) -> None:
    """Get Git provider details."""
    c: AppContext = ctx.obj
    providers = c.client.get("/gitProvider.getAll")
    data = next(
        (p for p in (providers if isinstance(providers, list) else []) if p.get("gitProviderId") == provider_id), None
    )
    if not isinstance(data, dict):
        c.output.error(f"Git provider '{provider_id}' not found")
        raise typer.Exit(1)
    sections = [
        (
            "Git Provider",
            [
                ("ID", data.get("gitProviderId", "")),
                ("Name", data.get("name", "")),
                ("Type", data.get("gitProviderType", "unknown")),
                ("Organization", data.get("organizationName", "-")),
                ("Created", data.get("createdAt", "-")),
            ],
        ),
    ]
    c.output.detail(f"Git Provider: {data.get('name', '')}", sections, data_for_json=data)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Provider name")],
    provider_type: Annotated[str, typer.Option("--type", "-t", help="Provider type (github, gitlab, bitbucket)")],
    organization: Annotated[str | None, typer.Option("--org", help="Organization name")] = None,
    access_token: Annotated[str | None, typer.Option("--token", help="Access token", envvar="GIT_TOKEN")] = None,
) -> None:
    """Create a new Git provider."""
    c: AppContext = ctx.obj
    payload: dict = {
        "name": name,
        "gitProviderType": provider_type,
    }
    if organization:
        payload["organizationName"] = organization
    if access_token:
        payload["accessToken"] = access_token
    result = c.client.post("/gitProvider.create", json=payload)
    gid = result.get("gitProviderId", "") if isinstance(result, dict) else ""
    c.output.success(f"Git provider '{name}' created: {gid}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def update(
    ctx: typer.Context,
    provider_id: Annotated[str, typer.Argument(help="Git provider ID")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="New name")] = None,
    organization: Annotated[str | None, typer.Option("--org", help="New organization")] = None,
    access_token: Annotated[str | None, typer.Option("--token", help="New access token")] = None,
) -> None:
    """Update a Git provider."""
    c: AppContext = ctx.obj
    payload: dict = {"gitProviderId": provider_id}
    if name is not None:
        payload["name"] = name
    if organization is not None:
        payload["organizationName"] = organization
    if access_token is not None:
        payload["accessToken"] = access_token
    result = c.client.post("/gitProvider.update", json=payload)
    c.output.success(f"Git provider '{provider_id}' updated")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def remove(
    ctx: typer.Context,
    provider_id: Annotated[str, typer.Argument(help="Git provider ID to remove")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Remove a Git provider (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Remove Git provider '{provider_id}'? This cannot be undone.", abort=True)
    result = c.client.post("/gitProvider.remove", json={"gitProviderId": provider_id})
    c.output.success(f"Git provider '{provider_id}' removed")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("test")
def test_connection(
    ctx: typer.Context,
    provider_id: Annotated[str, typer.Argument(help="Git provider ID to test")],
) -> None:
    """Test connection to a Git provider."""
    c: AppContext = ctx.obj
    c.output.info(f"Testing Git provider '{provider_id}'...")
    result = c.client.post("/gitProvider.testConnection", json={"gitProviderId": provider_id})
    c.output.success(f"Git provider '{provider_id}' connection test passed")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def branches(
    ctx: typer.Context,
    provider_id: Annotated[str, typer.Argument(help="Git provider ID")],
    owner: Annotated[str, typer.Option("--owner", "-o", help="Repository owner")],
    repo: Annotated[str, typer.Option("--repo", "-r", help="Repository name")],
) -> None:
    """List branches for a repository on a Git provider."""
    c: AppContext = ctx.obj
    data = c.client.post(
        "/gitProvider.getBranches",
        json={
            "gitProviderId": provider_id,
            "owner": owner,
            "repo": repo,
        },
    )
    branch_list = data if isinstance(data, list) else data.get("branches", []) if isinstance(data, dict) else []
    rows = []
    for b in branch_list:
        if isinstance(b, str):
            rows.append([b])
        elif isinstance(b, dict):
            rows.append([b.get("name", b.get("branch", str(b)))])
        else:
            rows.append([str(b)])
    c.output.table(
        f"Branches ({owner}/{repo})",
        [("Branch", "cyan")],
        rows,
        data_for_json=data if isinstance(data, (list, dict)) else {"branches": branch_list},
    )
