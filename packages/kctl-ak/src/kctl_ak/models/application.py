"""Application models."""

from __future__ import annotations

from pydantic import BaseModel


class ProviderRef(BaseModel):
    name: str = ""
    verbose_name: str | None = None


class Application(BaseModel):
    pk: str
    slug: str
    name: str
    provider: int | None = None
    provider_obj: ProviderRef | None = None
    meta_launch_url: str | None = None
    meta_description: str | None = None
    meta_icon_url: str | None = None
    meta_publisher: str | None = None
    open_in_new_tab: bool = False
    policy_engine_mode: str | None = None
    backchannel_providers: list[int] = []


class ApplicationCreate(BaseModel):
    name: str
    slug: str
    provider: int | None = None
    meta_launch_url: str | None = None
    meta_description: str | None = None


class ApplicationUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    provider: int | None = None
    meta_launch_url: str | None = None
    meta_description: str | None = None
    open_in_new_tab: bool | None = None
