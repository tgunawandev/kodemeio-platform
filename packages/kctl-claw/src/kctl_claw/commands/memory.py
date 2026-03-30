"""Memory and knowledge graph commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.exceptions import GatewayError

app = typer.Typer(help="Manage agent memory and knowledge graph.")

_GATEWAY_HINT = "Start the gateway first: kctl-claw deploy up"


@app.command()
def stats(ctx: typer.Context) -> None:
    """Show memory stats (file count, sizes) from workspace directory."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    workspace_dir = root / "config" / "workspace"

    if not workspace_dir.exists():
        out.warn(f"Workspace directory not found: {workspace_dir}")
        return

    total_files = 0
    total_bytes = 0
    rows = []
    json_data = []

    for item in sorted(workspace_dir.rglob("*")):
        if item.is_file() and not item.name.startswith("."):
            size = item.stat().st_size
            total_files += 1
            total_bytes += size
            rel = str(item.relative_to(workspace_dir))
            rows.append([rel, f"{size:,}"])
            json_data.append({"file": rel, "size_bytes": size})

    total_kb = total_bytes / 1024
    out.table(
        f"Memory Stats ({total_files} files, {total_kb:.1f} KB total)",
        [("File", "cyan"), ("Size (bytes)", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def search(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Search query")],
) -> None:
    """Search knowledge graph (BM25+vector)."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info(f"Searching memory for: {query!r}")
    try:
        data = actx.gateway.get("/api/memory/search", q=query)
        if isinstance(data, list):
            rows = [[str(item.get("id", "")), str(item.get("content", ""))[:80]] for item in data]
            out.table(
                f"Search Results ({len(data)})",
                [("ID", "cyan"), ("Content (preview)", "")],
                rows,
                data_for_json=data,
            )
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List memory files from the workspace directory."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    memory_dir = root / "config" / "workspace" / "memory"

    if not memory_dir.exists():
        out.warn(f"Memory directory not found: {memory_dir}")
        return

    rows = []
    json_data = []
    for item in sorted(memory_dir.rglob("*")):
        if item.is_file() and not item.name.startswith("."):
            size = item.stat().st_size
            rel = str(item.relative_to(memory_dir))
            rows.append([rel, f"{size:,}"])
            json_data.append({"file": rel, "size_bytes": size})

    if not rows:
        out.info("No memory files found.")
        return

    out.table(
        f"Memory Files ({len(rows)})",
        [("File", "cyan"), ("Size (bytes)", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def prune(ctx: typer.Context) -> None:
    """Remove old memory entries (placeholder — requires running gateway)."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.warn("Prune will remove memory entries older than the retention window.")
    confirmation = typer.prompt("Type 'PRUNE' to confirm")
    if confirmation != "PRUNE":
        out.info("Aborted.")
        return

    out.info("Sending prune request to gateway...")
    try:
        actx.gateway.post("/api/memory/prune", {})
        out.success("Memory pruned.")
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command()
def export(ctx: typer.Context) -> None:
    """Export memory to JSON file (placeholder — requires running gateway)."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Requesting memory export from gateway...")
    try:
        data = actx.gateway.get("/api/memory/export")
        import json
        import time

        export_path = actx.project_root / f"memory-export-{int(time.time())}.json"
        export_path.write_text(json.dumps(data, indent=2, default=str))
        out.success(f"Memory exported to: {export_path}")
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command()
def clear(
    ctx: typer.Context,
    agent: Annotated[str, typer.Argument(help="Agent name whose memory to clear")],
) -> None:
    """Clear an agent's memory (requires confirmation)."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.warn(f"This will permanently clear all memory for agent: {agent!r}")
    confirmation = typer.prompt(f"Type the agent name '{agent}' to confirm")
    if confirmation != agent:
        out.info("Aborted.")
        return

    out.info(f"Clearing memory for agent: {agent!r}")
    try:
        actx.gateway.post(f"/api/memory/clear/{agent}", {})
        out.success(f"Memory cleared for agent: {agent!r}")
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command()
def validate(ctx: typer.Context) -> None:
    """Check MEMORY.md format in the workspace."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = actx.project_root
    memory_files = list(root.glob("**/MEMORY.md"))

    if not memory_files:
        out.warn("No MEMORY.md files found in project.")
        return

    results = []
    for mf in memory_files:
        rel = str(mf.relative_to(root))
        content = mf.read_text()
        lines = content.splitlines()

        errors = []
        # Check for required header
        if not any(line.startswith("# ") for line in lines):
            errors.append("Missing top-level heading (# ...)")
        # Check for section headings
        sections = [line for line in lines if line.startswith("## ")]
        if not sections:
            errors.append("No sections (## ...) found")
        # Check for empty content
        if len(content.strip()) < 50:
            errors.append("Very short content (< 50 chars)")

        status = "OK" if not errors else "WARN"
        detail = ", ".join(errors) if errors else f"{len(sections)} sections, {len(lines)} lines"
        results.append([rel, status, detail])

    out.table(
        f"MEMORY.md Validation ({len(memory_files)} files)",
        [("File", "cyan"), ("Status", ""), ("Detail", "dim")],
        results,
        data_for_json=[{"file": r[0], "status": r[1], "detail": r[2]} for r in results],
    )


@app.command()
def dedupe(ctx: typer.Context) -> None:
    """Find similar or duplicate memory entries."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = actx.project_root
    memory_dir = root / "config" / "workspace" / "memory"

    if not memory_dir.exists():
        out.warn(f"Memory directory not found: {memory_dir}")
        return

    files = [f for f in sorted(memory_dir.rglob("*.md")) if not f.name.startswith(".")]
    if not files:
        out.info("No memory files found.")
        return

    # Simple duplicate detection: compare first 100 chars of each file
    seen: dict[str, str] = {}
    dupes = []
    for f in files:
        key = f.read_text()[:100].strip()
        rel = str(f.relative_to(root))
        if key in seen:
            dupes.append((seen[key], rel, key[:60]))
        else:
            seen[key] = rel

    if not dupes:
        out.success(f"No duplicates found among {len(files)} memory files.")
        return

    rows = [[a, b, preview] for a, b, preview in dupes]
    out.table(
        f"Potential Duplicates ({len(dupes)} pairs)",
        [("File A", "cyan"), ("File B", "cyan"), ("Preview", "dim")],
        rows,
        data_for_json=[{"file_a": r[0], "file_b": r[1], "preview": r[2]} for r in rows],
    )


@app.command()
def relevance(ctx: typer.Context) -> None:
    """Score memory entries by recency and estimated reference count."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = actx.project_root
    memory_dir = root / "config" / "workspace" / "memory"

    if not memory_dir.exists():
        out.warn(f"Memory directory not found: {memory_dir}")
        return

    files = [f for f in sorted(memory_dir.rglob("*.md")) if not f.name.startswith(".")]
    if not files:
        out.info("No memory files found.")
        return

    rows = []
    json_data = []
    for f in files:
        rel = str(f.relative_to(root))
        stat = f.stat()
        size = stat.st_size
        mtime = stat.st_mtime
        # Score: newer + larger = more relevant (simple heuristic)
        import time as time_mod

        age_days = (time_mod.time() - mtime) / 86400
        recency_score = max(0, 100 - int(age_days))
        size_score = min(50, size // 200)
        total_score = recency_score + size_score

        rows.append([rel, f"{age_days:.0f}d", f"{size:,}", str(total_score)])
        json_data.append(
            {"file": rel, "age_days": round(age_days, 1), "size_bytes": size, "relevance_score": total_score}
        )

    # Sort by score descending
    rows.sort(key=lambda r: int(r[3]), reverse=True)

    out.table(
        f"Memory Relevance ({len(rows)} files)",
        [("File", "cyan"), ("Age", ""), ("Size", ""), ("Score", "dim")],
        rows,
        data_for_json=sorted(json_data, key=lambda x: x["relevance_score"], reverse=True),
    )


@app.command("age-report")
def age_report(ctx: typer.Context) -> None:
    """Report memory entries by age buckets."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = actx.project_root
    memory_dir = root / "config" / "workspace" / "memory"

    if not memory_dir.exists():
        out.warn(f"Memory directory not found: {memory_dir}")
        return

    import time as time_mod

    files = [f for f in sorted(memory_dir.rglob("*.md")) if not f.name.startswith(".")]
    if not files:
        out.info("No memory files found.")
        return

    buckets: dict[str, list[str]] = {"<7d": [], "7-30d": [], "30-90d": [], ">90d": []}
    now = time_mod.time()

    for f in files:
        rel = str(f.relative_to(root))
        age_days = (now - f.stat().st_mtime) / 86400
        if age_days < 7:
            buckets["<7d"].append(rel)
        elif age_days < 30:
            buckets["7-30d"].append(rel)
        elif age_days < 90:
            buckets["30-90d"].append(rel)
        else:
            buckets[">90d"].append(rel)

    rows = [
        [bucket, str(len(files_list)), ", ".join(files_list[:2]) + ("..." if len(files_list) > 2 else "")]
        for bucket, files_list in buckets.items()
    ]
    json_data = [{"bucket": b, "count": len(fl), "files": fl} for b, fl in buckets.items()]

    out.table(
        f"Memory Age Report ({len(files)} total files)",
        [("Age Bucket", "cyan"), ("Count", ""), ("Files (preview)", "dim")],
        rows,
        data_for_json=json_data,
    )
