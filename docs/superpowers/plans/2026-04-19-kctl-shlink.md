# kctl-shlink Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `kctl-shlink` CLI — Shlink REST API v3 client with ~30 commands across 9 domain groups plus standard kctl-* commands, declarative campaign manifest apply, QR generation with print presets, Shlink×Plausible cross-join report. Meeting quality baseline.

**Architecture:** Python CLI using kctl-lib>=0.4.0. Subclasses `APIClient` for Shlink's Bearer-token REST API. Campaign manifest apply pattern (Pydantic 2 schema + idempotent apply — analogous to `kctl-dbgate connections`). Soft-dependency on `kctl-plausible` for cross-join reports (lazy import). Follows `packages/kctl-zulip/` structural layout.

**Tech Stack:** Python 3.12+, kctl-lib>=0.4.0, Typer, httpx (via APIClient), Rich, Pydantic 2, PyYAML, qrcode[pil] + Pillow (QR generation). Hatchling + uv.

**Spec:** `docs/superpowers/specs/2026-04-19-kctl-marketing-wave-1-design.md` (§4.3, §6)

**Profile:** `kodemeio-kod-infra-shlink` — already exists after Plan A

**Working directory:** `/home/tgunawan/project/00-new-projects/kodemeio-workspace/kodemeio-platform`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `packages/kctl-shlink/pyproject.toml` | Package config, deps, entry points |
| Create | `packages/kctl-shlink/README.md` | User-facing docs ≥ 60 lines |
| Create | `packages/kctl-shlink/CHANGELOG.md` | Release log |
| Create | `packages/kctl-shlink/src/kctl_shlink/__init__.py` | Version |
| Create | `packages/kctl-shlink/src/kctl_shlink/__main__.py` | `python -m` entry |
| Create | `packages/kctl-shlink/src/kctl_shlink/cli.py` | Main Typer app, callback, registration |
| Create | `packages/kctl-shlink/src/kctl_shlink/core/__init__.py` | Empty |
| Create | `packages/kctl-shlink/src/kctl_shlink/core/config.py` | `SERVICE_KEY`, `ServiceConfig`, profile resolution |
| Create | `packages/kctl-shlink/src/kctl_shlink/core/client.py` | `ShlinkClient(APIClient)` |
| Create | `packages/kctl-shlink/src/kctl_shlink/core/callbacks.py` | `AppContext` dataclass |
| Create | `packages/kctl-shlink/src/kctl_shlink/core/output.py` | Re-export `Output` from kctl-lib |
| Create | `packages/kctl-shlink/src/kctl_shlink/core/validators.py` | Slug + utm_campaign regex validators |
| Create | `packages/kctl-shlink/src/kctl_shlink/core/manifest.py` | Pydantic `CampaignManifest` schema + loader |
| Create | `packages/kctl-shlink/src/kctl_shlink/core/qr.py` | QR rendering (PNG/SVG, margins, logo overlay) |
| Create | `packages/kctl-shlink/src/kctl_shlink/core/plausible_bridge.py` | Lazy-import bridge to kctl-plausible |
| Create | `packages/kctl-shlink/src/kctl_shlink/commands/__init__.py` | Empty |
| Create | `packages/kctl-shlink/src/kctl_shlink/commands/config_cmd.py` | `config init/add/use/show/validate/remove/set/profiles/current` |
| Create | `packages/kctl-shlink/src/kctl_shlink/commands/doctor_cmd.py` | `doctor` (incl. TLS, DNS, tag inventory, Plausible bridge, visit lag) |
| Create | `packages/kctl-shlink/src/kctl_shlink/commands/skill_cmd.py` | `skill generate` (SKILL.md auto-gen) |
| Create | `packages/kctl-shlink/src/kctl_shlink/commands/domains.py` | `domains list/add/remove/set-default` |
| Create | `packages/kctl-shlink/src/kctl_shlink/commands/urls.py` | `urls list/create/show/update/delete` (auto UTM injection) |
| Create | `packages/kctl-shlink/src/kctl_shlink/commands/tags.py` | `tags list/create/rename/delete/stats` |
| Create | `packages/kctl-shlink/src/kctl_shlink/commands/visits.py` | `visits list/stats/realtime/by-tag/by-url/orphans` |
| Create | `packages/kctl-shlink/src/kctl_shlink/commands/qr_cmd.py` | `qr generate/bulk` |
| Create | `packages/kctl-shlink/src/kctl_shlink/commands/campaigns.py` | `campaigns apply/diff/destroy/list` |
| Create | `packages/kctl-shlink/src/kctl_shlink/commands/reports.py` | `reports campaign/channel/product/compare` |
| Create | `packages/kctl-shlink/src/kctl_shlink/commands/redirects.py` | `redirects list/set/clear` |
| Create | `packages/kctl-shlink/src/kctl_shlink/commands/export_cmd.py` | `export csv/json` |
| Create | `packages/kctl-shlink/tests/__init__.py` | Empty |
| Create | `packages/kctl-shlink/tests/conftest.py` | Shared fixtures (runner, mock_client, mock_output, mock_context, mock_config) |
| Create | `packages/kctl-shlink/tests/test_smoke.py` | `--help`, `--version`, group help |
| Create | `packages/kctl-shlink/tests/test_client.py` | `ShlinkClient` subclass |
| Create | `packages/kctl-shlink/tests/test_config.py` | Profile resolution, `resolve_connection` |
| Create | `packages/kctl-shlink/tests/test_validators.py` | Slug + utm_campaign regex |
| Create | `packages/kctl-shlink/tests/test_manifest.py` | `CampaignManifest` loader + validation |
| Create | `packages/kctl-shlink/tests/test_qr.py` | PNG/SVG generation, margin presets, logo overlay |
| Create | `packages/kctl-shlink/tests/test_domains.py` | `domains` group |
| Create | `packages/kctl-shlink/tests/test_urls.py` | `urls` group, UTM auto-inject |
| Create | `packages/kctl-shlink/tests/test_tags.py` | `tags` group |
| Create | `packages/kctl-shlink/tests/test_visits.py` | `visits` group |
| Create | `packages/kctl-shlink/tests/test_campaigns.py` | `campaigns apply` idempotency |
| Create | `packages/kctl-shlink/tests/test_reports.py` | cross-join report with/without Plausible |
| Create | `packages/kctl-shlink/tests/test_redirects.py` | `redirects` group |
| Create | `packages/kctl-shlink/tests/test_export.py` | `export` group |
| Create | `packages/kctl-shlink/tests/test_doctor.py` | doctor checks |
| Create | `packages/kctl-shlink/skills/shlink-admin/SKILL.md` | Auto-gen skill placeholder |
| Create | `packages/kctl-shlink/skills/shlink-admin/SKILL.extra.md` | Hand-written skill content |
| Create | `deploys/marketing/shlink-campaigns/example-tpm-linkedin-q2.yaml` | Example campaign manifest |
| Modify | `pyproject.toml` (workspace root) | Add `kctl-shlink` to `[tool.uv.workspace]` members |
| Modify | `uv.lock` | Regenerated after `uv sync` |
| Modify | `CLAUDE.md` | Add `kctl-shlink` row to packages table |
| Modify | `.github/workflows/ci.yml` | Add `kctl-shlink` to lint/test matrix |

---

## Task 1: Package scaffolding (pyproject + version)

- [ ] **Step 1: Create `packages/kctl-shlink/pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "kctl-shlink"
version = "0.1.0"
description = "Kodemeio Shlink CLI — short URL management, campaign manifests, QR codes"
readme = "README.md"
license = "MIT"
requires-python = ">=3.12"
authors = [{ name = "Kodemeio", email = "dev@kodeme.io" }]
keywords = ["shlink", "shorturl", "marketing", "qr", "cli", "kodemeio"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: System Administrators",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.12",
    "Topic :: Internet :: WWW/HTTP",
]
dependencies = [
    "kctl-lib>=0.4.0",
    "typer>=0.15.0",
    "rich>=13.9.0",
    "pydantic>=2.10.0",
    "pyyaml>=6.0.2",
    "httpx>=0.28.0",
    "qrcode[pil]>=7.4.2",
    "Pillow>=11.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-cov>=5.0.0",
    "pytest-httpx>=0.35.0",
    "ruff>=0.9.0",
    "mypy>=1.14.0",
    "types-PyYAML>=6.0.0",
]

[project.scripts]
kctl-shlink = "kctl_shlink.cli:_run"

[tool.uv.sources]
kctl-lib = { workspace = true }

[project.entry-points."kctl_shlink.plugins"]

[tool.hatch.build.targets.wheel]
packages = ["src/kctl_shlink"]

[tool.ruff]
target-version = "py312"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "W", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.12"
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "integration: tests against a live Shlink instance",
    "smoke: basic CLI smoke tests",
]
```

- [ ] **Step 2: Create `src/kctl_shlink/__init__.py`**

```python
"""kctl-shlink: Kodemeio Shlink CLI."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Create `src/kctl_shlink/__main__.py`**

```python
"""Allow `python -m kctl_shlink`."""

from kctl_shlink.cli import _run

_run()
```

- [ ] **Step 4: Register `kctl-shlink` in workspace root `pyproject.toml`**

Add to existing `[tool.uv.workspace]` members list:

```toml
[tool.uv.workspace]
members = [
    # ... existing entries ...
    "packages/kctl-shlink",
]
```

- [ ] **Step 5: Run `uv sync --all-extras --all-packages`; commit pyproject + regenerated uv.lock.**

Commit: `chore(kctl-shlink): scaffold package skeleton`

---

## Task 2: Shared config module (profile + SERVICE_KEY)

- [ ] **Step 1 (TEST FIRST): Create `tests/test_config.py`**

```python
from __future__ import annotations

from unittest.mock import patch

from kctl_shlink.core.config import (
    SERVICE_KEY,
    ServiceConfig,
    get_service_config,
    resolve_connection,
    set_service_config,
)


def test_service_key_is_shlink() -> None:
    assert SERVICE_KEY == "shlink"


def test_set_and_get_service_config(mock_config) -> None:
    set_service_config("test", ServiceConfig(url="https://s.test.io", api_key="abc", default_domain="s.test.io"))
    svc = get_service_config("test")
    assert svc.url == "https://s.test.io"
    assert svc.api_key == "abc"
    assert svc.default_domain == "s.test.io"


def test_resolve_connection_precedence(mock_config) -> None:
    set_service_config("p", ServiceConfig(url="https://s.file.io", api_key="FILE", default_domain="s.file.io"))
    with patch.dict("os.environ", {"KCTL_SHLINK_URL": "https://s.env.io", "KCTL_SHLINK_API_KEY": "ENV"}, clear=False):
        url, key, domain = resolve_connection(profile_name="p")
        assert url == "https://s.env.io"
        assert key == "ENV"
    # CLI override wins over env
    with patch.dict("os.environ", {"KCTL_SHLINK_URL": "https://s.env.io"}, clear=False):
        url, key, domain = resolve_connection(profile_name="p", url_override="https://s.cli.io")
        assert url == "https://s.cli.io"


def test_resolve_connection_requires_profile(mock_config) -> None:
    import pytest

    with pytest.raises(ValueError, match="No active profile"):
        resolve_connection()
