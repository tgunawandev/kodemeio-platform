"""Flow models."""

from __future__ import annotations

from pydantic import BaseModel


class Flow(BaseModel):
    pk: str
    slug: str
    name: str
    title: str | None = None
    designation: str = ""
    policy_engine_mode: str | None = None
    compatibility_mode: bool = False
    denied_action: str | None = None
    authentication: str | None = None


class StageRef(BaseModel):
    name: str | None = None
    component: str | None = None
    verbose_name: str | None = None


class FlowBinding(BaseModel):
    pk: str
    order: int = 0
    stage: str | None = None
    stage_obj: StageRef | None = None
    enabled: bool = True
    target: str = ""
