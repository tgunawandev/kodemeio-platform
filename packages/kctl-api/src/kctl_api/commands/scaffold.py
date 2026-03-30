"""Scaffolding commands for kctl-api.

Generate new apps, endpoints, models, and webhooks.
"""

from __future__ import annotations

import subprocess
from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.utils import find_project_root

app = typer.Typer(name="scaffold", help="Scaffold — new app, endpoint, model, webhook.", no_args_is_help=True)


# ---------------------------------------------------------------------------
# app
# ---------------------------------------------------------------------------
@app.command(name="app")
def scaffold_app(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="New app name.")],
    app_type: Annotated[
        str, typer.Option("--type", "-t", help="App type: webhook, events, integration, agent, etl, scheduler, stream.")
    ] = "webhook",
    port: Annotated[int | None, typer.Option("--port", "-p", help="Port number.")] = None,
) -> None:
    """Scaffold a new deployable app via scripts/new-app."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    cmd = [str(root / "scripts" / "new-app"), name, "--type", app_type]
    if port:
        cmd.extend(["--port", str(port)])

    out.info(f"Scaffolding app: {name} (type={app_type})")
    result = subprocess.run(cmd, cwd=str(root), capture_output=False)
    if result.returncode != 0:
        out.error("Scaffolding failed.")
        raise typer.Exit(result.returncode)
    out.success(f"App '{name}' scaffolded successfully.")


# ---------------------------------------------------------------------------
# endpoint
# ---------------------------------------------------------------------------
@app.command()
def endpoint(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="Target app name.")],
    name: Annotated[str, typer.Argument(help="Endpoint/resource name.")],
) -> None:
    """Scaffold a new API endpoint in an existing app."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    script = root / "scripts" / "new-endpoint"

    if script.exists():
        result = subprocess.run([str(script), app_name, name], cwd=str(root), capture_output=False)
        if result.returncode != 0:
            out.error("Scaffolding failed.")
            raise typer.Exit(result.returncode)
        out.success(f"Endpoint '{name}' scaffolded in {app_name}.")
    else:
        out.info(f"Not yet implemented. Will scaffold endpoint '{name}' in {app_name}.")


# ---------------------------------------------------------------------------
# model
# ---------------------------------------------------------------------------
@app.command()
def model(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Model name (PascalCase).")],
    table: Annotated[str | None, typer.Option("--table", help="Table name override.")] = None,
) -> None:
    """Scaffold a new SQLAlchemy model with Alembic migration."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    script = root / "scripts" / "new-model"

    if script.exists():
        cmd = [str(script), name]
        if table:
            cmd.extend(["--table", table])
        result = subprocess.run(cmd, cwd=str(root), capture_output=False)
        if result.returncode != 0:
            out.error("Scaffolding failed.")
            raise typer.Exit(result.returncode)
        out.success(f"Model '{name}' scaffolded.")
    else:
        out.info(f"Not yet implemented. Will scaffold model '{name}'.")


# ---------------------------------------------------------------------------
# webhook
# ---------------------------------------------------------------------------
@app.command()
def webhook(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Webhook app name.")],
    port: Annotated[int | None, typer.Option("--port", "-p", help="Port number.")] = None,
) -> None:
    """Scaffold a new standalone webhook receiver app."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    script = root / "scripts" / "new-webhook"

    if script.exists():
        cmd = [str(script), name]
        if port:
            cmd.extend(["--port", str(port)])
        result = subprocess.run(cmd, cwd=str(root), capture_output=False)
        if result.returncode != 0:
            out.error("Scaffolding failed.")
            raise typer.Exit(result.returncode)
        out.success(f"Webhook '{name}' scaffolded.")
    else:
        # Fall back to new-app with webhook type
        cmd = [str(root / "scripts" / "new-app"), name, "--type", "webhook"]
        if port:
            cmd.extend(["--port", str(port)])
        result = subprocess.run(cmd, cwd=str(root), capture_output=False)
        if result.returncode != 0:
            out.error("Scaffolding failed.")
            raise typer.Exit(result.returncode)
        out.success(f"Webhook '{name}' scaffolded.")


# ---------------------------------------------------------------------------
# service
# ---------------------------------------------------------------------------
@app.command()
def service(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Service class name (PascalCase, e.g. UserService).")],
    app_name: Annotated[str | None, typer.Option("--app", "-a", help="Target app name.")] = None,
) -> None:
    """Scaffold a service class boilerplate file."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    snake_name = "".join(["_" + c.lower() if c.isupper() else c for c in name]).lstrip("_")
    snake_name = snake_name.replace("__", "_")

    # Determine target directory
    if app_name:
        target_dir = root / "apps" / app_name / "src" / f"kodemeio_{app_name.replace('-', '_')}" / "services"
    else:
        target_dir = root / "services"

    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / f"{snake_name}.py"

    if target_file.exists():
        out.error(f"File already exists: {target_file}")
        raise typer.Exit(1)

    content = f'''"""Service layer for {name}."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from kodemeio_core.utils.query import paginate


