"""Session models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from kctl_ak.models.user import UserBrief


class AuthenticatedSession(BaseModel):
    uuid: str = ""
    user: int = 0
    user_obj: UserBrief | None = None
    current: bool = False
    last_ip: str | None = None
    last_user_agent: str | None = None
    last_used: datetime | None = None
    geo_ip: dict | None = None
