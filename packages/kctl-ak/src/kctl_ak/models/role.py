"""Role definition model (loaded from YAML files)."""

from __future__ import annotations

from pydantic import BaseModel


class RoleDefinition(BaseModel):
    name: str
    description: str = ""
    groups: list[str] = []
    file_path: str | None = None
