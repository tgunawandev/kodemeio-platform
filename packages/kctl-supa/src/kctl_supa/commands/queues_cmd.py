"""pgmq message queue management commands for kctl-supa."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.docker import DockerOps
from kctl_supa.core.exceptions import DockerError

app = typer.Typer(help="Manage pgmq message queues.")


def _get_docker(actx: AppContext) -> DockerOps:
    return DockerOps(actx.config)


def _run_psql(actx: AppContext, query: str) -> str:
    out = actx.output
    try:
        docker = _get_docker(actx)
        result = docker.psql(query)
        docker.close()
        return result
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc


@app.command(name="list")
def list_queues(ctx: typer.Context) -> None:
    """List all message queues."""
    actx: AppContext = ctx.obj
    result = _run_psql(
        actx,
        "SELECT queue_name, created_at, is_partitioned, is_unlogged FROM pgmq.list_queues() ORDER BY queue_name",
    )
    typer.echo(result)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Queue name")],
) -> None:
    """Create a new message queue."""
    actx: AppContext = ctx.obj
    out = actx.output
    _run_psql(actx, f"SELECT pgmq.create('{name}')")
    out.success(f"Queue '{name}' created")


@app.command()
def drop(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Queue name to drop")],
) -> None:
    """Drop a message queue."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not typer.confirm(f"Drop queue '{name}'? All messages will be lost."):
        raise typer.Exit(0)

    _run_psql(actx, f"SELECT pgmq.drop_queue('{name}')")
    out.success(f"Queue '{name}' dropped")


@app.command()
def send(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Queue name")],
    message: Annotated[str, typer.Argument(help="JSON message payload")],
) -> None:
    """Send a message to a queue."""
    actx: AppContext = ctx.obj
    out = actx.output
    result = _run_psql(actx, f"SELECT pgmq.send('{name}', '{message}'::jsonb)")
    out.success("Message sent")
    typer.echo(result)


@app.command()
def read(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Queue name")],
    count: Annotated[int, typer.Option("--count", "-n", help="Number of messages")] = 5,
    visibility: Annotated[int, typer.Option("--vt", help="Visibility timeout in seconds")] = 30,
) -> None:
    """Read messages from a queue (makes them invisible for vt seconds)."""
    actx: AppContext = ctx.obj
    result = _run_psql(
        actx,
        f"SELECT msg_id, read_ct, enqueued_at, vt, message FROM pgmq.read('{name}', {visibility}, {count})",
    )
    typer.echo(result)


@app.command()
def pop(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Queue name")],
) -> None:
    """Pop (read and delete) a message from a queue."""
    actx: AppContext = ctx.obj
    result = _run_psql(
        actx,
        f"SELECT msg_id, read_ct, enqueued_at, vt, message FROM pgmq.pop('{name}')",
    )
    typer.echo(result)


@app.command()
def delete(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Queue name")],
    msg_id: Annotated[int, typer.Argument(help="Message ID to delete")],
) -> None:
    """Delete a specific message from a queue."""
    actx: AppContext = ctx.obj
    out = actx.output
    _run_psql(actx, f"SELECT pgmq.delete('{name}', {msg_id})")
    out.success(f"Message {msg_id} deleted from queue '{name}'")


@app.command()
def purge(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Queue name")],
) -> None:
    """Purge all messages from a queue."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not typer.confirm(f"Purge all messages from queue '{name}'?"):
        raise typer.Exit(0)

    result = _run_psql(actx, f"SELECT pgmq.purge_queue('{name}')")
    out.success(f"Queue '{name}' purged")
    typer.echo(result)


@app.command()
def metrics(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Queue name")] = "",
) -> None:
    """Show queue metrics (depth, oldest message age)."""
    actx: AppContext = ctx.obj
    if name:
        result = _run_psql(
            actx,
            f"SELECT queue_name, queue_length, newest_msg_age_sec, oldest_msg_age_sec, total_messages "
            f"FROM pgmq.metrics('{name}')",
        )
    else:
        result = _run_psql(
            actx,
            "SELECT queue_name, queue_length, newest_msg_age_sec, oldest_msg_age_sec, total_messages "
            "FROM pgmq.metrics_all() ORDER BY queue_name",
        )
    typer.echo(result)
