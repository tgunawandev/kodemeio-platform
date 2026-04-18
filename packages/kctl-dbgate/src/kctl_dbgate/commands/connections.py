"""Connection CRUD commands.

Wraps DBGate's /connections/* RPC endpoints.
"""

from __future__ import annotations

from typing import Annotated, Any

import typer
from kctl_lib.exceptions import KctlError

from kctl_dbgate.core.callbacks import AppContext

app = typer.Typer(help="Manage DBGate database connections.")


def _source_of(conn: dict[str, Any]) -> str:
    """Heuristic: env-configured connections are read-only."""
    if conn.get("isReadOnly") or conn.get("readOnly"):
        return "env"
    return "user"


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all connections known to DBGate (env-configured + user-added)."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        connections = actx.client.list_connections()
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    rows: list[list[str]] = []
    for conn in connections:
        rows.append(
            [
                str(conn.get("_id", "")),
                str(conn.get("displayName") or conn.get("label") or ""),
                str(conn.get("engine", "")),
                str(conn.get("server", "")),
                str(conn.get("port", "")),
                str(conn.get("user", "")),
                "yes" if (conn.get("isReadOnly") or conn.get("readOnly")) else "no",
                _source_of(conn),
            ]
        )

    out.table(
        title=f"{len(rows)} connection(s)",
        columns=[
            ("ID", "cyan"),
            ("Label", "white"),
            ("Engine", "magenta"),
            ("Server", "green"),
            ("Port", "yellow"),
            ("User", "blue"),
            ("ReadOnly", "yellow"),
            ("Source", "dim"),
        ],
        rows=rows,
        data_for_json=connections,
    )


@app.command()
def get(
    ctx: typer.Context,
    conid: Annotated[str, typer.Argument(help="Connection ID")],
) -> None:
    """Show full detail for a single connection."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        conn = actx.client.call("/connections/get", {"conid": conid})
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    if not conn:
        out.error(f"Connection {conid} not found")
        raise typer.Exit(1)

    sections = [
        (
            "Connection",
            [
                ("ID", str(conn.get("_id", ""))),
                ("Label", str(conn.get("displayName") or conn.get("label") or "")),
                ("Engine", str(conn.get("engine", ""))),
                ("Server", str(conn.get("server", ""))),
                ("Port", str(conn.get("port", ""))),
                ("User", str(conn.get("user", ""))),
                ("Database", str(conn.get("database", ""))),
                ("ReadOnly", "yes" if (conn.get("isReadOnly") or conn.get("readOnly")) else "no"),
            ],
        ),
    ]
    out.detail("Connection Details", sections, data_for_json=conn)


@app.command()
def test(
    ctx: typer.Context,
    conid: Annotated[str, typer.Argument(help="Connection ID")],
) -> None:
    """Test a connection."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        result = actx.client.call("/connections/test", {"conid": conid})
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    msgtype = (result or {}).get("msgtype", "")
    if msgtype == "connected":
        version = result.get("version", "")
        out.success(f"OK — connected ({version})" if version else "OK — connected")
    else:
        out.error(f"Test failed: {result}")
        raise typer.Exit(1)


