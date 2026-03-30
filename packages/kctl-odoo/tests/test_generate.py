"""Tests for code generation commands.

Tests the helper functions (pure logic, no I/O) directly, and uses
``typer.testing.CliRunner`` for end-to-end command invocation tests.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from kctl_odoo.commands.generate import _parse_fields, _to_snake, app

runner = CliRunner()


# ---------------------------------------------------------------------------
# _to_snake helper
# ---------------------------------------------------------------------------


class TestToSnake:
    """Test CamelCase-to-snake_case conversion."""

    def test_camel_case(self) -> None:
        """Standard CamelCase converts correctly."""
        assert _to_snake("MyModel") == "my_model"

    def test_already_snake(self) -> None:
        """Already-snake_case strings pass through unchanged."""
        assert _to_snake("my_model") == "my_model"

    def test_acronym(self) -> None:
        """Acronyms (consecutive uppercase) are handled."""
        assert _to_snake("HTMLParser") == "html_parser"

    def test_single_word(self) -> None:
        """Single lowercase word passes through."""
        assert _to_snake("model") == "model"

    def test_consecutive_upper(self) -> None:
        """Multiple consecutive uppercase letters like 'XMLHTTPRequest'."""
        result = _to_snake("XMLHTTPRequest")
        assert result == "xmlhttp_request"

    def test_numbers(self) -> None:
        """Strings with numbers are handled."""
        assert _to_snake("Order2Line") == "order2_line"


# ---------------------------------------------------------------------------
# _parse_fields helper
# ---------------------------------------------------------------------------


class TestParseFields:
    """Test field specification parsing."""

    def test_simple_fields(self) -> None:
        """Basic 'name:Char,amount:Float' parsing."""
        result = _parse_fields("name:Char,amount:Float")
        assert len(result) == 2
        assert result[0] == {"name": "name", "type": "Char", "comodel": ""}
        assert result[1] == {"name": "amount", "type": "Float", "comodel": ""}

    def test_with_comodel(self) -> None:
        """'partner_id:Many2one(res.partner)' extracts the comodel."""
        result = _parse_fields("partner_id:Many2one(res.partner)")
        assert len(result) == 1
        assert result[0]["name"] == "partner_id"
        assert result[0]["type"] == "Many2one"
        assert result[0]["comodel"] == "res.partner"

    def test_mixed_fields(self) -> None:
        """Mix of simple and relational fields."""
        result = _parse_fields("name:Char,partner_id:Many2one(res.partner),amount:Float")
        assert len(result) == 3
        assert result[1]["comodel"] == "res.partner"
        assert result[2]["comodel"] == ""

    def test_empty_string(self) -> None:
        """Empty string returns empty list."""
        assert _parse_fields("") == []

    def test_whitespace_handling(self) -> None:
        """Extra whitespace is stripped."""
        result = _parse_fields("  name : Char , amount : Float  ")
        assert len(result) == 2
        assert result[0]["name"] == "name"
        assert result[0]["type"] == "Char"

    def test_one2many_comodel(self) -> None:
        """One2many with comodel parses correctly."""
        result = _parse_fields("line_ids:One2many(sale.order.line)")
        assert result[0]["type"] == "One2many"
        assert result[0]["comodel"] == "sale.order.line"

    def test_many2many_comodel(self) -> None:
        """Many2many with comodel parses correctly."""
        result = _parse_fields("tag_ids:Many2many(res.partner.category)")
        assert result[0]["type"] == "Many2many"
        assert result[0]["comodel"] == "res.partner.category"


# ---------------------------------------------------------------------------
# generate module (CLI invocation)
# ---------------------------------------------------------------------------


class TestGenerateModule:
    """Test the 'generate module' command via CliRunner."""

    def test_creates_all_expected_files(self, tmp_path: Path) -> None:
        """Invoking generate module creates the standard directory structure."""
        result = runner.invoke(app, ["module", "test_mod", "--dest", str(tmp_path)])
        assert result.exit_code == 0, result.output

        mod_dir = tmp_path / "test_mod"
        assert mod_dir.is_dir()

        # Required files
        expected_files = [
            "__manifest__.py",
            "__init__.py",
            "CLAUDE.md",
            "models/__init__.py",
            "views",
            "security/ir.model.access.csv",
            "tests/__init__.py",
            "tests/test_test_mod.py",
        ]
        for f in expected_files:
            path = mod_dir / f
            assert path.exists(), f"Missing: {f}"

    def test_manifest_content(self, tmp_path: Path) -> None:
        """Generated __manifest__.py contains correct metadata."""
        runner.invoke(
            app,
            [
                "module",
                "my_module",
                "--dest",
                str(tmp_path),
                "--depends",
                "sale,stock",
                "--author",
                "TestCo",
                "--category",
                "Sales",
            ],
        )
        manifest = (tmp_path / "my_module" / "__manifest__.py").read_text()
        assert '"sale"' in manifest
        assert '"stock"' in manifest
        assert '"TestCo"' in manifest
        assert '"Sales"' in manifest
        assert "installable" in manifest

    def test_fastapi_creates_services_dir(self, tmp_path: Path) -> None:
        """With --fastapi, services/ and schemas/ directories are created."""
        result = runner.invoke(
            app,
            [
                "module",
                "api_mod",
                "--dest",
                str(tmp_path),
                "--fastapi",
            ],
        )
        assert result.exit_code == 0, result.output

        mod_dir = tmp_path / "api_mod"
        assert (mod_dir / "services" / "__init__.py").exists()
        assert (mod_dir / "schemas" / "__init__.py").exists()
        assert (mod_dir / "services" / "dependencies.py").exists()

        # Root __init__.py should import services
        init_content = (mod_dir / "__init__.py").read_text()
        assert "services" in init_content

    def test_no_fastapi_no_services_dir(self, tmp_path: Path) -> None:
        """Without --fastapi, services/ directory is NOT created."""
        runner.invoke(app, ["module", "plain_mod", "--dest", str(tmp_path)])
        mod_dir = tmp_path / "plain_mod"
        assert not (mod_dir / "services").exists()
        assert not (mod_dir / "schemas").exists()

    def test_no_overwrite_existing_module(self, tmp_path: Path) -> None:
        """Creating the same module twice exits with error (no overwrite)."""
        runner.invoke(app, ["module", "dup_mod", "--dest", str(tmp_path)])
        result = runner.invoke(app, ["module", "dup_mod", "--dest", str(tmp_path)])
        assert result.exit_code != 0
        assert "already exists" in result.output

    def test_security_csv_header(self, tmp_path: Path) -> None:
        """The generated ir.model.access.csv has the correct header."""
        runner.invoke(app, ["module", "sec_mod", "--dest", str(tmp_path)])
        csv_path = tmp_path / "sec_mod" / "security" / "ir.model.access.csv"
        content = csv_path.read_text()
        assert content.startswith("id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink")

    def test_test_file_content(self, tmp_path: Path) -> None:
        """The generated test file references the module name."""
        runner.invoke(app, ["module", "test_check", "--dest", str(tmp_path)])
        test_file = tmp_path / "test_check" / "tests" / "test_test_check.py"
        content = test_file.read_text()
        assert "test_check" in content
        assert "TransactionCase" in content


# ---------------------------------------------------------------------------
# generate model (CLI invocation)
# ---------------------------------------------------------------------------


class TestGenerateModel:
    """Test the 'generate model' command via CliRunner."""

    def _create_module(self, tmp_path: Path, name: str = "my_mod") -> Path:
        """Helper: scaffold a module first so model can be added."""
        runner.invoke(app, ["module", name, "--dest", str(tmp_path)])
        return tmp_path / name

    def test_creates_model_file(self, tmp_path: Path) -> None:
        """generate model creates a Python file in models/."""
        mod_dir = self._create_module(tmp_path)
        result = runner.invoke(
            app,
            [
                "model",
                str(mod_dir),
                "SaleOrder",
                "--fields",
                "name:Char,amount:Float",
            ],
        )
        assert result.exit_code == 0, result.output
        model_file = mod_dir / "models" / "sale_order.py"
        assert model_file.exists()
        content = model_file.read_text()
        assert '_name = "my_mod.sale_order"' in content
        assert "fields.Char()" in content
        assert "fields.Float()" in content

    def test_inherit_model(self, tmp_path: Path) -> None:
        """generate model --inherit creates an _inherit model."""
        mod_dir = self._create_module(tmp_path)
        result = runner.invoke(
            app,
            [
                "model",
                str(mod_dir),
                "ResPartner",
                "--inherit",
                "res.partner",
                "--fields",
                "custom_field:Boolean",
            ],
        )
        assert result.exit_code == 0, result.output
        model_file = mod_dir / "models" / "res_partner.py"
        content = model_file.read_text()
        assert '_inherit = "res.partner"' in content
        assert "_name" not in content


# ---------------------------------------------------------------------------
# generate router (CLI invocation)
# ---------------------------------------------------------------------------


class TestGenerateRouter:
    """Test the 'generate router' command via CliRunner."""

    def _create_module(self, tmp_path: Path) -> Path:
        runner.invoke(app, ["module", "api_mod", "--dest", str(tmp_path), "--fastapi"])
        return tmp_path / "api_mod"

    def test_creates_router_files(self, tmp_path: Path) -> None:
        """generate router creates router and schema files."""
        mod_dir = self._create_module(tmp_path)
        result = runner.invoke(app, ["router", str(mod_dir), "order"])
        assert result.exit_code == 0, result.output
        assert (mod_dir / "services" / "order_router.py").exists()
        assert (mod_dir / "schemas" / "order_schemas.py").exists()

    def test_crud_router_has_all_endpoints(self, tmp_path: Path) -> None:
        """--crud generates GET, POST, PUT, DELETE endpoints."""
        mod_dir = self._create_module(tmp_path)
        runner.invoke(app, ["router", str(mod_dir), "item", "--crud"])
        content = (mod_dir / "services" / "item_router.py").read_text()
        assert "item_router.get" in content
        assert "item_router.post" in content
        assert "item_router.delete" in content
