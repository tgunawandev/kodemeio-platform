from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from kctl_odoo.commands.roles import _resolve_roles_file
from kctl_odoo.commands.roles import app as roles_app

runner = CliRunner()


@patch("kctl_odoo.commands.roles._get_client")
def test_roles_list_shows_roles_with_user_counts(mock_get_client):
    client = MagicMock()
    client.search_read.side_effect = [
        [
            {"id": 1, "name": "Branch Staff", "implied_ids": [1, 2, 3]},
            {"id": 2, "name": "Director / Owner", "implied_ids": [1, 2, 3, 4]},
        ],
        [{"user_id": [46, "intan"]}, {"user_id": [43, "victor"]}],
        [{"user_id": [2, "admin"]}],
    ]
    mock_get_client.return_value = client
    result = runner.invoke(roles_app, ["list"])
    assert result.exit_code == 0
    assert "Branch Staff" in result.stdout
    assert "Director / Owner" in result.stdout


@patch("kctl_odoo.commands.roles._get_client")
def test_roles_show_prints_role_detail(mock_get_client):
    client = MagicMock()
    client.search_read.side_effect = [
        [{"id": 1, "name": "Branch Staff", "implied_ids": [10, 20]}],
        [{"user_id": [46, "intan"]}],
        [],  # hidden menus lookup (no hides for this role)
    ]
    client.read.side_effect = [
        [
            {"id": 10, "name": "POS User", "full_name": "Point of Sale / User"},
            {"id": 20, "name": "Stock User", "full_name": "Inventory / User"},
        ],
        [{"id": 1, "group_id": [500, "Branch Staff Group"]}],  # role group_id lookup
    ]
    mock_get_client.return_value = client
    result = runner.invoke(roles_app, ["show", "Branch Staff"])
    assert result.exit_code == 0
    assert "Point of Sale / User" in result.stdout
    assert "intan" in result.stdout


@patch("kctl_odoo.commands.roles._get_client")
def test_roles_show_displays_hidden_menus(mock_get_client):
    client = MagicMock()
    client.search_read.side_effect = [
        [{"id": 1, "name": "HR Officer", "implied_ids": [10]}],
        [],  # no users assigned
        [{"id": 77, "name": "Sales"}, {"id": 78, "name": "CRM"}],  # hidden menus
    ]
    client.read.side_effect = [
        [{"id": 10, "name": "HR User", "full_name": "HR / User"}],
        [{"id": 1, "group_id": [501, "HR Officer Group"]}],
    ]
    mock_get_client.return_value = client
    result = runner.invoke(roles_app, ["show", "HR Officer"])
    assert result.exit_code == 0
    assert "Hidden menus" in result.stdout
    assert "Sales" in result.stdout
    assert "CRM" in result.stdout


@patch("kctl_odoo.commands.roles._get_client")
def test_roles_show_errors_on_unknown_role(mock_get_client):
    client = MagicMock()
    client.search_read.return_value = []
    mock_get_client.return_value = client
    result = runner.invoke(roles_app, ["show", "Ghost"])
    assert result.exit_code != 0
    combined = (result.stdout or "") + (result.stderr or "")
    assert "not found" in combined.lower()


@patch("kctl_odoo.commands.roles._get_client")
def test_roles_sync_dry_run_prints_plan_no_writes(mock_get_client, tmp_path):
    yaml_file = tmp_path / "roles.yaml"
    yaml_file.write_text(
        "version: 1\nroles:\n  sales_user:\n    name: Sales User\n    groups: [sales_team.group_sale_salesman]\n"
    )

    client = MagicMock()
    client.search_read.side_effect = [
        [],
        [{"id": 1, "model": "res.groups", "module": "sales_team", "name": "group_sale_salesman", "res_id": 42}],
    ]
    mock_get_client.return_value = client

    result = runner.invoke(roles_app, ["sync", "--file", str(yaml_file), "--dry-run"])
    assert result.exit_code == 0
    assert "create" in result.stdout.lower()
    assert "sales user" in result.stdout.lower() or "sales_user" in result.stdout.lower()
    assert client.create.call_args_list == []
    assert client.write.call_args_list == []
    assert client.unlink.call_args_list == []


