"""Notion API client using kctl-lib APIClient base.

Notion API v1: REST endpoints with Bearer token auth.
Requires Notion-Version header on all requests.
Search and database queries use POST (not GET).
"""

from __future__ import annotations

from typing import Any

from kctl_lib.api_client import APIClient


class NotionClient(APIClient):
    """Synchronous client for Notion REST API v1."""

    BASE_URL = "https://api.notion.com/v1"
    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"

    NOTION_VERSION = "2022-06-28"

    def _build_auth_header(self) -> dict[str, str]:
        """Add Notion-Version header alongside auth."""
        headers = super()._build_auth_header()
        headers["Notion-Version"] = self.NOTION_VERSION
        return headers

    # ------------------------------------------------------------------
    # Notion-specific convenience methods
    # ------------------------------------------------------------------

    def search(
        self,
        query: str = "",
        filter_type: str | None = None,
        start_cursor: str | None = None,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """Search workspace. POST /search."""
        payload: dict[str, Any] = {}
        if query:
            payload["query"] = query
        if filter_type:
            payload["filter"] = {"value": filter_type, "property": "object"}
        if start_cursor:
            payload["start_cursor"] = start_cursor
        if page_size != 100:
            payload["page_size"] = page_size
        return self.post("/search", json=payload)

    def get_page(self, page_id: str) -> dict[str, Any]:
        """Get a page by ID. GET /pages/{id}."""
        return self.get(f"/pages/{page_id}")

    def create_page(self, parent_id: str, title: str, parent_type: str = "page_id") -> dict[str, Any]:
        """Create a new page. POST /pages."""
        parent: dict[str, str] = {parent_type: parent_id}
        payload: dict[str, Any] = {
            "parent": parent,
            "properties": {
                "title": {
                    "title": [{"text": {"content": title}}],
                },
            },
        }
        return self.post("/pages", json=payload)

    def update_page(self, page_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        """Update page properties. PATCH /pages/{id}."""
        return self.patch(f"/pages/{page_id}", json={"properties": properties})

    def get_database(self, database_id: str) -> dict[str, Any]:
        """Get database schema. GET /databases/{id}."""
        return self.get(f"/databases/{database_id}")

    def query_database(
        self,
        database_id: str,
        filter_obj: dict[str, Any] | None = None,
        sorts: list[dict[str, Any]] | None = None,
        start_cursor: str | None = None,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """Query database rows. POST /databases/{id}/query."""
        payload: dict[str, Any] = {}
        if filter_obj:
            payload["filter"] = filter_obj
        if sorts:
            payload["sorts"] = sorts
        if start_cursor:
            payload["start_cursor"] = start_cursor
        if page_size != 100:
            payload["page_size"] = page_size
        return self.post(f"/databases/{database_id}/query", json=payload)

    def query_database_all(
        self,
        database_id: str,
        filter_obj: dict[str, Any] | None = None,
        sorts: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Query all rows from a database, handling pagination."""
        all_results: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            result = self.query_database(database_id, filter_obj=filter_obj, sorts=sorts, start_cursor=cursor)
            all_results.extend(result.get("results", []))
            if not result.get("has_more"):
                break
            cursor = result.get("next_cursor")
            if not cursor:
                break
        return all_results

    def get_block_children(self, block_id: str, start_cursor: str | None = None) -> dict[str, Any]:
        """List child blocks of a page/block. GET /blocks/{id}/children."""
        params: dict[str, Any] = {}
        if start_cursor:
            params["start_cursor"] = start_cursor
        return self.get(f"/blocks/{block_id}/children", params=params)

    def append_block_children(self, block_id: str, children: list[dict[str, Any]]) -> dict[str, Any]:
        """Append child blocks to a page/block. PATCH /blocks/{id}/children."""
        return self.patch(f"/blocks/{block_id}/children", json={"children": children})

    def list_users(self, start_cursor: str | None = None) -> dict[str, Any]:
        """List workspace users. GET /users."""
        params: dict[str, Any] = {}
        if start_cursor:
            params["start_cursor"] = start_cursor
        return self.get("/users", params=params)

    def get_me(self) -> dict[str, Any]:
        """Get the current bot user. GET /users/me."""
        return self.get("/users/me")
