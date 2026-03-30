"""Group models."""

from __future__ import annotations

from pydantic import BaseModel


class UserRef(BaseModel):
    pk: int
    username: str
    email: str = ""
    is_active: bool = True


class GroupBrief(BaseModel):
    pk: str
    name: str
    is_superuser: bool = False


class Group(GroupBrief):
    parent: str | None = None
    parent_name: str | None = None
    users: list[int] = []
    users_obj: list[UserRef] = []
    attributes: dict = {}


class GroupCreate(BaseModel):
    name: str
    is_superuser: bool = False
    parent: str | None = None


class GroupUpdate(BaseModel):
    name: str | None = None
    is_superuser: bool | None = None
    parent: str | None = None
    attributes: dict | None = None
