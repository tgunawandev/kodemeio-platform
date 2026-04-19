"""Code generation commands for Odoo module scaffolding."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

app = typer.Typer(help="Generate Odoo module boilerplate (scaffold).")
console = Console()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_default_dest() -> Path:
    """Resolve default private module directory from any subfolder."""
    from kctl_odoo.core.utils import find_project_root

    return find_project_root() / "src" / "private"


def _to_snake(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _ensure_dir(path: Path) -> None:
    """Create directory if it does not exist."""
    path.mkdir(parents=True, exist_ok=True)


def _write_file(path: Path, content: str, *, overwrite: bool = False) -> bool:
    """Write *content* to *path*.  Return True if written, False if skipped."""
    if path.exists() and not overwrite:
        console.print(f"[yellow]SKIP[/yellow] {path} (already exists)")
        return False
    path.write_text(content, encoding="utf-8")
    console.print(f"[green]CREATE[/green] {path}")
    return True


def _append_init_import(init_path: Path, module_name: str) -> None:
    """Append ``from . import <module_name>`` to an ``__init__.py`` if not already present."""
    line = f"from . import {module_name}"
    if init_path.exists():
        text = init_path.read_text(encoding="utf-8")
        if line in text:
            return
        if not text.endswith("\n"):
            text += "\n"
        text += line + "\n"
        init_path.write_text(text, encoding="utf-8")
    else:
        init_path.write_text(line + "\n", encoding="utf-8")
    console.print(f"[blue]UPDATE[/blue] {init_path}")


def _append_csv_row(csv_path: Path, row: str) -> None:
    """Append a row to a CSV file, creating it with header if needed."""
    header = "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink"
    if csv_path.exists():
        text = csv_path.read_text(encoding="utf-8")
        if row in text:
            return
        if not text.endswith("\n"):
            text += "\n"
        text += row + "\n"
        csv_path.write_text(text, encoding="utf-8")
    else:
        csv_path.write_text(header + "\n" + row + "\n", encoding="utf-8")
    console.print(f"[blue]UPDATE[/blue] {csv_path}")


def _resolve_module_dir(module_dir: str) -> Path:
    """Resolve a module directory argument to an absolute path."""
    p = Path(module_dir)
    if not p.is_absolute():
        p = _get_default_dest() / p
    if not p.is_dir():
        console.print(f"[red]ERROR[/red] Module directory not found: {p}")
        raise typer.Exit(1)
    return p


def _parse_fields(fields_str: str) -> list[dict[str, str]]:
    """Parse ``name:Char,amount:Float,partner_id:Many2one(res.partner)`` into dicts."""
    result: list[dict[str, str]] = []
    for part in fields_str.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            console.print(f"[yellow]WARN[/yellow] Skipping malformed field spec: {part}")
            continue
        fname, ftype_raw = part.split(":", 1)
        # Extract comodel from e.g. Many2one(res.partner)
        m = re.match(r"(\w+)\(([^)]+)\)", ftype_raw)
        if m:
            ftype, comodel = m.group(1), m.group(2)
        else:
            ftype, comodel = ftype_raw.strip(), ""
        result.append({"name": fname.strip(), "type": ftype, "comodel": comodel})
    return result


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

_TPL_MANIFEST = """\
{{
    "name": "{display_name}",
    "version": "{version}",
    "category": "{category}",
    "summary": "{display_name}",
    "author": "{author}",
    "website": "https://kodeme.io",
    "license": "OPL-1",
    "depends": [{depends}],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": False,
}}
"""

_TPL_INIT_MODELS = """\
from . import models
"""

_TPL_INIT_MODELS_SERVICES = """\
from . import models
from . import services
"""

_TPL_TEST_BASIC = """\
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "{module}")
class Test{class_name}(TransactionCase):
    \"\"\"Basic tests for {module}.\"\"\"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_module_installed(self):
        \"\"\"Test that the module is installed.\"\"\"
        module = self.env["ir.module.module"].search(
            [("name", "=", "{module}")], limit=1,
        )
        self.assertEqual(module.state, "installed")
"""

_TPL_CLAUDE_MD = """\
# CLAUDE.md - {module}

## Overview

{display_name} module for Odoo 18.

## Models

(list models here)

## Security

- `security/ir.model.access.csv` -- access control
"""

_TPL_MODEL = """\
from odoo import fields, models


class {class_name}(models.Model):
    _name = "{model_name}"
    _description = "{description}"

{fields_block}
"""

_TPL_MODEL_INHERIT = """\
from odoo import fields, models


class {class_name}(models.Model):
    _inherit = "{inherit}"

{fields_block}
"""

_TPL_VIEWS = """\
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- List View -->
    <record id="{xml_id}_list" model="ir.ui.view">
        <field name="name">{model_name}.list</field>
        <field name="model">{model_name}</field>
        <field name="arch" type="xml">
            <list string="{description}">
{list_fields}
            </list>
        </field>
    </record>

    <!-- Form View -->
    <record id="{xml_id}_form" model="ir.ui.view">
        <field name="name">{model_name}.form</field>
        <field name="model">{model_name}</field>
        <field name="arch" type="xml">
            <form string="{description}">
                <sheet>
                    <group>
{form_fields}
                    </group>
                </sheet>
            </form>
        </field>
    </record>

    <!-- Action -->
    <record id="action_{xml_id}" model="ir.actions.act_window">
        <field name="name">{description}</field>
        <field name="res_model">{model_name}</field>
        <field name="view_mode">list,form</field>
    </record>
</odoo>
"""

_TPL_ROUTER = """\
# Copyright 2026 Kodemeio
# License OPL-1

\"\"\"FastAPI router for {name}.\"\"\"

from __future__ import annotations

from fastapi import APIRouter, Query, status, HTTPException

from ..schemas.{name}_schemas import {schema_class}ListResponse, {schema_class}Response
from .dependencies import (
    {error_code_class},
    authenticated_env,
    raise_api_error,
)
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError

{name}_router = APIRouter(prefix="/{prefix}", tags=["{tag}"])


