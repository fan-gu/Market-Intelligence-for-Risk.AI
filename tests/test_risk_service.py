from datetime import date

import pytest

from mirai.risk_service import RiskDataError, RiskDataService, classify_limit


def test_limit_classification_thresholds():
    assert classify_limit(79.99) == "OK"
    assert classify_limit(80.0) == "WARNING"
    assert classify_limit(99.99) == "WARNING"
    assert classify_limit(100.0) == "BREACH"


def test_latest_summary_has_governed_metrics():
    summary = RiskDataService.from_default_data().get_summary()
    assert summary["run_id"].startswith("DEMO-RUN-")
    assert summary["hvar"]["limit"] > 0
    assert summary["svar"]["limit"] == summary["hvar"]["limit"] * 1.5


def test_summary_uses_latest_available_run_before_requested_date():
    service = RiskDataService.from_default_data()
    summary = service.get_summary(date(2026, 8, 23))
    assert summary["as_of_date"].isoformat() == "2026-08-21"


def test_summary_rejects_date_before_first_run():
    with pytest.raises(RiskDataError):
        RiskDataService.from_default_data().get_summary(date(2000, 1, 1))


def test_scenario_is_explicitly_non_official():
    result = RiskDataService.from_default_data().run_scenario(
        as_of_date=None,
        rate_shock_bp=100,
        fx_spot_move_pct=0,
        volatility_shock_pct=0,
        severity="Adverse",
    )
    assert result["is_official_risk_result"] is False
    assert result["estimated_pnl"] <= 0
