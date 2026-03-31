"""Performance profiling commands."""

from __future__ import annotations

import json
from datetime import UTC
from pathlib import Path
from typing import Annotated

import typer

from kctl_react.core.callbacks import AppContext
from kctl_react.core.discovery import get_app_dir
from kctl_react.core.exceptions import CommandError
from kctl_react.core.runner import run

app = typer.Typer(help="Performance profiling and bundle analysis.")

# Default Lighthouse performance budget
_DEFAULT_BUDGET: dict[str, int] = {
    "performance": 80,
    "accessibility": 90,
    "best-practices": 80,
    "seo": 80,
}

_LIGHTHOUSE_HISTORY_FILE = "lighthouse.json"


def _lighthouse_history_path(root: Path) -> Path:
    return root / ".kctl-react" / _LIGHTHOUSE_HISTORY_FILE


def _load_lighthouse_history(root: Path) -> list[dict]:
    path = _lighthouse_history_path(root)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception:
        return []


def _save_lighthouse_result(root: Path, result: dict) -> None:
    from datetime import datetime

    history = _load_lighthouse_history(root)
    result["timestamp"] = datetime.now(UTC).isoformat()
    history.append(result)
    if len(history) > 50:
        history = history[-50:]

    path = _lighthouse_history_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=2))


