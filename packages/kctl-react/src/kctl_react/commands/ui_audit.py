"""UI component audit — detect shadcn violations."""

from __future__ import annotations

import contextlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Annotated

import typer

from kctl_react.core.analyzers import find_raw_html_elements, scan_imports
from kctl_react.core.callbacks import AppContext
from kctl_react.core.exceptions import CommandError
from kctl_react.core.runner import run

app = typer.Typer(help="UI component audit and shadcn compliance.")

# React anti-patterns to detect
_ANTI_PATTERNS: list[tuple[str, str, str]] = [
    # (pattern, name, fix)
    (r"style=\{\{", "inline style", "Use Tailwind utility classes instead"),
    (r'from\s+["\'][^"\']+\.module\.css["\']', "CSS module import", "Use Tailwind v4 utility classes"),
    (r'from\s+["\']styled-components["\']', "styled-components import", "Use Tailwind v4 utility classes"),
    (r"document\.getElementById\(", "direct DOM access", "Use React refs (useRef) instead"),
    (
        r'from\s+["\'][^"\']*tailwind\.config["\']',
        "tailwind.config import",
        "Use CSS @theme in index.css (Tailwind v4)",
    ),
]


def _scan_anti_patterns(src_dir: Path) -> list[dict]:
    """Scan all TSX/TS files in src_dir for React anti-patterns."""
    results: list[dict] = []
    for f in src_dir.rglob("*.ts"):
        _check_file_anti_patterns(f, results, src_dir)
    for f in src_dir.rglob("*.tsx"):
        _check_file_anti_patterns(f, results, src_dir)
    return results


def _check_file_anti_patterns(file_path: Path, results: list[dict], base_dir: Path) -> None:
    try:
        lines = file_path.read_text(errors="ignore").splitlines()
    except OSError:
        return
    rel = str(file_path.relative_to(base_dir.parent.parent))
    for line_num, line in enumerate(lines, start=1):
        for pattern, name, fix in _ANTI_PATTERNS:
            if re.search(pattern, line):
                results.append(
                    {
                        "file": rel,
                        "line": line_num,
                        "pattern": name,
                        "fix": fix,
                        "code": line.strip()[:80],
                    }
                )


@app.command()
def audit(ctx: typer.Context, app_name: Annotated[str, typer.Argument(help="App name")]) -> None:
    """Find raw HTML elements that should be shadcn components."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    src_dir = actx.get_app_dir(app_name) / "src"
    violations: list[dict] = []
    for f in src_dir.rglob("*.tsx"):
        for v in find_raw_html_elements(f):
            # Normalise file path to be relative to project root
            v = dict(v)
            with contextlib.suppress(ValueError):
                v["file"] = str(Path(str(v["file"])).relative_to(actx.project_root))
            violations.append(v)
    if not violations:
        out.success("No shadcn violations found")
        return
    rows = [
        [v["file"], str(v["line"]), v["element"], f"Use <{v['replacement'].split('+')[0].strip()}>"]
        for v in violations[:50]
    ]
    out.table(
        f"UI Violations ({len(violations)} found)",
        [("File", "red"), ("Line", "dim"), ("Element", "yellow"), ("Fix", "green")],
        rows,
        data_for_json=violations[:50],
    )
    if len(violations) > 50:
        out.warn(f"Showing 50/{len(violations)} — use --json for full list")


@app.command()
def compliance(ctx: typer.Context, app_name: Annotated[str, typer.Argument(help="App name")]) -> None:
    """Score shadcn compliance as % of clean TSX files (no violations)."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    src_dir = actx.get_app_dir(app_name) / "src"

    total_files = 0
    clean_files = 0
    total_violations = 0
    violation_by_file: dict[str, int] = {}

    for f in src_dir.rglob("*.tsx"):
        total_files += 1
        file_violations = find_raw_html_elements(f)
        count = len(file_violations)
        total_violations += count
        if count == 0:
            clean_files += 1
        else:
            rel = str(f.relative_to(actx.project_root))
            violation_by_file[rel] = count

    if total_files == 0:
        out.warn("No TSX files found")
        return

    score = round(clean_files / total_files * 100, 1)
    status = "✓ PASS" if score >= 80 else "✗ FAIL"

    rows = [
        [
            app_name,
            f"{score}%",
            str(total_files),
            str(clean_files),
            str(total_violations),
            status,
        ]
    ]
    json_data = [
        {
            "app": app_name,
            "score_pct": score,
            "total_files": total_files,
            "clean_files": clean_files,
            "violation_count": total_violations,
            "status": status,
        }
    ]
    out.table(
        f"shadcn Compliance — {app_name}",
        [
            ("App", "cyan"),
            ("Score", "green" if score >= 80 else "red"),
            ("Total Files", ""),
            ("Clean Files", ""),
            ("Violations", "yellow"),
            ("Status", ""),
        ],
        rows,
        data_for_json=json_data,
    )

    if violation_by_file:
        top = sorted(violation_by_file.items(), key=lambda x: -x[1])[:10]
        detail_rows = [[f, str(c)] for f, c in top]
        out.table(
            "Top Violating Files",
            [("File", "red"), ("Violations", "yellow")],
            detail_rows,
            data_for_json=[{"file": f, "violations": c} for f, c in top],
        )


