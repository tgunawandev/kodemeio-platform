"""Database service management commands (Dokploy managed DBs)."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

DB_TYPES = ("postgres", "redis", "mysql", "mariadb", "mongo")

app = typer.Typer(help="Manage Dokploy database services.")


def _id_field(db_type: str) -> str:
    """Return the ID field name for a given DB type."""
    return f"{db_type}Id"


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all database services across all projects."""
    c: AppContext = ctx.obj
    projects = c.client.get("/project.all")
    if not isinstance(projects, list):
        projects = []
    rows = []
    json_data = []
    for p in projects:
        project_name = p.get("name", "")
        for env in p.get("environments", [p]):
            for db_type in DB_TYPES:
                for db in env.get(db_type, []):
                    db_id = db.get(_id_field(db_type), "")[:12]
                    name = db.get("name", "")
                    status = db.get(f"{db_type}Status", db.get("status", "unknown"))
                    version = db.get("databaseVersion", db.get("version", "-"))
                    rows.append([db_id, name, db_type, str(version), status, project_name])
                    json_data.append(
                        {
                            "id": db.get(_id_field(db_type), ""),
                            "name": name,
                            "type": db_type,
                            "version": str(version),
                            "status": status,
                            "project": project_name,
                        }
                    )
    c.output.table(
        "Database Services",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("Type", ""),
            ("Version", "dim"),
            ("Status", ""),
            ("Project", ""),
        ],
        rows,
        data_for_json=json_data,
    )


@app.command()
def get(
    ctx: typer.Context,
    db_id: Annotated[str, typer.Argument(help="Database service ID")],
    db_type: Annotated[
        str, typer.Option("--type", "-t", help="Database type (postgres, redis, mysql, mariadb, mongo)")
    ],
) -> None:
    """Get database service details."""
    c: AppContext = ctx.obj
    if db_type not in DB_TYPES:
        c.output.error(f"Invalid type '{db_type}'. Must be one of: {', '.join(DB_TYPES)}")
        raise typer.Exit(1)
    id_field = _id_field(db_type)
    data = c.client.get(f"/{db_type}.one", params={id_field: db_id})
    if not isinstance(data, dict):
        c.output.error(f"{db_type} database '{db_id}' not found")
        raise typer.Exit(1)
    name = data.get("name", "unknown")
    sections = [
        (
            f"{db_type.capitalize()} Database",
            [
                ("ID", data.get(id_field, "")),
                ("Name", name),
                ("Status", data.get(f"{db_type}Status", data.get("status", "unknown"))),
                ("Version", str(data.get("databaseVersion", data.get("version", "-")))),
                ("Docker Image", data.get("dockerImage", "-")),
                ("External Port", str(data.get("externalPort", "-"))),
                ("Created", data.get("createdAt", "-")),
            ],
        ),
    ]
    c.output.detail(f"Database: {name}", sections, data_for_json=data)


