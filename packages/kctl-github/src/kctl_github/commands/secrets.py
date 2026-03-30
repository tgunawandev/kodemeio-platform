"""Cross-repo secret management."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_github.core.callbacks import AppContext
from kctl_github.core.client import gh_run

app = typer.Typer(help="Cross-repo Actions secret management.")


@app.command("list")
def list_secrets(
    ctx: typer.Context,
    repo: Annotated[str, typer.Argument(help="Repository name")],
) -> None:
    """List Actions secrets for a repo."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client
    owner = client.organization

    data = client.get(f"/repos/{owner}/{repo}/actions/secrets")
    secrets = data.get("secrets", [])

    if out.json_mode:
        out.raw_json([{"name": s["name"], "updated_at": s.get("updated_at", "")} for s in secrets])
        return

    rows = [[s["name"], s.get("updated_at", "")[:10]] for s in secrets]
    out.table(
        f"Secrets: {repo}",
        [("Name", "cyan"), ("Last Updated", "yellow")],
        rows,
    )


@app.command()
def audit(ctx: typer.Context) -> None:
    """Check which repos have which secrets (matrix view)."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client
    owner = client.organization

    repos = client.get_repos()
    all_secret_names: set[str] = set()
    repo_secrets: dict[str, set[str]] = {}

    for repo in repos:
        name = repo["name"]
        try:
            data = client.get(f"/repos/{owner}/{name}/actions/secrets")
            secrets = data.get("secrets", [])
            secret_names = {s["name"] for s in secrets}
            all_secret_names.update(secret_names)
            repo_secrets[name] = secret_names
        except Exception:  # noqa: BLE001
            repo_secrets[name] = set()

    sorted_secrets = sorted(all_secret_names)

    if out.json_mode:
        out.raw_json({repo: [s for s in sorted_secrets if s in secs] for repo, secs in repo_secrets.items()})
        return

    columns: list[tuple[str, str]] = [("Repo", "cyan")]
    columns.extend((s, "") for s in sorted_secrets)

    rows = []
    for repo_name in sorted(repo_secrets.keys()):
        row = [repo_name]
        for secret in sorted_secrets:
            row.append("Y" if secret in repo_secrets[repo_name] else "-")
        rows.append(row)

    out.table("Secrets Audit", columns, rows)


@app.command("set")
def set_secret(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Secret name")],
    repos: Annotated[str, typer.Option("--repos", "-r", help="Comma-separated repo names")],
) -> None:
    """Set a secret across multiple repos (prompts for value)."""
    actx: AppContext = ctx.obj
    out = actx.output
    owner = actx.client.organization

    value = typer.prompt(f"Secret value for {name}", hide_input=True)
    repo_list = [r.strip() for r in repos.split(",")]

    for repo in repo_list:
        try:
            gh_run(["secret", "set", name, "--repo", f"{owner}/{repo}", "--body", value])
            out.success(f"Set {name} in {repo}")
        except Exception as e:  # noqa: BLE001
            out.error(f"Failed to set {name} in {repo}: {e}")


@app.command()
def rotate(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Secret name to rotate")],
) -> None:
    """Update a secret across all repos that have it."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client
    owner = client.organization

    value = typer.prompt(f"New value for {name}", hide_input=True)
    repos = client.get_repos()
    updated = 0

    for repo in repos:
        repo_name = repo["name"]
        try:
            data = client.get(f"/repos/{owner}/{repo_name}/actions/secrets")
            secret_names = {s["name"] for s in data.get("secrets", [])}
            if name in secret_names:
                gh_run(["secret", "set", name, "--repo", f"{owner}/{repo_name}", "--body", value])
                out.success(f"Rotated {name} in {repo_name}")
                updated += 1
        except Exception as e:  # noqa: BLE001
            out.error(f"Failed for {repo_name}: {e}")

    out.info(f"Rotated {name} in {updated} repo(s)")