@app.command()
def delete(
    ctx: typer.Context,
    conid: Annotated[str, typer.Argument(help="Connection ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a connection."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not force and not typer.confirm(f"Delete connection {conid}?"):
        raise typer.Exit(0)

    try:
        actx.client.call("/connections/delete", {"_id": conid})
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    out.success(f"Connection {conid} deleted")


_SSH_MODES = {"userPassword", "agent", "keyFile"}


def _build_payload(
    label: str | None,
    engine: str | None,
    server: str | None,
    port: str | None,
    user: str | None,
    password: str | None,
    database: str | None,
    *,
    ssh_host: str | None = None,
    ssh_port: str | None = None,
    ssh_user: str | None = None,
    ssh_mode: str | None = None,
    ssh_password: str | None = None,
    ssh_keyfile: str | None = None,
    ssh_keyfile_password: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if label is not None:
        payload["displayName"] = label
    if engine is not None:
        payload["engine"] = engine
    if server is not None:
        payload["server"] = server
    if port is not None:
        payload["port"] = port
    if user is not None:
        payload["user"] = user
    if password is not None:
        payload["password"] = password
    if database is not None:
        payload["database"] = database
    # SSH tunnel fields — DBGate triggers tunnelling when useSshTunnel is true.
    if ssh_host is not None:
        payload["useSshTunnel"] = True
        payload["sshHost"] = ssh_host
    if ssh_port is not None:
        payload["sshPort"] = ssh_port
    if ssh_user is not None:
        payload["sshLogin"] = ssh_user
    if ssh_mode is not None:
        if ssh_mode not in _SSH_MODES:
            raise typer.BadParameter(f"--ssh-mode must be one of {sorted(_SSH_MODES)}")
        payload["sshMode"] = ssh_mode
    if ssh_password is not None:
        payload["sshPassword"] = ssh_password
    if ssh_keyfile is not None:
        payload["sshKeyfile"] = ssh_keyfile
    if ssh_keyfile_password is not None:
        payload["sshKeyfilePassword"] = ssh_keyfile_password
    return payload


@app.command()
def create(
    ctx: typer.Context,
    label: Annotated[str, typer.Option("--label", help="Display name")],
    engine: Annotated[str, typer.Option("--engine", help="Engine key, e.g. postgres@dbgate-plugin-postgres")],
    server: Annotated[
        str, typer.Option("--server", help="DB server host (from the SSH target's perspective if --ssh-host is set)")
    ],
    port: Annotated[str, typer.Option("--port", help="DB server port")],
    user: Annotated[str, typer.Option("--user", help="DB username")],
    password: Annotated[str, typer.Option("--password", help="DB password")],
    database: Annotated[str | None, typer.Option("--database", help="Default database (optional)")] = None,
    ssh_host: Annotated[str | None, typer.Option("--ssh-host", help="SSH tunnel host")] = None,
    ssh_port: Annotated[str | None, typer.Option("--ssh-port", help="SSH port (default 22)")] = None,
    ssh_user: Annotated[str | None, typer.Option("--ssh-user", help="SSH login user")] = None,
    ssh_mode: Annotated[
        str | None,
        typer.Option("--ssh-mode", help="SSH auth mode: userPassword | agent | keyFile"),
    ] = None,
    ssh_password: Annotated[str | None, typer.Option("--ssh-password", help="SSH password (userPassword mode)")] = None,
    ssh_keyfile: Annotated[
        str | None,
        typer.Option("--ssh-keyfile", help="Path to SSH private key inside the DBGate container (keyFile mode)"),
    ] = None,
    ssh_keyfile_password: Annotated[
        str | None, typer.Option("--ssh-keyfile-password", help="Passphrase for encrypted SSH key")
    ] = None,
) -> None:
    """Create a new database connection.

    Pass `--ssh-host …` (plus `--ssh-mode keyFile --ssh-keyfile …` or
    `--ssh-mode userPassword --ssh-password …`) to route the DB connection
    through an SSH tunnel. `--server`/`--port` are then resolved from the
    SSH target's perspective (commonly `127.0.0.1:5432`).
    """
    actx: AppContext = ctx.obj
    out = actx.output

    payload = _build_payload(
        label,
        engine,
        server,
        port,
        user,
        password,
        database,
        ssh_host=ssh_host,
        ssh_port=ssh_port,
        ssh_user=ssh_user,
        ssh_mode=ssh_mode,
        ssh_password=ssh_password,
        ssh_keyfile=ssh_keyfile,
        ssh_keyfile_password=ssh_keyfile_password,
    )

    try:
        result = actx.client.call("/connections/save", payload)
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    new_id = (result or {}).get("_id", "")
    out.success(f"Connection created: {new_id}")
    out.kv("Label", label)
    out.kv("Engine", engine)
    if ssh_host:
        out.kv("SSH Tunnel", f"{ssh_user or 'root'}@{ssh_host}:{ssh_port or '22'} ({ssh_mode or 'keyFile'})")


@app.command()
def update(
    ctx: typer.Context,
    conid: Annotated[str, typer.Argument(help="Connection ID")],
    label: Annotated[str | None, typer.Option("--label", help="Display name")] = None,
    engine: Annotated[str | None, typer.Option("--engine", help="Engine key")] = None,
    server: Annotated[str | None, typer.Option("--server", help="DB server host")] = None,
    port: Annotated[str | None, typer.Option("--port", help="DB server port")] = None,
    user: Annotated[str | None, typer.Option("--user", help="DB username")] = None,
    password: Annotated[str | None, typer.Option("--password", help="DB password")] = None,
    database: Annotated[str | None, typer.Option("--database", help="Default database")] = None,
) -> None:
    """Update an existing connection (pass only the fields to change).

    DBGate's /connections/update destructures `{_id, values}` and feeds
    `values` into datastore.patch — a flat payload silently patches with
    `undefined` and is a no-op.
    """
    actx: AppContext = ctx.obj
    out = actx.output

    values = _build_payload(label, engine, server, port, user, password, database)
    if not values:
        out.error(
            "No fields to update — pass at least one of --label/--engine/--server/--port/--user/--password/--database"
        )
        raise typer.Exit(1)

    try:
        actx.client.call("/connections/update", {"_id": conid, "values": values})
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    out.success(f"Connection {conid} updated")


@app.command("new-sqlite")
def new_sqlite(
    ctx: typer.Context,
    label: Annotated[str, typer.Option("--label", help="Display name")],
    file: Annotated[str, typer.Option("--file", help="Path to SQLite .db file")],
) -> None:
    """Create a new SQLite-backed connection.

    DBGate's /connections/new-sqlite-database only reads a short `file`
    (used as a NAME, not a path) and drops the sqlite file inside DBGate's
    own app folder — it ignores `displayName`, `databaseFile`, and any
    engine override. We therefore create the connection directly via
    /connections/save so the user-provided path and label are honoured.
    """
    actx: AppContext = ctx.obj
    out = actx.output

    payload = {
        "displayName": label,
        "databaseFile": file,
        "engine": "sqlite@dbgate-plugin-sqlite",
        "singleDatabase": True,
        "defaultDatabase": file.rsplit("/", 1)[-1],
    }
    try:
        result = actx.client.call("/connections/save", payload)
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    out.success(f"SQLite connection created: {(result or {}).get('_id', '')}")


@app.command("new-duckdb")
def new_duckdb(
    ctx: typer.Context,
    label: Annotated[str, typer.Option("--label", help="Display name")],
    file: Annotated[str, typer.Option("--file", help="Path to DuckDB file")],
) -> None:
    """Create a new DuckDB-backed connection.

    See `new-sqlite` for rationale: we use /connections/save directly so
    the user-provided path and label are honoured by DBGate.
    """
    actx: AppContext = ctx.obj
    out = actx.output

    payload = {
        "displayName": label,
        "databaseFile": file,
        "engine": "duckdb@dbgate-plugin-duckdb",
        "singleDatabase": True,
        "defaultDatabase": file.rsplit("/", 1)[-1],
    }
    try:
        result = actx.client.call("/connections/save", payload)
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    out.success(f"DuckDB connection created: {(result or {}).get('_id', '')}")
