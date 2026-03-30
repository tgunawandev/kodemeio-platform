"""Environment variable management commands."""

from __future__ import annotations

from pathlib import Path

import typer

from kctl_claw.core.callbacks import AppContext

app = typer.Typer(help="Manage environment variables (.env.prod vs .env.example).")


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file into a dict, skipping comments and blank lines."""
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


def _redact(value: str) -> str:
    """Redact a value: show first 3 chars + *** if long enough, else ***."""
    if not value:
        return "(empty)"
    if len(value) <= 3:
        return "***"
    return value[:3] + "***"


@app.command("check")
def check(ctx: typer.Context) -> None:
    """Compare .env.prod vs .env.example and show missing vars."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    prod_path = root / ".env.prod"
    example_path = root / ".env.example"

    if not example_path.exists():
        out.error(".env.example not found")
        raise typer.Exit(1)

    example = _parse_env_file(example_path)
    prod = _parse_env_file(prod_path)

    missing = [k for k in example if k not in prod]
    present = [k for k in example if k in prod]

    rows = []
    json_data = []
    for k in sorted(example):
        status = "OK" if k in prod else "MISSING"
        rows.append([k, status])
        json_data.append({"key": k, "status": status})

    out.table(
        f"Env Check ({len(present)} present, {len(missing)} missing)",
        [("Key", "cyan"), ("Status", "")],
        rows,
        data_for_json=json_data,
    )

    if missing:
        out.warn(f"{len(missing)} variable(s) missing from .env.prod: {', '.join(missing)}")
        raise typer.Exit(1)
    else:
        out.success("All example variables are present in .env.prod")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all env vars from .env.prod with redacted values."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    prod_path = root / ".env.prod"
    if not prod_path.exists():
        out.error(".env.prod not found")
        raise typer.Exit(1)

    prod = _parse_env_file(prod_path)

    rows = []
    json_data = []
    for k in sorted(prod):
        redacted = _redact(prod[k])
        rows.append([k, redacted])
        json_data.append({"key": k, "value": redacted})

    out.table(
        f"Env Variables ({len(prod)})",
        [("Key", "cyan"), ("Value (redacted)", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command("diff")
def diff(ctx: typer.Context) -> None:
    """Show vars in .env.example that are missing or differ from .env.prod."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    prod_path = root / ".env.prod"
    example_path = root / ".env.example"

    if not example_path.exists():
        out.error(".env.example not found")
        raise typer.Exit(1)

    example = _parse_env_file(example_path)
    prod = _parse_env_file(prod_path)

    rows = []
    json_data = []
    for k in sorted(example):
        if k not in prod:
            status = "MISSING"
            note = "not in .env.prod"
        elif prod[k] and not example[k]:
            status = "SET"
            note = "has value"
        elif not prod[k] and not example[k]:
            status = "EMPTY"
            note = "both empty"
        else:
            status = "OK"
            note = ""

        if status != "OK":
            rows.append([k, status, note])
            json_data.append({"key": k, "status": status, "note": note})

    if not rows:
        out.success("No differences — .env.prod matches .env.example template.")
        return

    out.table(
        f"Env Diff ({len(rows)} item(s))",
        [("Key", "cyan"), ("Status", ""), ("Note", "dim")],
        rows,
        data_for_json=json_data,
    )
