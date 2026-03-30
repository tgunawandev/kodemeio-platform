"""Cross-repo label standardization."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_github.core.callbacks import AppContext

app = typer.Typer(help="Cross-repo label management.")


@app.command("list")
def list_labels(
    ctx: typer.Context,
    repo: Annotated[str, typer.Argument(help="Repository name")],
) -> None:
    """List labels for a repo."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client
    owner = client.organization

    labels = client.get(f"/repos/{owner}/{repo}/labels", params={"per_page": 100})

    if out.json_mode:
        out.raw_json(
            [
                {
                    "name": label["name"],
                    "color": label.get("color", ""),
                    "description": label.get("description", ""),
                }
                for label in labels
            ]
        )
        return

    rows = [[label["name"], f"#{label.get('color', '')}", label.get("description", "") or ""] for label in labels]
    out.table(
        f"Labels: {repo}",
        [("Name", "cyan"), ("Color", "yellow"), ("Description", "")],
        rows,
    )


@app.command()
def sync(
    ctx: typer.Context,
    source: Annotated[str, typer.Option("--source", "-s", help="Source repo to copy labels from")],
) -> None:
    """Copy labels from source repo to all other kodemeio-* repos."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client
    owner = client.organization

    # Get source labels
    source_labels = client.get(f"/repos/{owner}/{source}/labels", params={"per_page": 100})
    if not isinstance(source_labels, list):
        out.error("Failed to fetch source labels")
        raise typer.Exit(1)

    repos = client.get_repos()
    target_repos = [r for r in repos if r["name"] != source]

    for repo in target_repos:
        name = repo["name"]
        existing = client.get(f"/repos/{owner}/{name}/labels", params={"per_page": 100})
        existing_names = {label["name"] for label in existing} if isinstance(existing, list) else set()

        created = 0
        for label in source_labels:
            if label["name"] not in existing_names:
                try:
                    client.post(
                        f"/repos/{owner}/{name}/labels",
                        json={
                            "name": label["name"],
                            "color": label.get("color", "000000"),
                            "description": label.get("description", ""),
                        },
                    )
                    created += 1
                except Exception:  # noqa: BLE001
                    pass  # Label may already exist with different casing

        if created > 0:
            out.success(f"{name}: added {created} label(s)")
        else:
            out.info(f"{name}: already in sync")


@app.command()
def diff(ctx: typer.Context) -> None:
    """Show label differences across repos."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client
    owner = client.organization

    repos = client.get_repos()
    all_labels: set[str] = set()
    repo_labels: dict[str, set[str]] = {}

    for repo in repos:
        name = repo["name"]
        labels = client.get(f"/repos/{owner}/{name}/labels", params={"per_page": 100})
        label_names = {label["name"] for label in labels} if isinstance(labels, list) else set()
        all_labels.update(label_names)
        repo_labels[name] = label_names

    sorted_labels = sorted(all_labels)

    if out.json_mode:
        out.raw_json({repo: sorted(names) for repo, names in repo_labels.items()})
        return

    columns: list[tuple[str, str]] = [("Label", "cyan")]
    sorted_repos = sorted(repo_labels.keys())
    columns.extend((r.removeprefix("kodemeio-")[:12], "") for r in sorted_repos)

    rows = []
    for label in sorted_labels:
        row = [label]
        for repo_name in sorted_repos:
            row.append("Y" if label in repo_labels[repo_name] else "-")
        rows.append(row)

    out.table("Label Diff", columns, rows)