@app.command("anti-patterns")
def anti_patterns(ctx: typer.Context, app_name: Annotated[str, typer.Argument(help="App name")]) -> None:
    """Detect React anti-patterns: inline styles, CSS modules, styled-components, direct DOM access."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    src_dir = actx.get_app_dir(app_name) / "src"
    issues = _scan_anti_patterns(src_dir)
    if not issues:
        out.success("No React anti-patterns detected")
        return
    rows = [[v["file"], str(v["line"]), v["pattern"], v["fix"]] for v in issues[:50]]
    out.table(
        f"React Anti-Patterns ({len(issues)} found)",
        [("File", "red"), ("Line", "dim"), ("Pattern", "yellow"), ("Fix", "green")],
        rows,
        data_for_json=issues[:50],
    )
    if len(issues) > 50:
        out.warn(f"Showing 50/{len(issues)} — use --json for full list")


@app.command()
def components(ctx: typer.Context, app_name: Annotated[str, typer.Argument(help="App name")]) -> None:
    """List shadcn components used by the app."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    src_dir = actx.get_app_dir(app_name) / "src"
    imports: dict[str, int] = {}
    for f in src_dir.rglob("*.tsx"):
        for name in scan_imports(f, "@kodemeio/ui"):
            imports[name] = imports.get(name, 0) + 1
    if not imports:
        out.warn("No @kodemeio/ui imports found")
        return
    rows = [[comp, str(count)] for comp, count in sorted(imports.items(), key=lambda x: -x[1])]
    out.table(
        f"shadcn Components — {app_name}",
        [("Component", "cyan"), ("Imports", "")],
        rows,
        data_for_json=[{"component": c, "imports": n} for c, n in sorted(imports.items(), key=lambda x: -x[1])],
    )


