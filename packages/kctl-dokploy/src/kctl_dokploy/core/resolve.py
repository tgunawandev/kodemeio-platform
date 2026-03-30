"""Name-to-ID resolution helpers.

Allows commands to accept names instead of UUIDs.
Results are cached within a single CLI invocation.
"""

from __future__ import annotations

from typing import Any

from kctl_dokploy.core.exceptions import NotFoundError

# Module-level cache (reset per process)
_cache: dict[str, str] = {}


def _cache_key(resource_type: str, identifier: str) -> str:
    return f"{resource_type}:{identifier.lower()}"


def resolve_project(client: Any, name_or_id: str) -> str:
    """Resolve a project name or ID to a project ID."""
    key = _cache_key("project", name_or_id)
    if key in _cache:
        return _cache[key]

    projects = client.get("/project.all")
    if not isinstance(projects, list):
        raise NotFoundError("project", name_or_id)

    # Try exact ID match first
    for p in projects:
        pid = p.get("projectId", "")
        if pid == name_or_id or pid.startswith(name_or_id):
            _cache[key] = pid
            return pid

    # Try name match (case-insensitive)
    for p in projects:
        if p.get("name", "").lower() == name_or_id.lower():
            pid = p.get("projectId", "")
            _cache[key] = pid
            return pid

    raise NotFoundError("project", name_or_id)


def resolve_compose(client: Any, name_or_id: str, project: str | None = None) -> str:
    """Resolve a compose service name or ID to a compose ID."""
    key = _cache_key("compose", f"{project or ''}:{name_or_id}")
    if key in _cache:
        return _cache[key]

    projects = client.get("/project.all")
    if not isinstance(projects, list):
        raise NotFoundError("compose", name_or_id)

    all_compose: list[dict] = []
    for p in projects:
        if project and p.get("name", "").lower() != project.lower() and p.get("projectId", "") != project:
            continue
        for comp in p.get("compose", []):
            comp["_projectName"] = p.get("name", "")
            all_compose.append(comp)

    # Try exact ID match
    for c in all_compose:
        cid = c.get("composeId", "")
        if cid == name_or_id or cid.startswith(name_or_id):
            _cache[key] = cid
            return cid

    # Try name match (case-insensitive)
    for c in all_compose:
        if c.get("name", "").lower() == name_or_id.lower():
            cid = c.get("composeId", "")
            _cache[key] = cid
            return cid

    raise NotFoundError("compose", name_or_id)


def resolve_application(client: Any, name_or_id: str, project: str | None = None) -> str:
    """Resolve an application name or ID to an application ID."""
    key = _cache_key("application", f"{project or ''}:{name_or_id}")
    if key in _cache:
        return _cache[key]

    projects = client.get("/project.all")
    if not isinstance(projects, list):
        raise NotFoundError("application", name_or_id)

    all_apps: list[dict] = []
    for p in projects:
        if project and p.get("name", "").lower() != project.lower() and p.get("projectId", "") != project:
            continue
        for app in p.get("applications", []):
            all_apps.append(app)

    # Try exact ID match
    for a in all_apps:
        aid = a.get("applicationId", "")
        if aid == name_or_id or aid.startswith(name_or_id):
            _cache[key] = aid
            return aid

    # Try name match
    for a in all_apps:
        if a.get("name", "").lower() == name_or_id.lower():
            aid = a.get("applicationId", "")
            _cache[key] = aid
            return aid

    raise NotFoundError("application", name_or_id)


def resolve_server(client: Any, name_or_id: str) -> str:
    """Resolve a server name or ID to a server ID."""
    key = _cache_key("server", name_or_id)
    if key in _cache:
        return _cache[key]

    servers = client.get("/server.all")
    if not isinstance(servers, list):
        raise NotFoundError("server", name_or_id)

    # Try exact ID match
    for s in servers:
        sid = s.get("serverId", "")
        if sid == name_or_id or sid.startswith(name_or_id):
            _cache[key] = sid
            return sid

    # Try name match
    for s in servers:
        if s.get("name", "").lower() == name_or_id.lower():
            sid = s.get("serverId", "")
            _cache[key] = sid
            return sid

    raise NotFoundError("server", name_or_id)


def clear_cache() -> None:
    """Clear the resolution cache."""
    _cache.clear()
