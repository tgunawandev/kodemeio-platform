"""Compose autoDeploy management — quick status, toggles, and bulk disable.

Dokploy's autoDeploy field controls whether a compose service redeploys
automatically on git push. For production services we typically want this off
(manual deploys via ``kctl-dokploy deploy apply``); staging can opt-in.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="View and toggle compose auto-deploy on git push.")


def _list_composes(c: AppContext, project_filter: str | None = None) -> list[dict]:
    """Return every compose across projects, with project + environment names attached."""
    projects = c.client.get("/project.all")
    if not isinstance(projects, list):
        return []
    out: list[dict] = []
    for p in projects:
        proj_name = p.get("name", "")
        proj_id = p.get("projectId", "")
        if project_filter and project_filter not in (proj_name, proj_id):
            continue
        for comp in p.get("compose", []):
            comp = dict(comp)
            comp["_projectName"] = proj_name
            comp["_environmentName"] = ""
            out.append(comp)
        for env in p.get("environments", []):
            env_name = env.get("name", "")
            for comp in env.get("compose", []):
                comp = dict(comp)
                comp["_projectName"] = proj_name
                comp["_environmentName"] = env_name
                out.append(comp)
    return out


def _fetch_autodeploy(c: AppContext, compose_id: str) -> bool | None:
    """Fetch the current autoDeploy flag for one compose. Returns None on error."""
    try:
        detail = c.client.get("/compose.one", params={"composeId": compose_id})
    except Exception:
        return None
    if isinstance(detail, dict):
        val = detail.get("autoDeploy")
        if isinstance(val, bool):
            return val
    return None


def _set_autodeploy(c: AppContext, compose_id: str, enabled: bool) -> tuple[bool, str]:
    """Set autoDeploy on one compose and verify. Returns (ok, message)."""
    try:
        c.client.post("/compose.update", json={"composeId": compose_id, "autoDeploy": enabled})
    except Exception as e:
        return False, f"update failed: {e}"
    verified = _fetch_autodeploy(c, compose_id)
    if verified is enabled:
        return True, "verified"
    if verified is None:
        return True, "updated (could not verify)"
    return False, f"still {verified} after update"


@app.command("status")
def status_cmd(
    ctx: typer.Context,
    project: Annotated[str | None, typer.Option("--project", "-p", help="Filter by project name or ID")] = None,
    only_enabled: Annotated[
        bool, typer.Option("--only-enabled", help="Show only services with autoDeploy=true")
    ] = False,
) -> None:
    """Show autoDeploy status across every compose service.

    Fetches detail for each compose (Dokploy's list endpoint doesn't include
    ``autoDeploy``), so this is an O(N) call — fine for <100 services.
    """
    c: AppContext = ctx.obj
    services = _list_composes(c, project_filter=project)
    rows: list[list[str]] = []
    json_data: list[dict] = []
    enabled_count = 0
    for s in services:
        cid = s.get("composeId", "")
        ad = _fetch_autodeploy(c, cid)
        if only_enabled and ad is not True:
            continue
        if ad is True:
            enabled_count += 1
        label = "ENABLED" if ad is True else ("disabled" if ad is False else "unknown")
        rows.append(
            [
                cid,
                s.get("name", ""),
                s.get("_projectName", ""),
                s.get("_environmentName", "") or "-",
                label,
            ]
        )
        json_data.append(
            {
                "composeId": cid,
                "name": s.get("name", ""),
                "project": s.get("_projectName", ""),
                "environment": s.get("_environmentName", "") or None,
                "autoDeploy": ad,
            }
        )
    title = f"AutoDeploy Status ({enabled_count} enabled / {len(rows)} shown)"
    c.output.table(
        title,
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("Project", "green"),
            ("Environment", ""),
            ("Auto-Deploy", "yellow"),
        ],
        rows,
        data_for_json=json_data,
    )


@app.command("enable")
def enable_cmd(
    ctx: typer.Context,
    compose_ids: Annotated[list[str], typer.Argument(help="One or more compose service IDs")],
) -> None:
    """Enable autoDeploy on one or more compose services (space-separated IDs)."""
    c: AppContext = ctx.obj
    ok_count = 0
    for cid in compose_ids:
        ok, msg = _set_autodeploy(c, cid, True)
        if ok:
            c.output.success(f"{cid}: autoDeploy=true ({msg})")
            ok_count += 1
        else:
            c.output.error(f"{cid}: {msg}")
    c.output.info(f"{ok_count}/{len(compose_ids)} updated")
    if ok_count < len(compose_ids):
        raise typer.Exit(1)


@app.command("disable")
def disable_cmd(
    ctx: typer.Context,
    compose_ids: Annotated[list[str], typer.Argument(help="One or more compose service IDs")],
) -> None:
    """Disable autoDeploy on one or more compose services (space-separated IDs)."""
    c: AppContext = ctx.obj
    ok_count = 0
    for cid in compose_ids:
        ok, msg = _set_autodeploy(c, cid, False)
        if ok:
            c.output.success(f"{cid}: autoDeploy=false ({msg})")
            ok_count += 1
        else:
            c.output.error(f"{cid}: {msg}")
    c.output.info(f"{ok_count}/{len(compose_ids)} updated")
    if ok_count < len(compose_ids):
        raise typer.Exit(1)


@app.command("disable-all")
def disable_all_cmd(
    ctx: typer.Context,
    project: Annotated[
        str | None,
        typer.Option("--project", "-p", help="Limit to a single project (name or ID)"),
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would change without applying")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Disable autoDeploy on every compose where it is currently true."""
    c: AppContext = ctx.obj
    services = _list_composes(c, project_filter=project)
    to_fix: list[tuple[str, str, str]] = []
    for s in services:
        cid = s.get("composeId", "")
        ad = _fetch_autodeploy(c, cid)
        if ad is True:
            to_fix.append((cid, s.get("name", ""), s.get("_projectName", "")))
    if not to_fix:
        c.output.success("No compose services have autoDeploy=true. Nothing to do.")
        return
    c.output.info(f"Found {len(to_fix)} service(s) with autoDeploy=true:")
    for cid, name, proj in to_fix:
        c.output.info(f"  - {proj or '-'} / {name}  ({cid})")
    if dry_run:
        c.output.warn("--dry-run set, no changes applied.")
        return
    if not force and not typer.confirm("Disable autoDeploy on all of the above?"):
        c.output.warn("Aborted.")
        raise typer.Exit(1)
    ok = 0
    for cid, name, _ in to_fix:
        set_ok, msg = _set_autodeploy(c, cid, False)
        if set_ok:
            c.output.success(f"  {name}: disabled ({msg})")
            ok += 1
        else:
            c.output.error(f"  {name}: {msg}")
    c.output.info(f"Disabled {ok}/{len(to_fix)}")
    if ok < len(to_fix):
        raise typer.Exit(1)