@app.command("theme-check")
def theme_check(ctx: typer.Context, app_name: Annotated[str, typer.Argument(help="App name")]) -> None:
    """Validate theme CSS variable references and Tailwind v4 patterns."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    theme_file = actx.project_root / "packages" / "tailwind-config" / "themes" / f"{app_name}.css"
    if not theme_file.exists():
        out.error(f"No theme file: {theme_file}")
        raise typer.Exit(1)
    theme_content = theme_file.read_text()
    defined_vars = set(re.findall(r"--([a-z0-9-]+)\s*:", theme_content))
    # Check source for var(--xxx) references
    src_dir = actx.get_app_dir(app_name) / "src"
    used_vars: set[str] = set()
    for f in src_dir.rglob("*.tsx"):
        content = f.read_text(errors="ignore")
        used_vars.update(re.findall(r"var\(--([a-z0-9-]+)\)", content))
    missing = used_vars - defined_vars
    if missing:
        out.warn(f"{len(missing)} CSS variable(s) used but not defined in theme:")
        for v in sorted(missing):
            out.text(f"  --{v}")
    else:
        out.success("All CSS variables properly defined")

    # Tailwind v4 pattern checks
    issues: list[str] = []
    index_css = src_dir / "index.css"
    if index_css.exists():
        css_content = index_css.read_text()
        if '@import "tailwindcss"' not in css_content and "@import 'tailwindcss'" not in css_content:
            issues.append("index.css missing '@import \"tailwindcss\"' (Tailwind v4 pattern)")
    else:
        issues.append("src/index.css not found")

    vite_cfg = actx.get_app_dir(app_name) / "vite.config.ts"
    if vite_cfg.exists():
        vite_content = vite_cfg.read_text()
        if "@tailwindcss/vite" not in vite_content:
            issues.append("vite.config.ts missing '@tailwindcss/vite' plugin (Tailwind v4 pattern)")
    else:
        issues.append("vite.config.ts not found")

    if issues:
        out.warn(f"{len(issues)} Tailwind v4 issue(s):")
        for issue in issues:
            out.text(f"  • {issue}")
    else:
        out.success("Tailwind v4 patterns verified")


# ── shadcn CLI wrapper commands ──────────────────────────────────────

# Known custom components (not from the shadcn registry)
_CUSTOM_COMPONENTS = frozenset(
    {
        "data-table",
        "file-upload",
        "image-gallery",
        "signature-pad",
        "timeline",
        "tour-overlay",
    }
)


@app.command()
def add(
    ctx: typer.Context,
    component: Annotated[str | None, typer.Argument(help="Component name (e.g. button, card)")] = None,
    all_components: Annotated[bool, typer.Option("--all", "-a", help="Install all components")] = False,
    overwrite: Annotated[bool, typer.Option("--overwrite", "-o", help="Overwrite existing")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview changes")] = False,
) -> None:
    """Install a shadcn component into @kodemeio/ui."""
    actx: AppContext = ctx.obj
    out = actx.output
    if not component and not all_components:
        out.error("Specify a component name or use --all")
        raise typer.Exit(1)
    cmd = ["npx", "shadcn@latest", "add"]
    if component:
        cmd.append(component)
    if all_components:
        cmd.append("-a")
    cmd.extend(["-c", "packages/ui", "-y"])
    if overwrite:
        cmd.append("-o")
    if dry_run:
        cmd.append("--dry-run")
    try:
        run(cmd, cwd=actx.project_root, capture=False)
    except CommandError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc


@app.command("diff")
def diff_cmd(
    ctx: typer.Context,
    component: Annotated[str, typer.Argument(help="Component name")],
) -> None:
    """Show diff for a shadcn component update."""
    actx: AppContext = ctx.obj
    out = actx.output
    cmd = ["npx", "shadcn@latest", "add", component, "--diff", "-c", "packages/ui"]
    try:
        run(cmd, cwd=actx.project_root, capture=False)
    except CommandError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc


@app.command()
def search(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Search query")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 20,
) -> None:
    """Search the shadcn component registry."""
    actx: AppContext = ctx.obj
    out = actx.output
    cmd = ["npx", "shadcn@latest", "search", "@shadcn", "-q", query, "-l", str(limit)]
    try:
        run(cmd, cwd=actx.project_root, capture=False)
    except CommandError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc


@app.command()
def docs(
    ctx: typer.Context,
    component: Annotated[str, typer.Argument(help="Component name")],
) -> None:
    """Get shadcn component documentation and API reference."""
    actx: AppContext = ctx.obj
    out = actx.output
    cmd = ["npx", "shadcn@latest", "docs", component, "-c", "packages/ui"]
    try:
        run(cmd, cwd=actx.project_root, capture=False)
    except CommandError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc


_VALID_APPS = frozenset({"sfa", "lfa", "shop", "wms", "bia", "eam", "mrp", "hrm", "tpm", "dms", "saas"})


def _extract_css_blocks(css: str) -> dict[str, str]:
    """Extract structured CSS blocks from shadcn-generated index.css.

    Returns a dict with keys: ":root", ".dark", "@theme", "@layer".
    Values are the inner content of each block (without the braces).
    """
    blocks: dict[str, str] = {}

    # Extract @theme inline { ... }
    m = re.search(r"@theme\s+inline\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}", css, re.DOTALL)
    if m:
        blocks["@theme"] = m.group(1).strip()

    # Extract top-level :root { ... } (not inside @layer)
    # Find :root blocks that are NOT preceded by @layer
    for m in re.finditer(r"(?<!\w):root\s*\{([^}]*)\}", css, re.DOTALL):
        # Check it's not inside @layer by looking at the preceding text
        before = css[: m.start()]
        # Count open/close braces to see if we're inside something
        open_braces = before.count("{") - before.count("}")
        if open_braces == 0:
            blocks[":root"] = m.group(1).strip()
            break

    # Extract top-level .dark { ... }
    for m in re.finditer(r"\.dark\s*\{([^}]*)\}", css, re.DOTALL):
        before = css[: m.start()]
        open_braces = before.count("{") - before.count("}")
        if open_braces == 0:
            blocks[".dark"] = m.group(1).strip()
            break

    # Extract @layer base { ... } — may contain nested braces
    m = re.search(r"@layer\s+base\s*\{(.*)\}", css, re.DOTALL)
    if m:
        # Greedy match gets the outermost @layer base block; trim to balanced braces
        content = m.group(1)
        # Find the balanced closing brace
        depth = 0
        end = len(content)
        for i, ch in enumerate(content):
            if ch == "{":
                depth += 1
            elif ch == "}":
                if depth == 0:
                    end = i
                    break
                depth -= 1
        blocks["@layer"] = content[:end].strip()

    return blocks


def _indent_block(content: str) -> str:
    """Ensure consistent 4-space indentation for all lines in a CSS block."""
    lines = content.splitlines()
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            result.append(f"    {stripped}")
        else:
            result.append("")
    return "\n".join(result)


# CSS variables that shadcn presets don't include but our apps need.
_CUSTOM_THEME_INLINE_VARS = """    --color-destructive-foreground: var(--destructive-foreground);
    --color-success: var(--success);
    --color-success-foreground: var(--success-foreground);
    --color-warning: var(--warning);
    --color-warning-foreground: var(--warning-foreground);"""


def _ensure_custom_theme_vars(theme_block: str) -> str:
    """Append our custom color mappings if the preset didn't include them."""
    for var in ("--color-destructive-foreground", "--color-success", "--color-warning"):
        if var not in theme_block:
            theme_block = theme_block.rstrip() + "\n" + _CUSTOM_THEME_INLINE_VARS
            break
    return theme_block


