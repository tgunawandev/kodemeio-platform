"""Addon analysis and audit commands."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Annotated

import typer

from kctl_odoo.core.addons import (
    Addon,
    discover_addons,
    get_addon_path_labels,
    get_default_addon_paths,
    score_health,
)
from kctl_odoo.core.bundles import (
    discover_bundles,
    discover_profiles,
    get_default_install_dir,
    load_profile,
    resolve_modules,
    resolve_profile_modules,
)
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.snapshots import load_snapshot

app = typer.Typer(help="Addon analysis, health scoring, and bundle coverage audits.")


# ============================================================================
# Helpers
# ============================================================================


def _resolve_addon_paths(addon_paths_str: str | None) -> list[Path]:
    """Parse comma-separated addon paths or return defaults."""
    if addon_paths_str:
        return [Path(p.strip()) for p in addon_paths_str.split(",") if p.strip()]
    return get_default_addon_paths()


def _resolve_install_dir(dir_path: str | None) -> Path:
    """Resolve the install directory from flag or default."""
    p = Path(dir_path) if dir_path else get_default_install_dir()
    if not p.is_dir():
        typer.echo(
            f"Install directory not found: {p}\nRun from the kodemeio-odoo repo, or set KCTL_ODOO_REPO=/path/to/repo",
            err=True,
        )
        raise typer.Exit(1)
    return p


def _all_bundle_modules(install_dir: Path) -> set[str]:
    """Collect all module names across all bundles."""
    bundles = discover_bundles(install_dir)
    all_mods: set[str] = set()
    for b in bundles:
        mods = resolve_modules(b, ["all"])
        all_mods.update(mods)
    return all_mods


def _find_profile_file(install_dir: Path, name: str) -> Path | None:
    """Find a profile YAML file by name."""
    for prefix in ("profile-", ""):
        for ext in (".yaml", ".yml"):
            path = install_dir / f"{prefix}{name}{ext}"
            if path.exists():
                return path
    return None


def _discover_with_labels(addon_paths_str: str | None) -> list[Addon]:
    """Discover addons with proper source-type labels."""
    paths = _resolve_addon_paths(addon_paths_str)
    labels = get_addon_path_labels()
    return discover_addons(paths, path_labels=labels)


# ============================================================================
# Local commands (no Odoo connection)
# ============================================================================


@app.command("scan")
def scan(
    ctx: typer.Context,
    addon_paths: Annotated[str | None, typer.Option("--addon-paths", help="Comma-separated addon paths")] = None,
) -> None:
    """List all addons discovered on disk."""
    actx: AppContext = ctx.obj
    out = actx.output

    addons = _discover_with_labels(addon_paths)
    if not addons:
        out.info("No addons found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for a in addons:
        rows.append(
            [
                a.name,
                a.source_type,
                a.version or "-",
                "[green]yes[/green]" if a.installable else "[red]no[/red]",
                (a.summary or "-")[:60],
            ]
        )
        json_data.append(
            {
                "name": a.name,
                "source_type": a.source_type,
                "version": a.version,
                "installable": a.installable,
                "summary": a.summary,
            }
        )

    out.table(
        f"Addons ({len(addons)})",
        [
            ("Name", "cyan"),
            ("Source", ""),
            ("Version", "dim"),
            ("Installable", ""),
            ("Summary", "dim"),
        ],
        rows,
        json_data,
    )


@app.command("orphans")
def orphans(
    ctx: typer.Context,
    addon_paths: Annotated[str | None, typer.Option("--addon-paths", help="Comma-separated addon paths")] = None,
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
) -> None:
    """Find addons on disk not referenced in any bundle."""
    actx: AppContext = ctx.obj
    out = actx.output
    install_dir = _resolve_install_dir(dir_path)

    addons = _discover_with_labels(addon_paths)
    bundle_mods = _all_bundle_modules(install_dir)
    orphan_addons = [a for a in addons if a.name not in bundle_mods]

    if not orphan_addons:
        out.success("All addons are referenced in at least one bundle.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for a in orphan_addons:
        rows.append([a.name, a.source_type, a.version or "-"])
        json_data.append(
            {
                "name": a.name,
                "source_type": a.source_type,
                "version": a.version,
            }
        )

    out.table(
        f"Orphan Addons ({len(orphan_addons)})",
        [("Name", "cyan"), ("Source", ""), ("Version", "dim")],
        rows,
        json_data,
    )


@app.command("missing")
def missing(
    ctx: typer.Context,
    addon_paths: Annotated[str | None, typer.Option("--addon-paths", help="Comma-separated addon paths")] = None,
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
) -> None:
    """Find modules in bundles that are not on disk."""
    actx: AppContext = ctx.obj
    out = actx.output
    install_dir = _resolve_install_dir(dir_path)

    addons = _discover_with_labels(addon_paths)
    disk_names = {a.name for a in addons}
    bundle_mods = _all_bundle_modules(install_dir)
    missing_mods = sorted(bundle_mods - disk_names)

    if not missing_mods:
        out.success("All bundle modules are present on disk.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = [[m] for m in missing_mods]
    json_data = [{"name": m} for m in missing_mods]

    out.table(
        f"Missing Addons ({len(missing_mods)})",
        [("Module", "cyan")],
        rows,
        json_data,
    )


@app.command("duplicates")
def duplicates(
    ctx: typer.Context,
    addon_paths: Annotated[str | None, typer.Option("--addon-paths", help="Comma-separated addon paths")] = None,
) -> None:
    """Find addon names that appear in multiple source directories."""
    actx: AppContext = ctx.obj
    out = actx.output

    addons = _discover_with_labels(addon_paths)
    by_name: dict[str, list[Addon]] = defaultdict(list)
    for a in addons:
        by_name[a.name].append(a)

    dups = {name: items for name, items in by_name.items() if len(items) > 1}

    if not dups:
        out.success("No duplicate addon names found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for name in sorted(dups):
        paths = [str(a.path) for a in dups[name]]
        sources = [a.source_type for a in dups[name]]
        rows.append([name, str(len(dups[name])), ", ".join(sources)])
        json_data.append(
            {
                "name": name,
                "count": len(dups[name]),
                "sources": sources,
                "paths": paths,
            }
        )

    out.table(
        f"Duplicate Addons ({len(dups)})",
        [("Name", "cyan"), ("Count", ""), ("Sources", "dim")],
        rows,
        json_data,
    )


@app.command("health")
def health(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Addon name to check")],
    addon_paths: Annotated[str | None, typer.Option("--addon-paths", help="Comma-separated addon paths")] = None,
) -> None:
    """Show health score for a single addon."""
    actx: AppContext = ctx.obj
    out = actx.output

    addons = _discover_with_labels(addon_paths)
    match = [a for a in addons if a.name == name]
    if not match:
        out.error(f"Addon not found: {name}")
        raise typer.Exit(1)

    addon = match[0]
    result = score_health(addon)

    check_pairs = []
    for check_name, passed in result.checks.items():
        status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
        check_pairs.append((check_name, status))

    sections = [
        (
            "Addon",
            [
                ("Name", addon.name),
                ("Source", addon.source_type),
                ("Version", addon.version or "-"),
                ("Score", f"{result.score}/100"),
            ],
        ),
        ("Checks", check_pairs),
    ]
    if result.issues:
        sections.append(("Issues", [(issue, "") for issue in result.issues]))

    json_obj = {
        "name": addon.name,
        "source_type": addon.source_type,
        "version": addon.version,
        "score": result.score,
        "checks": result.checks,
        "issues": result.issues,
    }

    out.detail(f"Health: {addon.name} ({result.score}/100)", sections, json_obj)


@app.command("health-summary")
def health_summary(
    ctx: typer.Context,
    source: Annotated[
        str, typer.Option("--source", "-s", help="Filter by source type (private/oca/external/all)")
    ] = "private",
    addon_paths: Annotated[str | None, typer.Option("--addon-paths", help="Comma-separated addon paths")] = None,
) -> None:
    """Aggregate health scores across addons, sorted worst-first."""
    actx: AppContext = ctx.obj
    out = actx.output

    addons = _discover_with_labels(addon_paths)
    if source != "all":
        addons = [a for a in addons if a.source_type == source]

    if not addons:
        out.info(f"No addons found for source type: {source}")
        if actx.json_mode:
            out.raw_json([])
        return

    scored = []
    for a in addons:
        result = score_health(a)
        scored.append((a, result))

    # Sort by score ascending (worst first)
    scored.sort(key=lambda x: x[1].score)

    rows = []
    json_data = []
    total_score = 0
    for a, result in scored:
        total_score += result.score
        issue_count = len(result.issues)
        rows.append(
            [
                a.name,
                str(result.score),
                str(issue_count),
                a.source_type,
            ]
        )
        json_data.append(
            {
                "name": a.name,
                "score": result.score,
                "issues": issue_count,
                "source_type": a.source_type,
            }
        )

    avg_score = total_score // len(scored) if scored else 0
    out.table(
        f"Health Summary ({len(scored)} addons, avg: {avg_score}/100)",
        [
            ("Name", "cyan"),
            ("Score", "green"),
            ("Issues", ""),
            ("Source", "dim"),
        ],
        rows,
        json_data,
    )


@app.command("matrix")
def matrix(
    ctx: typer.Context,
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
    addon_paths: Annotated[str | None, typer.Option("--addon-paths", help="Comma-separated addon paths")] = None,
    source: Annotated[
        str, typer.Option("--source", "-s", help="Filter by source type (private/oca/external/all)")
    ] = "all",
) -> None:
    """Show addon x profile matrix."""
    actx: AppContext = ctx.obj
    out = actx.output
    install_dir = _resolve_install_dir(dir_path)

    addons = _discover_with_labels(addon_paths)
    if source != "all":
        addons = [a for a in addons if a.source_type == source]

    # Discover profiles, exclude AI profiles that use extends
    profiles = [p for p in discover_profiles(install_dir) if not p.extends]

    if not addons or not profiles:
        out.info("No addons or profiles found.")
        return

    # Resolve modules for each profile
    profile_modules: dict[str, set[str]] = {}
    for p in profiles:
        mods = resolve_profile_modules(p, install_dir)
        profile_modules[p.name] = set(mods)

    rows = []
    json_data = []
    for a in sorted(addons, key=lambda x: x.name):
        row = [a.name]
        entry: dict = {"addon": a.name}
        for p in profiles:
            has_it = a.name in profile_modules[p.name]
            row.append("[green]yes[/green]" if has_it else "[dim]-[/dim]")
            entry[p.name] = has_it
        rows.append(row)
        json_data.append(entry)

    cols: list[tuple[str, str]] = [("Addon", "cyan")]
    for p in profiles:
        cols.append((p.name, ""))

    out.table(
        f"Addon x Profile Matrix ({len(addons)} addons, {len(profiles)} profiles)",
        cols,
        rows,
        json_data,
    )


@app.command("deps-graph")
def deps_graph(
    ctx: typer.Context,
    module: Annotated[str | None, typer.Option("--module", "-m", help="Filter to one module's dependency tree")] = None,
    format_: Annotated[str, typer.Option("--format", "-f", help="Output format: text, dot, json")] = "text",
    addon_paths: Annotated[str | None, typer.Option("--addon-paths", help="Comma-separated addon paths")] = None,
) -> None:
    """Show dependency graph from manifest depends keys."""
    actx: AppContext = ctx.obj
    out = actx.output

    addons = _discover_with_labels(addon_paths)
    addon_map = {a.name: a for a in addons}

    if module:
        if module not in addon_map:
            out.error(f"Module not found: {module}")
            raise typer.Exit(1)

        # Build transitive dependency tree
        visited: set[str] = set()
        edges: list[tuple[str, str]] = []

        def _walk(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            if name in addon_map:
                for dep in addon_map[name].depends:
                    edges.append((name, dep))
                    _walk(dep)

        _walk(module)

        if format_ == "json":
            out.raw_json({"root": module, "edges": edges, "nodes": sorted(visited)})
        elif format_ == "dot":
            lines = ["digraph deps {"]
            for src, dst in edges:
                lines.append(f'  "{src}" -> "{dst}";')
            lines.append("}")
            typer.echo("\n".join(lines))
        else:
            # text format
            sections = [
                (
                    "Dependency Tree",
                    [
                        ("Root", module),
                        ("Nodes", str(len(visited))),
                        ("Edges", str(len(edges))),
                    ],
                ),
                ("Dependencies", [(f"{s} -> {d}", "") for s, d in edges]),
            ]
            out.detail(f"Deps: {module}", sections, None)
    else:
        # Show all addons with dep counts
        rows = []
        json_data = []
        for a in sorted(addons, key=lambda x: x.name):
            dep_count = len(a.depends)
            rows.append([a.name, str(dep_count), ", ".join(a.depends[:5]) + ("..." if dep_count > 5 else "")])
            json_data.append(
                {
                    "name": a.name,
                    "dep_count": dep_count,
                    "depends": a.depends,
                }
            )

        if format_ == "json":
            out.raw_json(json_data)
        else:
            out.table(
                f"Dependency Counts ({len(addons)} addons)",
                [("Addon", "cyan"), ("Deps", "green"), ("Dependencies", "dim")],
                rows,
                json_data,
            )


@app.command("coverage")
def coverage(
    ctx: typer.Context,
    addon_paths: Annotated[str | None, typer.Option("--addon-paths", help="Comma-separated addon paths")] = None,
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
) -> None:
    """Show bundle coverage: how many disk addons are in at least one bundle."""
    actx: AppContext = ctx.obj
    out = actx.output
    install_dir = _resolve_install_dir(dir_path)

    addons = _discover_with_labels(addon_paths)
    bundle_mods = _all_bundle_modules(install_dir)

    # Group by source type
    by_source: dict[str, list[Addon]] = defaultdict(list)
    for a in addons:
        by_source[a.source_type].append(a)

    rows = []
    json_data = []
    total_covered = 0
    total_addons = 0

    for source_type in sorted(by_source):
        source_addons = by_source[source_type]
        covered = [a for a in source_addons if a.name in bundle_mods]
        pct = (len(covered) * 100 // len(source_addons)) if source_addons else 0
        total_covered += len(covered)
        total_addons += len(source_addons)

        rows.append(
            [
                source_type,
                str(len(source_addons)),
                str(len(covered)),
                str(len(source_addons) - len(covered)),
                f"{pct}%",
            ]
        )
        json_data.append(
            {
                "source_type": source_type,
                "total": len(source_addons),
                "covered": len(covered),
                "uncovered": len(source_addons) - len(covered),
                "coverage_pct": pct,
            }
        )

    # Total row
    total_pct = (total_covered * 100 // total_addons) if total_addons else 0
    rows.append(
        [
            "TOTAL",
            str(total_addons),
            str(total_covered),
            str(total_addons - total_covered),
            f"{total_pct}%",
        ]
    )
    json_data.append(
        {
            "source_type": "TOTAL",
            "total": total_addons,
            "covered": total_covered,
            "uncovered": total_addons - total_covered,
            "coverage_pct": total_pct,
        }
    )

    out.table(
        "Bundle Coverage",
        [
            ("Source", "cyan"),
            ("Total", ""),
            ("Covered", "green"),
            ("Uncovered", "red"),
            ("Coverage", ""),
        ],
        rows,
        json_data,
    )


@app.command("report")
def report(
    ctx: typer.Context,
    addon_paths: Annotated[str | None, typer.Option("--addon-paths", help="Comma-separated addon paths")] = None,
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
    output_file: Annotated[str | None, typer.Option("--output", "-o", help="Save JSON report to file")] = None,
) -> None:
    """Full audit: orphans + missing + duplicates + health + coverage."""
    actx: AppContext = ctx.obj
    out = actx.output
    install_dir = _resolve_install_dir(dir_path)

    addons = _discover_with_labels(addon_paths)
    bundle_mods = _all_bundle_modules(install_dir)
    disk_names = {a.name for a in addons}

    # Orphans
    orphan_list = sorted(a.name for a in addons if a.name not in bundle_mods)

    # Missing
    missing_list = sorted(bundle_mods - disk_names)

    # Duplicates
    by_name: dict[str, list[Addon]] = defaultdict(list)
    for a in addons:
        by_name[a.name].append(a)
    dup_list = sorted(name for name, items in by_name.items() if len(items) > 1)

    # Health (private only)
    private_addons = [a for a in addons if a.source_type == "private"]
    health_scores = []
    for a in private_addons:
        result = score_health(a)
        health_scores.append({"name": a.name, "score": result.score, "issues": len(result.issues)})
    health_scores.sort(key=lambda x: x["score"])
    avg_health = (sum(h["score"] for h in health_scores) // len(health_scores)) if health_scores else 0

    # Coverage
    by_source: dict[str, list[Addon]] = defaultdict(list)
    for a in addons:
        by_source[a.source_type].append(a)
    coverage_data = {}
    for st, items in sorted(by_source.items()):
        covered = len([a for a in items if a.name in bundle_mods])
        coverage_data[st] = {"total": len(items), "covered": covered}

    sections = [
        (
            "Summary",
            [
                ("Total Addons", str(len(addons))),
                ("Orphans", str(len(orphan_list))),
                ("Missing", str(len(missing_list))),
                ("Duplicates", str(len(dup_list))),
                ("Avg Health (private)", f"{avg_health}/100"),
            ],
        ),
    ]
    if orphan_list:
        sections.append(("Orphans (not in any bundle)", [(o, "") for o in orphan_list[:20]]))
        if len(orphan_list) > 20:
            sections[-1][1].append((f"... and {len(orphan_list) - 20} more", ""))
    if missing_list:
        sections.append(("Missing (in bundle, not on disk)", [(m, "") for m in missing_list[:20]]))
        if len(missing_list) > 20:
            sections[-1][1].append((f"... and {len(missing_list) - 20} more", ""))
    if dup_list:
        sections.append(("Duplicates", [(d, "") for d in dup_list]))
    if health_scores:
        worst = health_scores[:10]
        sections.append(("Worst Health (private)", [(h["name"], f"{h['score']}/100") for h in worst]))

    json_obj = {
        "total_addons": len(addons),
        "orphans": orphan_list,
        "missing": missing_list,
        "duplicates": dup_list,
        "health_summary": health_scores,
        "avg_health": avg_health,
        "coverage": coverage_data,
    }

    out.detail("Addon Audit Report", sections, json_obj)

    if output_file:
        import json

        Path(output_file).write_text(json.dumps(json_obj, indent=2), encoding="utf-8")
        out.success(f"Report saved to {output_file}")


# ============================================================================
# Remote commands (need Odoo connection)
# ============================================================================


@app.command("drift")
def drift(
    ctx: typer.Context,
    profile: Annotated[str, typer.Argument(help="Profile name to compare against")],
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
    addon_paths: Annotated[str | None, typer.Option("--addon-paths", help="Comma-separated addon paths")] = None,
) -> None:
    """Compare profile YAML vs live Odoo installed modules."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    install_dir = _resolve_install_dir(dir_path)

    # Resolve profile modules
    profile_path = _find_profile_file(install_dir, profile)
    if not profile_path:
        out.error(f"Profile not found: {profile}")
        raise typer.Exit(1)

    prof = load_profile(profile_path)
    expected_modules = set(resolve_profile_modules(prof, install_dir))

    # Get disk addons for version comparison
    addons = _discover_with_labels(addon_paths)
    disk_versions = {a.name: a.version for a in addons}

    # Query installed modules from Odoo
    installed_records = c.search_read(
        "ir.module.module",
        domain=[("state", "=", "installed")],
        fields=["name", "installed_version"],
    )
    installed_map = {r["name"]: r.get("installed_version", "") for r in installed_records}
    installed_names = set(installed_map)

    # Compute drift
    missing_mods = sorted(expected_modules - installed_names)
    extra_mods = sorted(installed_names - expected_modules)
    version_mismatches = []
    for mod in sorted(expected_modules & installed_names):
        disk_ver = disk_versions.get(mod, "")
        live_ver = installed_map.get(mod, "")
        if disk_ver and live_ver and disk_ver != live_ver:
            version_mismatches.append((mod, disk_ver, live_ver))

    sections = [
        (
            "Drift Summary",
            [
                ("Profile", prof.name),
                ("Expected modules", str(len(expected_modules))),
                ("Installed modules", str(len(installed_names))),
                ("Missing (in profile, not installed)", str(len(missing_mods))),
                ("Extra (installed, not in profile)", str(len(extra_mods))),
                ("Version mismatches", str(len(version_mismatches))),
            ],
        ),
    ]
    if missing_mods:
        sections.append(("Missing", [(m, "") for m in missing_mods]))
    if extra_mods:
        sections.append(("Extra", [(m, "") for m in extra_mods]))
    if version_mismatches:
        sections.append(
            (
                "Version Mismatches",
                [(name, f"disk={disk} live={live}") for name, disk, live in version_mismatches],
            )
        )

    json_obj = {
        "profile": prof.name,
        "expected": len(expected_modules),
        "installed": len(installed_names),
        "missing": missing_mods,
        "extra": extra_mods,
        "version_mismatches": [{"module": n, "disk": d, "live": l} for n, d, l in version_mismatches],
    }

    out.detail(f"Drift: {prof.name}", sections, json_obj)