```

- [ ] **Step 2: Create `src/kctl_shlink/core/config.py`**

Copy structure from `packages/kctl-zulip/src/kctl_zulip/core/config.py` with these differences:

- `SERVICE_KEY = "shlink"`
- `ServiceConfig` fields:
  ```python
  class ServiceConfig(BaseModel):
      url: str = ""
      api_key: str = ""
      default_domain: str = ""
      plausible_profile: str = ""  # optional — for cross-join reports
  ```
- `resolve_active_profile_name` follows the platform rule — **raises `ValueError`** listing profiles if neither `-p` nor `KCTL_SHLINK_PROFILE` is set. No silent default.
- `resolve_connection(...) -> tuple[str, str, str]` returns `(url, api_key, default_domain)`. Env var expansion via `_expand_token` for `${...}` values.
- Include `get_service_config` with prefix inheritance walking (`idtpp-tpp-odoo-erp → idtpp-tpp-odoo → idtpp-tpp → idtpp`).

- [ ] **Step 3: Create `src/kctl_shlink/core/__init__.py`** (empty docstring).

- [ ] **Step 4: Run `uv run pytest packages/kctl-shlink/tests/test_config.py -v`.**

Commit: `feat(kctl-shlink): profile config module with SERVICE_KEY=shlink`

---

## Task 3: ShlinkClient (APIClient subclass)

- [ ] **Step 1 (TEST FIRST): Create `tests/test_client.py`**

```python
from __future__ import annotations

import httpx
import pytest
from pytest_httpx import HTTPXMock

from kctl_shlink.core.client import ShlinkClient


def test_client_requires_url() -> None:
    from kctl_lib.exceptions import ConfigError
    with pytest.raises(ConfigError):
        ShlinkClient(base_url="", api_key="k")


def test_client_requires_key() -> None:
    from kctl_lib.exceptions import ConfigError
    with pytest.raises(ConfigError):
        ShlinkClient(base_url="https://s.test.io", api_key="")


def test_client_auth_header() -> None:
    c = ShlinkClient(base_url="https://s.test.io", api_key="SECRET")
    hdr = c._build_auth_header()
    assert hdr == {"X-Api-Key": "SECRET"}


def test_list_short_urls(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://s.test.io/rest/v3/short-urls?page=1&itemsPerPage=50",
        json={"shortUrls": {"data": [{"shortCode": "tpm-linkedin-q2a"}]}},
    )
    c = ShlinkClient(base_url="https://s.test.io", api_key="k")
    result = c.list_short_urls()
    assert result[0]["shortCode"] == "tpm-linkedin-q2a"


def test_check_health(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://s.test.io/rest/health", json={"status": "pass", "version": "4.4.0"})
    c = ShlinkClient(base_url="https://s.test.io", api_key="k")
    h = c.check_health()
    assert h["status"] == "pass"
```

- [ ] **Step 2: Create `src/kctl_shlink/core/client.py`**

```python
"""Shlink REST API v3 client (subclass of kctl-lib APIClient).

Shlink auth is `X-Api-Key: <key>` — NOT Bearer. Override AUTH_HEADER + clear AUTH_PREFIX.
API prefix: /rest/v3.
"""

from __future__ import annotations

from typing import Any

import httpx
from kctl_lib.api_client import APIClient


class ShlinkClient(APIClient):
    AUTH_HEADER = "X-Api-Key"
    AUTH_PREFIX = ""  # Shlink uses raw key, no "Bearer" prefix
    API_PREFIX = "/rest/v3"

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        default_domain: str = "",
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            base_url=base_url,
            credential=api_key,
            timeout=timeout,
            retry_enabled=True,
            max_retries=3,
            **kwargs,
        )
        self.default_domain = default_domain

    # ------------------------------------------------------------------
    # Health (public endpoint, no auth needed, different path)
    # ------------------------------------------------------------------

    @property
    def root_url(self) -> str:
        return self._base_url.rsplit("/rest/v3", 1)[0]

    def check_health(self) -> dict:
        try:
            r = httpx.get(f"{self.root_url}/rest/health", timeout=5)
            return r.json()
        except httpx.HTTPError:
            return {"status": "error", "message": "unreachable"}

    # ------------------------------------------------------------------
    # Short URLs
    # ------------------------------------------------------------------

    def list_short_urls(
        self,
        page: int = 1,
        items_per_page: int = 50,
        tags: list[str] | None = None,
        search_term: str | None = None,
    ) -> list[dict]:
        params: dict[str, Any] = {"page": page, "itemsPerPage": items_per_page}
        if tags:
            params["tags[]"] = tags
        if search_term:
            params["searchTerm"] = search_term
        resp = self.get("/short-urls", params=params)
        return resp.get("shortUrls", {}).get("data", [])

    def create_short_url(self, body: dict) -> dict:
        return self.post("/short-urls", json=body)

    def get_short_url(self, short_code: str, domain: str | None = None) -> dict:
        params = {"domain": domain} if domain else None
        return self.get(f"/short-urls/{short_code}", params=params)

    def update_short_url(self, short_code: str, body: dict, domain: str | None = None) -> dict:
        params = {"domain": domain} if domain else None
        return self.patch(f"/short-urls/{short_code}", json=body, params=params)

    def delete_short_url(self, short_code: str, domain: str | None = None) -> None:
        params = {"domain": domain} if domain else None
        self.delete(f"/short-urls/{short_code}", params=params)

    # ------------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------------

    def list_tags(self, with_stats: bool = False) -> list[dict]:
        params = {"withStats": "true"} if with_stats else None
        resp = self.get("/tags", params=params)
        if with_stats:
            return resp.get("tags", {}).get("stats", [])
        return [{"tag": t} for t in resp.get("tags", {}).get("data", [])]

    def rename_tag(self, old: str, new: str) -> None:
        self.put("/tags", json={"oldName": old, "newName": new})

    def delete_tags(self, tags: list[str]) -> None:
        self.delete("/tags", params={"tags[]": tags})

    # ------------------------------------------------------------------
    # Domains
    # ------------------------------------------------------------------

    def list_domains(self) -> list[dict]:
        resp = self.get("/domains")
        return resp.get("domains", {}).get("data", [])

    def set_domain_redirects(self, domain: str, redirects: dict) -> dict:
        return self.patch(f"/domains/redirects", json={"domain": domain, **redirects})

    # ------------------------------------------------------------------
    # Visits
    # ------------------------------------------------------------------

    def get_visits_summary(self) -> dict:
        return self.get("/visits")

    def get_visits_by_tag(self, tag: str, params: dict | None = None) -> dict:
        return self.get(f"/tags/{tag}/visits", params=params)

    def get_visits_by_short_url(self, short_code: str, params: dict | None = None) -> dict:
        return self.get(f"/short-urls/{short_code}/visits", params=params)

    def get_orphan_visits(self, params: dict | None = None) -> dict:
        return self.get("/visits/orphan", params=params)
```

- [ ] **Step 3: Run `uv run pytest packages/kctl-shlink/tests/test_client.py -v`.**

Commit: `feat(kctl-shlink): ShlinkClient subclassing APIClient with X-Api-Key auth`

---

## Task 4: Output re-export + callbacks + exceptions

- [ ] **Step 1: Create `src/kctl_shlink/core/output.py`**

```python
"""Re-export Output from kctl-lib for module-local imports."""

from __future__ import annotations

from kctl_lib.output import Output

__all__ = ["Output"]
```

- [ ] **Step 2: Create `src/kctl_shlink/core/callbacks.py`**

```python
"""Typer global callback + shared AppContext."""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_shlink.core.client import ShlinkClient
from kctl_shlink.core.config import resolve_connection
from kctl_shlink.core.output import Output


@dataclass
class AppContext:
    json_mode: bool = False
    quiet: bool = False
    format: str = "pretty"
    no_header: bool = False
    profile: str | None = None
    url_override: str | None = None
    api_key_override: str | None = None
    _client: ShlinkClient | None = field(default=None, repr=False, init=False)
    _output: Output | None = field(default=None, repr=False, init=False)

    @property
    def output(self) -> Output:
        if self._output is None:
            self._output = Output(
                json_mode=self.json_mode,
                quiet=self.quiet,
                format=self.format,
                no_header=self.no_header,
            )
        return self._output

    @property
    def client(self) -> ShlinkClient:
        if self._client is None:
            url, api_key, default_domain = resolve_connection(
                profile_name=self.profile,
                url_override=self.url_override,
                api_key_override=self.api_key_override,
            )
            self._client = ShlinkClient(base_url=url, api_key=api_key, default_domain=default_domain)
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
```

Commit: `feat(kctl-shlink): AppContext + Output re-export`

---

## Task 5: Validators (slug + utm_campaign regex)

- [ ] **Step 1 (TEST FIRST): Create `tests/test_validators.py`**

```python
from __future__ import annotations

import pytest

from kctl_shlink.core.validators import (
    SLUG_REGEX,
    UTM_CAMPAIGN_REGEX,
    validate_slug,
    validate_utm_campaign,
)


class TestSlugValidator:
    @pytest.mark.parametrize(
        "slug",
        [
            "tpm-linkedin-q2a",
            "bas-google-pricing",
            "tms-meta-parent01",
            "cross-email-may-v2",
            "careers-event-openhouse",
        ],
    )
    def test_valid(self, slug: str) -> None:
        validate_slug(slug)  # no raise

    @pytest.mark.parametrize(
        "slug",
        [
            "foo-google-x",          # unknown product
            "TPM-linkedin-q2a",      # uppercase
            "tpm_linkedin_q2a",      # underscores
            "tpm-linkedin",          # missing campaign tag
            "tpm-linkedin-q2a-v1-x", # too many segments
            "",
        ],
    )
    def test_invalid(self, slug: str) -> None:
        with pytest.raises(ValueError):
            validate_slug(slug)


class TestUtmCampaignValidator:
    @pytest.mark.parametrize(
        "v",
        [
            "2026_q2_tpm_fmcg_outreach",
            "2026_q1_bas_pricing_relaunch",
            "2099_q4_cross_brand_hero",
        ],
    )
    def test_valid(self, v: str) -> None:
        validate_utm_campaign(v)

    @pytest.mark.parametrize(
        "v",
        [
            "2026-q2-tpm-fmcg",    # hyphens
            "2026_q5_tpm_x",       # invalid quarter
            "26_q2_tpm_x",         # 2-digit year
            "2026_q2_unknown_x",   # unknown product
            "",
        ],
    )
    def test_invalid(self, v: str) -> None:
        with pytest.raises(ValueError):
            validate_utm_campaign(v)
```

- [ ] **Step 2: Create `src/kctl_shlink/core/validators.py`**

```python
"""Slug + utm_campaign regex validators (spec §6.2, §6.3)."""

from __future__ import annotations

import re

SLUG_REGEX = re.compile(r"^(bas|hrm|tpm|tms|agency|careers|cross)-[a-z]+-[a-z0-9]+(-[a-z0-9]+)?$")
UTM_CAMPAIGN_REGEX = re.compile(r"^(20\d{2})_q[1-4]_(bas|hrm|tpm|tms|agency|careers|cross)_[a-z0-9_]+$")


