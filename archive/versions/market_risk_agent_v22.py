"""M.R. AI Agent V22: deterministic run comparison and expanded governed risk sets."""

from __future__ import annotations

import re

import pandas as pd
from google.genai import types

from archive.versions import market_risk_agent_v21 as v21


VERSION = "V22"
v21.v9.VERSION = VERSION
v20 = v21.v20
v19 = v21.v19
v18 = v21.v18
v17 = v21.v17
v16 = v21.v16
v15 = v21.v15
v14 = v21.v14
v13 = v21.v13
v12 = v21.v12
v11 = v21.v11
v9 = v21.v9
v8 = v21.v8
DRIVER_COLUMNS = v21.DRIVER_COLUMNS
build_pla_demo_history = v21.build_pla_demo_history
evaluate_pla_test = v21.evaluate_pla_test
evaluate_all_limits = v21.evaluate_all_limits
evaluate_pnl_explain_alerts = v21.evaluate_pnl_explain_alerts
build_supplied_stress_frame = v21.build_supplied_stress_frame
get_stress_evolution = v21.get_stress_evolution
get_material_stress_scenarios = v21.get_material_stress_scenarios

INFLATION_CURVES = [
    ("EUR", "EUR HICPxT", -12_000, 155, -4_200),
    ("USD", "USD CPI", 9_500, 130, 3_600),
    ("JPY", "JPY CPI", -3_800, 55, -1_100),
    ("GBP", "GBP RPI", 7_200, 95, 2_500),
]

ADDITIONAL_STRESS_CONFIGURATIONS = [
    {"scenario": "Credit +150 bp", "category": "Adverse", "shock": "+150 bp parallel credit-spread widening", "derived_from": "", "pricing_status": "Awaiting risk-engine revaluation"},
    {"scenario": "Equity -30%", "category": "Adverse", "shock": "-30% global equity spot", "derived_from": "", "pricing_status": "Awaiting risk-engine revaluation"},
    {"scenario": "EUR/USD -15%", "category": "Adverse", "shock": "-15% EUR/USD spot", "derived_from": "", "pricing_status": "Awaiting risk-engine revaluation"},
    {"scenario": "Basis +50 bp", "category": "Adverse", "shock": "+50 bp cross-currency basis widening", "derived_from": "", "pricing_status": "Awaiting risk-engine revaluation"},
    {"scenario": "Credit +300 bp", "category": "Extreme", "shock": "+300 bp parallel credit-spread widening", "derived_from": "Credit +150 bp", "pricing_status": "Awaiting risk-engine revaluation"},
    {"scenario": "Equity -60%", "category": "Extreme", "shock": "-60% global equity spot", "derived_from": "Equity -30%", "pricing_status": "Awaiting risk-engine revaluation"},
    {"scenario": "EUR/USD -30%", "category": "Extreme", "shock": "-30% EUR/USD spot", "derived_from": "EUR/USD -15%", "pricing_status": "Awaiting risk-engine revaluation"},
    {"scenario": "Basis +100 bp", "category": "Extreme", "shock": "+100 bp cross-currency basis widening", "derived_from": "Basis +50 bp", "pricing_status": "Awaiting risk-engine revaluation"},
]


def get_market_sensitivities():
    """Return V21 sensitivities plus one governed Inflation curve family."""
    result = v21.get_market_sensitivities()
    rows = list(result["sensitivities"])
    for currency, curve, delta, gamma, vega in INFLATION_CURVES:
        rows.extend([
            {
                "risk_class": "Rates",
                "measure": "IR Delta (DV01)",
                "currency": currency,
                "curve_type": "Inflation",
                "curve": curve,
                "value": float(delta),
                "unit": "EUR / bp",
                "definition": "P&L change for a +1 bp move in the named inflation curve.",
            },
            {
                "risk_class": "Rates",
                "measure": "IR Gamma",
                "currency": currency,
                "curve_type": "Inflation",
                "curve": curve,
                "value": float(gamma),
                "unit": "EUR / bp²",
                "definition": "Change in inflation-curve DV01 for a +1 bp move.",
            },
            {
                "risk_class": "Rates",
                "measure": "Vega",
                "currency": currency,
                "curve_type": "Inflation",
                "curve": curve,
                "value": float(vega),
                "unit": "EUR / vol point",
                "definition": "P&L change for a +1 percentage-point move in inflation-option volatility.",
            },
        ])
    return {
        **result,
        "sensitivities": rows,
        "curve_families": ["OIS", "BOR", "Inflation"],
        "usage_note": (
            "Deterministic synthetic V22 sensitivity feed across EUR, USD, JPY and GBP. "
            "Rates are grouped into OIS, BOR and Inflation curve families; replace with governed risk-engine records in production."
        ),
    }


