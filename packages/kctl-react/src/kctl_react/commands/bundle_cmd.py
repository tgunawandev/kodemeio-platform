"""Advanced bundle analysis — budgets, duplicates, tree-shaking."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from kctl_react.core.callbacks import AppContext

app = typer.Typer(help="Advanced bundle analysis.")


def _find_assets_dir(actx: AppContext, app_name: str) -> Path | None:
    """Find the JS/CSS assets directory for an app (Vite: dist/assets, Next.js: .next/static)."""
    app_dir = actx.get_app_dir(app_name)
    if actx.is_nextjs(app_name):
        for candidate in (app_dir / ".next" / "static", app_dir / ".next"):
            if candidate.is_dir():
                return candidate
    else:
        for candidate in (app_dir / "dist" / "assets", app_dir / "dist"):
            if candidate.is_dir():
                return candidate
    return None


@app.command()
def budget(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    max_js: Annotated[int, typer.Option("--max-js", help="Max JS size in KB")] = 500,
) -> None:
    """Check bundle sizes against budgets. Exits 1 if exceeded."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    dist = _find_assets_dir(actx, app_name)
    if dist is None or not dist.exists():
        out.error(f"No build output for {app_name} — run build first")
        raise typer.Exit(1)
    js_size = sum(f.stat().st_size for f in dist.rglob("*.js"))
    js_kb = js_size / 1024
    status = "PASS" if js_kb <= max_js else "FAIL"
    if out.json_mode:
        out.raw_json({"app": app_name, "js_kb": round(js_kb, 1), "budget_kb": max_js, "status": status})
        return
    color = "green" if status == "PASS" else "red"
    out.table(
        "Bundle Budget",
        [("App", "cyan"), ("JS Size", color), ("Budget", ""), ("Status", color)],
        [[app_name, f"{js_kb:.1f} KB", f"{max_js} KB", status]],
    )
    if status == "FAIL":
        out.error(f"Bundle exceeds budget by {js_kb - max_js:.1f} KB")
        raise typer.Exit(1)


@app.command()
def duplicates(ctx: typer.Context) -> None:
    """Detect packages bundled at different versions across apps."""
    actx: AppContext = ctx.obj
    out = actx.output
    lock_file = actx.project_root / "pnpm-lock.yaml"
    if not lock_file.exists():
        out.error("No pnpm-lock.yaml found")
        raise typer.Exit(1)
    import yaml

    lock = yaml.safe_load(lock_file.read_text())
    packages = lock.get("packages", {})
    # Find packages with multiple versions
    pkg_versions: dict[str, list[str]] = {}
    for key in packages:
        # key format: /package@version or package@version
        parts = key.rsplit("@", 1)
        if len(parts) == 2:
            name, ver = parts
            name = name.lstrip("/")
            pkg_versions.setdefault(name, []).append(ver)
    dupes = {k: v for k, v in pkg_versions.items() if len(set(v)) > 1}
    if not dupes:
        out.success("No duplicate packages found")
        return
    rows = [[name, ", ".join(sorted(set(versions)))] for name, versions in sorted(dupes.items())]
    out.table(f"Duplicate Packages ({len(dupes)})", [("Package", "yellow"), ("Versions", "dim")], rows)


@app.command()
def treeshake(ctx: typer.Context, app_name: Annotated[str, typer.Argument(help="App name")]) -> None:
    """Detect imports that may prevent tree-shaking."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    import re

    src = actx.get_app_dir(app_name) / "src"
    issues: list[dict] = []
    for f in src.rglob("*.tsx"):
        content = f.read_text(errors="ignore")
        rel = str(f.relative_to(actx.project_root))
        for i, line in enumerate(content.splitlines(), 1):
            if re.search(r"import\s+\*\s+as", line):
                issues.append({"file": rel, "line": i, "type": "import *", "code": line.strip()[:80]})
    for f in src.rglob("*.ts"):
        content = f.read_text(errors="ignore")
        rel = str(f.relative_to(actx.project_root))
        if f.name == "index.ts" and "export *" in content:
            issues.append({"file": rel, "line": 0, "type": "barrel re-export", "code": "export * from ..."})
    if not issues:
        out.success("No tree-shaking issues found")
        return
    rows = [[i["file"], str(i["line"]), i["type"]] for i in issues]
    out.table("Tree-Shaking Issues", [("File", "yellow"), ("Line", "dim"), ("Issue", "red")], rows)


@app.command()
def compare(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
) -> None:
    """Compare current build against saved snapshot."""
    import json

    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)

    snapshot_file = actx.project_root / ".kctl-react" / "bundle-snapshot.json"
    if not snapshot_file.exists():
        out.error("No snapshot found — run 'kctl-react bundle analyze --save' first")
        raise typer.Exit(1) from None

    try:
        snapshot: dict = json.loads(snapshot_file.read_text())
    except Exception:
        out.error("Could not read snapshot file")
        raise typer.Exit(1) from None

    app_snap = snapshot.get(app_name)
    if app_snap is None:
        out.error(f"No snapshot entry for '{app_name}'")
        raise typer.Exit(1) from None

    dist = _find_assets_dir(actx, app_name)
    if dist is None or not dist.exists():
        out.error(f"No build output for {app_name} — run build first")
        raise typer.Exit(1) from None

    js_current = sum(f.stat().st_size for f in dist.rglob("*.js"))
    css_current = sum(f.stat().st_size for f in dist.rglob("*.css"))

    js_snap = app_snap.get("js", 0)
    css_snap = app_snap.get("css", 0)

    def _delta_str(current: int, baseline: int) -> str:
        diff_kb = (current - baseline) / 1024
        if diff_kb > 0:
            return f"[red]+{diff_kb:.1f} KB[/red]"
        elif diff_kb < 0:
            return f"[green]{diff_kb:.1f} KB[/green]"
        return "[dim]0.0 KB[/dim]"

    rows = [
        [
            app_name,
            f"{js_current / 1024:.1f} KB",
            _delta_str(js_current, js_snap),
            f"{css_current / 1024:.1f} KB",
            _delta_str(css_current, css_snap),
        ]
    ]
    out.table(
        "Bundle Comparison vs Snapshot",
        [("App", "cyan"), ("JS", ""), ("JS Delta", ""), ("CSS", ""), ("CSS Delta", "")],
        rows,
    )


@app.command()
def impact(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    top: Annotated[int, typer.Option("--top", help="Show top N chunks")] = 15,
) -> None:
    """Show which chunks contribute most to bundle size."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)

    dist = _find_assets_dir(actx, app_name)
    if dist is None or not dist.exists():
        out.error(f"No build output for {app_name} — run build first")
        raise typer.Exit(1) from None

    files = sorted((f for f in dist.rglob("*") if f.is_file()), key=lambda f: f.stat().st_size, reverse=True)
    total = sum(f.stat().st_size for f in files)

    if total == 0:
        out.info("No assets found")
        return

    rows = []
    cumulative = 0
    for f in files[:top]:
        size = f.stat().st_size
        cumulative += size
        pct = size / total * 100
        cum_pct = cumulative / total * 100
        rows.append([f.name, f"{size / 1024:.1f} KB", f"{pct:.1f}%", f"{cum_pct:.1f}%"])

    out.table(
        f"Bundle Impact — {app_name} (top {min(top, len(files))} of {len(files)} files)",
        [("File", "cyan"), ("Size", ""), ("% of Total", ""), ("Cumulative %", "dim")],
        rows,
    )
