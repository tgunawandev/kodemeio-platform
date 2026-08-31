#!/usr/bin/env python3
"""Minimal Dokploy API client shared by the ops scripts.

Deliberately stdlib + pyyaml only. This repo does not depend on kctl-dokploy as
a library (README lists it as a separately installed CLI tool), and importing
its private `_get_service_config` would couple ops tooling to CLI internals.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

CONFIG_PATH = Path.home() / ".config" / "kodemeio" / "config.yaml"

# Dokploy sits behind Cloudflare, which rejects the default Python-urllib user
# agent with "error code: 1010" before the request ever reaches Dokploy. Any
# ordinary browser UA passes. Without this every call 403s.
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"


def load_profile(profile: str) -> tuple[str, str]:
    """Return (base_url, api_key) for a profile from the shared kctl config."""
    cfg = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    try:
        block = cfg["profiles"][profile]["dokploy"]
    except KeyError as exc:
        raise SystemExit(f"profile {profile!r} has no dokploy block in {CONFIG_PATH}") from exc
    url = str(block.get("url", "")).rstrip("/")
    key = str(block.get("api_key", ""))
    if not url or not key:
        raise SystemExit(f"profile {profile!r} is missing dokploy url or api_key")
    return url, key


def _headers(api_key: str) -> dict[str, str]:
    return {"x-api-key": api_key, "User-Agent": USER_AGENT}


def api_get(base_url: str, api_key: str, path: str, params: dict | None = None) -> object:
    """GET one Dokploy API endpoint, returning decoded JSON."""
    qs = f"?{urllib.parse.urlencode(params)}" if params else ""
    req = urllib.request.Request(f"{base_url}/api{path}{qs}", headers=_headers(api_key))
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed https host from config
        return json.load(resp)


def api_post(base_url: str, api_key: str, path: str, payload: dict) -> object:
    """POST JSON to one Dokploy API endpoint, returning decoded JSON."""
    headers = {**_headers(api_key), "Content-Type": "application/json"}
    req = urllib.request.Request(
        f"{base_url}/api{path}",
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 - fixed https host from config
        body = resp.read()
        return json.loads(body) if body else {}


def flatten_composes(projects: object) -> list[dict]:
    """Flatten compose services out of the /project.all tree.

    There is no /compose.all endpoint. Composes are nested TWO levels deep:
    project -> environments[] -> compose[]. Reading project["compose"] directly
    yields an empty list and no error, which once made schedule-status.py
    cheerfully report "All 0 schedule(s) healthy" against 18 schedules.
    """
    out: list[dict] = []
    for project in projects if isinstance(projects, list) else []:
        for env in project.get("environments") or []:
            for comp in env.get("compose") or []:
                if comp.get("composeId"):
                    out.append(
                        {
                            "composeId": comp["composeId"],
                            "name": comp.get("name", ""),
                            "project": project.get("name", ""),
                        }
                    )
    return out


def list_composes(base_url: str, api_key: str) -> list[dict]:
    """Every compose service the profile can see."""
    return flatten_composes(api_get(base_url, api_key, "/project.all"))


def list_schedules(base_url: str, api_key: str, compose_id: str) -> list[dict]:
    """Every compose-type schedule on one compose service."""
    out = api_get(base_url, api_key, "/schedule.list", {"id": compose_id, "scheduleType": "compose"})
    return out if isinstance(out, list) else []


def list_runs(base_url: str, api_key: str, schedule_id: str) -> list[dict]:
    """Run history for one schedule.

    NOT on schedule.one, which carries no run history at all -- this is why
    `kctl-dokploy schedules history` always reports "No execution history".
    """
    out = api_get(base_url, api_key, "/deployment.allByType", {"id": schedule_id, "type": "schedule"})
    return out if isinstance(out, list) else []