def get_stress_scenario_catalog():
    """Return priced and configured scenarios across the four governance categories."""
    return v21.get_stress_scenario_catalog() + ADDITIONAL_STRESS_CONFIGURATIONS


def get_var_change_summary(as_of_date=None):
    """Return Historical VaR changes over daily, weekly and monthly horizons."""
    frame = v8.df[["cob_date", "var_1d_99_hist"]].sort_values("cob_date").reset_index(drop=True)
    if frame.empty:
        return {"status": "NO_DATA", "comparisons": []}

    requested_date = pd.Timestamp(as_of_date) if as_of_date is not None else frame.iloc[-1]["cob_date"]
    eligible = frame.index[frame["cob_date"] <= requested_date].tolist()
    if not eligible:
        return {"status": "NO_DATA_ON_OR_BEFORE_DATE", "comparisons": []}

    current_position = eligible[-1]
    current = frame.iloc[current_position]
    current_date = pd.Timestamp(current["cob_date"])
    current_value = float(current["var_1d_99_hist"])

    horizons = [
        ("Daily", None),
        ("Weekly", current_date - pd.Timedelta(days=7)),
        ("Monthly", current_date - pd.DateOffset(months=1)),
    ]
    comparisons = []
    for period, target_date in horizons:
        if period == "Daily":
            reference_position = current_position - 1
            reference = frame.iloc[reference_position] if reference_position >= 0 else None
        else:
            candidates = frame.loc[frame["cob_date"] <= target_date]
            reference = candidates.iloc[-1] if not candidates.empty else None

        if reference is None:
            comparisons.append({
                "period": period,
                "available": False,
                "reference_date": None,
                "reference_value": None,
                "change": None,
                "change_pct": None,
                "reason": f"Insufficient history for a {period.lower()} comparison.",
            })
            continue

        reference_value = float(reference["var_1d_99_hist"])
        change = current_value - reference_value
        comparisons.append({
            "period": period,
            "available": True,
            "reference_date": str(pd.Timestamp(reference["cob_date"]).date()),
            "reference_value": reference_value,
            "change": change,
            "change_pct": None if reference_value == 0 else change / abs(reference_value) * 100.0,
            "reason": "",
        })

    return {
        "status": "AVAILABLE",
        "as_of_date": str(current_date.date()),
        "current_var": current_value,
        "comparisons": comparisons,
        "usage_note": (
            "Daily uses the preceding business-day observation. Weekly and monthly use the latest available "
            "business-day observation on or before the target calendar date."
        ),
    }

v8.TOOL_FUNCTIONS["get_market_sensitivities"] = get_market_sensitivities
v8.TOOL_DESCRIPTIONS["get_market_sensitivities"] = "IR Delta, Gamma and Vega across OIS, BOR and Inflation curves, plus FX Delta and Theta."
v8.TOOL_FUNCTIONS["get_stress_scenario_catalog"] = get_stress_scenario_catalog
v8.TOOL_DESCRIPTIONS["get_stress_scenario_catalog"] = "Governed Historical, Hypothetical, Adverse and Extreme scenario catalogue, including unpriced configurations."
v8.TOOL_FUNCTIONS.pop("compare_risk_runs", None)
v8.TOOL_DESCRIPTIONS.pop("compare_risk_runs", None)
v8.TOOL_FUNCTIONS["get_var_change_summary"] = get_var_change_summary
v8.TOOL_DESCRIPTIONS["get_var_change_summary"] = "Historical VaR changes over daily, weekly and monthly horizons for the selected as-of date."

v9.SYSTEM_INSTRUCTION += """

V22 controls:
- Use get_var_change_summary for deterministic Historical VaR changes over daily, weekly and monthly horizons.
- The additional Adverse and Extreme configurations are unpriced until risk-engine revaluation; never infer their P&L by scaling another result.
- The Inflation sensitivity family is deterministic synthetic demo data and must be labelled as such.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v21.ask_risk_agent