@app.command("drift-snapshot")
def drift_snapshot(
    ctx: typer.Context,
    profile: Annotated[str, typer.Argument(help="Profile name to compare against")],
    snapshot_file: Annotated[str, typer.Argument(help="Path to snapshot JSON file")],
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory path")] = None,
    addon_paths: Annotated[str | None, typer.Option("--addon-paths", help="Comma-separated addon paths")] = None,
) -> None:
    """Compare profile YAML vs a snapshot JSON file (offline)."""
    actx: AppContext = ctx.obj
    out = actx.output
    install_dir = _resolve_install_dir(dir_path)

    # Resolve profile modules
    profile_path = _find_profile_file(install_dir, profile)
    if not profile_path:
        out.error(f"Profile not found: {profile}")
        raise typer.Exit(1)

    prof = load_profile(profile_path)
    expected_modules = set(resolve_profile_modules(prof, install_dir))

    # Load snapshot
    snap_path = Path(snapshot_file)
    if not snap_path.exists():
        out.error(f"Snapshot file not found: {snapshot_file}")
        raise typer.Exit(1)

    snapshot = load_snapshot(snap_path)
    snap_map = {e.name: e for e in snapshot.modules}
    snap_names = set(snap_map)

    # Get disk addons for version comparison
    addons = _discover_with_labels(addon_paths)
    disk_versions = {a.name: a.version for a in addons}

    # Compute drift
    missing_mods = sorted(expected_modules - snap_names)
    extra_mods = sorted(snap_names - expected_modules)
    version_mismatches = []
    for mod in sorted(expected_modules & snap_names):
        disk_ver = disk_versions.get(mod, "")
        snap_ver = snap_map[mod].version
        if disk_ver and snap_ver and disk_ver != snap_ver:
            version_mismatches.append((mod, disk_ver, snap_ver))

    sections = [
        (
            "Drift Summary (snapshot)",
            [
                ("Profile", prof.name),
                ("Snapshot", snapshot_file),
                ("Snapshot date", snapshot.metadata.exported_at or "-"),
                ("Expected modules", str(len(expected_modules))),
                ("Snapshot modules", str(len(snap_names))),
                ("Missing (in profile, not in snapshot)", str(len(missing_mods))),
                ("Extra (in snapshot, not in profile)", str(len(extra_mods))),
                ("Version mismatches", str(len(version_mismatches))),
            ],
        ),
    ]
    if missing_mods:
        sections.append(("Missing", [(m, "") for m in missing_mods]))
    if extra_mods:
        sections.append(("Extra", [(m, "") for m in extra_mods]))
    if version_mismatches:
        sections.append(
            (
                "Version Mismatches",
                [(name, f"disk={disk} snap={snap}") for name, disk, snap in version_mismatches],
            )
        )

    json_obj = {
        "profile": prof.name,
        "snapshot_file": snapshot_file,
        "snapshot_date": snapshot.metadata.exported_at,
        "expected": len(expected_modules),
        "snapshot_count": len(snap_names),
        "missing": missing_mods,
        "extra": extra_mods,
        "version_mismatches": [{"module": n, "disk": d, "snapshot": s} for n, d, s in version_mismatches],
    }

    out.detail(f"Drift (snapshot): {prof.name}", sections, json_obj)
