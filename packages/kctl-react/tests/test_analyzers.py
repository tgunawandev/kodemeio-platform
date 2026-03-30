"""Tests for core/analyzers.py — shared static analysis utilities."""

from __future__ import annotations

from pathlib import Path

from kctl_react.core.analyzers import (
    SHADCN_ELEMENT_MAP,
    check_interpolation_vars,
    find_hook_files,
    find_query_keys,
    find_raw_html_elements,
    read_tsconfig_strict,
    scan_imports,
)


class TestShadcnElementMap:
    def test_has_minimum_patterns(self) -> None:
        assert len(SHADCN_ELEMENT_MAP) >= 22

    def test_each_entry_is_tuple_pair(self) -> None:
        for _pattern, value in SHADCN_ELEMENT_MAP.items():
            assert isinstance(value, tuple) and len(value) == 2


class TestFindRawHtmlElements:
    def test_detects_raw_button(self, tmp_path: Path) -> None:
        tsx = tmp_path / "Foo.tsx"
        tsx.write_text("export const Foo = () => <button onClick={handleClick}>Save</button>;\n")
        results = find_raw_html_elements(tsx)
        assert len(results) >= 1
        assert results[0]["element"] == "button"
        assert "Button" in results[0]["replacement"]

    def test_ignores_shadcn_button(self, tmp_path: Path) -> None:
        tsx = tmp_path / "Bar.tsx"
        tsx.write_text('import { Button } from "@kodemeio/ui";\nexport const Bar = () => <Button>OK</Button>;\n')
        results = find_raw_html_elements(tsx)
        assert len(results) == 0

    def test_detects_title_attribute(self, tmp_path: Path) -> None:
        tsx = tmp_path / "Tip.tsx"
        tsx.write_text('<span title="help text">info</span>\n')
        results = find_raw_html_elements(tsx)
        assert any(r["element"] == "title= attr" for r in results)
        assert any("Tooltip" in r["replacement"] for r in results)

    def test_detects_hr_element(self, tmp_path: Path) -> None:
        tsx = tmp_path / "Div.tsx"
        tsx.write_text("<div>\n  <hr />\n</div>\n")
        results = find_raw_html_elements(tsx)
        assert any(r["element"] == "hr" for r in results)
        assert any("Separator" in r["replacement"] for r in results)

    def test_detects_custom_modal_div(self, tmp_path: Path) -> None:
        tsx = tmp_path / "Modal.tsx"
        tsx.write_text('<div className="fixed inset-0 bg-black/50">\n  <div>modal</div>\n</div>\n')
        results = find_raw_html_elements(tsx)
        assert any("Dialog" in r["replacement"] or "Sheet" in r["replacement"] for r in results)

    def test_detects_animate_pulse(self, tmp_path: Path) -> None:
        tsx = tmp_path / "Loading.tsx"
        tsx.write_text('<div className="animate-pulse h-4 w-full bg-gray-200" />\n')
        results = find_raw_html_elements(tsx)
        assert any("Skeleton" in r["replacement"] for r in results)

    def test_returns_correct_line_numbers(self, tmp_path: Path) -> None:
        tsx = tmp_path / "Lines.tsx"
        tsx.write_text("const A = () => (\n  <div>\n    <button>Click</button>\n  </div>\n);\n")
        results = find_raw_html_elements(tsx)
        assert results[0]["line"] == 3


class TestScanImports:
    def test_finds_single_line_import(self, tmp_path: Path) -> None:
        tsx = tmp_path / "Comp.tsx"
        tsx.write_text('import { Button, Input } from "@kodemeio/ui";\n')
        names = scan_imports(tsx, "@kodemeio/ui")
        assert "Button" in names
        assert "Input" in names

    def test_handles_multi_line_import(self, tmp_path: Path) -> None:
        tsx = tmp_path / "Multi.tsx"
        tsx.write_text('import {\n  Button,\n  Input,\n  Badge,\n} from "@kodemeio/ui";\n')
        names = scan_imports(tsx, "@kodemeio/ui")
        assert set(names) == {"Button", "Input", "Badge"}

    def test_ignores_other_packages(self, tmp_path: Path) -> None:
        tsx = tmp_path / "Other.tsx"
        tsx.write_text('import { useState } from "react";\nimport { Button } from "@kodemeio/ui";\n')
        names = scan_imports(tsx, "@kodemeio/ui")
        assert names == ["Button"]
        assert "useState" not in names


