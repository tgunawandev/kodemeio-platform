"""Keyword-cluster definitions + matching.

YAML shape:
  products:
    bas:
      property: sc-domain:kodeme.io
      path_filter: /bas/         # optional, passed as page-dimension filter
      clusters:
        - name: payroll
          patterns: [payroll, gaji]
        - name: erp_intent
          patterns: [odoo, erp]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class Cluster(BaseModel):
    name: str
    patterns: list[str]


class ProductConfig(BaseModel):
    property: str
    path_filter: str = ""
    clusters: list[Cluster] = []


class ClusterConfig(BaseModel):
    products: dict[str, ProductConfig] = {}


def load_clusters(path: Path) -> ClusterConfig:
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    return ClusterConfig.model_validate(raw)


@dataclass
class ClusterBucket:
    name: str
    impressions: int = 0
    clicks: int = 0
    queries: list[str] = field(default_factory=list)
    _positions_weighted: float = 0.0

    @property
    def ctr(self) -> float:
        return (self.clicks / self.impressions * 100) if self.impressions else 0.0

    @property
    def avg_position(self) -> float:
        return (self._positions_weighted / self.impressions) if self.impressions else 0.0

    @property
    def top_query(self) -> str:
        return self.queries[0] if self.queries else ""


def apply_clusters(product: ProductConfig, rows: list[dict[str, Any]]) -> list[ClusterBucket]:
    """Bucket rows into named clusters; rows that match multiple clusters are counted in each.
    Rows matching no cluster go into 'unclustered'.
    """
    buckets: dict[str, ClusterBucket] = {c.name: ClusterBucket(name=c.name) for c in product.clusters}
    buckets["unclustered"] = ClusterBucket(name="unclustered")

    for r in rows:
        q = str(r.get("query", "")).lower()
        impressions = int(r.get("impressions", 0))
        clicks = int(r.get("clicks", 0))
        position = float(r.get("position", 0))
        matched = False
        for cluster in product.clusters:
            if any(p.lower() in q for p in cluster.patterns):
                matched = True
                b = buckets[cluster.name]
                b.impressions += impressions
                b.clicks += clicks
                b._positions_weighted += position * impressions
                b.queries.append(str(r.get("query", "")))
        if not matched:
            b = buckets["unclustered"]
            b.impressions += impressions
            b.clicks += clicks
            b._positions_weighted += position * impressions
            b.queries.append(str(r.get("query", "")))

    for b in buckets.values():
        b.queries.sort(
            key=lambda name: next((int(r["impressions"]) for r in rows if r["query"] == name), 0),
            reverse=True,
        )
    return list(buckets.values())