@patch("kctl_odoo.commands.roles._get_client")
def test_roles_sync_applies_create(mock_get_client, tmp_path):
    yaml_file = tmp_path / "roles.yaml"
    yaml_file.write_text(
        "version: 1\nroles:\n  sales_user:\n    name: Sales User\n    groups: [sales_team.group_sale_salesman]\n"
    )

    client = MagicMock()
    client.search_read.side_effect = [
        [],
        [{"id": 1, "model": "res.groups", "module": "sales_team", "name": "group_sale_salesman", "res_id": 42}],
    ]
    client.create.return_value = 999
    mock_get_client.return_value = client

    result = runner.invoke(roles_app, ["sync", "--file", str(yaml_file)])
    assert result.exit_code == 0
    create_calls = [
        call for call in client.create.call_args_list if len(call.args) >= 1 and call.args[0] == "res.users.role"
    ]
    assert len(create_calls) == 1


@patch("kctl_odoo.commands.roles._get_client")
def test_roles_sync_warns_on_missing_xmlids(mock_get_client, tmp_path):
    yaml_file = tmp_path / "roles.yaml"
    yaml_file.write_text(
        "version: 1\n"
        "roles:\n"
        "  director_owner:\n"
        "    name: Director / Owner\n"
        "    groups:\n"
        "      - base.group_user\n"
        "      - point_of_sale.group_pos_manager\n"
    )

    client = MagicMock()
    client.search_read.side_effect = [
        [],
        [{"id": 1, "model": "res.groups", "module": "base", "name": "group_user", "res_id": 1}],
    ]
    mock_get_client.return_value = client

    result = runner.invoke(roles_app, ["sync", "--file", str(yaml_file), "--dry-run"])
    assert result.exit_code == 0
    assert "point_of_sale.group_pos_manager" in result.stdout
    assert (
        "skipped" in result.stdout.lower()
        or "missing" in result.stdout.lower()
        or "not installed" in result.stdout.lower()
    )


@patch("kctl_odoo.commands.roles._get_client")
def test_roles_sync_strict_exits_2_on_missing_xmlid(mock_get_client, tmp_path):
    yaml_file = tmp_path / "roles.yaml"
    yaml_file.write_text(
        "version: 1\n"
        "roles:\n"
        "  director_owner:\n"
        "    name: Director / Owner\n"
        "    groups:\n"
        "      - base.group_user\n"
        "      - point_of_sale.group_pos_manager\n"
    )
    client = MagicMock()
    client.search_read.side_effect = [
        [],
        [{"id": 1, "model": "res.groups", "module": "base", "name": "group_user", "res_id": 1}],
    ]
    mock_get_client.return_value = client

    result = runner.invoke(
        roles_app,
        ["sync", "--file", str(yaml_file), "--dry-run", "--strict"],
    )
    assert result.exit_code == 2
    assert "point_of_sale.group_pos_manager" in result.stdout


@patch("kctl_odoo.commands.roles._get_client")
def test_roles_diff_reports_drift(mock_get_client, tmp_path):
    yaml_file = tmp_path / "roles.yaml"
    yaml_file.write_text(
        "version: 1\nroles:\n  sales_user:\n    name: Sales User\n    groups: [sales_team.group_sale_salesman]\n"
    )
    client = MagicMock()
    client.search_read.side_effect = [
        [{"id": 1, "name": "Sales User", "implied_ids": [42, 99]}],
        [{"id": 1, "model": "res.groups", "module": "sales_team", "name": "group_sale_salesman", "res_id": 42}],
    ]
    mock_get_client.return_value = client
    result = runner.invoke(roles_app, ["diff", "--file", str(yaml_file)])
    assert result.exit_code == 0
    assert "drift" in result.stdout.lower() or "update" in result.stdout.lower()


@patch("kctl_odoo.commands.roles._get_client")
def test_roles_audit_finds_orphan_groups(mock_get_client, tmp_path):
    yaml_file = tmp_path / "roles.yaml"
    yaml_file.write_text(
        "version: 1\nroles:\n  sales_user:\n    name: Sales User\n    groups: [sales_team.group_sale_salesman]\n"
    )
    ignored_file = tmp_path / "roles.ignored.yaml"
    ignored_file.write_text("version: 1\nignored: []\n")

    client = MagicMock()
    client.search_read.side_effect = [
        [
            {"id": 42, "full_name": "Sales / User"},
            {"id": 99, "full_name": "Fleet / Manager"},
        ],
        [
            {"id": 10, "model": "res.groups", "module": "sales_team", "name": "group_sale_salesman", "res_id": 42},
            {"id": 11, "model": "res.groups", "module": "fleet", "name": "fleet_manager", "res_id": 99},
        ],
        [{"id": 10, "model": "res.groups", "module": "sales_team", "name": "group_sale_salesman", "res_id": 42}],
    ]
    mock_get_client.return_value = client

    result = runner.invoke(
        roles_app,
        ["audit", "--file", str(yaml_file), "--ignored-file", str(ignored_file)],
    )
    assert result.exit_code == 0
    assert "fleet.fleet_manager" in result.stdout or "fleet_manager" in result.stdout


