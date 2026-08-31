"""M.R. AI Agent V18: multi-metric limit governance."""

from archive.versions import market_risk_agent_v17 as v17
from google.genai import types


VERSION = "V18"
v17.v9.VERSION = VERSION
v16 = v17.v16
v15 = v17.v15
v14 = v17.v14
v13 = v17.v13
v12 = v17.v12
v11 = v17.v11
v9 = v17.v9
v8 = v17.v8
build_supplied_stress_frame = v17.build_supplied_stress_frame
get_market_sensitivities = v17.get_market_sensitivities
get_stress_evolution = v17.get_stress_evolution

WARNING_THRESHOLD_PCT = 80.0
BREACH_THRESHOLD_PCT = 100.0


def _limit_record(family, metric, exposure, limit, unit, owner, basis):
    consumption = 0.0 if limit == 0 else float(exposure) / float(limit) * 100.0
    if consumption >= BREACH_THRESHOLD_PCT:
        status = "BREACH"
        escalation = "Immediate escalation required"
    elif consumption >= WARNING_THRESHOLD_PCT:
        status = "WARNING"
        escalation = "Owner review required"
    else:
        status = "OK"
        escalation = "No escalation"
    return {
        "family": family,
        "metric": metric,
        "exposure": float(exposure),
        "limit": float(limit),
        "unit": unit,
        "consumption_pct": consumption,
        "warning_threshold_pct": WARNING_THRESHOLD_PCT,
        "breach_threshold_pct": BREACH_THRESHOLD_PCT,
        "status": status,
        "owner": owner,
        "consumption_basis": basis,
        "escalation_status": escalation,
    }


def evaluate_all_limits():
    """Evaluate the principal V18 market-risk limit families."""
    current = v8.get_current_risk()
    row = v8.df.iloc[-1]
    stress_frame, _ = v17.build_supplied_stress_frame()
    worst_stress_loss = abs(min(0.0, float(stress_frame.iloc[-1].drop(labels="cob_date").min())))

    sensitivity_rows = v17.get_market_sensitivities()["sensitivities"]
    gross_ir_dv01 = sum(abs(item["value"]) for item in sensitivity_rows if item["measure"] == "IR Delta (DV01)")
    ir_gamma = sum(abs(item["value"]) for item in sensitivity_rows if item["measure"] == "IR Gamma")
    fx_delta = sum(abs(item["value"]) for item in sensitivity_rows if item["measure"] == "FX Delta")
    gross_vega = sum(abs(item["value"]) for item in sensitivity_rows if item["measure"] == "Vega")

    limits = [
        _limit_record("VaR", "Historical VaR (1 day, 99%)", current["var_hist"], current["var_limit"], "EUR", "Market Risk", "Current exposure"),
        _limit_record("VaR", "Stressed VaR (1 day, 99%)", current["stressed_var"], 10_000_000, "EUR", "Market Risk", "Current exposure"),
        _limit_record("Stress", "Worst supplied scenario loss", worst_stress_loss, 15_000_000, "EUR loss", "Stress Testing", "Absolute loss"),
        _limit_record("Sensitivity", "Gross IR Delta (DV01)", gross_ir_dv01, 250_000, "EUR / bp", "Rates Risk", "Gross absolute sensitivity"),
        _limit_record("Sensitivity", "IR Gamma", ir_gamma, 5_000, "EUR / bp²", "Rates Risk", "Absolute sensitivity"),
        _limit_record("Sensitivity", "Gross FX Delta", fx_delta, 500_000, "EUR / 1% spot", "FX Risk", "Gross absolute sensitivity"),
        _limit_record("Sensitivity", "Gross Vega", gross_vega, 150_000, "EUR / vol point", "Volatility Risk", "Gross absolute sensitivity"),
        _limit_record("P&L", "Daily actual loss", max(0.0, -float(row["actual_pnl"])), 1_000_000, "EUR loss", "P&L Control", "Loss only"),
        _limit_record("P&L", "Absolute unexplained P&L", abs(float(row["unexplained_pnl"])), 250_000, "EUR", "P&L Control", "Absolute amount"),
        _limit_record("Backtesting", "250-day exceptions", float(row["backtest_exception_count_250d"]), 4.0, "Exceptions", "Market Risk", "Exception count"),
    ]
    return {
        "as_of_date": current["date"],
        "warning_threshold_pct": WARNING_THRESHOLD_PCT,
        "breach_threshold_pct": BREACH_THRESHOLD_PCT,
        "summary": {
            "breaches": sum(item["status"] == "BREACH" for item in limits),
            "warnings": sum(item["status"] == "WARNING" for item in limits),
            "ok": sum(item["status"] == "OK" for item in limits),
        },
        "limits": limits,
        "usage_note": (
            "V18 demo limits cover the principal supplied metrics. Limits and owners are configurable prototype values, "
            "not approved production mandates."
        ),
    }


v8.TOOL_FUNCTIONS.pop("evaluate_limit_breaches", None)
v8.TOOL_DESCRIPTIONS.pop("evaluate_limit_breaches", None)
v8.TOOL_FUNCTIONS["evaluate_all_limits"] = evaluate_all_limits
v8.TOOL_DESCRIPTIONS["evaluate_all_limits"] = (
    "Multi-metric market-risk limits with 80% warning, 100% breach, owners and escalation status."
)
v9.SYSTEM_INSTRUCTION += """

V18 limit governance:
- Use evaluate_all_limits for VaR, SVaR, stress, sensitivity, P&L and backtesting controls.
- Consumption below 80% is OK; 80% to below 100% is WARNING; 100% or above is BREACH.
- State that V18 thresholds and owners are configurable demo values, not approved production mandates.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v17.ask_risk_agent
