"""Environment variable commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Manage compose environment variables.")


def _parse_env_string(env_str: str) -> list[tuple[str, str]]:
    """Parse an env string into list of (key, value) tuples."""
    result = []
    for line in env_str.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            result.append((key.strip(), value.strip()))
    return result


def _fetch_env(c: AppContext, compose_id: str) -> str:
    """Fetch the current env string for a compose service."""
    data = c.client.get("/compose.one", params={"composeId": compose_id})
    if isinstance(data, dict):
        return data.get("env", "")
    return ""


@app.command("list")
def list_(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
) -> None:
    """List environment variables for a compose service."""
    c: AppContext = ctx.obj
    data = c.client.get("/compose.one", params={"composeId": compose_id})
    env_str = data.get("env", "") if isinstance(data, dict) else ""
    lines = [line for line in env_str.strip().splitlines() if line.strip()] if isinstance(env_str, str) else []
    rows = []
    for line in lines:
        if "=" in line:
            key, _, value = line.partition("=")
            rows.append([key.strip(), value.strip()])
        else:
            rows.append([line, ""])
    c.output.table(
        f"Environment: {compose_id}",
        [("Key", "cyan"), ("Value", "")],
        rows,
        data_for_json={"composeId": compose_id, "environment": env_str},
    )


@app.command()
def get(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
    key: Annotated[str, typer.Argument(help="Environment variable name")],
) -> None:
    """Get a single environment variable."""
    c: AppContext = ctx.obj
    data = c.client.get("/compose.one", params={"composeId": compose_id})
    env_str = data.get("env", "") if isinstance(data, dict) else ""
    found_value: str | None = None
    if isinstance(env_str, str):
        for line in env_str.strip().splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                if k.strip() == key:
                    found_value = v.strip()
                    break
    if found_value is None:
        c.output.error(f"Variable '{key}' not found in compose {compose_id}")
        raise typer.Exit(1)
    sections = [
        (
            "Environment Variable",
            [
                ("Compose", compose_id),
                ("Key", key),
                ("Value", found_value),
            ],
        )
    ]
    c.output.detail(
        f"Env: {key}",
        sections,
        data_for_json={"composeId": compose_id, "key": key, "value": found_value},
    )


@app.command("set")
def set_(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
    key: Annotated[str, typer.Argument(help="Environment variable name")],
    value: Annotated[str, typer.Argument(help="Environment variable value")],
) -> None:
    """Set an environment variable on a compose service."""
    c: AppContext = ctx.obj
    current_env = _fetch_env(c, compose_id)
    new_lines = []
    found = False
    for line in current_env.splitlines():
        stripped = line.strip()
        if stripped and "=" in stripped:
            existing_key = stripped.split("=", 1)[0].strip()
            if existing_key == key:
                new_lines.append(f"{key}={value}")
                found = True
                continue
        new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}")
    updated_env = "\n".join(new_lines)
    result = c.client.post("/compose.update", json={"composeId": compose_id, "env": updated_env})
    c.output.success(f"Set {key} on compose '{compose_id}'")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("delete")
def delete_(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
    key: Annotated[str, typer.Argument(help="Environment variable name to remove")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Remove an environment variable from a compose service."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete env var '{key}' from compose '{compose_id}'?", abort=True)
    current_env = _fetch_env(c, compose_id)
    new_lines = []
    removed = False
    for line in current_env.splitlines():
        stripped = line.strip()
        if stripped and "=" in stripped:
            existing_key = stripped.split("=", 1)[0].strip()
            if existing_key == key:
                removed = True
                continue
        new_lines.append(line)
    if not removed:
        c.output.error(f"Variable '{key}' not found in compose '{compose_id}'")
        raise typer.Exit(1)
    updated_env = "\n".join(new_lines)
    result = c.client.post("/compose.update", json={"composeId": compose_id, "env": updated_env})
    c.output.success(f"Removed {key} from compose '{compose_id}'")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def push(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
    file: Annotated[str, typer.Argument(help="Path to .env file to push")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Push an entire .env file to a compose service (overwrites all env vars)."""
    import pathlib

    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"This will REPLACE ALL env vars on compose '{compose_id}'. Continue?", abort=True)
    path = pathlib.Path(file)
    if not path.exists():
        c.output.error(f"File not found: {file}")
        raise typer.Exit(1)
    if not path.is_file():
        c.output.error(f"Not a file: {file}")
        raise typer.Exit(1)
    env_content = path.read_text()
    line_count = len([line for line in env_content.splitlines() if line.strip() and not line.strip().startswith("#")])
    c.output.info(f"Pushing {line_count} env var(s) from {file} to compose '{compose_id}'...")
    result = c.client.post("/compose.update", json={"composeId": compose_id, "env": env_content})
    c.output.success(f"Pushed {line_count} env var(s) to compose '{compose_id}'")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def pull(
    ctx: typer.Context,
    compose_id: Annotated[str, typer.Argument(help="Compose service ID")],
    output_file: Annotated[str | None, typer.Argument(help="Output file path (stdout if omitted)")] = None,
) -> None:
    """Pull environment variables from a compose service to file or stdout."""
    c: AppContext = ctx.obj
    env_str = _fetch_env(c, compose_id)
    if output_file:
        import pathlib

        pathlib.Path(output_file).write_text(env_str + "\n")
        c.output.success(f"Env vars written to {output_file}")
    else:
        if c.json_mode:
            pairs = _parse_env_string(env_str)
            c.output.raw_json({k: v for k, v in pairs})
        else:
            c.output.text(env_str)