def _build_updated_globals(
    old_globals: str,
    new_blocks: dict[str, str],
    *,
    colors_in_target: bool = False,
) -> str:
    """Rebuild globals.css replacing @theme inline and @layer base blocks.

    When *colors_in_target* is True (--target APP), :root/.dark color tokens
    are NOT written into globals.css — they go to the theme file instead.
    globals.css stays structural-only.
    """
    lines = old_globals.splitlines(keepends=True)
    result_parts: list[str] = []
    i = 0

    # Phase 1: Collect imports and pre-@theme content
    while i < len(lines):
        line = lines[i]
        if re.match(r"\s*@theme\s+inline\s*\{", line):
            break
        if re.match(r"(?<!\w):root\s*\{", line.strip()):
            break
        result_parts.append(line)
        i += 1

    # Phase 2: Write new structural blocks
    if "@theme" in new_blocks:
        themed = _indent_block(new_blocks["@theme"])
        themed = _ensure_custom_theme_vars(themed)
        result_parts.append("@theme inline {\n")
        result_parts.append(themed + "\n")
        result_parts.append("}\n")
        result_parts.append("\n")

    # Only write :root/.dark into globals when colors are NOT going to a target theme file
    if not colors_in_target:
        if ":root" in new_blocks:
            result_parts.append(":root {\n")
            result_parts.append(_indent_block(new_blocks[":root"]) + "\n")
            result_parts.append("}\n")
            result_parts.append("\n")

        if ".dark" in new_blocks:
            result_parts.append(".dark {\n")
            result_parts.append(_indent_block(new_blocks[".dark"]) + "\n")
            result_parts.append("}\n")
            result_parts.append("\n")

    if "@layer" in new_blocks:
        result_parts.append("@layer base {\n")
        result_parts.append(_indent_block(new_blocks["@layer"]) + "\n")
        result_parts.append("}\n")

    # Phase 3: Skip over old managed blocks in original, collect custom content
    custom_lines: list[str] = []
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Always skip these managed block types
        skip_patterns = [
            r"\s*@theme\s+inline\s*\{",
            r":root\s*\{",
            r"\.dark\s*\{",
            r"@layer\s+base\s*\{",
        ]
        skipped = False
        for pattern in skip_patterns:
            if re.match(pattern, stripped):
                depth = 1
                i += 1
                while i < len(lines) and depth > 0:
                    for ch in lines[i]:
                        if ch == "{":
                            depth += 1
                        elif ch == "}":
                            depth -= 1
                    i += 1
                skipped = True
                break
        if skipped:
            continue

        # Skip @custom-variant (managed by preset)
        if stripped.startswith("@custom-variant"):
            i += 1
            continue

        # Everything else is custom content — keep it
        custom_lines.append(lines[i])
        i += 1

    # Phase 4: Append custom content (strip leading blank lines)
    while custom_lines and custom_lines[0].strip() == "":
        custom_lines.pop(0)
    if custom_lines:
        result_parts.append("\n")
        result_parts.extend(custom_lines)

    return "".join(result_parts)


