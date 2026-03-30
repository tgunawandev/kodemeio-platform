"""PostgreSQL role/user management commands."""

from __future__ import annotations

import secrets
import string
from typing import Annotated

import typer

from kctl_pg.core.callbacks import AppContext

app = typer.Typer(help="Manage PostgreSQL roles and users.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all roles/users."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    rows_data = c.fetchall("""
        SELECT
            r.rolname AS name,
            r.rolsuper AS superuser,
            r.rolinherit AS inherit,
            r.rolcreaterole AS createrole,
            r.rolcreatedb AS createdb,
            r.rolcanlogin AS login,
            r.rolreplication AS replication,
            r.rolconnlimit AS conn_limit,
            COALESCE(
                (SELECT string_agg(b.rolname, ', ' ORDER BY b.rolname)
                 FROM pg_auth_members m
                 JOIN pg_roles b ON m.roleid = b.oid
                 WHERE m.member = r.oid),
                ''
            ) AS member_of
        FROM pg_roles r
        WHERE r.rolname !~ '^pg_'
        ORDER BY r.rolname
    """)

    def _flags(r: dict) -> str:
        flags = []
        if r["superuser"]:
            flags.append("S")
        if r["login"]:
            flags.append("L")
        if r["createdb"]:
            flags.append("C")
        if r["createrole"]:
            flags.append("R")
        if r["replication"]:
            flags.append("P")
        return "".join(flags)

    rows = [
        [r["name"], _flags(r), r["member_of"] or "-", str(r["conn_limit"]) if r["conn_limit"] >= 0 else "-"]
        for r in rows_data
    ]

    out.table(
        "Roles  (S=super L=login C=createdb R=createrole P=replication)",
        [("Name", "cyan"), ("Flags", ""), ("Member Of", "dim"), ("Conn Limit", "")],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Role name")],
    password: Annotated[str | None, typer.Option("--password", help="Password (auto-generated if omitted)")] = None,
    login: Annotated[bool, typer.Option("--login/--no-login", help="Allow login")] = True,
    createdb: Annotated[bool, typer.Option("--createdb", help="Allow creating databases")] = False,
    superuser: Annotated[bool, typer.Option("--superuser", help="Superuser role")] = False,
) -> None:
    """Create a new role/user."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    exists = c.fetchval("SELECT 1 FROM pg_roles WHERE rolname = %s", (name,))
    if exists:
        out.error(f"Role '{name}' already exists")
        raise typer.Exit(1)

    generated = False
    if password is None:
        password = _generate_password()
        generated = True

    opts = []
    if login:
        opts.append("LOGIN")
    if createdb:
        opts.append("CREATEDB")
    if superuser:
        opts.append("SUPERUSER")

    opts_str = " ".join(opts)
    from psycopg import sql

    c.execute(
        sql.SQL("CREATE ROLE {} {} PASSWORD {}").format(
            sql.Identifier(name),
            sql.SQL(opts_str),
            sql.Literal(password),
        )
    )

    out.success(f"Role '{name}' created")
    if generated:
        out.kv("Generated password", password)
    out.kv("Login", str(login))
    if createdb:
        out.kv("CreateDB", "yes")
    if superuser:
        out.kv("Superuser", "yes")


@app.command()
def drop(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Role name")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Drop a role/user."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    exists = c.fetchval("SELECT 1 FROM pg_roles WHERE rolname = %s", (name,))
    if not exists:
        out.error(f"Role '{name}' does not exist")
        raise typer.Exit(1)

    if name in ("postgres",):
        out.error(f"Cannot drop system role '{name}'")
        raise typer.Exit(1)

    if not force:
        if not typer.confirm(f"Drop role '{name}'? This cannot be undone"):
            raise typer.Exit(0)

    c.execute(f"DROP ROLE {_quote_ident(name)}")
    out.success(f"Role '{name}' dropped")


@app.command()
def password(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Role name")],
    new_password: Annotated[
        str | None, typer.Option("--password", help="New password (auto-generated if omitted)")
    ] = None,
) -> None:
    """Set or reset a role's password."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    exists = c.fetchval("SELECT 1 FROM pg_roles WHERE rolname = %s", (name,))
    if not exists:
        out.error(f"Role '{name}' does not exist")
        raise typer.Exit(1)

    generated = False
    if new_password is None:
        new_password = _generate_password()
        generated = True

    from psycopg import sql

    c.execute(
        sql.SQL("ALTER ROLE {} PASSWORD {}").format(
            sql.Identifier(name),
            sql.Literal(new_password),
        )
    )
    out.success(f"Password updated for '{name}'")
    if generated:
        out.kv("Generated password", new_password)


@app.command()
def get(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Role name")],
) -> None:
    """Show detailed role info."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    role = c.fetchone(
        """
        SELECT
            r.rolname AS name,
            r.rolsuper AS superuser,
            r.rolinherit AS inherit,
            r.rolcreaterole AS createrole,
            r.rolcreatedb AS createdb,
            r.rolcanlogin AS login,
            r.rolreplication AS replication,
            r.rolconnlimit AS conn_limit,
            r.rolvaliduntil AS valid_until
        FROM pg_roles r
        WHERE r.rolname = %s
    """,
        (name,),
    )

    if not role:
        out.error(f"Role '{name}' not found")
        raise typer.Exit(1)

    # Get group memberships
    memberships = c.fetchall(
        """
        SELECT b.rolname
        FROM pg_auth_members m
        JOIN pg_roles b ON m.roleid = b.oid
        WHERE m.member = (SELECT oid FROM pg_roles WHERE rolname = %s)
        ORDER BY b.rolname
    """,
        (name,),
    )

    # Get owned databases
    owned_dbs = c.fetchall(
        """
        SELECT datname FROM pg_database
        WHERE datdba = (SELECT oid FROM pg_roles WHERE rolname = %s)
        ORDER BY datname
    """,
        (name,),
    )

    sections = [
        (
            "Role",
            [
                ("Name", role["name"]),
                ("Superuser", str(role["superuser"])),
                ("Login", str(role["login"])),
                ("CreateDB", str(role["createdb"])),
                ("CreateRole", str(role["createrole"])),
                ("Replication", str(role["replication"])),
                ("Inherit", str(role["inherit"])),
                ("Conn Limit", str(role["conn_limit"]) if role["conn_limit"] >= 0 else "unlimited"),
                ("Valid Until", str(role["valid_until"]) if role["valid_until"] else "no expiry"),
            ],
        ),
        ("Memberships", [(m["rolname"], "") for m in memberships] or [("(none)", "")]),
        ("Owned Databases", [(d["datname"], "") for d in owned_dbs] or [("(none)", "")]),
    ]

    out.detail(
        f"Role: {name}",
        sections,
        data_for_json={
            **role,
            "member_of": [m["rolname"] for m in memberships],
            "owned_databases": [d["datname"] for d in owned_dbs],
        },
    )


@app.command()
def grant(
    ctx: typer.Context,
    role: Annotated[str, typer.Argument(help="Role to grant")],
    to: Annotated[str, typer.Option("--to", help="Target role to receive the grant")],
) -> None:
    """Grant a role to another role."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    c.execute(f"GRANT {_quote_ident(role)} TO {_quote_ident(to)}")
    out.success(f"Granted '{role}' to '{to}'")


@app.command()
def revoke(
    ctx: typer.Context,
    role: Annotated[str, typer.Argument(help="Role to revoke")],
    from_: Annotated[str, typer.Option("--from", help="Target role to revoke from")],
) -> None:
    """Revoke a role from another role."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    c.execute(f"REVOKE {_quote_ident(role)} FROM {_quote_ident(from_)}")
    out.success(f"Revoked '{role}' from '{from_}'")


@app.command()
def alter(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Role name")],
    set_param: Annotated[str, typer.Option("--set", help="Configuration parameter name")],
    value: Annotated[str, typer.Argument(help="Parameter value")],
) -> None:
    """Set a configuration parameter for a role."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    exists = c.fetchval("SELECT 1 FROM pg_roles WHERE rolname = %s", (name,))
    if not exists:
        out.error(f"Role '{name}' does not exist")
        raise typer.Exit(1)

    # Validate parameter exists
    param_exists = c.fetchval("SELECT 1 FROM pg_settings WHERE name = %s", (set_param,))
    if not param_exists:
        out.error(f"Unknown configuration parameter '{set_param}'")
        raise typer.Exit(1)

    c.execute(f"ALTER ROLE {_quote_ident(name)} SET {_quote_ident(set_param)} = %s", (value,))
    out.success(f"Set '{set_param}' = '{value}' for role '{name}'")


@app.command("grant-db")
def grant_db(
    ctx: typer.Context,
    role: Annotated[str, typer.Argument(help="Role to grant privileges to")],
    database: Annotated[str, typer.Argument(help="Database name")],
    privileges: Annotated[
        str, typer.Option("--privileges", "-p", help="Comma-separated: connect,create,temp,all")
    ] = "connect",
) -> None:
    """Grant privileges on a database to a role."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Validate database exists
    exists = c.fetchval("SELECT 1 FROM pg_database WHERE datname = %s", (database,))
    if not exists:
        out.error(f"Database '{database}' does not exist")
        raise typer.Exit(1)

    # Validate role exists
    role_exists = c.fetchval("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
    if not role_exists:
        out.error(f"Role '{role}' does not exist")
        raise typer.Exit(1)

    valid_privs = {"connect", "create", "temp", "temporary", "all"}
    priv_list = [p.strip().upper() for p in privileges.split(",")]
    for p in priv_list:
        if p.lower() not in valid_privs and p.lower() != "all privileges":
            out.error(f"Invalid privilege '{p}'. Valid: connect, create, temp, all")
            raise typer.Exit(1)

    priv_str = ", ".join(priv_list)
    c.execute(f"GRANT {priv_str} ON DATABASE {_quote_ident(database)} TO {_quote_ident(role)}")
    out.success(f"Granted {priv_str} on database '{database}' to '{role}'")


@app.command("grant-schema")
def grant_schema(
    ctx: typer.Context,
    role: Annotated[str, typer.Argument(help="Role to grant privileges to")],
    schema: Annotated[str, typer.Argument(help="Schema name")],
    database: Annotated[str, typer.Option("--db", "-d", help="Target database")] = "postgres",
    privileges: Annotated[str, typer.Option("--privileges", "-p", help="Comma-separated: usage,create,all")] = "usage",
) -> None:
    """Grant privileges on a schema to a role."""
    actx: AppContext = ctx.obj
    out = actx.output

    c = actx.get_client(database=database)
    try:
        # Validate schema exists
        exists = c.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = %s", (schema,))
        if not exists:
            out.error(f"Schema '{schema}' does not exist in '{database}'")
            raise typer.Exit(1)

        valid_privs = {"usage", "create", "all"}
        priv_list = [p.strip().upper() for p in privileges.split(",")]
        for p in priv_list:
            if p.lower() not in valid_privs and p.lower() != "all privileges":
                out.error(f"Invalid privilege '{p}'. Valid: usage, create, all")
                raise typer.Exit(1)

        priv_str = ", ".join(priv_list)
        c.execute(f"GRANT {priv_str} ON SCHEMA {_quote_ident(schema)} TO {_quote_ident(role)}")
        out.success(f"Granted {priv_str} on schema '{schema}' to '{role}' in '{database}'")
    finally:
        c.close()


@app.command("grant-table")
def grant_table(
    ctx: typer.Context,
    role: Annotated[str, typer.Argument(help="Role to grant privileges to")],
    table: Annotated[str, typer.Argument(help="Table name (or ALL TABLES IN SCHEMA <schema>)")],
    database: Annotated[str, typer.Option("--db", "-d", help="Target database")] = "postgres",
    privileges: Annotated[
        str,
        typer.Option(
            "--privileges", "-p", help="Comma-separated: select,insert,update,delete,truncate,references,trigger,all"
        ),
    ] = "select",
) -> None:
    """Grant privileges on a table to a role."""
    actx: AppContext = ctx.obj
    out = actx.output

    c = actx.get_client(database=database)
    try:
        valid_privs = {"select", "insert", "update", "delete", "truncate", "references", "trigger", "all"}
        priv_list = [p.strip().upper() for p in privileges.split(",")]
        for p in priv_list:
            if p.lower() not in valid_privs and p.lower() != "all privileges":
                out.error(
                    f"Invalid privilege '{p}'. Valid: select, insert, update, delete, truncate, references, trigger, all"
                )
                raise typer.Exit(1)

        priv_str = ", ".join(priv_list)

        # Support "ALL TABLES IN SCHEMA <schema>" syntax
        if table.upper().startswith("ALL TABLES IN SCHEMA "):
            schema_name = table.split()[-1]
            c.execute(f"GRANT {priv_str} ON ALL TABLES IN SCHEMA {_quote_ident(schema_name)} TO {_quote_ident(role)}")
            out.success(f"Granted {priv_str} on all tables in schema '{schema_name}' to '{role}' in '{database}'")
        else:
            c.execute(f"GRANT {priv_str} ON TABLE {_quote_ident(table)} TO {_quote_ident(role)}")
            out.success(f"Granted {priv_str} on table '{table}' to '{role}' in '{database}'")
    finally:
        c.close()


@app.command("default-privileges")
def default_privileges(
    ctx: typer.Context,
    role: Annotated[str, typer.Argument(help="Role whose created objects get defaults")],
    grant_to: Annotated[str, typer.Option("--grant-to", help="Target role to receive default privileges")],
    privileges: Annotated[
        str, typer.Option("--privileges", "-p", help="Comma-separated: select,insert,update,delete,all")
    ] = "select",
    database: Annotated[str, typer.Option("--db", "-d", help="Target database")] = "postgres",
    schema: Annotated[str | None, typer.Option("--schema", "-s", help="Limit to a specific schema")] = None,
) -> None:
    """Set default privileges for tables created by a role."""
    actx: AppContext = ctx.obj
    out = actx.output

    c = actx.get_client(database=database)
    try:
        valid_privs = {"select", "insert", "update", "delete", "truncate", "references", "trigger", "all"}
        priv_list = [p.strip().upper() for p in privileges.split(",")]
        for p in priv_list:
            if p.lower() not in valid_privs and p.lower() != "all privileges":
                out.error(
                    f"Invalid privilege '{p}'. Valid: select, insert, update, delete, truncate, references, trigger, all"
                )
                raise typer.Exit(1)

        priv_str = ", ".join(priv_list)

        schema_clause = f" IN SCHEMA {_quote_ident(schema)}" if schema else ""
        sql = (
            f"ALTER DEFAULT PRIVILEGES FOR ROLE {_quote_ident(role)}{schema_clause} "
            f"GRANT {priv_str} ON TABLES TO {_quote_ident(grant_to)}"
        )
        c.execute(sql)

        scope = f"schema '{schema}'" if schema else f"database '{database}'"
        out.success(f"Default privileges set: {priv_str} on tables by '{role}' -> '{grant_to}' in {scope}")
    finally:
        c.close()


def _quote_ident(name: str) -> str:
    """Quote a SQL identifier safely."""
    return '"' + name.replace('"', '""') + '"'


def _generate_password(length: int = 24) -> str:
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
