"""Tests for automation command group."""

from __future__ import annotations

from kctl_pg.commands.automation import _alert_style, _dead_style, _schedule_style


def test_dead_style_critical():
    assert "[red]" in _dead_style(25.0)


def test_dead_style_warning():
    assert "[yellow]" in _dead_style(15.0)


def test_dead_style_ok():
    assert "[green]" in _dead_style(5.0)


def test_schedule_style_daily():
    assert "[red]" in _schedule_style("daily")


def test_schedule_style_weekly():
    assert "[yellow]" in _schedule_style("weekly")


def test_schedule_style_monthly():
    assert "[green]" in _schedule_style("monthly")


def test_alert_style_alert():
    assert "[red]" in _alert_style("ALERT")


def test_alert_style_ok():
    assert "[green]" in _alert_style("OK")


def test_alert_style_na():
    assert "[dim]" in _alert_style("N/A")