@app.command()
def lighthouse(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    budget: Annotated[str | None, typer.Option("--budget", help="JSON budget file")] = None,
    url: Annotated[str | None, typer.Option("--url", help="Override URL")] = None,
) -> None:
    """Run Lighthouse CI and compare against performance budget."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_info = actx.apps[app_name]
    target_url = url or f"http://localhost:{app_info['port']}"

    # Load budget
    thresholds = dict(_DEFAULT_BUDGET)
    if budget:
        budget_path = Path(budget)
        if budget_path.exists():
            try:
                thresholds.update(json.loads(budget_path.read_text()))
            except Exception as e:
                out.warn(f"Cannot parse budget file: {e} — using defaults")
        else:
            out.warn(f"Budget file not found: {budget} — using defaults")

    out.info(f"Running Lighthouse on {target_url}...")

    # Run lighthouse via npx
    try:
        result = run(
            [
                "npx",
                "--yes",
                "lighthouse",
                target_url,
                "--output=json",
                "--chrome-flags=--headless --no-sandbox",
                "--quiet",
            ],
            cwd=root,
            capture=True,
            timeout=120,
        )
        lh_data = json.loads(result.stdout)
    except CommandError as e:
        out.error(f"Lighthouse failed: {e}")
        raise typer.Exit(1) from None
    except json.JSONDecodeError:
        out.error("Failed to parse Lighthouse output")
        raise typer.Exit(1) from None

    # Extract scores
    categories = lh_data.get("categories", {})
    scores: dict[str, int] = {}
    for key in ("performance", "accessibility", "best-practices", "seo"):
        cat = categories.get(key, {})
        scores[key] = int((cat.get("score", 0) or 0) * 100)

    # Compare against budget
    rows: list[list[str]] = []
    json_data: list[dict] = []
    all_pass = True

    for category, score in scores.items():
        threshold = thresholds.get(category, 0)
        passed = score >= threshold
        if not passed:
            all_pass = False
        status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
        rows.append([category, str(score), str(threshold), status])
        json_data.append({"category": category, "score": score, "threshold": threshold, "passed": passed})

    out.table(
        f"Lighthouse — {app_name} ({target_url})",
        [("Category", "cyan"), ("Score", "green"), ("Budget", "dim"), ("Status", "")],
        rows,
        data_for_json=json_data,
    )

    # Save to history
    _save_lighthouse_result(root, {"app": app_name, "url": target_url, "scores": scores})

    if all_pass:
        out.success("All categories meet budget thresholds")
    else:
        out.warn("Some categories below budget — see FAIL items above")
        raise typer.Exit(1)


@app.command("history")
def perf_history(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of records to show")] = 10,
) -> None:
    """Show Lighthouse score and build size trends over time."""
    from kctl_react.commands.build import _format_size
    from kctl_react.core.history import load_history as load_build_history

    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)

    # Lighthouse history
    lh_records = [r for r in _load_lighthouse_history(root) if r.get("app") == app_name]

    if lh_records:
        rows: list[list[str]] = []
        json_data: list[dict] = []

        for record in lh_records[-limit:]:
            ts = record.get("timestamp", "")[:19].replace("T", " ")
            scores = record.get("scores", {})
            perf = str(scores.get("performance", "-"))
            a11y = str(scores.get("accessibility", "-"))
            bp = str(scores.get("best-practices", "-"))
            seo = str(scores.get("seo", "-"))
            rows.append([ts, perf, a11y, bp, seo])
            json_data.append({"timestamp": record.get("timestamp"), "scores": scores})

        out.table(
            f"Lighthouse History — {app_name}",
            [("Timestamp", "dim"), ("Perf", "green"), ("A11y", "cyan"), ("Best Prac", ""), ("SEO", "")],
            rows,
            data_for_json=json_data,
        )
    else:
        out.info(f"No Lighthouse history for {app_name}. Run `kctl-react perf lighthouse {app_name}` first.")

    # Build size history
    build_records = load_build_history(root)
    if build_records:
        rows = []
        json_data = []
        for record in build_records[-limit:]:
            ts = record.get("timestamp", "")[:19].replace("T", " ")
            apps_data = record.get("apps", {})
            app_size = apps_data.get(app_name, 0)
            if app_size > 0:
                rows.append([ts, _format_size(app_size)])
                json_data.append({"timestamp": record.get("timestamp"), "bytes": app_size})

        if rows:
            out.table(
                f"Build Size History — {app_name}",
                [("Timestamp", "dim"), ("Size", "green")],
                rows,
                data_for_json=json_data,
            )
        else:
            out.info(f"No build size data for {app_name}.")
    else:
        out.info("No build history. Run `kctl-react build --analyze` to start tracking.")


def _check_pwa_readiness(app_dir: Path) -> dict:
    """Check PWA readiness for a single app directory."""
    result: dict[str, bool] = {
        "manifest": False,
        "service_worker": False,
        "pwa_plugin": False,
        "icons": False,
        "offline": False,
    }

    # Manifest check: public/ or dist/
    for manifest_name in ("manifest.webmanifest", "manifest.json"):
        if (app_dir / "public" / manifest_name).exists() or (app_dir / "dist" / manifest_name).exists():
            result["manifest"] = True
            break

    # Service worker check
    for sw_name in ("sw.js", "service-worker.js", "sw.ts"):
        for search_dir in (app_dir / "dist", app_dir / "src", app_dir / "public"):
            if search_dir.is_dir() and (search_dir / sw_name).exists():
                result["service_worker"] = True
                break
        if result["service_worker"]:
            break
    # Also check dist for generated SW files
    dist = app_dir / "dist"
    if dist.is_dir():
        for _f in dist.rglob("sw*.js"):
            result["service_worker"] = True
            break

    # PWA plugin check (Vite: vite-plugin-pwa, Next.js: next-pwa or @ducanh2912/next-pwa)
    vite_config = app_dir / "vite.config.ts"
    if not vite_config.exists():
        vite_config = app_dir / "vite.config.js"
    if vite_config.exists():
        try:
            content = vite_config.read_text()
            if "VitePWA" in content or "@vite-pwa" in content or "vite-plugin-pwa" in content:
                result["pwa_plugin"] = True
                result["service_worker"] = True
        except Exception:
            pass
    # Next.js PWA check
    for next_config_name in ("next.config.ts", "next.config.js", "next.config.mjs"):
        next_config = app_dir / next_config_name
        if next_config.exists():
            try:
                content = next_config.read_text()
                if "next-pwa" in content or "withPWA" in content:
                    result["pwa_plugin"] = True
                    result["service_worker"] = True
            except Exception:
                pass
            break

    # Icons check
    icons_dir = app_dir / "public" / "icons"
    if icons_dir.is_dir() and any(icons_dir.iterdir()):
        result["icons"] = True
    else:
        # Check manifest for icons array
        for manifest_name in ("manifest.webmanifest", "manifest.json"):
            manifest_path = app_dir / "public" / manifest_name
            if manifest_path.exists():
                try:
                    import json as _json

                    manifest = _json.loads(manifest_path.read_text())
                    if manifest.get("icons"):
                        result["icons"] = True
                except Exception:
                    pass
                break

    # Offline fallback
    if (app_dir / "public" / "offline.html").exists():
        result["offline"] = True
    elif result["pwa_plugin"]:
        # vite-plugin-pwa with registerType: "prompt" handles offline via SW
        result["offline"] = True

    return result


@app.command()
def pwa(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (omit for all)")] = None,
) -> None:
    """Check PWA readiness for each app."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    if app_name:
        actx.validate_app(app_name)
        apps_to_check = [app_name]
    else:
        apps_to_check = actx.app_names

    out.info("Checking PWA readiness...")

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for name in apps_to_check:
        app_dir = get_app_dir(root, name)
        checks = _check_pwa_readiness(app_dir)

        def _icon(val: bool) -> str:
            return "[green]yes[/green]" if val else "[red]no[/red]"

        score = sum(checks.values())
        total = len(checks)
        status = f"[green]{score}/{total}[/green]" if score == total else f"[yellow]{score}/{total}[/yellow]"

        rows.append(
            [
                name,
                _icon(checks["manifest"]),
                _icon(checks["service_worker"]),
                _icon(checks["pwa_plugin"]),
                _icon(checks["icons"]),
                _icon(checks["offline"]),
                status,
            ]
        )
        json_data.append({"app": name, **checks, "score": score, "total": total})

    out.table(
        "PWA Readiness",
        [
            ("App", "cyan"),
            ("Manifest", ""),
            ("SW", ""),
            ("Plugin", ""),
            ("Icons", ""),
            ("Offline", ""),
            ("Score", ""),
        ],
        rows,
        data_for_json=json_data,
    )