@patch("kctl_odoo.commands.roles._get_client")
def test_roles_audit_strict_exits_nonzero_on_findings(mock_get_client, tmp_path):
    yaml_file = tmp_path / "roles.yaml"
    yaml_file.write_text("version: 1\nroles: {}\n")
    ignored_file = tmp_path / "roles.ignored.yaml"
    ignored_file.write_text("version: 1\nignored: []\n")

    client = MagicMock()
    client.search_read.side_effect = [
        [{"id": 99, "full_name": "Fleet / Manager"}],
        [{"id": 11, "model": "res.groups", "module": "fleet", "name": "fleet_manager", "res_id": 99}],
    ]
    mock_get_client.return_value = client

    result = runner.invoke(
        roles_app,
        ["audit", "--file", str(yaml_file), "--ignored-file", str(ignored_file), "--strict"],
    )
    assert result.exit_code == 1


@patch("kctl_odoo.commands.roles._get_client")
def test_roles_assign_attaches_roles_and_ous(mock_get_client):
    client = MagicMock()
    client.search_read.side_effect = [
        [{"id": 46, "login": "intan.rahayu"}],
        [{"id": 5, "name": "Branch Staff"}],
        [{"id": 1, "code": "BHO"}, {"id": 3, "code": "TSLO1"}],
    ]
    client.write.return_value = True
    mock_get_client.return_value = client
    result = runner.invoke(
        roles_app,
        ["assign", "intan.rahayu", "Branch Staff", "--ous", "BHO,TSLO1"],
    )
    assert result.exit_code == 0
    write_calls = [c for c in client.write.call_args_list if len(c.args) >= 1 and c.args[0] == "res.users"]
    assert len(write_calls) == 1
    payload = write_calls[0].args[2]
    assert "role_line_ids" in payload
    assert "assigned_operating_unit_ids" in payload
    assert payload.get("default_operating_unit_id") == 1


@patch("kctl_odoo.commands.roles._get_client")
def test_roles_assign_clear_wipes_roles(mock_get_client):
    client = MagicMock()
    client.search_read.side_effect = [
        [{"id": 46, "login": "intan.rahayu"}],
    ]
    client.write.return_value = True
    mock_get_client.return_value = client
    result = runner.invoke(roles_app, ["assign", "intan.rahayu", "--clear"])
    assert result.exit_code == 0
    write_calls = client.write.call_args_list
    assert write_calls
    payload = write_calls[0].args[2]
    assert payload["role_line_ids"] == [(5, 0, 0)]


@patch("kctl_odoo.commands.roles._get_client")
def test_roles_sync_applies_menu_visibility(mock_get_client, tmp_path):
    yaml_file = tmp_path / "roles.yaml"
    yaml_file.write_text(
        "version: 1\n"
        "roles:\n"
        "  hr_user:\n"
        "    name: HR Officer\n"
        "    groups: [hr.group_hr_user]\n"
        "    hide_menus: [Sales]\n"
    )

    client = MagicMock()
    client.search_read.side_effect = [
        # _fetch_db_state: list roles (HR Officer already exists, same group)
        [{"id": 5, "name": "HR Officer", "implied_ids": [1]}],
        # _fetch_db_state: resolve xml_ids
        [{"id": 1, "model": "res.groups", "module": "hr", "name": "group_hr_user", "res_id": 1}],
        # _sync_menu_visibility: fetch role backing group
        [{"id": 5, "name": "HR Officer", "group_id": [999, "Role HR Officer"]}],
    ]
    # _sync_menu_visibility: fetch top-level menus (uses execute_kw with full_list context)
    client.execute_kw.return_value = [{"id": 77, "name": "Sales", "excluded_group_ids": []}]
    client.write.return_value = True
    mock_get_client.return_value = client

    result = runner.invoke(roles_app, ["sync", "--file", str(yaml_file)])
    assert result.exit_code == 0, result.output
    # Verify a write was issued to ir.ui.menu
    menu_writes = [c for c in client.write.call_args_list if c.args and c.args[0] == "ir.ui.menu"]
    assert len(menu_writes) == 1
    assert menu_writes[0].args[1] == [77]
    assert menu_writes[0].args[2] == {"excluded_group_ids": [(4, 999)]}


