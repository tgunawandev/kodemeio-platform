"""Route introspection commands for kctl-api.

Inspect endpoints, auth requirements, and middleware chains from the OpenAPI spec.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext

app = typer.Typer(
    name="routes", help="Endpoint introspection — list, auth, middleware, unprotected.", no_args_is_help=True
)

_AUTH_KEYWORDS = ("bearer", "api_key", "apikey", "oauth", "security", "authorization")


def _fetch_spec(actx: AppContext) -> dict:
    data = actx.client.get("/openapi.json")
    if not data:
        raise RuntimeError("Empty response from /openapi.json")
    return data


def _is_protected(operation: dict) -> bool:
    """Return True if the operation has a security requirement."""
    security = operation.get("security")
    if security is not None:
        return bool(security)  # empty list [] means explicitly no auth
    return False


def _extract_routes(spec: dict) -> list[dict]:
    """Extract all routes from an OpenAPI spec."""
    routes = []
    for path, path_item in spec.get("paths", {}).items():
        for method, operation in path_item.items():
            if method not in ("get", "post", "put", "patch", "delete", "head", "options"):
                continue
            routes.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "operation_id": operation.get("operationId", ""),
                    "summary": operation.get("summary", ""),
                    "tags": operation.get("tags", []),
                    "protected": _is_protected(operation),
                    "security": operation.get("security", []),
                    "deprecated": operation.get("deprecated", False),
                }
            )
    return routes


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------
@app.command(name="list")
def list_routes(ctx: typer.Context) -> None:
    """List all API endpoints with methods, paths, and auth status."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        spec = _fetch_spec(actx)
    except Exception as e:
        out.error(f"Failed to fetch spec: {e}")
        raise typer.Exit(1) from None

    routes = _extract_routes(spec)

    rows = [
        [
            r["method"],
            r["path"],
            "[green]yes[/green]" if r["protected"] else "[yellow]no[/yellow]",
            "[red]deprecated[/red]" if r["deprecated"] else "",
            ", ".join(r["tags"]),
            r["summary"][:60],
        ]
        for r in routes
    ]

    out.table(
        title=f"API Routes ({len(routes)})",
        columns=[
            ("Method", "bold"),
            ("Path", ""),
            ("Auth", ""),
            ("Status", ""),
            ("Tags", ""),
            ("Summary", ""),
        ],
        rows=rows,
        data_for_json=routes,
    )


