"""Shared pytest fixtures for kctl-outline tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

import pytest


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """A clean tmp directory standing in for a repo root."""
    return tmp_path


@pytest.fixture
def write_ssot(tmp_repo: Path):
    """Helper to write a .ssot marker at a given path."""

    def _write(rel_dir: str, value: str) -> Path:
        d = tmp_repo / rel_dir
        d.mkdir(parents=True, exist_ok=True)
        marker = d / ".ssot"
        marker.write_text(value + "\n")
        return marker

    return _write


class FakeOutlineClient:
    """In-memory fake of the kctl-outline httpx client.

    Records every call as a (endpoint, data) tuple in self.calls.
    Stores documents and collections so post('documents.list') etc. work.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.collections: list[dict[str, Any]] = []
        self.documents: list[dict[str, Any]] = []
        self._next_id = 1

    def _new_id(self) -> str:
        sid = f"id-{self._next_id:06d}"
        self._next_id += 1
        return sid

    def post(self, endpoint: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        data = data or {}
        self.calls.append((endpoint, dict(data)))
        if endpoint == "collections.list":
            return {"data": list(self.collections)}
        if endpoint == "collections.create":
            col = {"id": self._new_id(), "name": data["name"], "permission": data.get("permission", "read")}
            self.collections.append(col)
            return {"data": col}
        if endpoint == "documents.list":
            cid = data.get("collectionId")
            docs = [d for d in self.documents if cid is None or d.get("collectionId") == cid]
            return {"data": docs}
        if endpoint == "documents.create":
            doc = {
                "id": self._new_id(),
                "title": data["title"],
                "text": data["text"],
                "collectionId": data["collectionId"],
                "parentDocumentId": data.get("parentDocumentId"),
            }
            self.documents.append(doc)
            return {"data": doc}
        if endpoint == "documents.update":
            for d in self.documents:
                if d["id"] == data["id"]:
                    d["title"] = data.get("title", d["title"])
                    d["text"] = data.get("text", d["text"])
                    return {"data": d}
            raise KeyError(f"no doc with id={data['id']}")
        if endpoint == "documents.info":
            for d in self.documents:
                if d["id"] == data["id"]:
                    return {"data": d}
            raise KeyError(f"no doc with id={data['id']}")
        raise NotImplementedError(f"FakeOutlineClient does not implement {endpoint}")

    def post_all(self, endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Pagination helper — fake returns all results in one shot."""
        result = self.post(endpoint, params or {})
        return result.get("data", [])


@pytest.fixture
def fake_client() -> FakeOutlineClient:
    return FakeOutlineClient()


@pytest.fixture
def fake_client_with_seed():
    """Returns a builder that creates a FakeOutlineClient with seed data."""

    def _build(*, collections: list[dict] | None = None, documents: list[dict] | None = None) -> FakeOutlineClient:
        c = FakeOutlineClient()
        for col in collections or []:
            c.collections.append({"id": c._new_id(), **col})
        for doc in documents or []:
            c.documents.append({"id": c._new_id(), **doc})
        return c

    return _build
