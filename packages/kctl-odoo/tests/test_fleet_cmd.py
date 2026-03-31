"""Tests for fleet command group."""

from __future__ import annotations

from unittest.mock import MagicMock

import typer

from kctl_odoo.core.callbacks import AppContext


def _make_actx(client: MagicMock | None = None) -> AppContext:
    actx = MagicMock(spec=AppContext)
    actx.json_mode = False
    actx.client = client or MagicMock()
    from kctl_lib import Output

    actx.output = Output(json_mode=False)
    return actx


def _make_ctx(actx: AppContext) -> typer.Context:
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = actx
    return ctx


class TestFleetImport:
    def test_import_app(self) -> None:
        from kctl_odoo.commands.fleet_cmd import app

        assert app is not None


class TestFleetSummary:
    def test_summary_no_fleet(self) -> None:
        """summary should handle fleet not installed."""
        c = MagicMock()
        c.search_count.return_value = 0
        actx = _make_actx(client=c)
        from kctl_odoo.commands.fleet_cmd import summary

        ctx = _make_ctx(actx)
        summary(ctx)

    def test_summary_with_data(self) -> None:
        """summary should display vehicle and contract counts."""
        c = MagicMock()
        # model_available(fleet.vehicle) -> 1
        # vehicle_count search_count -> 5
        # model_available(fleet.vehicle.log.contract) -> 1
        # expiring_count search_count -> 3
        # model_available(fleet.vehicle.log.services) -> 1
        # services_due search_count -> 2
        c.search_count.side_effect = [1, 5, 1, 3, 1, 2]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.fleet_cmd import summary

        ctx = _make_ctx(actx)
        summary(ctx)


class TestFleetVehicles:
    def test_vehicles_empty(self) -> None:
        """vehicles should handle no results."""
        c = MagicMock()
        c.search_count.return_value = 1  # model_available -> True
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.fleet_cmd import vehicles

        ctx = _make_ctx(actx)
        vehicles(ctx, state=None, driver=None, limit=50)

    def test_vehicles_no_fleet(self) -> None:
        """vehicles should handle fleet not installed."""
        c = MagicMock()
        c.search_count.return_value = 0
        actx = _make_actx(client=c)
        from kctl_odoo.commands.fleet_cmd import vehicles

        ctx = _make_ctx(actx)
        vehicles(ctx, state=None, driver=None, limit=50)

    def test_vehicles_with_results(self) -> None:
        """vehicles should display results table."""
        c = MagicMock()
        c.search_count.return_value = 3
        c.search_read.return_value = [
            {
                "id": 1,
                "name": "Fleet/001",
                "driver_id": [5, "John Doe"],
                "state_id": [1, "Active"],
                "license_plate": "B 1234 AB",
                "model_id": [2, "Toyota Avanza"],
                "odometer": 45000.0,
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.fleet_cmd import vehicles

        ctx = _make_ctx(actx)
        vehicles(ctx, state="Active", driver=None, limit=10)


class TestFleetContracts:
    def test_contracts_empty(self) -> None:
        """contracts should handle no results."""
        c = MagicMock()
        c.search_count.return_value = 1
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.fleet_cmd import contracts

        ctx = _make_ctx(actx)
        contracts(ctx, expiring_days=30, limit=50)

    def test_contracts_with_results(self) -> None:
        """contracts should display expiring contracts."""
        c = MagicMock()
        c.search_count.return_value = 2
        c.search_read.return_value = [
            {
                "id": 1,
                "name": "Insurance 2026",
                "vehicle_id": [1, "Fleet/001"],
                "expiration_date": "2026-04-15",
                "state_id": [1, "Open"],
                "amount": 5000000.0,
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.fleet_cmd import contracts

        ctx = _make_ctx(actx)
        contracts(ctx, expiring_days=30, limit=50)


class TestFleetCosts:
    def test_costs_empty(self) -> None:
        """costs should handle no results."""
        c = MagicMock()
        c.search_count.return_value = 1
        c.read_group.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.fleet_cmd import costs

        ctx = _make_ctx(actx)
        costs(ctx, vehicle=None, period="month")

    def test_costs_with_results(self) -> None:
        """costs should display grouped costs."""
        c = MagicMock()
        c.search_count.return_value = 5
        c.read_group.return_value = [
            {"vehicle_id": [1, "Fleet/001"], "amount": 1500000.0, "__count": 3},
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.fleet_cmd import costs

        ctx = _make_ctx(actx)
        costs(ctx, vehicle=None, period="year")