# ---------------------------------------------------------------------------
# auth
# ---------------------------------------------------------------------------
@app.command()
def auth(ctx: typer.Context) -> None:
    """Group endpoints by authentication requirement."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        spec = _fetch_spec(actx)
    except Exception as e:
        out.error(f"Failed to fetch spec: {e}")
        raise typer.Exit(1) from None

    routes = _extract_routes(spec)
    protected = [r for r in routes if r["protected"]]
    unprotected = [r for r in routes if not r["protected"]]

    # Get security scheme names from components
    security_schemes = list(spec.get("components", {}).get("securitySchemes", {}).keys())

    out.header(f"Authentication Summary ({len(routes)} total routes)")
    out.text("")
    out.text(f"  Protected:   [green]{len(protected)}[/green]")
    out.text(f"  Unprotected: [yellow]{len(unprotected)}[/yellow]")
    if security_schemes:
        out.text(f"  Schemes:     {', '.join(security_schemes)}")
    out.text("")

    if protected:
        rows = [[r["method"], r["path"], ", ".join(str(s) for s in r["security"])] for r in protected]
        out.table(
            title=f"Protected Endpoints ({len(protected)})",
            columns=[("Method", "bold"), ("Path", ""), ("Security", "green")],
            rows=rows,
            data_for_json=protected,
        )

    if actx.json_mode:
        out.raw_json({"protected": protected, "unprotected": unprotected, "schemes": security_schemes})


# ---------------------------------------------------------------------------
# middleware
# ---------------------------------------------------------------------------
@app.command()
def middleware(
    ctx: typer.Context,
    path: Annotated[str, typer.Argument(help="Endpoint path to inspect (e.g. /api/v1/users).")],
) -> None:
    """Describe the middleware chain for a specific endpoint path."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        spec = _fetch_spec(actx)
    except Exception as e:
        out.error(f"Failed to fetch spec: {e}")
        raise typer.Exit(1) from None

    paths = spec.get("paths", {})
    matched = {k: v for k, v in paths.items() if path in k}

    if not matched:
        out.warn(f"No endpoints matching '{path}' found in spec.")
        raise typer.Exit(1)

    # Infer middleware from path patterns and security
    chain: list[dict] = []

    # CORS — always present
    chain.append({"middleware": "CORS", "status": "enabled", "note": "All origins policy from config"})

    # Auth middleware
    for _ep_path, path_item in matched.items():
        for method, operation in path_item.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            if _is_protected(operation):
                chain.append({"middleware": "JWT Auth", "status": "enabled", "note": "Bearer token required"})
                break

    # Rate limiting — always present
    chain.append(
        {
            "middleware": "Rate Limit",
            "status": "enabled",
            "note": "Tier-based: free=30, user=100, premium=300, admin=600 req/min",
        }
    )

    # Request validation
    chain.append(
        {"middleware": "Request Validation", "status": "enabled", "note": "Pydantic body + query param validation"}
    )

    rows = [[c["middleware"], c["status"], c["note"]] for c in chain]
    out.table(
        title=f"Middleware Chain: {path}",
        columns=[("Middleware", "bold"), ("Status", "green"), ("Note", "")],
        rows=rows,
        data_for_json={"path": path, "chain": chain},
    )


# ---------------------------------------------------------------------------
# unprotected
# ---------------------------------------------------------------------------
@app.command()
def unprotected(ctx: typer.Context) -> None:
    """Find endpoints without authentication requirements."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        spec = _fetch_spec(actx)
    except Exception as e:
        out.error(f"Failed to fetch spec: {e}")
        raise typer.Exit(1) from None

    routes = _extract_routes(spec)
    unprotected_routes = [r for r in routes if not r["protected"]]

    # Filter out common public endpoints
    public_patterns = ("/health", "/openapi", "/docs", "/redoc", "/metrics")
    flagged = [r for r in unprotected_routes if not any(r["path"].startswith(p) for p in public_patterns)]

    if not flagged:
        out.success(
            f"All non-public endpoints require authentication. ({len(unprotected_routes)} public endpoints skipped)"
        )
        return

    rows = [[r["method"], r["path"], ", ".join(r["tags"]), r["summary"][:60]] for r in flagged]
    out.table(
        title=f"Potentially Unprotected Endpoints ({len(flagged)})",
        columns=[("Method", "bold"), ("Path", "yellow"), ("Tags", ""), ("Summary", "")],
        rows=rows,
        data_for_json=flagged,
    )
    out.warn(f"{len(flagged)} endpoints may be missing authentication.")


# ---------------------------------------------------------------------------
# graph
# ---------------------------------------------------------------------------
@app.command()
def graph(ctx: typer.Context) -> None:
    """Show route count per tag/module/router."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        spec = _fetch_spec(actx)
    except Exception as e:
        out.error(f"Failed to fetch spec: {e}")
        raise typer.Exit(1) from None

    routes = _extract_routes(spec)

    # Count by tag
    tag_counts: dict[str, int] = {}
    for route in routes:
        for tag in route["tags"] or ["(untagged)"]:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    sorted_tags = sorted(tag_counts.items(), key=lambda x: -x[1])

    rows = [[tag, str(count), "#" * min(count, 40)] for tag, count in sorted_tags]
    out.table(
        title=f"Routes per Module ({len(routes)} total)",
        columns=[("Module/Tag", "bold"), ("Count", ""), ("Bar", "green")],
        rows=rows,
        data_for_json=[{"tag": t, "count": c} for t, c in sorted_tags],
    )
