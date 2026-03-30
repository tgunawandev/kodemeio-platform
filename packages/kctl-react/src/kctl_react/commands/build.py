"""Build commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from kctl_react.core.callbacks import AppContext
from kctl_react.core.runner import run_turbo

app = typer.Typer(help="Production builds and bundle analysis.")


def _find_build_dir(app_dir: Path) -> Path | None:
    """Find the build output directory (Vite: dist/, Next.js: .next/)."""
    for name in ("dist", ".next"):
        d = app_dir / name
        if d.is_dir():
            return d
    return None


def _get_dist_size(dist_dir: Path) -> int:
    """Get total size of a build output directory in bytes."""
    if not dist_dir.is_dir():
        return 0
    total = 0
    for f in dist_dir.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total


def _format_size(size_bytes: int) -> str:
    """Format bytes as human-readable string."""
    if size_bytes == 0:
        return "[dim]--[/dim]"
    size: float = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


_SUBCOMMANDS = {"size", "compare", "history", "chunks", "bundle"}


@app.callback(invoke_without_command=True)
def build(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (omit for all apps)")] = None,
    analyze: Annotated[bool, typer.Option("--analyze", "-a", help="Show bundle size analysis after build.")] = False,
) -> None:
    """Build app(s) for production.

    Examples:
      kctl-react build sfa          # Build SFA only
      kctl-react build              # Build all apps
      kctl-react build sfa --analyze  # Build + show bundle sizes
    """
    if ctx.invoked_subcommand is not None:
        return
    if app_name and app_name in _SUBCOMMANDS:
        return

    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    if app_name:
        actx.validate_app(app_name)

    target = app_name or "all apps"
    out.info(f"Building {target}...")

    try:
        run_turbo("build", root, filter_app=app_name, capture=False, timeout=600)
        out.success(f"Build complete: {target}")
    except Exception as e:
        out.error(f"Build failed: {e}")
        raise typer.Exit(1) from None

    if analyze:
        _show_sizes(actx, app_name)
        # Save snapshot for history tracking
        from kctl_react.core.history import save_snapshot

        snapshot = _collect_sizes(root, app_name, actx.app_names)
        save_snapshot(root, snapshot)


@app.command()
def size(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (omit for all apps)")] = None,
) -> None:
    """Show bundle sizes for built app(s)."""
    actx: AppContext = ctx.obj
    if app_name:
        actx.validate_app(app_name)
    _show_sizes(actx, app_name)


def _show_sizes(actx: AppContext, app_name: str | None) -> None:
    """Display bundle size analysis."""
    out = actx.output
    root = actx.project_root

    apps_to_check = [app_name] if app_name else actx.app_names
    rows: list[list[str]] = []
    json_data: list[dict] = []

    for name in apps_to_check:
        build_dir = _find_build_dir(root / "apps" / name)
        has_build = build_dir is not None
        total_size = _get_dist_size(build_dir) if build_dir else 0

        # Count JS/CSS files
        js_count = len(list(build_dir.rglob("*.js"))) if has_build else 0
        css_count = len(list(build_dir.rglob("*.css"))) if has_build else 0

        # Get JS/CSS total size
        js_size = sum(f.stat().st_size for f in build_dir.rglob("*.js")) if has_build else 0
        css_size = sum(f.stat().st_size for f in build_dir.rglob("*.css")) if has_build else 0

        rows.append(
            [
                name,
                _format_size(total_size),
                f"{_format_size(js_size)} ({js_count} files)",
                f"{_format_size(css_size)} ({css_count} files)",
            ]
        )
        json_data.append(
            {
                "app": name,
                "total_bytes": total_size,
                "js_bytes": js_size,
                "js_files": js_count,
                "css_bytes": css_size,
                "css_files": css_count,
                "built": has_build,
            }
        )

    out.table(
        "Bundle Sizes",
        [("App", "cyan"), ("Total", "green"), ("JS", ""), ("CSS", "")],
        rows,
        data_for_json=json_data,
    )


def _collect_sizes(root: Path, app_name: str | None, app_names: list[str]) -> dict:
    """Collect size data for history snapshot."""
    apps_to_check = [app_name] if app_name else app_names
    apps_data: dict[str, int] = {}
    for name in apps_to_check:
        build_dir = _find_build_dir(root / "apps" / name)
        apps_data[name] = _get_dist_size(build_dir) if build_dir else 0
    return {"apps": apps_data}


@app.command()
def compare(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (omit for all)")] = None,
) -> None:
    """Compare current bundle sizes against last recorded snapshot.

    Run `kctl-react build --analyze` first to save a snapshot.
    """
    from kctl_react.core.history import get_latest_snapshot

    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    if app_name:
        actx.validate_app(app_name)

    prev = get_latest_snapshot(root)
    if not prev:
        out.warn("No previous snapshot. Run `kctl-react build --analyze` first.")
        return

    prev_apps = prev.get("apps", {})
    apps_to_check = [app_name] if app_name else actx.app_names

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for name in apps_to_check:
        build_dir = _find_build_dir(root / "apps" / name)
        current = _get_dist_size(build_dir) if build_dir else 0
        previous = prev_apps.get(name, 0)
        diff = current - previous

        if diff > 0:
            diff_str = f"[red]+{_format_size(diff)}[/red]"
        elif diff < 0:
            diff_str = f"[green]{_format_size(abs(diff))}[/green]"
        else:
            diff_str = "[dim]no change[/dim]"

        rows.append([name, _format_size(previous), _format_size(current), diff_str])
        json_data.append({"app": name, "previous": previous, "current": current, "diff": diff})

    out.table(
        f"Size Comparison (vs {prev.get('timestamp', 'unknown')[:10]})",
        [("App", "cyan"), ("Previous", ""), ("Current", "green"), ("Diff", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def history(ctx: typer.Context) -> None:
    """Show build size history over time."""
    from kctl_react.core.history import load_history

    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    records = load_history(root)
    if not records:
        out.warn("No build history. Run `kctl-react build --analyze` to start tracking.")
        return

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for record in records[-10:]:  # Last 10
        ts = record.get("timestamp", "")[:19].replace("T", " ")
        apps_data = record.get("apps", {})
        total = sum(apps_data.values())
        app_count = sum(1 for v in apps_data.values() if v > 0)
        rows.append([ts, _format_size(total), f"{app_count} apps"])
        json_data.append({"timestamp": record.get("timestamp"), "total_bytes": total, "apps_built": app_count})

    out.table(
        "Build Size History",
        [("Timestamp", "dim"), ("Total Size", "green"), ("Apps", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def chunks(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
) -> None:
    """Show chunk breakdown for a built app."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    build_dir = _find_build_dir(root / "apps" / app_name)

    if not build_dir:
        out.warn(f"{app_name}: not built (run `kctl-react build {app_name}` first)")
        return

    dist_dir = build_dir  # For relative_to below

    # Find JS/CSS chunks — Vite: assets/, Next.js: static/chunks/
    assets_dir = build_dir / "assets"
    if not assets_dir.is_dir():
        assets_dir = build_dir / "static"  # Next.js
    if not assets_dir.is_dir():
        assets_dir = build_dir  # Fallback to build root

    js_files = sorted(assets_dir.rglob("*.js"), key=lambda f: f.stat().st_size, reverse=True)
    css_files = sorted(assets_dir.rglob("*.css"), key=lambda f: f.stat().st_size, reverse=True)

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for f in js_files:
        size = f.stat().st_size
        name = f.relative_to(dist_dir)
        rows.append([str(name), "JS", _format_size(size)])
        json_data.append({"file": str(name), "type": "js", "bytes": size})

    for f in css_files:
        size = f.stat().st_size
        name = f.relative_to(dist_dir)
        rows.append([str(name), "CSS", _format_size(size)])
        json_data.append({"file": str(name), "type": "css", "bytes": size})

    total = sum(d["bytes"] for d in json_data)
    rows.append(["[bold]Total[/bold]", "", f"[bold]{_format_size(total)}[/bold]"])

    out.table(
        f"Chunks: {app_name}",
        [("File", ""), ("Type", "cyan"), ("Size", "green")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def bundle(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    top: Annotated[int, typer.Option("--top", "-n", help="Show top N largest files")] = 20,
) -> None:
    """Show treemap-style bundle composition for a built app."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    build_dir = _find_build_dir(root / "apps" / app_name)

    if not build_dir:
        out.warn(f"{app_name}: not built — run `kctl-react build {app_name}` first")
        return

    total = _get_dist_size(build_dir)
    if total == 0:
        out.warn(f"{app_name}: build output is empty")
        return

    files: list[tuple[str, int, str]] = []
    for f in build_dir.rglob("*"):
        if not f.is_file():
            continue
        size = f.stat().st_size
        rel = str(f.relative_to(build_dir))
        ext = f.suffix.lstrip(".")
        files.append((rel, size, ext))

    files.sort(key=lambda x: -x[1])

    by_ext: dict[str, int] = {}
    for _, size, ext in files:
        by_ext[ext] = by_ext.get(ext, 0) + size

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for rel, size, ext in files[:top]:
        pct = (size / total * 100) if total else 0
        bar_len = int(pct / 2)
        bar = "[green]" + "█" * bar_len + "[/green]" + "░" * (50 - bar_len)
        rows.append([rel, ext.upper() or "?", _format_size(size), f"{pct:.1f}%", bar])
        json_data.append({"file": rel, "type": ext, "bytes": size, "percent": round(pct, 1)})

    out.table(
        f"Bundle Treemap — {app_name} ({_format_size(total)} total)",
        [("File", ""), ("Type", "cyan"), ("Size", "green"), ("%", ""), ("Distribution", "dim")],
        rows,
        data_for_json=json_data,
    )

    ext_rows: list[list[str]] = []
    ext_json: list[dict] = []
    for ext, size in sorted(by_ext.items(), key=lambda x: -x[1]):
        pct = (size / total * 100) if total else 0
        ext_rows.append([ext.upper() or "other", _format_size(size), f"{pct:.1f}%"])
        ext_json.append({"type": ext or "other", "bytes": size, "percent": round(pct, 1)})

    out.table(
        "By File Type",
        [("Type", "cyan"), ("Size", "green"), ("%", "")],
        ext_rows,
        data_for_json=ext_json,
    )
