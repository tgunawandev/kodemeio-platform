"""Shared static analysis utilities for TSX/TS files.

Used by ui_audit, lint, state, and i18n commands to scan React source
files for shadcn violations, import patterns, query keys, and i18n issues.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# SHADCN_ELEMENT_MAP: regex pattern -> (element_name, shadcn_replacement)
# ---------------------------------------------------------------------------

SHADCN_ELEMENT_MAP: dict[str, tuple[str, str]] = {
    # Basic HTML elements
    r"<button[\s>]": ("button", "Button"),
    r"<input[\s/>]": ("input", "Input"),
    r"<select[\s>]": ("select", "Select + SelectTrigger + SelectContent + SelectItem"),
    r"<textarea[\s/>]": ("textarea", "Textarea"),
    r"<label[\s>]": ("label", "Label"),
    r"<table[\s>]": ("table", "Table + TableHeader + TableBody + TableRow"),
    r"<hr\s*/?\s*>": ("hr", "Separator"),
    # Anti-patterns: title= attribute
    r'\btitle\s*=\s*["\'{]': ("title= attr", "Tooltip + TooltipTrigger + TooltipContent"),
    # Anti-patterns: custom modal (fixed inset-0)
    r'className="[^"]*fixed\s+inset-0': ("fixed inset-0 div", "Dialog or Sheet"),
    r"className='[^']*fixed\s+inset-0": ("fixed inset-0 div", "Dialog or Sheet"),
    # Anti-patterns: animate-pulse skeleton
    r'className="[^"]*animate-pulse': ("animate-pulse div", "Skeleton"),
    r"className='[^']*animate-pulse": ("animate-pulse div", "Skeleton"),
    # Anti-patterns: absolute dropdown
    r'className="[^"]*absolute[^"]*top-': ("absolute dropdown div", "DropdownMenu"),
    r"className='[^']*absolute[^']*top-": ("absolute dropdown div", "DropdownMenu"),
    # More HTML elements
    r"<img[\s/>]": ("img", "Avatar + AvatarImage + AvatarFallback (for avatars)"),
    r"<progress[\s/>]": ("progress", "Progress"),
    r"<details[\s>]": ("details", "Collapsible + CollapsibleTrigger + CollapsibleContent"),
    r"<summary[\s>]": ("summary", "CollapsibleTrigger"),
    # Anti-patterns: overflow-auto scroll area
    r'className="[^"]*overflow-auto': ("overflow-auto div", "ScrollArea"),
    r"className='[^']*overflow-auto": ("overflow-auto div", "ScrollArea"),
    # Anti-patterns: custom toggle
    r'role="switch"': ("role=switch", "Toggle or Switch"),
    r'role="tab"': ("role=tab", "Tabs + TabsList + TabsTrigger + TabsContent"),
}


def find_raw_html_elements(file_path: Path) -> list[dict[str, str | int]]:
    """Scan a TSX file for raw HTML that should use shadcn/ui components.

    Returns a list of dicts with keys: file, line, element, replacement, code.
    """
    results: list[dict[str, str | int]] = []
    try:
        lines = file_path.read_text().splitlines()
    except OSError:
        return results

    for line_num, line in enumerate(lines, start=1):
        for pattern, (element, replacement) in SHADCN_ELEMENT_MAP.items():
            if re.search(pattern, line):
                results.append(
                    {
                        "file": str(file_path),
                        "line": line_num,
                        "element": element,
                        "replacement": replacement,
                        "code": line.strip(),
                    }
                )
    return results


def scan_imports(file_path: Path, package_name: str) -> list[str]:
    """Extract named imports from a specific package.

    Handles both single-line and multi-line import statements.
    Returns a sorted list of imported names.
    """
    try:
        text = file_path.read_text()
    except OSError:
        return []

    # Collapse multi-line imports into single lines for easier parsing
    # Match: import { ... } from "package"
    escaped = re.escape(package_name)
    pattern = rf'import\s*\{{([^}}]*)\}}\s*from\s*["\']{escaped}["\']'
    names: list[str] = []
    for match in re.finditer(pattern, text, re.DOTALL):
        raw = match.group(1)
        for name in raw.split(","):
            name = name.strip()
            if name:
                # Handle "Foo as Bar" — keep the local name
                parts = name.split(" as ")
                names.append(parts[-1].strip())
    return sorted(names)


def read_tsconfig_strict(app_dir: Path) -> bool:
    """Check if tsconfig.json has ``strict: true``.

    Handles JSON with ``//`` comments (common in tsconfig files).
    """
    tsconfig = app_dir / "tsconfig.json"
    if not tsconfig.exists():
        return False
    try:
        text = tsconfig.read_text()
        # Strip single-line comments
        text = re.sub(r"//.*", "", text)
        data = json.loads(text)
        return bool(data.get("compilerOptions", {}).get("strict", False))
    except (json.JSONDecodeError, OSError):
        return False


def find_query_keys(file_path: Path) -> list[dict[str, str | int]]:
    """Extract TanStack Query queryKey definitions from a file.

    Returns a list of dicts with keys: file, line, key_prefix, full_key.
    """
    results: list[dict[str, str | int]] = []
    try:
        lines = file_path.read_text().splitlines()
    except OSError:
        return results

    pattern = re.compile(r"queryKey\s*:\s*\[([^\]]+)\]")

    for line_num, line in enumerate(lines, start=1):
        match = pattern.search(line)
        if match:
            full_key = match.group(1).strip()
            # Extract first element as prefix (strip quotes)
            parts = [p.strip().strip("\"'") for p in full_key.split(",")]
            key_prefix = parts[0] if parts else ""
            results.append(
                {
                    "file": str(file_path),
                    "line": line_num,
                    "key_prefix": key_prefix,
                    "full_key": full_key,
                }
            )
    return results


def find_hook_files(src_dir: Path) -> list[Path]:
    """Find all TanStack Query hook files (use*.ts) in src/hooks/.

    Returns sorted list of Paths matching use*.ts in the hooks directory.
    """
    hooks_dir = src_dir / "hooks"
    if not hooks_dir.is_dir():
        return []
    return sorted(p for p in hooks_dir.iterdir() if p.is_file() and p.name.startswith("use") and p.suffix == ".ts")


def check_interpolation_vars(en: dict, id_: dict, prefix: str = "") -> list[dict[str, str | set[str]]]:
    """Compare ``{{var}}`` placeholders between en and id translation dicts.

    Recursively walks nested dicts. Returns a list of dicts with keys:
    key, en_vars, id_vars, missing_in_id, extra_in_id.
    """
    var_pattern = re.compile(r"\{\{(\w+)\}\}")
    mismatches: list[dict[str, str | set[str]]] = []

    for key in en:
        full_key = f"{prefix}.{key}" if prefix else key
        en_val = en[key]
        id_val = id_.get(key)

        if isinstance(en_val, dict):
            id_sub = id_val if isinstance(id_val, dict) else {}
            mismatches.extend(check_interpolation_vars(en_val, id_sub, prefix=full_key))
            continue

        if not isinstance(en_val, str):
            continue

        en_vars = set(var_pattern.findall(en_val))
        id_vars = set(var_pattern.findall(id_val)) if isinstance(id_val, str) else set()

        if en_vars != id_vars:
            mismatches.append(
                {
                    "key": full_key,
                    "en_vars": en_vars,
                    "id_vars": id_vars,
                    "missing_in_id": en_vars - id_vars,
                    "extra_in_id": id_vars - en_vars,
                }
            )

    return mismatches