def _build_theme_css(root_content: str, dark_content: str, *, with_globals_import: bool = False) -> str:
    """Build a theme CSS file with :root and .dark blocks.

    When *with_globals_import* is True, adds ``@import "../globals.css"`` at top
    so the theme file can be the single import in an app's index.css.
    """
    parts: list[str] = []
    if with_globals_import:
        parts.append('@import "../globals.css";\n\n')
    parts.extend(
        [
            ":root {\n",
            _indent_block(root_content) + "\n",
            "}\n",
            "\n",
            ".dark {\n",
            _indent_block(dark_content) + "\n",
            "}\n",
        ]
    )
    return "".join(parts)


@app.command()
def preset(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Preset ID from ui.shadcn.com/themes (e.g. bIkeymG)")],
    reinstall: Annotated[
        bool, typer.Option("--reinstall", help="Re-install existing components with new style")
    ] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would change without writing")] = False,
    target: Annotated[
        str,
        typer.Option("--target", "-t", help="Target: 'base' for base-neutral.css or APP_NAME for theme file"),
    ] = "base",
) -> None:
    """Apply a shadcn theme preset — extract CSS vars into the monorepo theme system.

    Creates a temp Vite project, runs shadcn init --preset, extracts the
    generated CSS variables and @theme inline block, then updates:

    \b
    - globals.css — @theme inline, :root, .dark, @layer base
    - base-neutral.css (or themes/{app}.css) — :root and .dark color vars

    Get preset IDs from https://ui.shadcn.com/themes — click a theme,
    copy the preset code from the URL or init command.

    Examples:
      kctl-react ui preset b1D0dv72                     # Apply to base-neutral.css
      kctl-react ui preset b1D0dv72 --target sfa        # Apply to themes/sfa.css
      kctl-react ui preset b1D0dv72 --dry-run           # Preview changes
      kctl-react ui preset b1D0dv72 --reinstall         # Apply + reinstall components
    """
    actx: AppContext = ctx.obj
    out = actx.output

    # Validate target
    if target != "base" and target not in _VALID_APPS:
        out.error(f"Invalid target '{target}'. Use 'base' or an app name: {', '.join(sorted(_VALID_APPS))}")
        raise typer.Exit(1)

    tc_src = actx.project_root / "packages" / "tailwind-config" / "src"
    globals_path = tc_src / "globals.css"
    target_path = tc_src / "base-neutral.css" if target == "base" else tc_src / "themes" / f"{target}.css"

    ui_components_json = actx.project_root / "packages" / "ui" / "components.json"

    # Step 1: Create temp directory with minimal Vite scaffolding
    tmp_dir = tempfile.mkdtemp(prefix="kctl-preset-")
    try:
        out.info(f"Creating temp Vite project in {tmp_dir}...")

        # package.json
        pkg = {
            "name": "preset-tmp",
            "private": True,
            "dependencies": {
                "vite": "*",
                "react": "*",
                "react-dom": "*",
                "tailwindcss": "*",
                "@tailwindcss/vite": "*",
            },
        }
        Path(tmp_dir, "package.json").write_text(json.dumps(pkg, indent=2))

        # vite.config.js
        Path(tmp_dir, "vite.config.js").write_text(
            'import { defineConfig } from "vite"\n'
            'import tailwindcss from "@tailwindcss/vite"\n'
            "export default defineConfig({ plugins: [tailwindcss()] })\n"
        )

        # tsconfig.json
        Path(tmp_dir, "tsconfig.json").write_text(
            json.dumps(
                {
                    "compilerOptions": {
                        "baseUrl": ".",
                        "paths": {"@/*": ["./src/*"]},
                    }
                },
                indent=2,
            )
        )

        # components.json — copy from packages/ui
        if ui_components_json.exists():
            shutil.copy2(ui_components_json, Path(tmp_dir, "components.json"))
        else:
            Path(tmp_dir, "components.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://ui.shadcn.com/schema.json",
                        "style": "new-york",
                        "rsc": False,
                        "tsx": True,
                        "aliases": {"components": "src/components", "utils": "src/lib/utils"},
                    },
                    indent=2,
                )
            )

        # src/index.css
        src_dir = Path(tmp_dir, "src")
        src_dir.mkdir()
        (src_dir / "index.css").write_text('@import "tailwindcss";\n')

        # Step 2: Install deps and run preset
        out.info("Installing temp dependencies (npm)...")
        try:
            run(["npm", "install", "--silent"], cwd=Path(tmp_dir), capture=True, timeout=120)
        except CommandError as exc:
            out.error(f"npm install failed: {exc}")
            raise typer.Exit(1) from exc

        out.info(f"Running shadcn init --preset {name}...")
        try:
            run(
                ["npx", "shadcn@latest", "init", "--preset", name, "--force", "--no-reinstall", "-y"],
                cwd=Path(tmp_dir),
                capture=True,
                timeout=120,
            )
        except CommandError as exc:
            out.error(f"shadcn init --preset failed: {exc}")
            raise typer.Exit(1) from exc

        # Step 3: Extract CSS from generated index.css
        generated_css_path = src_dir / "index.css"
        if not generated_css_path.exists():
            out.error("shadcn did not generate src/index.css")
            raise typer.Exit(1)

        generated_css = generated_css_path.read_text()
        blocks = _extract_css_blocks(generated_css)

        if ":root" not in blocks:
            out.error("Could not extract :root block from generated CSS")
            raise typer.Exit(1)

        # Step 4: Extract style from generated components.json
        new_style: str | None = None
        generated_cj = Path(tmp_dir, "components.json")
        if generated_cj.exists():
            try:
                cj_data = json.loads(generated_cj.read_text())
                new_style = cj_data.get("style")
            except (json.JSONDecodeError, OSError):
                pass

        # ── Summary / Dry-run ───────────────────────────────────────
        out.info("Extracted CSS blocks:")
        for key in ("@theme", ":root", ".dark", "@layer"):
            if key in blocks:
                line_count = blocks[key].count("\n") + 1
                out.text(f"  {key}: {line_count} lines")

        if new_style:
            out.text(f"  style: {new_style}")

        if dry_run:
            out.info("[dry-run] Would update:")
            if globals_path.exists():
                out.text(f"  {globals_path.relative_to(actx.project_root)}")
            out.text(f"  {target_path.relative_to(actx.project_root) if target_path.exists() else target_path.name}")
            if new_style and ui_components_json.exists():
                out.text(f"  {ui_components_json.relative_to(actx.project_root)} (style -> {new_style})")
            out.success("[dry-run] No files modified")
            return

        # ── Step 5: Update globals.css ──────────────────────────────
        changes: list[str] = []
        colors_in_target = target != "base"

        if globals_path.exists() and blocks:
            old_globals = globals_path.read_text()
            new_globals = _build_updated_globals(old_globals, blocks, colors_in_target=colors_in_target)
            globals_path.write_text(new_globals)
            changes.append(str(globals_path.relative_to(actx.project_root)))

        # ── Step 6: Update target theme file ────────────────────────
        root_content = blocks.get(":root", "")
        dark_content = blocks.get(".dark", "")
        if root_content:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            # App themes get @import "../globals.css"; base-neutral does not
            target_path.write_text(_build_theme_css(root_content, dark_content, with_globals_import=colors_in_target))
            changes.append(str(target_path.relative_to(actx.project_root)))

        # ── Step 7: Update components.json style ────────────────────
        if new_style and ui_components_json.exists():
            try:
                cj = json.loads(ui_components_json.read_text())
                old_style = cj.get("style", "")
                if old_style != new_style:
                    cj["style"] = new_style
                    ui_components_json.write_text(json.dumps(cj, indent=2) + "\n")
                    changes.append(
                        f"{ui_components_json.relative_to(actx.project_root)} (style: {old_style} -> {new_style})"
                    )
            except (json.JSONDecodeError, OSError):
                out.warn("Could not update components.json")

        for c in changes:
            out.text(f"  Updated: {c}")
        out.success(f"Preset '{name}' applied successfully")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # ── Step 8: Optional reinstall ──────────────────────────────────
    if reinstall:
        out.info("Re-installing components with new style...")
        try:
            run(
                ["npx", "shadcn@latest", "init", "--force", "--reinstall", "-c", "packages/ui"],
                cwd=actx.project_root,
                capture=False,
            )
            out.success("Components reinstalled with new style")
        except CommandError as exc:
            out.warn(f"Reinstall failed (components may need manual update): {exc}")


