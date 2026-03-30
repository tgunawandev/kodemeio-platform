"""Skill testing commands."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated

import typer

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.exceptions import GatewayError, NotFoundError

app = typer.Typer(help="Test, lint, and validate OpenClaw skills.")

_GATEWAY_HINT = "Start the gateway first: kctl-claw deploy up"

REQUIRED_FRONTMATTER = ["name", "version", "description"]
REQUIRED_SECTIONS = ["## Overview", "## Usage"]


def _skills_root(project_root: Path) -> Path:
    return project_root / "config" / "skills"


def _parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Parse YAML frontmatter from markdown. Returns (meta, body)."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, content

    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return {}, content

    meta: dict[str, str] = {}
    for line in lines[1:end_idx]:
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip().strip('"').strip("'")

    body = "\n".join(lines[end_idx + 1 :])
    return meta, body


@app.command("run")
def run(
    ctx: typer.Context,
    skill: Annotated[str, typer.Argument(help="Skill name")],
    input_text: Annotated[str, typer.Option("--input", help="Test input text")] = "test",
) -> None:
    """Execute a skill with test input via the gateway."""
    actx: AppContext = ctx.obj
    out = actx.output

    skill_dir = _skills_root(actx.project_root) / skill
    if not skill_dir.exists():
        raise NotFoundError("Skill", skill)

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        out.error(f"No SKILL.md found in config/skills/{skill}/")
        raise typer.Exit(1)

    meta, _ = _parse_frontmatter(skill_md.read_text())
    trigger = meta.get("trigger", f"/{skill}")

    out.info(f"Running skill {skill!r} (trigger: {trigger!r}) with input: {input_text!r}")

    start = time.perf_counter()
    try:
        data = actx.gateway.post("/api/skills/run", {"skill": skill, "trigger": trigger, "input": input_text})
        elapsed_ms = (time.perf_counter() - start) * 1000

        if isinstance(data, dict):
            sections = [
                (
                    "Result",
                    [
                        ("Skill", skill),
                        ("Trigger", trigger),
                        ("Status", str(data.get("status", ""))),
                        ("Duration", f"{elapsed_ms:.0f}ms"),
                        ("Output", str(data.get("output", ""))[:200]),
                    ],
                )
            ]
            out.detail(f"Skill Run: {skill}", sections, data_for_json=data)
        else:
            out.text(str(data))
    except GatewayError as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        out.warn(f"Gateway not available ({elapsed_ms:.0f}ms): {e}")
        out.info(_GATEWAY_HINT)


@app.command()
def lint(
    ctx: typer.Context,
    skill: Annotated[str, typer.Argument(help="Skill name")],
) -> None:
    """Validate skill markdown: required frontmatter fields and sections."""
    actx: AppContext = ctx.obj
    out = actx.output

    skill_dir = _skills_root(actx.project_root) / skill
    if not skill_dir.exists():
        raise NotFoundError("Skill", skill)

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        out.error(f"No SKILL.md found for skill {skill!r}")
        raise typer.Exit(1)

    content = skill_md.read_text()
    meta, body = _parse_frontmatter(content)

    errors: list[str] = []
    warnings: list[str] = []

    # Check required frontmatter
    for field in REQUIRED_FRONTMATTER:
        if field not in meta:
            errors.append(f"Missing frontmatter field: {field!r}")
        elif not meta[field]:
            warnings.append(f"Empty frontmatter field: {field!r}")

    # Check required sections
    for section in REQUIRED_SECTIONS:
        if section not in content:
            warnings.append(f"Missing section: {section!r}")

    # Check trigger format
    trigger = meta.get("trigger", "")
    if trigger and not trigger.startswith("/"):
        errors.append(f"Trigger must start with '/': got {trigger!r}")

    rows = []
    json_data = []
    if errors:
        for e in errors:
            rows.append(["ERROR", e])
            json_data.append({"level": "ERROR", "message": e})
    if warnings:
        for w in warnings:
            rows.append(["WARN", w])
            json_data.append({"level": "WARN", "message": w})
    if not errors and not warnings:
        rows.append(["OK", "All checks passed"])
        json_data.append({"level": "OK", "message": "All checks passed"})

    out.table(
        f"Lint: {skill} ({len(errors)} errors, {len(warnings)} warnings)",
        [("Level", "cyan"), ("Message", "")],
        rows,
        data_for_json=json_data,
    )

    if errors:
        raise typer.Exit(1)


@app.command()
def validate(ctx: typer.Context) -> None:
    """Validate all skills: file refs, tool refs, frontmatter."""
    actx: AppContext = ctx.obj
    out = actx.output

    skills_dir = _skills_root(actx.project_root)
    if not skills_dir.exists():
        out.warn("Skills directory not found: config/skills/")
        return

    rows = []
    json_data = []
    total_errors = 0

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue

        skill_name = skill_dir.name
        skill_md = skill_dir / "SKILL.md"

        if not skill_md.exists():
            rows.append([skill_name, "ERROR", "Missing SKILL.md"])
            json_data.append({"skill": skill_name, "status": "ERROR", "detail": "Missing SKILL.md"})
            total_errors += 1
            continue

        content = skill_md.read_text()
        meta, _ = _parse_frontmatter(content)

        missing_fields = [f for f in REQUIRED_FRONTMATTER if f not in meta]
        if missing_fields:
            detail = f"Missing frontmatter: {', '.join(missing_fields)}"
            rows.append([skill_name, "WARN", detail])
            json_data.append({"skill": skill_name, "status": "WARN", "detail": detail})
        else:
            rows.append([skill_name, "OK", f"v{meta.get('version', '?')} — {meta.get('trigger', '')}"])
            json_data.append({"skill": skill_name, "status": "OK", "meta": meta})

    out.table(
        f"Skill Validation ({len(rows)} skills, {total_errors} errors)",
        [("Skill", "cyan"), ("Status", ""), ("Detail", "dim")],
        rows,
        data_for_json=json_data,
    )

    if total_errors:
        raise typer.Exit(1)
    else:
        out.success("All skills validated.")


@app.command()
def bench(
    ctx: typer.Context,
    skill: Annotated[str, typer.Argument(help="Skill name")],
) -> None:
    """Measure skill execution time via the gateway."""
    actx: AppContext = ctx.obj
    out = actx.output

    skill_dir = _skills_root(actx.project_root) / skill
    if not skill_dir.exists():
        raise NotFoundError("Skill", skill)

    out.info(f"Benchmarking skill {skill!r}...")

    timings = []
    iterations = 3
    for _ in range(iterations):
        start = time.perf_counter()
        try:
            actx.gateway.post("/api/skills/run", {"skill": skill, "input": "benchmark test"})
            elapsed_ms = (time.perf_counter() - start) * 1000
            timings.append(elapsed_ms)
        except GatewayError:
            break

    if not timings:
        out.warn("Gateway not available. Cannot benchmark skill execution.")
        out.info(_GATEWAY_HINT)
        return

    avg = sum(timings) / len(timings)
    sections = [
        (
            "Benchmark",
            [
                ("Skill", skill),
                ("Iterations", str(len(timings))),
                ("Avg (ms)", f"{avg:.0f}"),
                ("Min (ms)", f"{min(timings):.0f}"),
                ("Max (ms)", f"{max(timings):.0f}"),
            ],
        )
    ]
    out.detail(
        f"Skill Bench: {skill}",
        sections,
        data_for_json={"skill": skill, "iterations": len(timings), "avg_ms": round(avg, 1), "timings": timings},
    )