@{name}_router.get("/", response_model={schema_class}ListResponse)
def list_{name}s(
    env: authenticated_env,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    \"\"\"List {name} records.\"\"\"
    domain = []
    records = env["{odoo_model}"].search(domain, limit=limit, offset=offset, order="id desc")
    total = env["{odoo_model}"].search_count(domain)

    return {{
        "success": True,
        "data": [
            {{
                "id": r.id,
                "name": r.name or "",
            }}
            for r in records
        ],
        "total": total,
    }}


@{name}_router.get("/{{record_id}}", response_model={schema_class}Response)
def get_{name}(record_id: int, env: authenticated_env) -> dict:
    \"\"\"Get a single {name} by ID.\"\"\"
    record = env["{odoo_model}"].browse(record_id).exists()
    if not record:
        raise_api_error({error_code_class}.NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)

    return {{
        "success": True,
        "data": {{
            "id": record.id,
            "name": record.name or "",
        }},
    }}
"""

_TPL_ROUTER_CRUD = """\
# Copyright 2026 Kodemeio
# License OPL-1

\"\"\"FastAPI CRUD router for {name}.\"\"\"

from __future__ import annotations

from fastapi import APIRouter, Query, status, HTTPException

from ..schemas.{name}_schemas import (
    {schema_class}ListResponse,
    {schema_class}Response,
    {schema_class}MessageResponse,
    {schema_class}CreateRequest,
)
from .dependencies import (
    {error_code_class},
    authenticated_env,
    raise_api_error,
)
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError

{name}_router = APIRouter(prefix="/{prefix}", tags=["{tag}"])


def _serialize(record) -> dict:
    \"\"\"Serialize a {name} record to dict.\"\"\"
    return {{
        "id": record.id,
        "name": record.name or "",
    }}


@{name}_router.get("/", response_model={schema_class}ListResponse)
def list_{name}s(
    env: authenticated_env,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    \"\"\"List {name} records.\"\"\"
    domain = []
    records = env["{odoo_model}"].search(domain, limit=limit, offset=offset, order="id desc")
    total = env["{odoo_model}"].search_count(domain)

    return {{
        "success": True,
        "data": [_serialize(r) for r in records],
        "total": total,
    }}


@{name}_router.get("/{{record_id}}", response_model={schema_class}Response)
def get_{name}(record_id: int, env: authenticated_env) -> dict:
    \"\"\"Get a single {name} by ID.\"\"\"
    record = env["{odoo_model}"].browse(record_id).exists()
    if not record:
        raise_api_error({error_code_class}.NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)

    return {{"success": True, "data": _serialize(record)}}


@{name}_router.post("/", response_model={schema_class}MessageResponse)
def create_{name}(body: {schema_class}CreateRequest, env: authenticated_env) -> dict:
    \"\"\"Create a new {name}.\"\"\"
    record = env["{odoo_model}"].create({{"name": body.name}})
    return {{"success": True, "data": _serialize(record), "message": "Created"}}


@{name}_router.delete("/{{record_id}}")
def delete_{name}(record_id: int, env: authenticated_env) -> dict:
    \"\"\"Delete a {name}.\"\"\"
    record = env["{odoo_model}"].browse(record_id).exists()
    if not record:
        raise_api_error({error_code_class}.NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
    record.unlink()
    return {{"success": True, "message": "Deleted"}}
"""

_TPL_SCHEMA = """\
# Copyright 2026 Kodemeio
# License OPL-1

\"\"\"Pydantic schemas for {name}.\"\"\"

from __future__ import annotations

from pydantic import BaseModel


class {schema_class}Item(BaseModel):
    \"\"\"Single {name} item.\"\"\"

    id: int
    name: str = ""


class {schema_class}ListResponse(BaseModel):
    \"\"\"List response envelope.\"\"\"

    success: bool = True
    data: list[{schema_class}Item] = []
    total: int = 0


class {schema_class}Response(BaseModel):
    \"\"\"Detail response envelope.\"\"\"

    success: bool = True
    data: {schema_class}Item


class {schema_class}MessageResponse(BaseModel):
    \"\"\"Mutation response envelope.\"\"\"

    success: bool = True
    data: {schema_class}Item
    message: str = ""


class {schema_class}CreateRequest(BaseModel):
    \"\"\"Create request body.\"\"\"

    name: str
"""

_TPL_DEPENDENCIES = """\
# Copyright 2026 Kodemeio
# License OPL-1

\"\"\"
Shared dependencies for {module_display} FastAPI routers.

Uses the base_management factory to create all standard dependencies:
- JWT authentication
- Rate limiting
- Error handling
- OIDC integration
- API logging
\"\"\"

from __future__ import annotations

from odoo.addons.base_management.services.app_dependencies import (
    create_app_dependencies,
)
from odoo.addons.base_management.services.errors import BaseErrorCode


class {error_code_class}(BaseErrorCode):
    \"\"\"Error codes for {module_display} API.\"\"\"

    ACCESS_DENIED = "{error_prefix}_ACCESS_DENIED"
    NOT_FOUND = "{error_prefix}_NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"


ERROR_MESSAGES = {{
    {error_code_class}.AUTH_REQUIRED: "Please log in to continue",
    {error_code_class}.AUTH_INVALID: "Your session has expired. Please log in again",
    {error_code_class}.TOKEN_EXPIRED: "Token has expired. Please log in again",
    {error_code_class}.TOKEN_INVALID: "Invalid token",
    {error_code_class}.ACCESS_DENIED: "{module_display} access is not enabled for your account",
    {error_code_class}.NOT_FOUND: "Record not found",
    {error_code_class}.RATE_LIMITED: "Too many requests. Please wait a moment",
    {error_code_class}.INTERNAL_ERROR: "An error occurred. Please try again later",
    {error_code_class}.VALIDATION_ERROR: "Validation error",
}}

_deps = create_app_dependencies(
    app_prefix="{app_prefix}",
    app_id="{app_id}",
    error_code_class={error_code_class},
    error_messages=ERROR_MESSAGES,
    access_group="base.group_user",
)

# Re-export all standard dependencies for use by routers
get_authenticated_env = _deps.get_authenticated_env
authenticated_env = _deps.authenticated_env
raise_api_error = _deps.raise_api_error
create_access_token = _deps.create_access_token
decode_token = _deps.decode_token
get_oidc_config = _deps.get_oidc_config
exchange_oidc_code = _deps.exchange_oidc_code
find_odoo_user_by_oidc = _deps.find_odoo_user_by_oidc
check_login_rate_limit = _deps.check_login_rate_limit
log_api_request = _deps.log_api_request
log_api_error = _deps.log_api_error
log_login_attempt = _deps.log_login_attempt
logout_token = _deps.logout_token
"""

_TPL_TEST_MODEL = """\
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "{module}")
class Test{class_name}(TransactionCase):
    \"\"\"Tests for {model_name}.\"\"\"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Model = cls.env["{model_name}"]

    def test_create(self):
        \"\"\"Test basic record creation.\"\"\"
        record = self.Model.create({{"name": "Test"}})
        self.assertTrue(record.id)
        self.assertEqual(record.name, "Test")
"""

_TPL_TEST_ROUTER = """\
# Copyright 2026 Kodemeio
# License OPL-1

\"\"\"FastAPI integration tests for {name} router.\"\"\"

from odoo.addons.fastapi.context import odoo_env_ctx
from odoo.addons.fastapi.tests.common import FastAPITransactionCase
from odoo.tests import tagged

from ..services.{name}_router import {name}_router
from ..services.dependencies import get_authenticated_env


def _mock_authenticated_env():
    \"\"\"Return the Odoo env already set by _create_test_client via odoo_env_ctx.\"\"\"
    return odoo_env_ctx.get()


@tagged("post_install", "-at_install", "{module}")
class TestApi{class_name}(FastAPITransactionCase):
    \"\"\"FastAPI integration tests for {name} endpoints.\"\"\"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.default_fastapi_router = {name}_router
        cls.default_fastapi_dependency_overrides = {{
            get_authenticated_env: _mock_authenticated_env,
        }}

    def test_list(self):
        \"\"\"Test list endpoint returns success envelope.\"\"\"
        with self._create_test_client() as client:
            resp = client.get("/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertIn("data", data)
        self.assertIn("total", data)
"""


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("module")
def generate_module(
    name: Annotated[str, typer.Argument(help="Module technical name (snake_case)")],
    dest: Annotated[
        str | None,
        typer.Option("--dest", "-d", help="Destination parent directory"),
    ] = None,
    depends: Annotated[str, typer.Option("--depends", help="Comma-separated dependencies")] = "base",
    author: Annotated[str, typer.Option("--author", help="Module author")] = "Kodemeio",
    category: Annotated[str, typer.Option("--category", help="Module category")] = "Uncategorized",
    fastapi: Annotated[bool, typer.Option("--fastapi", help="Add FastAPI services scaffolding")] = False,
    version: Annotated[str, typer.Option("--version", help="Module version")] = "18.0.1.0.0",
) -> None:
    """Create a new Odoo 18 module with standard directory structure."""
    dest_path = Path(dest) if dest else _get_default_dest()
    if not dest_path.is_dir():
        console.print(f"[red]ERROR[/red] Destination directory not found: {dest_path}")
        raise typer.Exit(1)

    mod_dir = dest_path / name
    if mod_dir.exists():
        console.print(f"[red]ERROR[/red] Module directory already exists: {mod_dir}")
        raise typer.Exit(1)

    display_name = name.replace("_", " ").title()
    class_name = name.replace("_", " ").title().replace(" ", "")
    depends_str = ", ".join(f'"{d.strip()}"' for d in depends.split(",") if d.strip())

    console.print(f"\n[bold]Scaffolding module[/bold] [cyan]{name}[/cyan] in {mod_dir}\n")

    # Create directories
    for subdir in ["models", "views", "security", "data", "tests"]:
        _ensure_dir(mod_dir / subdir)
    if fastapi:
        for subdir in ["services", "schemas"]:
            _ensure_dir(mod_dir / subdir)

    # __manifest__.py
    _write_file(
        mod_dir / "__manifest__.py",
        _TPL_MANIFEST.format(
            display_name=display_name,
            version=version,
            category=category,
            author=author,
            depends=depends_str,
        ),
    )

    # __init__.py (root)
    init_content = _TPL_INIT_MODELS_SERVICES if fastapi else _TPL_INIT_MODELS
    _write_file(mod_dir / "__init__.py", init_content)

    # models/__init__.py (empty -- models added via `generate model`)
    _write_file(mod_dir / "models" / "__init__.py", "")

    # security/ir.model.access.csv (header only)
    _write_file(
        mod_dir / "security" / "ir.model.access.csv",
        "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\n",
    )

    # tests/__init__.py
    _write_file(mod_dir / "tests" / "__init__.py", "")

    # tests/test_<name>.py
    _write_file(
        mod_dir / "tests" / f"test_{name}.py",
        _TPL_TEST_BASIC.format(module=name, class_name=class_name),
    )

    # CLAUDE.md
    _write_file(
        mod_dir / "CLAUDE.md",
        _TPL_CLAUDE_MD.format(module=name, display_name=display_name),
    )

    # FastAPI scaffolding with proper base_management factory pattern
    if fastapi:
        app_prefix = class_name
        app_id = name.removesuffix("_management")
        error_prefix = app_id.upper()
        error_code_class = f"{class_name}ErrorCode"

        _write_file(mod_dir / "services" / "__init__.py", "")
        _write_file(
            mod_dir / "services" / "dependencies.py",
            _TPL_DEPENDENCIES.format(
                module_display=display_name,
                error_code_class=error_code_class,
                error_prefix=error_prefix,
                app_prefix=app_prefix,
                app_id=app_id,
            ),
        )
        _write_file(mod_dir / "schemas" / "__init__.py", "")

    console.print(f"\n[green]Module [bold]{name}[/bold] created successfully.[/green]")
    console.print("Next steps:")
    console.print(f"  kctl-odoo generate model {name} MyModel --fields 'name:Char'")
    if fastapi:
        console.print(f"  kctl-odoo generate router {name} my_entity --crud")


@app.command("model")
def generate_model(
    module_dir: Annotated[str, typer.Argument(help="Module directory name or path")],
    model_name: Annotated[str, typer.Argument(help="Model class name in CamelCase (e.g. SaleOrder)")],
    inherit: Annotated[
        str | None,
        typer.Option("--inherit", "-i", help="Existing model to inherit (e.g. res.partner)"),
    ] = None,
    fields: Annotated[
        str | None,
        typer.Option(
            "--fields", "-f", help="Field definitions: 'name:Char,amount:Float,partner_id:Many2one(res.partner)'"
        ),
    ] = None,
) -> None:
    """Add a model to an existing module."""
    mod_path = _resolve_module_dir(module_dir)
    module = mod_path.name
    snake = _to_snake(model_name)
    dotted = inherit if inherit else f"{module}.{snake}"
    description = model_name.replace("_", " ")
    # Insert a space before each uppercase letter for CamelCase
    description = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", description)

    console.print(f"\n[bold]Adding model[/bold] [cyan]{model_name}[/cyan] to {mod_path}\n")

    # Build fields block
    field_lines: list[str] = []
    parsed_fields = _parse_fields(fields) if fields else []
    if not parsed_fields and not inherit:
        # Default: add a name field
        parsed_fields = [{"name": "name", "type": "Char", "comodel": ""}]

    for f in parsed_fields:
        if f["comodel"] and f["type"] == "One2many":
            field_lines.append(f'    {f["name"]} = fields.One2many("{f["comodel"]}", "FIXME_inverse_field_name")')
        elif f["comodel"] and f["type"] == "Many2many":
            field_lines.append(f'    {f["name"]} = fields.Many2many("{f["comodel"]}")')
        elif f["comodel"]:
            field_lines.append(f'    {f["name"]} = fields.{f["type"]}("{f["comodel"]}", ondelete="restrict")')
        else:
            field_lines.append(f"    {f['name']} = fields.{f['type']}()")

    fields_block = "\n".join(field_lines) if field_lines else "    pass"

    # Write model file
    models_dir = mod_path / "models"
    _ensure_dir(models_dir)
    model_file = models_dir / f"{snake}.py"

    if inherit:
        content = _TPL_MODEL_INHERIT.format(
            class_name=model_name,
            inherit=inherit,
            fields_block=fields_block,
        )
    else:
        content = _TPL_MODEL.format(
            class_name=model_name,
            model_name=dotted,
            description=description,
            fields_block=fields_block,
        )

    _write_file(model_file, content)

    # Update models/__init__.py
    _append_init_import(models_dir / "__init__.py", snake)

    # Add security CSV row (skip for inherited models -- they use the parent's access)
    if not inherit:
        csv_path = mod_path / "security" / "ir.model.access.csv"
        model_xmlid = dotted.replace(".", "_")
        row = f"access_{model_xmlid},access.{dotted},model_{model_xmlid},base.group_user,1,1,1,0"
        _ensure_dir(csv_path.parent)
        _append_csv_row(csv_path, row)

    # Create views XML (only for new models, not inherits)
    if not inherit:
        views_dir = mod_path / "views"
        _ensure_dir(views_dir)
        xml_id = f"view_{snake}"
        list_fields = ""
        form_fields = ""
        for f in parsed_fields:
            list_fields += f'                <field name="{f["name"]}"/>\n'
            form_fields += f'                        <field name="{f["name"]}"/>\n'
        if not list_fields:
            list_fields = '                <field name="name"/>\n'
            form_fields = '                        <field name="name"/>\n'
        # Strip trailing newline from field blocks
        list_fields = list_fields.rstrip("\n")
        form_fields = form_fields.rstrip("\n")

        _write_file(
            views_dir / f"{snake}_views.xml",
            _TPL_VIEWS.format(
                xml_id=xml_id,
                model_name=dotted,
                description=description,
                list_fields=list_fields,
                form_fields=form_fields,
            ),
        )

        # Remind to add view to __manifest__.py data list
        console.print(
            f"\n[yellow]REMINDER[/yellow] Add [bold]'views/{snake}_views.xml'[/bold] to __manifest__.py 'data' list."
        )

    console.print(f"\n[green]Model [bold]{model_name}[/bold] added to {module}.[/green]")


@app.command("router")
def generate_router(
    module_dir: Annotated[str, typer.Argument(help="Module directory name or path")],
    name: Annotated[str, typer.Argument(help="Router name (snake_case, e.g. 'order')")],
    crud: Annotated[bool, typer.Option("--crud", help="Generate full CRUD endpoints")] = False,
) -> None:
    """Add a FastAPI router to an existing module."""
    mod_path = _resolve_module_dir(module_dir)
    module = mod_path.name
    name = name.strip().lower().replace("-", "_")
    schema_class = name.replace("_", " ").title().replace(" ", "")

    # Derive app-specific identifiers from module name
    app_id = module.removesuffix("_management")
    class_name = module.replace("_", " ").title().replace(" ", "")
    error_code_class = f"{class_name}ErrorCode"
    odoo_model = f"{module}.{name}"
    tag = f"{app_id}-{name}"

    console.print(f"\n[bold]Adding router[/bold] [cyan]{name}[/cyan] to {mod_path}\n")

    # services/<name>_router.py
    services_dir = mod_path / "services"
    _ensure_dir(services_dir)
    if not (services_dir / "__init__.py").exists():
        _write_file(services_dir / "__init__.py", "")

    tpl = _TPL_ROUTER_CRUD if crud else _TPL_ROUTER
    _write_file(
        services_dir / f"{name}_router.py",
        tpl.format(
            name=name,
            schema_class=schema_class,
            error_code_class=error_code_class,
            odoo_model=odoo_model,
            prefix=name + "s",
            tag=tag,
        ),
    )

    # schemas/<name>_schemas.py
    schemas_dir = mod_path / "schemas"
    _ensure_dir(schemas_dir)
    if not (schemas_dir / "__init__.py").exists():
        _write_file(schemas_dir / "__init__.py", "")

    _write_file(
        schemas_dir / f"{name}_schemas.py",
        _TPL_SCHEMA.format(name=name, schema_class=schema_class),
    )

    console.print(f"\n[green]Router [bold]{name}[/bold] created in {mod_path.name}.[/green]")


@app.command("test")
def generate_test(
    module_dir: Annotated[str, typer.Argument(help="Module directory name or path")],
    name: Annotated[str, typer.Argument(help="Test name (without test_ prefix)")],
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="Model dotted name to generate model tests for"),
    ] = None,
    router: Annotated[bool, typer.Option("--router", help="Generate FastAPI router test")] = False,
) -> None:
    """Add a test file to an existing module."""
    mod_path = _resolve_module_dir(module_dir)
    module = mod_path.name
    name = name.strip().lower().replace("-", "_")
    class_name = name.replace("_", " ").title().replace(" ", "")

    console.print(f"\n[bold]Adding test[/bold] [cyan]test_{name}[/cyan] to {mod_path}\n")

    tests_dir = mod_path / "tests"
    _ensure_dir(tests_dir)
    if not (tests_dir / "__init__.py").exists():
        _write_file(tests_dir / "__init__.py", "")

    if model:
        content = _TPL_TEST_MODEL.format(
            module=module,
            class_name=class_name,
            model_name=model,
        )
    elif router:
        content = _TPL_TEST_ROUTER.format(
            module=module,
            class_name=class_name,
            name=name,
        )
    else:
        content = _TPL_TEST_BASIC.format(module=module, class_name=class_name)

    _write_file(tests_dir / f"test_{name}.py", content)

    console.print(f"\n[green]Test [bold]test_{name}.py[/bold] created in {module}.[/green]")


@app.command("schema")
def generate_schema(
    module_dir: Annotated[str, typer.Argument(help="Module directory name or path")],
    name: Annotated[str, typer.Argument(help="Schema name (snake_case, e.g. 'order')")],
) -> None:
    """Add a Pydantic schema file to an existing module."""
    mod_path = _resolve_module_dir(module_dir)
    name = name.strip().lower().replace("-", "_")
    schema_class = name.replace("_", " ").title().replace(" ", "")

    console.print(f"\n[bold]Adding schema[/bold] [cyan]{name}[/cyan] to {mod_path}\n")

    schemas_dir = mod_path / "schemas"
    _ensure_dir(schemas_dir)
    if not (schemas_dir / "__init__.py").exists():
        _write_file(schemas_dir / "__init__.py", "")

    _write_file(
        schemas_dir / f"{name}_schemas.py",
        _TPL_SCHEMA.format(name=name, schema_class=schema_class),
    )

    console.print(f"\n[green]Schema [bold]{name}_schemas.py[/bold] created in {mod_path.name}.[/green]")


# ---------------------------------------------------------------------------
# New scaffold commands (SP4)
# ---------------------------------------------------------------------------

_VIEW_TYPES = ["form", "list", "search", "kanban"]

_TPL_VIEW_FORM = """\
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_{model_snake}_form" model="ir.ui.view">
        <field name="name">{model_name}.form</field>
        <field name="model">{model_name}</field>
        <field name="arch" type="xml">
            <form string="{model_label}">
                <sheet>
                    <group>
                        <field name="name"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>
</odoo>
"""

_TPL_VIEW_LIST = """\
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_{model_snake}_list" model="ir.ui.view">
        <field name="name">{model_name}.list</field>
        <field name="model">{model_name}</field>
        <field name="arch" type="xml">
            <list string="{model_label}">
                <field name="name"/>
            </list>
        </field>
    </record>
</odoo>
"""

_TPL_VIEW_SEARCH = """\
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_{model_snake}_search" model="ir.ui.view">
        <field name="name">{model_name}.search</field>
        <field name="model">{model_name}</field>
        <field name="arch" type="xml">
            <search string="{model_label}">
                <field name="name"/>
                <separator/>
                <filter string="Active" name="active" domain="[('active', '=', True)]"/>
            </search>
        </field>
    </record>
</odoo>
"""

_TPL_VIEW_KANBAN = """\
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_{model_snake}_kanban" model="ir.ui.view">
        <field name="name">{model_name}.kanban</field>
        <field name="model">{model_name}</field>
        <field name="arch" type="xml">
            <kanban>
                <field name="name"/>
                <templates>
                    <t t-name="card">
                        <field name="name"/>
                    </t>
                </templates>
            </kanban>
        </field>
    </record>
</odoo>
"""

_TPL_WIZARD_PY = """\
from odoo import fields, models


class {class_name}(models.TransientModel):
    _name = "{model_name}"
    _description = "{description}"

    # Add wizard fields here
    name = fields.Char(required=True)

    def action_confirm(self):
        \"\"\"Execute wizard action.\"\"\"
        self.ensure_one()
        # Implement wizard logic here
        return {{"type": "ir.actions.act_window_close"}}
"""

_TPL_WIZARD_VIEW = """\
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_{name_snake}_wizard_form" model="ir.ui.view">
        <field name="name">{model_name}.wizard.form</field>
        <field name="model">{model_name}</field>
        <field name="arch" type="xml">
            <form string="{description}">
                <group>
                    <field name="name"/>
                </group>
                <footer>
                    <button name="action_confirm" type="object" string="Confirm" class="btn-primary"/>
                    <button string="Cancel" class="btn-secondary" special="cancel"/>
                </footer>
            </form>
        </field>
    </record>

    <record id="action_{name_snake}_wizard" model="ir.actions.act_window">
        <field name="name">{description}</field>
        <field name="res_model">{model_name}</field>
        <field name="view_mode">form</field>
        <field name="target">new</field>
    </record>
</odoo>
"""

_TPL_REPORT_PY = """\
from odoo import fields, models


class {class_name}Report(models.AbstractModel):
    _name = "report.{module}.{name_snake}_report"
    _description = "{description} Report"

    def _get_report_values(self, docids, data=None):
        \"\"\"Provide values for the QWeb template.\"\"\"
        docs = self.env["{model_name}"].browse(docids)
        return {{
            "docs": docs,
            "data": data,
        }}
"""

_TPL_REPORT_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <template id="report_{name_snake}_document">
        <t t-call="web.html_container">
            <t t-foreach="docs" t-as="doc">
                <t t-call="web.external_layout">
                    <div class="page">
                        <h2><t t-esc="doc.name"/></h2>
                        <!-- Report content here -->
                    </div>
                </t>
            </t>
        </t>
    </template>

    <record id="action_report_{name_snake}" model="ir.actions.report">
        <field name="name">{description}</field>
        <field name="model">{model_name}</field>
        <field name="report_type">qweb-pdf</field>
        <field name="report_name">{module}.report_{name_snake}_document</field>
        <field name="report_file">{module}.report_{name_snake}_document</field>
    </record>
</odoo>
"""

_TPL_CONTROLLER = """\
# Copyright 2026 Kodemeio
# License OPL-1

\"\"\"HTTP controller for {description}.\"\"\"

from odoo import http
from odoo.http import request


class {class_name}Controller(http.Controller):

    @http.route("/{module}/{name_snake}", auth="user", type="http")
    def index(self, **kwargs):
        \"\"\"Main controller endpoint.\"\"\"
        return request.render("{module}.{name_snake}_template", {{}})
"""

_TPL_MIGRATION = """\
# Copyright 2026 Kodemeio
# License OPL-1

\"\"\"Migration script for {module} {version}.\"\"\"

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    \"\"\"Run {stage} migration for {module} {version}.

    Args:
        cr: Database cursor
        version: Previous version string
    \"\"\"
    if not version:
        # Fresh install — skip migration
        return

    _logger.info("Running {stage} migration for {module} from %s to {version}", version)

    # Add migration SQL here:
    # cr.execute("ALTER TABLE table_name ADD COLUMN ...")
"""


@app.command("view")
def scaffold_view(
    module_dir: Annotated[str, typer.Argument(help="Module directory name or path")],
    model: Annotated[str, typer.Argument(help="Model dotted name (e.g. sale.order)")],
    view_type: Annotated[str, typer.Option("--type", "-t", help=f"View type: {', '.join(_VIEW_TYPES)}")] = "form",
    overwrite: Annotated[bool, typer.Option("--overwrite", help="Overwrite if file exists")] = False,
) -> None:
    """Generate an XML view file for a model."""
    if view_type not in _VIEW_TYPES:
        console.print(f"[red]ERROR[/red] Invalid view type: {view_type}. Choose from: {', '.join(_VIEW_TYPES)}")
        raise typer.Exit(1)

    mod_path = _resolve_module_dir(module_dir)
    model_snake = model.replace(".", "_")
    model_label = model.replace(".", " ").replace("_", " ").title()

    tpls = {
        "form": _TPL_VIEW_FORM,
        "list": _TPL_VIEW_LIST,
        "search": _TPL_VIEW_SEARCH,
        "kanban": _TPL_VIEW_KANBAN,
    }

    views_dir = mod_path / "views"
    _ensure_dir(views_dir)

    content = tpls[view_type].format(
        model_name=model,
        model_snake=model_snake,
        model_label=model_label,
    )
    file_name = f"{model_snake}_{view_type}_view.xml"
    _write_file(views_dir / file_name, content, overwrite=overwrite)
    console.print(f"\n[green]View [bold]{file_name}[/bold] created.[/green]")
    console.print(f"[yellow]REMINDER[/yellow] Add 'views/{file_name}' to __manifest__.py 'data' list.")


@app.command("wizard")
def scaffold_wizard(
    module_dir: Annotated[str, typer.Argument(help="Module directory name or path")],
    name: Annotated[str, typer.Argument(help="Wizard name in CamelCase (e.g. ImportProducts)")],
    overwrite: Annotated[bool, typer.Option("--overwrite", help="Overwrite if files exist")] = False,
) -> None:
    """Generate a transient model (wizard) with view and action."""
    mod_path = _resolve_module_dir(module_dir)
    module = mod_path.name
    name_snake = _to_snake(name)
    model_name = f"{module}.{name_snake}.wizard"
    description = name.replace("_", " ")
    description = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", description)
    class_name = name if name[0].isupper() else name.title().replace("_", "")

    console.print(f"\n[bold]Scaffolding wizard[/bold] [cyan]{name}[/cyan] in {mod_path}\n")

    # Python model
    wizards_dir = mod_path / "wizards"
    _ensure_dir(wizards_dir)
    if not (wizards_dir / "__init__.py").exists():
        _write_file(wizards_dir / "__init__.py", "")
    _write_file(
        wizards_dir / f"{name_snake}_wizard.py",
        _TPL_WIZARD_PY.format(
            class_name=class_name,
            model_name=model_name,
            description=description,
        ),
        overwrite=overwrite,
    )
    _append_init_import(wizards_dir / "__init__.py", f"{name_snake}_wizard")

    # XML view + action
    views_dir = mod_path / "views"
    _ensure_dir(views_dir)
    _write_file(
        views_dir / f"{name_snake}_wizard_views.xml",
        _TPL_WIZARD_VIEW.format(
            name_snake=name_snake,
            model_name=model_name,
            description=description,
        ),
        overwrite=overwrite,
    )

    console.print(f"\n[green]Wizard [bold]{name}[/bold] created.[/green]")
    console.print("[yellow]REMINDER[/yellow] Add to __manifest__.py:")
    console.print(f"  'data': ['views/{name_snake}_wizard_views.xml']")
    console.print("  Also add 'from . import wizards' to __init__.py if not present.")


@app.command("report")
def scaffold_report(
    module_dir: Annotated[str, typer.Argument(help="Module directory name or path")],
    name: Annotated[str, typer.Argument(help="Report name (e.g. SaleOrderReport or sale_order)")],
    model: Annotated[str, typer.Option("--model", "-m", help="Target model (e.g. sale.order)")] = "",
    overwrite: Annotated[bool, typer.Option("--overwrite", help="Overwrite if files exist")] = False,
) -> None:
    """Generate a QWeb report template with ir.actions.report record."""
    mod_path = _resolve_module_dir(module_dir)
    module = mod_path.name
    name_snake = _to_snake(name) if name[0].isupper() else name
    class_name = "".join(w.title() for w in name_snake.split("_"))
    description = " ".join(w.title() for w in name_snake.split("_"))
    model_name = model or f"{module}.{name_snake}"

    console.print(f"\n[bold]Scaffolding report[/bold] [cyan]{name}[/cyan] in {mod_path}\n")

    # Python abstract model
    reports_dir = mod_path / "reports"
    _ensure_dir(reports_dir)
    if not (reports_dir / "__init__.py").exists():
        _write_file(reports_dir / "__init__.py", "")
    _write_file(
        reports_dir / f"{name_snake}_report.py",
        _TPL_REPORT_PY.format(
            class_name=class_name,
            module=module,
            name_snake=name_snake,
            model_name=model_name,
            description=description,
        ),
        overwrite=overwrite,
    )
    _append_init_import(reports_dir / "__init__.py", f"{name_snake}_report")

    # XML report template + action
    views_dir = mod_path / "views"
    _ensure_dir(views_dir)
    _write_file(
        views_dir / f"{name_snake}_report.xml",
        _TPL_REPORT_XML.format(
            name_snake=name_snake,
            model_name=model_name,
            module=module,
            description=description,
        ),
        overwrite=overwrite,
    )

    console.print(f"\n[green]Report [bold]{name}[/bold] created.[/green]")
    console.print("[yellow]REMINDER[/yellow] Add to __manifest__.py:")
    console.print(f"  'data': ['views/{name_snake}_report.xml']")
    console.print("  Also add 'from . import reports' to __init__.py.")


@app.command("controller")
def scaffold_controller(
    module_dir: Annotated[str, typer.Argument(help="Module directory name or path")],
    name: Annotated[str, typer.Argument(help="Controller name (e.g. Main or portal)")],
    overwrite: Annotated[bool, typer.Option("--overwrite", help="Overwrite if file exists")] = False,
) -> None:
    """Generate an HTTP controller skeleton."""
    mod_path = _resolve_module_dir(module_dir)
    module = mod_path.name
    name_snake = _to_snake(name) if name[0].isupper() else name
    class_name = "".join(w.title() for w in name_snake.split("_"))
    description = " ".join(w.title() for w in name_snake.split("_"))

    console.print(f"\n[bold]Scaffolding controller[/bold] [cyan]{name}[/cyan] in {mod_path}\n")

    controllers_dir = mod_path / "controllers"
    _ensure_dir(controllers_dir)
    if not (controllers_dir / "__init__.py").exists():
        _write_file(controllers_dir / "__init__.py", "")

    _write_file(
        controllers_dir / f"{name_snake}.py",
        _TPL_CONTROLLER.format(
            class_name=class_name,
            module=module,
            name_snake=name_snake,
            description=description,
        ),
        overwrite=overwrite,
    )
    _append_init_import(controllers_dir / "__init__.py", name_snake)

    console.print(f"\n[green]Controller [bold]{name_snake}.py[/bold] created.[/green]")
    console.print(f"[yellow]REMINDER[/yellow] Add 'from . import controllers' to {module}/__init__.py.")


@app.command("security")
def scaffold_security(
    module_dir: Annotated[str, typer.Argument(help="Module directory name or path")],
    group: Annotated[str, typer.Option("--group", "-g", help="Security group XML ID")] = "base.group_user",
    overwrite: Annotated[bool, typer.Option("--overwrite", help="Overwrite existing CSV")] = False,
) -> None:
    """Generate ir.model.access.csv rows for all models declared in the module."""
    import ast

    mod_path = _resolve_module_dir(module_dir)
    module = mod_path.name

    console.print(f"\n[bold]Generating security CSV[/bold] for [cyan]{module}[/cyan]\n")

    # Scan models/*.py for _name declarations
    models_found: list[str] = []
    models_dir = mod_path / "models"
    if models_dir.exists():
        for py_file in sorted(models_dir.glob("*.py")):
            if py_file.name == "__init__.py":
                continue
            try:
                content = py_file.read_text(encoding="utf-8")
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        for item in node.body:
                            if (
                                isinstance(item, ast.Assign)
                                and len(item.targets) == 1
                                and isinstance(item.targets[0], ast.Name)
                                and item.targets[0].id == "_name"
                                and isinstance(item.value, ast.Constant)
                            ):
                                models_found.append(item.value.value)
            except Exception:
                continue

    if not models_found:
        console.print("[yellow]No models with _name found in models/[/yellow]")
        return

    header = "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink"
    rows = [header]
    for model_name in models_found:
        model_xmlid = model_name.replace(".", "_")
        row = f"access_{model_xmlid},access.{model_name},model_{model_xmlid},{group},1,1,1,1"
        rows.append(row)
        console.print(f"  [green]+[/green] {row}")

    csv_path = mod_path / "security" / "ir.model.access.csv"
    _ensure_dir(csv_path.parent)

    if csv_path.exists() and not overwrite:
        # Append missing rows
        existing = csv_path.read_text(encoding="utf-8")
        added = 0
        for row in rows[1:]:  # Skip header
            if row not in existing:
                if not existing.endswith("\n"):
                    existing += "\n"
                existing += row + "\n"
                added += 1
        csv_path.write_text(existing, encoding="utf-8")
        console.print(f"\n[green]Updated ir.model.access.csv — added {added} rows.[/green]")
    else:
        csv_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        console.print(f"\n[green]Created ir.model.access.csv with {len(models_found)} model(s).[/green]")


@app.command("migration")
def scaffold_migration(
    module_dir: Annotated[str, typer.Argument(help="Module directory name or path")],
    version: Annotated[str, typer.Argument(help="Target version (e.g. 18.0.2.0.0)")],
    stage: Annotated[str, typer.Option("--stage", "-s", help="Migration stage: pre or post")] = "post",
    overwrite: Annotated[bool, typer.Option("--overwrite", help="Overwrite if file exists")] = False,
) -> None:
    """Generate a pre/post migration script for a version upgrade."""
    if stage not in ("pre", "post"):
        console.print("[red]ERROR[/red] Stage must be 'pre' or 'post'")
        raise typer.Exit(1)

    mod_path = _resolve_module_dir(module_dir)
    module = mod_path.name

    console.print(f"\n[bold]Scaffolding {stage}-migration[/bold] [cyan]{version}[/cyan] for {module}\n")

    migrations_dir = mod_path / "migrations" / version
    _ensure_dir(migrations_dir)

    # Create __init__.py if needed
    if not (mod_path / "migrations" / "__init__.py").exists():
        _write_file(mod_path / "migrations" / "__init__.py", "")
    if not (migrations_dir / "__init__.py").exists():
        _write_file(migrations_dir / "__init__.py", "")

    script_name = f"{stage}_migration.py"
    _write_file(
        migrations_dir / script_name,
        _TPL_MIGRATION.format(
            module=module,
            version=version,
            stage=stage,
        ),
        overwrite=overwrite,
    )

    console.print(f"\n[green]Migration script created: migrations/{version}/{script_name}[/green]")


@app.command("bridge")
def scaffold_bridge(
    ctx: typer.Context,
    module_a: Annotated[str, typer.Argument(help="First module name (e.g. whatsapp_integration)")],
    module_b: Annotated[str, typer.Argument(help="Second module name (e.g. sale)")],
    dest: Annotated[str | None, typer.Option("--dest", "-d", help="Destination directory")] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite", help="Overwrite existing files")] = False,
) -> None:
    """Generate a bridge module skeleton with auto_install=True.

    Creates src/private/{module_a}_{module_b}/ with:
    - __manifest__.py (depends=[module_a, module_b], auto_install=True)
    - __init__.py
    - models/__init__.py
    - security/ir.model.access.csv (header only)
    """
    bridge_name = f"{module_a}_{module_b}"
    dest_base = Path(dest) if dest else _get_default_dest()
    mod_path = dest_base / bridge_name

    if mod_path.exists() and not overwrite:
        console.print(f"[yellow]Module directory already exists: {mod_path}[/yellow]")
        console.print("Use --overwrite to regenerate files.")
        return

    _ensure_dir(mod_path)
    _ensure_dir(mod_path / "models")
    _ensure_dir(mod_path / "security")

    manifest_content = f'''\
# -*- coding: utf-8 -*-
{{
    "name": "{module_a.replace("_", " ").title()} {module_b.replace("_", " ").title()} Bridge",
    "summary": "Bridge between {module_a} and {module_b}",
    "version": "18.0.1.0.0",
    "category": "Technical",
    "author": "Kodeme.io",
    "website": "https://kodeme.io",
    "license": "OPL-1",
    "depends": [
        "{module_a}",
        "{module_b}",
    ],
    "auto_install": True,
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
}}
'''

    _write_file(mod_path / "__manifest__.py", manifest_content, overwrite=overwrite)
    _write_file(mod_path / "__init__.py", "# -*- coding: utf-8 -*-\nfrom . import models\n", overwrite=overwrite)
    _write_file(mod_path / "models" / "__init__.py", "# -*- coding: utf-8 -*-\n", overwrite=overwrite)

    csv_header = "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\n"
    _write_file(mod_path / "security" / "ir.model.access.csv", csv_header, overwrite=overwrite)

    console.print(f"\n[green]Bridge module created: {mod_path}[/green]")
    console.print("  auto_install: True")
    console.print(f"  depends: [{module_a!r}, {module_b!r}]")


@app.command("crud-api")
def scaffold_crud_api(
    ctx: typer.Context,
    module: Annotated[str, typer.Argument(help="Module technical name (e.g. sfa_management)")],
    model: Annotated[str, typer.Argument(help="Odoo model name (e.g. sfa.visit)")],
    dest: Annotated[str | None, typer.Option("--dest", "-d", help="Destination directory")] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite", help="Overwrite existing files")] = False,
) -> None:
    """Generate FastAPI CRUD router + Pydantic schema + test for a model.

    Creates in src/private/{module}/:
    - controllers/{model_short}_router.py (CRUD endpoints)
    - schemas/{model_short}_schema.py (Pydantic models)
    - tests/test_{model_short}_router.py (basic test)
    """
    dest_base = Path(dest) if dest else _get_default_dest()
    mod_path = dest_base / module

    if not mod_path.exists():
        console.print(f"[red]Module directory not found: {mod_path}[/red]")
        console.print("Create the module first with: kctl-odoo scaffold module <name>")
        raise typer.Exit(1)

    # Parse model: "sfa.visit" -> short="visit", class="Visit"
    parts = model.split(".")
    model_short = parts[-1].replace("-", "_").replace(".", "_")
    model_class = "".join(p.title() for p in model_short.split("_"))
    parts[0].replace("-", "_") if len(parts) > 1 else module.split("_")[0]
    api_prefix = model_short.replace("_", "-")

    controllers_dir = mod_path / "controllers"
    schemas_dir = mod_path / "schemas"
    tests_dir = mod_path / "tests"
    _ensure_dir(controllers_dir)
    _ensure_dir(schemas_dir)
    _ensure_dir(tests_dir)

    # Ensure __init__.py files exist
    if not (controllers_dir / "__init__.py").exists():
        _write_file(controllers_dir / "__init__.py", "# -*- coding: utf-8 -*-\n")
    if not (schemas_dir / "__init__.py").exists():
        _write_file(schemas_dir / "__init__.py", "# -*- coding: utf-8 -*-\n")
    if not (tests_dir / "__init__.py").exists():
        _write_file(tests_dir / "__init__.py", "# -*- coding: utf-8 -*-\n")

    router_content = f'''\
# -*- coding: utf-8 -*-
"""CRUD router for {model}."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from odoo.api import Environment

from ..schemas.{model_short}_schema import (
    {model_class}Create,
    {model_class}Response,
    {model_class}Update,
)

router = APIRouter(prefix="/{api_prefix}", tags=["{model_short}"])


def _get_env() -> Environment:
    from odoo.http import request
    return request.env


@router.get("/", response_model=list[{model_class}Response])
async def list_{model_short}(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    env: Environment = Depends(_get_env),
) -> list[{model_class}Response]:
    """List {model} records."""
    records = env["{model}"].sudo().search([], limit=limit, offset=offset)
    return [_to_response(r) for r in records]


@router.get("/{{record_id}}", response_model={model_class}Response)
async def get_{model_short}(
    record_id: int,
    env: Environment = Depends(_get_env),
) -> {model_class}Response:
    """Get a single {model} record."""
    record = env["{model}"].sudo().browse(record_id)
    if not record.exists():
        raise HTTPException(status_code=404, detail="{model_class} not found")
    return _to_response(record)


@router.post("/", response_model={model_class}Response, status_code=201)
async def create_{model_short}(
    data: {model_class}Create,
    env: Environment = Depends(_get_env),
) -> {model_class}Response:
    """Create a new {model} record."""
    record = env["{model}"].sudo().create(data.model_dump(exclude_unset=True))
    return _to_response(record)


@router.patch("/{{record_id}}", response_model={model_class}Response)
async def update_{model_short}(
    record_id: int,
    data: {model_class}Update,
    env: Environment = Depends(_get_env),
) -> {model_class}Response:
    """Update a {model} record."""
    record = env["{model}"].sudo().browse(record_id)
    if not record.exists():
        raise HTTPException(status_code=404, detail="{model_class} not found")
    record.write(data.model_dump(exclude_unset=True))
    return _to_response(record)


@router.delete("/{{record_id}}", status_code=204)
async def delete_{model_short}(
    record_id: int,
    env: Environment = Depends(_get_env),
) -> None:
    """Delete a {model} record."""
    record = env["{model}"].sudo().browse(record_id)
    if not record.exists():
        raise HTTPException(status_code=404, detail="{model_class} not found")
    record.unlink()


def _to_response(record) -> {model_class}Response:
    """Convert Odoo record to response schema."""
    return {model_class}Response(
        id=record.id,
        name=record.name if hasattr(record, "name") else str(record.id),
        # TODO: add more fields
    )
'''

    schema_content = f'''\
# -*- coding: utf-8 -*-
"""Pydantic schemas for {model}."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class {model_class}Base(BaseModel):
    """Base schema for {model}."""
    name: Optional[str] = None
    # TODO: add more fields


class {model_class}Create({model_class}Base):
    """Schema for creating a {model} record."""
    name: str = Field(..., description="Name of the record")


class {model_class}Update({model_class}Base):
    """Schema for updating a {model} record."""
    pass


class {model_class}Response({model_class}Base):
    """Schema for {model} API response."""
    id: int

    model_config = {{"from_attributes": True}}
'''

    test_content = f'''\
# -*- coding: utf-8 -*-
"""Tests for {model_short} CRUD router."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


class Test{model_class}Router:
    """Basic tests for {model_short} router."""

    def test_schema_import(self):
        """Verify schema classes are importable."""
        from {module}.schemas.{model_short}_schema import (
            {model_class}Create,
            {model_class}Update,
            {model_class}Response,
        )
        assert {model_class}Create
        assert {model_class}Update
        assert {model_class}Response

    def test_create_schema(self):
        """Verify create schema validates required fields."""
        from {module}.schemas.{model_short}_schema import {model_class}Create
        obj = {model_class}Create(name="Test Record")
        assert obj.name == "Test Record"

    def test_response_schema(self):
        """Verify response schema includes id field."""
        from {module}.schemas.{model_short}_schema import {model_class}Response
        obj = {model_class}Response(id=42, name="Test")
        assert obj.id == 42
'''

    _write_file(controllers_dir / f"{model_short}_router.py", router_content, overwrite=overwrite)
    _write_file(schemas_dir / f"{model_short}_schema.py", schema_content, overwrite=overwrite)
    _write_file(tests_dir / f"test_{model_short}_router.py", test_content, overwrite=overwrite)

    console.print(f"\n[green]CRUD API scaffolded for {model} in {module}[/green]")
    console.print(f"  Router:  controllers/{model_short}_router.py")
    console.print(f"  Schema:  schemas/{model_short}_schema.py")
    console.print(f"  Tests:   tests/test_{model_short}_router.py")


# ---------------------------------------------------------------------------
# scaffold print-report - registered from a dedicated module
# ---------------------------------------------------------------------------

from kctl_odoo.commands.scaffold_print_report import print_report as _print_report_impl  # noqa: E402

app.command(name="print-report")(_print_report_impl)