def validate_slug(slug: str) -> None:
    if not SLUG_REGEX.match(slug):
        raise ValueError(
            f"Slug '{slug}' does not match {SLUG_REGEX.pattern}. "
            "Format: <product>-<channel>-<campaign_tag>[-<variant>]"
        )


def validate_utm_campaign(value: str) -> None:
    if not UTM_CAMPAIGN_REGEX.match(value):
        raise ValueError(
            f"utm_campaign '{value}' does not match {UTM_CAMPAIGN_REGEX.pattern}. "
            "Format: <yyyy>_q<n>_<product>_<theme>"
        )
```

- [ ] **Step 3: Run `uv run pytest packages/kctl-shlink/tests/test_validators.py -v`.**

Commit: `feat(kctl-shlink): slug + utm_campaign regex validators`

---

## Task 6: Campaign manifest (Pydantic schema + loader)

- [ ] **Step 1 (TEST FIRST): Create `tests/test_manifest.py`**

```python
from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from kctl_shlink.core.manifest import CampaignManifest, load_manifest


def _write(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "camp.yaml"
    p.write_text(yaml.dump(data))
    return p


def _valid() -> dict:
    return {
        "name": "2026_q2_tpm_fmcg_outreach",
        "product": "tpm",
        "tags": ["tpm", "2026-q2"],
        "domain": "s.kodeme.io",
        "defaults": {"utm": {"campaign": "2026_q2_tpm_fmcg_outreach"}},
        "links": [
            {
                "slug": "tpm-linkedin-q2a",
                "long_url": "https://provetics.com/pricing",
                "utm": {"source": "linkedin", "medium": "paid_social", "content": "ad_a"},
            }
        ],
    }


def test_loader_parses_valid(tmp_path: Path) -> None:
    m = load_manifest(_write(tmp_path, _valid()))
    assert isinstance(m, CampaignManifest)
    assert m.name == "2026_q2_tpm_fmcg_outreach"
    assert m.product == "tpm"
    assert len(m.links) == 1
    assert m.links[0].slug == "tpm-linkedin-q2a"


def test_rejects_bad_slug(tmp_path: Path) -> None:
    data = _valid()
    data["links"][0]["slug"] = "BAD-slug"
    with pytest.raises(ValueError):
        load_manifest(_write(tmp_path, data))


def test_rejects_bad_campaign_name(tmp_path: Path) -> None:
    data = _valid()
    data["name"] = "2026-q2-tpm-fmcg"
    with pytest.raises(ValueError):
        load_manifest(_write(tmp_path, data))


def test_defaults_inherited_to_links(tmp_path: Path) -> None:
    data = _valid()
    m = load_manifest(_write(tmp_path, data))
    # utm.campaign is inherited from defaults
    assert m.links[0].utm.campaign == "2026_q2_tpm_fmcg_outreach"
```

- [ ] **Step 2: Create `src/kctl_shlink/core/manifest.py`**

```python
"""Campaign manifest schema (spec §4.3).

Pydantic 2 model for declarative YAML manifests consumed by `campaigns apply`.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, HttpUrl, field_validator, model_validator

from kctl_shlink.core.validators import validate_slug, validate_utm_campaign


class CampaignUTM(BaseModel):
    source: str
    medium: str
    campaign: str | None = None  # inherited from defaults if None
    content: str
    term: str | None = None


class CampaignQR(BaseModel):
    format: Literal["png", "svg"] = "png"
    size: int = 1000
    margin: Literal["web", "print", "billboard"] = "web"
    logo: Path | None = None
    output: Path


class CampaignLink(BaseModel):
    slug: str
    long_url: HttpUrl
    utm: CampaignUTM
    qr: CampaignQR | None = None
    expire_at: datetime | None = None
    max_visits: int | None = None

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        validate_slug(v)
        return v


class CampaignDefaults(BaseModel):
    utm: dict[str, str] = {}


class CampaignManifest(BaseModel):
    name: str
    product: Literal["bas", "hrm", "tpm", "tms", "agency", "careers", "cross"]
    tags: list[str] = []
    domain: str
    defaults: CampaignDefaults = CampaignDefaults()
    links: list[CampaignLink]

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        # staging prefix "stg_" is allowed per §6.4
        base = v[4:] if v.startswith("stg_") else v
        validate_utm_campaign(base)
        return v

    @model_validator(mode="after")
    def _inherit_defaults(self) -> CampaignManifest:
        default_campaign = self.defaults.utm.get("campaign") or self.name
        for link in self.links:
            if link.utm.campaign is None:
                link.utm.campaign = default_campaign
        return self


def load_manifest(path: Path) -> CampaignManifest:
    data = yaml.safe_load(path.read_text())
    return CampaignManifest.model_validate(data)
```

- [ ] **Step 3: Run `uv run pytest packages/kctl-shlink/tests/test_manifest.py -v`.**

Commit: `feat(kctl-shlink): CampaignManifest Pydantic schema + YAML loader`

---

## Task 7: QR code generation module

- [ ] **Step 1 (TEST FIRST): Create `tests/test_qr.py`**

```python
from __future__ import annotations

from pathlib import Path

import pytest

from kctl_shlink.core.qr import MARGIN_PRESETS, render_qr


def test_margin_presets() -> None:
    assert MARGIN_PRESETS == {"web": 4, "print": 10, "billboard": 20}


def test_png_no_logo(tmp_path: Path) -> None:
    out = tmp_path / "q.png"
    render_qr("https://s.kodeme.io/x", out, fmt="png", size=300, margin="web")
    assert out.exists()
    assert out.stat().st_size > 100


def test_svg(tmp_path: Path) -> None:
    out = tmp_path / "q.svg"
    render_qr("https://s.kodeme.io/x", out, fmt="svg", size=300, margin="print")
    assert out.exists()
    assert b"<svg" in out.read_bytes()


def test_svg_rejects_logo(tmp_path: Path) -> None:
    out = tmp_path / "q.svg"
    logo = tmp_path / "logo.png"
    logo.write_bytes(b"\x89PNG\r\n\x1a\n")
    with pytest.raises(ValueError):
        render_qr("https://x", out, fmt="svg", logo=logo)


def test_png_with_logo(tmp_path: Path) -> None:
    from PIL import Image

    logo = tmp_path / "logo.png"
    Image.new("RGBA", (200, 200), (255, 0, 0, 255)).save(logo)
    out = tmp_path / "q.png"
    render_qr("https://s.kodeme.io/x", out, fmt="png", size=600, margin="print", logo=logo)
    assert out.exists()
```

- [ ] **Step 2: Create `src/kctl_shlink/core/qr.py`**

```python
"""QR code generation (spec §4.3 `qr generate` + `qr bulk`).

Margin presets (quiet-zone modules):
  - web:       4 (default)
  - print:     10 (safe for most printed collateral)
  - billboard: 20 (large-format reliability)

Logo overlay: PNG only, scaled to 22% of image size, centered,
placed over a white backing square for readability.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import qrcode
import qrcode.image.svg
from PIL import Image

MARGIN_PRESETS: dict[str, int] = {"web": 4, "print": 10, "billboard": 20}

QRFormat = Literal["png", "svg"]
QRMargin = Literal["web", "print", "billboard"]


def render_qr(
    url: str,
    output: Path,
    fmt: QRFormat = "png",
    size: int = 1000,
    margin: QRMargin = "web",
    logo: Path | None = None,
) -> Path:
    """Render a QR code for `url` to `output`.

    Returns the absolute path written.
    """
    if fmt == "svg" and logo is not None:
        raise ValueError("Logo overlay is only supported for PNG format")

    output.parent.mkdir(parents=True, exist_ok=True)
    border = MARGIN_PRESETS[margin]

    if fmt == "svg":
        factory = qrcode.image.svg.SvgImage
        qr = qrcode.QRCode(
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            border=border,
            image_factory=factory,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image()
        img.save(str(output))
        return output

    # PNG path
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, border=border)
    qr.add_data(url)
    qr.make(fit=True)
    png = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    png = png.resize((size, size), Image.Resampling.NEAREST)

    if logo is not None:
        logo_img = Image.open(logo).convert("RGBA")
        logo_side = int(size * 0.22)
        logo_img = logo_img.resize((logo_side, logo_side), Image.Resampling.LANCZOS)
        # White backing square slightly larger than logo
        pad = logo_side // 10
        backing_side = logo_side + pad * 2
        backing = Image.new("RGBA", (backing_side, backing_side), (255, 255, 255, 255))
        # Composite
        cx = (size - backing_side) // 2
        cy = (size - backing_side) // 2
        png.paste(backing, (cx, cy), backing)
        lx = (size - logo_side) // 2
        ly = (size - logo_side) // 2
        png.paste(logo_img, (lx, ly), logo_img)

    png.save(output)
    return output
```

- [ ] **Step 3: Run `uv run pytest packages/kctl-shlink/tests/test_qr.py -v`.**

Commit: `feat(kctl-shlink): QR rendering with margin presets + logo overlay`

---

## Task 8: Plausible bridge (lazy import, optional)

- [ ] **Step 1: Create `src/kctl_shlink/core/plausible_bridge.py`**

```python
"""Soft-dependency bridge to kctl-plausible.

Import is deferred until runtime — a missing kctl-plausible module causes
`get_plausible_client(...)` to return None, which callers degrade gracefully
over.
"""

from __future__ import annotations

from typing import Any


def get_plausible_client(profile: str | None) -> Any | None:
    """Return a configured Plausible client or None.

    If kctl-plausible is not installed, or no profile resolves,
    returns None. Callers must treat None as "no cross-join available".
    """
    try:
        from kctl_plausible.core.client import PlausibleClient  # type: ignore[import-not-found]
        from kctl_plausible.core.config import resolve_connection  # type: ignore[import-not-found]
    except ImportError:
        return None

    try:
        url, api_key, _site = resolve_connection(profile_name=profile)
    except Exception:
        return None

    if not url or not api_key:
        return None
    try:
        return PlausibleClient(base_url=url, api_key=api_key)
    except Exception:
        return None


def goal_aggregate(client: Any, site: str, campaign: str, content: str) -> dict[str, int]:
    """Query Plausible for goals firing under (campaign, content)."""
    try:
        filters = f"event:page==/*;event:props:utm_campaign=={campaign};event:props:utm_content=={content}"
        metrics = "visitors,pageviews,events"
        result = client.get(
            "/api/v1/stats/aggregate",
            params={"site_id": site, "filters": filters, "metrics": metrics},
        )
        return result.get("results", {})
    except Exception:
        return {}
```

- [ ] **Step 2: No unit test yet — tested indirectly via `tests/test_reports.py` in Task 17.**

Commit: `feat(kctl-shlink): lazy Plausible bridge for cross-join reports`

---

## Task 9: Tests conftest (shared fixtures)

- [ ] **Step 1: Create `tests/__init__.py`** (empty).

- [ ] **Step 2: Create `tests/conftest.py`**

```python
"""Shared test fixtures for kctl-shlink."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_shlink.cli import app
from kctl_shlink.core.callbacks import AppContext
from kctl_shlink.core.client import ShlinkClient
from kctl_shlink.core.output import Output


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    c = MagicMock(spec=ShlinkClient)
    c.default_domain = "s.test.io"
    c.root_url = "https://s.test.io"
    return c


@pytest.fixture
def mock_output() -> Output:
    return Output(json_mode=False, quiet=True, format="pretty")


@pytest.fixture
def mock_context(mock_client: MagicMock, mock_output: Output) -> AppContext:
    ctx = AppContext(quiet=True)
    ctx._client = mock_client
    ctx._output = mock_output
    return ctx


@pytest.fixture
def cli_app():
    return app


@pytest.fixture
def mock_config(tmp_path: Path):
    config_dir = tmp_path / "kodemeio"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.yaml"
    config_file.write_text(
        "profiles:\n"
        "  kodemeio-kod-infra-shlink:\n"
        "    shlink:\n"
        "      url: https://s.test.io\n"
        "      api_key: test-key-1234\n"
        "      default_domain: s.test.io\n"
    )
    with (
        patch("kctl_shlink.core.config.CONFIG_FILE", config_file),
        patch("kctl_shlink.core.config.CONFIG_DIR", config_dir),
    ):
        yield config_file
```

Commit: `test(kctl-shlink): conftest with shared fixtures`

---

## Task 10: cli.py + smoke tests

- [ ] **Step 1 (TEST FIRST): Create `tests/test_smoke.py`**

```python
from __future__ import annotations

import pytest
from typer.testing import CliRunner

from kctl_shlink import __version__
from kctl_shlink.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestSmoke:
    def test_help(self, runner: CliRunner) -> None:
        r = runner.invoke(app, ["--help"])
        assert r.exit_code == 0
        assert "shlink" in r.output.lower()

    def test_version(self, runner: CliRunner) -> None:
        r = runner.invoke(app, ["--version"])
        assert r.exit_code == 0
        assert __version__ in r.output

    @pytest.mark.parametrize(
        "group",
        [
            "config", "doctor", "domains", "urls", "tags",
            "visits", "qr", "campaigns", "reports", "redirects", "export",
        ],
    )
    def test_group_help(self, runner: CliRunner, group: str) -> None:
        r = runner.invoke(app, [group, "--help"])
        assert r.exit_code == 0
```

- [ ] **Step 2: Create `src/kctl_shlink/cli.py`** (mirroring `kctl-zulip/cli.py`)

```python
"""Main CLI entry point for kctl-shlink."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_shlink import __version__
from kctl_shlink.commands.campaigns import app as campaigns_app
from kctl_shlink.commands.config_cmd import app as config_app
from kctl_shlink.commands.doctor_cmd import app as doctor_app
from kctl_shlink.commands.domains import app as domains_app
from kctl_shlink.commands.export_cmd import app as export_app
from kctl_shlink.commands.qr_cmd import app as qr_app
from kctl_shlink.commands.redirects import app as redirects_app
from kctl_shlink.commands.reports import app as reports_app
from kctl_shlink.commands.skill_cmd import app as skill_app
from kctl_shlink.commands.tags import app as tags_app
from kctl_shlink.commands.urls import app as urls_app
from kctl_shlink.commands.visits import app as visits_app
from kctl_shlink.core.callbacks import AppContext


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-shlink {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-shlink",
    help="Kodemeio Shlink CLI — short URLs, campaigns, QR codes.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


@app.callback()
def main(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q")] = False,
    output_format: Annotated[str, typer.Option("--format", "-f", help="pretty/json/csv/yaml")] = "pretty",
    no_header: Annotated[bool, typer.Option("--no-header")] = False,
    profile: Annotated[str | None, typer.Option("--profile", "-p")] = None,
    url: Annotated[str | None, typer.Option("--url")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True)
    ] = False,
) -> None:
    """Kodemeio Shlink CLI."""
    effective_format = "json" if json_output else output_format
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output or effective_format == "json",
        quiet=quiet,
        format=effective_format,
        no_header=no_header,
        profile=profile,
        url_override=url,
        api_key_override=api_key,
    )


