from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from kctl_mm.core.callbacks import AppContext

app = typer.Typer(help="Channel management.", no_args_is_help=True)


def _c(ctx: typer.Context) -> AppContext:
    return ctx.ensure_object(AppContext)


@app.command("list")
def list_cmd(ctx: typer.Context, team_name: str) -> None:
    c = _c(ctx)
    team = c.client.get_team_by_name(team_name)
    channels = c.client.list_channels_for_team(team["id"])
    rows = [[ch.get("id", ""), ch.get("name", ""), ch.get("display_name", ""), ch.get("type", "")] for ch in channels]
    c.output.table(
        "Channels",
        [("ID", "dim"), ("Name", "cyan"), ("Display", "green"), ("Type", "yellow")],
        rows,
        data_for_json=channels,
    )


@app.command("get")
def get_cmd(ctx: typer.Context, team_name: str, channel_name: str) -> None:
    c = _c(ctx)
    team = c.client.get_team_by_name(team_name)
    c.output.raw_json(c.client.get_channel_by_name(team["id"], channel_name))


@app.command("create")
def create_cmd(
    ctx: typer.Context,
    team_name: str,
    channel_name: str,
    display: str,
    private: bool = typer.Option(False, "--private"),
) -> None:
    c = _c(ctx)
    team = c.client.get_team_by_name(team_name)
    c.output.raw_json(c.client.create_channel(team["id"], channel_name, display, private=private))


@app.command("archive")
def archive_cmd(ctx: typer.Context, team_name: str, channel_name: str) -> None:
    r = _c(ctx).mm_exec.mmctl(["channel", "archive", f"{team_name}:{channel_name}"])
    typer.echo(r.stdout)


@app.command("members")
def members_cmd(ctx: typer.Context, team_name: str, channel_name: str) -> None:
    c = _c(ctx)
    team = c.client.get_team_by_name(team_name)
    channel = c.client.get_channel_by_name(team["id"], channel_name)
    c.output.raw_json(c.client.list_channel_members(channel["id"]))


@app.command("add")
def add_cmd(ctx: typer.Context, team_name: str, channel_name: str, user: str) -> None:
    r = _c(ctx).mm_exec.mmctl(["channel", "users", "add", f"{team_name}:{channel_name}", user])
    typer.echo(r.stdout)


@app.command("remove")
def remove_cmd(ctx: typer.Context, team_name: str, channel_name: str, user: str) -> None:
    r = _c(ctx).mm_exec.mmctl(["channel", "users", "remove", f"{team_name}:{channel_name}", user])
    typer.echo(r.stdout)


@app.command("rename")
def rename_cmd(ctx: typer.Context, team_name: str, channel_name: str, new_display: str) -> None:
    c = _c(ctx)
    team = c.client.get_team_by_name(team_name)
    channel = c.client.get_channel_by_name(team["id"], channel_name)
    c.output.raw_json(c.client.rename_channel(channel["id"], new_display))


@app.command("patch")
def patch_cmd(
    ctx: typer.Context,
    team_name: str,
    channel_name: str,
    display_name: Annotated[str | None, typer.Option("--display-name")] = None,
    header: Annotated[str | None, typer.Option("--header")] = None,
    purpose: Annotated[str | None, typer.Option("--purpose")] = None,
) -> None:
    """Patch channel metadata (display name, header, purpose)."""
    c = _c(ctx)
    team = c.client.get_team_by_name(team_name)
    channel = c.client.get_channel_by_name(team["id"], channel_name)
    fields = {
        k: v for k, v in {"display_name": display_name, "header": header, "purpose": purpose}.items() if v is not None
    }
    if not fields:
        c.output.warn("No fields to patch.")
        return
    c.output.raw_json(c.client.patch_channel(channel["id"], **fields))


@app.command("sync-pinned")
def sync_pinned_cmd(
    ctx: typer.Context,
    team_name: Annotated[str, typer.Argument(help="Team slug (e.g. 'tpp').")],
    channel_name: Annotated[str, typer.Argument(help="Channel name (e.g. 'onboarding').")],
    source_dir: Annotated[Path, typer.Argument(help="Directory containing NN-*.md pinned-post sources.")],
    display_name: Annotated[
        str | None, typer.Option("--display-name", help="Create channel with this display name if missing.")
    ] = None,
    header: Annotated[str | None, typer.Option("--header", help="Channel header (applied on every run).")] = None,
    purpose: Annotated[str | None, typer.Option("--purpose", help="Channel purpose (applied on every run).")] = None,
    private: Annotated[
        bool, typer.Option("--private", help="Create the channel as private if it doesn't exist yet.")
    ] = False,
    state_file: Annotated[
        Path | None,
        typer.Option("--state-file", help="Path to persist post-id mapping. Default: <source_dir>/.synced-ids.json."),
    ] = None,
) -> None:
    """Idempotently sync a channel's pinned posts from a directory of markdown files.

    Creates the channel if missing, patches header/purpose, then for each file
    matching ``NN-*.md`` (sorted): creates a new pinned post or updates the
    previously-synced one, based on a state file keyed by filename.

    Re-runs are safe — existing posts are updated in place (Mattermost preserves
    post id + pin status), new files produce new pinned posts, and deletions are
    not handled automatically (unpin manually if you want to remove a topic).
    """
    c = _c(ctx)
    if not source_dir.is_dir():
        c.output.error(f"source-dir {source_dir} does not exist or is not a directory")
        raise typer.Exit(2)
    state_path = state_file or (source_dir / ".synced-ids.json")
    state: dict[str, str] = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
        except Exception:
            c.output.warn(f"state file {state_path} unreadable — starting fresh")

    team = c.client.get_team_by_name(team_name)
    # Ensure channel exists
    channel = None
    try:
        channel = c.client.get_channel_by_name(team["id"], channel_name)
        if not isinstance(channel, dict) or "id" not in channel or len(channel.get("id", "")) != 26:
            channel = None
    except Exception:
        channel = None
    if channel is None:
        c.output.info(f"channel #{channel_name} not found — creating")
        channel = c.client.create_channel(
            team["id"],
            channel_name,
            display_name or channel_name,
            private=private,
        )
    channel_id = channel["id"]

    if header is not None or purpose is not None or display_name is not None:
        fields = {
            k: v
            for k, v in {"display_name": display_name, "header": header, "purpose": purpose}.items()
            if v is not None
        }
        c.client.patch_channel(channel_id, **fields)
        c.output.info("  patched channel metadata")

    files = sorted(p for p in source_dir.glob("[0-9][0-9]-*.md"))
    if not files:
        c.output.warn("no NN-*.md files found in source-dir")
        return

    created = updated = failed = 0
    for f in files:
        slug = f.stem
        body = f.read_text().strip()
        existing = state.get(slug)
        if existing:
            try:
                c.client.update_post(existing, body)
                updated += 1
                c.output.info(f"  ↻ updated {slug}")
                continue
            except Exception as e:
                c.output.warn(f"  update of {slug} failed ({e}) — will recreate")
        try:
            post = c.client.create_post(channel_id, body)
            pid = post["id"]
            c.client.pin_post(pid)
            state[slug] = pid
            created += 1
            c.output.success(f"  ＋ created + pinned {slug} ({pid})")
        except Exception as e:
            failed += 1
            c.output.error(f"  create of {slug} failed: {e}")

    state_path.write_text(json.dumps(state, indent=2, sort_keys=True))
    c.output.success(f"sync complete: created={created} updated={updated} failed={failed} · state={state_path}")
