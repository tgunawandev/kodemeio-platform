"""PWA and Service Worker management."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from kctl_react.core.callbacks import AppContext
from kctl_react.core.discovery import get_app_dir

app = typer.Typer(help="PWA and Service Worker management (Vite apps).")


def _require_vite(actx: AppContext, app_name: str) -> None:
    """Exit with a warning if the app is not a Vite PWA."""
    if actx.is_nextjs(app_name):
        actx.output.warn(
            f"{app_name} is a Next.js app. PWA commands are for Vite apps only. "
            "Use next-pwa or @ducanh2912/next-pwa directly for Next.js PWA management."
        )
        raise typer.Exit(0)


@app.command()
def status(ctx: typer.Context, app_name: Annotated[str, typer.Argument(help="App name")]) -> None:
    """Show PWA status — service worker version, precache count, manifest."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    _require_vite(actx, app_name)
    root = actx.project_root
    dist = get_app_dir(root, app_name) / "dist"
    sw = dist / "sw.js"
    manifest = dist / "manifest.webmanifest"
    data = {"app": app_name, "sw_exists": sw.exists(), "manifest_exists": manifest.exists()}
    if sw.exists():
        content = sw.read_text(errors="ignore")
        data["sw_size"] = sw.stat().st_size
        data["precache_count"] = content.count("url:")
    if manifest.exists():
        try:
            m = json.loads(manifest.read_text())
            data["name"] = m.get("name", "")
            data["start_url"] = m.get("start_url", "")
            data["display"] = m.get("display", "")
            data["icons"] = len(m.get("icons", []))
        except json.JSONDecodeError:
            data["manifest_error"] = "Invalid JSON"
    if out.json_mode:
        out.raw_json(data)
        return
    sections = [("PWA Status", [(k, str(v)) for k, v in data.items()])]
    out.detail(f"PWA — {app_name}", sections, data_for_json=data)


@app.command("cache-list")
def cache_list(ctx: typer.Context, app_name: Annotated[str, typer.Argument(help="App name")]) -> None:
    """List precached URLs from service worker manifest."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    _require_vite(actx, app_name)
    dist = actx.get_app_dir(app_name) / "dist"
    sw = dist / "sw.js"
    if not sw.exists():
        out.warn(f"No built service worker at {sw}")
        return
    content = sw.read_text(errors="ignore")
    # Parse workbox precache manifest entries
    import re

    urls = re.findall(r'"url"\s*:\s*"([^"]+)"', content)
    rows = [[url, "precache"] for url in urls]
    out.table(
        f"Cached URLs — {app_name}",
        [("URL", "cyan"), ("Strategy", "dim")],
        rows,
        data_for_json=[{"url": u, "strategy": "precache"} for u in urls],
    )


@app.command("cache-clear")
def cache_clear(ctx: typer.Context, app_name: Annotated[str, typer.Argument(help="App name")]) -> None:
    """Clear built service worker files."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    _require_vite(actx, app_name)
    dist = actx.get_app_dir(app_name) / "dist"
    cleared = 0
    for f in [dist / "sw.js", dist / "sw.js.map", dist / "workbox-*.js"]:
        if f.exists():
            f.unlink()
            cleared += 1
    # Also glob workbox files
    for f in dist.glob("workbox-*.js"):
        f.unlink()
        cleared += 1
    out.success(f"Cleared {cleared} service worker file(s)")


@app.command("manifest-validate")
def manifest_validate(ctx: typer.Context, app_name: Annotated[str, typer.Argument(help="App name")]) -> None:
    """Validate web app manifest against PWA requirements."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    dist = actx.get_app_dir(app_name) / "dist"
    manifest_file = dist / "manifest.webmanifest"
    if not manifest_file.exists():
        # Check public/ too
        manifest_file = actx.get_app_dir(app_name) / "public" / "manifest.webmanifest"
    if not manifest_file.exists():
        out.error("No manifest.webmanifest found in dist/ or public/")
        raise typer.Exit(1) from None
    m = json.loads(manifest_file.read_text())
    issues = []
    required = ["name", "short_name", "start_url", "display", "icons"]
    for key in required:
        if key not in m:
            issues.append(f"Missing required field: {key}")
    if "icons" in m:
        sizes = [icon.get("sizes", "") for icon in m["icons"]]
        if "192x192" not in sizes:
            issues.append("Missing 192x192 icon")
        if "512x512" not in sizes:
            issues.append("Missing 512x512 icon")
    if m.get("display") not in ("standalone", "fullscreen", "minimal-ui"):
        issues.append(f"display should be standalone/fullscreen/minimal-ui, got: {m.get('display')}")
    if issues:
        out.error(f"{len(issues)} issue(s) found:")
        for issue in issues:
            out.text(f"  - {issue}")
        raise typer.Exit(1)
    out.success("Manifest is valid")


@app.command("offline-report")
def offline_report(ctx: typer.Context, app_name: Annotated[str, typer.Argument(help="App name")]) -> None:
    """Analyze offline support coverage."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    _require_vite(actx, app_name)
    # Count total routes vs precached routes
    app_dir = actx.get_app_dir(app_name) / "src" / "pages"
    total_pages = len(list(app_dir.glob("**/*.tsx"))) if app_dir.exists() else 0
    dist = actx.get_app_dir(app_name) / "dist"
    sw = dist / "sw.js"
    precached = 0
    if sw.exists():
        import re

        precached = len(re.findall(r'"url"\s*:\s*"([^"]+)"', sw.read_text(errors="ignore")))
    out.table(
        "Offline Coverage",
        [("Metric", "cyan"), ("Value", "")],
        [["Total pages", str(total_pages)], ["Precached assets", str(precached)]],
        data_for_json=[
            {"metric": "total_pages", "value": total_pages},
            {"metric": "precached_assets", "value": precached},
        ],
    )


@app.command("sw-info")
def sw_info(ctx: typer.Context, app_name: Annotated[str, typer.Argument(help="App name")]) -> None:
    """Show vite-plugin-pwa configuration."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    _require_vite(actx, app_name)
    vite_config = actx.get_app_dir(app_name) / "vite.config.ts"
    if not vite_config.exists():
        out.error("No vite.config.ts found")
        raise typer.Exit(1)
    content = vite_config.read_text()
    import re

    register_type = re.search(r"registerType\s*:\s*['\"](\w+)['\"]", content)
    strategies = re.findall(r"(CacheFirst|NetworkFirst|StaleWhileRevalidate|NetworkOnly|CacheOnly)", content)
    data = {
        "register_type": register_type.group(1) if register_type else "unknown",
        "runtime_caching_strategies": list(set(strategies)),
        "has_workbox_config": "workbox" in content.lower(),
    }
    if out.json_mode:
        out.raw_json(data)
        return
    sections = [("PWA Config", [(k, str(v)) for k, v in data.items()])]
    out.detail(f"Service Worker Config — {app_name}", sections)