@app.command("create-postgres")
def create_postgres(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Database name")],
    project_id: Annotated[str, typer.Option("--project", "-p", help="Project ID")],
    version: Annotated[str, typer.Option("--version", "-v", help="PostgreSQL version")] = "16",
    password: Annotated[str | None, typer.Option("--password", help="Database password")] = None,
) -> None:
    """Create a PostgreSQL database service."""
    c: AppContext = ctx.obj
    payload: dict = {
        "name": name,
        "projectId": project_id,
        "databaseVersion": version,
        "dockerImage": f"postgres:{version}",
    }
    if password:
        payload["databasePassword"] = password
    result = c.client.post("/postgres.create", json=payload)
    db_id = result.get("postgresId", "") if isinstance(result, dict) else ""
    c.output.success(f"PostgreSQL '{name}' created: {db_id}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("create-redis")
def create_redis(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Database name")],
    project_id: Annotated[str, typer.Option("--project", "-p", help="Project ID")],
    version: Annotated[str, typer.Option("--version", "-v", help="Redis version")] = "7",
) -> None:
    """Create a Redis database service."""
    c: AppContext = ctx.obj
    payload: dict = {
        "name": name,
        "projectId": project_id,
        "dockerImage": f"redis:{version}",
    }
    result = c.client.post("/redis.create", json=payload)
    db_id = result.get("redisId", "") if isinstance(result, dict) else ""
    c.output.success(f"Redis '{name}' created: {db_id}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("create-mysql")
def create_mysql(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Database name")],
    project_id: Annotated[str, typer.Option("--project", "-p", help="Project ID")],
    version: Annotated[str, typer.Option("--version", "-v", help="MySQL version")] = "8",
    password: Annotated[str | None, typer.Option("--password", help="Database password")] = None,
) -> None:
    """Create a MySQL database service."""
    c: AppContext = ctx.obj
    payload: dict = {
        "name": name,
        "projectId": project_id,
        "databaseVersion": version,
        "dockerImage": f"mysql:{version}",
    }
    if password:
        payload["databasePassword"] = password
    result = c.client.post("/mysql.create", json=payload)
    db_id = result.get("mysqlId", "") if isinstance(result, dict) else ""
    c.output.success(f"MySQL '{name}' created: {db_id}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("create-mariadb")
def create_mariadb(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Database name")],
    project_id: Annotated[str, typer.Option("--project", "-p", help="Project ID")],
    version: Annotated[str, typer.Option("--version", "-v", help="MariaDB version")] = "11",
    password: Annotated[str | None, typer.Option("--password", help="Database password")] = None,
) -> None:
    """Create a MariaDB database service."""
    c: AppContext = ctx.obj
    payload: dict = {
        "name": name,
        "projectId": project_id,
        "databaseVersion": version,
        "dockerImage": f"mariadb:{version}",
    }
    if password:
        payload["databasePassword"] = password
    result = c.client.post("/mariadb.create", json=payload)
    db_id = result.get("mariadbId", "") if isinstance(result, dict) else ""
    c.output.success(f"MariaDB '{name}' created: {db_id}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("create-mongo")
def create_mongo(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Database name")],
    project_id: Annotated[str, typer.Option("--project", "-p", help="Project ID")],
    version: Annotated[str, typer.Option("--version", "-v", help="MongoDB version")] = "7",
    password: Annotated[str | None, typer.Option("--password", help="Database password")] = None,
) -> None:
    """Create a MongoDB database service."""
    c: AppContext = ctx.obj
    payload: dict = {
        "name": name,
        "projectId": project_id,
        "dockerImage": f"mongo:{version}",
    }
    if password:
        payload["databasePassword"] = password
    result = c.client.post("/mongo.create", json=payload)
    db_id = result.get("mongoId", "") if isinstance(result, dict) else ""
    c.output.success(f"MongoDB '{name}' created: {db_id}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def remove(
    ctx: typer.Context,
    db_id: Annotated[str, typer.Argument(help="Database service ID")],
    db_type: Annotated[
        str, typer.Option("--type", "-t", help="Database type (postgres, redis, mysql, mariadb, mongo)")
    ],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Remove a database service (destructive)."""
    c: AppContext = ctx.obj
    if db_type not in DB_TYPES:
        c.output.error(f"Invalid type '{db_type}'. Must be one of: {', '.join(DB_TYPES)}")
        raise typer.Exit(1)
    if not force:
        typer.confirm(f"Remove {db_type} database '{db_id}'? This cannot be undone.", abort=True)
    id_field = _id_field(db_type)
    result = c.client.post(f"/{db_type}.remove", json={id_field: db_id})
    c.output.success(f"{db_type.capitalize()} database '{db_id}' removed")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def deploy(
    ctx: typer.Context,
    db_id: Annotated[str, typer.Argument(help="Database service ID")],
    db_type: Annotated[
        str, typer.Option("--type", "-t", help="Database type (postgres, redis, mysql, mariadb, mongo)")
    ],
) -> None:
    """Deploy/redeploy a database service."""
    c: AppContext = ctx.obj
    if db_type not in DB_TYPES:
        c.output.error(f"Invalid type '{db_type}'. Must be one of: {', '.join(DB_TYPES)}")
        raise typer.Exit(1)
    id_field = _id_field(db_type)
    result = c.client.post(f"/{db_type}.deploy", json={id_field: db_id})
    c.output.success(f"{db_type.capitalize()} database '{db_id}' deployment triggered")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def stop(
    ctx: typer.Context,
    db_id: Annotated[str, typer.Argument(help="Database service ID")],
    db_type: Annotated[
        str, typer.Option("--type", "-t", help="Database type (postgres, redis, mysql, mariadb, mongo)")
    ],
) -> None:
    """Stop a database service."""
    c: AppContext = ctx.obj
    if db_type not in DB_TYPES:
        c.output.error(f"Invalid type '{db_type}'. Must be one of: {', '.join(DB_TYPES)}")
        raise typer.Exit(1)
    id_field = _id_field(db_type)
    result = c.client.post(f"/{db_type}.stop", json={id_field: db_id})
    c.output.success(f"{db_type.capitalize()} database '{db_id}' stopped")
    if c.json_mode:
        c.output.raw_json(result)
