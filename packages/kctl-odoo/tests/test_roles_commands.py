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