@app.command()
def info(ctx: typer.Context) -> None:
    """Show shadcn project configuration from packages/ui."""
    actx: AppContext = ctx.obj
    out = actx.output
    cmd = ["npx", "shadcn@latest", "info", "-c", "packages/ui"]
    try:
        run(cmd, cwd=actx.project_root, capture=False)
    except CommandError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc


@app.command()
def installed(ctx: typer.Context) -> None:
    """List all installed shadcn components in @kodemeio/ui."""
    actx: AppContext = ctx.obj
    out = actx.output
    components_dir = actx.project_root / "packages" / "ui" / "src" / "components"
    if not components_dir.exists():
        out.warn("No components directory found at packages/ui/src/components")
        return
    files = sorted(components_dir.glob("*.tsx"))
    if not files:
        out.warn("No .tsx component files found")
        return
    rows: list[list[str]] = []
    json_data: list[dict[str, str]] = []
    for f in files:
        name = f.stem
        comp_type = "custom" if name in _CUSTOM_COMPONENTS else "shadcn"
        rel_path = str(f.relative_to(actx.project_root))
        rows.append([name, comp_type, rel_path])
        json_data.append({"component": name, "type": comp_type, "path": rel_path})
    out.table(
        f"Installed Components ({len(files)})",
        [("Component", "cyan"), ("Type", "yellow"), ("Path", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def unused(ctx: typer.Context) -> None:
    """Find installed components not used by any app."""
    actx: AppContext = ctx.obj
    out = actx.output
    components_dir = actx.project_root / "packages" / "ui" / "src" / "components"
    if not components_dir.exists():
        out.warn("No components directory found at packages/ui/src/components")
        return
    comp_names = {f.stem for f in components_dir.glob("*.tsx")}
    if not comp_names:
        out.warn("No .tsx component files found")
        return
    # Scan all apps for imports from @kodemeio/ui
    usage: dict[str, set[str]] = {name: set() for name in comp_names}
    for app_name in actx.app_names:
        app_dir = actx.get_app_dir(app_name)
        src_dir = app_dir / "src"
        if not src_dir.is_dir():
            continue
            app_name = app_dir.name
            for tsx_file in src_dir.rglob("*.tsx"):
                try:
                    content = tsx_file.read_text(errors="ignore")
                except OSError:
                    continue
                for comp in comp_names:
                    # Check if the component name (PascalCase or kebab-case) appears
                    # in an import from @kodemeio/ui
                    pascal = comp.replace("-", " ").title().replace(" ", "")
                    if pascal in content or f"/{comp}" in content:
                        usage[comp].add(app_name)
    rows: list[list[str]] = []
    json_data: list[dict] = []
    for comp in sorted(comp_names):
        apps_using = usage[comp]
        status = "used" if apps_using else "unused"
        count = len(apps_using)
        rows.append([comp, status, str(count)])
        json_data.append({"component": comp, "status": status, "used_by": count})
    out.table(
        f"Component Usage ({len(comp_names)} total)",
        [("Component", "cyan"), ("Status", "green"), ("Used By", "")],
        rows,
        data_for_json=json_data,
    )
