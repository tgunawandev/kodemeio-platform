"""Pydantic data models for config and runtime types."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

# --- Config models (for JSON file validation) ---


class RetryConfig(BaseModel):
    max_attempts: int = 3
    backoff: str = "exponential"


class AgentConfig(BaseModel):
    name: str
    model: str
    profile: str
    thinking: str = "adaptive"
    system_prompt: str | None = None
    workspace: str | None = None
    sandbox: bool = True


class CronJob(BaseModel):
    id: str
    name: str
    schedule: str
    agent: str
    model: str | None = None
    prompt: str
    enabled: bool = True
    silent: bool = False
    retry: RetryConfig | None = None


class McpServer(BaseModel):
    command: str
    args: list[str]
    env: dict[str, str] = {}
    disabled: bool = False


class ToolProfile(BaseModel):
    name: str
    servers: list[str]
    denied_tools: list[str] = []


class TelegramBot(BaseModel):
    name: str
    token_env: str
    bound_agent: str


class SecurityConfig(BaseModel):
    audit_on_start: bool = True
    redact_sensitive: bool = True
    sandbox_non_main: bool = True


class GatewayConfig(BaseModel):
    port: int = 18789
    auth_mode: str = "token"
    token_env: str = "OPENCLAW_GATEWAY_TOKEN"


# --- Runtime models (from Gateway API responses) ---


class HealthStatus(BaseModel):
    healthy: bool
    uptime_seconds: int
    version: str
    agents_active: int
    mcp_servers_connected: int
    memory_usage_mb: float


class AgentStatus(BaseModel):
    name: str
    model: str
    profile: str
    active_sessions: int
    last_activity: datetime | None = None


class CronExecution(BaseModel):
    job_id: str
    started_at: datetime
    finished_at: datetime | None = None
    status: str
    duration_seconds: float | None = None
    error: str | None = None
    attempt: int = 1


class McpTestResult(BaseModel):
    server: str
    connected: bool
    tools_count: int
    latency_ms: float | None = None
    error: str | None = None


class ModelUsage(BaseModel):
    requests: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    avg_latency_ms: float


class UsageSummary(BaseModel):
    period: str
    total_tokens: int
    total_cost_usd: float
    by_model: dict[str, ModelUsage] = {}


class ContainerStatus(BaseModel):
    name: str
    status: str
    health: str = ""
    uptime: str = ""


class DiffEntry(BaseModel):
    path: str
    local_value: str
    remote_value: str