class {name}:
    """Business logic for {name.replace("Service", "")} operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list(self, params: object) -> object:
        """List {name.replace("Service", "").lower()} resources with pagination."""
        raise NotImplementedError

    async def get(self, resource_id: str) -> object | None:
        """Get a single {name.replace("Service", "").lower()} by ID."""
        raise NotImplementedError

    async def create(self, data: object) -> object:
        """Create a new {name.replace("Service", "").lower()} resource."""
        raise NotImplementedError

    async def update(self, resource_id: str, data: object) -> object:
        """Update an existing {name.replace("Service", "").lower()} resource."""
        raise NotImplementedError

    async def delete(self, resource_id: str) -> bool:
        """Soft-delete a {name.replace("Service", "").lower()} resource."""
        raise NotImplementedError
'''

    target_file.write_text(content)
    out.success(f"Service '{name}' scaffolded at {target_file.relative_to(root)}")


# ---------------------------------------------------------------------------
# middleware
# ---------------------------------------------------------------------------
@app.command(name="middleware")
def scaffold_middleware(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Middleware name (e.g. RequestLogging).")],
    app_name: Annotated[str | None, typer.Option("--app", "-a", help="Target app name.")] = None,
) -> None:
    """Scaffold a Starlette/FastAPI middleware boilerplate."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    snake_name = "".join(["_" + c.lower() if c.isupper() else c for c in name]).lstrip("_")
    snake_name = snake_name.replace("__", "_")

    if app_name:
        target_dir = root / "apps" / app_name / "src" / f"kodemeio_{app_name.replace('-', '_')}" / "middleware"
    else:
        target_dir = root / "packages" / "core" / "src" / "kodemeio_core" / "middleware"

    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / f"{snake_name}.py"

    if target_file.exists():
        out.error(f"File already exists: {target_file}")
        raise typer.Exit(1)

    content = f'''"""{name} middleware."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from kodemeio_core.logging import get_logger

logger = get_logger(__name__)


class {name}Middleware(BaseHTTPMiddleware):
    """{name} middleware — add description here."""

    def __init__(self, app: object, **kwargs: object) -> None:
        super().__init__(app)  # type: ignore[arg-type]

    async def dispatch(self, request: Request, call_next: object) -> Response:
        # Pre-processing
        logger.debug("request", path=request.url.path, method=request.method)

        response = await call_next(request)  # type: ignore[misc]

        # Post-processing
        return response
'''

    target_file.write_text(content)
    out.success(f"Middleware '{name}Middleware' scaffolded at {target_file.relative_to(root)}")


# ---------------------------------------------------------------------------
# background-job
# ---------------------------------------------------------------------------
@app.command(name="background-job")
def background_job(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Job function name (snake_case, e.g. send_email).")],
    app_name: Annotated[str | None, typer.Option("--app", "-a", help="Target app name.")] = None,
) -> None:
    """Scaffold an ARQ background job boilerplate."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()

    if app_name:
        target_dir = root / "apps" / app_name / "src" / f"kodemeio_{app_name.replace('-', '_')}" / "jobs"
    else:
        target_dir = root / "apps" / "api-main" / "src" / "kodemeio_api_main" / "jobs"

    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / f"{name}.py"

    if target_file.exists():
        out.error(f"File already exists: {target_file}")
        raise typer.Exit(1)

    content = f'''"""ARQ background job: {name}."""

from __future__ import annotations

from arq import ArqRedis
from kodemeio_core.logging import get_logger

logger = get_logger(__name__)


async def {name}(ctx: dict, **kwargs: object) -> dict:
    """Background job: {name.replace("_", " ")}.

    Args:
        ctx: ARQ job context (contains redis, job_id, etc.)
        **kwargs: Job-specific parameters

    Returns:
        Result dict with status and any relevant data.
    """
    job_id = ctx.get("job_id", "unknown")
    logger.info("job_started", job="{name}", job_id=job_id, params=kwargs)

    try:
        # TODO: implement job logic here
        result = {{"status": "completed", "job_id": job_id}}
        logger.info("job_completed", job="{name}", job_id=job_id)
        return result
    except Exception as e:
        logger.error("job_failed", job="{name}", job_id=job_id, error=str(e))
        raise
'''

    target_file.write_text(content)
    out.success(f"Background job '{name}' scaffolded at {target_file.relative_to(root)}")
    out.info("Enqueue via: POST /api/v1/jobs/enqueue (admin only)")


# ---------------------------------------------------------------------------
# migration
# ---------------------------------------------------------------------------
@app.command()
def migration(
    ctx: typer.Context,
    message: Annotated[str, typer.Argument(help="Migration message.")],
    autogenerate: Annotated[bool, typer.Option("--auto", help="Auto-generate from model changes.")] = True,
) -> None:
    """Generate an Alembic migration file."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    script = root / "scripts" / "db"

    cmd = [str(script), "generate", message]
    if not autogenerate:
        cmd.append("--no-autogenerate")

    out.info(f"Generating migration: {message}")
    result = subprocess.run(cmd, cwd=str(root), capture_output=False)
    if result.returncode != 0:
        out.error("Migration generation failed.")
        raise typer.Exit(result.returncode)
    out.success(f"Migration generated: {message}")
