"""Pydantic models for provisioning configuration and results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel


class MailcowConfig(BaseModel):
    api_url: str | None = None  # default/fallback; prefer per-company mailcow_url


class ProvisionDefaults(BaseModel):
    mailbox_quota: int = 5368709120  # 5GB


class CompanyConfig(BaseModel):
    domain: str
    hrms: str | None = None
    odoo_targets: list[str] = []
    mailcow_url: str | None = None  # per-company Mailcow endpoint
    mailcow_key_env: str | None = None  # env var name holding the Mailcow API key
    default_groups: list[str] = []  # Authentik groups to auto-assign on onboard
    apps: dict[str, str] = {}  # app label → URL for onboarding templates
    guide_url: str = ""  # public quick guide URL for onboarding


class ProvisionConfig(BaseModel):
    mailcow: MailcowConfig = MailcowConfig()
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
    name: str = ""
    company_code: str = ""
    user_id: int | None = None
    recovery_link: str = ""
    groups: list[str] = field(default_factory=list)
    mailbox_quota_gb: int = 0
    apps: dict[str, str] = field(default_factory=dict)
    guide_url: str = ""

    def add(self, name: str, status: StepStatus, detail: str = "") -> None:
        self.steps.append(StepResult(name=name, status=status, detail=detail))
        if status == StepStatus.FAILED:
            self.success = False
