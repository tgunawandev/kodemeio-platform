"""System, health, and maintenance models."""

from __future__ import annotations

from pydantic import BaseModel


class VersionInfo(BaseModel):
    version_current: str = ""
    version_latest: str | None = None
    build_hash: str | None = None
    outdated: bool = False


class SystemInfo(BaseModel):
    http_headers: dict = {}
    http_host: str = ""
    http_is_secure: bool = False
    runtime: dict = {}
    tenant: str = ""
    server_time: str = ""
    embedded_outpost_host: str = ""


class TaskInfo(BaseModel):
    full_name: str | None = None
    task_name: str | None = None
    status: str | None = None
    duration: float | None = None
    uid: str | None = None
    description: str | None = None


class Outpost(BaseModel):
    pk: str = ""
    name: str = ""
    type: str = ""
    providers: list[int] = []
    providers_obj: list[dict] = []
    service_connection: str | None = None
    token_identifier: str = ""
    managed: str | None = None


class Brand(BaseModel):
    brand_uuid: str = ""
    domain: str = ""
    branding_title: str = ""
    branding_logo: str = ""
    default: bool = False
