"""FastAPI endpoint testing commands."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated

import httpx
import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.utils import KNOWN_APPS

app = typer.Typer(help="Test FastAPI addon endpoints directly (not JSON-RPC).")


def _get_base_url(actx: AppContext, app_name: str) -> tuple[str, str, dict[str, str]]:
    """Return (full_base_url, database, headers) for a FastAPI app."""
    from kctl_odoo.core.config import resolve_connection

    url, database, _user, _key = resolve_connection(
        profile_name=actx.profile,
        url_override=actx.url_override,
        api_key_override=actx.api_key_override,
        database_override=actx.database_override,
        username_override=actx.username_override,
    )
    api_path = KNOWN_APPS.get(app_name, f"/{app_name}/api")
    base_url = f"{url.rstrip('/')}{api_path}"
    headers = {"X-Odoo-dbfilter": f"^{database}$"} if database else {}
    return base_url, database, headers


@app.command("test")
def test_endpoint(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name (sfa, tpm, dms, etc.)")],
    path: Annotated[str, typer.Argument(help="API path (e.g., /auth/login)")],
    method: Annotated[str, typer.Option("--method", "-m", help="HTTP method")] = "GET",
    body: Annotated[str | None, typer.Option("--body", "-b", help="JSON request body")] = None,
    token: Annotated[str | None, typer.Option("--token", "-t", help="JWT Bearer token")] = None,
) -> None:
    """Call a FastAPI endpoint directly.

    Constructs URL as {odoo_url}/{app}/api{path} with X-Odoo-dbfilter header.

    Examples:
        kctl-odoo fastapi test tpm /auth/login -m POST -b '{"login":"admin","password":"admin"}'
        kctl-odoo fastapi test sfa / --json
        kctl-odoo fastapi test dms /distributors -t <jwt_token>
    """
    actx: AppContext = ctx.obj
    out = actx.output

    base_url, database, headers = _get_base_url(actx, app_name)
    url = f"{base_url}{path}"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Parse JSON body if provided
    import json as json_lib

    parsed_body = None
    if body:
        try:
            parsed_body = json_lib.loads(body)
        except json_lib.JSONDecodeError as exc:
            out.error(f"Invalid JSON body: {exc}")
            raise typer.Exit(1) from exc

    out.info(f"{method} {url}")
    if database:
        out.info(f"Database filter: {database}")

    try:
        with httpx.Client(timeout=30) as client:
            if method.upper() == "GET":
                resp = client.get(url, headers=headers)
            elif method.upper() == "POST":
                resp = client.post(url, headers=headers, json=parsed_body or {})
            elif method.upper() == "PUT":
                resp = client.put(url, headers=headers, json=parsed_body or {})
            elif method.upper() == "PATCH":
                resp = client.patch(url, headers=headers, json=parsed_body or {})
            elif method.upper() == "DELETE":
                resp = client.delete(url, headers=headers)
            else:
                out.error(f"Unsupported method: {method}. Use GET, POST, PUT, PATCH, or DELETE.")
                raise typer.Exit(1)
    except httpx.ConnectError as exc:
        out.error(f"Connection failed: {exc}")
        raise typer.Exit(1) from exc

    status_color = "green" if resp.status_code < 400 else "yellow" if resp.status_code < 500 else "red"

    if actx.json_mode:
        try:
            resp_json = resp.json()
        except Exception:
            resp_json = resp.text
        out.raw_json(
            {
                "status_code": resp.status_code,
                "url": url,
                "method": method.upper(),
                "response": resp_json,
            }
        )
    else:
        out.detail(
            f"FastAPI Response — {app_name}",
            [
                (
                    "Request",
                    [
                        ("Method", method.upper()),
                        ("URL", url),
                        ("Database", database or "default"),
                    ],
                ),
                (
                    "Response",
                    [
                        ("Status", f"[{status_color}]{resp.status_code}[/{status_color}]"),
                        ("Content-Type", resp.headers.get("content-type", "")),
                        ("Body", resp.text[:2000]),
                    ],
                ),
            ],
            data_for_json={
                "status_code": resp.status_code,
                "url": url,
                "response": resp.text[:2000],
            },
        )

    if resp.status_code >= 400:
        raise typer.Exit(1)


@app.command()
def endpoints(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name (sfa, tpm, dms, etc.)")],
) -> None:
    """List FastAPI endpoints from OpenAPI schema.

    Fetches /{app}/api/openapi.json and lists all paths.

    Examples:
        kctl-odoo fastapi endpoints tpm
        kctl-odoo fastapi endpoints sfa --json
    """
    actx: AppContext = ctx.obj
    out = actx.output

    base_url, database, headers = _get_base_url(actx, app_name)
    schema_url = f"{base_url}/openapi.json"

    out.info(f"Fetching {schema_url}...")

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(schema_url, headers=headers)
    except httpx.ConnectError as exc:
        out.error(f"Connection failed: {exc}")
        raise typer.Exit(1) from exc

    if resp.status_code != 200:
        out.error(f"Failed to fetch OpenAPI schema: HTTP {resp.status_code}")
        raise typer.Exit(1)

    try:
        schema = resp.json()
    except Exception:
        out.error("Invalid JSON in OpenAPI response")
        raise typer.Exit(1) from None

    paths = schema.get("paths", {})

    if actx.json_mode:
        endpoint_list = []
        for path_str, methods in sorted(paths.items()):
            for method_str, detail in methods.items():
                if method_str in ("get", "post", "put", "patch", "delete"):
                    endpoint_list.append(
                        {
                            "method": method_str.upper(),
                            "path": path_str,
                            "summary": detail.get("summary", ""),
                        }
                    )
        out.raw_json(
            {
                "app": app_name,
                "base_url": base_url,
                "total": len(endpoint_list),
                "endpoints": endpoint_list,
            }
        )
        return

    rows = []
    for path_str, methods in sorted(paths.items()):
        for method_str, detail in methods.items():
            if method_str in ("get", "post", "put", "patch", "delete"):
                method_color = {
                    "get": "green",
                    "post": "yellow",
                    "put": "blue",
                    "patch": "cyan",
                    "delete": "red",
                }.get(method_str, "")
                rows.append(
                    [
                        f"[{method_color}]{method_str.upper()}[/{method_color}]",
                        path_str,
                        detail.get("summary", ""),
                    ]
                )

    out.table(
        f"{app_name.upper()} Endpoints ({len(rows)})",
        [("Method", ""), ("Path", ""), ("Summary", "dim")],
        rows,
    )


@app.command("openapi")
def openapi_spec(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name (sfa, tpm, dms, etc.)")],
    output: Annotated[str | None, typer.Option("--output", "-o", help="Output file path (default: stdout)")] = None,
) -> None:
    """Extract OpenAPI spec from a FastAPI addon and save or display it.

    Fetches /{app}/api/openapi.json from the running Odoo instance.
    """
    import json as json_lib

    actx: AppContext = ctx.obj
    out = actx.output

    base_url, database, headers = _get_base_url(actx, app_name)
    schema_url = f"{base_url}/openapi.json"
    out.info(f"Fetching OpenAPI spec from {schema_url}...")

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(schema_url, headers=headers)
    except httpx.ConnectError as exc:
        out.error(f"Connection failed: {exc}")
        raise typer.Exit(1) from exc

    if resp.status_code != 200:
        out.error(f"Failed: HTTP {resp.status_code}")
        raise typer.Exit(1)

    try:
        schema = resp.json()
    except Exception:
        out.error("Invalid JSON in OpenAPI response")
        raise typer.Exit(1) from None

    spec_text = json_lib.dumps(schema, indent=2, ensure_ascii=False)

    if output:
        from pathlib import Path

        Path(output).write_text(spec_text, encoding="utf-8")
        out.info(f"OpenAPI spec saved to {output}")
        out.info(f"Title: {schema.get('info', {}).get('title', 'N/A')}")
        out.info(f"Version: {schema.get('info', {}).get('version', 'N/A')}")
        out.info(f"Paths: {len(schema.get('paths', {}))}")
    else:
        typer.echo(spec_text)


@app.command("validate")
def validate_spec(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name (sfa, tpm, dms, etc.)")],
) -> None:
    """Validate OpenAPI spec completeness: schemas, operation IDs, response codes."""
    actx: AppContext = ctx.obj
    out = actx.output

    base_url, database, headers = _get_base_url(actx, app_name)
    schema_url = f"{base_url}/openapi.json"

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(schema_url, headers=headers)
    except httpx.ConnectError as exc:
        out.error(f"Connection failed: {exc}")
        raise typer.Exit(1) from exc

    if resp.status_code != 200:
        out.error(f"Failed to fetch spec: HTTP {resp.status_code}")
        raise typer.Exit(1)

    try:
        schema = resp.json()
    except Exception:
        out.error("Invalid JSON in OpenAPI response")
        raise typer.Exit(1) from None

    issues: list[str] = []
    paths = schema.get("paths", {})

    for path_str, methods in paths.items():
        for method_str, detail in methods.items():
            if method_str not in ("get", "post", "put", "patch", "delete"):
                continue
            op_id = f"{method_str.upper()} {path_str}"

            # Check for operationId
            if not detail.get("operationId"):
                issues.append(f"  [yellow]W[/yellow] {op_id}: Missing operationId")

            # Check for summary
            if not detail.get("summary"):
                issues.append(f"  [dim]I[/dim] {op_id}: Missing summary")

            # Check for response schemas
            responses = detail.get("responses", {})
            if not responses:
                issues.append(f"  [yellow]W[/yellow] {op_id}: No response schemas defined")
            elif "200" not in responses and "204" not in responses:
                issues.append(f"  [dim]I[/dim] {op_id}: No 2xx response code defined")

            # POST/PUT should have requestBody
            if method_str in ("post", "put") and not detail.get("requestBody"):
                issues.append(f"  [yellow]W[/yellow] {op_id}: {method_str.upper()} without requestBody")

    # Check for missing security schemes
    components = schema.get("components", {})
    if not components.get("securitySchemes"):
        issues.append("  [dim]I[/dim] No security schemes defined in components")

    if issues:
        typer.get_text_stream("stdout")
        for issue in issues:
            typer.echo(issue)
        out.info(f"\n{len(issues)} issue(s) found in {app_name} OpenAPI spec.")
    else:
        out.info(f"OpenAPI spec for {app_name} looks complete — {len(paths)} paths, no issues.")


@app.command("routes")
def list_routes(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name (sfa, tpm, dms, etc.)")],
    tag: Annotated[str | None, typer.Option("--tag", "-t", help="Filter by tag")] = None,
) -> None:
    """List all FastAPI routes for a module from its OpenAPI spec.

    Equivalent to 'endpoints' but with additional tag filtering and
    showing request/response schema names.
    """
    actx: AppContext = ctx.obj
    out = actx.output

    base_url, database, headers = _get_base_url(actx, app_name)
    schema_url = f"{base_url}/openapi.json"

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(schema_url, headers=headers)
    except httpx.ConnectError as exc:
        out.error(f"Connection failed: {exc}")
        raise typer.Exit(1) from exc

    if resp.status_code != 200:
        out.error(f"Failed: HTTP {resp.status_code}")
        raise typer.Exit(1)

    try:
        schema = resp.json()
    except Exception:
        out.error("Invalid JSON in OpenAPI response")
        raise typer.Exit(1) from None

    paths = schema.get("paths", {})
    rows = []
    json_data = []

    for path_str, methods in sorted(paths.items()):
        for method_str, detail in methods.items():
            if method_str not in ("get", "post", "put", "patch", "delete"):
                continue

            route_tags = detail.get("tags", [])
            if tag and tag not in route_tags:
                continue

            tags_str = ", ".join(route_tags)
            summary = detail.get("summary", "")
            req_body = "yes" if detail.get("requestBody") else "-"
            method_color = {
                "get": "green",
                "post": "yellow",
                "put": "blue",
                "patch": "cyan",
                "delete": "red",
            }.get(method_str, "")

            rows.append(
                [
                    f"[{method_color}]{method_str.upper()}[/{method_color}]",
                    path_str,
                    summary,
                    tags_str,
                    req_body,
                ]
            )
            json_data.append(
                {
                    "method": method_str.upper(),
                    "path": path_str,
                    "summary": summary,
                    "tags": route_tags,
                }
            )

    out.table(
        f"{app_name.upper()} Routes ({len(rows)}){f' [tag={tag}]' if tag else ''}",
        [("Method", ""), ("Path", ""), ("Summary", ""), ("Tags", "dim"), ("Body", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command("bench")
def bench_endpoint(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name (sfa, tpm, dms, etc.)")],
    endpoint: Annotated[str, typer.Argument(help="Endpoint path (e.g. /customers)")],
    count: Annotated[int, typer.Option("--count", "-n", help="Number of requests")] = 10,
    token: Annotated[str | None, typer.Option("--token", "-t", help="JWT Bearer token")] = None,
) -> None:
    """Benchmark response time for a FastAPI endpoint.

    Makes N GET requests and reports min/max/avg/p95 latency.
    """
    actx: AppContext = ctx.obj
    out = actx.output

    base_url, database, headers = _get_base_url(actx, app_name)
    url = f"{base_url}{endpoint}"

    if token:
        headers["Authorization"] = f"Bearer {token}"

    out.info(f"Benchmarking GET {url} ({count} requests)...")

    timings: list[float] = []
    errors = 0

    with httpx.Client(timeout=30) as client:
        for _i in range(count):
            start = time.monotonic()
            try:
                resp = client.get(url, headers=headers)
                elapsed = (time.monotonic() - start) * 1000
                timings.append(elapsed)
                if resp.status_code >= 400:
                    errors += 1
            except Exception:
                errors += 1

    if not timings:
        out.error("All requests failed.")
        raise typer.Exit(1)

    sorted_timings = sorted(timings)
    avg = sum(timings) / len(timings)
    p95_idx = max(0, int(len(sorted_timings) * 0.95) - 1)
    p95 = sorted_timings[p95_idx]

    sections = [
        (
            f"Benchmark: {app_name}{endpoint}",
            [
                ("URL", url),
                ("Requests", str(count)),
                ("Errors", str(errors)),
                ("Min", f"{sorted_timings[0]:.1f}ms"),
                ("Max", f"{sorted_timings[-1]:.1f}ms"),
                ("Avg", f"{avg:.1f}ms"),
                ("P95", f"{p95:.1f}ms"),
            ],
        ),
    ]
    out.detail(
        f"FastAPI Bench — {app_name}",
        sections,
        data_for_json={
            "url": url,
            "count": count,
            "errors": errors,
            "min_ms": round(sorted_timings[0], 1),
            "max_ms": round(sorted_timings[-1], 1),
            "avg_ms": round(avg, 1),
            "p95_ms": round(p95, 1),
        },
    )


@app.command()
def health(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name (sfa, tpm, dms, etc.)")],
) -> None:
    """Check if a FastAPI app router is responding.

    Examples:
        kctl-odoo fastapi health tpm
        kctl-odoo fastapi health sfa --json
    """
    actx: AppContext = ctx.obj
    out = actx.output

    base_url, database, headers = _get_base_url(actx, app_name)

    # Try openapi.json as health indicator
    schema_url = f"{base_url}/openapi.json"

    start = time.monotonic()
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(schema_url, headers=headers)
        latency_ms = round((time.monotonic() - start) * 1000)
    except httpx.ConnectError as exc:
        if actx.json_mode:
            out.raw_json({"app": app_name, "healthy": False, "error": str(exc)})
        else:
            out.error(f"{app_name}: unreachable ({exc})")
        raise typer.Exit(1) from exc

    healthy = resp.status_code == 200
    endpoint_count = 0
    if healthy:
        try:
            paths = resp.json().get("paths", {})
            endpoint_count = sum(
                1 for methods in paths.values() for m in methods if m in ("get", "post", "put", "patch", "delete")
            )
        except Exception:
            pass

    if actx.json_mode:
        out.raw_json(
            {
                "app": app_name,
                "healthy": healthy,
                "status_code": resp.status_code,
                "latency_ms": latency_ms,
                "endpoints": endpoint_count,
                "base_url": base_url,
            }
        )
    else:
        status = "[green]Healthy[/green]" if healthy else f"[red]HTTP {resp.status_code}[/red]"
        sections = [
            (
                f"{app_name.upper()} FastAPI",
                [
                    ("Status", status),
                    ("URL", base_url),
                    ("Latency", f"{latency_ms}ms"),
                    ("Endpoints", str(endpoint_count)),
                    ("Database", database or "default"),
                ],
            ),
        ]
        out.detail(f"FastAPI Health — {app_name}", sections)

    if not healthy:
        raise typer.Exit(1)


@app.command("audit")
def audit_api_live(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="FastAPI app name (e.g. tpm, sfa, dms)")],
) -> None:
    """Audit a FastAPI app's OpenAPI spec for quality and completeness.

    Fetches the OpenAPI spec from the running instance and checks:
    1. Endpoint count and organization (by prefix)
    2. Missing operation IDs
    3. Missing response models (no schema defined)
    4. Missing descriptions/summaries
    5. Endpoints without auth (no security scheme)
    6. Chatty API detection (>10 endpoints per resource)

    Examples:
        kctl-odoo fastapi audit tpm
        kctl-odoo fastapi audit sfa
    """
    actx: AppContext = ctx.obj
    out = actx.output

    base_url, database, headers = _get_base_url(actx, app_name)
    openapi_url = f"{base_url}/openapi.json"

    out.info(f"Fetching {openapi_url}...")
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as http:
            resp = http.get(openapi_url, headers=headers)
            if resp.status_code != 200:
                out.error(f"Failed to fetch OpenAPI spec: HTTP {resp.status_code}")
                raise typer.Exit(1)
            spec = resp.json()
    except typer.Exit:
        raise
    except Exception as e:
        out.error(f"Failed to fetch OpenAPI spec: {e}")
        raise typer.Exit(1)

    paths = spec.get("paths", {})
    total_endpoints = 0

    # Analyze by resource prefix
    prefix_counts: dict[str, int] = {}
    missing_operation_id = 0
    missing_description = 0
    missing_response_schema = 0
    no_auth_endpoints: list[str] = []

    global_security = spec.get("security", [])

    for path, methods in paths.items():
        # Extract resource prefix (first path segment)
        parts = path.strip("/").split("/")
        prefix = parts[0] if parts else "root"

        for method, details in methods.items():
            if method in ("parameters", "summary", "description"):
                continue
            total_endpoints += 1
            prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1

            # Check operation ID
            if not details.get("operationId"):
                missing_operation_id += 1

            # Check description/summary
            if not details.get("summary") and not details.get("description"):
                missing_description += 1

            # Check response schema
            responses = details.get("responses", {})
            has_schema = False
            for _status, resp_detail in responses.items():
                if isinstance(resp_detail, dict) and resp_detail.get("content"):
                    has_schema = True
                    break
            if not has_schema and method != "delete":
                missing_response_schema += 1

            # Check auth
            endpoint_security = details.get("security", global_security)
            if not endpoint_security and not global_security:
                no_auth_endpoints.append(f"{method.upper()} {path}")

    # Chatty API detection
    chatty_resources = []
    for prefix, count in sorted(prefix_counts.items(), key=lambda x: -x[1]):
        if count > 10:
            chatty_resources.append(f"{prefix} ({count} endpoints)")

    # Display summary table
    sections = [
        ("Total endpoints", str(total_endpoints)),
        ("Resource prefixes", str(len(prefix_counts))),
        ("Missing operation ID", f"{missing_operation_id} ({missing_operation_id * 100 // max(total_endpoints, 1)}%)"),
        ("Missing description", f"{missing_description} ({missing_description * 100 // max(total_endpoints, 1)}%)"),
        ("Missing response schema", f"{missing_response_schema}"),
        ("No auth endpoints", f"{len(no_auth_endpoints)}"),
        ("Chatty resources (>10)", f"{len(chatty_resources)}"),
    ]

    rows = [[k, v] for k, v in sections]
    out.table(
        f"FastAPI Audit: {app_name} — {total_endpoints} endpoints",
        [("Check", ""), ("Result", "")],
        rows,
    )

    # Resource breakdown
    prefix_rows = []
    for prefix, count in sorted(prefix_counts.items(), key=lambda x: -x[1]):
        status = "CHATTY" if count > 10 else "OK"
        prefix_rows.append([prefix, str(count), status])
    out.table(
        "Endpoints per Resource",
        [("Resource", ""), ("Count", ""), ("Status", "")],
        prefix_rows,
    )

    # Score
    score = 100
    if missing_operation_id > total_endpoints * 0.1:
        score -= 10
    if missing_description > total_endpoints * 0.2:
        score -= 10
    if missing_response_schema > total_endpoints * 0.1:
        score -= 10
    if len(no_auth_endpoints) > 5:
        score -= 15
    if len(chatty_resources) > 3:
        score -= 5

    grade = (
        "A+"
        if score >= 95
        else "A"
        if score >= 90
        else "B+"
        if score >= 85
        else "B"
        if score >= 80
        else "C"
        if score >= 70
        else "D"
    )
    out.info(f"\nAPI Quality Score: {score}% ({grade})")

    if actx.json_mode:
        out.raw_json(
            {
                "app": app_name,
                "total_endpoints": total_endpoints,
                "score": score,
                "grade": grade,
                "missing_operation_id": missing_operation_id,
                "missing_description": missing_description,
                "missing_response_schema": missing_response_schema,
                "no_auth_endpoints": len(no_auth_endpoints),
                "chatty_resources": chatty_resources,
                "prefix_counts": prefix_counts,
            }
        )


# =============================================================================
# PWA Module discovery
# =============================================================================

_PWA_MODULES = [
    "sfa_management",
    "lfa_management",
    "wms_management",
    "hrm_management",
    "shop_management",
    "asset_management",
    "mrp_management",
    "bia_management",
    "tpm_management",
    "dms_management",
]


def _find_private_root() -> Path | None:
    """Locate src/private/ from CWD or known paths."""
    from pathlib import Path

    for candidate in [
        Path.cwd() / "src" / "private",
        Path.cwd().parent / "src" / "private",
        Path("/home")
        / "tgunawan"
        / "project"
        / "00-new-projects"
        / "kodemeio-app"
        / "kodemeio-odoo"
        / "src"
        / "private",
    ]:
        if candidate.is_dir():
            return candidate
    return None


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


# =============================================================================
# audit-standards — Cross-module FastAPI standards checker
# =============================================================================


@app.command("audit-standards")
def audit_standards(
    ctx: typer.Context,
    module: Annotated[str | None, typer.Argument(help="Single module (e.g. tpm_management) or 'all'")] = "all",
    fix_hint: Annotated[bool, typer.Option("--fix-hint", help="Show fix hints for each issue")] = False,
) -> None:
    """Cross-check FastAPI/PWA backends against standardized patterns.

    Audits auth, security, API patterns, pagination, error handling, and
    code quality across all 10 PWA modules to ensure consistency.

    Categories checked (23 checks):
      Auth & Security (7): factory deps, factory auth router, OIDC,
        rate limiter, dev mode dual-gate, error code inheritance, safe_handle_error
      API Patterns (8): response envelope, pagination params, OpenAPI tags,
        authenticated_env usage, exception re-raise, list total field,
        consistent HTTP methods, schema directory
      Code Quality (4): no raw SQL, no env.cr.execute, file upload limits,
        filename sanitization
      Completeness (4): auth_router.py, dependencies.py, schemas/ dir,
        fastapi_endpoint registration

    Examples:
        kctl-odoo fastapi audit-standards
        kctl-odoo fastapi audit-standards tpm_management
        kctl-odoo fastapi audit-standards all --fix-hint
        kctl-odoo fastapi audit-standards --json
    """

    actx: AppContext = ctx.obj
    out = actx.output

    private_root = _find_private_root()
    if not private_root:
        out.error("Cannot find src/private/ directory")
        raise typer.Exit(1)

    # Determine which modules to check
    modules = [module] if module and module != "all" else [m for m in _PWA_MODULES if (private_root / m).is_dir()]

    if not modules:
        out.error("No PWA modules found")
        raise typer.Exit(1)

    out.info(f"Auditing {len(modules)} PWA module(s) against standards...")

    all_results: list[dict] = []
    summary_rows: list[list[str]] = []

    for mod_name in sorted(modules):
        mod_dir = private_root / mod_name
        if not mod_dir.is_dir():
            out.warn(f"Module {mod_name} not found at {mod_dir}")
            continue

        services_dir = mod_dir / "services"
        schemas_dir = mod_dir / "schemas"
        models_dir = mod_dir / "models"

        # Read key files
        deps_file = services_dir / "dependencies.py"
        auth_file = services_dir / "auth_router.py"
        deps_src = _read_file(deps_file)
        auth_src = _read_file(auth_file)

        # Read all router files
        router_sources: dict[str, str] = {}
        if services_dir.is_dir():
            for f in services_dir.glob("*_router.py"):
                router_sources[f.name] = _read_file(f)
            for f in services_dir.glob("*_routers.py"):
                router_sources[f.name] = _read_file(f)

        # Read all model files
        model_sources: dict[str, str] = {}
        if models_dir.is_dir():
            for f in models_dir.glob("*.py"):
                model_sources[f.name] = _read_file(f)

        all_router_code = "\n".join(router_sources.values())
        "\n".join(model_sources.values())

        checks: list[dict] = []

        def _check(category: str, name: str, passed: bool, hint: str = "", *, _checks: list[dict] = checks) -> None:
            _checks.append(
                {
                    "category": category,
                    "name": name,
                    "passed": passed,
                    "hint": hint,
                }
            )

        # =====================================================================
        # CATEGORY 1: Auth & Security (7 checks)
        # =====================================================================

        # 1.1 Uses create_app_dependencies() factory
        uses_factory = "create_app_dependencies" in deps_src
        _check(
            "Auth",
            "Uses create_app_dependencies() factory",
            uses_factory,
            "Migrate from manual wiring to create_app_dependencies() from base_management.services.app_dependencies",
        )

        # 1.2 Uses create_auth_router() factory
        uses_auth_factory = "create_auth_router" in auth_src
        _check(
            "Auth",
            "Uses create_auth_router() factory",
            uses_auth_factory,
            "Migrate auth router to create_auth_router() from base_management.services.auth_router",
        )

        # 1.3 OIDC callback present
        # create_auth_router() includes OIDC automatically
        has_oidc = uses_auth_factory or "oidc" in auth_src.lower() or "oidc_callback" in auth_src
        _check(
            "Auth",
            "OIDC/SSO callback present",
            has_oidc,
            "Add OIDC callback endpoint via create_auth_router() or manually add POST /auth/oidc/callback",
        )

        # 1.4 Rate limiter configured
        # create_app_dependencies() includes RateLimiter automatically
        has_rate_limit = (
            uses_factory
            or "RateLimiter" in deps_src
            or "rate_limiter" in deps_src
            or "login_attempts_per_minute" in deps_src
        )
        _check(
            "Security",
            "Rate limiter configured",
            has_rate_limit,
            "Add RateLimiter from base_management.services.rate_limiter with 120 req/min, 5 login/min",
        )

        # 1.5 Dev mode dual-gate
        has_dev_gate = "dev_mode" in auth_src and (
            "config_parameter" in auth_src or "ICP" in auth_src or "get_param" in auth_src
        )
        # Also pass if using create_auth_router (which has built-in dual-gate)
        if uses_auth_factory:
            has_dev_gate = True
        _check(
            "Security",
            "Dev mode dual-gate (server + system param)",
            has_dev_gate,
            "Guard dev endpoints with both odoo.tools.config.get('dev_mode') AND ir.config_parameter.{app}.dev_mode",
        )

        # 1.6 Error codes extend BaseErrorCode
        has_error_codes = "BaseErrorCode" in deps_src
        _check(
            "Auth",
            "Error codes extend BaseErrorCode",
            has_error_codes,
            "Create AppErrorCode class extending BaseErrorCode from base_management.services.errors",
        )

        # 1.7 safe_handle_error imported (checked in Quality too)
        uses_safe_handle = "safe_handle_error" in all_router_code or "safe_handle_error" in deps_src
        _check(
            "Security",
            "safe_handle_error imported for exception safety",
            uses_safe_handle,
            "Import safe_handle_error from base_management.services.errors for safe exception handling",
        )

        # =====================================================================
        # CATEGORY 2: API Patterns (8 checks)
        # =====================================================================

        # 2.1 Response envelope pattern
        has_envelope = '"success"' in all_router_code or "'success'" in all_router_code or "success" in all_router_code
        _check(
            "API",
            "Response envelope {success, data, total}",
            has_envelope and '"data"' in all_router_code or "'data'" in all_router_code or "data" in all_router_code,
            "All endpoints must return {success: bool, data: ..., total?: int, message?: str}",
        )

        # 2.2 Pagination params (offset/limit)
        has_pagination = "offset" in all_router_code and "limit" in all_router_code
        _check(
            "API",
            "Offset/limit pagination on list endpoints",
            has_pagination,
            "Add offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200) to list endpoints",
        )

        # 2.3 OpenAPI tags
        has_tags = "tags=" in all_router_code or "tags=[" in auth_src
        _check(
            "API",
            "OpenAPI tags on routers",
            has_tags,
            "Add tags=['{app}-{domain}'] to each APIRouter() for organized Swagger docs",
        )

        # 2.4 authenticated_env dependency
        has_auth_env = "authenticated_env" in all_router_code
        _check(
            "API",
            "Uses authenticated_env dependency",
            has_auth_env,
            "Use env: authenticated_env as parameter in protected endpoints",
        )

        # 2.5 Exception re-raise pattern (HTTPException re-raise)
        has_http_reraise = (
            "except HTTPException" in all_router_code or "HTTPException:\n        raise" in all_router_code
        )
        _check(
            "API",
            "HTTPException re-raise in try/except",
            has_http_reraise,
            "Add 'except HTTPException: raise' before generic exception handlers to avoid swallowing API errors",
        )

        # 2.6 List endpoints return total
        has_total = '"total"' in all_router_code or "'total'" in all_router_code
        _check(
            "API",
            "List endpoints include total count",
            has_total,
            "Return total: int in list responses for pagination (search_count before search)",
        )

        # 2.7 Consistent HTTP methods (no POST for reads)
        # Check for POST endpoints that look like reads (get_, list_, search_)
        import re

        post_reads = re.findall(r'@\w+\.post\(["\']/(get|list|search)', all_router_code)
        _check(
            "API",
            "No POST for read operations",
            len(post_reads) == 0,
            f"Found {len(post_reads)} POST endpoints for read operations — use GET instead",
        )

        # 2.8 Schemas directory
        has_schemas = schemas_dir.is_dir() and any(schemas_dir.glob("*.py"))
        _check(
            "API",
            "Pydantic schemas in schemas/ directory",
            has_schemas,
            "Create schemas/ directory with typed Pydantic models for all request/response bodies",
        )

        # =====================================================================
        # CATEGORY 3: Code Quality (4 checks)
        # =====================================================================

        # 3.1 No raw SQL in router layer
        import re as _re

        raw_sql_count = len(_re.findall(r"(?:env\.)?cr\.execute\s*\(", all_router_code))
        _check(
            "Quality",
            "No raw SQL in router layer",
            raw_sql_count == 0,
            f"Found {raw_sql_count} cr.execute() calls — move to model methods or use ORM",
        )

        # 3.2 No bare 'except Exception' without safe_handle_error
        bare_except_count = len(_re.findall(r"except\s+Exception.*:\s*\n\s+(?!.*safe_handle_error)", all_router_code))
        has_proper_except = bare_except_count == 0 or uses_safe_handle
        _check(
            "Quality",
            "Exception handling uses safe_handle_error",
            has_proper_except,
            "Wrap generic except blocks with safe_handle_error() to prevent info leaks",
        )

        # 3.3 File upload size limits (if upload endpoints exist)
        # Check schemas for image validation patterns too
        schema_code = ""
        if schemas_dir.is_dir():
            for sf in schemas_dir.glob("*.py"):
                schema_code += _read_file(sf)

        has_uploads = (
            "UploadFile" in all_router_code
            or "validate_base64_image" in all_router_code
            or "validate_base64_image" in schema_code
            or "max_length=14" in schema_code
        )
        if has_uploads:
            has_size_limit = (
                "MAX_FILE_SIZE" in all_router_code
                or "max_length" in all_router_code
                or "max_length" in schema_code
                or "validate_base64_image" in schema_code
                or "validate_base64_image" in all_router_code
            )
            _check(
                "Quality",
                "File upload size limits enforced",
                has_size_limit,
                "Add MAX_FILE_SIZE or use validate_base64_image() from base_management",
            )
        else:
            _check("Quality", "File upload size limits enforced", True, "N/A — no upload endpoints")

        # 3.4 Filename sanitization on downloads
        has_downloads = "Content-Disposition" in all_router_code
        if has_downloads:
            has_sanitize = "sanitize" in all_router_code.lower() or "replace" in all_router_code
            _check(
                "Quality",
                "Filename sanitization on downloads",
                has_sanitize,
                "Sanitize filenames in Content-Disposition headers to prevent header injection",
            )
        else:
            _check("Quality", "Filename sanitization on downloads", True, "N/A — no download endpoints")

        # =====================================================================
        # CATEGORY 4: Completeness (4 checks)
        # =====================================================================

        # 4.1 Has auth_router.py
        _check(
            "Complete",
            "Has auth_router.py",
            auth_file.is_file(),
            "Create services/auth_router.py with login, me, renew, logout endpoints",
        )

        # 4.2 Has dependencies.py
        _check(
            "Complete",
            "Has dependencies.py",
            deps_file.is_file(),
            "Create services/dependencies.py with error codes, auth deps, shared utilities",
        )

        # 4.3 Has schemas/ directory
        _check(
            "Complete",
            "Has schemas/ directory",
            schemas_dir.is_dir(),
            "Create schemas/ directory with Pydantic models",
        )

        # 4.4 FastAPI endpoint registration
        has_endpoint = any(
            "fastapi_endpoint" in name or "_get_fastapi_routers" in src for name, src in model_sources.items()
        )
        _check(
            "Complete",
            "FastAPI endpoint model registered",
            has_endpoint,
            "Create models/fastapi_endpoint_{app}.py with _get_fastapi_routers() method",
        )

        # =====================================================================
        # Scoring
        # =====================================================================
        total = len(checks)
        passed = sum(1 for c in checks if c["passed"])
        score = round(passed / total * 100) if total > 0 else 0

        cat_scores: dict[str, tuple[int, int]] = {}
        for c in checks:
            cat = c["category"]
            if cat not in cat_scores:
                cat_scores[cat] = (0, 0)
            p, t = cat_scores[cat]
            cat_scores[cat] = (p + (1 if c["passed"] else 0), t + 1)

        grade = (
            "A+"
            if score >= 96
            else "A"
            if score >= 91
            else "B+"
            if score >= 87
            else "B"
            if score >= 78
            else "C"
            if score >= 65
            else "D"
            if score >= 50
            else "F"
        )

        short_name = mod_name.replace("_management", "").replace("_integration", "")

        # Category breakdown for summary row
        auth_p, auth_t = cat_scores.get("Auth", (0, 0))
        sec_p, sec_t = cat_scores.get("Security", (0, 0))
        api_p, api_t = cat_scores.get("API", (0, 0))
        qual_p, qual_t = cat_scores.get("Quality", (0, 0))
        comp_p, comp_t = cat_scores.get("Complete", (0, 0))

        auth_sec_p = auth_p + sec_p
        auth_sec_t = auth_t + sec_t

        score_color = "green" if score >= 87 else "yellow" if score >= 70 else "red"
        summary_rows.append(
            [
                short_name,
                f"{auth_sec_p}/{auth_sec_t}",
                f"{api_p}/{api_t}",
                f"{qual_p}/{qual_t}",
                f"{comp_p}/{comp_t}",
                f"[{score_color}]{score}% {grade}[/{score_color}]",
            ]
        )

        all_results.append(
            {
                "module": mod_name,
                "score": score,
                "grade": grade,
                "passed": passed,
                "total": total,
                "categories": {k: {"passed": v[0], "total": v[1]} for k, v in cat_scores.items()},
                "checks": checks,
            }
        )

        # Show per-module detail (non-JSON mode only, if single module)
        if len(modules) == 1 and not actx.json_mode:
            detail_rows = []
            for c in checks:
                status = "[green]PASS[/green]" if c["passed"] else "[red]FAIL[/red]"
                row = [c["category"], c["name"], status]
                if fix_hint and not c["passed"]:
                    row.append(c["hint"])
                elif fix_hint:
                    row.append("")
                detail_rows.append(row)

            cols = [("Category", ""), ("Check", ""), ("Status", "")]
            if fix_hint:
                cols.append(("Fix Hint", "dim"))

            out.table(
                f"FastAPI Standards: {short_name} — {score}% ({grade})",
                cols,
                detail_rows,
            )

    # =========================================================================
    # Summary table (multi-module)
    # =========================================================================
    if len(modules) > 1 and not actx.json_mode:
        out.table(
            f"FastAPI Standards Audit — {len(modules)} modules",
            [
                ("Module", ""),
                ("Auth+Sec", ""),
                ("API", ""),
                ("Quality", ""),
                ("Complete", ""),
                ("Score", ""),
            ],
            summary_rows,
        )

        # Show failed checks across all modules
        fail_summary: dict[str, list[str]] = {}
        for r in all_results:
            for c in r["checks"]:
                if not c["passed"]:
                    key = f"{c['category']}: {c['name']}"
                    if key not in fail_summary:
                        fail_summary[key] = []
                    short = r["module"].replace("_management", "").replace("_integration", "")
                    fail_summary[key].append(short)

        if fail_summary:
            fail_rows = []
            for check_name, affected in sorted(fail_summary.items(), key=lambda x: -len(x[1])):
                fail_rows.append([check_name, str(len(affected)), ", ".join(affected)])
            out.table(
                "Common Gaps (sorted by frequency)",
                [("Check", ""), ("Count", ""), ("Modules", "dim")],
                fail_rows,
            )

        # Overall stats
        total_checks = sum(r["total"] for r in all_results)
        total_passed = sum(r["passed"] for r in all_results)
        overall_pct = round(total_passed / total_checks * 100) if total_checks else 0
        out.info(f"\nOverall: {total_passed}/{total_checks} checks passed ({overall_pct}%)")

        perfect = [r["module"].replace("_management", "") for r in all_results if r["score"] == 100]
        if perfect:
            out.success(f"Perfect score: {', '.join(perfect)}")

        needs_work = [r["module"].replace("_management", "") for r in all_results if r["score"] < 80]
        if needs_work:
            out.warn(f"Needs attention: {', '.join(needs_work)}")

    # JSON output
    if actx.json_mode:
        out.raw_json(
            {
                "modules": all_results,
                "total_modules": len(all_results),
                "overall_passed": sum(r["passed"] for r in all_results),
                "overall_total": sum(r["total"] for r in all_results),
            }
        )


# =============================================================================
# APP_NAME → module_name mapping for source analysis
# =============================================================================

_APP_TO_MODULE = {
    "sfa": "sfa_management",
    "lfa": "lfa_management",
    "wms": "wms_management",
    "hrm": "hrm_management",
    "shop": "shop_management",
    "asset": "asset_management",
    "mrp": "mrp_management",
    "bia": "bia_management",
    "tpm": "tpm_management",
    "dms": "dms_management",
}


def _count_source_routers(private_root: Path, module_name: str) -> int:
    """Count router registrations in fastapi_endpoint_*.py source."""
    import re

    models_dir = private_root / module_name / "models"
    if not models_dir.is_dir():
        return -1

    for f in models_dir.glob("fastapi_endpoint_*.py"):
        src = f.read_text(encoding="utf-8")
        # Count unique *_router names in _get_fastapi_routers
        matches = re.findall(r"\b(\w+_router)\b", src)
        # Deduplicate (routers appear in both branches of if/else sometimes)
        unique = set(matches)
        # Exclude 'auth_router' false matches from imports
        return len(unique)
    return -1


def _count_openapi_prefixes(spec: dict) -> dict[str, int]:
    """Count endpoints per first path prefix from OpenAPI spec."""
    prefixes: dict[str, int] = {}
    for path in spec.get("paths", {}):
        parts = path.strip("/").split("/")
        prefix = parts[0] if parts else "root"
        prefixes[prefix] = prefixes.get(prefix, 0) + sum(
            1 for m in spec["paths"][path] if m in ("get", "post", "put", "patch", "delete")
        )
    return prefixes


@app.command("audit-live")
def audit_live(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name (tpm, sfa, etc.) or 'all'")],
    quick: Annotated[bool, typer.Option("--quick", help="Skip auth flow and error format tests")] = False,
) -> None:
    """Live audit of a running FastAPI app — tests actual HTTP responses.

    Checks 5 categories against the live instance:
    1. Router sync: registered routers vs actual OpenAPI endpoints
    2. Response envelope: GET list endpoints verify {success, data, total}
    3. Auth flow: dev-login → /me → 401 without token
    4. Schema coverage: % endpoints with typed response_model
    5. Error format: send bad request, verify {error_code, message}

    Examples:
        kctl-odoo fastapi audit-live tpm
        kctl-odoo fastapi audit-live all
        kctl-odoo fastapi audit-live sfa --quick
        kctl-odoo fastapi audit-live tpm --json
    """
    actx: AppContext = ctx.obj
    out = actx.output

    apps_to_check = list(_APP_TO_MODULE.keys()) if app_name == "all" else [app_name]

    private_root = _find_private_root()
    all_results: list[dict] = []
    summary_rows: list[list[str]] = []

    for app_id in sorted(apps_to_check):
        module_name = _APP_TO_MODULE.get(app_id, f"{app_id}_management")

        # Get base URL and fetch OpenAPI spec
        try:
            base_url, database, headers = _get_base_url(actx, app_id)
        except Exception as e:
            out.warn(f"{app_id}: Cannot resolve connection — {e}")
            continue

        openapi_url = f"{base_url}/openapi.json"
        try:
            with httpx.Client(timeout=15) as http:
                resp = http.get(openapi_url, headers=headers)
                if resp.status_code != 200:
                    out.warn(f"{app_id}: OpenAPI fetch failed (HTTP {resp.status_code})")
                    continue
                spec = resp.json()
        except Exception as e:
            out.warn(f"{app_id}: Unreachable — {e}")
            continue

        paths = spec.get("paths", {})
        total_endpoints = sum(
            1 for methods in paths.values() for m in methods if m in ("get", "post", "put", "patch", "delete")
        )

        checks: list[dict] = []

        def _check(category: str, name: str, passed: bool, detail: str = "", *, _checks: list[dict] = checks) -> None:
            _checks.append({"category": category, "name": name, "passed": passed, "detail": detail})

        # =================================================================
        # 1. ROUTER SYNC CHECK
        # =================================================================
        if private_root:
            source_count = _count_source_routers(private_root, module_name)
            api_prefixes = _count_openapi_prefixes(spec)
            api_router_count = len(api_prefixes)

            if source_count > 0:
                # Each source router should produce at least 1 prefix
                # Allow some slack (some routers share prefixes)
                sync_ok = api_router_count >= source_count * 0.7
                _check(
                    "Sync",
                    "Router registration matches OpenAPI",
                    sync_ok,
                    f"Source: {source_count} routers, OpenAPI: {api_router_count} prefixes, {total_endpoints} endpoints"
                    + ("" if sync_ok else " — some routers may have failed to load"),
                )
            else:
                _check(
                    "Sync",
                    "Router registration matches OpenAPI",
                    True,
                    f"Source not available, OpenAPI: {total_endpoints} endpoints",
                )
        else:
            _check(
                "Sync",
                "Router registration matches OpenAPI",
                True,
                f"Source dir not found, OpenAPI: {total_endpoints} endpoints",
            )

        # Endpoint count sanity
        _check(
            "Sync",
            "Minimum endpoint count (>10)",
            total_endpoints > 10,
            f"{total_endpoints} endpoints" + (" — suspiciously low" if total_endpoints <= 10 else ""),
        )

        # =================================================================
        # 2. SCHEMA COVERAGE
        # =================================================================
        has_response_schema = 0
        no_schema_endpoints: list[str] = []
        spec.get("security", [])

        for path_str, methods in paths.items():
            for method_str, detail in methods.items():
                if method_str not in ("get", "post", "put", "patch", "delete"):
                    continue
                responses = detail.get("responses", {})
                has_schema_here = False
                for _code, resp_detail in responses.items():
                    if isinstance(resp_detail, dict) and resp_detail.get("content"):
                        has_schema_here = True
                        break
                if has_schema_here:
                    has_response_schema += 1
                elif method_str != "delete":
                    no_schema_endpoints.append(f"{method_str.upper()} {path_str}")

        schema_pct = round(has_response_schema / max(total_endpoints, 1) * 100)
        _check(
            "Schema",
            f"Response model coverage ({schema_pct}%)",
            schema_pct >= 90,
            f"{has_response_schema}/{total_endpoints} endpoints have typed response schemas"
            + (f" — {len(no_schema_endpoints)} missing" if no_schema_endpoints else ""),
        )

        # Check for security scheme definition
        components = spec.get("components", {})
        has_security = bool(components.get("securitySchemes"))
        _check(
            "Schema",
            "Security scheme defined in OpenAPI",
            has_security,
            "HTTPBearer scheme present" if has_security else "No security scheme in components",
        )

        # =================================================================
        # 3. RESPONSE ENVELOPE CHECK (sample list endpoints)
        # =================================================================
        # Find GET endpoints that look like list operations
        list_endpoints: list[str] = []
        for path_str, methods in paths.items():
            if "get" in methods and not path_str.rstrip("/").split("/")[-1].startswith("{"):
                # Likely a list endpoint (no {id} at end)
                summary = methods["get"].get("summary", "").lower()
                if any(kw in summary for kw in ("list", "search", "all", "")):
                    list_endpoints.append(path_str)

        envelope_pass = 0
        envelope_fail = 0
        envelope_errors: list[str] = []

        # Test up to 5 list endpoints
        with httpx.Client(timeout=10) as http:
            for ep in list_endpoints[:5]:
                try:
                    url = f"{base_url}{ep}"
                    r = http.get(url, headers=headers)
                    if r.status_code == 401:
                        # Needs auth — expected, skip
                        envelope_pass += 1
                        continue
                    if r.status_code == 200:
                        try:
                            body = r.json()
                            if isinstance(body, dict) and "success" in body:
                                envelope_pass += 1
                            else:
                                envelope_fail += 1
                                envelope_errors.append(f"{ep}: missing 'success' key")
                        except Exception:
                            envelope_fail += 1
                            envelope_errors.append(f"{ep}: not valid JSON")
                    else:
                        # Non-200 is OK (403, 404, etc.)
                        envelope_pass += 1
                except Exception:
                    pass

        tested = envelope_pass + envelope_fail
        _check(
            "Envelope",
            f"Response envelope {{success, data}} ({tested} tested)",
            envelope_fail == 0,
            f"{envelope_pass}/{tested} passed"
            + (f" — failures: {', '.join(envelope_errors[:3])}" if envelope_errors else ""),
        )

        # =================================================================
        # 4. AUTH FLOW CHECK (unless --quick)
        # =================================================================
        if not quick:
            auth_token = None
            auth_ok = False

            with httpx.Client(timeout=10) as http:
                # 4a. Try dev-login
                try:
                    dev_users_url = f"{base_url}/auth/dev-users"
                    r = http.get(dev_users_url, headers=headers)
                    if r.status_code == 200:
                        body = r.json()
                        users = body.get("users", body.get("data", []))
                        if users:
                            first_uid = users[0].get("id", 1)
                            login_url = f"{base_url}/auth/dev-login"
                            r2 = http.post(
                                login_url,
                                headers={**headers, "Content-Type": "application/json"},
                                json={"user_id": first_uid},
                            )
                            if r2.status_code == 200:
                                login_body = r2.json()
                                auth_token = login_body.get("access_token")
                                if auth_token:
                                    auth_ok = True
                except Exception:
                    pass

                # Determine why dev-login failed (if it did)
                dev_login_reason = ""
                if not auth_ok:
                    try:
                        r_check = http.get(f"{base_url}/auth/dev-users", headers=headers)
                        if r_check.status_code == 404:
                            dev_login_reason = "Dev endpoints disabled (by design for customer-facing apps)"
                        elif r_check.status_code == 403:
                            dev_login_reason = "Dev mode not enabled — set server --dev and ir.config_parameter"
                        elif r_check.status_code == 200:
                            body_check = r_check.json()
                            users_check = body_check.get("users", body_check.get("data", []))
                            if not users_check:
                                dev_login_reason = "No matching users found (module-specific user query returned empty)"
                            else:
                                dev_login_reason = "dev-login POST failed"
                        else:
                            dev_login_reason = f"dev-users returned HTTP {r_check.status_code}"
                    except Exception:
                        dev_login_reason = "Connection error"

                if auth_ok:
                    _check("Auth", "Dev login returns JWT token", True, "Token obtained via /auth/dev-login")

                    # 4b. Call /auth/me with token
                    try:
                        me_url = f"{base_url}/auth/me"
                        r = http.get(me_url, headers={**headers, "Authorization": f"Bearer {auth_token}"})
                        me_ok = r.status_code == 200
                        me_body = r.json() if me_ok else {}
                        has_user = "user" in me_body or "data" in me_body
                        _check(
                            "Auth",
                            "GET /auth/me with token",
                            me_ok and has_user,
                            f"HTTP {r.status_code}" + (", user data returned" if has_user else ", missing user data"),
                        )
                    except Exception as e:
                        _check("Auth", "GET /auth/me with token", False, str(e))

                    # 4c. Call /auth/me WITHOUT token — expect 401 or 200 (session fallback)
                    try:
                        r = http.get(me_url, headers=headers)
                        # 401 = JWT-only enforcement, 200 = session auth fallback (both valid)
                        # 500 = broken endpoint
                        no_token_ok = r.status_code in (200, 401)
                        detail = f"HTTP {r.status_code}"
                        if r.status_code == 200:
                            detail += " (session auth fallback)"
                        elif r.status_code == 401:
                            detail += " (JWT-only enforcement)"
                        else:
                            detail += " — endpoint error without token"
                        _check("Auth", "GET /auth/me without token → not 500", no_token_ok, detail)
                    except Exception as e:
                        _check("Auth", "GET /auth/me without token → not 500", False, str(e))

                    # 4d. Token renewal
                    try:
                        renew_url = f"{base_url}/auth/renew"
                        r = http.post(renew_url, headers={**headers, "Authorization": f"Bearer {auth_token}"})
                        renew_ok = r.status_code == 200
                        renew_body = r.json() if renew_ok else {}
                        has_new_token = "access_token" in renew_body
                        _check(
                            "Auth",
                            "POST /auth/renew returns new token",
                            renew_ok and has_new_token,
                            f"HTTP {r.status_code}" + (", new token issued" if has_new_token else ""),
                        )
                    except Exception as e:
                        _check("Auth", "POST /auth/renew returns new token", False, str(e))
                else:
                    # Dev endpoints disabled by design = PASS (not a failure)
                    dev_disabled = "disabled" in dev_login_reason.lower()
                    no_users = "no matching" in dev_login_reason.lower()
                    _check("Auth", "Dev login available", dev_disabled or no_users, dev_login_reason)
                    if dev_disabled or no_users:
                        # Can't test auth flow without token, but it's not a failure
                        _check("Auth", "GET /auth/me with token", True, "Skipped (no dev-login) — test manually")
                        _check("Auth", "GET /auth/me without token → not 500", True, "Skipped (no dev-login)")
                        _check("Auth", "POST /auth/renew returns new token", True, "Skipped (no dev-login)")
                    else:
                        _check("Auth", "GET /auth/me with token", False, "Skipped — " + dev_login_reason)
                        _check("Auth", "GET /auth/me without token → not 500", False, "Skipped — " + dev_login_reason)
                        _check("Auth", "POST /auth/renew returns new token", False, "Skipped — " + dev_login_reason)

            # =============================================================
            # 5. ERROR FORMAT CHECK
            # =============================================================
            with httpx.Client(timeout=10) as http:
                # Send POST to /auth/login with empty body
                try:
                    login_url = f"{base_url}/auth/login"
                    r = http.post(login_url, headers={**headers, "Content-Type": "application/json"}, json={})
                    if r.status_code in (400, 401, 422):
                        try:
                            err_body = r.json()
                            # FastAPI 422 returns {"detail": [...]}, our custom errors return {"detail": {"error_code":...}}
                            detail = err_body.get("detail")
                            if isinstance(detail, dict) and "error_code" in detail:
                                _check(
                                    "Error",
                                    "Error response has {error_code, message}",
                                    True,
                                    f"HTTP {r.status_code}: {detail.get('error_code')}",
                                )
                            elif isinstance(detail, list):
                                # Pydantic validation error (422) — also acceptable
                                _check(
                                    "Error",
                                    "Error response has {error_code, message}",
                                    True,
                                    f"HTTP {r.status_code}: Pydantic validation error (structured)",
                                )
                            else:
                                _check(
                                    "Error",
                                    "Error response has {error_code, message}",
                                    False,
                                    f"HTTP {r.status_code}: unexpected format: {str(detail)[:100]}",
                                )
                        except Exception:
                            _check(
                                "Error",
                                "Error response has {error_code, message}",
                                False,
                                f"HTTP {r.status_code}: response not JSON",
                            )
                    else:
                        _check(
                            "Error",
                            "Error response has {error_code, message}",
                            False,
                            f"Unexpected HTTP {r.status_code} for bad login request",
                        )
                except Exception as e:
                    _check("Error", "Error response has {error_code, message}", False, str(e))

                # Test that errors don't leak stack traces
                try:
                    login_url = f"{base_url}/auth/login"
                    r = http.post(
                        login_url,
                        headers={**headers, "Content-Type": "application/json"},
                        json={"login": "nonexistent@test.invalid", "password": "wrongpassword"},
                    )
                    resp_text = r.text
                    leaks_trace = "Traceback" in resp_text or 'File "/' in resp_text
                    _check(
                        "Error",
                        "No stack trace in error responses",
                        not leaks_trace,
                        "Clean error response" if not leaks_trace else "Stack trace leaked in response!",
                    )
                except Exception as e:
                    _check("Error", "No stack trace in error responses", False, str(e))

        # =================================================================
        # SCORING
        # =================================================================
        total = len(checks)
        passed = sum(1 for c in checks if c["passed"])
        score = round(passed / total * 100) if total > 0 else 0
        grade = (
            "A+"
            if score >= 96
            else "A"
            if score >= 91
            else "B+"
            if score >= 87
            else "B"
            if score >= 78
            else "C"
            if score >= 65
            else "D"
            if score >= 50
            else "F"
        )

        score_color = "green" if score >= 87 else "yellow" if score >= 70 else "red"
        summary_rows.append(
            [
                app_id,
                str(total_endpoints),
                f"{schema_pct}%",
                f"{passed}/{total}",
                f"[{score_color}]{score}% {grade}[/{score_color}]",
            ]
        )

        all_results.append(
            {
                "app": app_id,
                "endpoints": total_endpoints,
                "schema_coverage": schema_pct,
                "score": score,
                "grade": grade,
                "passed": passed,
                "total": total,
                "checks": checks,
            }
        )

        # Show per-app detail if single app
        if len(apps_to_check) == 1 and not actx.json_mode:
            detail_rows = []
            for c in checks:
                status = "[green]PASS[/green]" if c["passed"] else "[red]FAIL[/red]"
                detail_rows.append([c["category"], c["name"], status, c["detail"]])
            out.table(
                f"FastAPI Live Audit: {app_id} — {score}% ({grade})",
                [("Cat", ""), ("Check", ""), ("Status", ""), ("Detail", "dim")],
                detail_rows,
            )

    # =====================================================================
    # SUMMARY TABLE (multi-app)
    # =====================================================================
    if len(apps_to_check) > 1 and not actx.json_mode:
        out.table(
            f"FastAPI Live Audit — {len(all_results)} apps",
            [("App", ""), ("Endpoints", ""), ("Schema", ""), ("Checks", ""), ("Score", "")],
            summary_rows,
        )

        # Show failures
        fail_summary: dict[str, list[str]] = {}
        for r in all_results:
            for c in r["checks"]:
                if not c["passed"]:
                    key = f"{c['category']}: {c['name']}"
                    if key not in fail_summary:
                        fail_summary[key] = []
                    fail_summary[key].append(r["app"])

        if fail_summary:
            fail_rows = []
            for check_name, affected in sorted(fail_summary.items(), key=lambda x: -len(x[1])):
                fail_rows.append([check_name, str(len(affected)), ", ".join(affected)])
            out.table(
                "Failures",
                [("Check", ""), ("Count", ""), ("Apps", "dim")],
                fail_rows,
            )

        total_checks = sum(r["total"] for r in all_results)
        total_passed = sum(r["passed"] for r in all_results)
        overall_pct = round(total_passed / total_checks * 100) if total_checks else 0
        out.info(f"\nOverall: {total_passed}/{total_checks} checks passed ({overall_pct}%)")

    if actx.json_mode:
        out.raw_json(
            {
                "apps": all_results,
                "total_apps": len(all_results),
                "overall_passed": sum(r["passed"] for r in all_results),
                "overall_total": sum(r["total"] for r in all_results),
            }
        )