# URLs & taxonomy
app.add_typer(config_app, name="config", rich_help_panel="Admin")
app.add_typer(domains_app, name="domains", rich_help_panel="URLs")
app.add_typer(urls_app, name="urls", rich_help_panel="URLs")
app.add_typer(tags_app, name="tags", rich_help_panel="URLs")
app.add_typer(redirects_app, name="redirects", rich_help_panel="URLs")

# Campaigns & analytics
app.add_typer(campaigns_app, name="campaigns", rich_help_panel="Campaigns")
app.add_typer(qr_app, name="qr", rich_help_panel="Campaigns")
app.add_typer(visits_app, name="visits", rich_help_panel="Analytics")
app.add_typer(reports_app, name="reports", rich_help_panel="Analytics")
app.add_typer(export_app, name="export", rich_help_panel="Analytics")

# Tools
app.add_typer(doctor_app, name="doctor", rich_help_panel="Tools")
app.add_typer(skill_app, name="skill", hidden=True)


@app.command("self-update", rich_help_panel="Tools")
def self_update_cmd(ctx: typer.Context) -> None:
    """Check PyPI for updates and upgrade kctl-shlink."""
    actx = ctx.obj
    out = actx.output
    from kctl_lib.self_update import check_update
    from kctl_lib.self_update import update as do_update

    latest = check_update("kctl-shlink", __version__)
    if latest:
        out.info(f"Updating to {latest}...")
        do_update("kctl-shlink")
        out.success(f"Updated to {latest}")
    else:
        out.success("Already up to date")


@app.command(rich_help_panel="Tools")
def completions(
    shell: Annotated[str, typer.Argument(help="zsh/bash/fish")] = "zsh",
    install: Annotated[bool, typer.Option("--install")] = False,
) -> None:
    """Generate/install shell completions."""
    from kctl_lib.completions import get_completion_script, install_completions

    if install:
        path = install_completions("kctl-shlink", shell)
        if path:
            typer.echo(f"Completions installed to {path}")
        else:
            typer.echo(f"Could not install completions for {shell}", err=True)
            raise typer.Exit(code=1)
    else:
        typer.echo(get_completion_script("kctl-shlink", shell))


def _run() -> None:
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
```

- [ ] **Step 3: Create stub `src/kctl_shlink/commands/__init__.py`** (empty). Create empty stub files for each command module that just define `app = typer.Typer(help="...")` — enough to make imports resolve so smoke tests pass. Each stub will be fleshed out in its own task.

- [ ] **Step 4: Run `uv run pytest packages/kctl-shlink/tests/test_smoke.py -v`.**

Commit: `feat(kctl-shlink): main Typer app + smoke tests`

---

## Task 11: `config` command group

- [ ] **Step 1 (TEST FIRST): Add tests to `tests/test_config.py`** covering `config init --name X --url Y --api-key Z`, `config show` (masked), `config use`, `config remove`, `config profiles`, `config current`, `config validate`, `config set shlink.url=...`.

- [ ] **Step 2: Create `src/kctl_shlink/commands/config_cmd.py`**

Follows `packages/kctl-zulip/src/kctl_zulip/commands/config_cmd.py` pattern. Subcommands: `init`, `add`, `use`, `show` (mask secrets with `first4****last4`), `validate`, `remove`, `set`, `profiles`, `current`. API key mask helper:

```python
def _mask(val: str) -> str:
    if not val:
        return "[dim]not set[/dim]"
    if len(val) <= 8:
        return "****"
    return f"{val[:4]}{'*' * max(0, len(val) - 8)}{val[-4:]}"
```

- [ ] **Step 3: Run tests.**

Commit: `feat(kctl-shlink): config command group`

---

## Task 12: `domains` command group

- [ ] **Step 1 (TEST FIRST): Create `tests/test_domains.py`** with mocked `ShlinkClient.list_domains`, `list_short_urls` (for default detection). Assert table output + JSON mode.

- [ ] **Step 2: Create `src/kctl_shlink/commands/domains.py`**

Commands:
- `domains list` — table: domain, isDefault, redirect_base_url, redirect_regular_404
- `domains add <domain>` — POST `/domains`
- `domains remove <domain>` — DELETE `/domains`
- `domains set-default <domain>` — PATCH — warns user that Shlink's default domain is a service-wide setting

```python
from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib.exceptions import KctlError

from kctl_shlink.core.callbacks import AppContext

