"""Pydantic schema for kctl-odoo profile entries."""

from __future__ import annotations

from kctl_lib.schemas import register_service_schema
from pydantic import BaseModel, Field


class OdooServiceConfig(BaseModel):
    """Shape of the `odoo` block within a kctl-* profile."""

    url: str = Field(..., description="Odoo base URL, e.g. https://erp.idtpp.com")
    database: str = Field(..., description="Database name on the Odoo server")
    username: str = Field(default="admin", description="Odoo login")
    api_key: str = Field(..., description="API key or password")
    project_root: str | None = Field(default=None, description="Local project-root override (dev profiles only)")


register_service_schema("odoo", OdooServiceConfig)
