"""Pydantic models for provisioning configuration and results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel


class MailcowConfig(BaseModel):
    api_url: str


class ProvisionDefaults(BaseModel):
    mailbox_quota: int = 1073741824  # 1GB


class CompanyConfig(BaseModel):
    domain: str
    hrms: str | None = None
    odoo_targets: list[str] = []


class ProvisionConfig(BaseModel):
    mailcow: MailcowConfig
    defaults: ProvisionDefaults = ProvisionDefaults()
    companies: dict[str, CompanyConfig] = {}


class StepStatus(str, Enum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class StepResult:
    name: str
    status: StepStatus
    detail: str = ""


@dataclass
class ChainResult:
    email: str
    action: str  # "onboard" or "offboard"
    steps: list[StepResult] = field(default_factory=list)
    success: bool = True

    def add(self, name: str, status: StepStatus, detail: str = "") -> None:
        self.steps.append(StepResult(name=name, status=status, detail=detail))
        if status == StepStatus.FAILED:
            self.success = False