@app.command("bundle")
def bundle(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    budget_kb: Annotated[
        int | None, typer.Option("--budget", help="Warn when total JS exceeds this KB threshold")
    ] = None,
) -> None:
    """Report bundle size breakdown for a built app (reads dist/assets/)."""
    from kctl_react.commands.build import _format_size

    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)

    app_dir = get_app_dir(root, app_name)

    # Gather files from build output — Vite: dist/assets, Next.js: .next/static
    search_dir: Path | None = None
    if actx.is_nextjs(app_name):
        for candidate in (app_dir / ".next" / "static", app_dir / ".next"):
            if candidate.is_dir():
                search_dir = candidate
                break
    else:
        for candidate in (app_dir / "dist" / "assets", app_dir / "dist"):
            if candidate.is_dir():
                search_dir = candidate
                break

    if search_dir is None:
        out.info(f"{app_name} has not been built yet")
        if out.json_mode:
            out.raw_json([])
        return

    # Collect files
    rows: list[list[str]] = []
    json_data: list[dict] = []
    total_js = 0
    total_css = 0

    for f in sorted(search_dir.rglob("*")):
        if not f.is_file():
            continue
        size = f.stat().st_size
        ext = f.suffix.lower()
        file_type = "JS" if ext in (".js", ".mjs") else "CSS" if ext == ".css" else ext.lstrip(".").upper() or "other"
        if ext in (".js", ".mjs"):
            total_js += size
        elif ext == ".css":
            total_css += size

        rel = f.relative_to(search_dir)
        rows.append([str(rel), file_type, _format_size(size)])
        json_data.append({"file": str(rel), "type": file_type, "bytes": size})

    if not rows:
        out.info(f"{app_name}: dist/assets is empty")
        if out.json_mode:
            out.raw_json([])
        return

    out.table(
        f"Bundle Size — {app_name}",
        [("File", "cyan"), ("Type", "dim"), ("Size", "green")],
        rows,
        data_for_json=json_data,
    )

    summary = f"JS: {_format_size(total_js)}  CSS: {_format_size(total_css)}"
    if budget_kb and total_js > budget_kb * 1024:
        out.warn(f"Total JS ({_format_size(total_js)}) exceeds budget ({budget_kb} KB) — {summary}")
    else:
        out.success(f"Bundle sizes: {summary}")


