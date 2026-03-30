"""User models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class GroupRef(BaseModel):
    pk: str
    name: str
    is_superuser: bool = False


class UserBrief(BaseModel):
    pk: int
    username: str
    email: str = ""
    name: str = ""
    is_active: bool = True
    is_superuser: bool = False


class User(UserBrief):
    last_login: datetime | None = None
    type: str | None = None
    groups_obj: list[GroupRef] = []
    attributes: dict = {}
    avatar: str | None = None
    uid: str | None = None


class UserCreate(BaseModel):
    username: str
    email: str
    name: str
    is_active: bool = True
    is_superuser: bool = False


class UserUpdate(BaseModel):
    username: str | None = None
    email: str | None = None
    name: str | None = None
    is_active: bool | None = None
    is_superuser: bool | None = None
    attributes: dict | None = None
