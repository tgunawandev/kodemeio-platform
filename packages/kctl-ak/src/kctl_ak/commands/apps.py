"""Application management commands."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Annotated

import typer
import yaml

from kctl_ak.core.config import resolve_app_registry_path

app = typer.Typer(help="Application management")

_MANAGED_PREFIXES = ("mac-", "tpp-", "kod-", "tkz-", "pro-", "shared-")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all applications."""
    c = ctx.obj
    apps = c.client.get_all("core/applications/")
    rows = []
    for a in apps:
        provider = a.get("provider_obj", {}) or {}
        rows.append(
            [
                a.get("slug", ""),
                a.get("name", ""),
                a.get("group", "") or "-",
                provider.get("name", "-"),
                a.get("meta_launch_url", "") or "-",
            ]
        )
    c.output.table(
        "Applications",
        [("Slug", "cyan"), ("Name", ""), ("Group", "green"), ("Provider", "dim"), ("Launch URL", "dim")],
        rows,
        data_for_json=apps,
    )


@app.command()
def get(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Application slug")],
) -> None:
    """Get application details."""
    c = ctx.obj
    a = c.client.get(f"core/applications/{slug}/")
    provider = a.get("provider_obj", {}) or {}
    c.output.detail(
        a.get("name", slug),
        [
            (
                "Application",
                [
                    ("Slug", a.get("slug", "")),
                    ("Name", a.get("name", "")),
                    ("Description", a.get("meta_description", "") or "-"),
                    ("Launch URL", a.get("meta_launch_url", "") or "-"),
                    ("Open in new tab", str(a.get("open_in_new_tab", False))),
                ],
            ),
            (
                "Provider",
                [
                    ("ID", str(a.get("provider", "-"))),
                    ("Name", provider.get("name", "-")),
                    ("Type", provider.get("verbose_name", "-")),
                ],
            ),
            (
                "Policy",
                [
                    ("Engine mode", a.get("policy_engine_mode", "-")),
                    ("Backchannel providers", str(len(a.get("backchannel_providers", [])))),
                ],
            ),
        ],
        data_for_json=a,
    )


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Application name")],
    slug: Annotated[str, typer.Argument(help="Application slug")],
    provider: Annotated[int | None, typer.Option("--provider", help="Provider ID")] = None,
    launch_url: Annotated[str | None, typer.Option("--launch-url", help="Launch URL")] = None,
    description: Annotated[str | None, typer.Option("--description", help="Description")] = None,
) -> None:
    """Create a new application."""
    c = ctx.obj
    payload: dict = {"name": name, "slug": slug}
    if provider is not None:
        payload["provider"] = provider
    if launch_url is not None:
        payload["meta_launch_url"] = launch_url
    if description is not None:
        payload["meta_description"] = description

    result = c.client.post("core/applications/", data=payload)
    c.output.success(f"Created application '{result.get('name', name)}' (slug: {result.get('slug', slug)})")


@app.command()
def update(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Application slug")],
    field: Annotated[str, typer.Argument(help="Field to update")],
    value: Annotated[str, typer.Argument(help="New value")],
) -> None:
    """Update an application field."""
    c = ctx.obj
    result = c.client.patch(f"core/applications/{slug}/", data={field: value})
    c.output.success(f"Updated '{slug}' field '{field}'")


