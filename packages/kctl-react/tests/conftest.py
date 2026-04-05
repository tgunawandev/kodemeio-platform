"""Shared fixtures for kctl-react tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from kctl_lib.docker import DockerManager
from kctl_lib.output import Output
from typer.testing import CliRunner

from kctl_react.core.callbacks import AppContext


@pytest.fixture(autouse=True)
def reset_history_store() -> None:
    """Reset the kctl_react history singleton between tests to keep them isolated."""
    import kctl_react.core.history as history_mod

    # Clear any leftover state from a previous test
    if history_mod._store is not None:
        history_mod._store.clear("builds")
    history_mod._store = None
    yield
    if history_mod._store is not None:
        history_mod._store.clear("builds")
    history_mod._store = None


@pytest.fixture()
def mock_monorepo(tmp_path: Path) -> Path:
    """Create a minimal monorepo structure for testing."""
    # Root files
    (tmp_path / "turbo.json").write_text('{"tasks": {}}')
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "name": "kodemeio-react",
                "version": "0.1.0",
                "private": True,
            }
        )
    )
    (tmp_path / "pnpm-lock.yaml").write_text("")

    # Apps
    apps_dir = tmp_path / "apps"
    app_names = ["sfa", "lfa", "shop", "wms", "bia", "eam", "mrp", "hrm", "tpm", "dms", "saas"]
    ports = [4004, 4005, 4006, 4007, 4008, 4009, 4010, 4011, 4012, 4013, 4014]
    for app_name, port in zip(app_names, ports, strict=False):
        app_dir = apps_dir / app_name
        app_dir.mkdir(parents=True)
        (app_dir / "package.json").write_text(
            json.dumps(
                {
                    "name": f"@kodemeio/{app_name}",
                    "version": "0.1.0",
                    "scripts": {
                        "dev": f"vite --port {port}",
                        "build": "tsc -b && vite build",
                        "test": "vitest run",
                    },
                    "dependencies": {
                        "@kodemeio/core": "workspace:*",
                        "@kodemeio/ui": "workspace:*",
                    },
                    "devDependencies": {},
                }
            )
        )
        src_dir = app_dir / "src"
        src_dir.mkdir()
        (src_dir / "App.tsx").write_text("export function App() { return <div/>; }")

        # Add test files for some apps
        (src_dir / "App.test.tsx").write_text("test('renders', () => {});")
        (src_dir / "utils.test.ts").write_text("test('utils', () => {});")

        # Add openapi-ts config
        (app_dir / "openapi-ts.config.ts").write_text("export default {};")
        (app_dir / "src" / "generated").mkdir()
        types_dir = app_dir / "src" / "types"
        types_dir.mkdir()
        (types_dir / "api.ts").write_text("export type Foo = {};")

        # BadPage.tsx — raw HTML elements that violate shadcn rules
        (src_dir / "BadPage.tsx").write_text(
            "\n".join(
                [
                    'import React from "react";',
                    "export function BadPage() {",
                    "  return (",
                    "    <div>",
                    "      <button onClick={() => {}}>Click</button>",
                    '      <input type="text" />',
                    "      <select><option>A</option></select>",
                    "      <textarea />",
                    "      <table><tbody><tr><td>x</td></tr></tbody></table>",
                    "      <label>Name</label>",
                    "      <hr />",
                    '      <span title="tooltip text">hover me</span>',
                    '      <div className="fixed inset-0 bg-black/50">modal</div>',
                    '      <div className="animate-pulse h-4 w-full" />',
                    "    </div>",
                    "  );",
                    "}",
                ]
            )
        )

        # GoodPage.tsx — only shadcn components, zero violations
        (src_dir / "GoodPage.tsx").write_text(
            "\n".join(
                [
                    'import { Button, Input, Separator } from "@kodemeio/ui";',
                    "export function GoodPage() {",
                    "  return (",
                    "    <div>",
                    '      <Button variant="default">Click</Button>',
                    '      <Input type="text" />',
                    "      <Separator />",
                    "    </div>",
                    "  );",
                    "}",
                ]
            )
        )

        # i18n translation files
        # en.json has all keys including {{name}} and {{count}} in greeting
        # id.json intentionally missing: cancel, nested.deep, and {{count}} in greeting
        i18n_dir = src_dir / "i18n"
        i18n_dir.mkdir(exist_ok=True)
        (i18n_dir / "en.json").write_text(
            json.dumps(
                {
                    "title": "App Title",
                    "greeting": "Hello, {{name}}! You have {{count}} messages.",
                    "save": "Save",
                    "cancel": "Cancel",
                    "nested": {"deep": "Deep value"},
                },
                indent=2,
            )
        )
        (i18n_dir / "id.json").write_text(
            json.dumps(
                {
                    "title": "Judul App",
                    "greeting": "Halo, {{name}}! Anda punya pesan.",
                    "save": "Simpan",
                },
                indent=2,
            )
        )

        # tsconfig.json with strict mode
        (app_dir / "tsconfig.json").write_text(
            json.dumps(
                {
                    "compilerOptions": {
                        "strict": True,
                        "jsx": "react-jsx",
                        "target": "ES2020",
                        "module": "ESNext",
                        "moduleResolution": "bundler",
                    }
                },
                indent=2,
            )
        )

        # TanStack Query hook file
        hooks_dir = src_dir / "hooks"
        hooks_dir.mkdir(exist_ok=True)
        (hooks_dir / "useCustomers.ts").write_text(
            "\n".join(
                [
                    'import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";',
                    "",
                    "export function useCustomerList() {",
                    '  return useQuery({ queryKey: ["customers"], queryFn: () => [] });',
                    "}",
                    "",
                    "export function useCustomerDetail(id: number) {",
                    '  return useQuery({ queryKey: ["customers", id], queryFn: () => null });',
                    "}",
                    "",
                    "export function useCreateCustomer() {",
                    "  const qc = useQueryClient();",
                    "  return useMutation({",
                    "    mutationFn: (data: unknown) => Promise.resolve(data),",
                    '    onSuccess: () => qc.invalidateQueries({ queryKey: ["customers"] }),',
                    "  });",
                    "}",
                ]
            )
        )

        # Add env files for some apps
        if app_name in ("sfa", "wms", "mrp"):
            (app_dir / ".env").write_text(
                "VITE_ODOO_URL=http://localhost:8069\nVITE_ODOO_DB=odoo_18\nVITE_AUTH_MODE=development\n"
            )

    # Packages
    pkg_dir = tmp_path / "packages"
    for pkg_name in ["core", "ui", "tailwind-config", "vite-config", "offline"]:
        p = pkg_dir / pkg_name
        p.mkdir(parents=True)
        (p / "package.json").write_text(
            json.dumps(
                {
                    "name": f"@kodemeio/{pkg_name}",
                    "version": "0.1.0",
                    "description": f"Shared {pkg_name} package",
                }
            )
        )
        src = p / "src"
        src.mkdir()
        (src / "index.ts").write_text(f"// @kodemeio/{pkg_name}")

    # Add components.json for shadcn in packages/ui
    ui_pkg = pkg_dir / "ui"
    (ui_pkg / "components.json").write_text(
        json.dumps(
            {
                "$schema": "https://ui.shadcn.com/schema.json",
                "style": "new-york",
                "rsc": False,
                "tsx": True,
                "aliases": {"components": "src/components", "utils": "src/lib/utils"},
            }
        )
    )
    # Add some shadcn component files in packages/ui/src/components
    ui_components = ui_pkg / "src" / "components"
    ui_components.mkdir(parents=True, exist_ok=True)
    for comp_name in ["button", "input", "card", "dialog", "badge", "separator"]:
        (ui_components / f"{comp_name}.tsx").write_text(
            f"export function {comp_name.capitalize()}() {{ return null; }}"
        )
    # Add custom components
    (ui_components / "data-table.tsx").write_text("export function DataTable() { return null; }")
    (ui_components / "file-upload.tsx").write_text("export function FileUpload() { return null; }")

    return tmp_path


@pytest.fixture()
def mock_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary config directory and redirect config loading to it."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"

    monkeypatch.setattr("kctl_react.core.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("kctl_react.core.config.CONFIG_FILE", config_file)

    return config_file


@pytest.fixture
def runner() -> CliRunner:
    """Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_output() -> Output:
    """Output instance with quiet mode for testing."""
    return Output(json_mode=False, quiet=True, format="pretty")


@pytest.fixture
def mock_context(mock_monorepo: Path, mock_output: Output) -> AppContext:
    """AppContext pointed at a temporary monorepo with mocked output."""
    ctx = AppContext(quiet=True)
    ctx._project_root = mock_monorepo
    ctx._output = mock_output
    return ctx


@pytest.fixture
def mock_docker_manager() -> MagicMock:
    """Mock DockerManager spec'd to the real class."""
    mgr = MagicMock(spec=DockerManager)
    mgr.ps.return_value = []
    mgr.logs.return_value = ""
    return mgr
