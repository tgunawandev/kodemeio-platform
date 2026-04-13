"""Mattermost REST v4 API client."""

from __future__ import annotations

from typing import Any

import httpx

from kctl_lib.api_client import APIClient
from kctl_lib.exceptions import APIError, NotFoundError


class MattermostClient(APIClient):
    """Client for the Mattermost REST v4 API."""

    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"
    API_PREFIX = "/api/v4"

    def __init__(self, url: str, token: str, timeout: int = 30) -> None:
        super().__init__(base_url=url, credential=token, timeout=timeout)

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> httpx.Response:
        try:
            return super()._request(method, endpoint, **kwargs)
        except APIError as exc:
            if getattr(exc, "status_code", None) == 404:
                raise NotFoundError("resource", endpoint) from exc
            raise

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def get_me(self) -> Any:
        return self.get("/users/me")

    def get_user_by_username(self, username: str) -> Any:
        return self.get(f"/users/username/{username}")

    def list_users(self, page: int = 0, per_page: int = 60) -> Any:
        return self.get("/users", params={"page": page, "per_page": per_page})

    def create_user(self, payload: dict[str, Any]) -> Any:
        return self.post("/users", json=payload)

    def update_user_active(self, user_id: str, active: bool) -> Any:
        return self.put(f"/users/{user_id}/active", json={"active": active})

    def list_user_audits(self, user_id: str) -> Any:
        return self.get(f"/users/{user_id}/audits")

    # ------------------------------------------------------------------
    # Teams
    # ------------------------------------------------------------------

    def list_teams(self) -> Any:
        return self.get("/teams")

    def get_team_by_name(self, name: str) -> Any:
        return self.get(f"/teams/name/{name}")

    def create_team(self, name: str, display_name: str, type_: str = "O") -> Any:
        return self.post(
            "/teams",
            json={"name": name, "display_name": display_name, "type": type_},
        )

    def list_team_members(self, team_id: str) -> Any:
        return self.get(f"/teams/{team_id}/members")

    # ------------------------------------------------------------------
    # Channels
    # ------------------------------------------------------------------

    def list_channels_for_team(self, team_id: str) -> Any:
        return self.get(f"/teams/{team_id}/channels")

    def get_channel_by_name(self, team_id: str, name: str) -> Any:
        return self.get(f"/teams/{team_id}/channels/name/{name}")

    def create_channel(
        self,
        team_id: str,
        name: str,
        display_name: str,
        private: bool = False,
    ) -> Any:
        return self.post(
            "/channels",
            json={
                "team_id": team_id,
                "name": name,
                "display_name": display_name,
                "type": "P" if private else "O",
            },
        )

    def list_channel_members(self, channel_id: str) -> Any:
        return self.get(f"/channels/{channel_id}/members")

    def rename_channel(self, channel_id: str, display_name: str) -> Any:
        return self.put(
            f"/channels/{channel_id}/patch",
            json={"display_name": display_name},
        )

    # ------------------------------------------------------------------
    # Posts
    # ------------------------------------------------------------------

    def create_post(self, channel_id: str, message: str) -> Any:
        return self.post("/posts", json={"channel_id": channel_id, "message": message})

    def search_posts(self, team_id: str, terms: str) -> Any:
        return self.post(f"/teams/{team_id}/posts/search", json={"terms": terms})

    def get_post(self, post_id: str) -> Any:
        return self.get(f"/posts/{post_id}")

    def delete_post(self, post_id: str) -> Any:
        return self.delete(f"/posts/{post_id}")

    def pin_post(self, post_id: str) -> Any:
        return self.post(f"/posts/{post_id}/pin")

    def unpin_post(self, post_id: str) -> Any:
        return self.post(f"/posts/{post_id}/unpin")

    # ------------------------------------------------------------------
    # Webhooks
    # ------------------------------------------------------------------

    def list_incoming_hooks(self) -> Any:
        return self.get("/hooks/incoming")

    def list_outgoing_hooks(self) -> Any:
        return self.get("/hooks/outgoing")

    def create_incoming_hook(self, channel_id: str, display_name: str) -> Any:
        return self.post(
            "/hooks/incoming",
            json={"channel_id": channel_id, "display_name": display_name},
        )

    def create_outgoing_hook(self, team_id: str, trigger_words: list[str]) -> Any:
        return self.post(
            "/hooks/outgoing",
            json={"team_id": team_id, "trigger_words": trigger_words},
        )

    def delete_incoming_hook(self, hook_id: str) -> Any:
        return self.delete(f"/hooks/incoming/{hook_id}")

    def delete_outgoing_hook(self, hook_id: str) -> Any:
        return self.delete(f"/hooks/outgoing/{hook_id}")

    # ------------------------------------------------------------------
    # Bots
    # ------------------------------------------------------------------

    def list_bots(self) -> Any:
        return self.get("/bots")

    def create_bot(self, username: str, display_name: str) -> Any:
        return self.post(
            "/bots",
            json={"username": username, "display_name": display_name},
        )

    def enable_bot(self, bot_id: str) -> Any:
        return self.post(f"/bots/{bot_id}/enable")

    def disable_bot(self, bot_id: str) -> Any:
        return self.post(f"/bots/{bot_id}/disable")

    def delete_bot(self, bot_id: str) -> Any:
        return self.delete(f"/bots/{bot_id}")

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------

    def list_jobs(self, job_type: str | None = None) -> Any:
        params = {"job_type": job_type} if job_type else None
        return self.get("/jobs", params=params)

    def get_job(self, job_id: str) -> Any:
        return self.get(f"/jobs/{job_id}")

    def cancel_job(self, job_id: str) -> Any:
        return self.post(f"/jobs/{job_id}/cancel")

    # ------------------------------------------------------------------
    # Config / audit / system
    # ------------------------------------------------------------------

    def get_config(self) -> Any:
        return self.get("/config")

    def list_compliance_reports(self) -> Any:
        return self.get("/compliance/reports")

    def download_compliance_report(self, report_id: str, local_path: str) -> str:
        url = f"{self._base_url}/compliance/reports/{report_id}/download"
        headers = self._build_auth_header()
        with httpx.stream("GET", url, headers=headers) as r:
            r.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        return local_path

    def ping(self) -> Any:
        return self.get("/system/ping")

    def ping_full(self) -> dict[str, Any]:
        return self.get("/system/ping", params={"get_server_status": "true"})

    def user_stats(self) -> dict[str, Any]:
        return self.get("/users/stats")

    def analytics(self, team_id: str = "") -> list[dict[str, Any]]:
        return self.get("/analytics/old", params={"team_id": team_id} if team_id else None)

    # ------------------------------------------------------------------
    # Maintenance helpers
    # ------------------------------------------------------------------

    def recycle_database(self) -> dict[str, Any]:
        return self.post("/database/recycle")

    def invalidate_caches(self) -> dict[str, Any]:
        return self.post("/caches/invalidate")

    def reload_config(self) -> dict[str, Any]:
        return self.post("/config/reload")
