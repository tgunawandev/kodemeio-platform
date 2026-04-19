from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_odoo.commands.roles import app as roles_app

runner = CliRunner()


@patch("kctl_odoo.commands.roles._get_client")
def test_roles_list_shows_roles_with_user_counts(mock_get_client):
    client = MagicMock()
    client.execute.side_effect = [
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
    client.execute.side_effect = [
        [{"id": 1, "name": "Branch Staff", "implied_ids": [10, 20]}],
        [
            {"id": 10, "name": "POS User", "full_name": "Point of Sale / User"},
            {"id": 20, "name": "Stock User", "full_name": "Inventory / User"},
        ],
        [{"user_id": [46, "intan"]}],
    ]
    mock_get_client.return_value = client
    result = runner.invoke(roles_app, ["show", "Branch Staff"])
    assert result.exit_code == 0
    assert "Point of Sale / User" in result.stdout
    assert "intan" in result.stdout


@patch("kctl_odoo.commands.roles._get_client")
def test_roles_show_errors_on_unknown_role(mock_get_client):
    client = MagicMock()
    client.execute.return_value = []
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
    client.execute.side_effect = [
        [],
        [{"id": 1, "model": "res.groups", "module": "sales_team", "name": "group_sale_salesman", "res_id": 42}],
    ]
    mock_get_client.return_value = client

    result = runner.invoke(roles_app, ["sync", "--file", str(yaml_file), "--dry-run"])
    assert result.exit_code == 0
    assert "create" in result.stdout.lower()
    assert "sales user" in result.stdout.lower() or "sales_user" in result.stdout.lower()
    write_methods_called = [
        call.args[1]
        for call in client.execute.call_args_list
        if len(call.args) >= 2 and call.args[1] in ("create", "write", "unlink")
    ]
    assert write_methods_called == []


@patch("kctl_odoo.commands.roles._get_client")
def test_roles_sync_applies_create(mock_get_client, tmp_path):
    yaml_file = tmp_path / "roles.yaml"
    yaml_file.write_text(
        "version: 1\nroles:\n  sales_user:\n    name: Sales User\n    groups: [sales_team.group_sale_salesman]\n"
    )

    client = MagicMock()
    client.execute.side_effect = [
        [],
        [{"id": 1, "model": "res.groups", "module": "sales_team", "name": "group_sale_salesman", "res_id": 42}],
        999,
    ]
    mock_get_client.return_value = client

    result = runner.invoke(roles_app, ["sync", "--file", str(yaml_file)])
    assert result.exit_code == 0
    create_calls = [
        call
        for call in client.execute.call_args_list
        if len(call.args) >= 2 and call.args[0] == "res.users.role" and call.args[1] == "create"
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
    client.execute.side_effect = [
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
    client.execute.side_effect = [
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
    client.execute.side_effect = [
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
    client.execute.side_effect = [
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
    client.execute.side_effect = [
        [{"id": 99, "full_name": "Fleet / Manager"}],
        [{"id": 11, "model": "res.groups", "module": "fleet", "name": "fleet_manager", "res_id": 99}],
    ]
    mock_get_client.return_value = client

    result = runner.invoke(
        roles_app,
        ["audit", "--file", str(yaml_file), "--ignored-file", str(ignored_file), "--strict"],
    )
    assert result.exit_code != 0