@app.command()
def delete(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Application slug")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete an application."""
    if not force:
        typer.confirm(f"Delete application '{slug}'?", abort=True)
    c = ctx.obj
    c.client.delete(f"core/applications/{slug}/")
    c.output.success(f"Deleted application '{slug}'")


@app.command("set-icon")
def set_icon(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Application slug")],
    source: Annotated[str, typer.Argument(help="Local file path or URL")],
) -> None:
    """Set application icon from a local file or URL."""
    c = ctx.obj
    if source.startswith("http://") or source.startswith("https://"):
        c.client.patch(f"core/applications/{slug}/", data={"meta_icon": source})
        c.output.success(f"Icon set for '{slug}' from URL")
    else:
        path = Path(source)
        if not path.exists():
            c.output.error(f"File not found: {source}")
            raise typer.Exit(1)
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        with open(path, "rb") as f:
            c.client.patch_multipart(
                f"core/applications/{slug}/",
                files={"meta_icon": (path.name, f, content_type)},
            )
        c.output.success(f"Icon uploaded for '{slug}' from {path.name}")


@app.command("launch-urls")
def launch_urls(ctx: typer.Context) -> None:
    """List all applications with their launch URLs."""
    c = ctx.obj
    apps = c.client.get_all("core/applications/")
    rows = []
    for a in apps:
        rows.append(
            [
                a.get("slug", ""),
                a.get("name", ""),
                a.get("meta_launch_url", "") or "-",
            ]
        )
    c.output.table(
        "Launch URLs",
        [("Slug", "cyan"), ("Name", ""), ("Launch URL", "green")],
        rows,
        data_for_json=[
            {"slug": a["slug"], "name": a["name"], "launch_url": a.get("meta_launch_url", "")} for a in apps
        ],
    )


@app.command()
def access(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Application slug")],
) -> None:
    """Show which groups and policies can access an application."""
    c = ctx.obj
    a = c.client.get(f"core/applications/{slug}/")
    c.output.header(f"Access: {a.get('name', slug)}")
    c.output.info(f"Policy engine mode: {a.get('policy_engine_mode', 'unknown')}")

    bindings = c.client.get_all(
        "policies/bindings/",
        params={"target": a.get("pk", "")},
    )

    if not bindings:
        c.output.info("No policy bindings found (app may be open to all)")
        if c.output.json_mode:
            c.output.raw_json({"application": slug, "bindings": []})
        return

    rows = []
    for b in bindings:
        group = b.get("group_obj", {}) or {}
        user = b.get("user_obj", {}) or {}
        policy = b.get("policy_obj", {}) or {}
        target_type = "group" if group else ("user" if user else ("policy" if policy else "unknown"))
        target_name = group.get("name", "") or user.get("username", "") or policy.get("name", "") or "-"
        rows.append(
            [
                target_type,
                target_name,
                str(b.get("enabled", True)),
                str(b.get("order", 0)),
                str(b.get("negate", False)),
            ]
        )

    c.output.table(
        f"Access Bindings: {a.get('name', slug)}",
        [("Type", "cyan"), ("Target", ""), ("Enabled", ""), ("Order", "dim"), ("Negate", "dim")],
        rows,
        data_for_json=bindings,
    )


@app.command("audit")
def audit_(ctx: typer.Context) -> None:
    """Show apps with missing providers, no launch URL, or no policy bindings."""
    c = ctx.obj
    apps = c.client.get_all("core/applications/")
    issues: list[dict] = []

    for a in apps:
        problems: list[str] = []
        provider = a.get("provider_obj") or a.get("provider")
        if not provider:
            problems.append("no provider")
        launch_url = a.get("meta_launch_url", "")
        if not launch_url:
            problems.append("no launch URL")

        if problems:
            issues.append(
                {
                    "slug": a.get("slug", ""),
                    "name": a.get("name", ""),
                    "problems": problems,
                }
            )

    if not issues:
        c.output.success("All applications have providers and launch URLs")
        if c.output.json_mode:
            c.output.raw_json([])
        return

    rows = [[i["slug"], i["name"], ", ".join(i["problems"])] for i in issues]
    c.output.table(
        f"Application Audit ({len(issues)} issues)",
        [("Slug", "cyan"), ("Name", ""), ("Problems", "yellow")],
        rows,
        data_for_json=issues,
    )


@app.command()
def orphaned(ctx: typer.Context) -> None:
    """List applications that have no active provider."""
    c = ctx.obj
    apps = c.client.get_all("core/applications/")
    orphans = [a for a in apps if not a.get("provider") and not a.get("provider_obj")]

    if not orphans:
        c.output.success("No orphaned applications found")
        if c.output.json_mode:
            c.output.raw_json([])
        return

    rows = [[a.get("slug", ""), a.get("name", ""), a.get("meta_launch_url", "") or "-"] for a in orphans]
    c.output.table(
        f"Orphaned Applications ({len(orphans)})",
        [("Slug", "cyan"), ("Name", ""), ("Launch URL", "dim")],
        rows,
        data_for_json=orphans,
    )


def _compute_app_sync_plan(
    desired: list[dict],
    existing: list[dict],
) -> dict[str, list[dict]]:
    """Compare desired apps (from YAML) with existing apps (from API).

    Returns ``{"create": [...], "update": [...], "prune": [...]}``.
    This is a pure function with NO side effects.
    """
    existing_by_slug: dict[str, dict] = {a["slug"]: a for a in existing}
    desired_slugs: set[str] = set()

    create: list[dict] = []
    update: list[dict] = []

    for d in desired:
        slug = d.get("slug", "")
        if not slug:
            continue
        desired_slugs.add(slug)

        ex = existing_by_slug.get(slug)
        if ex is None:
            create.append(d)
            continue

        # Detect changes
        changes: dict = {}

        if d.get("name", "") != ex.get("name", ""):
            changes["name"] = d["name"]

        if d.get("group", "") != (ex.get("group", "") or ""):
            changes["group"] = d.get("group", "")

        if d.get("launch_url", "") != (ex.get("meta_launch_url", "") or ""):
            changes["meta_launch_url"] = d.get("launch_url", "")

        # Icon: only compare if desired icon is a URL
        desired_icon = d.get("icon", "")
        if desired_icon and (desired_icon.startswith("http://") or desired_icon.startswith("https://")):
            if desired_icon != (ex.get("meta_icon", "") or ""):
                changes["meta_icon"] = desired_icon

        if changes:
            update.append({"slug": slug, "changes": changes})

    # Prune: existing apps with managed prefixes not in desired set
    prune: list[dict] = []
    for ex in existing:
        slug = ex.get("slug", "")
        if any(slug.startswith(p) for p in _MANAGED_PREFIXES) and slug not in desired_slugs:
            prune.append({"slug": slug, "name": ex.get("name", "")})

    return {"create": create, "update": update, "prune": prune}


@app.command("sync")
def sync(
    ctx: typer.Context,
    dry_run: Annotated[bool, typer.Option("--dry-run/--no-dry-run", help="Preview changes without applying")] = True,
    prune: Annotated[bool, typer.Option("--prune", help="Delete managed apps not in YAML")] = False,
    file: Annotated[Path | None, typer.Option(help="Path to app-registry.yaml")] = None,
) -> None:
    """Sync applications from app-registry.yaml (3-phase: create/update/prune)."""
    c = ctx.obj

    if file:
        ar_path = file
    else:
        ar_path = resolve_app_registry_path()
        if ar_path is None:
            c.output.error("app-registry.yaml not found. Use --file to specify path.")
            raise typer.Exit(1)

    with open(ar_path) as f:
        registry = yaml.safe_load(f) or {}

    desired_apps = registry.get("apps", [])
    if not desired_apps:
        c.output.warn("No apps defined in registry file")
        return

    # --- Initial plan ---
    existing = c.client.get_all("core/applications/")
    plan = _compute_app_sync_plan(desired_apps, existing)

    c.output.header("App Sync")
    c.output.info(f"Source: {ar_path}")
    c.output.info(
        f"Desired: {len(desired_apps)} | "
        f"Create: {len(plan['create'])} | "
        f"Update: {len(plan['update'])} | "
        f"Prune: {len(plan['prune'])}"
    )

    # ---- Phase 1: CREATE ----
    if plan["create"]:
        c.output.header("Phase 1: Create")
        for d in plan["create"]:
            slug = d["slug"]
            if dry_run:
                c.output.info(f"[create] {slug}")
            else:
                try:
                    payload: dict = {
                        "name": d.get("name", slug),
                        "slug": slug,
                    }
                    if d.get("group"):
                        payload["group"] = d["group"]
                    if d.get("launch_url"):
                        payload["meta_launch_url"] = d["launch_url"]

                    icon = d.get("icon", "")
                    if icon and (icon.startswith("http://") or icon.startswith("https://")):
                        payload["meta_icon"] = icon

                    result = c.client.post("core/applications/", data=payload)
                    c.output.success(f"[create] {slug}")

                    # Upload local icon file after create
                    if icon and not icon.startswith("http://") and not icon.startswith("https://"):
                        icon_path = Path(icon)
                        if icon_path.exists():
                            content_type = mimetypes.guess_type(str(icon_path))[0] or "application/octet-stream"
                            with open(icon_path, "rb") as icon_f:
                                c.client.patch_multipart(
                                    f"core/applications/{slug}/",
                                    files={"meta_icon": (icon_path.name, icon_f, content_type)},
                                )
                            c.output.success(f"[create] {slug} icon uploaded")
                except Exception as e:
                    c.output.error(f"[create] Failed {slug}: {e}")

    # ---- Phase 2: UPDATE ----
    if plan["update"]:
        c.output.header("Phase 2: Update")
        for entry in plan["update"]:
            slug = entry["slug"]
            changes = entry["changes"]
            if dry_run:
                c.output.info(f"[update] {slug}: {changes}")
            else:
                try:
                    c.client.patch(f"core/applications/{slug}/", data=changes)
                    c.output.success(f"[update] {slug}")
                except Exception as e:
                    c.output.error(f"[update] Failed {slug}: {e}")

    # ---- Phase 3: PRUNE (only with --prune flag) ----
    if plan["prune"] and prune:
        c.output.header("Phase 3: Prune")
        for entry in plan["prune"]:
            slug = entry["slug"]
            if dry_run:
                c.output.info(f"[prune] {slug}")
            else:
                try:
                    c.client.delete(f"core/applications/{slug}/")
                    c.output.success(f"[prune] {slug}")
                except Exception as e:
                    c.output.error(f"[prune] Failed {slug}: {e}")
    elif plan["prune"] and not prune:
        c.output.warn(f"{len(plan['prune'])} stale managed app(s) found. Use --prune to remove them.")

    # ---- Summary ----
    actionable = plan["create"] or plan["update"] or (plan["prune"] and prune)
    if not actionable:
        if plan["prune"] and not prune:
            c.output.success("Apps in sync (stale managed apps exist — use --prune to remove)")
        else:
            c.output.success("All apps in sync")

    if dry_run and actionable:
        c.output.warn("Dry-run mode. Use --no-dry-run to apply changes.")
