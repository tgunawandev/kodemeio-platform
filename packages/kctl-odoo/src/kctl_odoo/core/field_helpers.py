"""Field discovery helpers for safe Odoo model introspection."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kctl_odoo.core.client import OdooClient

_CACHE_DIR = Path.home() / ".cache" / "kctl-odoo" / "fields"
_CACHE_TTL = 3600  # 1 hour


def _cache_key(base_url: str, database: str, model: str) -> str:
    """Generate a cache key from connection + model."""
    raw = f"{base_url}:{database}:{model}"
    return hashlib.md5(raw.encode()).hexdigest()


def _read_cache(key: str) -> dict | None:
    """Read cached fields_get result if fresh."""
    cache_file = _CACHE_DIR / f"{key}.json"
    if not cache_file.exists():
        return None
    try:
        data = json.loads(cache_file.read_text())
        if time.time() - data.get("_ts", 0) < _CACHE_TTL:
            return data.get("fields", {})
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _write_cache(key: str, fields: dict) -> None:
    """Write fields_get result to cache."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = _CACHE_DIR / f"{key}.json"
        cache_file.write_text(json.dumps({"_ts": time.time(), "fields": fields}))
    except OSError:
        pass  # Cache write failure is non-fatal


def clear_field_cache() -> int:
    """Clear all cached field definitions. Returns number of files removed."""
    if not _CACHE_DIR.exists():
        return 0
    count = 0
    for f in _CACHE_DIR.glob("*.json"):
        f.unlink()
        count += 1
    return count


# Fields guaranteed to exist on every Odoo model
_UNIVERSAL_FIELDS = {"id", "display_name", "create_date", "write_date", "create_uid", "write_uid"}

# Common fields that often exist but aren't guaranteed
_COMMON_FIELDS = {"name", "active", "state", "company_id", "sequence"}


def safe_fields(
    client: OdooClient,
    model: str,
    preferred: list[str],
    *,
    always_include: list[str] | None = None,
) -> list[str]:
    """Return intersection of preferred fields with actual model fields.

    Queries fields_get once and returns only fields that actually exist
    on the model. Falls back to universal fields on error.

    Args:
        client: OdooClient instance
        model: Odoo model name (e.g. 'form.type')
        preferred: List of field names you want (e.g. ['name', 'state', 'partner_id'])
        always_include: Fields to always include if they exist (e.g. ['display_name'])

    Returns:
        List of field names that exist on the model, preserving preferred order.

    Example:
        fields = safe_fields(c, "form.type", ["name", "model_id", "active", "code"])
        # Returns: ["name", "active", "code"]  (model_id doesn't exist, silently dropped)
    """
    try:
        all_fields = client.execute_kw(model, "fields_get", [], {"attributes": ["type", "string"]})
        available = set(all_fields.keys())
    except Exception:
        # Fallback: return universal fields that are in preferred
        return [f for f in preferred if f in _UNIVERSAL_FIELDS] or ["display_name", "create_date"]

    result = []
    seen = set()

    # Add always_include fields first
    if always_include:
        for f in always_include:
            if f in available and f not in seen:
                result.append(f)
                seen.add(f)

    # Add preferred fields that exist
    for f in preferred:
        if f in available and f not in seen:
            result.append(f)
            seen.add(f)

    # If nothing matched, fall back to display_name + create_date
    if not result:
        for f in ["display_name", "create_date"]:
            if f in available:
                result.append(f)

    return result


def get_model_fields(
    client: OdooClient,
    model: str,
    *,
    use_cache: bool = True,
) -> dict[str, dict]:
    """Get all fields for a model with their metadata.

    Caches results for 1 hour to avoid repeated RPC calls.

    Returns dict of field_name -> {"type": ..., "string": ..., "required": ..., "readonly": ...}
    Returns empty dict on error.
    """
    # Try cache first
    if use_cache:
        key = _cache_key(client._base_url, client._database, model)
        cached = _read_cache(key)
        if cached is not None:
            return cached

    try:
        fields = client.execute_kw(
            model, "fields_get", [], {"attributes": ["type", "string", "required", "readonly", "store", "relation"]}
        )
    except Exception:
        return {}

    # Cache the result
    if use_cache and fields:
        key = _cache_key(client._base_url, client._database, model)
        _write_cache(key, fields)

    return fields


def classify_fields(fields: dict[str, dict]) -> dict[str, list[str]]:
    """Classify model fields into categories for code generation.

    Returns:
        {
            "identifiers": [...],    # name, code, ref, display_name
            "states": [...],         # state, status, active
            "relations": [...],      # many2one fields
            "dates": [...],          # date, datetime fields
            "amounts": [...],        # float/monetary fields
            "text": [...],           # char/text fields
        }
    """
    result: dict[str, list[str]] = {
        "identifiers": [],
        "states": [],
        "relations": [],
        "dates": [],
        "amounts": [],
        "text": [],
    }

    for fname, finfo in fields.items():
        if fname.startswith("_") or fname in _UNIVERSAL_FIELDS:
            continue

        ftype = finfo.get("type", "")
        stored = finfo.get("store", True)

        if not stored:
            continue

        if fname in ("name", "code", "ref", "reference", "display_name"):
            result["identifiers"].append(fname)
        elif fname in ("state", "status", "active"):
            result["states"].append(fname)
        elif ftype == "many2one":
            result["relations"].append(fname)
        elif ftype in ("date", "datetime"):
            result["dates"].append(fname)
        elif ftype in ("float", "monetary", "integer"):
            result["amounts"].append(fname)
        elif ftype in ("char", "text", "html"):
            result["text"].append(fname)

    return result