@patch("kctl_odoo.commands.roles._get_client")
def test_roles_sync_menu_visibility_dry_run_no_writes(mock_get_client, tmp_path):
    yaml_file = tmp_path / "roles.yaml"
    yaml_file.write_text(
        "version: 1\n"
        "roles:\n"
        "  hr_user:\n"
        "    name: HR Officer\n"
        "    groups: [hr.group_hr_user]\n"
        "    hide_menus: [Sales]\n"
    )

    client = MagicMock()
    client.search_read.side_effect = [
        [{"id": 5, "name": "HR Officer", "implied_ids": [1]}],
        [{"id": 1, "model": "res.groups", "module": "hr", "name": "group_hr_user", "res_id": 1}],
        [{"id": 5, "name": "HR Officer", "group_id": [999, "Role HR Officer"]}],
    ]
    client.execute_kw.return_value = [{"id": 77, "name": "Sales", "excluded_group_ids": []}]
    mock_get_client.return_value = client

    result = runner.invoke(roles_app, ["sync", "--file", str(yaml_file), "--dry-run"])
    assert result.exit_code == 0
    # No writes to ir.ui.menu in dry-run
    menu_writes = [c for c in client.write.call_args_list if c.args and c.args[0] == "ir.ui.menu"]
    assert menu_writes == []
    assert "Menu visibility plan" in result.stdout or "menu visibility" in result.stdout.lower()


@patch("kctl_odoo.commands.roles._get_client")
def test_roles_apply_csv_dry_run(mock_get_client, tmp_path):
    csv_file = tmp_path / "users_roles.csv"
    csv_file.write_text('login,roles,ous\nintan.rahayu,Branch Staff,"BHO,TSLO1"\n')
    client = MagicMock()
    mock_get_client.return_value = client

    result = runner.invoke(roles_app, ["apply", str(csv_file), "--dry-run"])
    assert result.exit_code == 0
    assert client.write.call_args_list == []


def test_resolve_roles_file_erp_suffix():
    assert _resolve_roles_file("idtpp-mac-odoo-erp", None) == Path("install/roles-erp.yaml")
    assert _resolve_roles_file("idtpp-tpp-odoo-erp", None) == Path("install/roles-erp.yaml")


def test_resolve_roles_file_hrms_suffix():
    assert _resolve_roles_file("idtpp-mac-odoo-hrms", None) == Path("install/roles-hrms.yaml")
    assert _resolve_roles_file("idtpp-tpp-odoo-hrms", None) == Path("install/roles-hrms.yaml")


def test_resolve_roles_file_unknown_profile_raises():
    with pytest.raises(typer.BadParameter) as exc:
        _resolve_roles_file("idtpp-mac-odoo-full", None)
    msg = str(exc.value)
    assert "Cannot auto-detect" in msg
    assert "-odoo-erp" in msg
    assert "-odoo-hrms" in msg


def test_resolve_roles_file_explicit_override_wins():
    custom = Path("custom/path/my-roles.yaml")
    assert _resolve_roles_file("idtpp-mac-odoo-erp", custom) == custom
    assert _resolve_roles_file("idtpp-mac-odoo-full", custom) == custom


def test_resolve_roles_file_staging_suffix_is_unknown():
    with pytest.raises(typer.BadParameter):
        _resolve_roles_file("idtpp-tpp-odoo-hrms-stg", None)


@patch("kctl_odoo.commands.roles._get_client")
def test_sync_auto_detects_erp_file_from_profile(mock_get_client, tmp_path, monkeypatch):
    # Given an ERP profile and install/roles-erp.yaml in cwd.
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    erp_yaml = install_dir / "roles-erp.yaml"
    erp_yaml.write_text("version: 1\nroles:\n  x_role:\n    name: X Role\n    groups: [base.group_user]\n")
    monkeypatch.chdir(tmp_path)

    client = MagicMock()
    client.search_read.side_effect = [
        [],  # existing roles
        [{"id": 1, "model": "res.groups", "module": "base", "name": "group_user", "res_id": 1}],  # xmlid resolve
    ]
    client.create.return_value = 999
    mock_get_client.return_value = client

    # Simulate ctx.obj with profile="idtpp-mac-odoo-erp"
    app_ctx = MagicMock()
    app_ctx.profile = "idtpp-mac-odoo-erp"
    app_ctx.client = client

    result = runner.invoke(roles_app, ["sync"], obj=app_ctx)
    assert result.exit_code == 0, result.output
    # Verify the ERP YAML was loaded by checking the created role name appears
    assert "X Role" in result.stdout or "x_role" in result.stdout.lower()