app = typer.Typer(help="Manage short URL domains.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    actx: AppContext = ctx.obj
    out = actx.output
    try:
        domains = actx.client.list_domains()
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e
    rows = [
        [d.get("domain", ""), "yes" if d.get("isDefault") else "no", d.get("redirects", {}).get("baseUrlRedirect", "")]
        for d in domains
    ]
    out.table(
        f"{len(rows)} domain(s)",
        [("Domain", "cyan"), ("Default", "green"), ("Base URL redirect", "dim")],
        rows,
        data_for_json=domains,
    )


@app.command()
def add(ctx: typer.Context, domain: Annotated[str, typer.Argument()]) -> None:
    actx: AppContext = ctx.obj
    out = actx.output
    actx.client.post("/domains", json={"domain": domain})
    out.success(f"Domain '{domain}' added")


@app.command()
def remove(ctx: typer.Context, domain: Annotated[str, typer.Argument()]) -> None:
    actx: AppContext = ctx.obj
    out = actx.output
    actx.client.delete("/domains", params={"domain": domain})
    out.success(f"Domain '{domain}' removed")


@app.command("set-default")
def set_default(ctx: typer.Context, domain: Annotated[str, typer.Argument()]) -> None:
    actx: AppContext = ctx.obj
    out = actx.output
    actx.client.patch("/domains/redirects", json={"domain": domain})
    out.success(f"Default domain set to '{domain}'")
```

- [ ] **Step 3: Run tests.**

Commit: `feat(kctl-shlink): domains command group`

---

## Task 13: `urls` command group (auto UTM injection)

- [ ] **Step 1 (TEST FIRST): Create `tests/test_urls.py`**

- Happy path: `urls create https://example.com --slug tpm-linkedin-q2a --source linkedin --medium paid_social --campaign 2026_q2_tpm_fmcg_outreach --content ad_a` → client POST body has `longUrl` with `?utm_source=linkedin&utm_medium=paid_social&...` query appended AND `customSlug=tpm-linkedin-q2a` AND `tags`.
- Slug regex rejection: `--slug BAD-slug` → exit 1, error contains "does not match".
- `urls list --tag tpm` calls client with `tags=["tpm"]`.

- [ ] **Step 2: Create `src/kctl_shlink/commands/urls.py`**

Commands: `list`, `create`, `show <shortCode>`, `update <shortCode>`, `delete <shortCode>`.

`create` auto-injects UTM params into `long_url` query string, validates slug via `validate_slug`, and passes `tags` through.

```python
from __future__ import annotations

from typing import Annotated
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import typer
from kctl_lib.exceptions import KctlError

from kctl_shlink.core.callbacks import AppContext
from kctl_shlink.core.validators import validate_slug, validate_utm_campaign

app = typer.Typer(help="Manage short URLs.")


def _inject_utm(url: str, source: str, medium: str, campaign: str, content: str, term: str | None) -> str:
    parsed = urlparse(url)
    q = dict(parse_qsl(parsed.query))
    q["utm_source"] = source
    q["utm_medium"] = medium
    q["utm_campaign"] = campaign
    q["utm_content"] = content
    if term:
        q["utm_term"] = term
    return urlunparse(parsed._replace(query=urlencode(q)))


@app.command("list")
def list_(
    ctx: typer.Context,
    tag: Annotated[list[str] | None, typer.Option("--tag", "-t")] = None,
    search: Annotated[str | None, typer.Option("--search", "-s")] = None,
    page: Annotated[int, typer.Option("--page")] = 1,
) -> None:
    actx: AppContext = ctx.obj
    out = actx.output
    try:
        urls = actx.client.list_short_urls(page=page, tags=tag, search_term=search)
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e
    rows = [
        [u.get("shortCode", ""), u.get("shortUrl", ""), u.get("longUrl", "")[:60], str(u.get("visitsCount", 0)), ",".join(u.get("tags", []))]
        for u in urls
    ]
    out.table(
        f"{len(rows)} short URL(s)",
        [("Slug", "cyan"), ("Short URL", "green"), ("Long URL", "dim"), ("Visits", "yellow"), ("Tags", "blue")],
        rows,
        data_for_json=urls,
    )


@app.command()
def create(
    ctx: typer.Context,
    long_url: Annotated[str, typer.Argument()],
    slug: Annotated[str, typer.Option("--slug")],
    source: Annotated[str, typer.Option("--source")],
    medium: Annotated[str, typer.Option("--medium")],
    campaign: Annotated[str, typer.Option("--campaign")],
    content: Annotated[str, typer.Option("--content")],
    term: Annotated[str | None, typer.Option("--term")] = None,
    tag: Annotated[list[str] | None, typer.Option("--tag", "-t")] = None,
    domain: Annotated[str | None, typer.Option("--domain")] = None,
) -> None:
    actx: AppContext = ctx.obj
    out = actx.output
    try:
        validate_slug(slug)
        validate_utm_campaign(campaign.removeprefix("stg_"))
    except ValueError as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    final_url = _inject_utm(long_url, source, medium, campaign, content, term)
    body = {"longUrl": final_url, "customSlug": slug, "tags": tag or [], "validateUrl": False}
    if domain:
        body["domain"] = domain
    res = actx.client.create_short_url(body)
    out.success(f"Created {res.get('shortUrl')}")


@app.command()
def show(ctx: typer.Context, slug: Annotated[str, typer.Argument()]) -> None:
    actx: AppContext = ctx.obj
    out = actx.output
    data = actx.client.get_short_url(slug)
    out.detail("Short URL", [("Info", [("Slug", slug), ("Long URL", data.get("longUrl", "")), ("Visits", str(data.get("visitsCount", 0)))])], data_for_json=data)


@app.command()
def update(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument()],
    long_url: Annotated[str | None, typer.Option("--long-url")] = None,
    tag: Annotated[list[str] | None, typer.Option("--tag", "-t")] = None,
) -> None:
    actx: AppContext = ctx.obj
    out = actx.output
    body: dict = {}
    if long_url:
        body["longUrl"] = long_url
    if tag is not None:
        body["tags"] = tag
    actx.client.update_short_url(slug, body)
    out.success(f"Updated '{slug}'")


@app.command()
def delete(ctx: typer.Context, slug: Annotated[str, typer.Argument()], force: Annotated[bool, typer.Option("--force")] = False) -> None:
    actx: AppContext = ctx.obj
    out = actx.output
    if not force:
        typer.confirm(f"Delete '{slug}'?", abort=True)
    actx.client.delete_short_url(slug)
    out.success(f"Deleted '{slug}'")
```

- [ ] **Step 3: Run tests.**

Commit: `feat(kctl-shlink): urls command group with UTM auto-injection`

---

## Task 14: `tags` command group

- [ ] **Step 1 (TEST FIRST): Create `tests/test_tags.py`** — `list`, `list --with-stats`, `create`, `rename`, `delete`, `stats`.

- [ ] **Step 2: Create `src/kctl_shlink/commands/tags.py`** with subcommands:

- `list [--with-stats]` — GET `/tags`
- `create <tag>` — POST `/short-urls/{ignored}/tags` is not supported; instead create a throwaway URL or reject. Shlink auto-creates tags. Document: "Tags are auto-created when first assigned to a short URL; use `kctl-shlink urls create --tag X` to create tag X." This command is a help-only alias.
- `rename <old> <new>` — PUT `/tags`
- `delete <tag>` — DELETE `/tags`
- `stats <tag>` — GET `/tags` with stats filter

Commit: `feat(kctl-shlink): tags command group`

---

## Task 15: `visits` command group

- [ ] **Step 1 (TEST FIRST): Create `tests/test_visits.py`**

- [ ] **Step 2: Create `src/kctl_shlink/commands/visits.py`**

Commands:
- `visits list [--slug X | --tag Y] [--start YYYY-MM-DD] [--end YYYY-MM-DD]`
- `visits stats` — global summary
- `visits realtime [--window 5m]` — polls and prints last N visits
- `visits by-tag <tag>` — paginated visits + aggregate
- `visits by-url <slug>`
- `visits orphans` — `/visits/orphan`

Commit: `feat(kctl-shlink): visits command group`

---

## Task 16: `qr` command group

- [ ] **Step 1 (TEST FIRST): Extend `tests/test_qr.py`** with CLI tests via `runner`:
  - `qr generate tpm-linkedin-q2a --out /tmp/x.png --margin print` — mock client returns `shortUrl`.
  - `qr bulk -f camp.yaml --out ./print/` — generates N files, one per link.

- [ ] **Step 2: Create `src/kctl_shlink/commands/qr_cmd.py`**

```python
from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from kctl_shlink.core.callbacks import AppContext
from kctl_shlink.core.manifest import load_manifest
from kctl_shlink.core.qr import render_qr

app = typer.Typer(help="Generate QR codes.")


@app.command()
def generate(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument()],
    out: Annotated[Path, typer.Option("--out", "-o")],
    fmt: Annotated[str, typer.Option("--format", "-f")] = "png",
    size: Annotated[int, typer.Option("--size")] = 1000,
    margin: Annotated[str, typer.Option("--margin")] = "web",
    logo: Annotated[Path | None, typer.Option("--logo")] = None,
) -> None:
    """Generate a QR code for a single short URL."""
    actx: AppContext = ctx.obj
    data = actx.client.get_short_url(slug)
    short_url = data.get("shortUrl") or f"https://{actx.client.default_domain}/{slug}"
    render_qr(short_url, out, fmt=fmt, size=size, margin=margin, logo=logo)  # type: ignore[arg-type]
    actx.output.success(f"QR written to {out}")


@app.command()
def bulk(
    ctx: typer.Context,
    manifest: Annotated[list[Path], typer.Option("--file", "-f")],
    out_dir: Annotated[Path, typer.Option("--out", "-o")],
) -> None:
    """Generate QR codes for every link in the manifest(s)."""
    actx: AppContext = ctx.obj
    out = actx.output
    out_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for path in manifest:
        m = load_manifest(path)
        for link in m.links:
            if link.qr is None:
                continue
            target = out_dir / link.qr.output
            short_url = f"https://{m.domain}/{link.slug}"
            render_qr(short_url, target, fmt=link.qr.format, size=link.qr.size, margin=link.qr.margin, logo=link.qr.logo)
            count += 1
    out.success(f"Generated {count} QR code(s)")
```

- [ ] **Step 3: Run tests.**

Commit: `feat(kctl-shlink): qr command group`

---

## Task 17: `campaigns apply/diff/destroy/list` — idempotent manifest

- [ ] **Step 1 (TEST FIRST): Create `tests/test_campaigns.py`**

```python
from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from typer.testing import CliRunner

from kctl_shlink.cli import app


def _write_manifest(tmp_path: Path) -> Path:
    p = tmp_path / "c.yaml"
    p.write_text(dedent("""
        name: 2026_q2_tpm_fmcg_outreach
        product: tpm
        tags: [tpm, 2026-q2]
        domain: s.test.io
        defaults: {utm: {campaign: 2026_q2_tpm_fmcg_outreach}}
        links:
          - slug: tpm-linkedin-q2a
            long_url: https://provetics.com/pricing
            utm: {source: linkedin, medium: paid_social, content: ad_a}
          - slug: tpm-linkedin-q2b
            long_url: https://provetics.com/pricing
            utm: {source: linkedin, medium: paid_social, content: ad_b}
    """))
    return p


def test_apply_dry_run(runner, tmp_path, mock_client, monkeypatch):
    from kctl_shlink.core.callbacks import AppContext
    manifest = _write_manifest(tmp_path)

    # Simulate zero existing URLs
    mock_client.list_short_urls.return_value = []

    def _inject(*args, **kwargs):
        import typer
        actx = AppContext(quiet=True)
        actx._client = mock_client
        typer.Context = typer.Context  # no-op

    # Direct command invocation via runner: needs full DI, so use a helper
    # exposed by cli.py; alternatively, test the planner pure-fn (see below).


def test_planner_detects_creates(tmp_path, mock_client):
    from kctl_shlink.commands.campaigns import compute_plan
    from kctl_shlink.core.manifest import load_manifest

    m = load_manifest(_write_manifest(tmp_path))
    existing: list[dict] = []
    plan = compute_plan(m, existing)
    assert [a["slug"] for a in plan["create"]] == ["tpm-linkedin-q2a", "tpm-linkedin-q2b"]
    assert plan["update"] == []
    assert plan["delete"] == []


def test_planner_detects_noop(tmp_path, mock_client):
    from kctl_shlink.commands.campaigns import compute_plan
    from kctl_shlink.core.manifest import load_manifest

    m = load_manifest(_write_manifest(tmp_path))
    existing = [
        {
            "shortCode": "tpm-linkedin-q2a",
            "longUrl": "https://provetics.com/pricing?utm_source=linkedin&utm_medium=paid_social&utm_campaign=2026_q2_tpm_fmcg_outreach&utm_content=ad_a",
            "tags": ["tpm", "2026-q2"],
            "domain": "s.test.io",
        },
        {
            "shortCode": "tpm-linkedin-q2b",
            "longUrl": "https://provetics.com/pricing?utm_source=linkedin&utm_medium=paid_social&utm_campaign=2026_q2_tpm_fmcg_outreach&utm_content=ad_b",
            "tags": ["tpm", "2026-q2"],
            "domain": "s.test.io",
        },
    ]
    plan = compute_plan(m, existing)
    assert plan["create"] == []
    assert plan["update"] == []
    assert plan["delete"] == []
    assert len(plan["noop"]) == 2


def test_apply_idempotent(tmp_path, mock_client):
    from kctl_shlink.commands.campaigns import compute_plan, execute_plan
    from kctl_shlink.core.manifest import load_manifest

    m = load_manifest(_write_manifest(tmp_path))
    mock_client.list_short_urls.return_value = []
    plan = compute_plan(m, [])
    execute_plan(mock_client, plan)

    # Now "existing" = what was created
    after = [
        {"shortCode": a["slug"], "longUrl": a["body"]["longUrl"], "tags": a["body"]["tags"], "domain": "s.test.io"}
        for a in plan["create"]
    ]
    plan2 = compute_plan(m, after)
    assert plan2["create"] == []
    assert plan2["update"] == []
    assert len(plan2["noop"]) == 2
```

- [ ] **Step 2: Create `src/kctl_shlink/commands/campaigns.py`**

```python
"""Declarative campaign manifest apply (spec §4.3).

Pure-function planner + executor so idempotency is testable without CLI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import typer
from kctl_lib.exceptions import KctlError

from kctl_shlink.core.callbacks import AppContext
from kctl_shlink.core.manifest import CampaignLink, CampaignManifest, load_manifest

app = typer.Typer(help="Declarative campaign manifest management.")


def _render_long_url(link: CampaignLink) -> str:
    parsed = urlparse(str(link.long_url))
    q = dict(parse_qsl(parsed.query))
    q["utm_source"] = link.utm.source
    q["utm_medium"] = link.utm.medium
    if link.utm.campaign:
        q["utm_campaign"] = link.utm.campaign
    q["utm_content"] = link.utm.content
    if link.utm.term:
        q["utm_term"] = link.utm.term
    return urlunparse(parsed._replace(query=urlencode(q)))


def _canonical_tags(manifest_tags: list[str]) -> list[str]:
    return sorted({t for t in manifest_tags})


def _long_url_matches(a: str, b: str) -> bool:
    pa, pb = urlparse(a), urlparse(b)
    return (pa.scheme, pa.netloc, pa.path) == (pb.scheme, pb.netloc, pb.path) and dict(parse_qsl(pa.query)) == dict(parse_qsl(pb.query))


def compute_plan(manifest: CampaignManifest, existing: list[dict]) -> dict[str, list[dict]]:
    """Compute create/update/delete/noop for a manifest vs the current state."""
    by_slug = {u.get("shortCode", ""): u for u in existing}
    desired_slugs: set[str] = set()
    plan: dict[str, list[dict]] = {"create": [], "update": [], "delete": [], "noop": []}

    wanted_tags = _canonical_tags(manifest.tags)

    for link in manifest.links:
        desired_slugs.add(link.slug)
        body = {
            "longUrl": _render_long_url(link),
            "customSlug": link.slug,
            "tags": wanted_tags,
            "domain": manifest.domain,
            "validateUrl": False,
        }
        if link.expire_at:
            body["validSince"] = None
            body["validUntil"] = link.expire_at.isoformat()
        if link.max_visits is not None:
            body["maxVisits"] = link.max_visits

        actual = by_slug.get(link.slug)
        if actual is None:
            plan["create"].append({"slug": link.slug, "body": body, "qr": link.qr})
            continue

        if (
            _long_url_matches(actual.get("longUrl", ""), body["longUrl"])
            and sorted(actual.get("tags", [])) == wanted_tags
        ):
            plan["noop"].append({"slug": link.slug})
        else:
            plan["update"].append({"slug": link.slug, "body": {k: v for k, v in body.items() if k != "customSlug"}})

    # Delete: existing URLs matching ALL manifest tags that are NOT in desired
    tag_set = set(wanted_tags)
    for u in existing:
        slug = u.get("shortCode", "")
        if slug in desired_slugs:
            continue
        if tag_set.issubset(set(u.get("tags", []))):
            plan["delete"].append({"slug": slug})

    return plan


def execute_plan(client: Any, plan: dict[str, list[dict]]) -> None:
    for action in plan["create"]:
        client.create_short_url(action["body"])
    for action in plan["update"]:
        client.update_short_url(action["slug"], action["body"])
    for action in plan["delete"]:
        client.delete_short_url(action["slug"])


def _fetch_existing(client: Any, manifest: CampaignManifest) -> list[dict]:
    return client.list_short_urls(tags=manifest.tags, items_per_page=200)


@app.command()
def apply(
    ctx: typer.Context,
    manifest_path: Annotated[Path, typer.Option("--file", "-f")],
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """Apply a campaign manifest (idempotent)."""
    actx: AppContext = ctx.obj
    out = actx.output
    try:
        m = load_manifest(manifest_path)
    except ValueError as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    existing = _fetch_existing(actx.client, m)
    plan = compute_plan(m, existing)
    _render_plan(out, plan, dry_run)

    if dry_run:
        return

    try:
        execute_plan(actx.client, plan)
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e
    out.success(f"Applied: +{len(plan['create'])} ~{len(plan['update'])} -{len(plan['delete'])} ={len(plan['noop'])}")


@app.command()
def diff(ctx: typer.Context, manifest_path: Annotated[Path, typer.Option("--file", "-f")]) -> None:
    """Show what `apply` would change (alias for `apply --dry-run`)."""
    apply.callback(ctx, manifest_path, dry_run=True)  # type: ignore[union-attr]


@app.command()
def destroy(
    ctx: typer.Context,
    manifest_path: Annotated[Path, typer.Option("--file", "-f")],
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Delete every short URL declared in the manifest."""
    actx: AppContext = ctx.obj
    out = actx.output
    m = load_manifest(manifest_path)
    if not force:
        typer.confirm(f"Destroy {len(m.links)} short URL(s)?", abort=True)
    for link in m.links:
        try:
            actx.client.delete_short_url(link.slug)
        except KctlError:
            pass
    out.success(f"Destroyed {len(m.links)} short URL(s)")


@app.command("list")
def list_(
    ctx: typer.Context,
    manifest_dir: Annotated[Path, typer.Option("--dir", "-d")] = Path("deploys/marketing/shlink-campaigns"),
) -> None:
    """List all campaign manifests in a directory."""
    actx: AppContext = ctx.obj
    out = actx.output
    rows = []
    for path in sorted(manifest_dir.glob("*.yaml")):
        try:
            m = load_manifest(path)
            rows.append([m.name, m.product, str(len(m.links)), m.domain, str(path)])
        except Exception as e:
            rows.append([path.stem, "?", "?", "?", f"ERROR: {e}"])
    out.table(
        f"{len(rows)} campaign manifest(s)",
        [("Name", "cyan"), ("Product", "magenta"), ("Links", "yellow"), ("Domain", "green"), ("Path", "dim")],
        rows,
    )


def _render_plan(out, plan: dict[str, list[dict]], dry_run: bool) -> None:
    header = "Plan (dry-run)" if dry_run else "Plan"
    sections = [
        ("Create", [(a["slug"], a["body"]["longUrl"]) for a in plan["create"]]),
        ("Update", [(a["slug"], a["body"].get("longUrl", "")) for a in plan["update"]]),
        ("Delete", [(a["slug"], "") for a in plan["delete"]]),
        ("No-op", [(a["slug"], "") for a in plan["noop"]]),
    ]
    out.detail(header, sections)
```

- [ ] **Step 3: Run `uv run pytest packages/kctl-shlink/tests/test_campaigns.py -v`.**

Commit: `feat(kctl-shlink): campaigns apply/diff/destroy/list with idempotent planner`

---

## Task 18: `reports` command group (Shlink × Plausible cross-join)

- [ ] **Step 1 (TEST FIRST): Create `tests/test_reports.py`**

```python
from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_shlink.commands import reports as reports_mod


def test_campaign_report_without_plausible(runner: CliRunner, mock_client):
    """If kctl-plausible unavailable, print click columns only."""
    mock_client.list_short_urls.return_value = [
        {"shortCode": "tpm-linkedin-q2a", "tags": ["tpm"], "visitsCount": 120, "longUrl": "https://x?utm_content=ad_a"},
        {"shortCode": "tpm-linkedin-q2b", "tags": ["tpm"], "visitsCount": 80, "longUrl": "https://x?utm_content=ad_b"},
    ]
    with patch("kctl_shlink.commands.reports.get_plausible_client", return_value=None):
        rows = reports_mod.build_campaign_rows(mock_client, "2026_q2_tpm_fmcg_outreach", plausible_profile=None, site=None)
    assert [r["slug"] for r in rows] == ["tpm-linkedin-q2a", "tpm-linkedin-q2b"]
    assert all("pv" not in r for r in rows)  # no Plausible columns


def test_campaign_report_with_plausible(runner: CliRunner, mock_client):
    mock_client.list_short_urls.return_value = [
        {"shortCode": "tpm-linkedin-q2a", "tags": ["tpm"], "visitsCount": 120, "longUrl": "https://x?utm_content=ad_a"},
    ]
    mock_plausible = MagicMock()
    mock_plausible.get.return_value = {"results": {"pageviews": {"value": 95}, "visitors": {"value": 70}}}

    with (
        patch("kctl_shlink.commands.reports.get_plausible_client", return_value=mock_plausible),
        patch("kctl_shlink.commands.reports.goal_aggregate", return_value={"pageviews": 95, "visitors": 70, "demo_request": 6, "trial_start": 2, "paid": 1}),
    ):
        rows = reports_mod.build_campaign_rows(mock_client, "2026_q2_tpm_fmcg_outreach", plausible_profile="p", site="provetics.com")
    assert rows[0]["pv"] == 95
    assert rows[0]["demo_request"] == 6
    assert rows[0]["paid"] == 1
```

- [ ] **Step 2: Create `src/kctl_shlink/commands/reports.py`**

```python
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any
from urllib.parse import parse_qs, urlparse

import typer

from kctl_shlink.core.callbacks import AppContext
from kctl_shlink.core.manifest import load_manifest
from kctl_shlink.core.plausible_bridge import get_plausible_client, goal_aggregate

app = typer.Typer(help="Cross-join reports.")


GOAL_NAMES = ["demo_request", "trial_start", "paid"]


def _extract_utm_content(long_url: str) -> str:
    q = parse_qs(urlparse(long_url).query)
    return q.get("utm_content", [""])[0]


def build_campaign_rows(
    client: Any,
    campaign: str,
    plausible_profile: str | None,
    site: str | None,
) -> list[dict]:
    """Return one row per short URL matching campaign tag, optionally joined with Plausible."""
    urls = client.list_short_urls(items_per_page=500, tags=[campaign.split("_", 2)[-1][:10]] if False else None)
    # Filter to those whose longUrl has utm_campaign == campaign
    matching = []
    for u in urls:
        q = parse_qs(urlparse(u.get("longUrl", "")).query)
        if q.get("utm_campaign", [""])[0] == campaign:
            matching.append(u)

    plausible = get_plausible_client(plausible_profile) if plausible_profile else None

    rows: list[dict] = []
    for u in matching:
        content = _extract_utm_content(u.get("longUrl", ""))
        row: dict = {
            "slug": u.get("shortCode", ""),
            "channel": content,
            "clicks": u.get("visitsCount", 0),
            "unique": u.get("visitsCount", 0),  # Shlink reports total == unique by default
        }
        if plausible and site:
            agg = goal_aggregate(plausible, site, campaign, content)
            row["pv"] = int(agg.get("pageviews", 0))
            for goal in GOAL_NAMES:
                row[goal] = int(agg.get(goal, 0))
        rows.append(row)

    return rows


@app.command()
def campaign(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="utm_campaign value")],
    site: Annotated[str | None, typer.Option("--site", help="Plausible site_id")] = None,
    plausible_profile: Annotated[str | None, typer.Option("--plausible-profile")] = None,
) -> None:
    """Cross-join Shlink clicks with Plausible goals for a campaign."""
    actx: AppContext = ctx.obj
    out = actx.output

    rows = build_campaign_rows(actx.client, name, plausible_profile, site)

    if not rows:
        out.warn(f"No short URLs matched utm_campaign={name}")
        return

    has_plausible = "pv" in rows[0]
    if has_plausible:
        cols = [("Slug", "cyan"), ("Channel", "blue"), ("Clicks", "yellow"), ("Unique", "yellow"),
                ("PV", "green"), ("demo_request", "magenta"), ("trial_start", "magenta"), ("paid", "red")]
        table_rows = [
            [r["slug"], r["channel"], str(r["clicks"]), str(r["unique"]),
             str(r.get("pv", 0)), str(r.get("demo_request", 0)), str(r.get("trial_start", 0)), str(r.get("paid", 0))]
            for r in rows
        ]
    else:
        out.warn("kctl-plausible not available — showing click columns only")
        cols = [("Slug", "cyan"), ("Channel", "blue"), ("Clicks", "yellow"), ("Unique", "yellow")]
        table_rows = [[r["slug"], r["channel"], str(r["clicks"]), str(r["unique"])] for r in rows]

    out.table(f"Campaign {name}", cols, table_rows, data_for_json=rows)


@app.command()
def channel(
    ctx: typer.Context,
    source: Annotated[str, typer.Argument(help="utm_source to filter")],
    days: Annotated[int, typer.Option("--days")] = 30,
) -> None:
    """Aggregate clicks by utm_source across all campaigns."""
    actx: AppContext = ctx.obj
    urls = actx.client.list_short_urls(items_per_page=500)
    rows = []
    for u in urls:
        q = parse_qs(urlparse(u.get("longUrl", "")).query)
        if q.get("utm_source", [""])[0] == source:
            rows.append([u.get("shortCode", ""), q.get("utm_campaign", [""])[0], str(u.get("visitsCount", 0))])
    actx.output.table(f"Channel {source}", [("Slug", "cyan"), ("Campaign", "blue"), ("Clicks", "yellow")], rows)


@app.command()
def product(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="bas|hrm|tpm|tms|agency|careers")],
) -> None:
    """Aggregate clicks by product code (slug prefix)."""
    actx: AppContext = ctx.obj
    urls = actx.client.list_short_urls(items_per_page=500)
    rows = []
    for u in urls:
        slug = u.get("shortCode", "")
        if slug.startswith(f"{name}-"):
            rows.append([slug, str(u.get("visitsCount", 0)), ",".join(u.get("tags", []))])
    actx.output.table(f"Product {name}", [("Slug", "cyan"), ("Clicks", "yellow"), ("Tags", "dim")], rows)


@app.command()
def compare(
    ctx: typer.Context,
    manifest_a: Annotated[Path, typer.Option("--a")],
    manifest_b: Annotated[Path, typer.Option("--b")],
) -> None:
    """Compare clicks between two campaign manifests side-by-side."""
    actx: AppContext = ctx.obj
    a = load_manifest(manifest_a)
    b = load_manifest(manifest_b)
    rows_a = build_campaign_rows(actx.client, a.name, None, None)
    rows_b = build_campaign_rows(actx.client, b.name, None, None)
    total_a = sum(r["clicks"] for r in rows_a)
    total_b = sum(r["clicks"] for r in rows_b)
    actx.output.table(
        "Campaign comparison",
        [("Name", "cyan"), ("Links", "yellow"), ("Total clicks", "green")],
        [[a.name, str(len(rows_a)), str(total_a)], [b.name, str(len(rows_b)), str(total_b)]],
    )
```

- [ ] **Step 3: Run tests.**

Commit: `feat(kctl-shlink): reports with Shlink × Plausible cross-join`

---

## Task 19: `redirects` command group (device-based)

- [ ] **Step 1 (TEST FIRST): Create `tests/test_redirects.py`**

- [ ] **Step 2: Create `src/kctl_shlink/commands/redirects.py`**

Commands:
- `redirects list <slug>` — GET short URL → show `deviceLongUrls` (iOS / Android / desktop)
- `redirects set <slug> --ios URL --android URL --desktop URL`
- `redirects clear <slug> [--ios|--android|--desktop]`

Shlink endpoint: PATCH `/short-urls/{shortCode}` body includes `deviceLongUrls: {ios, android, desktop}`.

Commit: `feat(kctl-shlink): redirects command group (device-based)`

---

## Task 20: `export` command group

- [ ] **Step 1 (TEST FIRST): Create `tests/test_export.py`**

- [ ] **Step 2: Create `src/kctl_shlink/commands/export_cmd.py`**

Commands:
- `export csv [--out path] [--tag X]` — iterate `list_short_urls`, write CSV: shortCode, shortUrl, longUrl, tags, visitsCount, dateCreated
- `export json [--out path] [--tag X]`

Commit: `feat(kctl-shlink): export command group`

---

## Task 21: `doctor` command

- [ ] **Step 1 (TEST FIRST): Create `tests/test_doctor.py`** — mock each check's dependencies, assert each returns a `CheckResult`.

- [ ] **Step 2: Create `src/kctl_shlink/commands/doctor_cmd.py`**

Checks:
1. `ConfigCheck` — profile has `url` + `api_key`
2. `APIReachabilityCheck` — `GET /rest/health` returns `status=pass`
3. `TLSCheck` — `kctl_lib.monitor_base.ssl_check(default_domain)` returns days-until-expiry ≥ 14
4. `DNSCheck` — configured domains resolve to expected Shlink public IP (fetched by reverse-resolving `default_domain`)
5. `InventoryCheck` — count short URLs (GET `/short-urls?itemsPerPage=1` reports `pagination.totalItems`) + count tags
6. `PlausibleBridgeCheck` — `get_plausible_client(profile)`; warn if None (not fail)
7. `FreshnessCheck` — visits summary `last_visit` timestamp < 1 hour old; warn if stale (not fail)

```python
"""Doctor diagnostic checks for kctl-shlink."""

from __future__ import annotations

import socket
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
import typer

from kctl_lib.doctor_base import CheckResult, DoctorCheck, run_doctor
from kctl_lib.monitor_base import ssl_check

from kctl_shlink.core.callbacks import AppContext


@dataclass
class ConfigCheck:
    name: str = "Configuration"

    def run(self) -> CheckResult:
        try:
            from kctl_shlink.core.config import get_service_config, resolve_active_profile_name
            profile = resolve_active_profile_name()
            cfg = get_service_config(profile)
            if not cfg.url or not cfg.api_key:
                return CheckResult(
                    name=self.name, status="fail", message="Missing url or api_key",
                    fix_command="kctl-shlink config init",
                )
            return CheckResult(name=self.name, status="ok", message=f"Profile '{profile}' -> {cfg.url}")
        except Exception as e:
            return CheckResult(name=self.name, status="fail", message=str(e))


@dataclass
class APIReachabilityCheck:
    name: str = "API Reachability"

    def run(self) -> CheckResult:
        try:
            from kctl_shlink.core.config import get_service_config, resolve_active_profile_name
            cfg = get_service_config(resolve_active_profile_name())
            r = httpx.get(f"{cfg.url.rstrip('/')}/rest/health", timeout=5)
            if r.status_code == 200 and r.json().get("status") == "pass":
                return CheckResult(name=self.name, status="ok", message=f"Shlink {r.json().get('version')} responding")
            return CheckResult(name=self.name, status="fail", message=f"Health endpoint returned {r.status_code}")
        except Exception as e:
            return CheckResult(name=self.name, status="fail", message=str(e))


@dataclass
class TLSCheck:
    name: str = "Default Domain TLS"

    def run(self) -> CheckResult:
        try:
            from kctl_shlink.core.config import get_service_config, resolve_active_profile_name
            cfg = get_service_config(resolve_active_profile_name())
            days = ssl_check(cfg.default_domain or cfg.url.replace("https://", ""))
            if days is None:
                return CheckResult(name=self.name, status="warn", message="Cert check unavailable")
            if days < 14:
                return CheckResult(name=self.name, status="warn", message=f"Cert expires in {days} days")
            return CheckResult(name=self.name, status="ok", message=f"Cert valid for {days} days")
        except Exception as e:
            return CheckResult(name=self.name, status="warn", message=str(e))


@dataclass
class DNSCheck:
    name: str = "Domain DNS"

    def run(self) -> CheckResult:
        try:
            from kctl_shlink.core.callbacks import AppContext as _AC
            from kctl_shlink.core.config import get_service_config, resolve_active_profile_name
            cfg = get_service_config(resolve_active_profile_name())
            default_ip = socket.gethostbyname(cfg.default_domain or cfg.url.replace("https://", ""))
            # Fetch configured domains
            client = _AC(profile=resolve_active_profile_name()).client
            mismatches = []
            for d in client.list_domains():
                name = d.get("domain", "")
                if not name:
                    continue
                try:
                    ip = socket.gethostbyname(name)
                    if ip != default_ip:
                        mismatches.append(f"{name}={ip}")
                except socket.gaierror:
                    mismatches.append(f"{name}=NXDOMAIN")
            if mismatches:
                return CheckResult(name=self.name, status="warn", message=f"Mismatches: {', '.join(mismatches)}")
            return CheckResult(name=self.name, status="ok", message=f"All domains → {default_ip}")
        except Exception as e:
            return CheckResult(name=self.name, status="warn", message=str(e))


@dataclass
class InventoryCheck:
    name: str = "Short URL Inventory"

    def run(self) -> CheckResult:
        try:
            from kctl_shlink.core.callbacks import AppContext as _AC
            from kctl_shlink.core.config import resolve_active_profile_name
            client = _AC(profile=resolve_active_profile_name()).client
            resp = client.get("/short-urls", params={"itemsPerPage": 1})
            total = resp.get("shortUrls", {}).get("pagination", {}).get("totalItems", 0)
            tags = len(client.list_tags())
            return CheckResult(name=self.name, status="ok", message=f"{total} short URLs, {tags} tags")
        except Exception as e:
            return CheckResult(name=self.name, status="warn", message=str(e))


@dataclass
class PlausibleBridgeCheck:
    name: str = "kctl-plausible Bridge"

    def run(self) -> CheckResult:
        try:
            from kctl_shlink.core.plausible_bridge import get_plausible_client
            client = get_plausible_client(None)
            if client is None:
                return CheckResult(
                    name=self.name, status="warn",
                    message="Not available — cross-join reports disabled",
                    fix_command="uv tool install kctl-plausible && kctl-plausible config init",
                )
            return CheckResult(name=self.name, status="ok", message="Plausible client available for cross-join")
        except Exception as e:
            return CheckResult(name=self.name, status="warn", message=str(e))


@dataclass
class FreshnessCheck:
    name: str = "Visit Data Freshness"

    def run(self) -> CheckResult:
        try:
            from kctl_shlink.core.callbacks import AppContext as _AC
            from kctl_shlink.core.config import resolve_active_profile_name
            client = _AC(profile=resolve_active_profile_name()).client
            urls = client.list_short_urls(items_per_page=50)
            latest = max(
                (u.get("dateCreated", "") for u in urls if u.get("visitsCount", 0) > 0),
                default="",
            )
            if not latest:
                return CheckResult(name=self.name, status="warn", message="No recent visits recorded")
            ts = datetime.fromisoformat(latest.replace("Z", "+00:00"))
            age = datetime.now(timezone.utc) - ts
            if age.total_seconds() > 3600:
                return CheckResult(name=self.name, status="warn", message=f"Newest visited URL is {age} old")
            return CheckResult(name=self.name, status="ok", message=f"Fresh data within {age.total_seconds():.0f}s")
        except Exception as e:
            return CheckResult(name=self.name, status="warn", message=str(e))


app = typer.Typer(help="Diagnostic checks.", no_args_is_help=False, invoke_without_command=True)


@app.callback(invoke_without_command=True)
def doctor(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return
    actx: AppContext = ctx.obj
    out = actx.output

    from kctl_lib.doctor_base import DoctorCheck as _DC
    from kctl_lib.doctor_base import PythonCheck, UvCheck, GitCheck, DockerCheck

    checks: list[_DC] = [
        PythonCheck(),
        UvCheck(),
        GitCheck(),
        DockerCheck(),
        ConfigCheck(),
        APIReachabilityCheck(),
        TLSCheck(),
        DNSCheck(),
        InventoryCheck(),
        PlausibleBridgeCheck(),
        FreshnessCheck(),
    ]
    if not run_doctor(checks, out):  # type: ignore[arg-type]
        raise typer.Exit(code=1)
```

- [ ] **Step 3: Run tests.**

Commit: `feat(kctl-shlink): doctor command with TLS/DNS/freshness/Plausible-bridge checks`

---

## Task 22: `skill generate` command

- [ ] **Step 1: Create `skills/shlink-admin/SKILL.extra.md`** with hand-written runbook:
  - Profile setup cheat-sheet
  - Common workflows (apply a campaign, generate QR for booth, read a Q2 report)
  - Taxonomy reminder link to `docs/marketing/taxonomy.md`
  - Soft-dependency note on kctl-plausible

- [ ] **Step 2: Create `src/kctl_shlink/commands/skill_cmd.py`** (mirror `packages/kctl-zulip/src/kctl_zulip/commands/skill_cmd.py`) — `skill_name = "shlink-admin"`, `description = "Shlink short URL + campaign administration via kctl-shlink CLI"`.

- [ ] **Step 3: Generate the initial SKILL.md** — `uv run kctl-shlink skill generate`.

Commit: `feat(kctl-shlink): skill generate + shlink-admin SKILL extras`

---

## Task 23: Example campaign manifest + README

- [ ] **Step 1: Create `deploys/marketing/shlink-campaigns/example-tpm-linkedin-q2.yaml`**

```yaml
name: 2026_q2_tpm_fmcg_outreach
product: tpm
tags: [tpm, 2026-q2, linkedin]
domain: s.kodeme.io
defaults:
  utm:
    campaign: 2026_q2_tpm_fmcg_outreach
links:
  - slug: tpm-linkedin-q2a
    long_url: https://provetics.com/pricing
    utm:
      source: linkedin
      medium: paid_social
      content: ad_a
    qr:
      format: png
      size: 1000
      margin: print
      output: tpm-linkedin-q2a.png
  - slug: tpm-linkedin-q2b
    long_url: https://provetics.com/pricing
    utm:
      source: linkedin
      medium: paid_social
      content: ad_b
    qr:
      format: png
      size: 1000
      margin: print
      output: tpm-linkedin-q2b.png
```

- [ ] **Step 2: Create `packages/kctl-shlink/README.md`** (≥ 60 lines):
  - Install (`uv tool install kctl-shlink`)
  - Quick start: `config init`, `doctor`, `campaigns apply`
  - Command reference table (by group)
  - Campaign manifest schema — full YAML example
  - QR generation recipes (booth poster, digital ad, billboard)
  - Shlink × Plausible cross-join reporting
  - Taxonomy link (spec §6)
  - Troubleshooting

- [ ] **Step 3: Create `packages/kctl-shlink/CHANGELOG.md`** with `## 0.1.0 - 2026-04-19` (initial release).

Commit: `docs(kctl-shlink): README + CHANGELOG + example campaign manifest`

---

## Task 24: Wire CI + workspace integration

- [ ] **Step 1: Modify `.github/workflows/ci.yml`**

Add `kctl-shlink` to the matrix list of packages that run `ruff`, `mypy`, `pytest`.

- [ ] **Step 2: Modify root `CLAUDE.md`** — add one row to the packages table:

```
| `packages/kctl-shlink/` | Shlink short URL + campaign CLI |
```

And append `kctl-shlink` to the "Marketing & Ads" section if present, else the "Developer & SaaS Tools" list.

- [ ] **Step 3: Run `uv sync --all-extras --all-packages`** and verify `kctl-shlink` shows in `uv tool list`.

Commit: `chore(kctl-shlink): wire into CI matrix + workspace CLAUDE.md`

---

## Task 25: Quality gates — lint, type, test, coverage

- [ ] **Step 1: Ruff**

```bash
uv run ruff check packages/kctl-shlink/src/ packages/kctl-shlink/tests/
uv run ruff format --check packages/kctl-shlink/
```

Fix all violations; re-run.

- [ ] **Step 2: Mypy strict**

```bash
cd packages/kctl-shlink && uv run mypy src/
```

Must be zero errors. Add `# type: ignore[...]` only for `kctl_plausible` soft-import lines (justified via comment).

- [ ] **Step 3: Pytest + coverage**

```bash
uv run pytest packages/kctl-shlink/tests/ -v --cov=kctl_shlink --cov-report=term-missing
```

Coverage threshold: ≥ 60% lines. Commands-per-test ratio ≥ 0.3 per `scripts/audit-platform.py`. Roughly ~30 commands → ≥ 10 test files (we have 14 test files).

Commit if any fixes were needed: `fix(kctl-shlink): resolve lint/mypy/coverage gaps`

---

## Task 26: Audit score verification (≥ 9/10)

- [ ] **Step 1: Run auditor on kctl-shlink only**

```bash
uv run python scripts/audit-platform.py --package kctl-shlink
```

- [ ] **Step 2: If score < 9/10, read the `--fix-list` output and remediate**

Common gaps:
- README.md too short (< 60 lines) → expand
- Missing SKILL.md → re-run `kctl-shlink skill generate`
- conftest.py missing a standard fixture → add
- No `doctor` / `self-update` / `completions` / `skill generate` → already covered
- Command naming: ensure `clean` (not `cleanup`), `doctor` (not `diagnose`), `scaffold` (not `generate-cli`)

- [ ] **Step 3: Re-run auditor until score ≥ 9/10.**

- [ ] **Step 4: Run full audit to confirm no regressions elsewhere**

```bash
uv run python scripts/audit-platform.py --json | python -c "import json,sys; d=json.load(sys.stdin); print({p['name']:p['score'] for p in d['packages']})"
```

Confirm all 30 packages (29 existing + kctl-shlink) are at ≥ 9/10.

Commit (if any): `chore(kctl-shlink): close quality baseline gaps; audit ≥ 9/10`

---

## Task 27: Integration smoke (optional, requires live profile)

- [ ] **Step 1: With `kodemeio-kod-infra-shlink` profile loaded, run:**

```bash
kctl-shlink -p kodemeio-kod-infra-shlink doctor
kctl-shlink -p kodemeio-kod-infra-shlink domains list
kctl-shlink -p kodemeio-kod-infra-shlink campaigns apply \
    -f deploys/marketing/shlink-campaigns/example-tpm-linkedin-q2.yaml \
    --dry-run
kctl-shlink -p kodemeio-kod-infra-shlink campaigns apply \
    -f deploys/marketing/shlink-campaigns/example-tpm-linkedin-q2.yaml
kctl-shlink -p kodemeio-kod-infra-shlink campaigns apply \
    -f deploys/marketing/shlink-campaigns/example-tpm-linkedin-q2.yaml
# Second apply must show 0 create / 0 update / 0 delete — idempotency proof
kctl-shlink -p kodemeio-kod-infra-shlink reports campaign 2026_q2_tpm_fmcg_outreach
```

- [ ] **Step 2: Verify** each short URL actually redirects via `curl -IL https://s.kodeme.io/tpm-linkedin-q2a`.

- [ ] **Step 3: Clean up the example campaign**

```bash
kctl-shlink -p kodemeio-kod-infra-shlink campaigns destroy \
    -f deploys/marketing/shlink-campaigns/example-tpm-linkedin-q2.yaml --force
```

No commit — this is verification only.

---

## Task 28: Build + publish prep (hatchling wheel)

- [ ] **Step 1: Build wheel locally**

```bash
cd packages/kctl-shlink
uv build
```

Verify `dist/kctl_shlink-0.1.0-*.whl` + `.tar.gz`.

- [ ] **Step 2: Install wheel into a throwaway env to test**

```bash
uv venv /tmp/shlink-test
/tmp/shlink-test/bin/pip install packages/kctl-shlink/dist/kctl_shlink-0.1.0-*.whl
/tmp/shlink-test/bin/kctl-shlink --version
```

- [ ] **Step 3: Tag for PyPI** (pushed to PyPI by `.github/workflows/publish.yml` on `v*` tag — NOT in this plan; mentioned only so the reviewer knows the release is automated).

Commit: `chore(kctl-shlink): bump to 0.1.0 for initial release`

---

## Completion checklist

- [ ] All 11 spec §4.3 command groups implemented: `config`, `doctor`, `self-update`, `completions`, `skill`, `domains`, `urls`, `tags`, `visits`, `qr`, `campaigns`, `reports`, `redirects`, `export`
- [ ] `CampaignManifest` Pydantic schema matches spec §4.3 exactly (CampaignUTM, CampaignQR, CampaignLink, CampaignDefaults)
- [ ] Slug regex + utm_campaign regex enforced at load time (Pydantic validators)
- [ ] `campaigns apply` idempotency verified: apply twice → zero changes
- [ ] QR: PNG + SVG, `web/print/billboard` margin presets (4/10/20), PNG logo overlay at 22% with white backing
- [ ] Cross-join: reports campaign renders joined table when kctl-plausible profile loadable, degrades to click-only otherwise
- [ ] `doctor` includes: Config, API Reachability, TLS expiry, DNS, Inventory, Plausible bridge, Freshness
- [ ] Standard commands: `config init/add/use/show/validate/remove/set/profiles/current`, `doctor`, `self-update`, `completions`, `skill generate`
- [ ] README.md ≥ 60 lines; SKILL.md generated; conftest.py with all standard fixtures
- [ ] Ruff + format + mypy strict + pytest pass; coverage ≥ 60%
- [ ] `scripts/audit-platform.py --package kctl-shlink` → 9+/10
- [ ] Workspace: pyproject.toml updated, uv.lock regenerated, CLAUDE.md row added, CI matrix wired
- [ ] Example manifest `deploys/marketing/shlink-campaigns/example-tpm-linkedin-q2.yaml` applies cleanly

---

## References

- Spec: `docs/superpowers/specs/2026-04-19-kctl-marketing-wave-1-design.md`
- Structural template: `packages/kctl-zulip/`
- APIClient base: `packages/kctl-lib/src/kctl_lib/api_client.py`
- Declarative-apply analogue: `packages/kctl-dbgate/src/kctl_dbgate/commands/connections.py`
- Standards: `docs/cli-standards.md`
- Audit tool: `scripts/audit-platform.py`
