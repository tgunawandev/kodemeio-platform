"""Blueprint models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class BlueprintInstance(BaseModel):
    pk: str = ""
    name: str = ""
    path: str | None = None
    status: str | None = None
    enabled: bool = True
    last_applied: datetime | None = None
    content: str | None = None
