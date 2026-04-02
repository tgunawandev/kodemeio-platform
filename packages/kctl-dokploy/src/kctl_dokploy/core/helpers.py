"""Shared helpers for collecting Dokploy resources across environments."""

from __future__ import annotations

from typing import Any


def collect_all_services(client: Any) -> dict:
    """Collect ALL compose + application services across ALL projects/environments.

    Returns dict with keys: projects, composes, applications, domains, summary
    """
    try:
        raw_projects = client.get("/project.all")
    except Exception:
        return {"projects": [], "composes": [], "applications": [], "domains": [], "summary": {}}

    if not isinstance(raw_projects, list):
        raw_projects = []

    projects = []
    composes = []
    applications = []
    all_domains = []

    seen_compose_ids: set[str] = set()
    seen_app_ids: set[str] = set()

    for p in raw_projects:
        project_name = p.get("name", "")
        project_id = p.get("projectId", "")
        envs = p.get("environments", [])

        projects.append(
            {
                "name": project_name,
                "projectId": project_id,
                "env_count": len(envs),
            }
        )

        # Collect from environments (standard Dokploy structure)
        for env in envs:
            for comp in env.get("compose", []):
                cid = comp.get("composeId", "")
                if cid and cid not in seen_compose_ids:
                    seen_compose_ids.add(cid)
                    comp["_project"] = project_name
                    composes.append(comp)
            for app_item in env.get("applications", []):
                aid = app_item.get("applicationId", "")
                if aid and aid not in seen_app_ids:
                    seen_app_ids.add(aid)
                    app_item["_project"] = project_name
                    applications.append(app_item)

        # Also collect from project root (older API compat)
        for comp in p.get("compose", []):
            cid = comp.get("composeId", "")
            if cid and cid not in seen_compose_ids:
                seen_compose_ids.add(cid)
                comp["_project"] = project_name
                composes.append(comp)
        for app_item in p.get("applications", []):
            aid = app_item.get("applicationId", "")
            if aid and aid not in seen_app_ids:
                seen_app_ids.add(aid)
                app_item["_project"] = project_name
                applications.append(app_item)

    # Collect domains from each compose/application detail
    for comp in composes:
        cid = comp.get("composeId", "")
        try:
            detail = client.get("/compose.one", params={"composeId": cid})
            if isinstance(detail, dict):
                for d in detail.get("domains", []):
                    d["_project"] = comp.get("_project", "")
                    d["_service"] = comp.get("name", "")
                    d["_serviceType"] = "compose"
                    all_domains.append(d)
                # Enrich compose with detail fields
                comp["domains"] = detail.get("domains", [])
                comp["backups"] = detail.get("backups", [])
                comp["githubId"] = detail.get("githubId")
                comp["autoDeploy"] = detail.get("autoDeploy", False)
                comp["sourceType"] = detail.get("sourceType", "")
                comp["serverId"] = detail.get("serverId")
                comp["composeStatus"] = detail.get("composeStatus", comp.get("composeStatus", "unknown"))
        except Exception:
            pass

    for app_item in applications:
        aid = app_item.get("applicationId", "")
        try:
            detail = client.get("/application.one", params={"applicationId": aid})
            if isinstance(detail, dict):
                for d in detail.get("domains", []):
                    d["_project"] = app_item.get("_project", "")
                    d["_service"] = app_item.get("name", "")
                    d["_serviceType"] = "application"
                    all_domains.append(d)
                # Enrich application with detail fields
                app_item["domains"] = detail.get("domains", [])
                app_item["autoDeploy"] = detail.get("autoDeploy", False)
        except Exception:
            pass

    summary = {
        "projects": len(projects),
        "composes": len(composes),
        "applications": len(applications),
        "domains": len(all_domains),
    }

    return {
        "projects": projects,
        "composes": composes,
        "applications": applications,
        "domains": all_domains,
        "summary": summary,
    }
