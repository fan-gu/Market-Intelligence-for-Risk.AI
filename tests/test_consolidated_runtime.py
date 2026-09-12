import sys

from mirai import runtime


def test_runtime_does_not_import_archived_versions():
    assert not [name for name in sys.modules if name.startswith("archive.versions")]


def test_consolidated_data_contracts():
    assert runtime.VERSION == "V33"
    assert len(runtime.df) == 260
    assert len(runtime.get_market_sensitivities()["sensitivities"]) == 493
    assert runtime.validate_data()["business_date_sequence_ok"] is True


def test_governance_has_no_more_than_three_demo_breaches():
    result = runtime.evaluate_all_limits()
    assert result["summary"]["breaches"] <= 3
    assert result["summary"]["warnings"] >= 1


def test_scenario_is_deterministic():
    parameters = {
        "rate_currency": "EUR",
        "parallel_shift_bp": 50,
        "fx_pair": "EUR/USD",
        "fx_spot_move_pct": -5,
        "volatility_shift_points": 5,
        "horizon_days": 1,
    }
    first = runtime.run_interactive_scenario(**parameters)
    second = runtime.run_interactive_scenario(**parameters)
    assert first["scenario_id"] == second["scenario_id"]
    assert first["scenario"] == second["scenario"]