@patch("kctl_odoo.commands.roles._get_client")
def test_sync_auto_detects_hrms_file_from_profile(mock_get_client, tmp_path, monkeypatch):
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    hrms_yaml = install_dir / "roles-hrms.yaml"
    hrms_yaml.write_text("version: 1\nroles:\n  hr_role:\n    name: HR Role\n    groups: [base.group_user]\n")
    monkeypatch.chdir(tmp_path)

    client = MagicMock()
    client.search_read.side_effect = [
        [],
        [{"id": 1, "model": "res.groups", "module": "base", "name": "group_user", "res_id": 1}],
    ]
    client.create.return_value = 999
    mock_get_client.return_value = client

    app_ctx = MagicMock()
    app_ctx.profile = "idtpp-mac-odoo-hrms"
    app_ctx.client = client

    result = runner.invoke(roles_app, ["sync"], obj=app_ctx)
    assert result.exit_code == 0, result.output
    assert "HR Role" in result.stdout or "hr_role" in result.stdout.lower()


@patch("kctl_odoo.commands.roles._get_client")
def test_sync_errors_on_unknown_profile_without_file(mock_get_client):
    client = MagicMock()
    mock_get_client.return_value = client
    app_ctx = MagicMock()
    app_ctx.profile = "idtpp-mac-odoo-full"
    app_ctx.client = client

    result = runner.invoke(roles_app, ["sync"], obj=app_ctx)
    assert result.exit_code != 0
    combined = (result.stdout or "") + (result.stderr or "")
    assert "Cannot auto-detect" in combined or "cannot auto-detect" in combined.lower()


@patch("kctl_odoo.commands.roles._get_client")
def test_roles_example_prints_role_profile(mock_get_client, tmp_path, monkeypatch):
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    examples_yaml = install_dir / "roles-hrms.examples.yaml"
    examples_yaml.write_text(
        "version: 1\n"
        "examples:\n"
        "  hr_user:\n"
        "    typical_title: HR Officer\n"
        "    responsibilities:\n"
        "      - Manage all employees\n"
        "      - Approve time-off\n"
        "    real_examples_mac: []\n"
        "    real_examples_tpp: []\n"
        "    must_see_apps: [HRM, Employees]\n"
        "    must_not_see_apps: [Settings]\n"
        "    typical_ou_arg: '--ous \"*\"'\n"
        "    capabilities:\n"
        "      can: [Create employees]\n"
        "      cannot: [Install modules]\n"
        "    acceptance_checklist: [Login works]\n"
    )
    monkeypatch.chdir(tmp_path)

    app_ctx = MagicMock()
    app_ctx.profile = "idtpp-mac-odoo-hrms"
    app_ctx.client = MagicMock()
    mock_get_client.return_value = app_ctx.client

    result = runner.invoke(roles_app, ["example", "hr_user"], obj=app_ctx)
    assert result.exit_code == 0, result.output
    assert "HR Officer" in result.stdout
    assert "Manage all employees" in result.stdout
    assert "HRM" in result.stdout
    assert "Create employees" in result.stdout
    assert "Login works" in result.stdout


@patch("kctl_odoo.commands.roles._get_client")
def test_roles_example_errors_on_unknown_role(mock_get_client, tmp_path, monkeypatch):
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    examples_yaml = install_dir / "roles-hrms.examples.yaml"
    examples_yaml.write_text("version: 1\nexamples:\n  hr_user:\n    typical_title: HR Officer\n")
    monkeypatch.chdir(tmp_path)

    app_ctx = MagicMock()
    app_ctx.profile = "idtpp-mac-odoo-hrms"
    app_ctx.client = MagicMock()
    mock_get_client.return_value = app_ctx.client

    result = runner.invoke(roles_app, ["example", "ghost_role"], obj=app_ctx)
    assert result.exit_code != 0
    combined = (result.stdout or "") + (result.stderr or "")
    assert "not found" in combined.lower() or "ghost_role" in combined


@patch("kctl_odoo.commands.roles._get_client")
def test_roles_example_errors_on_unknown_profile_without_file(mock_get_client):
    app_ctx = MagicMock()
    app_ctx.profile = "idtpp-mac-odoo-full"
    app_ctx.client = MagicMock()
    mock_get_client.return_value = app_ctx.client

    result = runner.invoke(roles_app, ["example", "hr_user"], obj=app_ctx)
    assert result.exit_code != 0
    combined = (result.stdout or "") + (result.stderr or "")
    assert "Cannot auto-detect" in combined or "cannot auto-detect" in combined.lower()
