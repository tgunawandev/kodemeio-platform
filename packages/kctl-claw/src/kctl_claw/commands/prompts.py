"""Prompt management commands."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated

import typer

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.exceptions import GatewayError

app = typer.Typer(help="Manage system prompts: list, view, diff, test, history, optimize.")

_GATEWAY_HINT = "Start the gateway first: kctl-claw deploy up"

_PROMPT_DIRS = [
    "config/workspace",
    "config/agents",
    "config/skills",
]


def _find_prompts(project_root: Path) -> dict[str, Path]:
    """Scan prompt directories for markdown files. Returns name -> Path."""
    found: dict[str, Path] = {}
    for rel_dir in _PROMPT_DIRS:
        d = project_root / rel_dir
        if not d.exists():
            continue
        for md_file in sorted(d.rglob("*.md")):
            rel = md_file.relative_to(project_root)
            name = str(rel).replace("\\", "/")
            found[name] = md_file
    return found


def _count_tokens_estimate(text: str) -> int:
    """Word-based token estimate (~0.75 words/token)."""
    words = len(text.split())
    return int(words / 0.75)


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all system prompts (agents, skills, workspace)."""
    actx: AppContext = ctx.obj
    out = actx.output

    prompts = _find_prompts(actx.project_root)

    rows = []
    json_data = []
    for name, path in prompts.items():
        size = path.stat().st_size
        tokens = _count_tokens_estimate(path.read_text())
        category = name.split("/")[1] if name.count("/") >= 1 else "root"
        rows.append([name, category, f"{size:,}", f"~{tokens:,}"])
        json_data.append({"name": name, "category": category, "size_bytes": size, "tokens_est": tokens})

    out.table(
        f"System Prompts ({len(prompts)})",
        [("Name", "cyan"), ("Category", ""), ("Size", ""), ("Tokens (est)", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def get(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Prompt name or path")],
) -> None:
    """View prompt content."""
    actx: AppContext = ctx.obj
    out = actx.output

    prompts = _find_prompts(actx.project_root)
    # Try exact match, then partial match
    path = prompts.get(name)
    if path is None:
        matches = {k: v for k, v in prompts.items() if name in k}
        if len(matches) == 1:
            name, path = next(iter(matches.items()))
        elif len(matches) > 1:
            out.error(f"Ambiguous name {name!r}. Matches: {', '.join(matches)}")
            raise typer.Exit(1)
        else:
            out.error(f"Prompt not found: {name!r}")
            raise typer.Exit(1)

    content = path.read_text()
    tokens = _count_tokens_estimate(content)

    if out.json_mode or out.format == "json":
        import json

        typer.echo(json.dumps({"name": name, "content": content, "tokens_est": tokens}))
    else:
        out.info(f"Prompt: {name} (~{tokens} tokens)")
        typer.echo(content)


@app.command()
def diff(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Prompt name or path")],
    base: Annotated[str, typer.Option("--base", help="Git ref to diff against")] = "HEAD~1",
) -> None:
    """Diff a prompt file between git refs."""
    actx: AppContext = ctx.obj
    out = actx.output

    prompts = _find_prompts(actx.project_root)
    path = prompts.get(name)
    if path is None:
        out.error(f"Prompt not found: {name!r}")
        raise typer.Exit(1)

    rel_path = path.relative_to(actx.project_root)
    out.info(f"Diff: {rel_path} ({base} vs HEAD)")

    try:
        result = subprocess.run(
            ["git", "diff", base, "HEAD", "--", str(rel_path)],
            cwd=str(actx.project_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout:
            typer.echo(result.stdout)
        elif result.returncode == 0:
            out.info("No changes since HEAD~1.")
        else:
            out.warn(f"Git diff error: {result.stderr[:200]}")
    except FileNotFoundError as err:
        out.error("git not found in PATH.")
        raise typer.Exit(1) from err


@app.command()
def test(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Prompt name or path")],
    input_text: Annotated[str, typer.Argument(help="Test input to send with the prompt")],
) -> None:
    """Test a prompt via the gateway with given input."""
    actx: AppContext = ctx.obj
    out = actx.output

    prompts = _find_prompts(actx.project_root)
    path = prompts.get(name)
    if path is None:
        out.error(f"Prompt not found: {name!r}")
        raise typer.Exit(1)

    content = path.read_text()
    out.info(f"Testing prompt {name!r} with input: {input_text!r}")

    try:
        data = actx.gateway.post("/api/prompts/test", {"prompt": content, "input": input_text})
        if isinstance(data, dict):
            sections = [
                (
                    "Result",
                    [
                        ("Prompt", name),
                        ("Status", str(data.get("status", ""))),
                        ("Response", str(data.get("content", ""))[:300]),
                        ("Tokens", str(data.get("tokens", ""))),
                    ],
                )
            ]
            out.detail(f"Prompt Test: {name}", sections, data_for_json=data)
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command()
def history(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Prompt name or path")],
) -> None:
    """Show git log of changes to a prompt file."""
    actx: AppContext = ctx.obj
    out = actx.output

    prompts = _find_prompts(actx.project_root)
    path = prompts.get(name)
    if path is None:
        out.error(f"Prompt not found: {name!r}")
        raise typer.Exit(1)

    rel_path = path.relative_to(actx.project_root)
    out.info(f"Git history: {rel_path}")

    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--follow", "-20", "--", str(rel_path)],
            cwd=str(actx.project_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout:
            lines = result.stdout.strip().splitlines()
            rows = [[line[:8], line[9:]] for line in lines]
            out.table(
                f"Prompt History: {name}",
                [("Hash", "dim"), ("Message", "cyan")],
                rows,
                data_for_json=[{"hash": r[0], "message": r[1]} for r in rows],
            )
        else:
            out.warn("No git history found. Is this a git repository?")
    except FileNotFoundError as err:
        out.error("git not found in PATH.")
        raise typer.Exit(1) from err


@app.command()
def optimize(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Prompt name or path")],
) -> None:
    """Token count analysis and optimization suggestions for a prompt."""
    actx: AppContext = ctx.obj
    out = actx.output

    prompts = _find_prompts(actx.project_root)
    path = prompts.get(name)
    if path is None:
        out.error(f"Prompt not found: {name!r}")
        raise typer.Exit(1)

    content = path.read_text()
    lines = content.splitlines()
    words = content.split()
    tokens = _count_tokens_estimate(content)

    # Analyze content structure
    blank_lines = sum(1 for line in lines if not line.strip())
    code_blocks = content.count("```")
    headers = sum(1 for line in lines if line.startswith("#"))
    lists = sum(1 for line in lines if line.strip().startswith(("-", "*", "+")))

    # Generate suggestions
    suggestions = []
    if tokens > 8000:
        suggestions.append("WARN: Prompt exceeds 8K tokens — consider splitting into sections")
    if tokens > 4000:
        suggestions.append("INFO: Large prompt (>4K tokens) may impact latency and cost")
    if blank_lines > len(lines) * 0.3:
        suggestions.append("OPTIMIZE: High blank line ratio — remove extra whitespace")
    if code_blocks > 10:
        suggestions.append("OPTIMIZE: Many code blocks — consider moving examples to separate files")
    if not suggestions:
        suggestions.append("OK: Prompt size looks reasonable")

    sections = [
        (
            "Token Analysis",
            [
                ("File", name),
                ("Lines", str(len(lines))),
                ("Words", str(len(words))),
                ("Tokens (est)", f"~{tokens:,}"),
                ("Size (bytes)", f"{path.stat().st_size:,}"),
                ("Blank Lines", str(blank_lines)),
                ("Headers", str(headers)),
                ("List Items", str(lists)),
                ("Code Blocks", str(code_blocks // 2)),
            ],
        ),
        ("Suggestions", [("", s) for s in suggestions]),
    ]
    out.detail(
        f"Prompt Optimize: {name}",
        sections,
        data_for_json={"name": name, "tokens_est": tokens, "words": len(words), "suggestions": suggestions},
    )
