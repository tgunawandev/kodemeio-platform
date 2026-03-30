"""Database management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext

app = typer.Typer(help="Manage Odoo databases.")


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Database name to create")],
    lang: Annotated[str, typer.Option("--lang", "-l", help="Default language")] = "en_US",
) -> None:
    """Create a new database."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if c.db_exist(name):
        out.error(f"Database '{name}' already exists")
        raise typer.Exit(1)

    out.info(f"Creating database '{name}' (lang={lang})...")
    c.db_create(name, lang=lang)
    out.success(f"Database '{name}' created")


@app.command()
def drop(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Database name to drop")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation")] = False,
) -> None:
    """Drop a database (irreversible)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not c.db_exist(name):
        out.error(f"Database '{name}' does not exist")
        raise typer.Exit(1)

    if not force and not typer.confirm(f"DROP database '{name}'? This is irreversible."):
        raise typer.Exit(0)

    out.info(f"Dropping database '{name}'...")
    c.db_drop(name)
    out.success(f"Database '{name}' dropped")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List available databases."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    databases = c.db_list()
    current_db = c.database

    rows = []
    json_data = []
    for db in sorted(databases):
        marker = "[green]current[/green]" if db == current_db else ""
        rows.append([db, marker])
        json_data.append({"name": db, "current": db == current_db})

    out.table(
        f"Databases ({len(databases)})",
        [("Name", "cyan"), ("", "green")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def duplicate(
    ctx: typer.Context,
    source: Annotated[str, typer.Argument(help="Source database name")],
    target: Annotated[str, typer.Argument(help="Target database name")],
) -> None:
    """Duplicate a database."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not typer.confirm(f"Duplicate '{source}' -> '{target}'?"):
        raise typer.Exit(0)

    out.info(f"Duplicating '{source}' -> '{target}'...")
    c.db_duplicate(source, target)
    out.success(f"Database '{target}' created from '{source}'")


@app.command()
def rename(
    ctx: typer.Context,
    old_name: Annotated[str, typer.Argument(help="Current database name")],
    new_name: Annotated[str, typer.Argument(help="New database name")],
) -> None:
    """Rename a database."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not typer.confirm(f"Rename database '{old_name}' -> '{new_name}'?"):
        raise typer.Exit(0)

    out.info(f"Renaming '{old_name}' -> '{new_name}'...")
    c.db_rename(old_name, new_name)
    out.success(f"Database renamed: '{old_name}' -> '{new_name}'")


@app.command()
def exists(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Database name to check")],
) -> None:
    """Check if a database exists."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    result = c.db_exist(name)

    if actx.json_mode:
        out.raw_json({"name": name, "exists": bool(result)})
        return

    if result:
        out.success(f"Database '{name}' exists")
    else:
        out.info(f"Database '{name}' does not exist")


@app.command()
def languages(ctx: typer.Context) -> None:
    """List available languages for database creation."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    langs = c.db_list_lang()

    rows = []
    json_data = []
    for lang in langs:
        # lang is typically [code, name] pair
        if isinstance(lang, (list, tuple)) and len(lang) >= 2:
            code, name = lang[0], lang[1]
        else:
            code, name = str(lang), str(lang)
        rows.append([code, name])
        json_data.append({"code": code, "name": name})

    out.table(
        f"Available Languages ({len(langs)})",
        [("Code", "cyan"), ("Language", "")],
        rows,
        data_for_json=json_data,
    )
