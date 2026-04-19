from __future__ import annotations

from pathlib import Path

from kctl_gsc.core.clusters import ClusterConfig, apply_clusters, load_clusters


def test_load_and_match(tmp_path: Path) -> None:
    f = tmp_path / "clusters.yaml"
    f.write_text(
        """
products:
  bas:
    property: sc-domain:kodeme.io
    path_filter: /bas/
    clusters:
      - name: payroll
        patterns: ["payroll", "gaji", "penggajian"]
      - name: erp_intent
        patterns: ["odoo", "erp"]
"""
    )
    cfg = load_clusters(f)
    assert "bas" in cfg.products
    product = cfg.products["bas"]
    assert product.property == "sc-domain:kodeme.io"
    assert len(product.clusters) == 2


def test_apply_clusters_buckets_queries() -> None:
    rows = [
        {"query": "Odoo ERP Indonesia", "impressions": 100, "clicks": 10, "position": 3.0},
        {"query": "aplikasi payroll", "impressions": 50, "clicks": 2, "position": 5.0},
        {"query": "cuaca hari ini", "impressions": 5, "clicks": 0, "position": 40.0},
        {"query": "payroll odoo", "impressions": 20, "clicks": 1, "position": 4.5},
    ]
    product_cfg = ClusterConfig.model_validate(
        {
            "products": {
                "bas": {
                    "property": "sc-domain:kodeme.io",
                    "clusters": [
                        {"name": "payroll", "patterns": ["payroll"]},
                        {"name": "erp", "patterns": ["odoo", "erp"]},
                    ],
                }
            }
        }
    ).products["bas"]
    buckets = apply_clusters(product_cfg, rows)
    assert {b.name for b in buckets} == {"payroll", "erp", "unclustered"}
    payroll = next(b for b in buckets if b.name == "payroll")
    assert payroll.impressions == 50 + 20  # matches both "aplikasi payroll" and "payroll odoo"
    erp = next(b for b in buckets if b.name == "erp")
    assert erp.impressions == 100 + 20  # multi-match allowed
    unclustered = next(b for b in buckets if b.name == "unclustered")
    assert unclustered.impressions == 5
