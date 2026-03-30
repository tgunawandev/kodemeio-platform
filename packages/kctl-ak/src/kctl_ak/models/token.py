"""Token models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from kctl_ak.models.user import UserBrief


class Token(BaseModel):
    identifier: str = ""
    user: int = 0
    user_obj: UserBrief | None = None
    intent: str = ""
    description: str | None = None
    expires: datetime | None = None
    expiring: bool = False
    managed: str | None = None


class TokenCreate(BaseModel):
    identifier: str
    user: int
    intent: str = "api"
    description: str | None = None


class TokenKey(BaseModel):
    key: str = ""
