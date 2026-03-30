"""Parse React hook files for API call patterns."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# Matches: apiClient.get<Type>("url") or apiClient.post<Resp, Req>(`url`)
# Single-line variant
_API_CALL_RE = re.compile(r"apiClient\.(get|post|put|delete|patch)<([^>]*)>\s*\(\s*[`\"']([^`\"']*)[`\"']")
# Multi-line variant: captures method and generics on one line, URL on next line
_API_CALL_MULTILINE_RE = re.compile(r"apiClient\.(get|post|put|delete|patch)<([^>]*)>\s*\(\s*$")
_URL_LINE_RE = re.compile(r"^\s*[`\"']([^`\"']*)[`\"']")

# Matches template literal interpolations: ${someVar}
_TEMPLATE_VAR_RE = re.compile(r"\$\{[^}]+\}")

# Matches URLSearchParams .set("key", ...) or searchParams.set("key", ...)
_SEARCH_PARAM_RE = re.compile(r"\.set\(\s*[\"'](\w+)[\"']")


@dataclass
class HookCall:
    file: str  # relative path from app root
    line: int
    method: str  # get, post, put, delete
    url: str  # /productions/${id} (raw)
    normalized_url: str  # /productions/{id}
    response_type: str | None = None
    request_type: str | None = None
    query_params: list[str] = field(default_factory=list)


def _normalize_url(url: str) -> str:
    """Replace template literal variables with OpenAPI-style path params and clean up."""
    # Strip everything after ? (query string)
    clean = url.split("?")[0]
    # Strip template literal ternary/query patterns: ${qs ...}, ${qs}, etc.
    # This handles: /path${qs ? `?${qs}` : ""}  →  /path
    clean = re.sub(r"\$\{qs\b.*", "", clean)
    # Strip any trailing template expressions that look like query strings
    clean = re.sub(r"\$\{[^}]*qs[^}]*\}.*$", "", clean)
    # Replace path-segment template vars (e.g., ${id}, ${bomId}) with {id}
    clean = _TEMPLATE_VAR_RE.sub("{id}", clean)
    # Normalize trailing slash
    clean = clean.rstrip("/")
    return clean


def _parse_generics(generics: str) -> tuple[str | None, str | None]:
    """Parse generic type args like 'ResponseType, RequestType'."""
    parts = [p.strip() for p in generics.split(",") if p.strip()]
    response_type = parts[0] if len(parts) >= 1 else None
    request_type = parts[1] if len(parts) >= 2 else None
    return response_type, request_type


def parse_hooks(app_path: Path) -> list[HookCall]:
    """Scan hook files for API client calls and return structured results."""
    api_dir = app_path / "src" / "api"
    if not api_dir.is_dir():
        return []

    results: list[HookCall] = []

    for hook_file in sorted(api_dir.glob("use*.ts")):
        if hook_file.name == "client.ts":
            continue

        try:
            content = hook_file.read_text()
        except OSError:
            continue

        # Extract query params used across the file
        file_query_params = _SEARCH_PARAM_RE.findall(content)

        rel_path = str(hook_file.relative_to(app_path))
        lines = content.splitlines()

        pending_multiline: tuple[int, str, str] | None = None  # (line_num, method, generics)

        for line_num, line in enumerate(lines, start=1):
            # Check for multi-line continuation from previous line
            if pending_multiline is not None:
                url_match = _URL_LINE_RE.search(line)
                if url_match:
                    ml_line, method, generics = pending_multiline
                    url = url_match.group(1)
                    response_type, request_type = _parse_generics(generics)
                    normalized = _normalize_url(url)
                    results.append(
                        HookCall(
                            file=rel_path,
                            line=ml_line,
                            method=method,
                            url=url,
                            normalized_url=normalized,
                            response_type=response_type,
                            request_type=request_type,
                            query_params=file_query_params,
                        )
                    )
                pending_multiline = None
                continue

            # Single-line matches
            for match in _API_CALL_RE.finditer(line):
                method = match.group(1)
                generics = match.group(2)
                url = match.group(3)
                response_type, request_type = _parse_generics(generics)
                normalized = _normalize_url(url)
                results.append(
                    HookCall(
                        file=rel_path,
                        line=line_num,
                        method=method,
                        url=url,
                        normalized_url=normalized,
                        response_type=response_type,
                        request_type=request_type,
                        query_params=file_query_params,
                    )
                )

            # Check if this line starts a multi-line call
            ml_match = _API_CALL_MULTILINE_RE.search(line)
            if ml_match and not _API_CALL_RE.search(line):
                pending_multiline = (line_num, ml_match.group(1), ml_match.group(2))

    return results