class TestReadTsconfigStrict:
    def test_strict_true(self, tmp_path: Path) -> None:
        tsconfig = tmp_path / "tsconfig.json"
        tsconfig.write_text('{\n  "compilerOptions": {\n    "strict": true\n  }\n}\n')
        assert read_tsconfig_strict(tmp_path) is True

    def test_strict_false(self, tmp_path: Path) -> None:
        tsconfig = tmp_path / "tsconfig.json"
        tsconfig.write_text('{\n  "compilerOptions": {\n    "strict": false\n  }\n}\n')
        assert read_tsconfig_strict(tmp_path) is False

    def test_missing_strict(self, tmp_path: Path) -> None:
        tsconfig = tmp_path / "tsconfig.json"
        tsconfig.write_text('{\n  "compilerOptions": {\n    "target": "ES2022"\n  }\n}\n')
        assert read_tsconfig_strict(tmp_path) is False

    def test_handles_comments(self, tmp_path: Path) -> None:
        tsconfig = tmp_path / "tsconfig.json"
        tsconfig.write_text('{\n  // Enable strict checks\n  "compilerOptions": {\n    "strict": true\n  }\n}\n')
        assert read_tsconfig_strict(tmp_path) is True

    def test_missing_file(self, tmp_path: Path) -> None:
        assert read_tsconfig_strict(tmp_path) is False


class TestFindQueryKeys:
    def test_finds_query_key(self, tmp_path: Path) -> None:
        hook = tmp_path / "useOrders.ts"
        hook.write_text('export const useOrders = () => useQuery({\n  queryKey: ["orders", "list"],\n});\n')
        results = find_query_keys(hook)
        assert len(results) >= 1
        assert results[0]["key_prefix"] == "orders"

    def test_finds_invalidation(self, tmp_path: Path) -> None:
        hook = tmp_path / "useMutation.ts"
        hook.write_text('queryClient.invalidateQueries({ queryKey: ["orders"] });\n')
        results = find_query_keys(hook)
        assert len(results) >= 1
        assert results[0]["key_prefix"] == "orders"


class TestFindHookFiles:
    def test_finds_hook_files(self, tmp_path: Path) -> None:
        hooks_dir = tmp_path / "src" / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "useOrders.ts").write_text("export const useOrders = () => {};\n")
        (hooks_dir / "useProducts.ts").write_text("export const useProducts = () => {};\n")
        (hooks_dir / "helpers.ts").write_text("export const helper = () => {};\n")
        results = find_hook_files(tmp_path / "src")
        assert len(results) == 2
        names = {p.name for p in results}
        assert names == {"useOrders.ts", "useProducts.ts"}

    def test_empty_when_no_hooks_dir(self, tmp_path: Path) -> None:
        results = find_hook_files(tmp_path / "src")
        assert results == []


class TestCheckInterpolationVars:
    def test_matching_vars(self) -> None:
        en = {"greeting": "Hello {{name}}, welcome to {{app}}!"}
        id_ = {"greeting": "Halo {{name}}, selamat datang di {{app}}!"}
        mismatches = check_interpolation_vars(en, id_)
        assert mismatches == []

    def test_missing_var_in_id(self) -> None:
        en = {"greeting": "Hello {{name}}, you have {{count}} items"}
        id_ = {"greeting": "Halo {{name}}, kamu punya item"}
        mismatches = check_interpolation_vars(en, id_)
        assert len(mismatches) == 1
        assert mismatches[0]["key"] == "greeting"
        assert "count" in str(mismatches[0]["missing_in_id"])

    def test_nested_keys(self) -> None:
        en = {"page": {"title": "Welcome {{user}}"}}
        id_ = {"page": {"title": "Selamat datang"}}
        mismatches = check_interpolation_vars(en, id_)
        assert len(mismatches) == 1
        assert mismatches[0]["key"] == "page.title"

    def test_extra_var_in_id(self) -> None:
        en = {"msg": "Hello"}
        id_ = {"msg": "Halo {{name}}"}
        mismatches = check_interpolation_vars(en, id_)
        assert len(mismatches) == 1
        assert "name" in str(mismatches[0]["extra_in_id"])