@app.command()
def vitals(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
) -> None:
    """Check Core Web Vitals readiness (code splitting, lazy images, SVGs, scripts)."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_dir = get_app_dir(root, app_name)
    src_dir = app_dir / "src"

    checks: list[tuple[str, bool, str]] = []

    # 1. React.lazy / lazy() usage (route code splitting)
    has_lazy = False
    if src_dir.is_dir():
        for tsx_file in src_dir.rglob("*.tsx"):
            try:
                content = tsx_file.read_text()
                if "React.lazy(" in content or "lazy(" in content:
                    has_lazy = True
                    break
            except Exception:
                pass
    checks.append(
        (
            "Route code splitting (React.lazy)",
            has_lazy,
            "lazy() found in src" if has_lazy else "No React.lazy() usage detected",
        )
    )

    # 2. Large inline SVGs (>5KB) in .tsx files
    large_svgs: list[str] = []
    if src_dir.is_dir():
        for tsx_file in src_dir.rglob("*.tsx"):
            try:
                content = tsx_file.read_text()
                # Count bytes of inline SVG blocks
                import re

                for match in re.finditer(r"<svg[\s>].*?</svg>", content, re.DOTALL):
                    if len(match.group().encode()) > 5120:
                        large_svgs.append(tsx_file.name)
                        break
            except Exception:
                pass
    has_no_large_svgs = len(large_svgs) == 0
    detail = "No large inline SVGs" if has_no_large_svgs else f"Large inline SVGs in: {', '.join(large_svgs[:3])}"
    checks.append(("No large inline SVGs (>5KB)", has_no_large_svgs, detail))

    # 3. Images have loading="lazy"
    imgs_without_lazy: list[str] = []
    if src_dir.is_dir():
        for tsx_file in src_dir.rglob("*.tsx"):
            try:
                content = tsx_file.read_text()
                import re

                for match in re.finditer(r"<img\b[^>]*>", content, re.DOTALL):
                    tag = match.group()
                    if "loading=" not in tag:
                        imgs_without_lazy.append(tsx_file.name)
                        break
            except Exception:
                pass
    has_lazy_images = len(imgs_without_lazy) == 0
    detail = (
        "All <img> tags have loading attribute"
        if has_lazy_images
        else f"Missing loading= in: {', '.join(imgs_without_lazy[:3])}"
    )
    checks.append(('Images use loading="lazy"', has_lazy_images, detail))

    # 4. No synchronous external scripts (no async/defer) — Vite SPAs only
    sync_scripts: list[str] = []
    index_html = app_dir / "index.html"
    if index_html.exists() and not actx.is_nextjs(app_name):
        try:
            import re

            html = index_html.read_text()
            for match in re.finditer(r'<script\b[^>]*src=["\'][^"\']*["\'][^>]*>', html):
                tag = match.group()
                if (
                    "async" not in tag
                    and "defer" not in tag
                    and 'type="module"' not in tag
                    and "type='module'" not in tag
                ):
                    sync_scripts.append(tag[:60])
        except Exception:
            pass
    has_no_sync_scripts = len(sync_scripts) == 0
    detail = (
        "No synchronous external scripts"
        if has_no_sync_scripts
        else f"{len(sync_scripts)} sync script(s) without async/defer"
    )
    checks.append(("External scripts use async/defer", has_no_sync_scripts, detail))

    rows: list[list[str]] = []
    json_data: list[dict] = []
    for check_name, ok, detail_text in checks:
        status = "[green]OK[/green]" if ok else "[yellow]WARN[/yellow]"
        rows.append([check_name, status, detail_text])
        json_data.append({"check": check_name, "status": "OK" if ok else "WARN", "detail": detail_text})

    out.table(
        f"Core Web Vitals Readiness — {app_name}",
        [("Check", "cyan"), ("Status", ""), ("Detail", "dim")],
        rows,
        data_for_json=json_data,
    )

    warnings = sum(1 for _, ok, _ in checks if not ok)
    if warnings == 0:
        out.success("All vitals checks passed")
    else:
        out.warn(f"{warnings} check(s) need attention")


@app.command()
def images(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    max_size: Annotated[int, typer.Option("--max-size", help="PNG/JPG size threshold in KB for WebP suggestion")] = 200,
) -> None:
    """Audit image assets in public/ and src/assets/ directories."""
    from kctl_react.commands.build import _format_size

    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_dir = get_app_dir(root, app_name)

    image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".svg", ".ico"}
    search_dirs = [app_dir / "public", app_dir / "src" / "assets"]

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for search_dir in search_dirs:
        if not search_dir.is_dir():
            continue
        for img_file in sorted(search_dir.rglob("*")):
            if not img_file.is_file():
                continue
            ext = img_file.suffix.lower()
            if ext not in image_extensions:
                continue

            size = img_file.stat().st_size
            fmt = ext.lstrip(".").upper()
            suggestion = ""

            if ext in (".png", ".jpg", ".jpeg") and size > max_size * 1024:
                suggestion = f"Convert to WebP/AVIF (>{max_size}KB)"
            elif ext == ".svg" and size > 50 * 1024:
                suggestion = "Run SVGO optimization (>50KB)"

            rel = img_file.relative_to(app_dir)
            rows.append([str(rel), fmt, _format_size(size), suggestion or "—"])
            json_data.append({"file": str(rel), "format": fmt, "bytes": size, "suggestion": suggestion})

    if not rows:
        out.info(f"{app_name}: No image files found in public/ or src/assets/")
        if out.json_mode:
            out.raw_json([])
        return

    out.table(
        f"Image Assets — {app_name}",
        [("File", "cyan"), ("Format", "dim"), ("Size", "green"), ("Suggestion", "yellow")],
        rows,
        data_for_json=json_data,
    )

    suggestions = sum(1 for r in rows if r[3] != "—")
    if suggestions == 0:
        out.success("All images look good")
    else:
        out.warn(f"{suggestions} image(s) have optimization suggestions")


@app.command()
def fonts(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
) -> None:
    """Check font loading strategy (preload, self-hosted, font-display, woff2)."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_dir = get_app_dir(root, app_name)

    checks: list[tuple[str, bool, str]] = []

    # 1. Font preload in index.html (Vite) or layout.tsx (Next.js)
    has_font_preload = False
    index_html = app_dir / "index.html"
    if actx.is_nextjs(app_name):
        # Next.js uses next/font — check for font imports in layout files
        for layout_file in app_dir.rglob("layout.tsx"):
            try:
                content = layout_file.read_text()
                if "next/font" in content or "@next/font" in content:
                    has_font_preload = True
                    break
            except Exception:
                pass
    elif index_html.exists():
        try:
            html = index_html.read_text()
            if 'rel="preload"' in html and "font" in html:
                has_font_preload = True
        except Exception:
            pass
    preload_detail = (
        "next/font import found in layout"
        if actx.is_nextjs(app_name) and has_font_preload
        else 'rel="preload" + font found'
        if has_font_preload
        else "No font preload/next-font found"
    )
    checks.append(("Font preload", has_font_preload, preload_detail))

    # 2. No Google Fonts CDN (suggest self-hosting)
    uses_google_fonts = False
    css_dirs = [app_dir / "src", app_dir / "public"]
    google_fonts_files: list[str] = []
    if index_html.exists():
        try:
            html = index_html.read_text()
            if "fonts.googleapis.com" in html or "fonts.gstatic.com" in html:
                uses_google_fonts = True
                google_fonts_files.append("index.html")
        except Exception:
            pass
    for css_dir in css_dirs:
        if css_dir.is_dir():
            for css_file in css_dir.rglob("*.css"):
                try:
                    content = css_file.read_text()
                    if "fonts.googleapis.com" in content or "fonts.gstatic.com" in content:
                        uses_google_fonts = True
                        google_fonts_files.append(css_file.name)
                except Exception:
                    pass
    no_google_fonts = not uses_google_fonts
    detail = (
        "No Google Fonts CDN usage"
        if no_google_fonts
        else f"Google Fonts CDN in: {', '.join(google_fonts_files[:3])} — consider self-hosting"
    )
    checks.append(("No Google Fonts CDN (self-host instead)", no_google_fonts, detail))

    # 3. font-display: swap in CSS
    has_font_display_swap = False
    for css_dir in css_dirs:
        if css_dir.is_dir():
            for css_file in css_dir.rglob("*.css"):
                try:
                    content = css_file.read_text()
                    if "font-display" in content and "swap" in content:
                        has_font_display_swap = True
                        break
                except Exception:
                    pass
        if has_font_display_swap:
            break
    checks.append(
        (
            "font-display: swap in CSS",
            has_font_display_swap,
            "font-display: swap found" if has_font_display_swap else "No font-display: swap declaration found",
        )
    )

    # 4. Self-hosted .woff2 font files
    has_woff2 = False
    woff2_dirs = [app_dir / "public", app_dir / "src" / "assets", app_dir / "src" / "fonts"]
    for woff2_dir in woff2_dirs:
        if woff2_dir.is_dir() and any(woff2_dir.rglob("*.woff2")):
            has_woff2 = True
            break
    checks.append(
        (
            "Self-hosted .woff2 fonts",
            has_woff2,
            "woff2 font files found" if has_woff2 else "No .woff2 files in public/ or src/",
        )
    )

    rows: list[list[str]] = []
    json_data: list[dict] = []
    for check_name, ok, detail_text in checks:
        status = "[green]OK[/green]" if ok else "[yellow]WARN[/yellow]"
        rows.append([check_name, status, detail_text])
        json_data.append({"check": check_name, "status": "OK" if ok else "WARN", "detail": detail_text})

    out.table(
        f"Font Loading Strategy — {app_name}",
        [("Check", "cyan"), ("Status", ""), ("Detail", "dim")],
        rows,
        data_for_json=json_data,
    )

    warnings = sum(1 for _, ok, _ in checks if not ok)
    if warnings == 0:
        out.success("Font loading strategy is well optimized")
    else:
        out.warn(f"{warnings} font check(s) need attention")
