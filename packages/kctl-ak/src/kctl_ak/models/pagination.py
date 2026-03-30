"""Pagination models for Authentik API responses."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Pagination(BaseModel):
    count: int = 0
    total_pages: int = 1
    current: int = 1
    next: int | None = None
    previous: int | None = None
    start_index: int = 0
    end_index: int = 0


class PaginatedResponse(BaseModel, Generic[T]):
    pagination: Pagination = Pagination()
    results: list[T] = []
