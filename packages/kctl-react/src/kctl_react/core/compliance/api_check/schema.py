"""OpenAPI schema loader and parser."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

APP_BACKEND_MAP = {
    "sfa": "sfa_management",
    "lfa": "lfa_management",
    "shop": "shop_management",
    "wms": "wms_management",
    "bia": "bia_management",
    "eam": "asset_management",
    "mrp": "mrp_management",
    "hrm": "hrm_management",
    "tpm": "tpm_management",
    "dms": "dms_management",
    "saas": "saas_management",
}


@dataclass
class Operation:
    method: str  # get, post, put, delete
    path: str  # /productions/{id}
    tag: str  # mrp-productions
    response_schema: str | None = None  # ProductionDetailResponse
    request_schema: str | None = None  # ProduceQuantityRequest
    parameters: list[str] = field(default_factory=list)  # ["state", "search"]


@dataclass
class ParsedSchema:
    operations: list[Operation] = field(default_factory=list)
    response_schemas: dict[str, dict] = field(default_factory=dict)


def load_schema(app_path: Path, app_name: str, *, offline: bool = False) -> dict | None:
    """Load OpenAPI schema from cache or fetch from backend."""
    cached = app_path / "openapi.json"
    if cached.exists():
        try:
            return json.loads(cached.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read cached schema: %s", exc)

    if offline:
        return None

    return fetch_schema(app_path, app_name)


def fetch_schema(app_path: Path, app_name: str) -> dict | None:
    """Fetch OpenAPI schema from the Odoo backend and cache it."""
    odoo_url = "http://localhost:8069"
    odoo_db = "odoo_18"

    env_file = app_path / ".env"
    if env_file.exists():
        try:
            content = env_file.read_text()
            url_match = re.search(r"VITE_ODOO_URL\s*=\s*(.+)", content)
            if url_match:
                odoo_url = url_match.group(1).strip().strip("\"'")
            db_match = re.search(r"VITE_ODOO_DB\s*=\s*(.+)", content)
            if db_match:
                odoo_db = db_match.group(1).strip().strip("\"'")
        except OSError as exc:
            logger.warning("Failed to read .env: %s", exc)

    backend_name = APP_BACKEND_MAP.get(app_name)
    if not backend_name:
        logger.warning("Unknown app %r — no backend mapping", app_name)
        return None

    url = f"{odoo_url}/{backend_name}/api/openapi.json?db={odoo_db}"

    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        logger.warning("Failed to fetch schema from %s: %s", url, exc)
        return None

    try:
        (app_path / "openapi.json").write_text(json.dumps(data, indent=2))
    except OSError as exc:
        logger.warning("Failed to cache schema: %s", exc)

    return data


def _extract_ref_name(ref: str) -> str:
    """Extract schema name from a $ref string like '#/components/schemas/Foo'."""
    return ref.rsplit("/", 1)[-1]


def parse_schema(raw: dict) -> ParsedSchema:
    """Parse a raw OpenAPI JSON dict into structured operations."""
    operations: list[Operation] = []

    for path, methods in raw.get("paths", {}).items():
        for method in ("get", "post", "put", "delete", "patch"):
            operation = methods.get(method)
            if operation is None:
                continue

            tag = operation.get("tags", ["unknown"])[0]

            # Response schema
            response_schema: str | None = None
            resp_200 = operation.get("responses", {}).get("200", {})
            resp_content = resp_200.get("content", {}).get("application/json", {})
            resp_schema_obj = resp_content.get("schema", {})
            if "$ref" in resp_schema_obj:
                response_schema = _extract_ref_name(resp_schema_obj["$ref"])

            # Request schema
            request_schema: str | None = None
            req_body = operation.get("requestBody", {})
            req_content = req_body.get("content", {}).get("application/json", {})
            req_schema_obj = req_content.get("schema", {})
            if "$ref" in req_schema_obj:
                request_schema = _extract_ref_name(req_schema_obj["$ref"])

            # Parameters
            parameters = [p["name"] for p in operation.get("parameters", []) if "name" in p]

            operations.append(
                Operation(
                    method=method,
                    path=path,
                    tag=tag,
                    response_schema=response_schema,
                    request_schema=request_schema,
                    parameters=parameters,
                )
            )

    response_schemas = raw.get("components", {}).get("schemas", {})

    return ParsedSchema(operations=operations, response_schemas=response_schemas)
