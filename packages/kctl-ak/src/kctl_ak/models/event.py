"""Event/audit models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class EventUser(BaseModel):
    pk: int | None = None
    username: str | None = None
    email: str | None = None


class Event(BaseModel):
    pk: str
    action: str
    app: str | None = None
    created: datetime | None = None
    expires: datetime | None = None
    user: EventUser | dict | None = None
    client_ip: str | None = None
    context: dict = {}
